
"""Tela de estudantes."""

import streamlit as st

from components.filtros import (
    botao_limpar_filtros,
    filtro_selecao,
)
from components.layout import titulo_pagina
from components.tabelas import tabela_paginada
from data import mock_data
from data.atribuicoes import listar_atribuicoes
from utils.formatacao import (
    decimal_br,
    numero_br,
    percentual_br,
)


CHAVES_FILTROS = [
    "est_busca",
    "est_serie",
    "est_turma",
    "est_turno",
    "est_risco",
]


def aplicar_responsividade():
    """Adapta os filtros e a tabela em telas menores."""

    st.html(
        """
        <style>
            /* Mantém os conteúdos dentro da página. */

            .st-key-estudantes_filtros,
            .st-key-estudantes_resumo,
            .st-key-estudantes_tabela {
                width: 100%;
                max-width: 100%;
                min-width: 0;
                box-sizing: border-box;
            }

            /* Os campos não devem ultrapassar suas colunas. */

            .st-key-estudantes_filtros
            [data-testid="stColumn"],
            .st-key-estudantes_resumo
            [data-testid="stColumn"] {
                min-width: 0 !important;
            }

            /* A tabela pode rolar horizontalmente. */

            .st-key-estudantes_tabela {
                overflow-x: auto;
                overflow-y: visible;
            }

            .st-key-estudantes_tabela
            [data-testid="stDataFrame"] {
                width: 100%;
                min-width: 0;
                max-width: 100%;
            }

            /* Tablet */

            @media (min-width: 601px) and (max-width: 1100px) {

                /* Seis filtros distribuídos em duas colunas. */

                .st-key-estudantes_filtros
                > [data-testid="stVerticalBlock"]
                > [data-testid="stHorizontalBlock"] {
                    display: grid !important;

                    grid-template-columns:
                        repeat(2, minmax(0, 1fr)) !important;

                    gap: 12px !important;
                    width: 100% !important;
                    align-items: end !important;
                }

                .st-key-estudantes_filtros
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                }

                /* Resumo e exportação continuam lado a lado. */

                .st-key-estudantes_resumo
                [data-testid="stHorizontalBlock"] {
                    align-items: center !important;
                }
            }

            /* Celular */

            @media (max-width: 600px) {

                /* Cada filtro ocupa a linha inteira. */

                .st-key-estudantes_filtros
                > [data-testid="stVerticalBlock"]
                > [data-testid="stHorizontalBlock"] {
                    display: grid !important;

                    grid-template-columns:
                        minmax(0, 1fr) !important;

                    gap: 10px !important;
                    width: 100% !important;
                }

                .st-key-estudantes_filtros
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                /* Busca e seletores com largura completa. */

                .st-key-estudantes_filtros
                [data-testid="stTextInput"],
                .st-key-estudantes_filtros
                [data-testid="stSelectbox"],
                .st-key-estudantes_filtros
                [data-testid="stButton"] {
                    width: 100% !important;
                    max-width: 100% !important;
                }

                /* Quantidade de estudantes e exportação. */

                .st-key-estudantes_resumo
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;

                    grid-template-columns:
                        minmax(0, 1fr) !important;

                    gap: 10px !important;
                    width: 100% !important;
                }

                .st-key-estudantes_resumo
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                }

                .st-key-estudantes_resumo
                [data-testid="stDownloadButton"],
                .st-key-estudantes_resumo
                [data-testid="stDownloadButton"] button {
                    width: 100% !important;
                }

                /* A tabela não aumenta a largura da página. */

                .st-key-estudantes_tabela {
                    max-width: 100% !important;
                    overflow-x: auto !important;
                }
            }
        </style>
        """
    )


def filtrar_por_professor(dados):
    """Retorna os estudantes das turmas atribuídas ao professor."""

    if st.session_state.get("perfil") == "administrador":
        return dados

    professor = st.session_state.get("professor_atual")

    atribuicoes = [
        item
        for item in listar_atribuicoes()
        if item["Professor"] == professor
    ]

    turmas_permitidas = {
        item["Turma"]
        for item in atribuicoes
    }

    turma_estudante = (
        dados["Série"]
        .str.replace(" ano", "", regex=False)
        + " "
        + dados["Turma"]
    )

    return dados.loc[
        turma_estudante.isin(turmas_permitidas)
    ].copy()


def obter_opcoes_filtro(dados, coluna):
    """Obtém as opções disponíveis para um filtro."""

    return sorted(
        dados[coluna]
        .dropna()
        .unique()
        .tolist()
    )


def validar_filtro(chave, opcoes):
    """Limpa seleções que não estão mais disponíveis."""

    valor_atual = st.session_state.get(chave)

    if valor_atual and valor_atual not in opcoes:
        st.session_state[chave] = None


def _filtrar(dados, busca, serie, turma, turno, risco):
    """Aplica os filtros selecionados à tabela."""

    if busca:
        dados = dados[
            dados["Identificador"].str.contains(
                busca,
                case=False,
                regex=False,
                na=False,
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
    """Formata os valores apresentados na tabela."""

    tabela = dados.copy()

    tabela["Frequência"] = tabela["Frequência"].map(
        percentual_br
    )

    tabela["Média geral"] = tabela["Média geral"].map(
        decimal_br
    )

    return tabela


def render():
    """Renderiza a página de estudantes."""

    aplicar_responsividade()
    titulo_pagina("Estudantes")

    estudantes_permitidos = filtrar_por_professor(
        st.session_state.get("entrada_importacoes", {}).get(
            "Estudantes", mock_data.ESTUDANTES
        )
    )

    series_disponiveis = obter_opcoes_filtro(
        estudantes_permitidos,
        "Série",
    )

    validar_filtro(
        "est_serie",
        series_disponiveis,
    )

    serie_atual = st.session_state.get("est_serie")

    dados_da_serie = estudantes_permitidos

    if serie_atual:
        dados_da_serie = estudantes_permitidos[
            estudantes_permitidos["Série"] == serie_atual
        ]

    turmas_disponiveis = obter_opcoes_filtro(
        dados_da_serie,
        "Turma",
    )

    validar_filtro(
        "est_turma",
        turmas_disponiveis,
    )

    turnos_disponiveis = obter_opcoes_filtro(
        estudantes_permitidos,
        "Turno",
    )

    riscos_disponiveis = obter_opcoes_filtro(
        estudantes_permitidos,
        "Risco",
    )

    validar_filtro(
        "est_turno",
        turnos_disponiveis,
    )

    validar_filtro(
        "est_risco",
        riscos_disponiveis,
    )

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
                series_disponiveis,
                "est_serie",
                todos="Todas",
            )

        with col_turma:
            turma = filtro_selecao(
                "Turma",
                turmas_disponiveis,
                "est_turma",
                todos="Todas",
            )

        with col_turno:
            turno = filtro_selecao(
                "Turno",
                turnos_disponiveis,
                "est_turno",
                todos="Todos",
            )

        with col_risco:
            risco = filtro_selecao(
                "Faixa de risco",
                riscos_disponiveis,
                "est_risco",
                todos="Todas",
            )

        with col_limpar:
            botao_limpar_filtros(CHAVES_FILTROS)

    estudantes = _filtrar(
        estudantes_permitidos,
        busca,
        serie,
        turma,
        turno,
        risco,
    )

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
