"""Tela: Meu Perfil — integrada aos endpoints reais de identidade e vínculo."""

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import titulo_pagina
from data.api_client import (
    listar_atribuicoes_api,
    listar_disciplinas_api,
    listar_turmas_api,
    obter_escola_api,
    obter_usuario_atual_api,
    possui_sessao_api_ativa,
)


_ROTULOS_PAPEL = {
    "administrador": "Administrador",
    "gestor": "Gestor Escolar",
    "professor": "Professor",
}


def carregar_perfil_api() -> dict[str, Any]:
    """Carrega identidade real (`GET /auth/me`), escola vinculada e atribuições do usuário."""
    estado: dict[str, Any] = {
        "conectado": False,
        "sessao_expirada": False,
        "sem_permissao": False,
        "erro": None,
        "usuario": None,
        "escola": None,
        "atribuicoes": [],
    }
    if not possui_sessao_api_ativa():
        estado["erro"] = "Sessão API não autenticada."
        return estado

    resp_me = obter_usuario_atual_api()
    if resp_me.sessao_expirada:
        estado["sessao_expirada"] = True
        estado["erro"] = resp_me.erro
        return estado
    if resp_me.sem_permissao:
        estado["sem_permissao"] = True
        estado["erro"] = resp_me.erro
        return estado
    if not resp_me.ok or not isinstance(resp_me.dados, dict):
        estado["erro"] = resp_me.erro or "Não foi possível obter os dados do perfil."
        return estado

    usuario = resp_me.dados
    estado["conectado"] = True
    estado["usuario"] = usuario

    escola_id = usuario.get("escola_id")
    if escola_id:
        resp_esc = obter_escola_api(str(escola_id))
        if resp_esc.ok and isinstance(resp_esc.dados, dict):
            estado["escola"] = resp_esc.dados
            if resp_esc.dados.get("nome"):
                st.session_state["escola_nome_atual"] = resp_esc.dados["nome"]

    papel = str(usuario.get("papel", "")).strip().lower()
    if papel == "professor":
        resp_atr = listar_atribuicoes_api()
        resp_turmas = listar_turmas_api()
        resp_discs = listar_disciplinas_api()

        turmas_por_id = (
            {str(t["id"]): t for t in resp_turmas.dados if isinstance(t, dict) and t.get("id")}
            if resp_turmas.ok and isinstance(resp_turmas.dados, list)
            else {}
        )
        discs_por_id = (
            {str(d["id"]): d for d in resp_discs.dados if isinstance(d, dict) and d.get("id")}
            if resp_discs.ok and isinstance(resp_discs.dados, list)
            else {}
        )

        atribuicoes_raw = resp_atr.dados if resp_atr.ok and isinstance(resp_atr.dados, list) else []
        lista_formatada = []
        for item in atribuicoes_raw:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("turma_id") or "")
            did = str(item.get("disciplina_id") or "")
            turma = turmas_por_id.get(tid, {})
            disc = discs_por_id.get(did, {})
            nome_turma = (
                f"{turma.get('nome')} ({turma.get('serie')} • {turma.get('ano_letivo')})"
                if turma.get("nome")
                else tid or "—"
            )
            nome_disc = (
                f"{disc.get('nome')} ({disc.get('codigo')})"
                if disc.get("nome")
                else ("Todas / Polivalente" if not did else did)
            )
            lista_formatada.append({"Turma": nome_turma, "Disciplina": nome_disc})
        estado["atribuicoes"] = lista_formatada

    return estado


def render():
    """Mostra as informações reais do usuário conectado e suas permissões no backend."""
    if not st.session_state.get("logado"):
        st.error("É necessário entrar no sistema.")
        return

    titulo_pagina(
        "Meu Perfil",
        "Identidade autenticada, escola vinculada e permissões reais no sistema.",
    )

    ctx = carregar_perfil_api()
    if ctx["sessao_expirada"]:
        st.warning(ctx["erro"] or "Sua sessão expirou. Faça login novamente.")
        return
    if not ctx["conectado"] or not ctx["usuario"]:
        st.error(ctx["erro"] or "Não foi possível carregar o perfil do servidor.")
        return

    usuario = ctx["usuario"]
    papel = str(usuario.get("papel") or "professor").strip().lower()
    rotulo_papel = _ROTULOS_PAPEL.get(papel, papel.capitalize())
    escola = ctx.get("escola") or {}
    escola_texto = (
        f"{escola.get('nome')} ({escola.get('codigo')})"
        if escola.get("nome")
        else ("Escopo global da rede" if papel == "administrador" else "Sem unidade escolar vinculada")
    )

    with st.container(key="perfil_informacoes"):
        st.subheader("Informações do usuário")

        col_nome, col_email = st.columns(2)
        with col_nome:
            st.text_input("Nome", value=str(usuario.get("nome") or "—"), disabled=True)
        with col_email:
            st.text_input("E-mail institucional", value=str(usuario.get("email") or "—"), disabled=True)

        col_papel, col_status, col_escola = st.columns(3)
        with col_papel:
            st.text_input("Papel no sistema", value=rotulo_papel, disabled=True)
        with col_status:
            st.text_input(
                "Status da conta",
                value="Ativa" if usuario.get("ativo", True) else "Inativa",
                disabled=True,
            )
        with col_escola:
            st.text_input("Unidade escolar", value=escola_texto, disabled=True)

    st.divider()
    st.subheader("Permissões e escopo de atuação")

    if papel == "administrador":
        st.success("Perfil Administrador: gestão estrutural global (escolas, usuários, turmas, disciplinas e atribuições).")
        st.caption(
            "Observação de segurança: o perfil Administrador não acessa diretamente os endpoints pedagógicos "
            "de indicadores operacionais, datasets importados ou assistente."
        )
    elif papel == "gestor":
        st.info(
            "Perfil Gestor Escolar: opera dados acadêmicos, importações, avaliações, participação, "
            "atribuições e assistente pedagógico no escopo da sua escola vinculada."
        )
    else:
        st.info(
            "Perfil Professor: opera indicadores, avaliações, participação, estudantes e assistente pedagógico "
            "estritamente para as turmas e disciplinas vinculadas."
        )
        st.subheader("Minhas turmas e disciplinas atribuídas")
        atribuicoes = ctx.get("atribuicoes") or []
        if atribuicoes:
            st.dataframe(pd.DataFrame(atribuicoes), hide_index=True, width="stretch")
        else:
            st.warning("Você ainda não possui turmas atribuídas no sistema.")
