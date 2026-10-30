
"""Tela: Visão geral."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.cards import card, card_kpi
from components.graficos import (
    grafico_barras_horizontais,
    grafico_dispersao,
    grafico_rosca,
)
from components.layout import titulo_pagina
from data import mock_data
from data.atribuicoes import listar_atribuicoes


CORES_KPI = ["azul", "verde", "laranja", "vermelho"]


def aplicar_responsividade():
    """Adapta somente os conteúdos da Visão Geral."""

    st.html(
        """
        <style>
            /* Evita que gráficos e cards ultrapassem a tela. */

            .st-key-vg_kpis_responsivos,
            .st-key-vg_graficos_linha_1,
            .st-key-vg_graficos_linha_2,
            .st-key-visao_geral_filtros {
                width: 100%;
                min-width: 0;
                max-width: 100%;
            }

            .st-key-vg_kpis_responsivos
            [data-testid="stColumn"],
            .st-key-vg_graficos_linha_1
            [data-testid="stColumn"],
            .st-key-vg_graficos_linha_2
            [data-testid="stColumn"],
            .st-key-visao_geral_filtros
            [data-testid="stColumn"],
            .st-key-vg_kpis_responsivos
            [data-testid="column"],
            .st-key-vg_graficos_linha_1
            [data-testid="column"],
            .st-key-vg_graficos_linha_2
            [data-testid="column"],
            .st-key-visao_geral_filtros
            [data-testid="column"] {
                min-width: 0 !important;
            }

            /* Tablet e janelas intermediárias. */

            @media (max-width: 1100px) {

                /* Indicadores: duas colunas. */

                .st-key-vg_kpis_responsivos
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        repeat(2, minmax(0, 1fr)) !important;
                    gap: 12px !important;
                    width: 100% !important;
                }

                /* Gráficos: uma coluna. */

                .st-key-vg_graficos_linha_1
                [data-testid="stHorizontalBlock"],
                .st-key-vg_graficos_linha_2
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 14px !important;
                    width: 100% !important;
                }

                /* Os elementos ocupam sua célula inteira. */

                .st-key-vg_kpis_responsivos
                [data-testid="stColumn"],
                .st-key-vg_graficos_linha_1
                [data-testid="stColumn"],
                .st-key-vg_graficos_linha_2
                [data-testid="stColumn"],
                .st-key-vg_kpis_responsivos
                [data-testid="column"],
                .st-key-vg_graficos_linha_1
                [data-testid="column"],
                .st-key-vg_graficos_linha_2
                [data-testid="column"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                }
            }

            /* Celular. */

            @media (max-width: 600px) {

                /* Todos os indicadores em coluna. */

                .st-key-vg_kpis_responsivos
                [data-testid="stHorizontalBlock"] {
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                }

                /* Série, turma e informação em coluna. */

                .st-key-visao_geral_filtros
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 8px !important;
                    width: 100% !important;
                }

                .st-key-visao_geral_filtros
                [data-testid="stColumn"],
                .st-key-visao_geral_filtros
                [data-testid="column"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                }

                /* Ajuste dos gráficos para celular. */

                .st-key-vg_graficos_linha_1
                [data-testid="stPlotlyChart"],
                .st-key-vg_graficos_linha_2
                [data-testid="stPlotlyChart"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                }
            }
        </style>
        """
    )


def obter_dados_importados():
    """Consulta os estudantes validados na Entrada de Dados."""

    importacoes = st.session_state.get(
        "entrada_importacoes", {}
    )

    dados = importacoes.get("Estudantes")

    if not isinstance(dados, pd.DataFrame):
        return pd.DataFrame(
            columns=mock_data.ESTUDANTES.columns
        )

    return dados.copy()


def turmas_autorizadas():
    """Obtém as turmas disponíveis para o perfil conectado."""

    if st.session_state.get("perfil") == "administrador":
        return {
            f"{serie.replace(' ano', '')} {turma}"
            for serie in mock_data.SERIES
            for turma in mock_data.TURMAS
        }

    professor = st.session_state.get("professor_atual")

    return {
        item["Turma"]
        for item in listar_atribuicoes()
        if item["Professor"] == professor
    }


def filtrar_por_professor(dados):
    """Restringe os estudantes às turmas autorizadas."""

    if dados.empty:
        return dados.copy()

    if st.session_state.get("perfil") == "administrador":
        return dados.copy()

    permitidas = turmas_autorizadas()

    turma_completa = (
        dados["Série"].astype(str)
        .str.replace(" ano", "", regex=False)
        + " "
        + dados["Turma"].astype(str)
    )

    return dados.loc[
        turma_completa.isin(permitidas)
    ].copy()


def formatar_numero(valor):
    return f"{int(valor):,}".replace(",", ".")


def formatar_percentual(valor):
    return f"{valor:.1f}".replace(".", ",") + "%"


def montar_indicadores(dados):
    """Calcula os indicadores com os dados importados."""

    if dados.empty:
        return [
            ("—", "Total de estudantes", "Aguardando dados"),
            ("—", "Frequência média", "Aguardando dados"),
            ("—", "Estudantes em atenção", "Aguardando dados"),
            ("—", "Alto risco identificado", "Aguardando dados"),
        ]

    total = len(dados)
    frequencia = dados["Frequência"].mean()

    em_atencao = dados["Risco"].isin(
        ["Atenção", "Alto"]
    ).sum()

    alto_risco = (
        dados["Risco"] == "Alto"
    ).sum()

    return [
        (
            formatar_numero(total),
            "Total de estudantes",
            "Estudantes no filtro atual",
        ),
        (
            formatar_percentual(frequencia),
            "Frequência média",
            "Meta de referência: 85%",
        ),
        (
            formatar_numero(em_atencao),
            "Estudantes em atenção",
            "Inclui atenção e alto risco",
        ),
        (
            formatar_numero(alto_risco),
            "Alto risco identificado",
            "Estudantes classificados em alto risco",
        ),
    ]


def montar_dados_graficos(dados):
    """Prepara os dados utilizados pelos quatro gráficos."""

    frequencia = (
        dados.groupby("Série", as_index=False)["Frequência"]
        .mean()
        .rename(
            columns={
                "Frequência": "Frequência média (%)"
            }
        )
    )

    distribuicao = (
        dados["Risco"]
        .value_counts()
        .reindex(
            ["Baixo", "Atenção", "Alto"],
            fill_value=0,
        )
        .rename_axis("Nível de risco")
        .reset_index(name="Estudantes")
    )

    alto_risco = (
        dados[dados["Risco"] == "Alto"]
        .groupby("Série")
        .size()
        .reindex(
            sorted(dados["Série"].unique()),
            fill_value=0,
        )
        .rename("Estudantes em alto risco")
        .reset_index()
    )

    notas = dados[
        ["Frequência", "Média geral"]
    ].rename(
        columns={
            "Frequência": "Frequência (%)"
        }
    )

    return (
        frequencia,
        distribuicao,
        alto_risco,
        notas,
    )


def montar_tabela_atencao(dados):
    """Monta a tabela de acompanhamento dos estudantes."""

    colunas = [
        "ID anonimizado",
        "Série/Turma",
        "Frequência",
        "Média geral",
        "Nível de risco",
    ]

    if dados.empty:
        return pd.DataFrame(columns=colunas)

    atencao = dados[
        dados["Risco"].isin(["Atenção", "Alto"])
    ].copy()

    if atencao.empty:
        return pd.DataFrame(columns=colunas)

    atencao = atencao.sort_values(
        ["Frequência", "Média geral"],
        ascending=True,
    )

    atencao["Série/Turma"] = (
        atencao["Série"]
        + " - "
        + atencao["Turma"]
    )

    atencao["Frequência"] = (
        atencao["Frequência"].map(
            formatar_percentual
        )
    )

    atencao["Média geral"] = (
        atencao["Média geral"].map(
            lambda valor: (
                f"{valor:.1f}".replace(".", ",")
            )
        )
    )

    return (
        atencao[
            [
                "Identificador",
                "Série/Turma",
                "Frequência",
                "Média geral",
                "Risco",
            ]
        ]
        .rename(
            columns={
                "Identificador": "ID anonimizado",
                "Risco": "Nível de risco",
            }
        )
        .head(10)
    )


def grafico_vazio():
    """Mantém o gráfico sem apresentar dados fictícios."""

    figura = go.Figure()

    figura.update_layout(
        height=290,
        margin=dict(
            l=15,
            r=15,
            t=15,
            b=15,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
        annotations=[
            dict(
                text="Aguardando dados importados",
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(
                    size=13,
                    color="#8792A2",
                ),
            )
        ],
    )

    return figura


def exibir_grafico(figura, chave):
    """Exibe os gráficos com os controles do Plotly."""

    figura.update_layout(
        height=290,
        autosize=True,
        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20,
        ),
    )

    st.plotly_chart(
        figura,
        width="stretch",
        key=chave,
        config={
            "displayModeBar": True,
            "displaylogo": False,
            "responsive": True,
        },
    )


def render():
    """Renderiza a Visão Geral respeitando as permissões."""

    aplicar_responsividade()
    titulo_pagina("Visão geral")

    dados_importados = obter_dados_importados()
    dados_permitidos = filtrar_por_professor(
        dados_importados
    )

    permitidas = turmas_autorizadas()

    series = [
        serie
        for serie in mock_data.SERIES
        if any(
            turma.startswith(
                serie.replace(" ano", "") + " "
            )
            for turma in permitidas
        )
    ]

    opcoes_series = ["Todas"] + series

    if st.session_state.get("vg_serie") not in opcoes_series:
        st.session_state["vg_serie"] = "Todas"

    with st.container(key="visao_geral_filtros"):

        col_serie, col_turma, col_info = st.columns(
            [1, 1, 3],
            vertical_alignment="bottom",
        )

        with col_serie:
            serie = st.selectbox(
                "Série",
                opcoes_series,
                key="vg_serie",
            )

        turmas = [
            turma
            for turma in mock_data.TURMAS
            if any(
                f"{s.replace(' ano', '')} {turma}"
                in permitidas
                for s in series
                if serie == "Todas" or s == serie
            )
        ]

        opcoes_turmas = ["Todas"] + turmas

        if (
            st.session_state.get("vg_turma")
            not in opcoes_turmas
        ):
            st.session_state["vg_turma"] = "Todas"

        with col_turma:
            turma = st.selectbox(
                "Turma",
                opcoes_turmas,
                key="vg_turma",
            )

        with col_info:
            if (
                st.session_state.get("perfil")
                == "professor"
            ):
                professor = (
                    st.session_state.get("professor_atual")
                    or "Professor"
                )

                st.caption(
                    f"Visualização de: {professor}"
                )
            else:
                st.caption(
                    "Visualização geral da escola"
                )

    dados = dados_permitidos.copy()

    if not dados.empty:
        if serie != "Todas":
            dados = dados[
                dados["Série"] == serie
            ]

        if turma != "Todas":
            dados = dados[
                dados["Turma"] == turma
            ]

    indicadores = montar_indicadores(dados)

    with st.container(key="vg_kpis_responsivos"):
        colunas_kpi = st.columns(
            4,
            gap="small",
        )

        for coluna, cor, indicador in zip(
            colunas_kpi,
            CORES_KPI,
            indicadores,
        ):
            with coluna:
                valor, rotulo, rodape = indicador

                card_kpi(
                    valor,
                    rotulo,
                    rodape,
                    cor,
                )

    if dados.empty:
        frequencia = None
        distribuicao = None
        alto_risco = None
        notas = None
    else:
        (
            frequencia,
            distribuicao,
            alto_risco,
            notas,
        ) = montar_dados_graficos(dados)

    with st.container(key="vg_graficos_linha_1"):

        col_frequencia, col_risco = st.columns(
            2,
            gap="small",
        )

        with col_frequencia:
            with card("Frequência média por série"):
                figura = (
                    grafico_barras_horizontais(
                        frequencia,
                        "Frequência média (%)",
                        "Série",
                    )
                    if frequencia is not None
                    else grafico_vazio()
                )

                exibir_grafico(
                    figura,
                    "vg_grafico_frequencia",
                )

        with col_risco:
            with card("Distribuição de risco"):
                figura = (
                    grafico_rosca(
                        distribuicao,
                        "Nível de risco",
                        "Estudantes",
                    )
                    if distribuicao is not None
                    else grafico_vazio()
                )

                exibir_grafico(
                    figura,
                    "vg_grafico_risco",
                )

    with st.container(key="vg_graficos_linha_2"):

        col_serie, col_notas = st.columns(
            2,
            gap="small",
        )

        with col_serie:
            with card("Risco por série"):
                figura = (
                    grafico_barras_horizontais(
                        alto_risco,
                        "Estudantes em alto risco",
                        "Série",
                    )
                    if alto_risco is not None
                    else grafico_vazio()
                )

                exibir_grafico(
                    figura,
                    "vg_grafico_alto_risco",
                )

        with col_notas:
            with card("Notas x frequência"):

                if (
                    notas is not None
                    and len(notas) >= 2
                    and notas["Frequência (%)"].nunique() >= 2
                ):
                    figura = grafico_dispersao(
                        notas,
                        "Frequência (%)",
                        "Média geral",
                    )
                else:
                    figura = grafico_vazio()

                exibir_grafico(
                    figura,
                    "vg_grafico_notas",
                )

    with card("Estudantes que exigem atenção"):

        tabela = montar_tabela_atencao(dados)

        if tabela.empty:
            st.caption(
                "Nenhum estudante para exibir "
                "com os dados e filtros atuais."
            )
        else:
            st.dataframe(
                tabela,
                hide_index=True,
                width="stretch",
            )

    if dados_importados.empty:
        st.caption(
            "Os indicadores serão preenchidos "
            "após a importação e validação "
            "dos dados dos estudantes."
        )

    elif dados.empty:
        st.caption(
            "Não há registros importados para "
            "os filtros ou permissões selecionados."
        )
