"""Tela de cadastro."""

import streamlit as st

from components.auth import painel_boas_vindas


def render():
    """Orienta sobre o provisionamento institucional de contas (sem autocadastro público)."""
    col_formulario, col_boas_vindas = st.columns([1, 1], gap=None)

    with col_formulario:
        with st.container(key="painel_azul"):
            with st.container(key="auth_formulario"):
                st.html('<div class="auth-form-titulo">Acesso institucional</div>')
                st.info(
                    "Por política de segurança e privacidade (LGPD), o Vértice não possui "
                    "autocadastro público. Contas de Administrador, Gestor Escolar e Professor "
                    "são criadas exclusivamente pelo Administrador da instituição."
                )
                if st.button("Voltar ao login", type="primary", key="btn_voltar_login"):
                    st.session_state["tela_auth"] = "login"
                    st.rerun()

    with col_boas_vindas:
        painel_boas_vindas("Já tem uma conta?", "Login", "login")
