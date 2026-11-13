
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
    """Faz a autenticação ocupar toda a área principal."""

    st.html(
        """
        <style>
            div[data-testid="stMainBlockContainer"]:has(
                .st-key-vertice_auth_tela
            ),
            div[data-testid="stAppViewBlockContainer"]:has(
                .st-key-vertice_auth_tela
            ),
            .stMainBlockContainer:has(
                .st-key-vertice_auth_tela
            ) {
                max-width: none !important;
                width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
            }

            .st-key-vertice_auth_tela {
                width: 100% !important;
                max-width: none !important;
                padding: 0 !important;
                margin: 0 !important;
            }

            .st-key-vertice_auth_tela
            [data-testid="stVerticalBlock"] {
                gap: 0 !important;
            }

            body:has(.st-key-vertice_auth_tela)
            header[data-testid="stHeader"] {
                display: none !important;
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

                <input
                    id="v-login-senha"
                    type="password"
                    placeholder="********"
                    autocomplete="current-password"
                    required
                >

                <label for="v-login-perfil">
                    Tipo de acesso
                </label>

                <select id="v-login-perfil">
                    <option value="administrador">
                        Administrador
                    </option>
                    <option value="professor">
                        Professor
                    </option>
                </select>

                <p class="v-forgot">
                    Esqueceu a senha?
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

            <h2>Cadastro</h2>

            <div class="v-fields">

                <label for="v-cad-nome">Nome</label>

                <input
                    id="v-cad-nome"
                    type="text"
                    placeholder="Insira o seu nome"
                    autocomplete="name"
                >

                <label for="v-cad-email">Email</label>

                <input
                    id="v-cad-email"
                    type="email"
                    placeholder="Insira o seu e-mail"
                    autocomplete="email"
                >

                <label for="v-cad-senha">Senha</label>

                <input
                    id="v-cad-senha"
                    type="password"
                    placeholder="********"
                    autocomplete="new-password"
                >

                <label for="v-cad-confirmar">
                    Confirmar senha
                </label>

                <input
                    id="v-cad-confirmar"
                    type="password"
                    placeholder="********"
                    autocomplete="new-password"
                >

                <p
                    class="v-error"
                    id="v-cadastro-erro"
                    role="alert"
                    aria-live="polite"
                ></p>

                <button
                    class="v-submit"
                    id="v-cadastrar"
                    type="button"
                >
                    Cadastrar
                </button>

            </div>

        </div>

    </section>

</div>
"""


CSS = """
:host {
    display: block;
    width: 100%;
    margin: 0;
    padding: 0;
    font-family: Arial, Helvetica, sans-serif;
}

* {
    box-sizing: border-box;
}

.v-auth {
    position: relative;
    width: 100%;
    height: 100dvh;
    min-height: 620px;
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

/* Recuperação de senha */

.v-forgot {
    margin: 15px 0 12px;
    text-align: right;
    font-size: 13px;
}

/* Mensagens de validação */

.v-error {
    min-height: 18px;
    margin: 9px 0 0;
    font-size: 13px;
    color: #ffe7a9;
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
        height: 850px;
        min-height: 850px;
        border-radius: 0;
    }

    /* O azul ocupa 58% e o creme 42%. */

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

    /* Animação vertical */

    .v-auth.is-register .v-cream {
        transform: translateY(138.095238%);
    }

    .v-auth.is-register .v-blue {
        transform: translateY(-72.413793%);
    }

    /* Formulários compactos */

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

    /* Boas-vindas */

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
    .v-form {
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

    // Configura a tela inicial somente uma vez.
    if (!root.dataset.initialized) {
        root.dataset.initialized = "true";

        if (data.initialView === "cadastro") {
            root.classList.add("is-register");
        }
    }

    // Carrega o logotipo.
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

    // Animação de troca de tela.
    function trocarTela(destino) {
        root.classList.toggle(
            "is-register",
            destino === "cadastro"
        );

        el("v-cadastro-erro").textContent = "";
        el("v-login-erro").textContent = "";
    }

    el("v-ir-cadastro").onclick = () => {
        trocarTela("cadastro");
    };

    el("v-ir-login").onclick = () => {
        trocarTela("login");
    };

    // Validação inicial do formulário.
    el("v-entrar").onclick = () => {
        const campoEmail = el("v-login-email");
        const email = campoEmail.value.trim();
        const senha = el("v-login-senha").value;
        const perfil = el("v-login-perfil").value;
        const erro = el("v-login-erro");

        if (!email || !senha) {
            erro.textContent =
                "Informe seu e-mail e sua senha.";
            return;
        }

        if (!campoEmail.checkValidity()) {
            erro.textContent =
                "Informe um e-mail válido.";
            return;
        }

        erro.textContent = "";

        setTriggerValue("submit", {
            tipo: "login",
            email: email,
            senha: senha,
            perfil: perfil
        });
    };

    // Validação inicial do cadastro.
    el("v-cadastrar").onclick = () => {
        const nome = el("v-cad-nome").value.trim();
        const campoEmail = el("v-cad-email");
        const email = campoEmail.value.trim();
        const senha = el("v-cad-senha").value;
        const confirmar = el("v-cad-confirmar").value;

        const erro = el("v-cadastro-erro");

        if (!nome || !email || !senha || !confirmar) {
            erro.textContent =
                "Preencha todos os campos.";
            return;
        }

        if (!campoEmail.checkValidity()) {
            erro.textContent =
                "Informe um e-mail válido.";
            return;
        }

        if (senha !== confirmar) {
            erro.textContent =
                "As senhas não coincidem.";
            return;
        }

        erro.textContent = "";

        trocarTela("login");

        window.setTimeout(() => {
            setTriggerValue("submit", {
                tipo: "cadastro"
            });
        }, 950);
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
    """Renderiza Login e Cadastro na mesma interface."""

    _estilos_pagina()

    with st.container(key="vertice_auth_tela"):
        resultado = componente_auth(
            key="vertice_auth",
            data={
                "initialView": "login",
                "capelo": _capelo_base64(),
            },
            on_submit_change=lambda: None,
        )

    acao = resultado.submit

    if not acao:
        return

    if acao.get("tipo") == "login":
        from data.api_client import autenticar_usuario_api

        perfil = acao.get("perfil", "administrador")
        email = acao.get("email", "").strip().lower()
        senha = acao.get("senha", "")

        if perfil not in ("administrador", "professor"):
            st.error("Tipo de acesso inválido.")
            return

        if email and senha:
            resp = autenticar_usuario_api(email, senha)
            if resp.ok and isinstance(resp.dados, dict):
                usuario = resp.dados.get("usuario") or {}
                papel_api = str(usuario.get("papel", perfil)).lower()
                st.session_state["perfil"] = (
                    "administrador"
                    if papel_api in ("administrador", "gestor")
                    else "professor"
                )
                st.session_state["papel_api"] = papel_api
                st.session_state["professor_atual"] = (
                    usuario.get("nome_completo")
                    if papel_api == "professor"
                    else None
                )
                st.session_state["email_atual"] = usuario.get("email", email)
                st.session_state["logado"] = True
                st.rerun()
                return
            if not resp.indisponivel:
                st.error(resp.erro or "E-mail ou senha inválidos.")
                return

        # Modo de navegação local apenas quando o backend não estiver em execução:
        professor = None
        st.session_state["perfil"] = perfil
        st.session_state["professor_atual"] = professor
        st.session_state["email_atual"] = email
        st.session_state["logado"] = True

        st.rerun()

    elif acao.get("tipo") == "cadastro":
        st.session_state["tela_auth"] = "login"

        st.toast(
            "Cadastro demonstrativo concluído. "
            "Os dados ainda não são salvos.",
            icon="ℹ️",
        )
