"""Tela: Visão geral integrada ao backend real do Vértice (Fase 7)."""

from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.cards import card, card_kpi
from components.graficos import (
    grafico_barras_horizontais,
    grafico_rosca,
)
from components.layout import titulo_pagina
from data.api_client import (
    consultar_indicadores_gerais_api,
    listar_disciplinas_api,
    listar_previsoes_api,
    listar_turmas_api,
    possui_sessao_api_ativa,
)


CORES_KPI = ["azul", "verde", "laranja", "vermelho"]

ROTULOS_FAIXAS = {
    "BAIXO": "Baixo",
    "MODERADO": "Moderado",
    "ALTO": "Alto",
    "CRITICO": "Crítico",
}


def aplicar_responsividade():
    """Adapta somente os conteúdos da Visão Geral."""

    st.html(
        """
        <style>
            .st-key-vg_kpis_responsivos,
            .st-key-vg_graficos_linha_1,
            .st-key-vg_graficos_linha_2,
            .st-key-visao_geral_filtros {
                width: 100%;
                min-width: 0;
                max-width: 100%;
            }

            .st-key-vg_kpis_responsivos [data-testid="stColumn"],
            .st-key-vg_graficos_linha_1 [data-testid="stColumn"],
            .st-key-vg_graficos_linha_2 [data-testid="stColumn"],
            .st-key-visao_geral_filtros [data-testid="stColumn"],
            .st-key-vg_kpis_responsivos [data-testid="column"],
            .st-key-vg_graficos_linha_1 [data-testid="column"],
            .st-key-vg_graficos_linha_2 [data-testid="column"],
            .st-key-visao_geral_filtros [data-testid="column"] {
                min-width: 0 !important;
            }

            @media (max-width: 1100px) {
                .st-key-vg_kpis_responsivos [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
                    gap: 14px !important;
                    width: 100% !important;
                }

                .st-key-vg_kpis_responsivos
                [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                }

                .st-key-vg_graficos_linha_1 [data-testid="stHorizontalBlock"],
                .st-key-vg_graficos_linha_2 [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns: minmax(0, 1fr) !important;
                    gap: 14px !important;
                    width: 100% !important;
                }

                .st-key-vg_graficos_linha_1
                [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
                .st-key-vg_graficos_linha_2
                [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                }
            }

            @media (max-width: 640px) {
                .st-key-vg_kpis_responsivos [data-testid="stHorizontalBlock"],
                .st-key-visao_geral_filtros [data-testid="stHorizontalBlock"] {
                    display: grid !important;
                    grid-template-columns: minmax(0, 1fr) !important;
                    gap: 10px !important;
                    width: 100% !important;
                }

                .st-key-vg_kpis_responsivos
                [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
                .st-key-visao_geral_filtros
                [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                    width: 100% !important;
                    max-width: 100% !important;
                    min-width: 0 !important;
                    flex: none !important;
                }
            }
        </style>
        """
    )


def formatar_numero(valor: Any) -> str:
    return f"{int(valor):,}".replace(",", ".")


def formatar_percentual(valor: Optional[float]) -> str:
    if valor is None:
        return "—"
    return f"{float(valor):.1f}".replace(".", ",") + "%"


def formatar_decimal(valor: Optional[float]) -> str:
    if valor is None:
        return "—"
    return f"{float(valor):.1f}".replace(".", ",")


def montar_kpis_visao_geral(indicadores: dict[str, Any]) -> list[tuple[str, str, str]]:
    """
    Constrói os KPIs da Visão Geral separando explicitamente métricas observadas
    de estimativas preditivas provenientes do contrato `/indicadores/gerais`.
    """
    total_est = int(indicadores.get("total_estudantes_distintos") or 0)
    freq_media = indicadores.get("frequencia_media")
    media_geral = indicadores.get("media_geral")
    possui_prev = bool(indicadores.get("possui_previsoes_risco"))
    dist_risco = indicadores.get("distribuicao_faixas_risco") or []

    sub_est = (
        f"{formatar_numero(indicadores.get('total_registros_boletim') or 0)} boletins no recorte (dado observado)"
        if total_est > 0
        else "Aguardando registros escolares no recorte"
    )
    sub_freq = (
        "Média dos boletins importados (dado observado)"
        if freq_media is not None
        else "Sem registros de frequência no recorte"
    )
    sub_media = (
        "Média acadêmica registrada (dado observado)"
        if media_geral is not None
        else "Sem registros de notas no recorte"
    )

    if possui_prev and dist_risco:
        qtd_alto_critico = sum(
            int(item.get("quantidade") or 0)
            for item in dist_risco
            if str(item.get("faixa") or "").upper() in {"ALTO", "CRITICO"}
        )
        m_nome = indicadores.get("modelo_nome_vigente") or "Modelo externo"
        m_ver = indicadores.get("modelo_versao_vigente") or "—"
        valor_risco = formatar_numero(qtd_alto_critico)
        sub_risco = f"Estimativa preditiva (Alto/Crítico) • {m_nome} v{m_ver}"
    else:
        valor_risco = "Sem previsões"
        sub_risco = "Aguardando envio de previsões preditivas"

    return [
        (
            formatar_numero(total_est) if total_est > 0 else "—",
            "Estudantes distintos",
            sub_est,
        ),
        (
            formatar_percentual(freq_media),
            "Frequência média observada",
            sub_freq,
        ),
        (
            formatar_decimal(media_geral),
            "Média geral observada",
            sub_media,
        ),
        (
            valor_risco,
            "Risco elevado (preditivo)",
            sub_risco,
        ),
    ]


def preparar_dados_risco_visao_geral(
    indicadores: dict[str, Any],
) -> tuple[bool, pd.DataFrame, Optional[str]]:
    """
    Extrai a distribuição de faixas de risco somente quando `possui_previsoes_risco` for True.
    Nunca gera faixas fictícias quando não houver previsões reais.
    """
    possui = bool(indicadores.get("possui_previsoes_risco"))
    itens = indicadores.get("distribuicao_faixas_risco") or []
    if not possui or not itens:
        return (
            False,
            pd.DataFrame(columns=["Faixa de risco", "Estudantes", "Percentual (%)"]),
            "Nenhuma previsão de risco foi registrada para o recorte selecionado.",
        )

    linhas = []
    for item in itens:
        faixa_cod = str(item.get("faixa") or "").upper()
        linhas.append(
            {
                "Faixa de risco": ROTULOS_FAIXAS.get(faixa_cod, faixa_cod),
                "Estudantes": int(item.get("quantidade") or 0),
                "Percentual (%)": float(item.get("percentual") or 0.0),
            }
        )
    df_risco = pd.DataFrame(linhas)
    modelo = indicadores.get("modelo_nome_vigente") or "Modelo externo"
    versao = indicadores.get("modelo_versao_vigente") or "—"
    ultima = str(indicadores.get("ultima_previsao_em") or "")[:19].replace("T", " ")
    nota = (
        f"Modelo vigente: {modelo} (versão {versao})"
        + (f" • Última previsão: {ultima} UTC" if ultima else "")
        + ". Estimativa probabilística separada das métricas observadas."
    )
    return True, df_risco, nota


def grafico_vazio(mensagem: str = "Sem dados para o recorte atual"):
    """Mantém o espaço gráfico limpo sem apresentar dados fictícios."""
    figura = go.Figure()
    figura.update_layout(
        height=290,
        margin=dict(l=15, r=15, t=15, b=15),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
        annotations=[
            dict(
                text=mensagem,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(size=13, color="#8792A2"),
            )
        ],
    )
    return figura


def render():
    """Renderiza a página de Visão Geral conectada à API real do Vértice."""

    aplicar_responsividade()
    titulo_pagina("Visão geral")

    if not possui_sessao_api_ativa():
        st.warning(
            "Faça login com sua conta institucional para visualizar os indicadores reais e previsões."
        )
        return

    usuario_api = st.session_state.get("usuario_api") or {}
    if usuario_api.get("papel") == "administrador":
        st.info(
            "O perfil administrativo não acessa dados pedagógicos individuais ou escolares nesta visão. "
            "Para analisar indicadores e previsões de risco, utilize uma conta de gestor ou professor."
        )
        return

    resp_turmas = listar_turmas_api()
    if resp_turmas.sessao_expirada:
        st.warning(resp_turmas.erro or "Sua sessão expirou. Faça login novamente.")
        return
    if resp_turmas.sem_permissao:
        st.error(resp_turmas.erro or "Permissão insuficiente para consultar turmas.")
        return
    if resp_turmas.indisponivel:
        st.error(resp_turmas.erro or "Backend indisponível no momento.")
        return

    turmas = resp_turmas.dados if (resp_turmas.ok and isinstance(resp_turmas.dados, list)) else []
    opcoes_turma: dict[str, Optional[str]] = {"Todas as turmas": None}
    for t in turmas:
        label = f"{t.get('nome', 'Turma')} ({t.get('ano_letivo', '')})".strip()
        opcoes_turma[label] = t.get("id")

    resp_discs = listar_disciplinas_api()
    if resp_discs.sessao_expirada:
        st.warning(resp_discs.erro or "Sua sessão expirou. Faça login novamente.")
        return
    discs = resp_discs.dados if (resp_discs.ok and isinstance(resp_discs.dados, list)) else []
    opcoes_disc: dict[str, Optional[str]] = {"Todas as disciplinas": None}
    for d in discs:
        opcoes_disc[f"{d.get('nome', 'Disciplina')} ({d.get('codigo', '')})".strip()] = d.get("id")

    with st.container(key="visao_geral_filtros"):
        col_turma, col_disc, col_ano, col_periodo, col_versao = st.columns(5)
        with col_turma:
            turma_label = st.selectbox(
                "Turma",
                options=list(opcoes_turma.keys()),
                key="vg_turma_api",
            )
        with col_disc:
            disc_label = st.selectbox(
                "Disciplina",
                options=list(opcoes_disc.keys()),
                key="vg_disc_api",
            )
        with col_ano:
            ano_str = st.text_input(
                "Ano letivo (opcional)",
                value="",
                placeholder="Ex.: 2026",
                key="vg_ano_api",
            )
        with col_periodo:
            periodo_str = st.text_input(
                "Período letivo (opcional)",
                value="",
                placeholder="Ex.: 1º Bimestre",
                key="vg_periodo_api",
            )
        with col_versao:
            versao_str = st.text_input(
                "Versão do modelo (opcional)",
                value="",
                placeholder="Mais recente automática",
                key="vg_versao_api",
            )

    ano_val: Optional[int] = None
    if ano_str.strip().isdigit():
        ano_val = int(ano_str.strip())

    turma_id_sel = opcoes_turma.get(turma_label)
    disc_id_sel = opcoes_disc.get(disc_label)
    resp_ind = consultar_indicadores_gerais_api(
        turma_id=turma_id_sel,
        disciplina_id=disc_id_sel,
        ano_letivo=ano_val,
        periodo_letivo=periodo_str.strip() or None,
        modelo_versao=versao_str.strip() or None,
    )

    if not resp_ind.ok:
        if resp_ind.sessao_expirada:
            st.warning(resp_ind.erro or "Sua sessão expirou. Faça login novamente.")
        elif resp_ind.sem_permissao:
            st.error(resp_ind.erro or "Sem permissão para consultar este recorte.")
        elif resp_ind.indisponivel:
            st.error(resp_ind.erro or "Backend indisponível no momento.")
        else:
            st.warning(resp_ind.erro or "Não foi possível carregar os indicadores gerais.")
        return

    indicadores = resp_ind.dados if isinstance(resp_ind.dados, dict) else {}
    kpis = montar_kpis_visao_geral(indicadores)

    with st.container(key="vg_kpis_responsivos"):
        colunas_kpi = st.columns(4)
        for indice, (valor, titulo, subtitulo) in enumerate(kpis):
            with colunas_kpi[indice]:
                card_kpi(
                    valor,
                    titulo,
                    subtitulo,
                    CORES_KPI[indice],
                )

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    possui_risco, df_risco, nota_risco = preparar_dados_risco_visao_geral(indicadores)
    dist_serie = indicadores.get("distribuicao_por_serie") or []
    evolucao = indicadores.get("evolucao_por_periodo") or []

    with st.container(key="vg_graficos_linha_1"):
        col1, col2 = st.columns(2)

        with col1:
            with card():
                st.subheader("Frequência observada por série")
                if not dist_serie:
                    st.plotly_chart(
                        grafico_vazio("Sem boletins importados neste recorte"),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    df_serie = pd.DataFrame(
                        [
                            {
                                "Série": str(item.get("chave") or "—"),
                                "Frequência média (%)": float(
                                    item.get("frequencia_media") or 0.0
                                ),
                            }
                            for item in dist_serie
                        ]
                    )
                    st.plotly_chart(
                        grafico_barras_horizontais(
                            df_serie,
                            "Série",
                            "Frequência média (%)",
                        ),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )

        with col2:
            with card():
                st.subheader("Distribuição preditiva de risco")
                if not possui_risco:
                    st.info(nota_risco or "Aguardando previsões de risco.")
                    st.plotly_chart(
                        grafico_vazio("Nenhuma previsão preditiva disponível"),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    st.plotly_chart(
                        grafico_rosca(
                            df_risco,
                            "Faixa de risco",
                            "Estudantes",
                            {
                                "Baixo": "#10B981",
                                "Moderado": "#F59E0B",
                                "Alto": "#EF4444",
                                "Crítico": "#7F1D1D",
                            },
                        ),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                    if nota_risco:
                        st.caption(nota_risco)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    with st.container(key="vg_graficos_linha_2"):
        col3, col4 = st.columns(2)

        with col3:
            with card():
                st.subheader("Média observada por série")
                if not dist_serie:
                    st.plotly_chart(
                        grafico_vazio("Sem dados observados por série"),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    df_notas_serie = pd.DataFrame(
                        [
                            {
                                "Série": str(item.get("chave") or "—"),
                                "Média geral": float(item.get("media_geral") or 0.0),
                            }
                            for item in dist_serie
                        ]
                    )
                    st.plotly_chart(
                        grafico_barras_horizontais(
                            df_notas_serie,
                            "Série",
                            "Média geral",
                        ),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )

        with col4:
            with card():
                st.subheader("Evolução longitudinal observada")
                if not evolucao:
                    st.plotly_chart(
                        grafico_vazio("Sem períodos letivos consolidados"),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    df_evol = pd.DataFrame(
                        [
                            {
                                "Período": f"{ev.get('ano_letivo')} • {ev.get('periodo_letivo')}",
                                "Estudantes": int(ev.get("total_estudantes") or 0),
                                "Frequência média (%)": ev.get("frequencia_media"),
                                "Média geral": ev.get("media_geral"),
                            }
                            for ev in evolucao
                        ]
                    )
                    st.dataframe(df_evol, use_container_width=True, hide_index=True)

    if possui_risco:
        resp_prev = listar_previsoes_api(
            turma_id=turma_id_sel,
            disciplina_id=disc_id_sel,
            ano_letivo=ano_val,
            periodo_letivo=periodo_str.strip() or None,
            modelo_versao=versao_str.strip() or None,
            limit=100,
        )
        if resp_prev.ok and isinstance(resp_prev.dados, list):
            prioridade = [
                p
                for p in resp_prev.dados
                if str(p.get("faixa_risco") or "").upper() in {"ALTO", "CRITICO"}
            ]
            st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
            with card():
                st.subheader("Estudantes com estimativa preditiva de risco elevado")
                st.caption(
                    "Lista anonimizada de apoio preventivo. Não constitui diagnóstico definitivo."
                )
                if not prioridade:
                    st.info("Nenhum estudante em faixa Alto ou Crítico neste recorte.")
                else:
                    df_prio = pd.DataFrame(
                        [
                            {
                                "ID anonimizado": p.get("codigo_anonimo") or str(p.get("estudante_id")),
                                "Turma": p.get("turma_nome") or "—",
                                "Período": f"{p.get('ano_letivo')} • {p.get('periodo_letivo')}",
                                "Faixa preditiva": ROTULOS_FAIXAS.get(
                                    str(p.get("faixa_risco") or "").upper(),
                                    p.get("faixa_risco"),
                                ),
                                "Pontuação": round(float(p.get("pontuacao_risco") or 0.0), 3),
                                "Modelo/Versão": f"{p.get('modelo_nome')} v{p.get('modelo_versao')}",
                            }
                            for p in prioridade[:15]
                        ]
                    )
                    st.dataframe(df_prio, use_container_width=True, hide_index=True)
