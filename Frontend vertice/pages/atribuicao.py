
"""Tela: Atribuição de Turmas aos Professores."""

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from data import mock_data
from data.atribuicoes import listar_atribuicoes


COLUNAS_TABELA = [
    "Professor",
    "Disciplina",
    "Turma",
]


def aplicar_responsividade():
    """Adapta os painéis de atribuição ao celular e tablet."""

    st.html(
        """
        <style>
            /* Mantém os painéis dentro da largura disponível. */

            .st-key-atribuicao_paineis,
            .st-key-atribuicao_formulario,
            .st-key-atribuicao_tabela {
                width: 100%;
                max-width: 100%;
                min-width: 0;
                box-sizing: border-box;
            }

            /* Evita que textos longos alarguem os painéis. */

            .st-key-atribuicao_formulario p,
            .st-key-atribuicao_tabela p {
                overflow-wrap: anywhere;
            }

            /* Os campos acompanham a largura do formulário. */

            .st-key-atribuicao_formulario
            [data-testid="stSelectbox"],
            .st-key-atribuicao_tabela
            [data-testid="stSelectbox"] {
                width: 100%;
                max-width: 100%;
                min-width: 0;
            }

            /* Mantém a tabela dentro do painel direito. */

            .st-key-atribuicao_tabela
            [data-testid="stDataFrame"] {
                width: 100% !important;
                max-width: 100% !important;
                min-width: 0 !important;
            }

            /* Tablet e celular */

            @media (max-width: 1000px) {

                /* Formulário acima da tabela. */

                .st-key-atribuicao_paineis
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 18px !important;
                    width: 100% !important;
                    align-items: start !important;
                }

                .st-key-atribuicao_paineis
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"],
                .st-key-atribuicao_paineis
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                    margin: 0 !important;
                }
            }

            /* Celular */

            @media (max-width: 600px) {

                .st-key-atribuicao_paineis {
                    width: 100% !important;
                    max-width: 100% !important;
                }

                /* Espaçamento entre formulário e tabela. */

                .st-key-atribuicao_paineis
                [data-testid="stHorizontalBlock"] {
                    gap: 16px !important;
                }

                /* Títulos menores para não quebrar demais. */

                .st-key-atribuicao_formulario h3,
                .st-key-atribuicao_tabela h3 {
                    font-size: 1.1rem !important;
                    line-height: 1.4 !important;
                }

                /* Botões largos e fáceis de tocar. */

                .st-key-atribuicao_formulario
                [data-testid="stButton"],
                .st-key-atribuicao_tabela
                [data-testid="stButton"] {
                    width: 100% !important;
                }

                .st-key-atribuicao_formulario
                [data-testid="stButton"] button,
                .st-key-atribuicao_tabela
                [data-testid="stButton"] button {
                    width: 100% !important;
                    min-height: 44px !important;
                }

                /* Impede que a tabela desloque a página. */

                .st-key-atribuicao_tabela {
                    overflow-x: auto;
                }
            }
        </style>
        """
    )


def _atribuir():
    """Valida e adiciona uma atribuição."""

    nova = {
        "Professor": st.session_state.get("at_professor"),
        "Disciplina": st.session_state.get("at_disciplina"),
        "Turma": st.session_state.get("at_turma"),
    }

    if not all(nova.values()):
        st.session_state["at_aviso"] = (
            "erro",
            "Selecione professor, disciplina e turma.",
        )
        return

    atribuicoes = listar_atribuicoes()

    if nova in atribuicoes:
        st.session_state["at_aviso"] = (
            "erro",
            "Esta atribuição já existe.",
        )
        return

    atribuicoes.append(nova)

    st.session_state["at_aviso"] = (
        "sucesso",
        f"{nova['Turma']} de {nova['Disciplina']} "
        f"atribuída a {nova['Professor']}.",
    )

    st.session_state["at_disciplina"] = None
    st.session_state["at_turma"] = None


def _remover():
    """Remove uma atribuição do professor selecionado."""

    professor = st.session_state.get("at_professor")
    escolha = st.session_state.get("at_remover")

    if not professor or not escolha:
        st.session_state["at_aviso"] = (
            "erro",
            "Selecione uma atribuição para remover.",
        )
        return

    atribuicoes = listar_atribuicoes()

    for item in atribuicoes:
        descricao = (
            f"{item['Disciplina']} • {item['Turma']}"
        )

        if (
            item["Professor"] == professor
            and descricao == escolha
        ):
            atribuicoes.remove(item)

            st.session_state["at_aviso"] = (
                "sucesso",
                f"Atribuição removida de {professor}.",
            )

            st.session_state["at_remover"] = None
            return


def _formulario():
    """Formulário para cadastrar vínculos."""

    with st.container(key="atribuicao_formulario"):
        st.markdown("### Nova atribuição")

        st.caption(
            "Selecione o professor, a disciplina e a turma."
        )

        st.selectbox(
            "Professor",
            mock_data.PROFESSORES,
            index=None,
            placeholder="Selecione o professor...",
            key="at_professor",
        )

        st.selectbox(
            "Disciplina",
            mock_data.DISCIPLINAS,
            index=None,
            placeholder="Selecione a disciplina...",
            key="at_disciplina",
        )

        st.selectbox(
            "Turma",
            mock_data.TURMAS_ATRIBUICAO,
            index=None,
            placeholder="Selecione a turma...",
            key="at_turma",
        )

        st.button(
            "Atribuir turma",
            key="btn_atribuir_turma",
            on_click=_atribuir,
            use_container_width=True,
        )


def _tabela_do_professor(professor):
    """Mostra e permite remover as atribuições."""

    atribuicoes = listar_atribuicoes()

    todas = pd.DataFrame(
        atribuicoes,
        columns=COLUNAS_TABELA,
    )

    if professor:
        do_professor = todas[
            todas["Professor"] == professor
        ]
    else:
        do_professor = todas.iloc[0:0]

    with st.container(key="atribuicao_tabela"):
        st.markdown("### Atribuições do professor")

        if not professor:
            st.caption(
                "Selecione um professor para visualizar "
                "suas turmas."
            )
        else:
            st.caption(
                f"Professor selecionado: {professor}"
            )

        st.dataframe(
            do_professor,
            hide_index=True,
            width="stretch",
        )

        if not professor:
            return

        if do_professor.empty:
            st.info(
                "Este professor ainda não possui "
                "turmas atribuídas."
            )
            return

        opcoes = [
            f"{item['Disciplina']} • {item['Turma']}"
            for item in do_professor.to_dict("records")
        ]

        if st.session_state.get("at_remover") not in opcoes:
            st.session_state["at_remover"] = None

        st.selectbox(
            "Selecione uma atribuição para remover",
            opcoes,
            index=None,
            placeholder="Escolha uma atribuição...",
            key="at_remover",
        )

        st.button(
            "Remover atribuição",
            key="btn_remover_atribuicao",
            on_click=_remover,
            use_container_width=True,
        )


def render():
    """Renderiza a página de atribuição."""

    aplicar_responsividade()

    if st.session_state.get("perfil") != "administrador":
        st.error(
            "Apenas administradores podem gerenciar turmas."
        )
        return

    listar_atribuicoes()

    titulo_pagina(
        "Atribuição de Turmas aos Professores",
        "Gerencie quais turmas e disciplinas estão "
        "vinculadas a cada professor.",
    )

    aviso = st.session_state.pop("at_aviso", None)

    if aviso:
        tipo, mensagem = aviso

        if tipo == "sucesso":
            st.success(mensagem)
        else:
            st.error(mensagem)

    with st.container(key="atribuicao_paineis"):

        col_formulario, col_tabela = st.columns(
            [1, 1.7],
            gap="large",
            vertical_alignment="top",
        )

        with col_formulario:
            _formulario()

        with col_tabela:
            _tabela_do_professor(
                st.session_state.get("at_professor")
            )
