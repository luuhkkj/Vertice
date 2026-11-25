"""
Transformação e validação anti-leakage dos registros antes da inferência ML.

Regras centrais:
- Reutiliza `CAMPOS_PROIBIDOS_PREDICAO` e `normalizar_chave_politica` de `leakage.py`.
- Bloqueia imediatamente qualquer variável pós-corte ou PII (`situacao_final`, `target`,
  `classe_real`, `nota_t2`, `g2`, `nota_t3`, `g3`, `media_geral`, `ausencias`,
  `absences`, `faltas`, `frequencia_percentual`, `nome`, `cpf`, etc.).
- Não inventa nem corrige silenciosamente valores inválidos; registros individuais com
  atributos obrigatórios ausentes, tipo inválido ou fora dos limites são rejeitados e
  contabilizados com código de motivo seguro.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import logging
import math
from typing import Any, Optional
import uuid

from app.integrations.prediction.leakage import (
    CAMPOS_PROIBIDOS_PREDICAO,
    normalizar_chave_politica,
)

logger = logging.getLogger(__name__)

# Campos pós-corte / alvo / agregados anuais que jamais podem entrar como features
# neste pipeline de corte do primeiro período (mesmo quando constam no catálogo geral).
CAMPOS_POS_CORTE_BLOQUEADOS_PIPELINE: dict[str, str] = {
    **CAMPOS_PROIBIDOS_PREDICAO,
    "situacao_final": "Variável-alvo / desfecho final do período letivo.",
    "target": "Variável-alvo supervisionada.",
    "classe_real": "Rótulo de desfecho real.",
    "nota_t2": "Nota do 2º período posterior ao corte inicial.",
    "g2": "Nota do 2º período UCI posterior ao corte inicial.",
    "nota_t3": "Nota do 3º período posterior ao corte inicial.",
    "g3": "Nota final UCI posterior ao corte inicial.",
    "media_geral": "Média consolidada anual/pós-corte proibida no corte do 1º período.",
    "ausencias": "Ausências acumuladas pós-corte.",
    "absences": "Ausências acumuladas UCI pós-corte.",
    "faltas": "Contagem de faltas não elegível neste modelo de corte inicial.",
    "frequencia_percentual": "Frequência não utilizada no contrato do protótipo atual.",
}

_PERIODOS_CORTE_VALIDOS = {
    "1o_bimestre",
    "1_bimestre",
    "bimestre_1",
    "1o_trimestre",
    "1_trimestre",
    "trimestre_1",
    "1o_semestre",
    "1_semestre",
    "semestre_1",
    "1o_periodo",
    "1_periodo",
    "periodo_1",
    "t1",
}

_CHAVES_ESTUDANTE = {"estudante_id", "id_estudante"}
_CHAVES_ESTRUTURAIS = {"escola_id", "turma_id", "ano_letivo", "periodo_letivo"}
_CHAVES_FEATURES_PERMITIDAS = {
    "idade",
    "age",
    "historico_reprovacoes",
    "historico_reprovacao",
    "failures",
    "nota_t1",
    "g1",
}


class ErroTransformacaoLeakage(ValueError):
    """Levantada quando o payload de entrada contém variável proibida por Data Leakage ou PII."""

    def __init__(self, mensagem: str, campos_detectados: list[str]) -> None:
        super().__init__(mensagem)
        self.campos_detectados = campos_detectados


@dataclass(frozen=True)
class RegistroInferenciaTransformado:
    """Registro validado, tipado e pronto para inferência pelo modelo de risco."""

    estudante_id: uuid.UUID
    escola_id: uuid.UUID
    turma_id: Optional[uuid.UUID]
    ano_letivo: int
    periodo_letivo: str
    idade: Optional[int]
    historico_reprovacao: Optional[int]
    nota_t1: float

    @property
    def variaveis_utilizadas(self) -> list[str]:
        """Retorna os nomes canônicos catalogados em `leakage.py` presentes neste registro."""
        usadas: list[str] = []
        if self.idade is not None:
            usadas.append("idade")
        if self.historico_reprovacao is not None:
            usadas.append("historico_reprovacoes")
        usadas.append("nota_t1")
        return usadas


@dataclass(frozen=True)
class MotivoRejeicaoRegistro:
    """Registro resumido de rejeição individual sem exposição de PII."""

    indice: int
    estudante_id: Optional[str]
    codigo_motivo: str
    detalhe: str


@dataclass(frozen=True)
class ResultadoTransformacao:
    """Resumo completo da etapa de validação e transformação."""

    validos: list[RegistroInferenciaTransformado]
    rejeitados: list[MotivoRejeicaoRegistro]
    total_recebidos: int
    resumo_motivos: dict[str, int]

    @property
    def total_validos(self) -> int:
        return len(self.validos)

    @property
    def total_rejeitados(self) -> int:
        return len(self.rejeitados)


def _inspecionar_chaves_recursivo(objeto: Any, prefixo: str = "") -> list[str]:
    detectados: list[str] = []
    if isinstance(objeto, Mapping):
        for chave, valor in objeto.items():
            chave_str = str(chave)
            chave_norm = normalizar_chave_politica(chave_str)
            caminho = f"{prefixo}.{chave_str}" if prefixo else chave_str
            if chave_norm in CAMPOS_POS_CORTE_BLOQUEADOS_PIPELINE:
                detectados.append(caminho)
            if isinstance(valor, (Mapping, list, tuple)):
                detectados.extend(_inspecionar_chaves_recursivo(valor, caminho))
    elif isinstance(objeto, (list, tuple)):
        for idx, item in enumerate(objeto):
            if isinstance(item, (Mapping, list, tuple)):
                detectados.extend(_inspecionar_chaves_recursivo(item, f"{prefixo}[{idx}]"))
    return detectados


def _eh_ausente(valor: Any) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str) and not valor.strip():
        return True
    try:
        return bool(math.isnan(float(valor))) if isinstance(valor, float) else False
    except (TypeError, ValueError):
        return False


def _converter_inteiro_estrito(
    valor: Any,
    nome: str,
    minimo: int,
    maximo: int,
) -> Optional[int]:
    if _eh_ausente(valor):
        return None
    if isinstance(valor, bool):
        raise ValueError(f"`{nome}` não aceita valor booleano.")
    if isinstance(valor, int):
        numero = valor
    elif isinstance(valor, float):
        if not math.isfinite(valor) or not valor.is_integer():
            raise ValueError(f"`{nome}` deve ser um número inteiro válido.")
        numero = int(valor)
    elif isinstance(valor, str):
        texto = valor.strip()
        try:
            fval = float(texto)
        except ValueError as exc:
            raise ValueError(f"`{nome}` deve ser inteiro numérico válido.") from exc
        if not math.isfinite(fval) or not fval.is_integer():
            raise ValueError(f"`{nome}` deve ser um número inteiro válido.")
        numero = int(fval)
    else:
        raise ValueError(f"Tipo inválido para `{nome}`: {type(valor).__name__}.")

    if numero < minimo or numero > maximo:
        raise ValueError(f"`{nome}` fora do intervalo permitido [{minimo}, {maximo}].")
    return numero


def _converter_float_estrito(
    valor: Any,
    nome: str,
    minimo: float,
    maximo: float,
) -> Optional[float]:
    if _eh_ausente(valor):
        return None
    if isinstance(valor, bool):
        raise ValueError(f"`{nome}` não aceita valor booleano.")
    if isinstance(valor, (int, float)):
        numero = float(valor)
    elif isinstance(valor, str):
        try:
            numero = float(valor.strip().replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"`{nome}` deve ser numérico válido.") from exc
    else:
        raise ValueError(f"Tipo inválido para `{nome}`: {type(valor).__name__}.")

    if not math.isfinite(numero):
        raise ValueError(f"`{nome}` deve ser finito.")
    if numero < minimo or numero > maximo:
        raise ValueError(
            f"`{nome}` fora do intervalo permitido [{minimo:g}, {maximo:g}]."
        )
    return round(numero, 4)


def _converter_uuid(valor: Any, nome: str, *, obrigatorio: bool) -> Optional[uuid.UUID]:
    if _eh_ausente(valor):
        if obrigatorio:
            raise ValueError(f"`{nome}` obrigatório ausente.")
        return None
    try:
        return uuid.UUID(str(valor).strip())
    except ValueError as exc:
        raise ValueError(f"`{nome}` inválido.") from exc


class TransformadorDadosInferencia:
    """Valida, normaliza e protege dados extraídos antes de enviá-los ao modelo local."""

    def __init__(self, *, escola_id_esperada: Optional[uuid.UUID] = None) -> None:
        self.escola_id_esperada = escola_id_esperada

    def transformar(
        self,
        registros: Sequence[Mapping[str, Any]],
    ) -> ResultadoTransformacao:
        validos: list[RegistroInferenciaTransformado] = []
        rejeitados: list[MotivoRejeicaoRegistro] = []

        for idx, registro in enumerate(registros):
            if not isinstance(registro, Mapping):
                rejeitados.append(
                    MotivoRejeicaoRegistro(
                        indice=idx,
                        estudante_id=None,
                        codigo_motivo="registro_nao_mapeavel",
                        detalhe="Registro de entrada não é um dicionário válido.",
                    )
                )
                continue

            campos_proibidos = _inspecionar_chaves_recursivo(registro)
            if campos_proibidos:
                lista_fmt = ", ".join(sorted(set(campos_proibidos)))
                raise ErroTransformacaoLeakage(
                    f"Data Leakage / PII detectado na entrada do pipeline: campo(s) proibido(s) [{lista_fmt}].",
                    campos_detectados=sorted(set(campos_proibidos)),
                )

            normalizado = {
                normalizar_chave_politica(str(k)): (k, v) for k, v in registro.items()
            }
            campos_desconhecidos = [
                orig
                for norm, (orig, _v) in normalizado.items()
                if norm not in (_CHAVES_ESTUDANTE | _CHAVES_ESTRUTURAIS | _CHAVES_FEATURES_PERMITIDAS)
            ]
            if campos_desconhecidos:
                raise ErroTransformacaoLeakage(
                    f"Campo(s) não catalogado(s) detectado(s) na entrada do pipeline: {campos_desconhecidos}.",
                    campos_detectados=campos_desconhecidos,
                )

            est_raw = (
                normalizado["estudante_id"][1]
                if "estudante_id" in normalizado
                else normalizado.get("id_estudante", (None, None))[1]
            )
            est_id_str = str(est_raw).strip() if not _eh_ausente(est_raw) else None

            try:
                estudante_id = _converter_uuid(est_raw, "estudante_id", obrigatorio=True)
                assert estudante_id is not None

                escola_raw = normalizado.get("escola_id", (None, None))[1]
                escola_id = _converter_uuid(escola_raw, "escola_id", obrigatorio=True)
                assert escola_id is not None

                if self.escola_id_esperada is not None and escola_id != self.escola_id_esperada:
                    raise ValueError("`escola_id` do registro diverge do escopo configurado.")

                turma_raw = normalizado.get("turma_id", (None, None))[1]
                turma_id = _converter_uuid(turma_raw, "turma_id", obrigatorio=False)

                ano_letivo = _converter_inteiro_estrito(
                    normalizado.get("ano_letivo", (None, None))[1],
                    "ano_letivo",
                    2000,
                    2100,
                )
                if ano_letivo is None:
                    raise ValueError("`ano_letivo` obrigatório ausente.")

                periodo_raw = normalizado.get("periodo_letivo", (None, None))[1]
                if _eh_ausente(periodo_raw):
                    raise ValueError("`periodo_letivo` obrigatório ausente.")
                periodo_letivo = str(periodo_raw).strip()
                if normalizar_chave_politica(periodo_letivo) not in _PERIODOS_CORTE_VALIDOS:
                    raise ErroTransformacaoLeakage(
                        f"Período `{periodo_letivo}` posterior ao corte permitido para este modelo.",
                        campos_detectados=["periodo_letivo"],
                    )

                idade_raw = (
                    normalizado["idade"][1]
                    if "idade" in normalizado
                    else normalizado.get("age", (None, None))[1]
                )
                idade = _converter_inteiro_estrito(idade_raw, "idade", 10, 100)

                hist_raw = None
                for k_hist in ("historico_reprovacoes", "historico_reprovacao", "failures"):
                    if k_hist in normalizado and not _eh_ausente(normalizado[k_hist][1]):
                        hist_raw = normalizado[k_hist][1]
                        break
                historico_reprovacao = _converter_inteiro_estrito(
                    hist_raw, "historico_reprovacoes", 0, 50
                )

                nota_t1_raw = normalizado.get("nota_t1", (None, None))[1]
                g1_raw = normalizado.get("g1", (None, None))[1]
                if not _eh_ausente(nota_t1_raw) and not _eh_ausente(g1_raw):
                    raise ValueError("Informe `nota_t1` ou `G1`, não ambos.")
                if not _eh_ausente(g1_raw):
                    nota_g1 = _converter_float_estrito(g1_raw, "G1", 0.0, 20.0)
                    nota_t1 = None if nota_g1 is None else round(nota_g1 / 2.0, 4)
                else:
                    nota_t1 = _converter_float_estrito(nota_t1_raw, "nota_t1", 0.0, 10.0)

                if nota_t1 is None:
                    rejeitados.append(
                        MotivoRejeicaoRegistro(
                            indice=idx,
                            estudante_id=str(estudante_id),
                            codigo_motivo="nota_t1_ausente",
                            detalhe="`nota_t1` ausente para o corte do 1º período.",
                        )
                    )
                    continue

                if idade is None and historico_reprovacao is None:
                    rejeitados.append(
                        MotivoRejeicaoRegistro(
                            indice=idx,
                            estudante_id=str(estudante_id),
                            codigo_motivo="contexto_minimo_ausente",
                            detalhe="Exige `idade` ou `historico_reprovacoes` além de `nota_t1`.",
                        )
                    )
                    continue

                validos.append(
                    RegistroInferenciaTransformado(
                        estudante_id=estudante_id,
                        escola_id=escola_id,
                        turma_id=turma_id,
                        ano_letivo=ano_letivo,
                        periodo_letivo=periodo_letivo,
                        idade=idade,
                        historico_reprovacao=historico_reprovacao,
                        nota_t1=nota_t1,
                    )
                )
            except ErroTransformacaoLeakage:
                raise
            except ValueError as exc:
                rejeitados.append(
                    MotivoRejeicaoRegistro(
                        indice=idx,
                        estudante_id=est_id_str,
                        codigo_motivo="valor_ou_tipo_invalido",
                        detalhe=str(exc),
                    )
                )

        contagem_motivos = dict(Counter(item.codigo_motivo for item in rejeitados))
        logger.info(
            "Transformação ML concluída | recebidos=%d | validos=%d | rejeitados=%d | motivos=%s",
            len(registros),
            len(validos),
            len(rejeitados),
            contagem_motivos,
        )
        return ResultadoTransformacao(
            validos=validos,
            rejeitados=rejeitados,
            total_recebidos=len(registros),
            resumo_motivos=contagem_motivos,
        )
