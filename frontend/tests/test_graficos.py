"""Testes de contrato visual dos gráficos reutilizados pelo frontend."""

from pathlib import Path
import sys

import pandas as pd

FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from components.graficos import (  # noqa: E402
    grafico_barras_horizontais,
    grafico_distribuicao_geral_acertos_avaliacao,
    grafico_linha,
)


def test_barras_horizontais_usam_valor_no_eixo_x_e_categoria_no_y() -> None:
    dados = pd.DataFrame(
        {
            "Série": ["1ª Série"],
            "Frequência média (%)": [80.0],
        }
    )

    figura = grafico_barras_horizontais(
        dados,
        x="Frequência média (%)",
        y="Série",
    )

    assert list(figura.data[0].x) == [80.0]
    assert list(figura.data[0].y) == ["1ª Série"]
    assert figura.layout.xaxis.rangemode == "tozero"


def test_distribuicao_de_acertos_usa_barras_horizontais_ordenadas() -> None:
    figura = grafico_distribuicao_geral_acertos_avaliacao(
        {
            "distribuicao_acertos_estudantes": [
                {
                    "quantidade_acertos": 1,
                    "total_questoes_avaliacao": 2,
                    "quantidade_estudantes": 3,
                    "percentual_estudantes": 60.0,
                },
                {
                    "quantidade_acertos": 2,
                    "total_questoes_avaliacao": 2,
                    "quantidade_estudantes": 2,
                    "percentual_estudantes": 40.0,
                },
            ]
        }
    )

    assert figura.data[0].orientation == "h"
    assert list(figura.data[0].x) == [3, 2]
    assert list(figura.data[0].y) == ["1/2 acertos", "2/2 acertos"]


def test_grafico_de_linha_mantem_pontos_visiveis_e_escala_definida() -> None:
    figura = grafico_linha(
        pd.DataFrame({"Período": ["2026 • 1º Bimestre"], "Frequência (%)": [80.0]}),
        x="Período",
        y="Frequência (%)",
        faixa_y=[0, 100],
    )

    assert figura.data[0].mode == "lines+markers"
    assert figura.data[0].marker.size == 8
    assert list(figura.layout.yaxis.range) == [0, 100]
