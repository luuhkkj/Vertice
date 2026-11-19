"""Treinamento reprodutível e avaliação comparativa do modelo de risco acadêmico."""

import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen
import zipfile

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.integrations.prediction.modelo_risco import (
    CAMINHO_ARTEFATO_PADRAO,
    LIMIAR_ALTO,
    LIMIAR_BAIXO,
    VERSAO_MODELO,
)

URL_BASE_UCI = "https://archive.ics.uci.edu/static/public/320/student+performance.zip"
CAMINHO_RELATORIO_PADRAO = (
    Path(__file__).resolve().parents[3] / "docs" / "RELATORIO_MODELO_RISCO.md"
)

FEATURES = ["idade", "historico_reprovacao", "nota_t1"]
GRUPOS_PERFIL = [
    "school",
    "sex",
    "age",
    "address",
    "famsize",
    "Pstatus",
    "Medu",
    "Fedu",
    "Mjob",
    "Fjob",
    "reason",
    "guardian",
    "traveltime",
    "studytime",
    "failures",
    "schoolsup",
    "famsup",
    "paid",
    "activities",
    "nursery",
    "higher",
    "internet",
    "romantic",
    "famrel",
    "freetime",
    "goout",
    "Dalc",
    "Walc",
    "health",
]

PARAMETROS_MODELOS: dict[str, dict[str, Any]] = {
    "baseline": {"strategy": "most_frequent"},
    "regressao_logistica": {
        "C": 1.0,
        "class_weight": "balanced",
        "max_iter": 2000,
        "solver": "liblinear",
        "random_state": 42,
        "imputacao": "mediana",
        "padronizacao": "StandardScaler",
    },
    "random_forest": {
        "n_estimators": 300,
        "max_depth": 6,
        "min_samples_leaf": 4,
        "class_weight": "balanced_subsample",
        "random_state": 42,
        "n_jobs": 1,
        "imputacao": "mediana",
    },
}


def carregar_base_uci() -> pd.DataFrame:
    """Baixa em memória os dois arquivos públicos usados pelo notebook."""
    try:
        with urlopen(URL_BASE_UCI, timeout=30) as resposta:
            arquivo_zip = zipfile.ZipFile(BytesIO(resposta.read()))
    except (URLError, TimeoutError, zipfile.BadZipFile) as exc:
        raise RuntimeError(
            "Não foi possível carregar o dataset público UCI. Verifique a conexão "
            f"e tente novamente: {URL_BASE_UCI}"
        ) from exc

    with arquivo_zip:
        if "student.zip" in arquivo_zip.namelist():
            with zipfile.ZipFile(BytesIO(arquivo_zip.read("student.zip"))) as dados:
                matematica = pd.read_csv(dados.open("student-mat.csv"), sep=";")
                portugues = pd.read_csv(dados.open("student-por.csv"), sep=";")
        else:
            matematica = pd.read_csv(arquivo_zip.open("student-mat.csv"), sep=";")
            portugues = pd.read_csv(arquivo_zip.open("student-por.csv"), sep=";")

    matematica["disciplina_origem"] = "matematica"
    portugues["disciplina_origem"] = "portugues"
    return pd.concat([matematica, portugues], ignore_index=True)


def preparar_base_modelagem(
    dados: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict[str, Any]]:
    """Cria o alvo combinado e as features disponíveis ao fim do primeiro período."""
    ausencias = pd.to_numeric(dados["absences"], errors="raise")
    nota_t1 = (pd.to_numeric(dados["G1"], errors="raise") / 2).round(1)
    nota_t2 = (pd.to_numeric(dados["G2"], errors="raise") / 2).round(1)
    nota_t3 = (pd.to_numeric(dados["G3"], errors="raise") / 2).round(1)
    frequencia_anual = (((200 - ausencias) / 200) * 100).clip(0, 100)
    media_final = ((nota_t1 + nota_t2 + nota_t3) / 3).round(1)

    situacao_final = np.select(
        [
            (frequencia_anual < 75.0) | (nota_t3 == 0.0),
            media_final < 5.0,
        ],
        ["Evadido", "Reprovado"],
        default="Aprovado",
    )
    alvo_risco = pd.Series(
        (situacao_final != "Aprovado").astype(int),
        index=dados.index,
        name="desfecho_desfavoravel_proxy",
    )

    # O primeiro período é o único desempenho do notebook observado no corte definido.
    features = pd.DataFrame(
        {
            "idade": pd.to_numeric(dados["age"], errors="raise"),
            "historico_reprovacao": pd.to_numeric(
                dados["failures"],
                errors="raise",
            ),
            "nota_t1": nota_t1,
        },
        index=dados.index,
    )
    grupos = pd.util.hash_pandas_object(
        dados[GRUPOS_PERFIL].astype(str),
        index=False,
    ).astype(str)
    metadados = {
        "total_registros": int(len(dados)),
        "registros_por_disciplina": {
            str(chave): int(valor)
            for chave, valor in dados["disciplina_origem"].value_counts().items()
        },
        "situacao_final_derivada": {
            str(chave): int(valor)
            for chave, valor in pd.Series(situacao_final).value_counts().items()
        },
        "total_grupos_perfil": int(grupos.nunique()),
        "rótulos_risco_proxy": {
            "aprovado": int((alvo_risco == 0).sum()),
            "reprovado_ou_evadido": int((alvo_risco == 1).sum()),
        },
        "features": FEATURES,
    }
    return features, alvo_risco, grupos, metadados


def _criar_candidatos() -> dict[str, Pipeline]:
    return {
        "baseline": Pipeline(
            [
                ("imputacao", SimpleImputer(strategy="median")),
                ("classificador", DummyClassifier(strategy="most_frequent")),
            ]
        ),
        "regressao_logistica": Pipeline(
            [
                ("imputacao", SimpleImputer(strategy="median")),
                ("escala", StandardScaler()),
                (
                    "classificador",
                    LogisticRegression(
                        C=1.0,
                        class_weight="balanced",
                        max_iter=2000,
                        solver="liblinear",
                        random_state=42,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("imputacao", SimpleImputer(strategy="median")),
                (
                    "classificador",
                    RandomForestClassifier(
                        n_estimators=300,
                        max_depth=6,
                        min_samples_leaf=4,
                        class_weight="balanced_subsample",
                        random_state=42,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
    }


def _probabilidade_risco(modelo: Any, features: pd.DataFrame) -> np.ndarray:
    classes = list(modelo.classes_)
    if 1 not in classes:
        raise RuntimeError("Classificador não treinou a classe positiva.")
    return modelo.predict_proba(features)[:, classes.index(1)]


def _metricas(
    y_real: pd.Series,
    predicoes: np.ndarray,
    probabilidades: np.ndarray,
) -> dict[str, Any]:
    precisao, revocacao, f1, suporte = precision_recall_fscore_support(
        y_real,
        predicoes,
        labels=[0, 1],
        zero_division=0,
    )
    matriz = confusion_matrix(y_real, predicoes, labels=[0, 1])
    metricas: dict[str, Any] = {
        "n": int(len(y_real)),
        "acuracia": float(accuracy_score(y_real, predicoes)),
        "precisao_macro": float(
            precision_recall_fscore_support(
                y_real,
                predicoes,
                average="macro",
                zero_division=0,
            )[0]
        ),
        "revocacao_macro": float(
            precision_recall_fscore_support(
                y_real,
                predicoes,
                average="macro",
                zero_division=0,
            )[1]
        ),
        "f1_macro": float(f1_score(y_real, predicoes, average="macro", zero_division=0)),
        "precisao_risco": float(precisao[1]),
        "revocacao_risco": float(revocacao[1]),
        "f1_risco": float(f1[1]),
        "classes": {
            "aprovado": {
                "precisao": float(precisao[0]),
                "revocacao": float(revocacao[0]),
                "f1": float(f1[0]),
                "suporte": int(suporte[0]),
            },
            "reprovado_ou_evadido_proxy": {
                "precisao": float(precisao[1]),
                "revocacao": float(revocacao[1]),
                "f1": float(f1[1]),
                "suporte": int(suporte[1]),
            },
        },
        "matriz_confusao": matriz.tolist(),
        "falsos_positivos": int(matriz[0, 1]),
        "falsos_negativos": int(matriz[1, 0]),
        "brier": float(brier_score_loss(y_real, probabilidades)),
        "roc_auc": float(roc_auc_score(y_real, probabilidades)),
        "average_precision": float(average_precision_score(y_real, probabilidades)),
    }
    return metricas


def _avaliar_faixas(
    y_real: pd.Series,
    probabilidades: np.ndarray,
) -> list[dict[str, Any]]:
    faixas = [
        ("BAIXO", 0.0, LIMIAR_BAIXO, "Estável"),
        ("MODERADO", LIMIAR_BAIXO, LIMIAR_ALTO, "Atenção"),
        ("ALTO", LIMIAR_ALTO, 1.0000001, "Prioritário"),
    ]
    resultado = []
    for nome, limite_inferior, limite_superior, status_acompanhamento in faixas:
        mascara = (probabilidades >= limite_inferior) & (
            probabilidades < limite_superior
        )
        suporte = int(mascara.sum())
        resultado.append(
            {
                "faixa": nome,
                "limite_inferior": limite_inferior,
                "limite_superior": (
                    None if nome == "ALTO" else limite_superior
                ),
                "status_acompanhamento": status_acompanhamento,
                "estudantes": suporte,
                "taxa_desfecho_proxy": (
                    float(y_real.iloc[np.flatnonzero(mascara)].mean())
                    if suporte
                    else None
                ),
            }
        )
    return resultado


def _calibrar(
    modelo: Pipeline,
    features_validacao: pd.DataFrame,
    alvo_validacao: pd.Series,
) -> CalibratedClassifierCV:
    calibrado = CalibratedClassifierCV(
        estimator=FrozenEstimator(modelo),
        method="sigmoid",
    )
    calibrado.fit(features_validacao, alvo_validacao)
    return calibrado


def _avaliar_modelos(
    dados: pd.DataFrame,
) -> dict[str, Any]:
    features, alvo, grupos, metadados_dados = preparar_base_modelagem(dados)
    particionador_teste = StratifiedGroupKFold(
        n_splits=5,
        shuffle=True,
        random_state=42,
    )
    indices_treino_validacao, indices_teste = next(
        particionador_teste.split(features, alvo, grupos)
    )
    particionador_validacao = StratifiedGroupKFold(
        n_splits=4,
        shuffle=True,
        random_state=43,
    )
    indices_treino_relativos, indices_validacao_relativos = next(
        particionador_validacao.split(
            features.iloc[indices_treino_validacao],
            alvo.iloc[indices_treino_validacao],
            grupos.iloc[indices_treino_validacao],
        )
    )
    indices_treino = indices_treino_validacao[indices_treino_relativos]
    indices_validacao = indices_treino_validacao[indices_validacao_relativos]

    conjuntos = {
        "treino": set(grupos.iloc[indices_treino]),
        "validacao": set(grupos.iloc[indices_validacao]),
        "teste": set(grupos.iloc[indices_teste]),
    }
    if (
        conjuntos["treino"] & conjuntos["validacao"]
        or conjuntos["treino"] & conjuntos["teste"]
        or conjuntos["validacao"] & conjuntos["teste"]
    ):
        raise RuntimeError("Um grupo de perfil apareceu em mais de uma partição.")

    candidatos = _criar_candidatos()
    resultados_validacao: dict[str, Any] = {}
    estimadores: dict[str, Pipeline] = {}
    for nome, estimador in candidatos.items():
        estimador.fit(features.iloc[indices_treino], alvo.iloc[indices_treino])
        estimadores[nome] = estimador
        predicoes = estimador.predict(features.iloc[indices_validacao])
        probabilidades = _probabilidade_risco(
            estimador,
            features.iloc[indices_validacao],
        )
        resultados_validacao[nome] = _metricas(
            alvo.iloc[indices_validacao],
            predicoes,
            probabilidades,
        )

    maior_f1 = max(
        resultados_validacao[nome]["f1_macro"]
        for nome in ("regressao_logistica", "random_forest")
    )
    margem_interpretabilidade = 0.02
    if (
        resultados_validacao["regressao_logistica"]["f1_macro"]
        >= maior_f1 - margem_interpretabilidade
    ):
        modelo_escolhido = "regressao_logistica"
    else:
        modelo_escolhido = "random_forest"

    calibrados: dict[str, Any] = {
        "baseline": estimadores["baseline"],
    }
    for nome in ("regressao_logistica", "random_forest"):
        calibrados[nome] = _calibrar(
            estimadores[nome],
            features.iloc[indices_validacao],
            alvo.iloc[indices_validacao],
        )

    resultados_teste: dict[str, Any] = {}
    probabilidades_teste: dict[str, np.ndarray] = {}
    for nome, estimador in calibrados.items():
        probabilidades = _probabilidade_risco(
            estimador,
            features.iloc[indices_teste],
        )
        probabilidades_teste[nome] = probabilidades
        resultados_teste[nome] = _metricas(
            alvo.iloc[indices_teste],
            (probabilidades >= 0.5).astype(int),
            probabilidades,
        )

    modelo_final = calibrados[modelo_escolhido]
    probabilidade_final = probabilidades_teste[modelo_escolhido]
    fracao_teste = {
        nome: len(indices)
        for nome, indices in (
            ("treino", indices_treino),
            ("validacao", indices_validacao),
            ("teste", indices_teste),
        )
    }
    fracao_teste["grupos_por_particao"] = {
        nome: len(grupos_particao)
        for nome, grupos_particao in conjuntos.items()
    }
    coeficientes_logistica = estimadores["regressao_logistica"].named_steps[
        "classificador"
    ].coef_[0]
    resultado: dict[str, Any] = {
        "versao_modelo": VERSAO_MODELO,
        "modelo_escolhido": modelo_escolhido,
        "features": FEATURES,
        "data": metadados_dados,
        "particoes": fracao_teste,
        "metricas_validacao": resultados_validacao,
        "metricas_teste": resultados_teste,
        "faixas_teste": _avaliar_faixas(
            alvo.iloc[indices_teste],
            probabilidade_final,
        ),
        "calibracao_teste": _calibracao_teste(
            alvo.iloc[indices_teste],
            probabilidade_final,
        ),
        "parametros": PARAMETROS_MODELOS,
        "coeficientes_regressao_logistica": {
            feature: float(coeficiente)
            for feature, coeficiente in zip(
                FEATURES,
                coeficientes_logistica,
                strict=True,
            )
        },
        "matriz_teste": {
            "alvo": alvo.iloc[indices_teste].astype(int).tolist(),
            "probabilidade": [float(x) for x in probabilidade_final],
        },
        "_modelo_final": modelo_final,
        "_pacote_python": {
            "python": sys.version.split()[0],
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "joblib": joblib.__version__,
        },
    }
    return resultado


def _calibracao_teste(
    y_real: pd.Series,
    probabilidades: np.ndarray,
) -> list[dict[str, float]]:
    observado, previsto = calibration_curve(
        y_real,
        probabilidades,
        n_bins=5,
        strategy="quantile",
    )
    return [
        {
            "probabilidade_media": float(p),
            "frequencia_observada": float(o),
        }
        for o, p in zip(observado, previsto, strict=True)
    ]


def _formatar_metricas(tabela: dict[str, dict[str, Any]], nomes: list[str]) -> str:
    cabecalho = (
        "| Modelo | Acurácia | Precisão macro | Revocação macro | F1 macro | "
        "Precisão risco | Revocação risco | F1 risco | Brier |"
    )
    divisor = "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
    linhas = [cabecalho, divisor]
    nomes_legiveis = {
        "baseline": "Baseline (classe majoritária)",
        "regressao_logistica": "Regressão Logística",
        "random_forest": "Random Forest",
    }
    for nome in nomes:
        item = tabela[nome]
        linhas.append(
            f"| {nomes_legiveis.get(nome, nome)} | {item['acuracia']:.3f} | "
            f"{item['precisao_macro']:.3f} | "
            f"{item['revocacao_macro']:.3f} | {item['f1_macro']:.3f} | "
            f"{item['precisao_risco']:.3f} | {item['revocacao_risco']:.3f} | "
            f"{item['f1_risco']:.3f} | {item['brier']:.3f} |"
        )
    return "\n".join(linhas)


def gerar_relatorio(resultado: dict[str, Any]) -> str:
    """Gera relatório Markdown com configuração, comparação e limitações."""
    nomes = ["baseline", "regressao_logistica", "random_forest"]
    metricas_teste = resultado["metricas_teste"]
    linhas_faixa = [
        "| Faixa | Pontuação | Status sugerido | Estudantes no teste | "
        "Taxa observada do rótulo proxy |",
        "|---|---|---|---:|---:|",
    ]
    for item in resultado["faixas_teste"]:
        intervalo = (
            f"[{item['limite_inferior']:.3f}, {item['limite_superior']:.3f})"
            if item["limite_superior"] is not None
            else f"[{item['limite_inferior']:.3f}, 1.000]"
        )
        taxa = (
            f"{item['taxa_desfecho_proxy']:.3f}"
            if item["taxa_desfecho_proxy"] is not None
            else "sem casos"
        )
        linhas_faixa.append(
            f"| {item['faixa']} | {intervalo} | "
            f"{item['status_acompanhamento']} | {item['estudantes']} | {taxa} |"
        )

    linhas_classes = [
        "| Classe real | Precisão | Revocação | F1-score | Suporte |",
        "|---|---:|---:|---:|---:|",
    ]
    escolhido = metricas_teste[resultado["modelo_escolhido"]]
    for classe, valores in escolhido["classes"].items():
        linhas_classes.append(
            f"| {classe} | {valores['precisao']:.3f} | {valores['revocacao']:.3f} | "
            f"{valores['f1']:.3f} | {valores['suporte']} |"
        )
    linhas_coeficientes = [
        "| Variável | Coeficiente logístico padronizado | Direção associativa |",
        "|---|---:|---|",
    ]
    for feature, coeficiente in resultado[
        "coeficientes_regressao_logistica"
    ].items():
        direcao = (
            "maior score do rótulo proxy"
            if coeficiente > 0
            else "menor score do rótulo proxy"
        )
        linhas_coeficientes.append(
            f"| {feature} | {coeficiente:.3f} | {direcao} |"
        )

    matriz = escolhido["matriz_confusao"]
    return f"""# Relatório de avaliação do modelo de risco acadêmico

## Decisões e escopo

- **Previsão:** desfecho acadêmico desfavorável combinado (`Reprovado` ou `Evadido`) ao fim do ano.
- **Momento da previsão:** após o primeiro período letivo.
- **Variáveis de entrada:** idade, histórico de reprovações anterior e nota do primeiro período (`G1 / 2`).
- **Referência usada:** notebook `notebooks/dados_estudantes.ipynb`, que combina os arquivos públicos UCI de Matemática e Português.
- **Limitação fundamental:** o notebook não contém rótulo histórico observado de evasão. Ele cria `situacao_final` por regra a partir de frequência anual, nota do terceiro período e média final. Portanto, as métricas abaixo avaliam a capacidade de reproduzir esse **rótulo proxy**, não a capacidade validada de prever resultados reais dos estudantes do Vértice.

## Dados e corte temporal

- Registros: **{resultado['data']['total_registros']}** (Matemática: {resultado['data']['registros_por_disciplina'].get('matematica', 0)}; Português: {resultado['data']['registros_por_disciplina'].get('portugues', 0)}).
- `situacao_final` reproduzida do notebook: {json.dumps(resultado['data']['situacao_final_derivada'], ensure_ascii=False)}.
- Rótulo de risco combinado: {json.dumps(resultado['data']['rótulos_risco_proxy'], ensure_ascii=False)}.
- Features no modelo: `{', '.join(resultado['features'])}`. `G2`, `G3`, `media_geral`, ausências/frequência anual e `situacao_final` não entram como preditores.
- Divisão agrupada: treino {resultado['particoes']['treino']}, validação {resultado['particoes']['validacao']}, teste {resultado['particoes']['teste']} registros. Os grupos são fingerprints de atributos estáveis porque o dataset não fornece um identificador real de aluno; isso reduz, mas não prova que elimina, contaminação entre disciplinas.
- Semente: 42 (partição de teste) e 43 (validação); imputação por mediana e transformações fazem parte dos pipelines.

## Modelos, parâmetros e validação

| Modelo | Parâmetros |
|---|---|
| Baseline | `DummyClassifier(strategy='most_frequent')` |
| Regressão logística | `C=1.0`, `class_weight='balanced'`, `solver='liblinear'`, `max_iter=2000`, `random_state=42`; mediana + padronização |
| Random Forest | `n_estimators=300`, `max_depth=6`, `min_samples_leaf=4`, `class_weight='balanced_subsample'`, `random_state=42`; mediana |

O modelo foi escolhido na validação pelo F1 macro. Se a regressão logística ficar até 0,020 abaixo do melhor F1 macro, ela é escolhida por ser mais interpretável. A calibração sigmoid é ajustada na validação; o teste fica separado. A seleção resultou em **{resultado['modelo_escolhido']}**.

### Validação (seleção do modelo)

{_formatar_metricas(resultado['metricas_validacao'], nomes)}

### Teste agrupado (avaliação final)

{_formatar_metricas(metricas_teste, nomes)}

No teste do modelo escolhido, matriz de confusão (linhas: real aprovado/risco; colunas: previsto aprovado/risco) é `[[{matriz[0][0]}, {matriz[0][1]}], [{matriz[1][0]}, {matriz[1][1]}]]`. Foram observados **{escolhido['falsos_positivos']} falsos positivos** (acompanhamento sugerido para rótulo proxy aprovado) e **{escolhido['falsos_negativos']} falsos negativos** (rótulo proxy desfavorável não identificado).

### Desempenho por classe

{chr(10).join(linhas_classes)}

### Interpretação

Os coeficientes abaixo são da Regressão Logística, medidos por desvio-padrão após `StandardScaler`; indicam associação com o rótulo proxy, não causalidade. A escolha desse modelo mantém uma regra linear auditável e teve F1 macro de validação empatado com a Random Forest.

{chr(10).join(linhas_coeficientes)}

### Probabilidade e faixas de acompanhamento

Brier score no teste: **{escolhido['brier']:.3f}** (menor é melhor; 0 é perfeito). A calibração foi medida apenas contra o rótulo proxy derivado do notebook, não contra desfechos reais do Vértice.

{chr(10).join(linhas_faixa)}

Os limites são divisões iniciais de um score calibrado em três partes iguais: baixo `< 0,333`, moderado `0,333–<0,667` e alto `>=0,667`. São critérios de triagem a validar com educadores e dados reais; não são decisões automáticas.

| Faixa | Status sugerido |
|---|---|
| Baixo | Estável |
| Moderado | Atenção |
| Alto | Prioritário |
| Sem previsão válida | Dados insuficientes |

## Limitações e uso responsável

1. A situação final do notebook é construída por regra e não distingue evasão observada de nota final zero/frequência anual baixa.
2. O identificador `ALU_...` do notebook é gerado pelo índice da linha, não é uma chave real. Grupos por fingerprint não substituem o identificador longitudinal correto.
3. O dataset público é pequeno e não representa necessariamente escolas, períodos ou critérios de aprovação do Vértice.
4. As features disponíveis no corte são limitadas; resultados não demonstram causalidade.
5. Ausência da nota do primeiro período ou de ambas as variáveis de contexto retorna **Sem previsão válida / Dados insuficientes**; não se imputa quando não existe o mínimo de informação.
6. A função e o artefato são uma prova de conceito. Antes de uso operacional, treine e avalie com desfechos históricos reais do Vértice, chave de estudante longitudinal e validação temporal externa.

Gerado em {datetime.now(timezone.utc).isoformat()} com Python {resultado['_pacote_python']['python']}, scikit-learn {resultado['_pacote_python']['scikit_learn']} e pandas {resultado['_pacote_python']['pandas']}.
"""


def treinar_e_avaliar(
    *,
    caminho_artefato: Path = CAMINHO_ARTEFATO_PADRAO,
    caminho_relatorio: Path = CAMINHO_RELATORIO_PADRAO,
) -> dict[str, Any]:
    dados = carregar_base_uci()
    resultado = _avaliar_modelos(dados)
    report = gerar_relatorio(resultado)

    caminho_artefato.parent.mkdir(parents=True, exist_ok=True)
    caminho_relatorio.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "modelo": resultado["_modelo_final"],
            "features": FEATURES,
            "versao_modelo": VERSAO_MODELO,
            "modelo_nome": resultado["modelo_escolhido"],
            "limiar_baixo": LIMIAR_BAIXO,
            "limiar_alto": LIMIAR_ALTO,
            "parametros": PARAMETROS_MODELOS[resultado["modelo_escolhido"]],
            "pacote_python": resultado["_pacote_python"],
            "dataset_url": URL_BASE_UCI,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
        },
        caminho_artefato,
        compress=3,
    )
    caminho_relatorio.write_text(report, encoding="utf-8")
    resultado["caminho_artefato"] = str(caminho_artefato)
    resultado["caminho_relatorio"] = str(caminho_relatorio)
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Treina e avalia o modelo de risco acadêmico de prova de conceito."
    )
    parser.add_argument(
        "--artefato",
        type=Path,
        default=CAMINHO_ARTEFATO_PADRAO,
    )
    parser.add_argument(
        "--relatorio",
        type=Path,
        default=CAMINHO_RELATORIO_PADRAO,
    )
    args = parser.parse_args()
    resultado = treinar_e_avaliar(
        caminho_artefato=args.artefato,
        caminho_relatorio=args.relatorio,
    )
    print(gerar_relatorio(resultado))
    print(f"\nArtefato salvo em: {resultado['caminho_artefato']}")
    print(f"Relatório salvo em: {resultado['caminho_relatorio']}")


if __name__ == "__main__":
    main()
