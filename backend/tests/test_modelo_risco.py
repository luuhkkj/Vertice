"""Testes focados do contrato local de inferência de risco."""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from app.integrations.prediction import prever_risco
from app.integrations.prediction.leakage import validar_variaveis_contra_leakage
from app.integrations.prediction.modelo_risco import VERSAO_MODELO


class _ModeloProbabilidadePorNota:
    classes_ = np.array([0, 1])

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        risco = features["nota_t1"].to_numpy(dtype=float) / 10
        return np.column_stack((1 - risco, risco))


def _salvar_artefato(caminho: Path) -> None:
    joblib.dump(
        {
            "modelo": _ModeloProbabilidadePorNota(),
            "features": ["idade", "historico_reprovacao", "nota_t1"],
            "versao_modelo": VERSAO_MODELO,
        },
        caminho,
    )


def test_prever_risco_retorna_insuficiencia_sem_carregar_modelo(
    tmp_path: Path,
) -> None:
    resultado = prever_risco(
        [
            {
                "id_estudante": "ALU-1",
                "idade": None,
                "historico_reprovacao": None,
                "nota_t1": None,
            }
        ],
        caminho_modelo=tmp_path / "inexistente.joblib",
    )

    assert len(resultado) == 1
    assert resultado[0].pontuacao_risco is None
    assert resultado[0].faixa_risco == "SEM_PREVISAO_VALIDA"
    assert resultado[0].status_acompanhamento == "Dados insuficientes"


def test_prever_risco_rejeita_alvo_e_features_pos_corte() -> None:
    with pytest.raises(ValueError, match="situacao_final"):
        prever_risco(
            [
                {
                    "id_estudante": "ALU-1",
                    "idade": 16,
                    "historico_reprovacao": 0,
                    "nota_t1": 8,
                    "situacao_final": "Aprovado",
                }
            ]
        )

    with pytest.raises(ValueError, match="nota_t3"):
        prever_risco(
            [
                {
                    "id_estudante": "ALU-1",
                    "idade": 16,
                    "historico_reprovacao": 0,
                    "nota_t1": 8,
                    "nota_t3": 9,
                }
            ]
        )


def test_contrato_de_variaveis_permite_nota_do_primeiro_periodo() -> None:
    resultado = validar_variaveis_contra_leakage(
        ["idade", "historico_reprovacoes", "nota_t1"],
        lancar_excecao=False,
    )

    assert resultado.valido is True
    assert resultado.variaveis_desconhecidas_rejeitadas == {}


def test_prever_risco_mapeia_score_e_status_e_aceita_aliases(
    tmp_path: Path,
) -> None:
    caminho_modelo = tmp_path / "modelo.joblib"
    _salvar_artefato(caminho_modelo)

    resultado = prever_risco(
        [
            {
                "id_aluno": "ALU-BAIXO",
                "age": 16,
                "failures": 0,
                "G1": 4,
            },
            {
                "id_estudante": "ALU-MODERADO",
                "idade": 17,
                "historico_reprovacoes": 1,
                "nota_t1": 5,
            },
            {
                "codigo_anonimo": "ALU-ALTO",
                "idade": 16,
                "historico_reprovacao": 0,
                "nota_t1": 9,
            },
            {
                "id_estudante": "ALU-SEM-DADOS",
                "idade": None,
                "historico_reprovacao": None,
                "nota_t1": 8,
            },
        ],
        caminho_modelo=caminho_modelo,
    )

    assert [item.faixa_risco for item in resultado] == [
        "BAIXO",
        "MODERADO",
        "ALTO",
        "SEM_PREVISAO_VALIDA",
    ]
    assert [item.status_acompanhamento for item in resultado] == [
        "Estável",
        "Atenção",
        "Prioritário",
        "Dados insuficientes",
    ]
    assert resultado[0].pontuacao_risco == 0.2
    assert resultado[1].pontuacao_risco == 0.5
    assert resultado[2].pontuacao_risco == 0.9
    assert resultado[0].versao_modelo == VERSAO_MODELO
    assert resultado[0].data_processamento.tzinfo is not None
