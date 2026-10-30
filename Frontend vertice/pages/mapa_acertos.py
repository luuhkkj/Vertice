
"""Tela: Mapa de Acertos."""

import streamlit as st

from components.graficos import grafico_barras_horizontais
from components.layout import titulo_pagina
from components.tabelas import tabela_selecionavel
from data import mock_data
from data.atribuicoes import listar_atribuicoes
from pages.entrada_dados import _arquivo_modelo
from utils.formatacao import percentual_br


COLUNAS_TABELA = [
    "Questão",
    "Dificuldade",
    "Acertos",
    "Erros",
    "Em branco",
    "Ação sugerida",
]


def aplicar_responsividade():
    """Adapta os filtros, gráficos e detalhes a telas menores."""

    st.html(
        """
        <style>
            /* Mantém os elementos dentro da largura da página. */

            .st-key-mapa_botoes,
            .st-key-mapa_filtros,
            .st-key-mapa_grafico,
            .st-key-mapa_tabela,
            .st-key-mapa_colunas_detalhe,
            .st-key-mapa_detalhe {
                width: 100%;
                max-width: 100%;
                min-width: 0;
                box-sizing: border-box;
            }

            .st-key-mapa_botoes
            [data-testid="stColumn"],
            .st-key-mapa_filtros
            [data-testid="stColumn"],
            .st-key-mapa_colunas_detalhe
            [data-testid="stColumn"] {
                min-width: 0 !important;
            }

            /* Gráfico e tabela respeitam o espaço disponível. */

            .st-key-mapa_grafico
            [data-testid="stPlotlyChart"] {
                width: 100% !important;
                min-width: 0 !important;
                max-width: 100% !important;
            }

            .st-key-mapa_tabela {
                overflow-x: auto;
            }

            .st-key-mapa_tabela
            [data-testid="stDataFrame"] {
                width: 100% !important;
                min-width: 0 !important;
                max-width: 100% !important;
            }

            /* Tablet */

            @media (min-width: 601px) and (max-width: 1100px) {

                .st-key-mapa_botoes
                [data-testid="stHorizontalBlock"],
                .st-key-mapa_filtros
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        repeat(2, minmax(0, 1fr)) !important;
                    gap: 12px !important;
                    width: 100% !important;
                }

                /* O terceiro botão ocupa a linha seguinte. */

                .st-key-mapa_botoes
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"]:nth-child(3) {
                    grid-column: 1 / -1;
                }

                /* Gráficos e detalhes ficam empilhados. */

                .st-key-mapa_colunas_detalhe
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 14px !important;
                    width: 100% !important;
                }

                .st-key-mapa_botoes
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"],
                .st-key-mapa_filtros
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"],
                .st-key-mapa_colunas_detalhe
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                    flex: none !important;
                }
            }

            /* Celular */

            @media (max-width: 600px) {

                .st-key-mapa_botoes
                [data-testid="stHorizontalBlock"],
                .st-key-mapa_filtros
                [data-testid="stHorizontalBlock"],
                .st-key-mapa_colunas_detalhe
                [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns:
                        minmax(0, 1fr) !important;
                    gap: 10px !important;
                    width: 100% !important;
                }

                .st-key-mapa_botoes
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"],
                .st-key-mapa_filtros
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"],
                .st-key-mapa_colunas_detalhe
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                    flex: none !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                /* Downloads e cadastro com largura completa. */

                .st-key-mapa_botoes button {
                    width: 100% !important;
                }

                /* Os filtros não podem alargar o celular. */

                .st-key-mapa_filtros
                [data-testid="stSelectbox"] {
                    width: 100% !important;
                    min-width: 0 !important;
                }

                /* Área do gráfico. */

                .st-key-mapa_grafico
                [data-testid="stPlotlyChart"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                }

                /* Rolagem dentro da tabela. */

                .st-key-mapa_tabela {
                    max-width: 100% !important;
                    overflow-x: auto !important;
                }

                /* Painel de detalhes. */

                .st-key-mapa_detalhe {
                    width: 100% !important;
                    max-width: 100% !important;
                }

                .st-key-mapa_detalhe p {
                    overflow-wrap: anywhere;
                }
            }
        </style>
        """
    )


def _atribuicoes_permitidas():
    """Retorna as atribuições permitidas ao usuário."""

    atribuicoes = listar_atribuicoes()

    if st.session_state.get("perfil") == "administrador":
        return atribuicoes

    professor = st.session_state.get("professor_atual")

    return [
        item
        for item in atribuicoes
        if item["Professor"] == professor
    ]


def _disciplinas_permitidas():
    """Lista as disciplinas que o usuário pode visualizar."""

    if st.session_state.get("perfil") == "administrador":
        return list(mock_data.DISCIPLINAS)

    return sorted({
        item["Disciplina"]
        for item in _atribuicoes_permitidas()
    })


def _turmas_permitidas(disciplina):
    """Lista as turmas autorizadas para uma disciplina."""

    if st.session_state.get("perfil") == "administrador":
        return list(mock_data.TURMAS_AVALIACAO)

    return sorted({
        item["Turma"]
        for item in _atribuicoes_permitidas()
        if item["Disciplina"] == disciplina
    })


@st.dialog("Inserir avaliação")
def _dialogo_inserir_avaliacao():
    """Cadastra uma avaliação na sessão atual."""

    disciplinas = _disciplinas_permitidas()

    if not disciplinas:
        st.warning(
            "Nenhuma disciplina atribuída ao seu perfil."
        )
        return

    nome = st.text_input(
        "Nome da avaliação",
        key="ma_novo_nome",
    )

    disciplina = st.selectbox(
        "Disciplina",
        disciplinas,
        key="ma_nova_disciplina",
    )

    turmas = _turmas_permitidas(disciplina)

    if not turmas:
        st.info(
            "Nenhuma turma disponível para esta disciplina."
        )
        return

    if st.session_state.get("ma_nova_turma") not in turmas:
        st.session_state["ma_nova_turma"] = turmas[0]

    turma = st.selectbox(
        "Turma",
        turmas,
        key="ma_nova_turma",
    )

    tipo = st.selectbox(
        "Tipo",
        mock_data.TIPOS_QUESTAO,
        key="ma_novo_tipo",
    )

    quantidade = st.number_input(
        "Número de questões",
        min_value=1,
        max_value=100,
        value=10,
        step=1,
        key="ma_nova_quantidade",
    )

    if st.button(
        "Salvar",
        type="primary",
        key="ma_salvar_avaliacao",
    ):
        if not nome.strip():
            st.error("Informe o nome da avaliação.")
            return

        st.session_state.setdefault(
            "ma_avaliacoes_criadas",
            [],
        ).append({
            "Nome": nome.strip(),
            "Disciplina": disciplina,
            "Turma": turma,
            "Tipo": tipo,
            "Questões": int(quantidade),
            "Professor": (
                st.session_state.get("professor_atual")
                if st.session_state.get("perfil") == "professor"
                else None
            ),
        })

        st.session_state["ma_aviso"] = (
            f'Avaliação "{nome.strip()}" cadastrada '
            "nesta sessão. Aguardando resultados."
        )

        st.rerun()


@st.dialog("Registrar ação pedagógica")
def _dialogo_registrar_acao(nome_questao):
    """Permite registrar uma ação pedagógica."""

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
    """Exibe informações da questão selecionada."""

    total = mock_data.TOTAL_RESPONDENTES
    respostas = detalhe["respostas"]

    erradas = {
        letra: quantidade
        for letra, quantidade in respostas.items()
        if letra != detalhe["correta"]
    }

    errada_mais_escolhida = (
        max(erradas, key=erradas.get)
        if erradas
        else "-"
    )

    interpretacao = (
        mock_data.INTERPRETACAO_POR_DIFICULDADE[
            questao["Dificuldade"]
        ].format(
            correta=detalhe["correta"],
            errada_mais_escolhida=errada_mais_escolhida,
        )
    )

    with st.container(key="mapa_detalhe"):

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

        with st.container(key="mapa_resumo_questao"):

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

        st.markdown(
            "#### Distribuição de resposta"
        )

        for letra, quantidade in respostas.items():

            percentual = (
                quantidade / total
                if total
                else 0
            )

            rotulo = (
                f"{letra}   "
                f"{quantidade}   "
                f"{percentual_br(percentual * 100, 0)}"
            )

            st.progress(
                percentual,
                text=rotulo,
            )

            if letra == detalhe["correta"]:
                st.caption(
                    f"Alternativa correta: {letra}"
                )

        st.divider()

        st.markdown("#### Interpretação")
        st.write(interpretacao)

        acao = st.session_state.get(
            "ma_acoes",
            {},
        ).get(questao["Questão"])

        if acao:
            st.caption(
                f"Ação registrada: {acao}"
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
    """Exibe o gráfico e a tabela de desempenho."""

    with st.container(key="mapa_grafico"):

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
            tickvals=[0, 20, 40, 60, 80, 100],
            ticksuffix="%",
            title=None,
            showgrid=True,
            gridcolor="#E6E6E6",
        )

        figura.update_yaxes(title=None)

        figura.update_traces(
            texttemplate="%{x:.0f}%",
            textposition="outside",
        )

        figura.update_layout(
            height=355,
            autosize=True,
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
                "responsive": True,
            },
        )

    with st.container(key="mapa_tabela"):

        linha_escolhida = tabela_selecionavel(
            questoes[COLUNAS_TABELA],
            "ma_tabela",
        )

    return linha_escolhida



def _botoes_cabecalho():
    """Exibe as ações principais do Mapa de Acertos."""

    titulo_pagina("Mapa de Acertos")

    with st.container(key="mapa_botoes"):

        col_csv, col_excel, col_inserir = st.columns(
            [1, 1, 1.3],
            gap="small",
        )

        with col_csv:
            st.download_button(
                "Baixar modelo CSV",
                data=_arquivo_modelo(
                    "Resultados de avaliações",
                    "CSV",
                ),
                file_name="modelo_resultados_avaliacoes.csv",
                mime="text/csv",
                key="ma_modelo_csv",
                use_container_width=True,
            )

        with col_excel:
            st.download_button(
                "Baixar modelo Excel",
                data=_arquivo_modelo(
                    "Resultados de avaliações",
                    "Excel",
                ),
                file_name="modelo_resultados_avaliacoes.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                key="ma_modelo_excel",
                use_container_width=True,
            )

        with col_inserir:
            if st.button(
                "Inserir avaliação",
                key="btn_inserir_avaliacao",
                use_container_width=True,
            ):
                _dialogo_inserir_avaliacao()

    st.write("")

    with st.container(key="mapa_acesso_modelos"):
        col_modelos, col_espaco = st.columns(
            [1.3, 2.7],
            gap="small",
        )

        with col_modelos:
            if st.button(
                "Modelos de Prova",
                icon=":material/description:",
                key="ma_abrir_modelos",
                use_container_width=True,
            ):
                pagina = st.session_state.get(
                    "pagina_modelos_prova"
                )

                if pagina is not None:
                    st.switch_page(pagina)


def render():
    """Renderiza o Mapa de Acertos conforme o perfil."""

    aplicar_responsividade()

    st.session_state.setdefault(
        "ma_questao_selecionada",
        None,
    )

    _botoes_cabecalho()

    aviso = st.session_state.pop(
        "ma_aviso",
        None,
    )

    if aviso:
        st.success(aviso)

    disciplinas = _disciplinas_permitidas()

    if not disciplinas:
        st.info(
            "Nenhuma disciplina foi atribuída "
            "ao seu perfil."
        )
        return

    with st.container(key="mapa_filtros"):

        (
            col_avaliacao,
            col_disciplina,
            col_turma,
            col_tipo,
        ) = st.columns(
            [1, 1.4, 1, 1.1],
            gap="small",
        )

        with col_disciplina:

            if (
                st.session_state.get("ma_disciplina")
                not in disciplinas
            ):
                st.session_state["ma_disciplina"] = (
                    disciplinas[0]
                )

            disciplina = st.selectbox(
                "Disciplina",
                disciplinas,
                key="ma_disciplina",
            )

        turmas = _turmas_permitidas(disciplina)

        if not turmas:
            st.info(
                "Nenhuma turma disponível "
                "para esta disciplina."
            )
            return

        with col_turma:

            if st.session_state.get("ma_turma") not in turmas:
                st.session_state["ma_turma"] = turmas[0]

            turma = st.selectbox(
                "Turma",
                turmas,
                key="ma_turma",
            )

        perfil = st.session_state.get("perfil")
        professor = st.session_state.get("professor_atual")

        cadastradas = [
            item["Nome"]
            for item in st.session_state.get(
                "ma_avaliacoes_criadas",
                [],
            )
            if item["Disciplina"] == disciplina
            and item["Turma"] == turma
            and (
                perfil == "administrador"
                or item["Professor"] == professor
            )
        ]

        with col_avaliacao:

            opcoes_avaliacoes = [
                "Nenhuma avaliação com resultados"
            ] + cadastradas

            if (
                st.session_state.get("ma_avaliacao_nova")
                not in opcoes_avaliacoes
            ):
                st.session_state["ma_avaliacao_nova"] = (
                    opcoes_avaliacoes[0]
                )

            avaliacao = st.selectbox(
                "Avaliação",
                opcoes_avaliacoes,
                key="ma_avaliacao_nova",
            )

        with col_tipo:
            st.selectbox(
                "Tipo",
                mock_data.TIPOS_QUESTAO,
                key="ma_tipo_novo",
                disabled=True,
            )

    if avaliacao != "Nenhuma avaliação com resultados":
        st.caption(
            f"Avaliação cadastrada: {avaliacao} • "
            f"{disciplina} • {turma}. "
            "Aguardando importação das respostas."
        )

    st.info(
        "Ainda não há resultados de avaliações vinculados "
        f"à turma {turma} e à disciplina {disciplina}. "
        "Os gráficos e a tabela serão preenchidos após "
        "a importação das respostas."
    )
