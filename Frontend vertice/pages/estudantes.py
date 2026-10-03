"""Tela: Estudantes."""

import streamlit as st

from components.filtros import botao_limpar_filtros, filtro_selecao
from components.layout import titulo_pagina
from components.tabelas import tabela_paginada
from data import mock_data
from utils.formatacao import decimal_br, numero_br, percentual_br


CHAVES_FILTROS = [
    "est_busca",
    "est_serie",
    "est_turma",
    "est_turno",
    "est_risco",
]


def _filtrar(dados, busca, serie, turma, turno, risco):
    """Aplica busca e filtros selecionados."""

    if busca:
        dados = dados[
            dados["Identificador"].str.contains(
                busca,
                case=False,
                regex=False,
            )
        ]

    for coluna, valor in (
        ("Série", serie),
        ("Turma", turma),
        ("Turno", turno),
        ("Risco", risco),
    ):
        if valor:
            dados = dados[dados[coluna] == valor]

    return dados


def _formatar_para_tabela(dados):
    """Formata frequência e média para exibição."""

    tabela = dados.copy()

    tabela["Frequência"] = (
        tabela["Frequência"].map(percentual_br)
    )

    tabela["Média geral"] = (
        tabela["Média geral"].map(decimal_br)
    )

    return tabela


def render():
    """Renderiza a tela de estudantes."""

    titulo_pagina("Estudantes")

    # Filtros
    with st.container(key="estudantes_filtros"):

        (
            col_busca,
            col_serie,
            col_turma,
            col_turno,
            col_risco,
            col_limpar,
        ) = st.columns(
            [3.4, 1, 1, 1.1, 1.4, 1.6],
            vertical_alignment="bottom",
        )

        with col_busca:
            busca = st.text_input(
                "Buscar por identificador",
                key="est_busca",
                placeholder="Buscar por identificador",
            )

        with col_serie:
            serie = filtro_selecao(
                "Série",
                mock_data.SERIES,
                "est_serie",
                todos="Todas",
            )

        with col_turma:
            turma = filtro_selecao(
                "Turma",
                mock_data.TURMAS,
                "est_turma",
                todos="Todas",
            )

        with col_turno:
            turno = filtro_selecao(
                "Turno",
                mock_data.TURNOS,
                "est_turno",
                todos="Todos",
            )

        with col_risco:
            risco = filtro_selecao(
                "Faixa de risco",
                mock_data.NIVEIS_RISCO,
                "est_risco",
                todos="Todas",
            )

        with col_limpar:
            botao_limpar_filtros(
                CHAVES_FILTROS
            )

    # Dados
    estudantes = _filtrar(
        mock_data.ESTUDANTES,
        busca,
        serie,
        turma,
        turno,
        risco,
    )

    # Contador + exportação
    with st.container(key="estudantes_resumo"):

        col_total, col_exportar = st.columns(
            [5, 1],
            vertical_alignment="center",
        )

        with col_total:
            st.markdown(
                f"**{numero_br(len(estudantes))}** "
                "estudantes encontrados"
            )

        with col_exportar:
            st.download_button(
                "↓  Exportar",
                data=estudantes.to_csv(
                    index=False
                ).encode("utf-8-sig"),
                file_name="estudantes.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # Tabela
    with st.container(key="estudantes_tabela"):

        tabela_paginada(
            _formatar_para_tabela(estudantes),
            tamanho_pagina=5,
            chave="est_pagina",
            reiniciar_quando=(
                busca,
                serie,
                turma,
                turno,
                risco,
            ),
        )