"""Tela de cadastro."""

import streamlit as st

from components.auth import painel_boas_vindas


def render():
    """Renderiza o formulário de cadastro."""
    col_formulario, col_boas_vindas = st.columns([1, 1], gap=None)

    with col_formulario:
        with st.container(key="painel_azul"):
            with st.container(key="auth_formulario"):
                st.html('<div class="auth-form-titulo">Cadastro</div>')

                st.text_input("Nome", placeholder="Insira o seu nome", key="cad_nome")
                st.text_input(
                    "Email",
                    placeholder="Insira o seu e-mail",
                    key="cad_email",
                )
                st.text_input(
                    "Senha",
                    type="password",
                    placeholder="********",
                    key="cad_senha",
                )
                st.text_input(
                    "Confirmar senha",
                    type="password",
                    placeholder="********",
                    key="cad_confirmar_senha",
                )

                if st.button("Cadastrar", type="primary", key="btn_cadastrar"):
                    # O cadastro será persistido pelo backend quando essa integração existir.
                    st.session_state["tela_auth"] = "login"
                    st.rerun()

    with col_boas_vindas:
        painel_boas_vindas("Já tem uma conta?", "Login", "login")
