"""Inferência local de risco acadêmico e critérios explícitos de insuficiência."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from functools import lru_cache
import math
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import sklearn

from app.integrations.prediction.leakage import normalizar_chave_politica
from app.integrations.prediction.modelo_schemas import PrevisaoRiscoModeloResponse

VERSAO_MODELO = "poc-risco-academico-uci-v1"
DIRETORIO_BACKEND = Path(__file__).resolve().parents[3]
CAMINHO_ARTEFATO_PADRAO = (
    DIRETORIO_BACKEND / "artifacts" / "modelo_risco_academico_v1.joblib"
)

LIMIAR_BAIXO = 1 / 3
LIMIAR_ALTO = 2 / 3

_ALIASES_ENTRADA = {
    "id_estudante": "id_estudante",
    "id_aluno": "id_estudante",
    "codigo_anonimo": "id_estudante",
    "idade": "idade",
    "age": "idade",
    "historico_reprovacao": "historico_reprovacao",
    "historico_reprovacoes": "historico_reprovacao",
    "failures": "historico_reprovacao",
    "nota_t1": "nota_t1",
    "g1": "nota_t1_original",
}
_METADADOS_ACEITOS = {
    "escola_id",
    "turma_id",
    "ano_letivo",
    "periodo_letivo",
}
_CAMPOS_POS_CORTE_PROIBIDOS = {
    "situacao_final",
    "target",
    "classe_real",
    "nota_t2",
    "g2",
    "nota_t3",
    "g3",
    "media_geral",
    "ausencias",
    "absences",
    "faltas",
    "frequencia_percentual",
}
_LIMITES_FEATURES = {
    "idade": (10.0, 100.0, "inteiro"),
    "historico_reprovacao": (0.0, 50.0, "inteiro"),
    "nota_t1": (0.0, 10.0, "nota"),
    "nota_t1_original": (0.0, 20.0, "nota"),
}
_FEATURES = ["idade", "historico_reprovacao", "nota_t1"]


def _normalizar_valor_numerico(
    nome: str,
    valor: Any,
) -> float | None:
    if valor is None:
        return None
    try:
        if bool(pd.isna(valor)):
            return None
    except (TypeError, ValueError):
        pass

    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"`{nome}` deve ser numérico ou nulo.") from exc
    if not math.isfinite(numero):
        raise ValueError(f"`{nome}` deve ser finito.")

    minimo, maximo, tipo = _LIMITES_FEATURES[nome]
    if numero < minimo or numero > maximo:
        raise ValueError(f"`{nome}` deve estar entre {minimo:g} e {maximo:g}.")
    if tipo == "inteiro" and not numero.is_integer():
        raise ValueError(f"`{nome}` deve ser inteiro.")
    return numero


def _normalizar_registros(
    dados_estudantes: pd.DataFrame | Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(dados_estudantes, pd.DataFrame):
        registros: Sequence[Mapping[str, Any]] = dados_estudantes.to_dict(
            orient="records"
        )
    elif isinstance(dados_estudantes, Sequence) and not isinstance(
        dados_estudantes,
        (str, bytes),
    ):
        registros = dados_estudantes
    else:
        raise TypeError(
            "`dados_estudantes` deve ser um DataFrame ou uma sequência de dicionários."
        )

    normalizados: list[dict[str, Any]] = []
    for indice, registro in enumerate(registros):
        if not isinstance(registro, Mapping):
            raise TypeError(f"O item {indice} não é um dicionário de dados.")

        linha: dict[str, Any] = {}
        for chave_original, valor in registro.items():
            chave = normalizar_chave_politica(str(chave_original))
            if chave in _CAMPOS_POS_CORTE_PROIBIDOS:
                raise ValueError(
                    f"`{chave_original}` é resultado ou dado posterior ao corte "
                    "e não pode ser usado para previsão."
                )
            nome = _ALIASES_ENTRADA.get(chave)
            if nome is None:
                if chave in _METADADOS_ACEITOS:
                    continue
                raise ValueError(
                    f"Campo de entrada não reconhecido: `{chave_original}`."
                )
            if nome in linha:
                anterior = linha[nome]
                anterior_nulo = anterior is None or bool(pd.isna(anterior))
                valor_nulo = valor is None or bool(pd.isna(valor))
                if anterior_nulo != valor_nulo or (
                    not anterior_nulo and str(anterior) != str(valor)
                ):
                    raise ValueError(
                        f"Foram informados valores conflitantes para `{nome}`."
                    )
            linha[nome] = valor

        identificador = linha.get("id_estudante")
        if identificador is None or not str(identificador).strip():
            raise ValueError(f"O item {indice} precisa de `id_estudante` ou `id_aluno`.")

        nota_t1_original = linha.get("nota_t1_original")
        nota_t1 = linha.get("nota_t1")
        if nota_t1_original is not None:
            nota_t1_convertida = _normalizar_valor_numerico(
                "nota_t1_original",
                nota_t1_original,
            )
            if nota_t1 is not None:
                raise ValueError(
                    "Informe `nota_t1` ou `G1`, mas não os dois campos."
                )
            nota_t1 = (
                None
                if nota_t1_convertida is None
                else nota_t1_convertida / 2
            )

        item: dict[str, Any] = {"id_estudante": str(identificador).strip()}
        for nome_feature in _FEATURES:
            item[nome_feature] = _normalizar_valor_numerico(
                nome_feature,
                nota_t1 if nome_feature == "nota_t1" else linha.get(nome_feature),
            )
        item["possui_dados_suficientes"] = (
            item["nota_t1"] is not None
            and (
                item["idade"] is not None
                or item["historico_reprovacao"] is not None
            )
        )
        normalizados.append(item)
    return normalizados


@lru_cache(maxsize=4)
def _carregar_artefato(caminho: str, _modificacao_ns: int) -> dict[str, Any]:
    caminho_arquivo = Path(caminho)
    if not caminho_arquivo.is_file():
        raise FileNotFoundError(
            f"Artefato de risco ausente em `{caminho_arquivo}`. "
            "Treine o modelo com `python -m app.integrations.prediction.treinar_modelo_risco`."
        )
    artefato = joblib.load(caminho_arquivo)
    if not isinstance(artefato, dict) or not hasattr(
        artefato.get("modelo"),
        "predict_proba",
    ):
        raise RuntimeError("O artefato de risco não contém um classificador válido.")
    if artefato.get("versao_modelo") != VERSAO_MODELO:
        raise RuntimeError(
            "A versão do artefato não corresponde ao contrato de inferência atual."
        )
    if artefato.get("features") != _FEATURES:
        raise RuntimeError("As variáveis do artefato não correspondem ao corte definido.")
    versoes = artefato.get("pacote_python", {})
    versao_sklearn = versoes.get("scikit_learn")
    if versao_sklearn is not None and versao_sklearn != sklearn.__version__:
        raise RuntimeError(
            "A versão do scikit-learn não corresponde à usada no treinamento; "
            "recrie o artefato com as dependências instaladas."
        )
    versao_joblib = versoes.get("joblib")
    if versao_joblib is not None and versao_joblib != joblib.__version__:
        raise RuntimeError(
            "A versão do joblib não corresponde à usada no treinamento; "
            "recrie o artefato com as dependências instaladas."
        )
    return artefato


def _classificar_faixa(
    pontuacao: float,
) -> tuple[str, str]:
    if pontuacao < LIMIAR_BAIXO:
        return "BAIXO", "Estável"
    if pontuacao < LIMIAR_ALTO:
        return "MODERADO", "Atenção"
    return "ALTO", "Prioritário"


def prever_risco(
    dados_estudantes: pd.DataFrame | Sequence[Mapping[str, Any]],
    *,
    caminho_modelo: Path | str = CAMINHO_ARTEFATO_PADRAO,
) -> list[PrevisaoRiscoModeloResponse]:
    """Estima risco combinado de reprovação/evasão com dados disponíveis no primeiro período."""
    registros = _normalizar_registros(dados_estudantes)
    agora = datetime.now(timezone.utc)
    respostas: list[PrevisaoRiscoModeloResponse] = []
    indices_validos = [
        indice
        for indice, registro in enumerate(registros)
        if registro["possui_dados_suficientes"]
    ]

    pontuacoes: dict[int, float] = {}
    if indices_validos:
        caminho_arquivo = Path(caminho_modelo).resolve()
        if not caminho_arquivo.is_file():
            raise FileNotFoundError(
                f"Artefato de risco ausente em `{caminho_arquivo}`. "
                "Treine o modelo com "
                "`python -m app.integrations.prediction.treinar_modelo_risco`."
            )
        artefato = _carregar_artefato(
            str(caminho_arquivo),
            caminho_arquivo.stat().st_mtime_ns,
        )
        matriz = pd.DataFrame(
            [
                {feature: registros[indice][feature] for feature in _FEATURES}
                for indice in indices_validos
            ],
            columns=_FEATURES,
        )
        modelo = artefato["modelo"]
        probabilidades = modelo.predict_proba(matriz)
        classes = list(modelo.classes_)
        if 1 not in classes:
            raise RuntimeError("O modelo carregado não possui a classe de risco esperada.")
        indice_classe_risco = classes.index(1)
        for posicao, indice in enumerate(indices_validos):
            pontuacao = float(probabilidades[posicao, indice_classe_risco])
            if not math.isfinite(pontuacao) or not 0 <= pontuacao <= 1:
                raise RuntimeError("O modelo retornou uma pontuação de risco inválida.")
            pontuacoes[indice] = pontuacao

    for indice, registro in enumerate(registros):
        pontuacao = pontuacoes.get(indice)
        if pontuacao is None:
            respostas.append(
                PrevisaoRiscoModeloResponse(
                    id_estudante=registro["id_estudante"],
                    pontuacao_risco=None,
                    faixa_risco="SEM_PREVISAO_VALIDA",
                    status_acompanhamento="Dados insuficientes",
                    versao_modelo=VERSAO_MODELO,
                    data_processamento=agora,
                )
            )
            continue

        faixa, status_acompanhamento = _classificar_faixa(pontuacao)
        respostas.append(
            PrevisaoRiscoModeloResponse(
                id_estudante=registro["id_estudante"],
                pontuacao_risco=round(pontuacao, 6),
                faixa_risco=faixa,
                status_acompanhamento=status_acompanhamento,
                versao_modelo=VERSAO_MODELO,
                data_processamento=agora,
            )
        )
    return respostas
