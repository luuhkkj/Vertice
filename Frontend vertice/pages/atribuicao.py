"""Tela: Atribuição de Turmas aos Professores."""

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from data import mock_data


COLUNAS_TABELA = [
    "Professor",
    "Disciplina",
    "Turma",
]


def _atribuir():
    """Valida e registra uma nova atribuição."""

    nova = {
        "Professor": st.session_state.get(
            "at_professor"
        ),
        "Disciplina": st.session_state.get(
            "at_disciplina"
        ),
        "Turma": st.session_state.get(
            "at_turma"
        ),
    }

    if not all(nova.values()):

        st.session_state["at_aviso"] = (
            "erro",
            "Selecione o professor, "
            "a disciplina e a turma.",
        )

        return

    if nova in st.session_state[
        "at_atribuicoes"
    ]:

        st.session_state["at_aviso"] = (
            "erro",
            "Esta atribuição já existe.",
        )

        return

    # backend 
    # aqui a atribuição será enviada
    

    st.session_state[
        "at_atribuicoes"
    ].append(nova)

    st.session_state["at_aviso"] = (
        "sucesso",
        (
            f"{nova['Turma']} de "
            f"{nova['Disciplina']} "
            f"atribuída a "
            f"{nova['Professor']}."
        ),
    )

    st.session_state[
        "at_disciplina"
    ] = None

    st.session_state[
        "at_turma"
    ] = None


def _formulario():
    """Formulário de atribuição."""

    with st.container(
        key="atribuicao_formulario"
    ):

        st.markdown(
            "### Nova atribuição"
        )

        st.caption(
            "Selecione o professor, "
            "a disciplina e a turma."
        )

        st.selectbox(
            "Professor",
            mock_data.PROFESSORES,
            index=None,
            placeholder=(
                "Selecione o professor..."
            ),
            key="at_professor",
        )

        st.selectbox(
            "Disciplina",
            mock_data.DISCIPLINAS,
            index=None,
            placeholder=(
                "Selecione a disciplina..."
            ),
            key="at_disciplina",
        )

        st.selectbox(
            "Turma",
            mock_data.TURMAS_ATRIBUICAO,
            index=None,
            placeholder=(
                "Selecione a turma..."
            ),
            key="at_turma",
        )

        st.button(
            "Atribuir turma",
            key="btn_atribuir_turma",
            on_click=_atribuir,
            use_container_width=True,
        )


def _tabela_do_professor(
    professor,
):
    """Mostra as atribuições do professor selecionado."""

    todas = pd.DataFrame(
        st.session_state[
            "at_atribuicoes"
        ],
        columns=COLUNAS_TABELA,
    )

    if professor:

        do_professor = todas[
            todas["Professor"]
            == professor
        ]

    else:

        do_professor = todas.iloc[
            0:0
        ]

    with st.container(
        key="atribuicao_tabela"
    ):

        st.markdown(
            "### Atribuições do professor"
        )

        if professor:

            st.caption(
                f"Professor selecionado: "
                f"{professor}"
            )

        else:

            st.caption(
                "Selecione um professor "
                "para visualizar suas turmas."
            )

        st.dataframe(
            do_professor,
            hide_index=True,
            width="stretch",
        )

        if (
            professor
            and do_professor.empty
        ):

            st.info(
                "Este professor ainda "
                "não possui turmas atribuídas."
            )


def render():
    """Renderiza a página de atribuição."""

    titulo_pagina(
        "Atribuição de Turmas aos Professores",
        (
            "Gerencie quais turmas e "
            "disciplinas estão vinculadas "
            "a cada professor."
        ),
    )

    # Estado
    st.session_state.setdefault(
        "at_atribuicoes",
        [
            dict(atribuicao)
            for atribuicao
            in mock_data
            .ATRIBUICOES_INICIAIS
        ],
    )

    # Aviso
    aviso = st.session_state.pop(
        "at_aviso",
        None,
    )

    if aviso:

        tipo, texto = aviso

        if tipo == "sucesso":
            st.success(texto)

        else:
            st.error(texto)

    # Conteúdo
    col_formulario, col_tabela = (
        st.columns(
            [1, 1.7],
            gap="large",
            vertical_alignment="top",
        )
    )

    with col_formulario:

        _formulario()

    with col_tabela:

        _tabela_do_professor(
            st.session_state.get(
                "at_professor"
            )
        )