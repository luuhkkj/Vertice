"""Tela: Mapa de Acertos (Fase 5 — Integração real com o backend do Vértice)."""

from datetime import date
from typing import Any, Optional

import pandas as pd
import streamlit as st

from components.graficos import (
    ALTERNATIVAS_ORDEM_OFICIAL,
    grafico_acertos_erros_brancos_por_questao,
    grafico_comparacao_desempenho_questoes,
    grafico_desempenho_por_topico,
    grafico_distribuicao_alternativas_questao,
    grafico_distribuicao_geral_acertos_avaliacao,
    grafico_percentual_acerto_por_questao,
)
from components.layout import titulo_pagina
from components.tabelas import tabela_selecionavel
from data import mock_data
from data.api_client import (
    consultar_indicadores_avaliacoes,
    criar_avaliacao_api,
    listar_atribuicoes_api,
    listar_avaliacoes_api,
    listar_disciplinas_api,
    listar_turmas_api,
    possui_sessao_api_ativa,
    registrar_acompanhamento_pedagogico_api,
)
from data.atribuicoes import listar_atribuicoes
from pages.entrada_dados import _arquivo_modelo
from utils.formatacao import decimal_br, numero_br, percentual_br


COLUNAS_TABELA = [
    "Questão",
    "Tipo",
    "Gabarito",
    "Tópico",
    "Dificuldade",
    "Acertos",
    "Erros",
    "Em branco",
    "Acerto (%)",
    "Ação sugerida",
]


ACAO_SUGERIDA_POR_FAIXA = {
    "Fácil": "Manter abordagem e aprofundar conceitos",
    "Adequada": "Reforço pontual nos distratores",
    "Atenção": "Revisão orientada do tópico em sala",
    "Difícil": "Retomada prioritária de conteúdo e resolução comentada",
}


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

                .st-key-mapa_botoes
                [data-testid="stHorizontalBlock"]
                > [data-testid="stColumn"]:nth-child(3) {
                    grid-column: 1 / -1;
                }

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

                .st-key-mapa_botoes button {
                    width: 100% !important;
                }

                .st-key-mapa_filtros
                [data-testid="stSelectbox"] {
                    width: 100% !important;
                    min-width: 0 !important;
                }

                .st-key-mapa_grafico
                [data-testid="stPlotlyChart"] {
                    width: 100% !important;
                    min-width: 0 !important;
                    max-width: 100% !important;
                }

                .st-key-mapa_tabela {
                    max-width: 100% !important;
                    overflow-x: auto !important;
                }

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
    """Retorna as atribuições permitidas ao usuário na sessão local."""
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
    """Lista as disciplinas que o usuário pode visualizar na sessão local."""
    if st.session_state.get("perfil") == "administrador":
        return list(mock_data.DISCIPLINAS)

    return sorted({
        item["Disciplina"]
        for item in _atribuicoes_permitidas()
    })


def _turmas_permitidas(disciplina):
    """Lista as turmas autorizadas para uma disciplina na sessão local."""
    if st.session_state.get("perfil") == "administrador":
        return list(mock_data.TURMAS_AVALIACAO)

    return sorted({
        item["Turma"]
        for item in _atribuicoes_permitidas()
        if item["Disciplina"] == disciplina
    })


def _carregar_contexto_api() -> dict[str, Any]:
    """Consulta turmas, disciplinas, atribuições e avaliações reais na API do Vértice."""
    contexto: dict[str, Any] = {
        "conectado": False,
        "sessao_expirada": False,
        "sem_permissao": False,
        "erro_comunicacao": None,
        "turmas": [],
        "disciplinas": [],
        "atribuicoes": [],
        "avaliacoes": [],
    }

    if st.session_state.get("sessao_api_expirada"):
        contexto["sessao_expirada"] = True
        contexto["erro_comunicacao"] = st.session_state.get(
            "mensagem_sessao_expirada",
            "Sua sessão expirou. Faça login novamente.",
        )
        return contexto

    if not possui_sessao_api_ativa():
        return contexto

    resp_turmas = listar_turmas_api()
    if resp_turmas.sessao_expirada:
        contexto["sessao_expirada"] = True
        contexto["erro_comunicacao"] = resp_turmas.erro
        return contexto
    if resp_turmas.sem_permissao:
        contexto["sem_permissao"] = True
        contexto["erro_comunicacao"] = resp_turmas.erro
        return contexto
    if not resp_turmas.ok:
        contexto["erro_comunicacao"] = resp_turmas.erro
        return contexto

    resp_disc = listar_disciplinas_api()
    resp_atrib = listar_atribuicoes_api()
    resp_av = listar_avaliacoes_api()

    for r in (resp_disc, resp_atrib, resp_av):
        if r.sessao_expirada:
            contexto["sessao_expirada"] = True
            contexto["erro_comunicacao"] = r.erro
            return contexto
        if r.sem_permissao:
            contexto["sem_permissao"] = True
            contexto["erro_comunicacao"] = r.erro
            return contexto
        if not r.ok:
            contexto["erro_comunicacao"] = r.erro
            return contexto

    turmas_lista = resp_turmas.dados if isinstance(resp_turmas.dados, list) else []
    disc_lista = resp_disc.dados if isinstance(resp_disc.dados, list) else []
    atrib_lista = resp_atrib.dados if isinstance(resp_atrib.dados, list) else []
    av_lista = resp_av.dados if isinstance(resp_av.dados, list) else []

    # Se o usuário for professor, restringe disciplinas às vinculadas às suas turmas ou avaliações
    usuario_api = st.session_state.get("usuario_api") or {}
    papel = str(usuario_api.get("papel") or st.session_state.get("papel_api") or "").lower()
    if papel == "professor" and atrib_lista:
        possui_vinculo_geral = any(a.get("disciplina_id") is None for a in atrib_lista)
        if not possui_vinculo_geral:
            ids_disc_prof = {
                str(a["disciplina_id"])
                for a in atrib_lista
                if a.get("disciplina_id") is not None
            } | {
                str(av["disciplina_id"])
                for av in av_lista
                if av.get("disciplina_id") is not None
            }
            disc_lista = [
                d for d in disc_lista if str(d.get("id")) in ids_disc_prof
            ]

    contexto["conectado"] = True
    contexto["turmas"] = turmas_lista
    contexto["disciplinas"] = disc_lista
    contexto["atribuicoes"] = atrib_lista
    contexto["avaliacoes"] = av_lista
    return contexto


def _interpretar_questao(questao_item: dict[str, Any]) -> str:
    """Gera texto de interpretação pedagógica com base nos indicadores reais da questão."""
    total_reg = int(questao_item.get("total_respostas_registradas") or 0)
    if total_reg == 0:
        return (
            "Ainda não há respostas individuais registradas para esta questão. "
            "Importe a planilha de resultados para visualizar a distribuição e o diagnóstico."
        )

    faixa = (
        questao_item.get("faixa_desempenho_observada")
        or questao_item.get("faixa_dificuldade_cadastrada")
        or "Adequada"
    )
    base = mock_data.INTERPRETACAO_POR_DIFICULDADE.get(
        faixa,
        "Análise consolidada das respostas registradas para a questão.",
    )
    tipo_q = str(questao_item.get("tipo_questao") or "").upper()
    correta = questao_item.get("alternativa_correta")
    dist = questao_item.get("distribuicao_alternativas") or {}

    if tipo_q == "FECHADA" and correta:
        distratores = {
            alt: int(qtd)
            for alt, qtd in dist.items()
            if alt not in (correta, "BRANCO") and int(qtd) > 0
        }
        if distratores:
            distrator_top = max(distratores, key=distratores.get)
            qtd_top = distratores[distrator_top]
            return (
                f"{base} O gabarito oficial é a alternativa {correta}. "
                f"Entre os erros, a alternativa mais assinalada foi {distrator_top} ({qtd_top} estudante(s))."
            )
        return f"{base} O gabarito oficial é a alternativa {correta}."

    media_nota = questao_item.get("media_nota_questao")
    valor_q = questao_item.get("valor_questao")
    if media_nota is not None and valor_q is not None:
        return (
            f"{base} Questão discursiva/aberta com média de {decimal_br(float(media_nota), 2)} "
            f"ponto(s) de um valor máximo de {decimal_br(float(valor_q), 2)}."
        )
    return base


def _construir_dataframe_questoes(questoes_api: list[dict[str, Any]]) -> pd.DataFrame:
    """Transforma a lista de `IndicadorQuestaoSchema` da API em DataFrame sem recalcular métricas."""
    linhas = []
    acoes_sessao = st.session_state.get("ma_acoes", {})

    for q in questoes_api:
        cod = str(q.get("codigo_questao") or "")
        tipo_q = str(q.get("tipo_questao") or "FECHADA").upper()
        gabarito = (
            str(q.get("alternativa_correta") or "-")
            if tipo_q == "FECHADA"
            else "Discursiva"
        )
        topico = str(q.get("topico") or "Geral / Não especificado")
        faixa_obs = q.get("faixa_desempenho_observada")
        faixa_cad = q.get("faixa_dificuldade_cadastrada") or "Adequada"
        dificuldade = str(faixa_obs or faixa_cad)
        taxa = q.get("taxa_acerto_percentual")
        taxa_num = float(taxa) if taxa is not None else 0.0

        acao_reg = acoes_sessao.get(cod)
        acao_sugerida = (
            f"Registrada: {acao_reg}"
            if acao_reg
            else ACAO_SUGERIDA_POR_FAIXA.get(dificuldade, "Acompanhamento pedagógico")
        )

        linhas.append({
            "Questão": cod,
            "Tipo": "Fechada" if tipo_q == "FECHADA" else "Aberta",
            "Gabarito": gabarito,
            "Tópico": topico,
            "Dificuldade": dificuldade,
            "Dificuldade cadastrada": str(faixa_cad),
            "Acertos": int(q.get("quantidade_acertos") or 0),
            "Erros": int(q.get("quantidade_erros") or 0),
            "Em branco": int(q.get("quantidade_em_branco") or 0),
            "Ausentes": int(q.get("quantidade_respostas_ausentes") or 0),
            "Acerto (%)": taxa_num,
            "Ação sugerida": acao_sugerida,
        })

    if not linhas:
        return pd.DataFrame(columns=COLUNAS_TABELA)
    return pd.DataFrame(linhas)


@st.dialog("Inserir avaliação")
def _dialogo_inserir_avaliacao(contexto_api: Optional[dict[str, Any]] = None):
    """Cadastra uma avaliação no backend (quando conectado) ou na sessão atual."""
    conectado = bool(contexto_api and contexto_api.get("conectado"))

    if conectado:
        disciplinas_api = contexto_api.get("disciplinas") or []
        turmas_api = contexto_api.get("turmas") or []
        atribuicoes_api = contexto_api.get("atribuicoes") or []

        if not disciplinas_api or not turmas_api:
            st.warning(
                "Nenhuma disciplina ou turma autorizada foi encontrada para o seu perfil."
            )
            return

        mapa_disc = {
            f"{d['nome']} ({d['codigo']})": d for d in disciplinas_api
        }
        nome = st.text_input("Nome da avaliação", key="ma_novo_nome")
        codigo = st.text_input(
            "Código da avaliação (opcional, ex.: AV1-MAT-9A)",
            key="ma_novo_codigo",
        )
        rotulo_disc = st.selectbox(
            "Disciplina",
            list(mapa_disc.keys()),
            key="ma_nova_disciplina_api",
        )
        disc_sel = mapa_disc[rotulo_disc]

        # Filtra turmas compatíveis com o vínculo do professor (se aplicável)
        usuario_api = st.session_state.get("usuario_api") or {}
        papel = str(usuario_api.get("papel") or "").lower()
        if papel == "professor" and atribuicoes_api:
            turmas_ids_validas = {
                str(a["turma_id"])
                for a in atribuicoes_api
                if a.get("disciplina_id") is None
                or str(a.get("disciplina_id")) == str(disc_sel["id"])
            }
            turmas_filtradas = [
                t for t in turmas_api if str(t["id"]) in turmas_ids_validas
            ]
        else:
            turmas_filtradas = list(turmas_api)

        if not turmas_filtradas:
            st.info("Nenhuma turma autorizada para esta disciplina.")
            return

        mapa_turmas = {t["nome"]: t for t in turmas_filtradas}
        nome_turma = st.selectbox(
            "Turma",
            list(mapa_turmas.keys()),
            key="ma_nova_turma_api",
        )
        turma_sel = mapa_turmas[nome_turma]

        periodo = st.selectbox(
            "Período letivo",
            ["1º Bimestre", "2º Bimestre", "3º Bimestre", "4º Bimestre"],
            key="ma_novo_periodo_api",
        )
        data_av = st.date_input(
            "Data da avaliação",
            value=date.today(),
            key="ma_nova_data_api",
        )

        if st.button("Salvar", type="primary", key="ma_salvar_avaliacao"):
            if not nome.strip():
                st.error("Informe o nome da avaliação.")
                return

            resp = criar_avaliacao_api(
                titulo=nome.strip(),
                turma_id=str(turma_sel["id"]),
                disciplina_id=str(disc_sel["id"]),
                periodo_letivo=periodo,
                data_avaliacao=data_av.isoformat(),
                codigo=codigo.strip() if codigo else None,
            )
            if resp.ok:
                st.session_state["ma_aviso"] = (
                    f'Avaliação "{nome.strip()}" cadastrada com sucesso no servidor.'
                )
                st.rerun()
            else:
                st.error(resp.erro or "Não foi possível cadastrar a avaliação.")
        return

    # Fallback de sessão local quando o backend não está conectado
    disciplinas = _disciplinas_permitidas()
    if not disciplinas:
        st.warning("Nenhuma disciplina atribuída ao seu perfil.")
        return

    nome = st.text_input("Nome da avaliação", key="ma_novo_nome")
    disciplina = st.selectbox(
        "Disciplina",
        disciplinas,
        key="ma_nova_disciplina",
    )
    turmas = _turmas_permitidas(disciplina)
    if not turmas:
        st.info("Nenhuma turma disponível para esta disciplina.")
        return

    if st.session_state.get("ma_nova_turma") not in turmas:
        st.session_state["ma_nova_turma"] = turmas[0]

    turma = st.selectbox("Turma", turmas, key="ma_nova_turma")
    tipo = st.selectbox("Tipo", mock_data.TIPOS_QUESTAO, key="ma_novo_tipo")
    quantidade = st.number_input(
        "Número de questões",
        min_value=1,
        max_value=100,
        value=10,
        step=1,
        key="ma_nova_quantidade",
    )

    if st.button("Salvar", type="primary", key="ma_salvar_avaliacao"):
        if not nome.strip():
            st.error("Informe o nome da avaliação.")
            return

        st.session_state.setdefault("ma_avaliacoes_criadas", []).append({
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
            f'Avaliação "{nome.strip()}" cadastrada nesta sessão. Aguardando resultados.'
        )
        st.rerun()


@st.dialog("Registrar ação pedagógica")
def _dialogo_registrar_acao(
    nome_questao: str,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
):
    """Permite registrar uma ação pedagógica vinculada à questão/avaliação."""
    st.markdown(f"**Questão:** `{nome_questao}`")

    tipo_acao = st.selectbox(
        "Tipo de ação pedagógica",
        [
            "Revisão de conteúdo em sala",
            "Lista de exercícios direcionada",
            "Atendimento individualizado / plantão",
            "Reelaboração didática do tópico",
        ],
        key="ma_tipo_acao_pedagogica",
    )
    texto = st.text_area(
        "Descreva a ação pedagógica planejada ou realizada",
        key="ma_texto_acao_pedagogica",
    )

    if st.button("Salvar", type="primary", key="ma_confirmar_acao_pedagogica"):
        if not texto or len(texto.strip()) < 3:
            st.error("Descreva a ação pedagógica (mínimo de 3 caracteres) antes de salvar.")
            return

        descricao_completa = f"[Questão {nome_questao}] {texto.strip()}"
        if possui_sessao_api_ativa() and turma_id:
            resp = registrar_acompanhamento_pedagogico_api(
                turma_id=str(turma_id),
                disciplina_id=str(disciplina_id) if disciplina_id else None,
                tipo_acao=tipo_acao,
                descricao=descricao_completa,
            )
            if not resp.ok:
                st.error(resp.erro or "Erro ao salvar acompanhamento no servidor.")
                return

        st.session_state.setdefault("ma_acoes", {})[nome_questao] = (
            f"{tipo_acao}: {texto.strip()}"
        )
        st.session_state["ma_aviso"] = (
            f"Ação pedagógica registrada para a questão {nome_questao}."
        )
        st.rerun()


def _painel_questao(questao_item: dict[str, Any]):
    """Exibe informações detalhadas e distribuição de alternativas da questão selecionada (Bloco B)."""
    cod_questao = str(questao_item.get("codigo_questao") or "")
    tipo_q = str(questao_item.get("tipo_questao") or "FECHADA").upper()
    correta = questao_item.get("alternativa_correta")
    topico = questao_item.get("topico") or "Geral / Não especificado"
    valor_q = float(questao_item.get("valor_questao") or 1.0)
    faixa_cad = questao_item.get("faixa_dificuldade_cadastrada") or "Adequada"
    faixa_obs = questao_item.get("faixa_desempenho_observada") or "Sem respostas"

    total_esp = int(questao_item.get("total_respostas_esperadas") or 0)
    total_reg = int(questao_item.get("total_respostas_registradas") or 0)
    ausentes = int(questao_item.get("quantidade_respostas_ausentes") or 0)
    acertos = int(questao_item.get("quantidade_acertos") or 0)
    erros = int(questao_item.get("quantidade_erros") or 0)
    em_branco = int(questao_item.get("quantidade_em_branco") or 0)
    taxa = questao_item.get("taxa_acerto_percentual")
    media_nota = questao_item.get("media_nota_questao")
    dist_alt = questao_item.get("distribuicao_alternativas") or {}

    with st.container(key="mapa_detalhe"):
        col_titulo, col_fechar = st.columns(
            [5, 1],
            vertical_alignment="center",
        )

        with col_titulo:
            st.markdown(f"### Questão {cod_questao}")
            st.caption(
                f"Tipo: **{'Fechada (Múltipla escolha)' if tipo_q == 'FECHADA' else 'Aberta (Discursiva)'}** • "
                f"Peso: **{decimal_br(valor_q, 2)}** • "
                f"Tópico: **{topico}**"
            )

        with col_fechar:
            if st.button(
                "×",
                key="ma_fechar_detalhe",
                help="Fechar detalhes",
            ):
                st.session_state["ma_questao_selecionada"] = None
                st.rerun()

        st.divider()

        with st.container(key="mapa_resumo_questao"):
            if tipo_q == "FECHADA" and correta:
                st.markdown(f"Gabarito oficial: **Alternativa {correta}**")
            st.markdown(
                f"Faixa de dificuldade: **{faixa_obs}** (cadastrada: {faixa_cad})"
            )
            st.markdown(f"**{numero_br(acertos)}** estudante(s) acertaram")
            st.markdown(f"**{numero_br(erros)}** estudante(s) erraram")
            st.markdown(
                f"**{numero_br(em_branco)}** estudante(s) deixaram em branco"
            )
            if ausentes > 0:
                st.markdown(
                    f"**{numero_br(ausentes)}** estudante(s) sem resposta registrada"
                )
            if taxa is not None:
                st.markdown(
                    f"**{percentual_br(float(taxa), 1)}** de acerto "
                    f"(sobre {numero_br(total_esp)} esperada(s))"
                )
            else:
                st.markdown("**Sem taxa de acerto** (nenhuma resposta esperada/registrada)")
            if media_nota is not None:
                st.markdown(
                    f"Nota média na questão: **{decimal_br(float(media_nota), 2)}** / {decimal_br(valor_q, 2)}"
                )

        st.divider()

        st.markdown("#### Distribuição de alternativas")

        if tipo_q == "FECHADA":
            denom_barra = total_esp if total_esp > 0 else max(total_reg, 1)
            for letra in ALTERNATIVAS_ORDEM_OFICIAL:
                quantidade = int(dist_alt.get(letra, 0))
                proporcao = (
                    min(max(quantidade / denom_barra, 0.0), 1.0)
                    if total_esp > 0 or total_reg > 0
                    else 0.0
                )
                rotulo = (
                    f"{letra}   "
                    f"{numero_br(quantidade)} estudante(s)   "
                    f"({percentual_br(proporcao * 100.0, 1)})"
                )
                st.progress(proporcao, text=rotulo)
                if letra == correta:
                    st.caption(f"✓ Alternativa correta (Gabarito): {letra}")

            fig_alt = grafico_distribuicao_alternativas_questao(questao_item)
            if fig_alt is not None and total_reg > 0:
                st.plotly_chart(
                    fig_alt,
                    width="stretch",
                    config={"displayModeBar": False, "responsive": True},
                )
        else:
            st.info(
                "Esta é uma questão ABERTA (discursiva). Questões abertas são "
                "avaliadas por nota obtida e em branco, não possuindo distribuição "
                "entre alternativas A–E."
            )

        st.divider()

        st.markdown("#### Interpretação pedagógica")
        st.write(_interpretar_questao(questao_item))

        acao = st.session_state.get("ma_acoes", {}).get(cod_questao)
        if acao:
            st.caption(f"Ação registrada: {acao}")

        if st.button(
            "Registrar ação pedagógica",
            key="btn_registrar_acao",
            use_container_width=True,
        ):
            _dialogo_registrar_acao(
                cod_questao,
                turma_id=str(questao_item["turma_id"])
                if questao_item.get("turma_id")
                else None,
                disciplina_id=str(questao_item["disciplina_id"])
                if questao_item.get("disciplina_id")
                else None,
            )


def _renderizar_painel_indicadores_reais(
    indicadores_payload: dict[str, Any],
    questao_filtro_codigo: Optional[str] = None,
):
    """Exibe os cartões de resumo, os 6 gráficos analíticos (Bloco C) e a tabela interativa."""
    questoes_todas: list[dict[str, Any]] = list(
        indicadores_payload.get("questoes") or []
    )

    if not questoes_todas:
        st.info(
            "A avaliação selecionada ainda não possui questões cadastradas. "
            "Importe a planilha de resultados de avaliações para visualizar o Mapa de Acertos."
        )
        return

    # Aplica filtro opcional por questão específica quando selecionado pelo usuário
    if questao_filtro_codigo and questao_filtro_codigo != "Todas as questões":
        questoes_exibidas = [
            q
            for q in questoes_todas
            if str(q.get("codigo_questao")) == questao_filtro_codigo
        ]
    else:
        questoes_exibidas = questoes_todas

    total_reg = int(indicadores_payload.get("total_respostas_registradas") or 0)
    total_esp = int(indicadores_payload.get("total_respostas_esperadas") or 0)
    total_acertos = int(indicadores_payload.get("total_acertos") or 0)
    total_erros = int(indicadores_payload.get("total_erros") or 0)
    total_brancos = int(indicadores_payload.get("total_em_branco") or 0)
    taxa_geral = indicadores_payload.get("taxa_acerto_geral_percentual")
    media_pond = indicadores_payload.get("media_avaliacao_ponderada")
    maior_q = indicadores_payload.get("questao_maior_taxa_acerto")
    menor_q = indicadores_payload.get("questao_menor_taxa_acerto")

    # Cartões de métricas consolidadas (sem recalcular no frontend)
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5, gap="small")
    with col_m1:
        st.metric(
            "Taxa geral de acerto",
            percentual_br(float(taxa_geral), 1) if taxa_geral is not None else "—",
        )
    with col_m2:
        st.metric(
            "Média ponderada (0–10)",
            decimal_br(float(media_pond), 2) if media_pond is not None else "—",
        )
    with col_m3:
        st.metric(
            "Acertos / Erros / Em branco",
            f"{numero_br(total_acertos)} / {numero_br(total_erros)} / {numero_br(total_brancos)}",
        )
    with col_m4:
        st.metric(
            "Maior acerto",
            (
                f"{maior_q['codigo_questao']} ({percentual_br(float(maior_q['taxa_acerto_percentual']), 1)})"
                if isinstance(maior_q, dict)
                and maior_q.get("taxa_acerto_percentual") is not None
                else "—"
            ),
        )
    with col_m5:
        st.metric(
            "Maior dificuldade",
            (
                f"{menor_q['codigo_questao']} ({percentual_br(float(menor_q['taxa_acerto_percentual']), 1)})"
                if isinstance(menor_q, dict)
                and menor_q.get("taxa_acerto_percentual") is not None
                else "—"
            ),
        )

    if total_reg == 0:
        st.warning(
            "As questões desta avaliação já estão cadastradas, mas ainda não há "
            "respostas de estudantes registradas. Importe as respostas na página "
            "Entrada de Dados para preencher os gráficos de desempenho."
        )

    df_questoes = _construir_dataframe_questoes(questoes_exibidas)

    # Sincroniza seleção de questão via filtro superior ou clique na tabela
    if questao_filtro_codigo and questao_filtro_codigo != "Todas as questões":
        st.session_state["ma_questao_selecionada"] = questao_filtro_codigo

    cod_selecionado = st.session_state.get("ma_questao_selecionada")
    questao_detalhe = next(
        (
            q
            for q in questoes_todas
            if str(q.get("codigo_questao")) == str(cod_selecionado)
        ),
        None,
    )

    with st.container(key="mapa_colunas_detalhe"):
        if questao_detalhe is not None:
            col_esq, col_dir = st.columns([1.85, 1.15], gap="medium")
        else:
            col_esq = st.container()
            col_dir = None

        with col_esq:
            with st.container(key="mapa_grafico"):
                st.markdown("### Desempenho e Análise Gráfica das Questões")
                (
                    aba_acerto,
                    aba_acertos_erros,
                    aba_alternativas,
                    aba_comparacao,
                    aba_dist_geral,
                    aba_topicos,
                ) = st.tabs([
                    "1. % de Acerto",
                    "2. Acertos x Erros x Em Branco",
                    "3. Alternativas (A–E / Branco)",
                    "4. Comparação entre Questões",
                    "5. Distribuição Geral da Avaliação",
                    "6. Desempenho por Tópico",
                ])

                with aba_acerto:
                    if not df_questoes.empty and total_esp > 0:
                        fig_p = grafico_percentual_acerto_por_questao(df_questoes)
                        st.plotly_chart(
                            fig_p,
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                        )
                    else:
                        st.info("Dados insuficientes para exibir o percentual de acerto por questão.")

                with aba_acertos_erros:
                    if questoes_exibidas and (total_reg > 0 or total_esp > 0):
                        fig_aeb = grafico_acertos_erros_brancos_por_questao(
                            questoes_exibidas
                        )
                        st.plotly_chart(
                            fig_aeb,
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                        )
                    else:
                        st.info("Ainda não há respostas registradas para comparar acertos, erros e respostas em branco.")

                with aba_alternativas:
                    questoes_fechadas = [
                        q
                        for q in questoes_exibidas
                        if str(q.get("tipo_questao", "")).upper() == "FECHADA"
                    ]
                    if not questoes_fechadas:
                        st.info(
                            "As questões selecionadas são do tipo ABERTA (discursiva). "
                            "Questões abertas não possuem distribuição de alternativas A–E."
                        )
                    else:
                        opcoes_qf = [
                            str(q["codigo_questao"]) for q in questoes_fechadas
                        ]
                        padrao_qf = (
                            cod_selecionado
                            if cod_selecionado in opcoes_qf
                            else opcoes_qf[0]
                        )
                        cod_qf_escolhida = st.selectbox(
                            "Selecione a questão fechada para inspecionar as alternativas (A, B, C, D, E e BRANCO)",
                            opcoes_qf,
                            index=opcoes_qf.index(padrao_qf),
                            key="ma_select_questao_alternativas",
                        )
                        q_alvo = next(
                            q
                            for q in questoes_fechadas
                            if str(q["codigo_questao"]) == cod_qf_escolhida
                        )
                        fig_dist_alt = grafico_distribuicao_alternativas_questao(
                            q_alvo
                        )
                        if fig_dist_alt is not None:
                            st.plotly_chart(
                                fig_dist_alt,
                                width="stretch",
                                config={
                                    "displayModeBar": False,
                                    "responsive": True,
                                },
                            )

                with aba_comparacao:
                    if questoes_exibidas and total_esp > 0:
                        fig_cmp = grafico_comparacao_desempenho_questoes(
                            questoes_exibidas
                        )
                        st.plotly_chart(
                            fig_cmp,
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                        )
                    else:
                        st.info("Dados insuficientes para comparar o desempenho entre questões.")

                with aba_dist_geral:
                    fig_geral = grafico_distribuicao_geral_acertos_avaliacao(
                        indicadores_payload
                    )
                    if fig_geral is not None:
                        st.plotly_chart(
                            fig_geral,
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                        )
                    else:
                        st.info(
                            "Ainda não há respostas registradas na avaliação para gerar a distribuição geral de acertos."
                        )

                with aba_topicos:
                    dist_topicos = (
                        indicadores_payload.get("distribuicao_por_topico") or []
                    )
                    fig_top = grafico_desempenho_por_topico(dist_topicos)
                    if fig_top is not None:
                        st.plotly_chart(
                            fig_top,
                            width="stretch",
                            config={"displayModeBar": False, "responsive": True},
                        )
                    else:
                        st.info(
                            "Não há dados suficientes por tópico/habilidade para esta avaliação."
                        )

            with st.container(key="mapa_tabela"):
                st.caption(
                    "Clique em uma questão na tabela abaixo para abrir o painel lateral de diagnóstico e alternativas."
                )
                indice_escolhido = tabela_selecionavel(
                    df_questoes[COLUNAS_TABELA],
                    "ma_tabela",
                )
                if indice_escolhido is not None and 0 <= indice_escolhido < len(df_questoes):
                    cod_clicado = str(df_questoes.iloc[indice_escolhido]["Questão"])
                    if st.session_state.get("ma_questao_selecionada") != cod_clicado:
                        st.session_state["ma_questao_selecionada"] = cod_clicado
                        st.rerun()

        if col_dir is not None and questao_detalhe is not None:
            with col_dir:
                _painel_questao(questao_detalhe)


def _botoes_cabecalho(contexto_api: Optional[dict[str, Any]] = None):
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
                _dialogo_inserir_avaliacao(contexto_api)

    st.write("")

    with st.container(key="mapa_acesso_modelos"):
        col_modelos, _col_espaco = st.columns(
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
                pagina = st.session_state.get("pagina_modelos_prova")
                if pagina is not None:
                    st.switch_page(pagina)


def _renderizar_modo_api(contexto_api: dict[str, Any]):
    """Renderiza filtros dinâmicos (Bloco D) e indicadores reais (Blocos B e C) conectados ao backend."""
    disciplinas_api: list[dict[str, Any]] = contexto_api["disciplinas"]
    turmas_api: list[dict[str, Any]] = contexto_api["turmas"]
    atribuicoes_api: list[dict[str, Any]] = contexto_api["atribuicoes"]
    avaliacoes_api: list[dict[str, Any]] = contexto_api["avaliacoes"]

    if not disciplinas_api:
        st.info("Nenhuma disciplina foi atribuída ou cadastrada para o seu perfil.")
        return

    if not turmas_api:
        st.info("Nenhuma turma autorizada foi encontrada no seu escopo de acesso.")
        return

    # Mapeamento de disciplinas
    opcoes_disc_nomes = [d["nome"] for d in disciplinas_api]
    mapa_disc_por_nome = {d["nome"]: d for d in disciplinas_api}

    with st.container(key="mapa_filtros"):
        (
            col_disciplina,
            col_turma,
            col_periodo,
            col_avaliacao,
            col_questao,
        ) = st.columns(
            [1.2, 1.0, 1.0, 1.4, 1.0],
            gap="small",
        )

        with col_disciplina:
            if st.session_state.get("ma_disciplina") not in opcoes_disc_nomes:
                st.session_state["ma_disciplina"] = opcoes_disc_nomes[0]
            disciplina_nome = st.selectbox(
                "Disciplina",
                opcoes_disc_nomes,
                key="ma_disciplina",
            )
            disc_obj = mapa_disc_por_nome[disciplina_nome]
            disc_id = str(disc_obj["id"])

        # Filtra turmas compatíveis com a disciplina selecionada (respeitando vínculo de professor)
        usuario_api = st.session_state.get("usuario_api") or {}
        papel = str(usuario_api.get("papel") or st.session_state.get("papel_api") or "").lower()
        if papel == "professor" and atribuicoes_api:
            turmas_ids_permitidas = {
                str(a["turma_id"])
                for a in atribuicoes_api
                if a.get("disciplina_id") is None
                or str(a.get("disciplina_id")) == disc_id
            }
            turmas_da_disciplina = [
                t for t in turmas_api if str(t["id"]) in turmas_ids_permitidas
            ]
        else:
            turmas_da_disciplina = list(turmas_api)

        if not turmas_da_disciplina:
            st.info("Nenhuma turma disponível para esta disciplina no seu escopo.")
            return

        opcoes_turma_nomes = [t["nome"] for t in turmas_da_disciplina]
        mapa_turma_por_nome = {t["nome"]: t for t in turmas_da_disciplina}

        with col_turma:
            if st.session_state.get("ma_turma") not in opcoes_turma_nomes:
                st.session_state["ma_turma"] = opcoes_turma_nomes[0]
            turma_nome = st.selectbox(
                "Turma",
                opcoes_turma_nomes,
                key="ma_turma",
            )
            turma_obj = mapa_turma_por_nome[turma_nome]
            turma_id = str(turma_obj["id"])

        # Avaliações disponíveis para a combinação de turma + disciplina
        avaliacoes_recorte = [
            av
            for av in avaliacoes_api
            if str(av.get("turma_id")) == turma_id
            and str(av.get("disciplina_id")) == disc_id
        ]

        periodos_disponiveis = sorted({
            str(av.get("periodo_letivo"))
            for av in avaliacoes_recorte
            if av.get("periodo_letivo")
        })
        opcoes_periodo = ["Todos os períodos"] + (
            periodos_disponiveis
            if periodos_disponiveis
            else ["1º Bimestre", "2º Bimestre", "3º Bimestre", "4º Bimestre"]
        )

        with col_periodo:
            if st.session_state.get("ma_periodo") not in opcoes_periodo:
                st.session_state["ma_periodo"] = opcoes_periodo[0]
            periodo_sel = st.selectbox(
                "Período letivo",
                opcoes_periodo,
                key="ma_periodo",
            )

        if periodo_sel != "Todos os períodos":
            avaliacoes_filtradas = [
                av
                for av in avaliacoes_recorte
                if str(av.get("periodo_letivo")) == periodo_sel
            ]
        else:
            avaliacoes_filtradas = avaliacoes_recorte

        mapa_avaliacoes = {
            f"{av['codigo']} — {av['titulo']}": av for av in avaliacoes_filtradas
        }
        opcoes_avaliacoes = (
            list(mapa_avaliacoes.keys())
            if mapa_avaliacoes
            else ["Nenhuma avaliação com resultados"]
        )

        with col_avaliacao:
            if st.session_state.get("ma_avaliacao_nova") not in opcoes_avaliacoes:
                st.session_state["ma_avaliacao_nova"] = opcoes_avaliacoes[0]
            avaliacao_rotulo = st.selectbox(
                "Avaliação",
                opcoes_avaliacoes,
                key="ma_avaliacao_nova",
            )

        av_selecionada = mapa_avaliacoes.get(avaliacao_rotulo)

        # Reinicia questão selecionada caso o usuário troque de avaliação/turma/disciplina
        chave_contexto_atual = (
            disc_id,
            turma_id,
            periodo_sel,
            str(av_selecionada["id"]) if av_selecionada else None,
        )
        if st.session_state.get("ma_contexto_anterior") != chave_contexto_atual:
            st.session_state["ma_contexto_anterior"] = chave_contexto_atual
            st.session_state["ma_questao_selecionada"] = None
            st.session_state["ma_filtro_questao"] = "Todas as questões"

        if av_selecionada is None:
            with col_questao:
                st.selectbox(
                    "Questão",
                    ["Todas as questões"],
                    key="ma_filtro_questao_vazio",
                    disabled=True,
                )
            st.info(
                f"Ainda não há resultados de avaliações vinculados à turma {turma_nome} "
                f"e à disciplina {disciplina_nome}"
                + (
                    f" no período {periodo_sel}."
                    if periodo_sel != "Todos os períodos"
                    else "."
                )
                + " Os gráficos e a tabela serão preenchidos após a importação das respostas."
            )
            return

        with st.spinner("Carregando indicadores e Mapa de Acertos..."):
            resp_ind = consultar_indicadores_avaliacoes(
                turma_id=turma_id,
                disciplina_id=disc_id,
                periodo_letivo=(
                    periodo_sel if periodo_sel != "Todos os períodos" else None
                ),
                avaliacao_id=str(av_selecionada["id"]),
            )

        if resp_ind.sessao_expirada:
            st.warning(
                resp_ind.erro
                or "Sua sessão expirou. Realize login novamente para continuar."
            )
            return
        if resp_ind.sem_permissao:
            st.error(
                resp_ind.erro
                or "Você não possui permissão para visualizar os indicadores desta turma/disciplina."
            )
            return
        if not resp_ind.ok or not isinstance(resp_ind.dados, dict):
            st.error(
                resp_ind.erro
                or "Erro ao consultar os indicadores da avaliação no servidor."
            )
            return

        dados_indicadores = resp_ind.dados
        questoes_da_avaliacao = [
            str(q.get("codigo_questao"))
            for q in (dados_indicadores.get("questoes") or [])
            if q.get("codigo_questao")
        ]
        opcoes_questao = ["Todas as questões"] + questoes_da_avaliacao

        with col_questao:
            if st.session_state.get("ma_filtro_questao") not in opcoes_questao:
                st.session_state["ma_filtro_questao"] = "Todas as questões"
            questao_filtro = st.selectbox(
                "Questão",
                opcoes_questao,
                key="ma_filtro_questao",
            )

    st.caption(
        f"Avaliação selecionada: **{av_selecionada['titulo']}** (`{av_selecionada['codigo']}`) • "
        f"Disciplina: **{disciplina_nome}** • Turma: **{turma_nome}** • "
        f"Período: **{av_selecionada.get('periodo_letivo', periodo_sel)}**"
    )

    _renderizar_painel_indicadores_reais(
        dados_indicadores,
        questao_filtro_codigo=questao_filtro,
    )


def render():
    """Renderiza o Mapa de Acertos conforme o perfil e os dados reais do backend."""

    aplicar_responsividade()

    st.session_state.setdefault(
        "ma_questao_selecionada",
        None,
    )

    contexto_api = _carregar_contexto_api()

    _botoes_cabecalho(contexto_api)

    aviso = st.session_state.pop("ma_aviso", None)
    if aviso:
        st.success(aviso)

    if contexto_api.get("sessao_expirada"):
        st.warning(
            contexto_api.get("erro_comunicacao")
            or "Sua sessão expirou. Faça login novamente para visualizar os dados das avaliações."
        )
        return

    if contexto_api.get("sem_permissao"):
        st.error(
            contexto_api.get("erro_comunicacao")
            or "Permissão insuficiente para acessar os dados de avaliações."
        )
        return

    if contexto_api.get("erro_comunicacao"):
        st.error(contexto_api["erro_comunicacao"])
        return

    if contexto_api.get("conectado"):
        _renderizar_modo_api(contexto_api)
        return

    st.warning(
        "Sessão autenticada no backend não encontrada. Faça login com uma conta "
        "válida conectada à API para consultar e registrar dados reais do Mapa de Acertos."
    )
