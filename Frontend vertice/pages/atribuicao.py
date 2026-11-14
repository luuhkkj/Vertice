
"""Tela: Atribuição de Turmas aos Professores (integrada ao backend real)."""

from typing import Any, Optional

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from data.api_client import (
    criar_atribuicao_api,
    listar_atribuicoes_api,
    listar_disciplinas_api,
    listar_escolas_api,
    listar_turmas_api,
    listar_usuarios_api,
    possui_sessao_api_ativa,
    remover_atribuicao_api,
)


COLUNAS_TABELA = [
    "Professor",
    "Disciplina",
    "Turma",
    "Escola",
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


def _papel_atual() -> str:
    usuario = st.session_state.get("usuario_api") or {}
    return str(
        usuario.get("papel")
        or st.session_state.get("papel_api")
        or st.session_state.get("perfil")
        or "professor"
    ).strip().lower()


def carregar_contexto_atribuicoes_api() -> dict[str, Any]:
    """Carrega docentes, turmas, disciplinas, escolas e atribuições da API real."""
    contexto: dict[str, Any] = {
        "conectado": False,
        "sessao_expirada": False,
        "sem_permissao": False,
        "erro": None,
        "papel": _papel_atual(),
        "professores": [],
        "turmas": [],
        "disciplinas": [],
        "escolas": [],
        "atribuicoes": [],
    }
    if not possui_sessao_api_ativa():
        contexto["erro"] = "Sessão API não autenticada."
        return contexto

    resp_atrib = listar_atribuicoes_api()
    if resp_atrib.sessao_expirada:
        contexto["sessao_expirada"] = True
        contexto["erro"] = resp_atrib.erro
        return contexto
    if not resp_atrib.ok:
        if resp_atrib.sem_permissao:
            contexto["sem_permissao"] = True
        contexto["erro"] = resp_atrib.erro
        return contexto

    resp_turmas = listar_turmas_api()
    resp_discs = listar_disciplinas_api()
    resp_escolas = listar_escolas_api()

    for r in (resp_turmas, resp_discs, resp_escolas):
        if r.sessao_expirada:
            contexto["sessao_expirada"] = True
            contexto["erro"] = r.erro
            return contexto

    contexto["atribuicoes"] = resp_atrib.dados if isinstance(resp_atrib.dados, list) else []
    contexto["turmas"] = (
        [t for t in resp_turmas.dados if isinstance(t, dict) and t.get("ativo", True)]
        if resp_turmas.ok and isinstance(resp_turmas.dados, list)
        else []
    )
    contexto["disciplinas"] = (
        [d for d in resp_discs.dados if isinstance(d, dict) and d.get("ativo", True)]
        if resp_discs.ok and isinstance(resp_discs.dados, list)
        else []
    )
    contexto["escolas"] = (
        [e for e in resp_escolas.dados if isinstance(e, dict) and e.get("ativo", True)]
        if resp_escolas.ok and isinstance(resp_escolas.dados, list)
        else []
    )

    if contexto["papel"] in ("administrador", "gestor"):
        resp_users = listar_usuarios_api(limit=200, papel="professor", apenas_ativos=True)
        if resp_users.sessao_expirada:
            contexto["sessao_expirada"] = True
            contexto["erro"] = resp_users.erro
            return contexto
        if resp_users.sem_permissao:
            contexto["sem_permissao"] = True
            contexto["erro"] = resp_users.erro
            return contexto
        if not resp_users.ok:
            contexto["erro"] = resp_users.erro
            return contexto
        usuarios = resp_users.dados if isinstance(resp_users.dados, list) else []
        contexto["professores"] = [
            u
            for u in usuarios
            if isinstance(u, dict)
            and str(u.get("papel", "")).lower() == "professor"
            and bool(u.get("ativo", True))
        ]

    contexto["conectado"] = True
    return contexto


def _formatar_linhas_atribuicoes(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    profs = {str(p["id"]): p for p in ctx["professores"] if p.get("id")}
    turmas = {str(t["id"]): t for t in ctx["turmas"] if t.get("id")}
    discs = {str(d["id"]): d for d in ctx["disciplinas"] if d.get("id")}
    escolas = {str(e["id"]): e for e in ctx["escolas"] if e.get("id")}

    linhas = []
    for atrib in ctx["atribuicoes"]:
        if not isinstance(atrib, dict):
            continue
        pid = str(atrib.get("professor_id") or "")
        tid = str(atrib.get("turma_id") or "")
        did = str(atrib.get("disciplina_id") or "")

        prof = profs.get(pid, {})
        turma = turmas.get(tid, {})
        disc = discs.get(did, {})
        escola = escolas.get(str(turma.get("escola_id") or ""), {})

        linhas.append(
            {
                "id": str(atrib.get("id") or ""),
                "professor_id": pid,
                "Professor": prof.get("nome") or prof.get("email") or pid,
                "Disciplina": (
                    f"{disc.get('nome')} ({disc.get('codigo')})"
                    if disc.get("nome")
                    else "Todas / Polivalente"
                ),
                "Turma": (
                    f"{turma.get('nome')} ({turma.get('serie')} • {turma.get('ano_letivo')})"
                    if turma.get("nome")
                    else tid
                ),
                "Escola": escola.get("nome") or "—",
            }
        )
    return linhas


def _render_painel_administrador(ctx: dict[str, Any]) -> None:
    """Visão complementar de entidades estruturais acessíveis ao Administrador."""
    with st.expander("Resumo estrutural da rede (Escolas, Turmas e Disciplinas)", expanded=False):
        c1, c2, c3 = st.columns(3)
        c1.metric("Escolas ativas", len(ctx["escolas"]))
        c2.metric("Turmas ativas", len(ctx["turmas"]))
        c3.metric("Disciplinas ativas", len(ctx["disciplinas"]))
        if ctx["escolas"]:
            st.caption("Escolas cadastradas")
            st.dataframe(
                pd.DataFrame(
                    [{"Nome": e.get("nome"), "Código": e.get("codigo")} for e in ctx["escolas"]]
                ),
                hide_index=True,
                width="stretch",
            )


def _formulario(
    opcoes_prof: dict[str, str],
    opcoes_turma: dict[str, str],
    opcoes_disc: dict[str, Optional[str]],
) -> None:
    """Formulário para cadastrar vínculos reais via API."""
    with st.container(key="atribuicao_formulario"):
        st.markdown("### Nova atribuição")
        st.caption("Selecione o professor ativo, a disciplina e a turma.")

        rotulos_prof = list(opcoes_prof.keys())
        rotulos_turma = list(opcoes_turma.keys())
        rotulos_disc = ["Todas / Polivalente (sem disciplina fixa)"] + list(opcoes_disc.keys())

        prof_sel = st.selectbox(
            "Professor",
            rotulos_prof,
            index=None,
            placeholder="Selecione o professor...",
            key="at_professor_label",
        )
        disc_sel = st.selectbox(
            "Disciplina",
            rotulos_disc,
            index=0,
            key="at_disciplina_label",
        )
        turma_sel = st.selectbox(
            "Turma",
            rotulos_turma,
            index=None,
            placeholder="Selecione a turma...",
            key="at_turma_label",
        )

        if st.button(
            "Atribuir turma",
            type="primary",
            key="btn_atribuir_turma",
            use_container_width=True,
        ):
            if not prof_sel or not turma_sel:
                st.error("Selecione o professor e a turma antes de confirmar.")
                return

            resp = criar_atribuicao_api(
                professor_id=opcoes_prof[prof_sel],
                turma_id=opcoes_turma[turma_sel],
                disciplina_id=opcoes_disc.get(disc_sel),
            )
            if resp.ok:
                st.session_state["at_aviso"] = (
                    "sucesso",
                    f"Atribuição criada para {prof_sel} na turma {turma_sel}.",
                )
                st.rerun()
            else:
                st.error(resp.erro or "Não foi possível criar a atribuição.")


def _tabela_atribuicoes(
    linhas: list[dict[str, Any]],
    professor_id_filtro: Optional[str],
    professor_rotulo: Optional[str],
) -> None:
    """Exibe vínculos existentes e permite remoção autorizada via API."""
    with st.container(key="atribuicao_tabela"):
        st.markdown("### Atribuições cadastradas")

        exibidas = (
            [linha for linha in linhas if linha["professor_id"] == professor_id_filtro]
            if professor_id_filtro
            else linhas
        )
        if professor_rotulo:
            st.caption(f"Filtrando por: {professor_rotulo}")
        else:
            st.caption("Exibindo todas as atribuições visíveis no seu escopo.")

        df_exibir = (
            pd.DataFrame(exibidas)[COLUNAS_TABELA]
            if exibidas
            else pd.DataFrame(columns=COLUNAS_TABELA)
        )
        st.dataframe(df_exibir, hide_index=True, width="stretch")

        if not exibidas:
            st.info("Nenhuma atribuição encontrada neste recorte.")
            return

        mapa_remocao = {
            f"{item['Professor']} • {item['Disciplina']} • {item['Turma']}": item["id"]
            for item in exibidas
            if item.get("id")
        }
        escolha_rem = st.selectbox(
            "Selecione uma atribuição para remover",
            list(mapa_remocao.keys()),
            index=None,
            placeholder="Escolha uma atribuição...",
            key="at_remover_label",
        )
        if st.button(
            "Remover atribuição",
            key="btn_remover_atribuicao",
            use_container_width=True,
        ):
            if not escolha_rem:
                st.error("Selecione uma atribuição para remover.")
                return
            resp_del = remover_atribuicao_api(mapa_remocao[escolha_rem])
            if resp_del.ok:
                st.session_state["at_aviso"] = (
                    "sucesso",
                    "Atribuição removida com sucesso.",
                )
                st.rerun()
            else:
                st.error(resp_del.erro or "Não foi possível remover a atribuição.")


def render():
    """Renderiza a página de atribuição integrada ao backend."""
    aplicar_responsividade()

    if not st.session_state.get("logado"):
        st.error("É necessário autenticar-se para acessar esta tela.")
        return

    papel = _papel_atual()
    if papel not in ("administrador", "gestor"):
        st.error(
            "Permissão insuficiente: apenas Administrador ou Gestor Escolar podem gerenciar atribuições."
        )
        return

    titulo_pagina(
        "Atribuição de Turmas aos Professores",
        "Gerencie vínculos reais entre professores, disciplinas e turmas respeitando o escopo escolar.",
    )

    aviso = st.session_state.pop("at_aviso", None)
    if aviso:
        tipo, mensagem = aviso
        if tipo == "sucesso":
            st.success(mensagem)
        else:
            st.error(mensagem)

    ctx = carregar_contexto_atribuicoes_api()
    if ctx["sessao_expirada"]:
        st.warning(ctx["erro"] or "Sua sessão expirou. Faça login novamente.")
        return
    if ctx["sem_permissao"]:
        st.error(ctx["erro"] or "Permissão insuficiente para gerenciar atribuições.")
        return
    if not ctx["conectado"]:
        st.error(ctx["erro"] or "Não foi possível carregar os dados de atribuição do servidor.")
        return

    if papel == "administrador":
        _render_painel_administrador(ctx)

    escolas_por_id = {str(e["id"]): e.get("nome", "") for e in ctx["escolas"] if e.get("id")}
    opcoes_prof = {
        f"{p.get('nome')} ({p.get('email')})": str(p["id"])
        for p in ctx["professores"]
        if p.get("id")
    }
    opcoes_turma: dict[str, str] = {}
    for t in ctx["turmas"]:
        if not t.get("id"):
            continue
        escola_nome = escolas_por_id.get(str(t.get("escola_id") or ""), "")
        sufixo_escola = f" — {escola_nome}" if escola_nome else ""
        rotulo_t = (
            f"{t.get('nome')} ({t.get('serie')} • {t.get('turno')} • {t.get('ano_letivo')}){sufixo_escola}"
        )
        opcoes_turma[rotulo_t] = str(t["id"])

    opcoes_disc: dict[str, Optional[str]] = {
        f"{d.get('nome')} ({d.get('codigo')})": str(d["id"])
        for d in ctx["disciplinas"]
        if d.get("id")
    }

    if not opcoes_prof or not opcoes_turma:
        st.warning(
            "É necessário possuir pelo menos um professor ativo e uma turma ativa no seu escopo para criar atribuições."
        )

    linhas = _formatar_linhas_atribuicoes(ctx)
    prof_sel_atual = st.session_state.get("at_professor_label")
    prof_id_filtro = opcoes_prof.get(prof_sel_atual) if prof_sel_atual else None

    with st.container(key="atribuicao_paineis"):
        col_formulario, col_tabela = st.columns(
            [1, 1.7],
            gap="large",
            vertical_alignment="top",
        )
        with col_formulario:
            _formulario(opcoes_prof, opcoes_turma, opcoes_disc)
        with col_tabela:
            _tabela_atribuicoes(linhas, prof_id_filtro, prof_sel_atual)
