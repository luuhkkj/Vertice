"""
Executor do pipeline de inferência de risco acadêmico do Vértice.

Fluxo simplificado com credencial técnica única (`VERTICE_ML_SERVICE_TOKEN`):
1. Extrai atributos anonimizados do corte inicial e metadados da credencial (`escola_id`, `modelo_nome`).
2. Localiza no registro central (`catalogo_modelos.py`) o artefato correspondente ao modelo autorizado.
3. Valida e transforma os registros com proteção estrita contra Data Leakage.
4. Executa inferência local (`modelo_risco.prever_risco()`) e valida as saídas.
5. Em modo `--send`, envia previsões via `POST /api/v1/previsoes/lote` usando o mesmo `X-Service-Token`.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from pathlib import Path
import sys
import time
from typing import Any, Optional
import uuid

from pydantic import ValidationError

from app.integrations.prediction import catalogo_modelos, modelo_risco
from app.integrations.prediction.leakage import (
    validar_metadados_tecnicos,
    validar_variaveis_contra_leakage,
)
from app.integrations.prediction.pipeline.cliente_api import (
    ClienteAPIPrevisoes,
    ErroEnvioPipeline,
    PrevisaoItemEnvio,
    ResultadoEnvioAPI,
)
from app.integrations.prediction.pipeline.config import (
    ErroConfiguracaoPipeline,
    PipelineMLConfig,
    sanitizar_texto_segredos,
)
from app.integrations.prediction.pipeline.extrator import (
    ErroExtracaoPipeline,
    ExtratorDadosInferencia,
)
from app.integrations.prediction.pipeline.transformador import (
    ErroTransformacaoLeakage,
    RegistroInferenciaTransformado,
    ResultadoTransformacao,
    TransformadorDadosInferencia,
)

logger = logging.getLogger(__name__)

FAIXAS_SAIDA_VALIDAS = {"BAIXO", "MODERADO", "ALTO", "CRITICO"}


class ErroArtefatoModelo(RuntimeError):
    """Artefato `.joblib` ausente, corrompido ou incompatível com o modelo autorizado."""


class ErroInferenciaModelo(RuntimeError):
    """Saída inválida ou falha na execução do modelo local de risco."""


@dataclass(frozen=True)
class InfoArtefatoModelo:
    """Metadados técnicos verificados do artefato carregado."""

    caminho: Path
    modelo_nome: str
    versao_modelo: str
    politica_classificacao_versao: str
    tipo_previsao: str
    features: list[str]
    sha256: str
    tamanho_bytes: int


@dataclass
class RelatorioExecucaoPipeline:
    """Relatório estruturado de observabilidade de uma execução do pipeline ML."""

    execucao_id: str
    modo: str
    sucesso: bool
    inicio_em: datetime
    fim_em: datetime
    duracao_ms: float
    escola_id: Optional[str] = None
    periodo_letivo: str = "1º Bimestre"
    modelo_nome: Optional[str] = None
    modelo_versao: Optional[str] = None
    etapa_falha: Optional[str] = None
    erro: Optional[str] = None
    extraidos: int = 0
    validos: int = 0
    rejeitados_transformacao: int = 0
    motivos_rejeicao: dict[str, int] = field(default_factory=dict)
    sem_previsao_valida: int = 0
    inferidos: int = 0
    enviados: int = 0
    persistidos: int = 0
    lotes_enviados: int = 0

    def to_dict(self) -> dict[str, Any]:
        dados = asdict(self)
        dados["inicio_em"] = self.inicio_em.isoformat()
        dados["fim_em"] = self.fim_em.isoformat()
        return dados


def _calcular_sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        while True:
            bloco = f.read(65536)
            if not bloco:
                break
            h.update(bloco)
    return h.hexdigest()


def inspecionar_artefato_modelo(
    modelo_nome: str = "regressao_logistica",
    *,
    diretorio_artefatos: Optional[Path] = None,
) -> InfoArtefatoModelo:
    """
    Resolve e valida o artefato `.joblib` do modelo autorizado via registro central,
    sem treinar automaticamente e sem substituir silenciosamente por outro modelo.
    """
    descritor, caminho_resolvido = catalogo_modelos.resolver_caminho_artefato_modelo(
        modelo_nome,
        diretorio_artefatos=diretorio_artefatos,
    )
    try:
        artefato = modelo_risco._carregar_artefato(
            str(caminho_resolvido),
            caminho_resolvido.stat().st_mtime_ns,
        )
    except Exception as exc:
        raise ErroArtefatoModelo(
            f"Falha ao carregar/validar artefato do modelo `{modelo_nome}` em "
            f"`{caminho_resolvido}`: {exc}"
        ) from exc

    versao_modelo = str(artefato.get("versao_modelo") or descritor.modelo_versao).strip()
    features = [str(f) for f in (artefato.get("features") or [])]

    return InfoArtefatoModelo(
        caminho=caminho_resolvido,
        modelo_nome=descritor.modelo_nome,
        versao_modelo=versao_modelo,
        politica_classificacao_versao=descritor.politica_classificacao_versao,
        tipo_previsao=descritor.tipo_previsao,
        features=features,
        sha256=_calcular_sha256_arquivo(caminho_resolvido),
        tamanho_bytes=caminho_resolvido.stat().st_size,
    )


class ExecutorPipelineML:
    """Orquestrador ponta a ponta com descoberta automática de escola e modelo."""

    def __init__(
        self,
        config: PipelineMLConfig,
        *,
        http_client: Optional[Any] = None,
        diretorio_artefatos: Optional[Path] = None,
    ) -> None:
        self.config = config
        self.http_client = http_client
        self.diretorio_artefatos = diretorio_artefatos

    def verificar_modelo(
        self,
        modelo_nome: str = "regressao_logistica",
    ) -> InfoArtefatoModelo:
        """Valida o carregamento de um modelo registrado sem executar envio."""
        return inspecionar_artefato_modelo(
            modelo_nome,
            diretorio_artefatos=self.diretorio_artefatos,
        )

    def executar(
        self,
        *,
        enviar: bool = False,
        registros_locais: Optional[Sequence[Mapping[str, Any]]] = None,
        escola_id_local: Optional[uuid.UUID] = None,
        modelo_nome_local: Optional[str] = None,
        execucao_id: Optional[str] = None,
    ) -> RelatorioExecucaoPipeline:
        """
        Executa o pipeline completo:
        - `enviar=False` (`--dry-run`): consulta API (ou amostra local opcional),
          identifica escola e modelo vinculados ao token, executa inferência e valida o
          schema da API sem persistir previsões.
        - `enviar=True` (`--send`): executa o fluxo completo e envia à API via `X-Service-Token`.
        """
        inicio = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        id_execucao = execucao_id or f"pipe-{uuid.uuid4().hex[:16]}"
        modo = "send" if enviar else "dry-run"

        etapa_atual = "configuracao"
        escola_alvo: Optional[uuid.UUID] = escola_id_local
        modelo_nome_alvo: Optional[str] = modelo_nome_local
        info_modelo: Optional[InfoArtefatoModelo] = None
        extraidos = 0
        validos = 0
        rejeitados_transf = 0
        motivos_rej: dict[str, int] = {}
        sem_prev_valida = 0
        inferidos = 0
        enviados = 0
        persistidos = 0
        lotes_enviados = 0

        try:
            if enviar or registros_locais is None:
                self.config.validar_configuracao()

            if registros_locais is not None:
                etapa_atual = "extracao"
                registros_brutos = list(registros_locais)
                if modelo_nome_alvo is None:
                    modelos_disp = catalogo_modelos.listar_modelos_preditivos(
                        apenas_disponiveis=True,
                        diretorio_artefatos=self.diretorio_artefatos,
                    )
                    if not modelos_disp:
                        raise FileNotFoundError(
                            "Nenhum modelo preditivo compatível encontrado para execução local. "
                            "Treine o modelo executando `python -m app.integrations.prediction.treinar_modelo_risco`."
                        )
                    modelo_nome_alvo = modelos_disp[0].modelo_nome
            else:
                etapa_atual = "extracao"
                extrator = ExtratorDadosInferencia(
                    self.config,
                    http_client=self.http_client,
                )
                res_extracao = extrator.extrair()
                registros_brutos = res_extracao.registros
                escola_alvo = res_extracao.escola_id
                modelo_nome_alvo = res_extracao.modelo_nome

            extraidos = len(registros_brutos)

            # Sempre valida a disponibilidade do modelo associado à credencial (mesmo se extraidos == 0),
            # interrompendo com erro claro caso o artefato associado não esteja disponível.
            etapa_atual = "carregamento_modelo"
            assert modelo_nome_alvo is not None
            info_modelo = self.verificar_modelo(modelo_nome_alvo)

            if extraidos == 0:
                fim = datetime.now(timezone.utc)
                duracao_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                rel = RelatorioExecucaoPipeline(
                    execucao_id=id_execucao,
                    modo=modo,
                    sucesso=True,
                    inicio_em=inicio,
                    fim_em=fim,
                    duracao_ms=duracao_ms,
                    escola_id=str(escola_alvo) if escola_alvo else None,
                    periodo_letivo=self.config.periodo_letivo,
                    modelo_nome=info_modelo.modelo_nome,
                    modelo_versao=info_modelo.versao_modelo,
                    extraidos=0,
                )
                logger.info(
                    "Execução pipeline ML concluída sem registros | execucao_id=%s | modo=%s | modelo=%s",
                    id_execucao,
                    modo,
                    info_modelo.modelo_nome,
                )
                return rel

            etapa_atual = "transformacao"
            transformador = TransformadorDadosInferencia(
                escola_id_esperada=escola_alvo
            )
            res_transf: ResultadoTransformacao = transformador.transformar(registros_brutos)
            validos = res_transf.total_validos
            rejeitados_transf = res_transf.total_rejeitados
            motivos_rej = res_transf.resumo_motivos

            if validos == 0:
                fim = datetime.now(timezone.utc)
                duracao_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                rel = RelatorioExecucaoPipeline(
                    execucao_id=id_execucao,
                    modo=modo,
                    sucesso=True,
                    inicio_em=inicio,
                    fim_em=fim,
                    duracao_ms=duracao_ms,
                    escola_id=str(escola_alvo) if escola_alvo else None,
                    periodo_letivo=self.config.periodo_letivo,
                    modelo_nome=info_modelo.modelo_nome,
                    modelo_versao=info_modelo.versao_modelo,
                    extraidos=extraidos,
                    validos=0,
                    rejeitados_transformacao=rejeitados_transf,
                    motivos_rejeicao=motivos_rej,
                )
                logger.info(
                    "Execução pipeline ML sem registros aptos após transformação | execucao_id=%s | rejeitados=%d",
                    id_execucao,
                    rejeitados_transf,
                )
                return rel

            etapa_atual = "inferencia"
            t_inf_0 = time.perf_counter()
            entradas_modelo = [
                {
                    "id_estudante": str(reg.estudante_id),
                    "idade": reg.idade,
                    "historico_reprovacao": reg.historico_reprovacao,
                    "nota_t1": reg.nota_t1,
                    "escola_id": str(reg.escola_id),
                    "turma_id": str(reg.turma_id) if reg.turma_id else None,
                    "ano_letivo": reg.ano_letivo,
                    "periodo_letivo": reg.periodo_letivo,
                }
                for reg in res_transf.validos
            ]
            saidas = modelo_risco.prever_risco(
                entradas_modelo,
                caminho_modelo=info_modelo.caminho,
            )
            tempo_inferencia_ms = round((time.perf_counter() - t_inf_0) * 1000.0, 2)

            if len(saidas) != len(res_transf.validos):
                raise ErroInferenciaModelo(
                    f"Quantidade de saídas ({len(saidas)}) diverge da entrada ({len(res_transf.validos)})."
                )

            itens_api, sem_prev_valida = self._construir_itens_api(
                registros_validos=res_transf.validos,
                saidas_modelo=saidas,
                info_modelo=info_modelo,
                execucao_id=id_execucao,
                tempo_inferencia_ms=tempo_inferencia_ms,
                data_corte_extracao=inicio,
            )
            inferidos = len(itens_api)

            if enviar and itens_api:
                etapa_atual = "envio"
                cliente = ClienteAPIPrevisoes(
                    self.config,
                    http_client=self.http_client,
                )
                res_envio: ResultadoEnvioAPI = cliente.enviar_previsoes(
                    itens_api,
                    lote_externo_id=id_execucao,
                )
                enviados = res_envio.total_enviado
                persistidos = res_envio.total_recebido
                lotes_enviados = res_envio.total_lotes

            fim = datetime.now(timezone.utc)
            duracao_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            rel = RelatorioExecucaoPipeline(
                execucao_id=id_execucao,
                modo=modo,
                sucesso=True,
                inicio_em=inicio,
                fim_em=fim,
                duracao_ms=duracao_ms,
                escola_id=str(escola_alvo) if escola_alvo else None,
                periodo_letivo=self.config.periodo_letivo,
                modelo_nome=info_modelo.modelo_nome,
                modelo_versao=info_modelo.versao_modelo,
                extraidos=extraidos,
                validos=validos,
                rejeitados_transformacao=rejeitados_transf,
                motivos_rejeicao=motivos_rej,
                sem_previsao_valida=sem_prev_valida,
                inferidos=inferidos,
                enviados=enviados,
                persistidos=persistidos,
                lotes_enviados=lotes_enviados,
            )
            logger.info(
                "Execução pipeline ML concluída | execucao_id=%s | modo=%s | escola_id=%s | modelo=%s | extraidos=%d | validos=%d | rejeitados=%d | inferidos=%d | persistidos=%d | duracao_ms=%.2f",
                id_execucao,
                modo,
                str(escola_alvo) if escola_alvo else "-",
                info_modelo.modelo_nome,
                extraidos,
                validos,
                rejeitados_transf,
                inferidos,
                persistidos,
                duracao_ms,
            )
            return rel

        except (
            ErroConfiguracaoPipeline,
            ErroExtracaoPipeline,
            ErroTransformacaoLeakage,
            FileNotFoundError,
            RuntimeError,
            ErroArtefatoModelo,
            ErroInferenciaModelo,
            ErroEnvioPipeline,
        ) as exc:
            fim = datetime.now(timezone.utc)
            duracao_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            msg_segura = sanitizar_texto_segredos(str(exc))
            logger.error(
                "Falha no pipeline ML | execucao_id=%s | modo=%s | etapa=%s | erro=%s",
                id_execucao,
                modo,
                etapa_atual,
                msg_segura,
            )
            return RelatorioExecucaoPipeline(
                execucao_id=id_execucao,
                modo=modo,
                sucesso=False,
                inicio_em=inicio,
                fim_em=fim,
                duracao_ms=duracao_ms,
                escola_id=str(escola_alvo) if escola_alvo else None,
                periodo_letivo=self.config.periodo_letivo,
                modelo_nome=(
                    info_modelo.modelo_nome if info_modelo else modelo_nome_alvo
                ),
                modelo_versao=info_modelo.versao_modelo if info_modelo else None,
                etapa_falha=etapa_atual,
                erro=msg_segura,
                extraidos=extraidos,
                validos=validos,
                rejeitados_transformacao=rejeitados_transf,
                motivos_rejeicao=motivos_rej,
                sem_previsao_valida=sem_prev_valida,
                inferidos=inferidos,
                enviados=enviados,
                persistidos=persistidos,
                lotes_enviados=lotes_enviados,
            )

    def _construir_itens_api(
        self,
        *,
        registros_validos: list[RegistroInferenciaTransformado],
        saidas_modelo: Sequence[Any],
        info_modelo: InfoArtefatoModelo,
        execucao_id: str,
        tempo_inferencia_ms: float,
        data_corte_extracao: datetime,
    ) -> tuple[list[PrevisaoItemEnvio], int]:
        itens: list[PrevisaoItemEnvio] = []
        sem_previsao = 0

        metadados_base: dict[str, Any] = {
            "pipeline_execucao_id": execucao_id,
            "framework_ml": "scikit-learn",
            "origem_pipeline": "vertice_pipeline_ml_v1",
            "data_corte_extracao": data_corte_extracao.isoformat(),
            "calibracao_aplicada": True,
            "tempo_inferencia_ms": tempo_inferencia_ms,
            "hash_artefato_modelo": info_modelo.sha256,
            "politica_limiares": {
                "baixo_max": round(float(modelo_risco.LIMIAR_BAIXO), 6),
                "moderado_max": round(float(modelo_risco.LIMIAR_ALTO), 6),
                "alto_max": 1.0,
            },
        }
        validar_metadados_tecnicos(metadados_base, lancar_excecao=True)

        for reg, resp in zip(registros_validos, saidas_modelo, strict=True):
            if str(getattr(resp, "id_estudante", "")).strip() != str(reg.estudante_id):
                raise ErroInferenciaModelo(
                    "Inconsistência na inferência: `id_estudante` retornado diverge da entrada."
                )

            faixa_bruta = str(getattr(resp, "faixa_risco", "")).strip().upper()
            pontuacao = getattr(resp, "pontuacao_risco", None)
            if faixa_bruta == "SEM_PREVISAO_VALIDA":
                if pontuacao is not None:
                    raise ErroInferenciaModelo(
                        "Saída inconsistente: `SEM_PREVISAO_VALIDA` com pontuação não nula."
                    )
                sem_previsao += 1
                continue

            if faixa_bruta not in FAIXAS_SAIDA_VALIDAS:
                raise ErroInferenciaModelo(
                    f"Faixa de risco inválida retornada pelo modelo: {faixa_bruta!r}."
                )
            if (
                pontuacao is None
                or isinstance(pontuacao, bool)
                or not isinstance(pontuacao, (int, float))
                or not math.isfinite(float(pontuacao))
                or not (0.0 <= float(pontuacao) <= 1.0)
            ):
                raise ErroInferenciaModelo(
                    f"Pontuação de risco inválida retornada pelo modelo: {pontuacao!r}."
                )

            versao = str(getattr(resp, "versao_modelo", "") or "").strip()
            if not versao:
                raise ErroInferenciaModelo("`versao_modelo` ausente na saída do modelo.")

            gerado_em = getattr(resp, "data_processamento", None) or datetime.now(
                timezone.utc
            )

            variaveis = reg.variaveis_utilizadas
            validar_variaveis_contra_leakage(variaveis, lancar_excecao=True)

            try:
                item = PrevisaoItemEnvio(
                    estudante_id=reg.estudante_id,
                    escola_id=reg.escola_id,
                    turma_id=reg.turma_id,
                    ano_letivo=reg.ano_letivo,
                    periodo_letivo=reg.periodo_letivo,
                    tipo_previsao=info_modelo.tipo_previsao,  # type: ignore[arg-type]
                    pontuacao_risco=round(float(pontuacao), 6),
                    faixa_risco=faixa_bruta,  # type: ignore[arg-type]
                    politica_classificacao_versao=info_modelo.politica_classificacao_versao,
                    modelo_nome=info_modelo.modelo_nome,
                    modelo_versao=versao,
                    gerado_em=gerado_em,
                    lote_externo_id=execucao_id,
                    variaveis_utilizadas=variaveis,
                    metadados_tecnicos=metadados_base,
                )
            except ValidationError as exc:
                raise ErroInferenciaModelo(
                    f"Saída do modelo incompatível com contrato da API: {exc}"
                ) from exc
            itens.append(item)

        return itens, sem_previsao


def _carregar_registros_json(caminho: Path) -> list[dict[str, Any]]:
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo de entrada JSON não encontrado: `{caminho}`.")
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    if isinstance(conteudo, dict) and isinstance(conteudo.get("itens"), list):
        return list(conteudo["itens"])
    if isinstance(conteudo, list):
        return list(conteudo)
    raise ValueError(
        "O JSON de entrada deve ser uma lista de objetos ou um objeto com chave `itens`."
    )


def _construir_parser_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.integrations.prediction.pipeline.executor",
        description="Executor simplificado do Pipeline Automatizado de ML do Vértice.",
    )
    grupo_acao = parser.add_mutually_exclusive_group(required=True)
    grupo_acao.add_argument(
        "--check-config",
        action="store_true",
        help="Valida URL, token técnico e disponibilidade da configuração vinculada à credencial.",
    )
    grupo_acao.add_argument(
        "--check-model",
        action="store_true",
        help="Lista e valida os modelos registrados disponíveis para inferência local.",
    )
    grupo_acao.add_argument(
        "--dry-run",
        action="store_true",
        help="Consulta os dados autorizados, identifica escola/modelo pelo token e executa inferência sem enviar.",
    )
    grupo_acao.add_argument(
        "--send",
        action="store_true",
        help="Executa extração, inferência e envio em lote usando `VERTICE_ML_SERVICE_TOKEN`.",
    )

    parser.add_argument("--input-json", type=Path, default=None, help="Arquivo JSON local (apenas para `--dry-run` offline).")
    parser.add_argument("--turma-id", type=str, default=None, help="Filtro opcional de turma (`VERTICE_ML_TURMA_ID`).")
    parser.add_argument("--disciplina-id", type=str, default=None, help="Filtro opcional de disciplina (`VERTICE_ML_DISCIPLINA_ID`).")
    parser.add_argument("--ano-letivo", type=int, default=None, help="Filtro opcional de ano letivo (`VERTICE_ML_ANO_LETIVO`).")
    parser.add_argument("--periodo-letivo", type=str, default=None, help="Período de corte inicial (`VERTICE_ML_PERIODO_LETIVO`).")
    parser.add_argument("--json", action="store_true", help="Imprime saída estruturada em JSON.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = _construir_parser_cli()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = PipelineMLConfig.from_env(
            overrides={
                "turma_id": args.turma_id,
                "disciplina_id": args.disciplina_id,
                "ano_letivo": args.ano_letivo,
                "periodo_letivo": args.periodo_letivo,
            }
        )
    except ErroConfiguracaoPipeline as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 2

    if args.check_config:
        resumo = config.resumo_seguro()
        if not config.service_token:
            print(
                json.dumps(
                    {
                        "configuracao_valida": False,
                        "erro": "Variável `VERTICE_ML_SERVICE_TOKEN` não configurada.",
                        "resumo": resumo,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2

        try:
            ext = ExtratorDadosInferencia(config).consultar_configuracao_credencial()
            info = inspecionar_artefato_modelo(ext.modelo_nome)
        except (ErroExtracaoPipeline, FileNotFoundError, RuntimeError, ErroArtefatoModelo) as exc:
            print(
                json.dumps(
                    {
                        "configuracao_valida": False,
                        "erro": sanitizar_texto_segredos(str(exc)),
                        "resumo": resumo,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2

        print(
            json.dumps(
                {
                    "configuracao_valida": True,
                    "credencial": {
                        "nome": ext.credencial_nome,
                        "escola_id": str(ext.escola_id),
                        "modelo_nome": ext.modelo_nome,
                        "modelo_versao": info.versao_modelo,
                        "artefato_disponivel": True,
                        "artefato_caminho": str(info.caminho),
                        "registros_elegiveis_corte": ext.total_reportado,
                    },
                    "resumo": resumo,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.check_model:
        modelos = catalogo_modelos.listar_modelos_preditivos(apenas_disponiveis=False)
        disponiveis = [m for m in modelos if m.disponivel_inferencia]
        if not disponiveis:
            print(
                json.dumps(
                    {
                        "status": "indisponivel",
                        "modelos": [asdict(m) for m in modelos],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 3
        info = inspecionar_artefato_modelo(disponiveis[0].modelo_nome)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "caminho": str(info.caminho),
                    "modelo_nome": info.modelo_nome,
                    "versao_modelo": info.versao_modelo,
                    "features": info.features,
                    "sha256": info.sha256,
                    "tamanho_bytes": info.tamanho_bytes,
                    "modelos_disponiveis": [asdict(m) for m in disponiveis],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.send and args.input_json is not None:
        print(
            "Uso inválido: `--input-json` é permitido apenas em modo `--dry-run`.",
            file=sys.stderr,
        )
        return 2

    registros_locais = None
    if args.input_json is not None:
        try:
            registros_locais = _carregar_registros_json(args.input_json)
        except Exception as exc:
            print(f"Erro ao ler `--input-json`: {exc}", file=sys.stderr)
            return 2

    executor = ExecutorPipelineML(config)
    relatorio = executor.executar(
        enviar=bool(args.send),
        registros_locais=registros_locais,
    )
    if args.json:
        print(json.dumps(relatorio.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(
            f"[Pipeline ML] execucao_id={relatorio.execucao_id} | modo={relatorio.modo} | "
            f"sucesso={relatorio.sucesso} | escola_id={relatorio.escola_id} | "
            f"modelo={relatorio.modelo_nome} | extraidos={relatorio.extraidos} | "
            f"validos={relatorio.validos} | rejeitados={relatorio.rejeitados_transformacao} | "
            f"inferidos={relatorio.inferidos} | persistidos={relatorio.persistidos} | "
            f"duracao_ms={relatorio.duracao_ms}"
        )
        if not relatorio.sucesso:
            print(
                f"Falha na etapa `{relatorio.etapa_falha}`: {relatorio.erro}",
                file=sys.stderr,
            )
    return 0 if relatorio.sucesso else 1


if __name__ == "__main__":
    raise SystemExit(main())
