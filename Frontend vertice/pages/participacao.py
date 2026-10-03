"""Tela: Participação."""

import streamlit as st

from components.cards import card, card_kpi
from components.filtros import filtro_selecao
from components.graficos import (
    grafico_barras_horizontais,
    grafico_linha,
)
from components.layout import titulo_pagina
from components.tabelas import tabela_paginada
from data import mock_data
from utils.formatacao import (
    decimal_br,
    numero_br,
    percentual_br,
)


@st.dialog("Inserir atividade")
def _dialogo_inserir_atividade():
    """Modal para inserir uma nova atividade."""

    nome = st.text_input(
        "Nome da atividade"
    )

    st.selectbox(
        "Disciplina",
        mock_data.DISCIPLINAS,
    )

    st.selectbox(
        "Turma",
        mock_data.TURMAS_PARTICIPACAO,
    )

    st.date_input(
        "Data de entrega",
        format="DD/MM/YYYY",
    )

    if st.button(
        "Salvar",
        type="primary",
    ):
        if not nome.strip():

            st.error(
                "Informe o nome da atividade."
            )

            return

        st.session_state["pa_aviso"] = (
            f'Atividade "{nome.strip()}" inserida.'
        )

        st.rerun()


@st.dialog("Estudante")
def _dialogo_ver_estudante(aluno):
    """Exibe informações do estudante selecionado."""

    ficha = (
        mock_data
        .ESTUDANTES
        .set_index("Identificador")
        .loc[aluno["Estudante"]]
    )

    st.subheader(
        aluno["Estudante"]
    )

    st.write(
        f"{ficha['Série']} • "
        f"Turma {ficha['Turma']} • "
        f"{ficha['Turno']}"
    )

    st.write(
        "Frequência: "
        f"{percentual_br(ficha['Frequência'], 1)}"
    )

    st.write(
        "Média geral: "
        f"{decimal_br(ficha['Média geral'])}"
    )

    st.write(
        "Nível de risco: "
        f"{ficha['Risco']}"
    )

    st.write(
        f"Entregas: {aluno['Entregas']} "
        f"de {mock_data.TOTAL_ATIVIDADES_POR_ALUNO}"
    )


@st.dialog("Registrar acompanhamento")
def _dialogo_registrar_acompanhamento(
    identificador,
):
    """Registra acompanhamento do estudante."""

    st.write(identificador)

    texto = st.text_area(
        "Descreva o acompanhamento"
    )

    if st.button(
        "Salvar",
        type="primary",
    ):
        if not texto.strip():

            st.error(
                "Descreva o acompanhamento antes de salvar."
            )

            return

        st.session_state.setdefault(
            "pa_acompanhamentos",
            {},
        )[identificador] = texto.strip()

        st.session_state["pa_aviso"] = (
            f"Acompanhamento registrado para "
            f"{identificador}."
        )

        st.rerun()


def _formatar_para_tabela(dados):
    """Formata dados para a tabela."""

    tabela = dados.copy()

    tabela["Entregas"] = (
        tabela["Entregas"]
        .map(
            lambda quantidade:
            f"Entregou {quantidade}"
        )
    )

    tabela["Porcentagem de entregas"] = (
        tabela["Porcentagem de entregas"]
        .map(percentual_br)
    )

    return tabela


def _indicadores():
    """Renderiza os indicadores principais."""

    entregaram = mock_data.ENTREGARAM
    total = mock_data.TOTAL_ALUNOS_ATIVIDADE

    taxa_entrega = (
        entregaram
        / total
        * 100
    )

    (
        col1,
        col2,
        col3,
        col4,
    ) = st.columns(4)

    with col1:
        card_kpi(
            numero_br(entregaram),
            "Entregaram",
            f"de {numero_br(total)} alunos",
        )

    with col2:
        card_kpi(
            numero_br(
                total - entregaram
            ),
            "Não entregaram",
            "requer atenção",
        )

    with col3:
        card_kpi(
            percentual_br(
                taxa_entrega
            ),
            "Taxa de entrega",
            mock_data
            .VARIACAO_TAXA_ENTREGA,
        )

    with col4:
        card_kpi(
            mock_data.MEDIA_ATIVIDADE,
            "Média da atividade",
            "nesta atividade",
        )


def _graficos():
    """Renderiza os dois gráficos da tela."""

    col_turma, col_evolucao = (
        st.columns(
            2,
            gap="medium",
        )
    )

    with col_turma:

        with card(
            "Entrega por turma"
        ):
            figura = (
                grafico_barras_horizontais(
                    mock_data.ENTREGA_POR_TURMA,
                    "Entrega (%)",
                    "Turma",
                    cor="Situação",
                )
            )

            figura.update_xaxes(
                range=[0, 100],
            )

            figura.update_traces(
                texttemplate="%{x:.0f}%",
                textposition="outside",
            )

            figura.update_layout(
                height=290,
                margin=dict(
                    l=10,
                    r=25,
                    t=15,
                    b=20,
                ),
            )

            st.plotly_chart(
                figura,
                width="stretch",
                config={
                    "displayModeBar": False
                },
            )

    with col_evolucao:

        with card(
            "Evolução da participação"
        ):
            figura = grafico_linha(
                mock_data
                .EVOLUCAO_PARTICIPACAO,
                "Atividade",
                "Participação (%)",
            )

            figura.update_yaxes(
                range=[0, 100],
            )

            figura.update_traces(
                mode="lines+markers+text",
                texttemplate="%{y}%",
                textposition="top center",
            )

            figura.update_layout(
                height=290,
                margin=dict(
                    l=10,
                    r=15,
                    t=15,
                    b=20,
                ),
            )

            st.plotly_chart(
                figura,
                width="stretch",
                config={
                    "displayModeBar": False
                },
            )


def _acoes_do_aluno(aluno):
    """Ações do estudante selecionado."""

    escolhido = (
        aluno is not None
    )

    if not escolhido:

        st.caption(
            "Selecione um aluno na tabela "
            "para ver as ações."
        )

    col_ver, col_acompanhar = (
        st.columns(
            [1, 1.7],
            gap="small",
        )
    )

    if col_ver.button(
        "Ver estudante",
        disabled=not escolhido,
        use_container_width=True,
    ):
        _dialogo_ver_estudante(
            aluno
        )

    if col_acompanhar.button(
        "Registrar acompanhamento",
        disabled=not escolhido,
        use_container_width=True,
    ):
        _dialogo_registrar_acompanhamento(
            aluno["Estudante"]
        )

    if escolhido:

        acompanhamento = (
            st.session_state
            .get(
                "pa_acompanhamentos",
                {},
            )
            .get(
                aluno["Estudante"]
            )
        )

        if acompanhamento:

            st.caption(
                "Acompanhamento registrado: "
                f"{acompanhamento}"
            )


def render():
    """Renderiza a página Participação."""

    # Título
    col_titulo, col_inserir = st.columns(
        [5, 1.3],
        vertical_alignment="center",
    )

    with col_titulo:

        titulo_pagina(
            "Participação",
            "Acompanhe a entrega e o "
            "envolvimento dos estudantes.",
        )

    with col_inserir:

        if st.button(
            "Inserir atividade",
            key="btn_inserir_atividade",
            use_container_width=True,
        ):
            _dialogo_inserir_atividade()

    # Aviso
    aviso = st.session_state.pop(
        "pa_aviso",
        None,
    )

    if aviso:
        st.success(aviso)

    # Filtros
    with st.container(
        key="participacao_filtros"
    ):

        (
            col_atividade,
            col_disciplina,
            col_turma,
            col_periodo,
        ) = st.columns(
            [1.4, 1.4, 1, 1.1],
            gap="small",
        )

        with col_atividade:

            filtro_selecao(
                "Atividade",
                mock_data.ATIVIDADES,
                "pa_atividade",
                todos="Todas",
            )

        with col_disciplina:

            filtro_selecao(
                "Disciplina",
                mock_data.DISCIPLINAS,
                "pa_disciplina",
                todos="Todas",
            )

        with col_turma:

            filtro_selecao(
                "Turma",
                mock_data
                .TURMAS_PARTICIPACAO,
                "pa_turma",
                todos="Todas",
            )

        with col_periodo:

            filtro_selecao(
                "Período",
                mock_data.PERIODOS,
                "pa_periodo",
                todos=None,
            )

    # Indicadores
    with st.container(
        key="participacao_indicadores"
    ):
        _indicadores()

    # Gráficos
    with st.container(
        key="participacao_graficos"
    ):
        _graficos()

    # Detalhes
    alunos = mock_data.DETALHE_ALUNOS

    with st.container(
        key="participacao_detalhes"
    ):

        st.markdown(
            "### Detalhes da atividade por aluno"
        )

        posicao = tabela_paginada(
            _formatar_para_tabela(
                alunos
            ),
            tamanho_pagina=5,
            chave="pa_pagina",
            selecionavel=True,
        )

        _acoes_do_aluno(
            alunos.iloc[posicao]
            if posicao is not None
            else None
        )