"""Tela: Mapa de Acertos."""

import streamlit as st

from components.filtros import filtro_selecao
from components.graficos import grafico_barras_horizontais
from components.layout import titulo_pagina
from components.tabelas import tabela_selecionavel
from data import mock_data
from utils.formatacao import percentual_br


COLUNAS_TABELA = [
    "Questão",
    "Dificuldade",
    "Acertos",
    "Erros",
    "Em branco",
    "Ação sugerida",
]


@st.dialog("Inserir avaliação")
def _dialogo_inserir_avaliacao():
    """Modal para inserir nova avaliação."""

    nome = st.text_input(
        "Nome da avaliação"
    )

    st.selectbox(
        "Disciplina",
        mock_data.DISCIPLINAS,
    )

    st.selectbox(
        "Turma",
        mock_data.TURMAS_AVALIACAO,
    )

    st.selectbox(
        "Tipo",
        mock_data.TIPOS_QUESTAO,
    )

    st.number_input(
        "Número de questões",
        min_value=1,
        max_value=100,
        value=10,
        step=1,
    )

    if st.button(
        "Salvar",
        type="primary",
    ):
        if not nome.strip():
            st.error(
                "Informe o nome da avaliação."
            )
            return

        st.session_state["ma_aviso"] = (
            f'Avaliação "{nome.strip()}" inserida.'
        )

        st.rerun()


@st.dialog("Registrar ação pedagógica")
def _dialogo_registrar_acao(nome_questao):
    """Modal para registrar ação pedagógica."""

    st.write(nome_questao)

    texto = st.text_area(
        "Descreva a ação pedagógica"
    )

    if st.button(
        "Salvar",
        type="primary",
    ):
        if not texto.strip():

            st.error(
                "Descreva a ação antes de salvar."
            )

            return

        st.session_state.setdefault(
            "ma_acoes",
            {},
        )[nome_questao] = texto.strip()

        st.session_state["ma_aviso"] = (
            f"Ação registrada para {nome_questao}."
        )

        st.rerun()


def _painel_questao(questao, detalhe):
    """Painel lateral exibido somente após selecionar uma questão."""

    total = mock_data.TOTAL_RESPONDENTES

    respostas = detalhe["respostas"]

    erradas = {
        letra: quantidade
        for letra, quantidade in respostas.items()
        if letra != detalhe["correta"]
    }

    errada_mais_escolhida = (
        max(
            erradas,
            key=erradas.get,
        )
        if erradas
        else "-"
    )

    interpretacao = (
        mock_data
        .INTERPRETACAO_POR_DIFICULDADE[
            questao["Dificuldade"]
        ]
        .format(
            correta=detalhe["correta"],
            errada_mais_escolhida=(
                errada_mais_escolhida
            ),
        )
    )

    with st.container(
        key="mapa_detalhe"
    ):

        # Cabeçalho
        col_titulo, col_fechar = st.columns(
            [5, 1],
            vertical_alignment="center",
        )

        with col_titulo:
            st.markdown(
                f"### {questao['Questão']}"
            )

        with col_fechar:

            if st.button(
                "×",
                key="ma_fechar_detalhe",
                help="Fechar detalhes",
            ):
                st.session_state[
                    "ma_questao_selecionada"
                ] = None

                st.rerun()

        st.divider()

        # Resumo
        with st.container(
            key="mapa_resumo_questao"
        ):

            st.markdown(
                f"**{questao['Acertos']}** "
                "estudantes acertaram"
            )

            st.markdown(
                f"**{questao['Erros']}** "
                "estudantes erraram"
            )

            st.markdown(
                f"**{questao['Em branco']}** "
                "estudantes deixaram em branco"
            )

            st.markdown(
                f"**{percentual_br(questao['Acerto (%)'], 1)}** "
                "de acerto"
            )

        st.divider()

        # Distribuição
        st.markdown(
            "#### Distribuição de resposta"
        )

        for letra, quantidade in respostas.items():

            percentual = (
                quantidade
                / total
            )

            percentual_texto = percentual_br(
                percentual * 100,
                0,
            )

            correta = (
                letra
                == detalhe["correta"]
            )

            rotulo = (
                f"{letra}   "
                f"{quantidade}   "
                f"{percentual_texto}"
            )

            st.progress(
                percentual,
                text=rotulo,
            )

            if correta:
                st.caption(
                    f"Alternativa correta: {letra}"
                )

        st.divider()

        # Interpretação
        st.markdown(
            "#### Interpretação"
        )

        st.write(
            interpretacao
        )

        # Ação pedagógica
        acao_registrada = (
            st.session_state
            .get(
                "ma_acoes",
                {},
            )
            .get(
                questao["Questão"]
            )
        )

        if acao_registrada:

            st.caption(
                f"Ação registrada: "
                f"{acao_registrada}"
            )

        if st.button(
            "Registrar ação pedagógica",
            key="btn_registrar_acao",
            use_container_width=True,
        ):
            _dialogo_registrar_acao(
                questao["Questão"]
            )


def _conteudo_principal(questoes):
    """Gráfico e tabela da página."""

    # Gráfico
    with st.container(
        key="mapa_grafico"
    ):

        st.markdown(
            "### Desempenho por questão"
        )

        figura = grafico_barras_horizontais(
            questoes,
            "Acerto (%)",
            "Questão",
            cor="Dificuldade",
        )

        figura.update_xaxes(
            range=[0, 100],
            tickvals=[
                0,
                20,
                40,
                60,
                80,
                100,
            ],
            ticksuffix="%",
            title=None,
            showgrid=True,
            gridcolor="#E6E6E6",
        )

        figura.update_yaxes(
            title=None,
        )

        figura.update_traces(
            texttemplate="%{x:.0f}%",
            textposition="outside",
        )

        figura.update_layout(
            height=355,
            margin=dict(
                l=10,
                r=25,
                t=15,
                b=20,
            ),
            legend=dict(
                orientation="v",
                x=1.02,
                y=1,
            ),
        )

        st.plotly_chart(
            figura,
            width="stretch",
            config={
                "displayModeBar": False,
            },
        )

    # Tabela
    with st.container(
        key="mapa_tabela"
    ):

        linha_escolhida = (
            tabela_selecionavel(
                questoes[
                    COLUNAS_TABELA
                ],
                "ma_tabela",
            )
        )

    return linha_escolhida


def render():
    """Renderiza a tela Mapa de Acertos."""

    # Estado
    st.session_state.setdefault(
        "ma_questao_selecionada",
        None,
    )

    # Título
    col_titulo, col_inserir = st.columns(
        [5, 1.3],
        vertical_alignment="center",
    )

    with col_titulo:
        titulo_pagina(
            "Mapa de Acertos"
        )

    with col_inserir:

        if st.button(
            "Inserir avaliação",
            key="btn_inserir_avaliacao",
            use_container_width=True,
        ):
            _dialogo_inserir_avaliacao()

    # Aviso
    aviso = st.session_state.pop(
        "ma_aviso",
        None,
    )

    if aviso:
        st.success(aviso)

    # Filtros
    with st.container(
        key="mapa_filtros"
    ):

        (
            col_avaliacao,
            col_disciplina,
            col_turma,
            col_tipo,
        ) = st.columns(
            [1, 1.4, 1, 1.1],
            gap="small",
        )

        with col_avaliacao:
            filtro_selecao(
                "Avaliação",
                mock_data.AVALIACOES,
                "ma_avaliacao",
                todos=None,
            )

        with col_disciplina:
            filtro_selecao(
                "Disciplina",
                mock_data.DISCIPLINAS,
                "ma_disciplina",
                todos=None,
            )

        with col_turma:
            filtro_selecao(
                "Turma",
                mock_data.TURMAS_AVALIACAO,
                "ma_turma",
                todos=None,
            )

        with col_tipo:
            filtro_selecao(
                "Tipo",
                mock_data.TIPOS_QUESTAO,
                "ma_tipo",
                todos=None,
            )

    # Dados
    questoes = (
        mock_data
        .DESEMPENHO_QUESTOES
        .copy()
        .reset_index(drop=True)
    )

    questao_selecionada = (
        st.session_state[
            "ma_questao_selecionada"
        ]
    )

    # Sem uma questão selecionada, gráfico e tabela usam toda a largura.

    if questao_selecionada is None:

        linha_escolhida = (
            _conteudo_principal(
                questoes
            )
        )

        if linha_escolhida is not None:

            st.session_state[
                "ma_questao_selecionada"
            ] = linha_escolhida

            st.rerun()

        return

    # Ao selecionar uma questão, o detalhe aparece na coluna lateral.

    col_principal, col_detalhe = (
        st.columns(
            [2.35, 1],
            gap="large",
            vertical_alignment="top",
        )
    )

    with col_principal:

        linha_escolhida = (
            _conteudo_principal(
                questoes
            )
        )

        if (
            linha_escolhida
            is not None
            and linha_escolhida
            != questao_selecionada
        ):

            st.session_state[
                "ma_questao_selecionada"
            ] = linha_escolhida

            st.rerun()

    with col_detalhe:

        _painel_questao(
            questoes.iloc[
                questao_selecionada
            ],
            mock_data
            .RESPOSTAS_POR_QUESTAO[
                questao_selecionada
            ],
        )