"""
Registro central leve de modelos preditivos disponíveis no Vértice.

Descobre dinamicamente os modelos com implementação e artefato compatíveis
para uso pela tela administrativa (`Credenciais ML`), pelo backend e pelo pipeline,
evitando nomes digitados manualmente ou listas fixas divergentes na interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.integrations.prediction import modelo_risco

DIRETORIO_BACKEND = Path(__file__).resolve().parents[3]
DIRETORIO_ARTIFACTS_PADRAO = DIRETORIO_BACKEND / "artifacts"


@dataclass(frozen=True)
class DescritorModeloPreditivo:
    """Metadados verificados de um modelo preditivo registrado no Vértice."""

    modelo_nome: str
    nome_exibicao: str
    modelo_versao: str
    artefato_nome: str
    artefato_relativo: str
    tipo_previsao: str
    politica_classificacao_versao: str
    disponivel_inferencia: bool
    motivo_indisponibilidade: Optional[str] = None


_MODELOS_IMPLEMENTADOS: tuple[dict[str, str], ...] = (
    {
        "modelo_nome": "regressao_logistica",
        "nome_exibicao": "Risco Acadêmico — Regressão Logística (1º Período)",
        "versao_esperada": modelo_risco.VERSAO_MODELO,
        "artefato_nome": "modelo_risco_academico_v1.joblib",
        "tipo_previsao": "RISCO_ACADEMICO",
        "politica_classificacao_versao": "tercos_calibrados_poc_v1",
    },
)


def _avaliar_modelo(
    definicao: dict[str, str],
    diretorio_artefatos: Optional[Path] = None,
) -> tuple[DescritorModeloPreditivo, Path]:
    pasta = Path(diretorio_artefatos or DIRETORIO_ARTIFACTS_PADRAO).resolve()
    caminho_artefato = pasta / definicao["artefato_nome"]
    artefato_relativo = f"artifacts/{definicao['artefato_nome']}"
    modelo_nome_def = definicao["modelo_nome"]
    versao_padrao = definicao["versao_esperada"]

    if not caminho_artefato.is_file():
        return (
            DescritorModeloPreditivo(
                modelo_nome=modelo_nome_def,
                nome_exibicao=definicao["nome_exibicao"],
                modelo_versao=versao_padrao,
                artefato_nome=definicao["artefato_nome"],
                artefato_relativo=artefato_relativo,
                tipo_previsao=definicao["tipo_previsao"],
                politica_classificacao_versao=definicao["politica_classificacao_versao"],
                disponivel_inferencia=False,
                motivo_indisponibilidade=(
                    f"Artefato `{artefato_relativo}` não encontrado. "
                    "Execute `python -m app.integrations.prediction.treinar_modelo_risco`."
                ),
            ),
            caminho_artefato,
        )

    try:
        artefato = modelo_risco._carregar_artefato(
            str(caminho_artefato),
            caminho_artefato.stat().st_mtime_ns,
        )
        nome_artefato = str(artefato.get("modelo_nome") or modelo_nome_def).strip()
        if nome_artefato != modelo_nome_def:
            raise RuntimeError(
                f"Artefato `{definicao['artefato_nome']}` corresponde ao modelo "
                f"`{nome_artefato}`, divergente de `{modelo_nome_def}`."
            )
        versao_artefato = str(artefato.get("versao_modelo") or versao_padrao).strip()
    except Exception as exc:
        return (
            DescritorModeloPreditivo(
                modelo_nome=modelo_nome_def,
                nome_exibicao=definicao["nome_exibicao"],
                modelo_versao=versao_padrao,
                artefato_nome=definicao["artefato_nome"],
                artefato_relativo=artefato_relativo,
                tipo_previsao=definicao["tipo_previsao"],
                politica_classificacao_versao=definicao["politica_classificacao_versao"],
                disponivel_inferencia=False,
                motivo_indisponibilidade=str(exc),
            ),
            caminho_artefato,
        )

    return (
        DescritorModeloPreditivo(
            modelo_nome=modelo_nome_def,
            nome_exibicao=definicao["nome_exibicao"],
            modelo_versao=versao_artefato,
            artefato_nome=definicao["artefato_nome"],
            artefato_relativo=artefato_relativo,
            tipo_previsao=definicao["tipo_previsao"],
            politica_classificacao_versao=definicao["politica_classificacao_versao"],
            disponivel_inferencia=True,
            motivo_indisponibilidade=None,
        ),
        caminho_artefato,
    )


def listar_modelos_preditivos(
    *,
    apenas_disponiveis: bool = True,
    diretorio_artefatos: Optional[Path] = None,
) -> list[DescritorModeloPreditivo]:
    """Lista modelos implementados com validação real de disponibilidade do artefato."""
    resultado: list[DescritorModeloPreditivo] = []
    for definicao in _MODELOS_IMPLEMENTADOS:
        descritor, _ = _avaliar_modelo(definicao, diretorio_artefatos=diretorio_artefatos)
        if apenas_disponiveis and not descritor.disponivel_inferencia:
            continue
        resultado.append(descritor)
    return resultado


def obter_modelo_preditivo(
    modelo_nome: str,
    *,
    exigir_disponivel: bool = True,
    diretorio_artefatos: Optional[Path] = None,
) -> Optional[DescritorModeloPreditivo]:
    """Busca metadados de um modelo pelo seu identificador técnico (`modelo_nome`)."""
    chave = (modelo_nome or "").strip()
    if not chave:
        return None
    for definicao in _MODELOS_IMPLEMENTADOS:
        if definicao["modelo_nome"] == chave:
            descritor, _ = _avaliar_modelo(definicao, diretorio_artefatos=diretorio_artefatos)
            if exigir_disponivel and not descritor.disponivel_inferencia:
                return None
            return descritor
    return None


def resolver_caminho_artefato_modelo(
    modelo_nome: str,
    *,
    diretorio_artefatos: Optional[Path] = None,
) -> tuple[DescritorModeloPreditivo, Path]:
    """
    Resolve o descritor e o caminho do artefato `.joblib` do modelo autorizado.
    Interrompe com erro explícito se o modelo não estiver registrado ou sem artefato
    compatível — nunca substitui silenciosamente por outro modelo.
    """
    chave = (modelo_nome or "").strip()
    for definicao in _MODELOS_IMPLEMENTADOS:
        if definicao["modelo_nome"] == chave:
            descritor, caminho = _avaliar_modelo(
                definicao,
                diretorio_artefatos=diretorio_artefatos,
            )
            if not descritor.disponivel_inferencia:
                if not caminho.is_file():
                    raise FileNotFoundError(
                        descritor.motivo_indisponibilidade
                        or f"Artefato do modelo `{chave}` ausente em `{caminho}`."
                    )
                raise RuntimeError(
                    descritor.motivo_indisponibilidade
                    or f"Artefato do modelo `{chave}` incompatível em `{caminho}`."
                )
            return descritor, caminho

    raise RuntimeError(
        f"O modelo `{chave}` associado à credencial não possui implementação "
        "disponível para execução no pipeline."
    )
