"""Tela: Visão geral."""
import streamlit as st

from components.cards import card, card_kpi
from components.graficos import (
    grafico_barras_horizontais, grafico_dispersao, grafico_linha, grafico_rosca,
)
from components.layout import titulo_pagina
from data import mock_data


CORES_KPI = ["azul", "verde", "laranja", "vermelho"]  # uma cor para cada cartão, na ordem

def render():
    # Os dados desta tela ainda vêm dos mocks do projeto.
    titulo_pagina("Visão geral", destaque=mock_data.PERIODO_ATUAL)

    # Linha de indicadores
    colunas_kpi = st.columns(4)
    for coluna, cor, (valor, rotulo, rodape) in zip(colunas_kpi, CORES_KPI, mock_data.KPIS_VISAO_GERAL):
        with coluna:
            card_kpi(valor, rotulo, rodape, cor)

    # Primeira linha de gráficos
    col_frequencia, col_risco = st.columns(2)
    with col_frequencia:
        with card("Frequência média"):
            st.plotly_chart(
                grafico_linha(mock_data.FREQUENCIA_POR_SERIE, "Mês", "Frequência (%)", "Série"),
                width="stretch",
            )
    with col_risco:
        with card("Distribuição de risco"):
            st.plotly_chart(
                grafico_rosca(mock_data.DISTRIBUICAO_RISCO, "Nível de risco", "Estudantes"),
                width="stretch",
            )

    # Segunda linha de gráficos
    col_serie, col_notas = st.columns(2)
    with col_serie:
        with card("Risco por série"):
            st.plotly_chart(
                grafico_barras_horizontais(
                    mock_data.ALTO_RISCO_POR_SERIE, "Estudantes em alto risco", "Série"),
                width="stretch",
            )
    with col_notas:
        with card("Notas x frequência"):
            st.plotly_chart(
                grafico_dispersao(mock_data.NOTAS_X_FREQUENCIA, "Frequência (%)", "Média geral"),
                width="stretch",
            )

    # Tabela
    with card("Estudantes que exigem atenção"):
        st.dataframe(mock_data.ESTUDANTES_EM_ATENCAO, hide_index=True, width="stretch")