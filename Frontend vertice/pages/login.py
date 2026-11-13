"""Tela de login."""

import streamlit as st

from components.auth import painel_boas_vindas
from data.api_client import autenticar_usuario_api


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

                email = st.text_input(
                    "Email",
                    placeholder="Insira o seu e-mail",
                    key="login_email",
                )
                senha = st.text_input(
                    "Senha",
                    type="password",
                    placeholder="********",
                    key="login_senha",
                )

                st.html('<div class="auth-esqueceu">Esqueceu a senha?</div>')

                if st.button("Login", type="primary", key="btn_login"):
                    if not email.strip() or not senha:
                        st.error("Informe seu e-mail e sua senha.")
                        return

                    with st.spinner("Autenticando no Vértice..."):
                        resp = autenticar_usuario_api(email.strip(), senha)

                    if resp.ok and isinstance(resp.dados, dict):
                        usuario = resp.dados.get("usuario") or {}
                        papel = str(usuario.get("papel", "professor")).lower()
                        st.session_state["perfil"] = (
                            "administrador"
                            if papel in ("administrador", "gestor")
                            else "professor"
                        )
                        st.session_state["papel_api"] = papel
                        st.session_state["professor_atual"] = (
                            usuario.get("nome_completo")
                            if papel == "professor"
                            else None
                        )
                        st.session_state["email_atual"] = usuario.get(
                            "email", email.strip().lower()
                        )
                        st.session_state["logado"] = True
                        st.rerun()
                    elif resp.indisponivel:
                        st.session_state["logado"] = True
                        st.rerun()
                    else:
                        st.error(resp.erro or "Credenciais inválidas.")

