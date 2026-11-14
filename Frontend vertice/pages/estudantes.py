"""Tela de Estudantes integrada à API real e histórico preditivo (Fase 7)."""

from typing import Any, Optional

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from components.tabelas import tabela_paginada
from data.api_client import (
    consultar_previsoes_estudante_api,
    listar_estudantes_api,
    listar_previsoes_api,
    listar_turmas_api,
    obter_estudante_historico_api,
    possui_sessao_api_ativa,
)


ROTULOS_FAIXAS = {
    "BAIXO": "Baixo",
    "MODERADO": "Moderado",
    "ALTO": "Alto",
    "CRITICO": "Crítico",
}


def aplicar_responsividade():
    """Adapta os filtros e a tabela em telas menores."""

    st.html(
        """
        <style>
            .st-key-estudantes_filtros,
            .st-key-estudantes_resumo,
            .st-key-estudantes_tabela {
                width: 100%;
                max-width: 100%;
                min-width: 0;
                box-sizing: border-box;
            }

            .st-key-estudantes_filtros [data-testid="stColumn"],
            .st-key-estudantes_resumo [data-testid="stColumn"] {
                min-width: 0 !important;
            }

            .st-key-estudantes_tabela {
                overflow-x: auto;
                overflow-y: visible;
            }
        </style>
        """
    )


def montar_tabela_estudantes_com_risco(
    estudantes: list[dict[str, Any]],
    previsoes: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    Combina estudantes anonimizados reais com sua previsão de risco mais recente,
    preservando rigorosamente ausência de previsões quando ainda não existirem.
    """
    ultima_por_est: dict[str, dict[str, Any]] = {}
    for prev in sorted(
        previsoes,
        key=lambda x: str(x.get("gerado_em") or ""),
        reverse=True,
    ):
        est_id = str(prev.get("estudante_id") or "")
        if est_id and est_id not in ultima_por_est:
            ultima_por_est[est_id] = prev

    linhas = []
    for est in estudantes:
        est_id = str(est.get("id") or "")
        prev = ultima_por_est.get(est_id)
        faixa_cod = str(prev.get("faixa_risco") or "").upper() if prev else ""
        linhas.append(
            {
                "estudante_id": est_id,
                "Código anonimizado": est.get("codigo_anonimo") or est_id,
                "Situação cadastral": "Ativo" if est.get("ativo", True) else "Inativo",
                "Reprovações históricas": int(est.get("historico_reprovacoes") or 0),
                "Faixa preditiva": (
                    ROTULOS_FAIXAS.get(faixa_cod, faixa_cod)
                    if prev
                    else "Sem previsão"
                ),
                "Pontuação risco": (
                    f"{float(prev.get('pontuacao_risco') or 0.0):.3f}"
                    if prev
                    else "—"
                ),
                "Modelo preditivo": (
                    f"{prev.get('modelo_nome')} v{prev.get('modelo_versao')}"
                    if prev
                    else "—"
                ),
                "Data da previsão": (
                    str(prev.get("gerado_em") or "")[:19].replace("T", " ")
                    if prev
                    else "—"
                ),
            }
        )

    colunas = [
        "estudante_id",
        "Código anonimizado",
        "Situação cadastral",
        "Reprovações históricas",
        "Faixa preditiva",
        "Pontuação risco",
        "Modelo preditivo",
        "Data da previsão",
    ]
    return pd.DataFrame(linhas, columns=colunas)


def filtrar_tabela_estudantes(
    df: pd.DataFrame,
    busca: str = "",
    faixa_risco: str = "Todas",
) -> pd.DataFrame:
    """Aplica filtro local por código anonimizado e faixa de risco."""
    if df.empty:
        return df
    filtrado = df.copy()
    if busca.strip():
        filtrado = filtrado[
            filtrado["Código anonimizado"]
            .astype(str)
            .str.contains(busca.strip(), case=False, regex=False, na=False)
        ]
    if faixa_risco and faixa_risco != "Todas":
        filtrado = filtrado[filtrado["Faixa preditiva"] == faixa_risco]
    return filtrado


def render():
    """Renderiza a página de Estudantes com dados reais do backend."""

    aplicar_responsividade()
    titulo_pagina("Estudantes")

    if not possui_sessao_api_ativa():
        st.warning(
            "Autentique-se para consultar estudantes anonimizados, boletins e previsões."
        )
        return

    usuario_api = st.session_state.get("usuario_api") or {}
    if usuario_api.get("papel") == "administrador":
        st.info(
            "Perfis administrativos não possuem acesso pedagógico aos dados individuais de estudantes."
        )
        return

    resp_turmas = listar_turmas_api()
    turmas = resp_turmas.dados if (resp_turmas.ok and isinstance(resp_turmas.dados, list)) else []
    opcoes_turma: dict[str, Optional[str]] = {"Todas as turmas": None}
    for t in turmas:
        opcoes_turma[f"{t.get('nome', 'Turma')} ({t.get('ano_letivo', '')})".strip()] = t.get("id")

    with st.container(key="estudantes_filtros"):
        c1, c2, c3, c4 = st.columns([2, 2, 1.5, 1.5])
        with c1:
            busca = st.text_input(
                "Buscar por código anonimizado",
                placeholder="Ex.: EST-001",
                key="est_busca_api",
            )
        with c2:
            turma_label = st.selectbox(
                "Turma",
                options=list(opcoes_turma.keys()),
                key="est_turma_api",
            )
        with c3:
            faixa_sel = st.selectbox(
                "Faixa preditiva",
                options=["Todas", "Baixo", "Moderado", "Alto", "Crítico", "Sem previsão"],
                key="est_faixa_api",
            )
        with c4:
            ano_txt = st.text_input(
                "Ano letivo",
                value="",
                placeholder="Ex.: 2025",
                key="est_ano_api",
            )

    ano_val = int(ano_txt.strip()) if ano_txt.strip().isdigit() else None
    turma_id_sel = opcoes_turma.get(turma_label)

    resp_est = listar_estudantes_api(
        turma_id=turma_id_sel,
        ano_letivo=ano_val,
        limit=200,
    )
    if not resp_est.ok:
        st.error(resp_est.erro or "Erro ao consultar estudantes no servidor.")
        return

    estudantes = resp_est.dados if isinstance(resp_est.dados, list) else []
    resp_prev = listar_previsoes_api(
        turma_id=turma_id_sel,
        ano_letivo=ano_val,
        limit=500,
    )
    previsoes = resp_prev.dados if (resp_prev.ok and isinstance(resp_prev.dados, list)) else []

    df_completo = montar_tabela_estudantes_com_risco(estudantes, previsoes)
    df_filtrado = filtrar_tabela_estudantes(
        df_completo,
        busca=busca,
        faixa_risco=faixa_sel,
    )

    df_exibicao = df_filtrado.drop(columns=["estudante_id"], errors="ignore")

    with st.container(key="estudantes_resumo"):
        col_info, col_dl = st.columns([3, 1])
        with col_info:
            st.caption(
                f"{len(df_exibicao)} estudante(s) anonimizado(s) no recorte autorizado • "
                "Previsões exibidas separadamente de dados observados."
            )
        with col_dl:
            csv_bytes = df_exibicao.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Exportar CSV",
                data=csv_bytes,
                file_name="estudantes_vertice.csv",
                mime="text/csv",
                disabled=df_exibicao.empty,
            )

    with st.container(key="estudantes_tabela"):
        if df_exibicao.empty:
            st.info("Nenhum estudante encontrado para os filtros selecionados.")
        else:
            tabela_paginada(
                df_exibicao,
                tamanho_pagina=10,
                chave="est_tabela_api",
                reiniciar_quando=(busca, turma_label, faixa_sel, ano_txt),
            )

    if not df_filtrado.empty:
        st.divider()
        st.subheader("Detalhe longitudinal e histórico preditivo do estudante")
        mapa_est = {
            f"{row['Código anonimizado']}": row["estudante_id"]
            for _, row in df_filtrado.iterrows()
        }
        codigo_sel = st.selectbox(
            "Selecionar estudante para detalhamento",
            options=list(mapa_est.keys()),
            key="est_detalhe_select",
        )
        est_id_sel = mapa_est.get(codigo_sel)
        if est_id_sel:
            col_obs, col_pred = st.columns(2)
            with col_obs:
                st.markdown("**Histórico escolar observado (anonimizado)**")
                resp_hist = obter_estudante_historico_api(est_id_sel)
                if resp_hist.ok and isinstance(resp_hist.dados, dict):
                    boletins = resp_hist.dados.get("boletins") or []
                    if not boletins:
                        st.info("Sem boletins registrados para este estudante.")
                    else:
                        df_bol = pd.DataFrame(
                            [
                                {
                                    "Ano": b.get("ano_letivo"),
                                    "Período": b.get("periodo_letivo"),
                                    "Turma": b.get("turma_nome") or "—",
                                    "Frequência (%)": b.get("frequencia_percentual"),
                                    "Média geral": b.get("media_geral"),
                                    "Faltas": b.get("faltas"),
                                }
                                for b in boletins
                            ]
                        )
                        st.dataframe(df_bol, use_container_width=True, hide_index=True)
                else:
                    st.warning(resp_hist.erro or "Não foi possível carregar o histórico.")

            with col_pred:
                st.markdown("**Histórico de previsões de risco (append-only)**")
                resp_prev_est = consultar_previsoes_estudante_api(est_id_sel)
                if resp_prev_est.ok and isinstance(resp_prev_est.dados, dict):
                    hist_prev = resp_prev_est.dados.get("historico") or []
                    if not hist_prev:
                        st.info(
                            "Nenhuma previsão preditiva registrada até o momento para este estudante."
                        )
                    else:
                        df_hp = pd.DataFrame(
                            [
                                {
                                    "Gerado em": str(p.get("gerado_em") or "")[:19].replace("T", " "),
                                    "Tipo": p.get("tipo_previsao"),
                                    "Faixa": ROTULOS_FAIXAS.get(
                                        str(p.get("faixa_risco") or "").upper(),
                                        p.get("faixa_risco"),
                                    ),
                                    "Pontuação": round(float(p.get("pontuacao_risco") or 0.0), 3),
                                    "Modelo/Versão": f"{p.get('modelo_nome')} v{p.get('modelo_versao')}",
                                }
                                for p in hist_prev
                            ]
                        )
                        st.dataframe(df_hp, use_container_width=True, hide_index=True)
                        aviso = resp_prev_est.dados.get("aviso_metodologico")
                        if aviso:
                            st.caption(aviso)
                else:
                    st.warning(
                        resp_prev_est.erro or "Não foi possível consultar previsões do estudante."
                    )
