"""Tela de login."""

import streamlit as st

from components.auth import painel_boas_vindas
from data.api_client import autenticar_usuario_api, registrar_usuario_sessao


def render():
    """Renderiza a tela de login."""
    col_esquerda, col_direita = st.columns([1, 1], gap=None)

    with col_esquerda:
        painel_boas_vindas(
            "Precisa de uma conta?",
            "Solicitar acesso",
            "cadastro",
        )

    with col_direita:
        with st.container(key="painel_azul"):
            with st.container(key="auth_formulario"):
                st.html('<div class="auth-form-titulo">Login</div>')

                if st.session_state.get("sessao_api_expirada"):
                    st.warning(
                        st.session_state.get("mensagem_sessao_expirada")
                        or "Sua sessão expirou. Faça login novamente."
                    )

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

                st.html('<div class="auth-esqueceu">Acesso restrito a contas institucionais.</div>')

                if st.button("Login", type="primary", key="btn_login"):
                    if not email.strip() or not senha:
                        st.error("Informe seu e-mail e sua senha.")
                        return

                    with st.spinner("Autenticando no Vértice..."):
                        resp = autenticar_usuario_api(email.strip(), senha)

                    if resp.ok and isinstance(resp.dados, dict):
                        usuario = resp.dados.get("usuario") or {}
                        registrar_usuario_sessao(usuario, email_fallback=email)
                        st.session_state["logado"] = True
                        st.rerun()
                    elif resp.indisponivel:
                        st.session_state["logado"] = False
                        st.error(
                            resp.erro
                            or "Servidor do Vértice indisponível. Não foi possível autenticar."
                        )
                    else:
                        st.session_state["logado"] = False
                        st.error(resp.erro or "Credenciais inválidas.")

