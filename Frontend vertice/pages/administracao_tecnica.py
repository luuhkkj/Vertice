"""Tela: Administração Técnica da Plataforma (exclusiva para o papel Administrador)."""

from typing import Any, Callable, Optional

import pandas as pd
import streamlit as st

from components.cards import card, card_kpi
from components.layout import titulo_pagina
from data.api_client import (
    atualizar_disciplina_api,
    atualizar_escola_api,
    atualizar_turma_api,
    atualizar_usuario_api,
    consultar_resumo_operacional_admin_api,
    criar_credencial_ml_api,
    criar_disciplina_api,
    criar_escola_api,
    criar_turma_api,
    criar_usuario_api,
    listar_auditoria_ia_api,
    listar_auditoria_tecnica_api,
    listar_credenciais_ml_api,
    listar_disciplinas_api,
    listar_escolas_api,
    listar_modelos_ml_disponiveis_api,
    listar_turmas_api,
    listar_usuarios_api,
    possui_sessao_api_ativa,
    revogar_credencial_ml_api,
)

_OPCOES_PAPEIS = {
    "Administrador (administrador)": "administrador",
    "Gestor/Coordenador (gestor)": "gestor",
    "Professor (professor)": "professor",
}
_ROTULOS_PAPEIS = {v: k for k, v in _OPCOES_PAPEIS.items()}


def _papel_atual() -> str:
    usuario_api = st.session_state.get("usuario_api")
    if isinstance(usuario_api, dict) and usuario_api.get("papel"):
        return str(usuario_api["papel"]).strip().lower()
    return str(
        st.session_state.get("papel_api")
        or st.session_state.get("perfil")
        or ""
    ).strip().lower()


def carregar_contexto_admin_tecnico_api() -> dict[str, Any]:
    """Carrega inventário operacional, cadastros estruturais, credenciais e auditorias via backend."""
    estado: dict[str, Any] = {
        "conectado": False,
        "sessao_expirada": False,
        "sem_permissao": False,
        "erro": None,
        "resumo": {},
        "usuarios": [],
        "escolas": [],
        "turmas": [],
        "disciplinas": [],
        "credenciais": [],
        "modelos_ml": [],
        "auditoria_tecnica": [],
        "auditoria_ia": [],
    }
    if not possui_sessao_api_ativa():
        estado["erro"] = "Sessão API não autenticada."
        return estado

    resp_resumo = consultar_resumo_operacional_admin_api()
    if resp_resumo.sessao_expirada:
        estado["sessao_expirada"] = True
        estado["erro"] = resp_resumo.erro
        return estado
    if resp_resumo.sem_permissao:
        estado["sem_permissao"] = True
        estado["erro"] = resp_resumo.erro
        return estado
    if not resp_resumo.ok:
        estado["erro"] = resp_resumo.erro or "Não foi possível carregar o painel técnico."
        return estado

    estado["resumo"] = resp_resumo.dados if isinstance(resp_resumo.dados, dict) else {}

    chamadas = [
        ("usuarios", listar_usuarios_api(limit=200)),
        ("escolas", listar_escolas_api(limit=200)),
        ("turmas", listar_turmas_api()),
        ("disciplinas", listar_disciplinas_api()),
        ("credenciais", listar_credenciais_ml_api()),
        ("modelos_ml", listar_modelos_ml_disponiveis_api()),
        ("auditoria_tecnica", listar_auditoria_tecnica_api(limit=100)),
        ("auditoria_ia", listar_auditoria_ia_api(limit=100)),
    ]
    for chave, resp in chamadas:
        if resp.sessao_expirada:
            estado["sessao_expirada"] = True
            estado["erro"] = resp.erro
            return estado
        if resp.sem_permissao:
            estado["sem_permissao"] = True
            estado["erro"] = resp.erro
            return estado
        if resp.ok and isinstance(resp.dados, list):
            estado[chave] = resp.dados

    estado["conectado"] = True
    return estado


def _render_kpis(resumo: dict[str, Any]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        card_kpi(
            f"{resumo.get('usuarios_ativos', 0)}/{resumo.get('total_usuarios', 0)}",
            "Usuários ativos",
            rodape="Contas administrativas, gestoras e docentes",
            cor="azul",
            chave="adm_usuarios",
        )
    with c2:
        card_kpi(
            f"{resumo.get('escolas_ativas', 0)}/{resumo.get('total_escolas', 0)}",
            "Escolas ativas",
            rodape="Unidades cadastradas na rede",
            cor="azul_medio",
            chave="adm_escolas",
        )
    with c3:
        card_kpi(
            f"{resumo.get('turmas_ativas', 0)} / {resumo.get('disciplinas_ativas', 0)}",
            "Turmas e disciplinas ativas",
            rodape="Registros estruturais em operação",
            cor="roxo",
            chave="adm_estrutura",
        )
    with c4:
        card_kpi(
            f"{resumo.get('credenciais_ml_ativas', 0)}/{resumo.get('total_credenciais_ml', 0)}",
            "Credenciais ML ativas",
            rodape=f"Eventos técnicos: {resumo.get('total_eventos_auditoria_tecnica', 0)}",
            cor="verde",
            chave="adm_credenciais",
        )


def _render_pagina_usuarios(ctx: dict[str, Any]) -> None:
    escolas = ctx["escolas"]
    escolas_por_id = {str(e["id"]): f"{e.get('nome')} ({e.get('codigo')})" for e in escolas if e.get("id")}
    opcoes_escola: dict[str, Optional[str]] = {"Sem vínculo escolar (global / multi-escola)": None}
    for e in escolas:
        if e.get("id"):
            opcoes_escola[f"{e.get('nome')} ({e.get('codigo')})"] = str(e["id"])

    col_esq, col_dir = st.columns([1.4, 1], gap="large")
    with col_esq:
        with card("Contas cadastradas na plataforma", chave="adm_lista_usuarios"):
            usuarios = ctx["usuarios"]
            if not usuarios:
                st.info("Nenhum usuário listado.")
            else:
                df = pd.DataFrame(
                    [
                        {
                            "Nome": u.get("nome"),
                            "E-mail": u.get("email"),
                            "Papel": _ROTULOS_PAPEIS.get(str(u.get("papel")), str(u.get("papel"))),
                            "Escola": escolas_por_id.get(str(u.get("escola_id") or ""), "—"),
                            "Ativo": "Sim" if u.get("ativo") else "Não",
                        }
                        for u in usuarios
                    ]
                )
                st.dataframe(df, hide_index=True, width="stretch")

    with col_dir:
        with card("Criar nova conta de usuário", chave="adm_criar_usuario"):
            with st.form("form_adm_criar_usuario", clear_on_submit=True):
                nome = st.text_input("Nome completo", key="adm_cu_nome")
                email = st.text_input("E-mail institucional", key="adm_cu_email")
                senha = st.text_input("Senha inicial", type="password", key="adm_cu_senha")
                papel_lbl = st.selectbox("Papel canônico", list(_OPCOES_PAPEIS.keys()), key="adm_cu_papel")
                esc_lbl = st.selectbox("Escola vinculada", list(opcoes_escola.keys()), key="adm_cu_escola")
                ativo = st.checkbox("Conta ativa", value=True, key="adm_cu_ativo")
                if st.form_submit_button("Criar usuário", type="primary", width="stretch"):
                    papel_val = _OPCOES_PAPEIS[papel_lbl]
                    escola_val = opcoes_escola[esc_lbl]
                    if not nome.strip() or not email.strip() or len(senha) < 8:
                        st.warning("Informe nome, e-mail válido e senha com ao menos 8 caracteres.")
                    elif papel_val == "gestor" and not escola_val:
                        st.warning("Perfis Gestor/Coordenador devem possuir uma escola vinculada.")
                    else:
                        resp = criar_usuario_api(
                            nome=nome,
                            email=email,
                            senha=senha,
                            papel=papel_val,
                            escola_id=escola_val,
                            ativo=ativo,
                        )
                        if resp.ok:
                            st.session_state["adm_aviso"] = ("sucesso", "Usuário criado e auditado com sucesso.")
                            st.rerun()
                        else:
                            st.error(resp.erro or "Falha ao criar usuário.")

        if ctx["usuarios"]:
            with card("Atualizar usuário existente", chave="adm_editar_usuario"):
                mapa_users = {
                    f"{u.get('nome')} ({u.get('email')})": u
                    for u in ctx["usuarios"]
                    if u.get("id")
                }
                u_sel = st.selectbox("Selecionar usuário", list(mapa_users.keys()), key="adm_eu_sel")
                u_obj = mapa_users[u_sel]
                with st.form("form_adm_editar_usuario"):
                    eu_nome = st.text_input("Nome", value=str(u_obj.get("nome") or ""), key="adm_eu_nome")
                    papel_atual = str(u_obj.get("papel") or "professor")
                    idx_papel = list(_OPCOES_PAPEIS.values()).index(papel_atual) if papel_atual in _OPCOES_PAPEIS.values() else 2
                    eu_papel_lbl = st.selectbox(
                        "Papel",
                        list(_OPCOES_PAPEIS.keys()),
                        index=idx_papel,
                        key="adm_eu_papel",
                    )
                    escola_atual = str(u_obj.get("escola_id") or "")
                    chaves_esc = list(opcoes_escola.keys())
                    idx_esc = next(
                        (i for i, k in enumerate(chaves_esc) if (opcoes_escola[k] or "") == escola_atual),
                        0,
                    )
                    eu_esc_lbl = st.selectbox(
                        "Escola vinculada",
                        chaves_esc,
                        index=idx_esc,
                        key="adm_eu_escola",
                    )
                    eu_ativo = st.checkbox("Conta ativa", value=bool(u_obj.get("ativo", True)), key="adm_eu_ativo")
                    eu_senha = st.text_input(
                        "Nova senha (opcional)",
                        type="password",
                        key="adm_eu_senha",
                    )
                    if st.form_submit_button("Salvar alterações", width="stretch"):
                        papel_novo = _OPCOES_PAPEIS[eu_papel_lbl]
                        esc_novo = opcoes_escola[eu_esc_lbl]
                        if papel_novo == "gestor" and not esc_novo:
                            st.warning("Perfis Gestor/Coordenador devem permanecer vinculados a uma escola.")
                        else:
                            resp = atualizar_usuario_api(
                                str(u_obj["id"]),
                                nome=eu_nome,
                                senha=eu_senha or None,
                                papel=papel_novo,
                                escola_id=esc_novo,
                                atualizar_escola=True,
                                ativo=eu_ativo,
                            )
                            if resp.ok:
                                st.session_state["adm_aviso"] = ("sucesso", "Usuário atualizado e auditado.")
                                st.rerun()
                            else:
                                st.error(resp.erro or "Falha ao atualizar usuário.")


def _render_pagina_estrutura(ctx: dict[str, Any]) -> None:
    escolas = ctx["escolas"]
    escolas_opcoes = {
        f"{e.get('nome')} ({e.get('codigo')})": str(e["id"])
        for e in escolas
        if e.get("id")
    }
    escolas_nome_por_id = {str(e["id"]): e.get("nome") for e in escolas if e.get("id")}

    c_esc, c_tur, c_dis = st.columns(3, gap="medium")

    with c_esc:
        with card("Unidades Escolares", chave="adm_card_escolas"):
            if escolas:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Nome": e.get("nome"),
                                "Código": e.get("codigo"),
                                "Ativa": "Sim" if e.get("ativo") else "Não",
                            }
                            for e in escolas
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("Nenhuma escola cadastrada.")
            with st.form("form_adm_escola", clear_on_submit=True):
                e_nome = st.text_input("Nome da escola", key="adm_es_nome")
                e_cod = st.text_input("Código único", key="adm_es_cod")
                if st.form_submit_button("Cadastrar escola", width="stretch"):
                    if not e_nome.strip() or not e_cod.strip():
                        st.warning("Informe nome e código da escola.")
                    else:
                        resp = criar_escola_api(nome=e_nome, codigo=e_cod)
                        if resp.ok:
                            st.session_state["adm_aviso"] = ("sucesso", "Escola cadastrada com sucesso.")
                            st.rerun()
                        else:
                            st.error(resp.erro or "Não foi possível cadastrar a escola.")

            if escolas_opcoes:
                e_sel = st.selectbox("Alternar status da escola", list(escolas_opcoes.keys()), key="adm_es_toggle_sel")
                e_id = escolas_opcoes[e_sel]
                e_obj = next((item for item in escolas if str(item.get("id")) == e_id), None)
                if e_obj and st.button("Ativar / Inativar escola", key="adm_es_toggle_btn", width="stretch"):
                    resp = atualizar_escola_api(e_id, ativo=not bool(e_obj.get("ativo", True)))
                    if resp.ok:
                        st.session_state["adm_aviso"] = ("sucesso", "Status da escola atualizado.")
                        st.rerun()
                    else:
                        st.error(resp.erro or "Erro ao atualizar escola.")

    with c_tur:
        with card("Turmas Cadastradas", chave="adm_card_turmas"):
            turmas = ctx["turmas"]
            if turmas:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Escola": escolas_nome_por_id.get(str(t.get("escola_id")), "—"),
                                "Turma": f"{t.get('nome')} ({t.get('serie')})",
                                "Ano": t.get("ano_letivo"),
                                "Ativa": "Sim" if t.get("ativo") else "Não",
                            }
                            for t in turmas
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("Nenhuma turma cadastrada.")

            with st.form("form_adm_turma", clear_on_submit=True):
                t_escola_lbl = (
                    st.selectbox("Escola da turma", list(escolas_opcoes.keys()), key="adm_tu_esc")
                    if escolas_opcoes
                    else None
                )
                t_nome = st.text_input("Nome da turma (ex.: 1º Ano A)", key="adm_tu_nome")
                t_serie = st.text_input("Série (ex.: 1ª Série)", key="adm_tu_serie")
                t_turno = st.selectbox("Turno", ["Matutino", "Vespertino", "Noturno", "Integral"], key="adm_tu_turno")
                t_ano = st.number_input("Ano letivo", min_value=2000, max_value=2100, value=2026, key="adm_tu_ano")
                if st.form_submit_button("Cadastrar turma", width="stretch"):
                    if not t_escola_lbl or not t_nome.strip() or not t_serie.strip():
                        st.warning("Selecione a escola e preencha nome e série.")
                    else:
                        resp = criar_turma_api(
                            nome=t_nome,
                            serie=t_serie,
                            turno=t_turno,
                            ano_letivo=int(t_ano),
                            escola_id=escolas_opcoes[t_escola_lbl],
                        )
                        if resp.ok:
                            st.session_state["adm_aviso"] = ("sucesso", "Turma cadastrada com sucesso.")
                            st.rerun()
                        else:
                            st.error(resp.erro or "Erro ao cadastrar turma.")

            if turmas:
                mapa_turmas = {
                    f"{t.get('nome')} ({t.get('ano_letivo')})": t
                    for t in turmas
                    if t.get("id")
                }
                t_sel_lbl = st.selectbox("Alternar status da turma", list(mapa_turmas.keys()), key="adm_tu_toggle_sel")
                t_obj = mapa_turmas[t_sel_lbl]
                if st.button("Ativar / Inativar turma", key="adm_tu_toggle_btn", width="stretch"):
                    resp = atualizar_turma_api(str(t_obj["id"]), ativo=not bool(t_obj.get("ativo", True)))
                    if resp.ok:
                        st.session_state["adm_aviso"] = ("sucesso", "Status da turma atualizado.")
                        st.rerun()
                    else:
                        st.error(resp.erro or "Erro ao atualizar turma.")

    with c_dis:
        with card("Disciplinas", chave="adm_card_disciplinas"):
            disciplinas = ctx["disciplinas"]
            if disciplinas:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Nome": d.get("nome"),
                                "Código": d.get("codigo"),
                                "Ativa": "Sim" if d.get("ativo") else "Não",
                            }
                            for d in disciplinas
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("Nenhuma disciplina cadastrada.")
            with st.form("form_adm_disciplina", clear_on_submit=True):
                d_nome = st.text_input("Nome da disciplina", key="adm_di_nome")
                d_cod = st.text_input("Código (ex.: MAT)", key="adm_di_cod")
                if st.form_submit_button("Cadastrar disciplina", width="stretch"):
                    if not d_nome.strip() or not d_cod.strip():
                        st.warning("Informe nome e código da disciplina.")
                    else:
                        resp = criar_disciplina_api(nome=d_nome, codigo=d_cod)
                        if resp.ok:
                            st.session_state["adm_aviso"] = ("sucesso", "Disciplina cadastrada com sucesso.")
                            st.rerun()
                        else:
                            st.error(resp.erro or "Erro ao cadastrar disciplina.")

            if disciplinas:
                mapa_disc = {
                    f"{d.get('nome')} ({d.get('codigo')})": d
                    for d in disciplinas
                    if d.get("id")
                }
                d_sel_lbl = st.selectbox("Alternar status da disciplina", list(mapa_disc.keys()), key="adm_di_toggle_sel")
                d_obj = mapa_disc[d_sel_lbl]
                if st.button("Ativar / Inativar disciplina", key="adm_di_toggle_btn", width="stretch"):
                    resp = atualizar_disciplina_api(str(d_obj["id"]), ativo=not bool(d_obj.get("ativo", True)))
                    if resp.ok:
                        st.session_state["adm_aviso"] = ("sucesso", "Status da disciplina atualizado.")
                        st.rerun()
                    else:
                        st.error(resp.erro or "Erro ao atualizar disciplina.")


def _render_pagina_credenciais(ctx: dict[str, Any]) -> None:
    escolas_ativas = [e for e in ctx["escolas"] if e.get("id") and e.get("ativo", True)]
    escolas_opcoes: dict[str, Optional[str]] = {
        f"{e.get('nome')} ({e.get('codigo')})": str(e["id"])
        for e in escolas_ativas
    }
    escolas_nome_por_id = {
        str(e["id"]): f"{e.get('nome')} ({e.get('codigo')})"
        for e in ctx["escolas"]
        if e.get("id")
    }
    if escolas_opcoes:
        escolas_opcoes["Todas as escolas (global — somente envio)"] = None

    modelos_disponiveis = [
        m
        for m in (ctx.get("modelos_ml") or [])
        if isinstance(m, dict) and m.get("disponivel_inferencia") and m.get("modelo_nome")
    ]
    modelos_opcoes = {
        f"{m.get('nome_exibicao', m['modelo_nome'])} ({m.get('modelo_versao', '')})".strip(): str(
            m["modelo_nome"]
        )
        for m in modelos_disponiveis
    }

    segredo_recem_criado = st.session_state.pop("adm_nova_credencial_segredo", None)
    if segredo_recem_criado:
        st.warning(
            "Copie o token de serviço ML abaixo agora. Por segurança, ele não será exibido novamente."
        )
        st.code(segredo_recem_criado, language=None)

    col_lista, col_form = st.columns([1.4, 1], gap="large")
    with col_lista:
        with card("Credenciais de integração preditiva (X-Service-Token)", chave="adm_cred_lista"):
            creds = ctx["credenciais"]
            if not creds:
                st.info("Nenhuma credencial técnica emitida até o momento.")
            else:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Nome": c.get("nome"),
                                "Prefixo": c.get("prefixo_chave"),
                                "Escola": (
                                    escolas_nome_por_id.get(str(c.get("escola_id")), str(c.get("escola_id")))
                                    if c.get("escola_id")
                                    else "Global"
                                ),
                                "Modelo": (
                                    c.get("modelo_autorizado")
                                    or ", ".join(c.get("modelos_permitidos") or [])
                                    or "Todos"
                                ),
                                "Permissão": (
                                    "Extração + Envio"
                                    if c.get("permite_leitura_inferencia")
                                    else "Somente envio"
                                ),
                                "Ativa": "Sim" if c.get("ativo") else "Revogada",
                            }
                            for c in creds
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
                ativas = [c for c in creds if c.get("ativo") and c.get("id")]
                if ativas:
                    mapa_ativas = {
                        f"{c.get('nome')} ({c.get('prefixo_chave')})": str(c["id"])
                        for c in ativas
                    }
                    sel_rev = st.selectbox("Credencial para revogar", list(mapa_ativas.keys()), key="adm_cred_rev_sel")
                    if st.button("Revogar credencial selecionada", key="adm_cred_rev_btn", width="stretch"):
                        resp = revogar_credencial_ml_api(mapa_ativas[sel_rev])
                        if resp.ok:
                            st.session_state["adm_aviso"] = ("sucesso", "Credencial ML revogada e auditada.")
                            st.rerun()
                        else:
                            st.error(resp.erro or "Falha ao revogar credencial.")

    with col_form:
        with card("Emitir nova credencial ML", chave="adm_cred_emitir"):
            if not escolas_ativas:
                st.info("Cadastre e ative ao menos uma unidade escolar antes de emitir uma credencial para o pipeline.")
            elif not modelos_opcoes:
                st.warning("Nenhum modelo preditivo compatível está disponível no backend no momento.")
            else:
                with st.form("form_adm_emitir_credencial", clear_on_submit=True):
                    c_nome = st.text_input("Identificação do serviço", key="adm_cr_nome")
                    c_esc_lbl = st.selectbox("Escola", list(escolas_opcoes.keys()), key="adm_cr_escola")
                    c_modelo_lbl = st.selectbox(
                        "Modelo de Machine Learning",
                        list(modelos_opcoes.keys()),
                        key="adm_cr_modelo",
                    )
                    if st.form_submit_button("Emitir token técnico", type="primary", width="stretch"):
                        if not c_nome.strip():
                            st.warning("Informe a identificação do serviço preditivo.")
                        else:
                            escola_sel = escolas_opcoes[c_esc_lbl]
                            modelo_sel = modelos_opcoes[c_modelo_lbl]
                            resp = criar_credencial_ml_api(
                                nome=c_nome,
                                escola_id=escola_sel,
                                modelo_autorizado=modelo_sel,
                                permite_leitura_inferencia=escola_sel is not None,
                            )
                            if resp.ok and isinstance(resp.dados, dict):
                                st.session_state["adm_nova_credencial_segredo"] = resp.dados.get("chave_secreta")
                                st.session_state["adm_aviso"] = ("sucesso", "Credencial ML emitida com segurança.")
                                st.rerun()
                            else:
                                st.error(resp.erro or "Falha ao emitir credencial ML.")


def _render_pagina_auditoria(ctx: dict[str, Any]) -> None:
    with card("Trilha de auditoria técnica administrativa", chave="adm_auditoria_tecnica"):
        eventos = ctx["auditoria_tecnica"]
        if not eventos:
            st.info("Ainda não há eventos técnicos administrativos registrados.")
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Data/Hora": ev.get("criado_em"),
                            "Ação": ev.get("acao"),
                            "Entidade": ev.get("entidade"),
                            "Papel ator": ev.get("papel_ator"),
                            "Detalhes": str(ev.get("detalhes") or "{}"),
                        }
                        for ev in eventos
                    ]
                ),
                hide_index=True,
                width="stretch",
            )

    with card("Auditoria de consultas e bloqueios do Assistente IA", chave="adm_auditoria_ia"):
        aud_ia = ctx["auditoria_ia"]
        if not aud_ia:
            st.info("Ainda não há registros de auditoria do Assistente IA.")
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Data/Hora": item.get("criado_em"),
                            "Resultado": item.get("resultado_autorizacao"),
                            "Papel": item.get("papel_usuario"),
                            "Contexto": item.get("tipo_contexto"),
                            "Request ID": item.get("request_id"),
                        }
                        for item in aud_ia
                    ]
                ),
                hide_index=True,
                width="stretch",
            )


def _render_visao_geral(ctx: dict[str, Any]) -> None:
    _render_kpis(ctx["resumo"])


def _render_pagina_admin(
    titulo: str,
    subtitulo: str,
    renderizar_conteudo: Callable[[dict[str, Any]], None],
) -> None:
    if not st.session_state.get("logado"):
        st.error("É necessário autenticar-se para acessar esta tela.")
        return

    if _papel_atual() != "administrador":
        st.error("Permissão insuficiente: esta área é restrita exclusivamente ao perfil Administrador.")
        return

    with st.container(key="admin_workspace"):
        with st.container(key="admin_page_heading"):
            titulo_pagina(titulo, subtitulo)

        aviso = st.session_state.pop("adm_aviso", None)
        if aviso:
            tipo, mensagem = aviso
            if tipo == "sucesso":
                st.success(mensagem)
            else:
                st.error(mensagem)

        ctx = carregar_contexto_admin_tecnico_api()
        if ctx["sessao_expirada"]:
            st.warning(ctx["erro"] or "Sua sessão expirou. Faça login novamente.")
            return
        if ctx["sem_permissao"]:
            st.error(ctx["erro"] or "Permissão insuficiente para consultar o painel técnico.")
            return
        if not ctx["conectado"]:
            st.error(ctx["erro"] or "Não foi possível carregar os dados operacionais do backend.")
            return

        renderizar_conteudo(ctx)


def render() -> None:
    """Renderiza a visão geral exclusiva do Administrador."""
    _render_pagina_admin(
        "Visão geral",
        "Acompanhe os principais indicadores e acesse cada área pelo menu lateral.",
        _render_visao_geral,
    )


def render_usuarios_e_contas() -> None:
    _render_pagina_admin(
        "Usuários e Contas",
        "Cadastre, revise e controle as contas administrativas e pedagógicas.",
        _render_pagina_usuarios,
    )


def render_estrutura() -> None:
    _render_pagina_admin(
        "Escolas, Turmas e Disciplinas",
        "Mantenha a estrutura da rede atualizada em um só lugar.",
        _render_pagina_estrutura,
    )


def render_credenciais_ml() -> None:
    _render_pagina_admin(
        "Credenciais ML",
        "Emita tokens de serviço e revogue credenciais quando necessário.",
        _render_pagina_credenciais,
    )


def render_auditoria() -> None:
    _render_pagina_admin(
        "Auditoria Técnica e IA",
        "Consulte ações administrativas e registros de autorização e bloqueio da IA.",
        _render_pagina_auditoria,
    )
