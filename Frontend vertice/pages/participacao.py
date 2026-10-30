
"""Tela: Participação."""

import streamlit as st

from components.cards import card, card_kpi
from components.graficos import grafico_barras_horizontais
from components.layout import titulo_pagina
from components.tabelas import tabela_paginada
from data import mock_data
from data.atribuicoes import listar_atribuicoes
from utils.formatacao import (
    decimal_br,
    numero_br,
    percentual_br,
)


def aplicar_responsividade():
    """Organiza a Participação em telas menores."""

    st.html(
        """
        <style>
            .st-key-participacao_cabecalho,
            .st-key-participacao_filtros,
            .st-key-participacao_indicadores,
            .st-key-participacao_graficos,
            .st-key-participacao_detalhes,
            .st-key-participacao_acoes {
                width: 100%;
                max-width: 100%;
                min-width: 0;
                box-sizing: border-box;
            }

            .st-key-participacao_cabecalho
            [data-testid="column"],
            .st-key-participacao_filtros
            [data-testid="column"],
            .st-key-participacao_indicadores
            [data-testid="column"],
            .st-key-participacao_graficos
            [data-testid="column"],
            .st-key-participacao_acoes
            [data-testid="column"] {
                min-width: 0 !important;
            }

            .st-key-participacao_detalhes
            [data-testid="stDataFrame"] {
                width: 100% !important;
                max-width: 100% !important;
                min-width: 0 !important;
            }

            /* Tablet: filtros e indicadores em duas colunas. */

            @media (min-width: 601px) and (max-width: 1100px) {

                .st-key-participacao_filtros
                [data-testid="stHorizontalBlock"],
                .st-key-participacao_indicadores
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        repeat(2, minmax(0, 1fr)) !important;
                    gap: 12px !important;
                    width: 100% !important;
                }

                .st-key-participacao_graficos
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 14px !important;
                    width: 100% !important;
                }

                .st-key-participacao_filtros
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"],
                .st-key-participacao_indicadores
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"],
                .st-key-participacao_graficos
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                    flex: none !important;
                }
            }

            /* Celular: conteúdo empilhado. */

            @media (max-width: 600px) {

                .st-key-participacao_cabecalho
                [data-testid="stHorizontalBlock"],
                .st-key-participacao_filtros
                [data-testid="stHorizontalBlock"],
                .st-key-participacao_indicadores
                [data-testid="stHorizontalBlock"],
                .st-key-participacao_graficos
                [data-testid="stHorizontalBlock"],
                .st-key-participacao_acoes
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 12px !important;
                    width: 100% !important;
                }

                .st-key-participacao_cabecalho
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"],
                .st-key-participacao_filtros
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"],
                .st-key-participacao_indicadores
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"],
                .st-key-participacao_graficos
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"],
                .st-key-participacao_acoes
                [data-testid="stHorizontalBlock"]
                > [data-testid="column"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                    flex: none !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                /* Botão Inserir atividade com largura completa. */

                .st-key-participacao_cabecalho
                [data-testid="stButton"],
                .st-key-participacao_cabecalho
                [data-testid="stButton"] button {
                    width: 100% !important;
                }

                /* Evita que gráficos ultrapassem o celular. */

                .st-key-participacao_graficos
                [data-testid="stPlotlyChart"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                }

                /* Botões de acompanhamento separados. */

                .st-key-participacao_acoes
                [data-testid="stButton"],
                .st-key-participacao_acoes
                [data-testid="stButton"] button {
                    width: 100% !important;
                }

                .st-key-participacao_detalhes {
                    overflow-x: auto;
                }
            }
        </style>
        """
    )


def obter_atribuicoes():
    """Consulta as atribuições do perfil conectado."""

    atribuicoes = listar_atribuicoes()

    if st.session_state.get("perfil") == "administrador":
        return atribuicoes

    professor = st.session_state.get("professor_atual")

    return [
        item
        for item in atribuicoes
        if item["Professor"] == professor
    ]


def obter_dados_permitidos():
    """Reúne entregas e dados dos estudantes autorizados."""

    estudantes = mock_data.ESTUDANTES.copy()
    entregas = mock_data.DETALHE_ALUNOS.copy()

    estudantes["Turma completa"] = (
        estudantes["Série"].str.replace(
            " ano",
            "",
            regex=False,
        )
        + " "
        + estudantes["Turma"]
    )

    dados = entregas.merge(
        estudantes[
            [
                "Identificador",
                "Série",
                "Turma completa",
                "Frequência",
                "Média geral",
                "Risco",
            ]
        ],
        left_on="Estudante",
        right_on="Identificador",
        how="inner",
    )

    if st.session_state.get("perfil") == "administrador":
        return dados

    turmas = {
        item["Turma"]
        for item in obter_atribuicoes()
    }

    return dados[
        dados["Turma completa"].isin(turmas)
    ].copy()


def obter_opcoes():
    """Retorna disciplinas e turmas disponíveis."""

    if st.session_state.get("perfil") == "administrador":
        return (
            list(mock_data.DISCIPLINAS),
            list(mock_data.TURMAS_PARTICIPACAO),
        )

    atribuicoes = obter_atribuicoes()

    disciplinas = sorted({
        item["Disciplina"]
        for item in atribuicoes
    })

    turmas = sorted({
        item["Turma"]
        for item in atribuicoes
    })

    return disciplinas, turmas


def selecionar_opcao(
    rotulo,
    opcoes,
    chave,
    todas="Todas",
):
    """Mostra as opções e valida a seleção anterior."""

    lista = ([todas] if todas else []) + list(opcoes)

    if not lista:
        return None

    if st.session_state.get(chave) not in lista:
        st.session_state[chave] = lista[0]

    escolha = st.selectbox(
        rotulo,
        lista,
        key=chave,
    )

    if todas and escolha == todas:
        return None

    return escolha


@st.dialog("Inserir atividade")
def _dialogo_inserir_atividade():
    """Simula o cadastro de uma atividade."""

    disciplinas, turmas = obter_opcoes()

    if not disciplinas or not turmas:
        st.warning(
            "Não existem disciplinas ou turmas atribuídas."
        )
        return

    nome = st.text_input(
        "Nome da atividade",
        key="pa_nova_atividade",
    )

    disciplina = st.selectbox(
        "Disciplina",
        disciplinas,
        key="pa_nova_disciplina",
    )

    if st.session_state.get("perfil") == "professor":
        turmas = sorted({
            item["Turma"]
            for item in obter_atribuicoes()
            if item["Disciplina"] == disciplina
        })

    if not turmas:
        st.warning(
            "Não existem turmas para esta disciplina."
        )
        return

    turma = st.selectbox(
        "Turma",
        turmas,
        key="pa_nova_turma",
    )

    data_entrega = st.date_input(
        "Data de entrega",
        format="DD/MM/YYYY",
        key="pa_nova_data",
    )

    if st.button(
        "Salvar",
        type="primary",
        key="pa_salvar_atividade",
    ):
        if not nome.strip():
            st.error("Informe o nome da atividade.")
            return

        atividades = st.session_state.setdefault(
            "pa_atividades_criadas",
            [],
        )

        atividades.append({
            "Nome": nome.strip(),
            "Disciplina": disciplina,
            "Turma": turma,
            "Data": data_entrega,
        })

        st.session_state["pa_aviso"] = (
            f'Atividade "{nome.strip()}" adicionada '
            "nesta sessão."
        )

        st.rerun()


@st.dialog("Estudante")
def _dialogo_ver_estudante(aluno):
    """Mostra as informações do estudante selecionado."""

    st.subheader(aluno["Estudante"])

    st.write(
        f"{aluno['Série']} • "
        f"Turma {aluno['Turma completa']} • "
        f"{aluno['Turno']}"
    )

    st.write(
        "Frequência: "
        f"{percentual_br(aluno['Frequência'], 1)}"
    )

    st.write(
        "Média geral: "
        f"{decimal_br(aluno['Média geral'])}"
    )

    st.write(
        f"Nível de risco: {aluno['Risco']}"
    )

    st.write(
        f"Entregas: {aluno['Entregas']} de "
        f"{mock_data.TOTAL_ATIVIDADES_POR_ALUNO}"
    )


@st.dialog("Registrar acompanhamento")
def _dialogo_registrar_acompanhamento(identificador):
    """Registra uma anotação temporária na sessão."""

    st.write(f"Estudante: {identificador}")

    texto = st.text_area(
        "Descreva o acompanhamento",
        key="pa_texto_acompanhamento",
    )

    if st.button(
        "Salvar",
        type="primary",
        key="pa_salvar_acompanhamento",
    ):
        if not texto.strip():
            st.error(
                "Descreva o acompanhamento antes de salvar."
            )
            return

        acompanhamentos = st.session_state.setdefault(
            "pa_acompanhamentos",
            {},
        )

        acompanhamentos[identificador] = texto.strip()

        st.session_state["pa_aviso"] = (
            "Acompanhamento registrado para "
            f"{identificador} nesta sessão."
        )

        st.rerun()


def _formatar_para_tabela(dados):
    """Prepara os valores da tabela de estudantes."""

    tabela = dados[
        [
            "Estudante",
            "Turma completa",
            "Turno",
            "Entregas",
            "Porcentagem de entregas",
            "Status",
        ]
    ].copy()

    tabela["Entregas"] = tabela["Entregas"].map(
        lambda quantidade: f"Entregou {quantidade}"
    )

    tabela["Porcentagem de entregas"] = (
        tabela["Porcentagem de entregas"]
        .map(percentual_br)
    )

    return tabela.rename(
        columns={
            "Turma completa": "Turma",
        }
    )


def _indicadores(dados):
    """Calcula os indicadores dos estudantes filtrados."""

    total = len(dados)

    com_entregas = int(
        (dados["Entregas"] > 0).sum()
    )

    sem_entregas = total - com_entregas

    total_possivel = (
        total * mock_data.TOTAL_ATIVIDADES_POR_ALUNO
    )

    entregas_realizadas = int(
        dados["Entregas"].sum()
    )

    taxa_entrega = (
        entregas_realizadas / total_possivel * 100
        if total_possivel
        else 0
    )

    media_geral = (
        dados["Média geral"].mean()
        if total
        else 0
    )

    indicadores = [
        (
            numero_br(com_entregas),
            "Com entregas",
            f"de {numero_br(total)} estudantes",
        ),
        (
            numero_br(sem_entregas),
            "Sem entregas",
            "Nenhuma entrega registrada",
        ),
        (
            percentual_br(taxa_entrega),
            "Taxa de entregas",
            "Proporção das entregas previstas",
        ),
        (
            decimal_br(media_geral) if total else "—",
            "Média geral",
            "Média dos estudantes selecionados",
        ),
    ]

    colunas = st.columns(
        4,
        gap="small",
    )

    for coluna, indicador in zip(
        colunas,
        indicadores,
    ):
        with coluna:
            card_kpi(*indicador)


def _graficos(dados):
    """Exibe os gráficos de participação."""

    col_turma, col_evolucao = st.columns(
        2,
        gap="medium",
    )

    with col_turma:
        with card("Entrega por turma"):

            if dados.empty:
                st.info(
                    "Nenhum dado disponível para o gráfico."
                )
            else:
                agrupados = (
                    dados.groupby("Turma completa")
                    .agg(
                        entregas=("Entregas", "sum"),
                        estudantes=("Estudante", "count"),
                    )
                    .reset_index()
                )

                agrupados["Entrega (%)"] = (
                    agrupados["entregas"]
                    / (
                        agrupados["estudantes"]
                        * mock_data.TOTAL_ATIVIDADES_POR_ALUNO
                    )
                    * 100
                )

                agrupados["Situação"] = (
                    agrupados["Entrega (%)"]
                    .map(mock_data._classificar_entrega)
                )

                agrupados = agrupados.rename(
                    columns={
                        "Turma completa": "Turma",
                    }
                )

                figura = grafico_barras_horizontais(
                    agrupados,
                    "Entrega (%)",
                    "Turma",
                    cor="Situação",
                )

                figura.update_xaxes(
                    range=[0, 100]
                )

                figura.update_traces(
                    texttemplate="%{x:.0f}%",
                    textposition="outside",
                )

                figura.update_layout(
                    height=290,
                    autosize=True,
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
                    key="pa_grafico_turmas",
                )

    with col_evolucao:
        with card("Evolução da participação"):
            st.info(
                "O histórico de participação por turma "
                "ainda não está disponível nos dados "
                "indisponíveis. Este gráfico será preenchido "
                "quando houver registros por atividade "
                "e período."
            )


def _acoes_do_aluno(aluno):
    """Oferece ações para o estudante selecionado."""

    if aluno is None:
        st.caption(
            "Selecione um aluno na tabela para ver as ações."
        )
        return

    with st.container(key="participacao_acoes"):

        col_ver, col_acompanhar = st.columns(
            [1, 1.7],
            gap="small",
        )

        with col_ver:
            if st.button(
                "Ver estudante",
                use_container_width=True,
            ):
                _dialogo_ver_estudante(aluno)

        with col_acompanhar:
            if st.button(
                "Registrar acompanhamento",
                use_container_width=True,
            ):
                _dialogo_registrar_acompanhamento(
                    aluno["Estudante"]
                )

    acompanhamento = (
        st.session_state.get("pa_acompanhamentos", {})
        .get(aluno["Estudante"])
    )

    if acompanhamento:
        st.caption(
            "Acompanhamento registrado: "
            f"{acompanhamento}"
        )


def render():
    """Renderiza a participação conforme o perfil conectado."""

    aplicar_responsividade()

    with st.container(key="participacao_cabecalho"):

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

    aviso = st.session_state.pop(
        "pa_aviso",
        None,
    )

    if aviso:
        st.success(aviso)

    disciplinas, turmas_permitidas = obter_opcoes()

    if not turmas_permitidas:
        st.info(
            "Nenhuma turma foi atribuída ao seu perfil."
        )
        return

    dados_permitidos = obter_dados_permitidos()

    with st.container(key="participacao_filtros"):

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
            st.selectbox(
                "Atividade",
                mock_data.ATIVIDADES,
                key="pa_atividade",
                disabled=True,
            )

        with col_disciplina:
            disciplina = selecionar_opcao(
                "Disciplina",
                disciplinas,
                "pa_disciplina",
            )

        if (
            st.session_state.get("perfil") == "professor"
            and disciplina
        ):
            turmas = sorted({
                item["Turma"]
                for item in obter_atribuicoes()
                if item["Disciplina"] == disciplina
            })
        else:
            turmas = turmas_permitidas

        with col_turma:
            turma = selecionar_opcao(
                "Turma",
                turmas,
                "pa_turma",
            )

        with col_periodo:
            st.selectbox(
                "Período",
                mock_data.PERIODOS,
                key="pa_periodo",
                disabled=True,
            )

    st.caption(
        "Atividade e período aguardam dados específicos "
        "para permitir a filtragem. A disciplina organiza "
        "as turmas autorizadas; os registros de entregas "
        "ainda não estão vinculados a disciplinas."
    )

    dados = dados_permitidos.copy()

    if turma:
        dados = dados[
            dados["Turma completa"] == turma
        ]

    with st.container(key="participacao_indicadores"):
        _indicadores(dados)

    with st.container(key="participacao_graficos"):
        _graficos(dados)

    with st.container(key="participacao_detalhes"):

        st.markdown(
            "### Detalhes da atividade por aluno"
        )

        if dados.empty:
            st.info(
                "Não existem registros de participação "
                "para a turma selecionada."
            )
            return

        dados = dados.reset_index(drop=True)

        posicao = tabela_paginada(
            _formatar_para_tabela(dados),
            tamanho_pagina=5,
            chave="pa_pagina",
            selecionavel=True,
            reiniciar_quando=(
                st.session_state.get("perfil"),
                st.session_state.get("professor_atual"),
                disciplina,
                turma,
            ),
        )

        aluno = (
            dados.iloc[posicao]
            if posicao is not None
            else None
        )

        _acoes_do_aluno(aluno)
