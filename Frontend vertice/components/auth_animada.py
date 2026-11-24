"""Autenticação do Vértice com painéis deslizantes."""

import base64
from pathlib import Path

import streamlit as st


PASTA_ICONS = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "icons"
)


def _capelo_base64():
    """Carrega o ícone do Vértice."""

    caminho = PASTA_ICONS / "capelo.svg"

    if not caminho.is_file():
        return ""

    return base64.b64encode(
        caminho.read_bytes()
    ).decode("utf-8")


def _estilos_pagina():
    """Fixa a tela de autenticação nas 4 bordas da janela sem margens."""

    st.html(
        """
        <style>
            html:has(.st-key-vertice_auth_tela),
            body:has(.st-key-vertice_auth_tela) {
                margin: 0 !important;
                padding: 0 !important;
                width: 100vw !important;
                height: 100vh !important;
                overflow: hidden !important;
            }

            body:has(.st-key-vertice_auth_tela) header[data-testid="stHeader"],
            body:has(.st-key-vertice_auth_tela) [data-testid="stToolbar"],
            body:has(.st-key-vertice_auth_tela) [data-testid="stDecoration"],
            body:has(.st-key-vertice_auth_tela) [data-testid="stSidebar"] {
                display: none !important;
            }

            .st-key-vertice_auth_tela,
            .st-key-vertice_auth_tela > div,
            .st-key-vertice_auth_tela [data-testid="stVerticalBlock"],
            .st-key-vertice_auth_tela [data-testid="stElementContainer"],
            .st-key-vertice_auth_tela [data-testid="stCustomComponentV2"],
            .st-key-vertice_auth_tela [data-testid="stCustomComponentV2"] > * {
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                right: 0 !important;
                bottom: 0 !important;
                width: 100vw !important;
                height: 100vh !important;
                max-width: none !important;
                max-height: none !important;
                margin: 0 !important;
                padding: 0 !important;
                gap: 0 !important;
                z-index: 999 !important;
                overflow: hidden !important;
            }
        </style>
        """
    )


HTML = """
<div class="v-auth">

    <section class="v-cream">

        <div class="v-welcome v-welcome-login">

            <div class="v-logo">
                <img id="v-capelo-login" alt="Vértice">
            </div>

            <h1>Olá! Bem-vindo(a)<br>ao Vértice</h1>

            <p>Não tem uma conta ainda?</p>

            <button
                class="v-outline-button"
                id="v-ir-cadastro"
                type="button"
            >
                Cadastro
            </button>

        </div>

        <div class="v-welcome v-welcome-register">

            <div class="v-logo">
                <img id="v-capelo-cadastro" alt="Vértice">
            </div>

            <h1>Olá! Bem-vindo(a)<br>ao Vértice</h1>

            <p>Já tem uma conta?</p>

            <button
                class="v-outline-button"
                id="v-ir-login"
                type="button"
            >
                Login
            </button>

        </div>

    </section>

    <section class="v-blue">

        <div class="v-form v-form-login">

            <h2>Login</h2>

            <div class="v-fields">

                <label for="v-login-email">Email</label>

                <input
                    id="v-login-email"
                    type="email"
                    placeholder="Insira o seu e-mail"
                    autocomplete="email"
                    required
                >

                <label for="v-login-senha">Senha</label>

                <div class="v-password-wrap">
                    <input
                        id="v-login-senha"
                        type="password"
                        placeholder="********"
                        autocomplete="current-password"
                        required
                    >
                    <button
                        type="button"
                        class="v-toggle-pass"
                        id="v-toggle-senha"
                        aria-label="Mostrar senha"
                        title="Mostrar senha"
                    >
                        <svg
                            id="v-icon-eye"
                            width="20"
                            height="20"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            stroke-width="2"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                        >
                            <path class="v-eye-outline" d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"></path>
                            <circle class="v-eye-pupil" cx="12" cy="12" r="3"></circle>
                            <line class="v-eye-slash" x1="3" y1="3" x2="21" y2="21"></line>
                        </svg>
                    </button>
                </div>

                <p class="v-forgot">
                    O perfil de acesso é definido automaticamente pela sua conta institucional.
                </p>

                <p
                    class="v-error"
                    id="v-login-erro"
                    role="alert"
                    aria-live="polite"
                ></p>

                <button
                    class="v-submit"
                    id="v-entrar"
                    type="button"
                >
                    Login
                </button>

            </div>

        </div>

        <div class="v-form v-form-register">

            <h2>Acesso Institucional</h2>

            <div class="v-fields">
                <p style="font-size: 14px; line-height: 1.6; color: #f7f4ed; margin: 8px 0 18px 0;">
                    Por segurança e conformidade com a LGPD, o Vértice não permite autocadastro público.
                    Solicite ao Administrador institucional o cadastro da sua conta (Gestor ou Professor)
                    ou entre com suas credenciais já habilitadas.
                </p>

                <button
                    class="v-submit"
                    id="v-cadastrar"
                    type="button"
                >
                    Ir para Login
                </button>

            </div>

        </div>

    </section>

</div>
"""


CSS = """
:host {
    position: fixed;
    inset: 0;
    display: block;
    width: 100vw;
    height: 100vh;
    margin: 0;
    padding: 0;
    overflow: hidden;
    font-family: Arial, Helvetica, sans-serif;
}

* {
    box-sizing: border-box;
}

.v-auth {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    min-height: 100vh;
    margin: 0;
    padding: 0;
    overflow: hidden;
    border-radius: 0;
    background: #f7f4ed;
    isolation: isolate;
}

/* Painéis do desktop */

.v-cream,
.v-blue {
    position: absolute;
    top: 0;
    width: 50%;
    height: 100%;
    overflow: hidden;

    transition:
        transform 950ms cubic-bezier(.76, 0, .24, 1);

    will-change: transform;
    backface-visibility: hidden;
}

.v-cream {
    left: 0;
    z-index: 1;
    background: #f7f4ed;
    color: #243d78;
    transform: translateX(0);
}

.v-blue {
    right: 0;
    z-index: 2;
    background: #4e67ca;
    color: #ffffff;
    transform: translateX(0);
}

/* Animação horizontal */

.v-auth.is-register .v-cream {
    transform: translateX(100%);
}

.v-auth.is-register .v-blue {
    transform: translateX(-100%);
}

/* Boas-vindas */

.v-welcome {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 32px;

    transition:
        opacity 280ms ease,
        transform 450ms ease;
}

.v-welcome-login {
    opacity: 1;
    transform: translateY(0);
    transition-delay: 320ms;
}

.v-welcome-register {
    opacity: 0;
    pointer-events: none;
    transform: translateY(15px);
}

.v-auth.is-register .v-welcome-login {
    opacity: 0;
    pointer-events: none;
    transform: translateY(-15px);
    transition-delay: 0ms;
}

.v-auth.is-register .v-welcome-register {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
    transition-delay: 320ms;
}

/* Logotipo */

.v-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 22px;
}

.v-logo img {
    width: 86px;
    height: 86px;
    object-fit: contain;
}

/* Textos de boas-vindas */

.v-welcome h1 {
    margin: 0 0 30px;
    font-size: clamp(27px, 3vw, 43px);
    line-height: 1.2;
    font-weight: 700;
    letter-spacing: -0.7px;
}

.v-welcome p {
    margin: 0 0 22px;
    font-size: 17px;
}

/* Botão de troca de tela */

.v-outline-button {
    min-width: 170px;
    min-height: 48px;
    padding: 10px 26px;
    border: 2px solid #4e67ca;
    border-radius: 12px;
    background: transparent;
    color: #344fae;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;

    transition:
        background 200ms ease,
        color 200ms ease,
        transform 200ms ease;
}

.v-outline-button:hover {
    background: #4e67ca;
    color: #ffffff;
    transform: translateY(-2px);
}

/* Formulários */

.v-form {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 28px 12%;

    transition:
        opacity 280ms ease,
        transform 450ms ease;
}

.v-form-login {
    opacity: 1;
    transform: translateY(0);
    transition-delay: 320ms;
}

.v-form-register {
    opacity: 0;
    pointer-events: none;
    transform: translateY(15px);
}

.v-auth.is-register .v-form-login {
    opacity: 0;
    pointer-events: none;
    transform: translateY(-15px);
    transition-delay: 0ms;
}

.v-auth.is-register .v-form-register {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
    transition-delay: 320ms;
}

/* Títulos */

.v-form h2 {
    margin: 0 0 24px;
    font-size: 37px;
    font-weight: 700;
    line-height: 1.2;
    text-align: center;
}

.v-fields {
    width: 100%;
    max-width: 420px;
}

.v-fields label {
    display: block;
    margin: 12px 0 7px;
    font-size: 14px;
    font-weight: 600;
}

/* Campos do formulário */

.v-fields input,
.v-fields select {
    display: block;
    width: 100%;
    min-height: 45px;
    padding: 10px 13px;
    border: 1px solid transparent;
    border-radius: 9px;
    outline: none;
    background: #ffffff;
    color: #24314e;
    font: inherit;
    font-size: 14px;

    transition:
        box-shadow 200ms ease,
        border-color 200ms ease;
}

.v-fields input:focus,
.v-fields select:focus {
    border-color: #dce5ff;
    box-shadow:
        0 0 0 3px rgba(255,255,255,.25);
}

.v-fields input::placeholder {
    color: #8890a0;
}

/* Campo de senha com um único olho e transição suave */

.v-password-wrap {
    position: relative;
    width: 100%;
}

.v-password-wrap input {
    padding-right: 44px;
}

.v-password-wrap input::-ms-reveal,
.v-password-wrap input::-ms-clear,
.v-password-wrap input::-webkit-credentials-auto-fill-button,
.v-password-wrap input::-webkit-contacts-auto-fill-button {
    display: none !important;
}

.v-toggle-pass {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    background: transparent;
    border: none;
    color: #52607a;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 5px;
    border-radius: 6px;
    transition: color 180ms ease, background 180ms ease;
}

.v-toggle-pass:hover {
    color: #24314e;
    background: rgba(36, 49, 78, 0.08);
}

.v-toggle-pass .v-eye-pupil {
    transform-origin: 12px 12px;
    transform: scale(0.75);
    opacity: 0.55;
    transition:
        transform 240ms cubic-bezier(.4, 0, .2, 1),
        opacity 240ms ease;
}

.v-toggle-pass .v-eye-slash {
    stroke-dasharray: 26;
    stroke-dashoffset: 0;
    opacity: 1;
    transition:
        stroke-dashoffset 260ms cubic-bezier(.4, 0, .2, 1),
        opacity 200ms ease;
}

.v-toggle-pass.is-open .v-eye-pupil {
    transform: scale(1);
    opacity: 1;
}

.v-toggle-pass.is-open .v-eye-slash {
    stroke-dashoffset: 26;
    opacity: 0;
}

/* Recuperação de senha */

.v-forgot {
    margin: 15px 0 12px;
    text-align: right;
    font-size: 13px;
}

/* Mensagens de validação / erro de login */

.v-error {
    min-height: 18px;
    margin: 9px 0 4px;
    font-size: 13px;
    font-weight: 600;
    color: #fff5f5;
}

.v-error:not(:empty) {
    background: rgba(229, 57, 53, 0.28);
    border: 1px solid rgba(255, 205, 210, 0.75);
    padding: 9px 12px;
    border-radius: 8px;
}

/* Botões principais */

.v-submit {
    display: block;
    width: 100%;
    min-height: 48px;
    margin-top: 12px;
    border: 0;
    border-radius: 10px;
    background: #ffffff;
    color: #344fae;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;

    transition:
        background 200ms ease,
        transform 200ms ease,
        box-shadow 200ms ease;
}

.v-submit:hover {
    background: #eef2ff;
    transform: translateY(-2px);
    box-shadow: 0 5px 16px rgba(0,0,0,.12);
}

button:focus-visible {
    outline: 3px solid #f7cb72;
    outline-offset: 3px;
}

/* Tablet e celular */

@media (max-width: 800px) {

    .v-auth {
        height: 100vh;
        min-height: 100vh;
        border-radius: 0;
    }

    .v-cream {
        top: 0;
        left: 0;
        width: 100%;
        height: 42%;
        transform: translateY(0);

        transition:
            transform 750ms cubic-bezier(.76, 0, .24, 1);
    }

    .v-blue {
        top: 42%;
        right: 0;
        width: 100%;
        height: 58%;
        transform: translateY(0);

        transition:
            transform 750ms cubic-bezier(.76, 0, .24, 1);
    }

    .v-auth.is-register .v-cream {
        transform: translateY(138.095238%);
    }

    .v-auth.is-register .v-blue {
        transform: translateY(-72.413793%);
    }

    .v-form {
        padding: 24px 8%;
        justify-content: center;
    }

    .v-form h2 {
        margin: 0 0 16px;
        font-size: 27px;
        line-height: 1.2;
    }

    .v-fields {
        width: 100%;
        max-width: 420px;
    }

    .v-fields label {
        margin: 8px 0 5px;
        font-size: 13px;
    }

    .v-fields input,
    .v-fields select {
        min-height: 41px;
        padding: 9px 12px;
        font-size: 13px;
    }

    .v-error {
        min-height: 14px;
        margin: 5px 0 0;
        font-size: 12px;
    }

    .v-submit {
        min-height: 44px;
        margin-top: 12px;
        font-size: 14px;
    }

    .v-forgot {
        margin: 12px 0;
    }

    .v-welcome {
        padding: 20px 14px;
        justify-content: center;
    }

    .v-logo {
        margin-bottom: 12px;
    }

    .v-logo img {
        width: 54px;
        height: 54px;
    }

    .v-welcome h1 {
        font-size: 24px;
        line-height: 1.25;
        margin: 0 0 14px;
    }

    .v-welcome p {
        font-size: 14px;
        margin: 0 0 12px;
    }

    .v-outline-button {
        min-width: 140px;
        min-height: 42px;
        padding: 8px 18px;
        font-size: 14px;
    }
}

/* Celulares estreitos */

@media (max-width: 380px) {

    .v-form {
        padding-left: 7%;
        padding-right: 7%;
    }

    .v-form h2 {
        font-size: 25px;
    }

    .v-welcome h1 {
        font-size: 22px;
    }

    .v-fields input,
    .v-fields select {
        font-size: 12px;
    }
}

/* Acessibilidade */

@media (prefers-reduced-motion: reduce) {

    .v-cream,
    .v-blue,
    .v-welcome,
    .v-form,
    .v-toggle-pass .v-eye-pupil,
    .v-toggle-pass .v-eye-slash {
        transition-duration: 0ms !important;
        transition-delay: 0ms !important;
    }
}
"""


JS = """
export default function(component) {
    const { parentElement, data, setTriggerValue } = component;

    const root = parentElement.querySelector(".v-auth");

    if (!root) return;

    const el = (id) => root.querySelector("#" + id);

    if (!root.dataset.initialized) {
        root.dataset.initialized = "true";

        if (data.initialView === "cadastro") {
            root.classList.add("is-register");
        }
    }

    const capelo = data.capelo || "";

    for (const id of [
        "v-capelo-login",
        "v-capelo-cadastro"
    ]) {
        const img = el(id);

        if (capelo) {
            img.src =
                "data:image/svg+xml;base64," + capelo;
            img.hidden = false;
        } else {
            img.hidden = true;
        }
    }

    // Exibe mensagem de erro retornada pelo backend quando houver nova tentativa
    const loginErro = el("v-login-erro");
    const seqAtual = String(data.erroSeq || 0);
    if (loginErro && data.erroLogin && root.dataset.lastErroSeq !== seqAtual) {
        root.dataset.lastErroSeq = seqAtual;
        loginErro.textContent = data.erroLogin;
    }

    // Único olho com transição suave entre fechado e aberto
    const btnToggleSenha = el("v-toggle-senha");
    const inputSenha = el("v-login-senha");

    if (btnToggleSenha && inputSenha) {
        btnToggleSenha.onclick = () => {
            const abrir = inputSenha.type === "password";
            inputSenha.type = abrir ? "text" : "password";
            btnToggleSenha.classList.toggle("is-open", abrir);
            btnToggleSenha.setAttribute(
                "aria-label",
                abrir ? "Ocultar senha" : "Mostrar senha"
            );
            btnToggleSenha.title = abrir ? "Ocultar senha" : "Mostrar senha";
        };
    }

    function trocarTela(destino) {
        root.classList.toggle(
            "is-register",
            destino === "cadastro"
        );

        if (loginErro) {
            loginErro.textContent = "";
        }
    }

    el("v-ir-cadastro").onclick = () => {
        trocarTela("cadastro");
    };

    el("v-ir-login").onclick = () => {
        trocarTela("login");
    };

    const campoEmail = el("v-login-email");
    for (const campo of [campoEmail, inputSenha]) {
        if (campo) {
            campo.oninput = () => {
                if (loginErro) loginErro.textContent = "";
            };
            campo.onkeydown = (ev) => {
                if (ev.key === "Enter") {
                    ev.preventDefault();
                    el("v-entrar").click();
                }
            };
        }
    }

    el("v-entrar").onclick = () => {
        const email = campoEmail.value.trim();
        const senha = inputSenha.value;

        if (!email || !senha) {
            loginErro.textContent =
                "Informe seu e-mail e sua senha.";
            return;
        }

        if (!campoEmail.checkValidity()) {
            loginErro.textContent =
                "Informe um e-mail válido.";
            return;
        }

        loginErro.textContent = "";

        setTriggerValue("submit", {
            tipo: "login",
            email: email,
            senha: senha
        });
    };

    el("v-cadastrar").onclick = () => {
        trocarTela("login");
    };
}
"""


componente_auth = st.components.v2.component(
    "vertice_auth_animada",
    html=HTML,
    css=CSS,
    js=JS,
)


def render():
    """Renderiza a autenticação institucional integrada ao backend."""

    _estilos_pagina()

    if st.session_state.get("sessao_api_expirada"):
        st.toast(
            st.session_state.get("mensagem_sessao_expirada")
            or "Sua sessão expirou. Faça login novamente para continuar.",
            icon="⚠️",
        )

    erro_login = st.session_state.get("auth_erro_login", "")
    erro_seq = st.session_state.get("auth_erro_seq", 0)

    with st.container(key="vertice_auth_tela"):
        resultado = componente_auth(
            key="vertice_auth",
            data={
                "initialView": "login",
                "capelo": _capelo_base64(),
                "erroLogin": erro_login,
                "erroSeq": erro_seq,
            },
            on_submit_change=lambda: None,
        )

    acao = resultado.submit

    if not acao:
        return

    if acao.get("tipo") == "login":
        from data.api_client import autenticar_usuario_api, registrar_usuario_sessao

        email = acao.get("email", "").strip().lower()
        senha = acao.get("senha", "")

        if email and senha:
            resp = autenticar_usuario_api(email, senha)
            if resp.ok and isinstance(resp.dados, dict):
                usuario = resp.dados.get("usuario") or {}
                registrar_usuario_sessao(usuario, email_fallback=email)
                st.session_state.pop("auth_erro_login", None)
                st.session_state.pop("auth_erro_seq", None)
                st.session_state["logado"] = True
                st.rerun()
                return

            st.session_state["logado"] = False
            st.session_state["auth_erro_login"] = (
                resp.erro
                or (
                    "Servidor do Vértice indisponível. "
                    "Não foi possível autenticar suas credenciais."
                    if resp.indisponivel
                    else "E-mail ou senha inválidos."
                )
            )
            st.session_state["auth_erro_seq"] = erro_seq + 1
            st.rerun()
            return

    elif acao.get("tipo") == "cadastro":
        st.session_state["tela_auth"] = "login"
        st.toast(
            "O provisionamento de contas no Vértice é realizado exclusivamente pelo Administrador.",
            icon="ℹ️",
        )
