"""Tela de login."""

import streamlit as st

from components.auth import painel_boas_vindas


def render():
    """Renderiza a tela de login."""
    col_esquerda, col_direita = st.columns([1, 1], gap=None)

    with col_esquerda:
        painel_boas_vindas(
            "Não tem uma conta ainda?",
            "Cadastro",
            "cadastro",
        )

    with col_direita:
        with st.container(key="painel_azul"):
            with st.container(key="auth_formulario"):
                st.html('<div class="auth-form-titulo">Login</div>')

                st.text_input(
                    "Email",
                    placeholder="Insira o seu e-mail",
                    key="login_email",
                )
                st.text_input(
                    "Senha",
                    type="password",
                    placeholder="********",
                    key="login_senha",
                )

                st.html('<div class="auth-esqueceu">Esqueceu a senha?</div>')

                if st.button("Login", type="primary", key="btn_login"):
                    # A validação real entra aqui quando o backend estiver conectado.
                    st.session_state["logado"] = True
                    st.rerun()
