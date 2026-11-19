"""Tela do Assistente IA integrada ao contexto autorizado e auditado do backend (Fase 7)."""

import base64
from pathlib import Path
from typing import Any, Optional
import uuid

import streamlit as st

from components.chat import balao
from components.layout import titulo_pagina
from data.api_client import (
    construir_contexto_assistente_api,
    consultar_assistente_ia_api,
    consultar_status_assistente_api,
    listar_estudantes_api,
    listar_turmas_api,
    possui_sessao_api_ativa,
)


PASTA_ICONS = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _icone_base64(nome: str) -> Optional[str]:
    caminho = PASTA_ICONS / nome
    if not caminho.is_file():
        return None
    return base64.b64encode(caminho.read_bytes()).decode("utf-8")


def montar_resumo_contexto_ui(contexto: dict[str, Any]) -> dict[str, Any]:
    """Extrai um resumo não-PII do pacote de contexto para consumo interno."""
    metadados = contexto.get("metadados") or {}
    ind_gerais = contexto.get("indicadores_gerais") or {}
    resumo_risco = contexto.get("resumo_previsoes_risco") or {}
    previsoes_estudante = contexto.get("previsoes_estudante") or {}
    return {
        "auditoria_id": metadados.get("auditoria_id"),
        "request_id": metadados.get("request_id"),
        "conversation_id": metadados.get("conversation_id"),
        "tipo_contexto": metadados.get("tipo_contexto"),
        "codigo_anonimo": metadados.get("codigo_anonimo"),
        "fontes_utilizadas": metadados.get("fontes_utilizadas") or [],
        "total_estudantes": ind_gerais.get("total_estudantes_distintos"),
        "frequencia_media": ind_gerais.get("frequencia_media"),
        "media_geral": ind_gerais.get("media_geral"),
        "possui_previsoes_risco": bool(
            resumo_risco.get("possui_previsoes")
            or previsoes_estudante.get("total_previsoes", 0) > 0
        ),
        "modelo_vigente": resumo_risco.get("modelo_nome_vigente"),
        "versao_vigente": resumo_risco.get("modelo_versao_vigente"),
    }


def _aplicar_estilos():
    """Mantém o layout do card e do chat responsivo."""

    st.html(
        """
        <style>
            .st-key-assistente_card {
                width: 90% !important;
                max-width: 1375px !important;
                margin: 20px auto 0 !important;
                min-width: 0 !important;
                box-sizing: border-box;
            }

            .st-key-assistente_cabecalho {
                width: 100%;
            }

            .st-key-assistente_cabecalho .assistente-header-linha {
                display: flex;
                align-items: center;
                gap: 14px;
            }

            .st-key-assistente_cabecalho .assistente-header-icone {
                width: 46px;
                height: 46px;
                border-radius: 50%;
                background: #334D8D;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
            }

            .st-key-assistente_cabecalho .assistente-header-icone img {
                width: 24px;
                height: 24px;
            }

            .st-key-assistente_cabecalho .assistente-header-titulo {
                font-size: 18px;
                font-weight: 700;
                color: #1E293B;
                line-height: 1.25;
            }

            .st-key-assistente_cabecalho .assistente-header-sub {
                font-size: 13px;
                color: #64748B;
            }

            .st-key-assistente_mensagens {
                min-height: 180px;
                max-height: 380px;
                overflow-y: auto;
                padding: 8px 4px;
            }

            .st-key-assistente_rodape [data-testid="stTextInput"] [data-baseweb="input"] {
                min-height: 46px;
                border-radius: 100px !important;
                background: #ffffff !important;
                border: 1px solid #e2e8f0 !important;
            }

            .st-key-assistente_rodape [data-testid="stFormSubmitButton"] button {
                width: 100% !important;
                min-height: 46px !important;
                background: #334D8D !important;
                color: #ffffff !important;
                border: none !important;
                border-radius: 15px !important;
                font-weight: 600 !important;
            }
        </style>
        """
    )


def render():
    """Renderiza a tela do Assistente IA conectada à camada de contexto auditado."""

    _aplicar_estilos()
    titulo_pagina("Assistente IA")

    if not possui_sessao_api_ativa():
        st.warning(
            "Autentique-se com sua conta institucional para preparar contexto autorizado e auditado."
        )
        return

    resp_status = consultar_status_assistente_api()
    if resp_status.sessao_expirada:
        st.warning(resp_status.erro or "Sua sessão expirou. Faça login novamente.")
        return
    if resp_status.sem_permissao:
        st.error(resp_status.erro or "Permissão insuficiente para acessar o Assistente IA.")
        return
    if resp_status.indisponivel:
        st.error(resp_status.erro or "Servidor do Vértice indisponível no momento.")
        return
    status_info = resp_status.dados if (resp_status.ok and isinstance(resp_status.dados, dict)) else {}
    provedor_ativo = bool(status_info.get("provedor_llm_configurado"))

    usuario_api = st.session_state.get("usuario_api") or {}
    papel = str(usuario_api.get("papel") or st.session_state.get("papel_api") or "").strip().lower()
    usuario_chave = str(usuario_api.get("id") or usuario_api.get("email") or "")
    if st.session_state.get("ia_usuario_chave") != usuario_chave:
        for chave in (
            "ia_ultimo_contexto",
            "ia_escopo_contexto",
            "chat_mensagens",
            "ia_conversation_id",
            "ia_formulario_versao",
            "ia_pergunta_pendente",
        ):
            st.session_state.pop(chave, None)
        st.session_state["ia_usuario_chave"] = usuario_chave
    st.session_state.setdefault("ia_conversation_id", str(uuid.uuid4()))
    st.session_state.setdefault("ia_formulario_versao", 0)

    with st.container(key="assistente_card", border=True):
        icone_b64 = _icone_base64("sparkles-2.svg")
        with st.container(key="assistente_cabecalho"):
            img_html = (
                f'<img src="data:image/svg+xml;base64,{icone_b64}" alt="IA">'
                if icone_b64
                else "✨"
            )
            sub_status = (
                "Seu assistente de IA para apoiar professores na leitura dos indicadores pedagógicos."
            )
            st.markdown(
                f"""
                <div class="assistente-header-linha">
                    <div class="assistente-header-icone">{img_html}</div>
                    <div>
                        <div class="assistente-header-titulo">Assistente Pedagógico Vértice</div>
                        <div class="assistente-header-sub">{sub_status}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if not provedor_ativo:
            st.warning(
                "O assistente está indisponível no momento. Verifique o serviço Ollama local "
                "e tente novamente."
            )

        if papel == "administrador":
            st.warning(
                "Perfis administrativos não podem gerar contexto pedagógico de escolas, turmas ou estudantes. "
                "Tentativas diretas na API são bloqueadas e registradas na trilha de auditoria."
            )
            return

        # Seletor real de recorte de contexto
        resp_turmas = listar_turmas_api()
        if resp_turmas.sessao_expirada:
            st.warning(resp_turmas.erro or "Sua sessão expirou. Faça login novamente.")
            return
        turmas = resp_turmas.dados if (resp_turmas.ok and isinstance(resp_turmas.dados, list)) else []
        mapa_turmas = {
            f"{t.get('nome', 'Turma')} ({t.get('ano_letivo', '')})".strip(): t.get("id")
            for t in turmas
        }

        resp_est = listar_estudantes_api(limit=200)
        if resp_est.sessao_expirada:
            st.warning(resp_est.erro or "Sua sessão expirou. Faça login novamente.")
            return
        estudantes = resp_est.dados if (resp_est.ok and isinstance(resp_est.dados, list)) else []
        mapa_est = {
            str(e.get("codigo_anonimo") or e.get("id")): e.get("id")
            for e in estudantes
        }

        col_n, col_t, col_e = st.columns(3)
        with col_n:
            nivel = st.selectbox(
                "Nível de contexto",
                options=["ESCOLA", "TURMA", "INDIVIDUAL"],
                key="ia_nivel_contexto",
            )
        with col_t:
            turma_sel = st.selectbox(
                "Turma",
                options=["(Opcional)"] + list(mapa_turmas.keys()),
                disabled=nivel != "TURMA",
                key="ia_turma_sel",
            )
        with col_e:
            est_sel = st.selectbox(
                "Estudante (código anonimizado)",
                options=["(Selecione)"] + list(mapa_est.keys()),
                disabled=nivel != "INDIVIDUAL",
                key="ia_est_sel",
            )

        escopo_selecionado = {
            "tipo_contexto": nivel,
            "turma_id": mapa_turmas.get(turma_sel) if nivel == "TURMA" else None,
            "estudante_id": mapa_est.get(est_sel) if nivel == "INDIVIDUAL" else None,
        }

        if st.button("Preparar contexto autorizado", key="ia_btn_preparar_contexto"):
            if st.session_state.get("ia_escopo_contexto") != escopo_selecionado:
                st.session_state["ia_conversation_id"] = str(uuid.uuid4())
                st.session_state.pop("chat_mensagens", None)
            turma_id = escopo_selecionado["turma_id"]
            est_id = escopo_selecionado["estudante_id"]
            if nivel == "TURMA" and not turma_id:
                st.warning("Selecione uma turma para montar contexto de turma.")
            elif nivel == "INDIVIDUAL" and not est_id:
                st.warning("Selecione um estudante anonimizado para montar contexto individual.")
            else:
                resp_ctx = construir_contexto_assistente_api(
                    tipo_contexto=nivel,
                    turma_id=turma_id,
                    estudante_id=est_id,
                    conversation_id=st.session_state["ia_conversation_id"],
                )
                if resp_ctx.ok and isinstance(resp_ctx.dados, dict):
                    st.session_state["ia_ultimo_contexto"] = resp_ctx.dados
                    st.session_state["ia_escopo_contexto"] = escopo_selecionado
                    st.success("Pronto! Já pode conversar sobre este recorte.")
                else:
                    st.session_state.pop("ia_ultimo_contexto", None)
                    st.error(
                        resp_ctx.erro
                        or "Não foi possível construir o contexto para este escopo."
                    )

        ctx_salvo = st.session_state.get("ia_ultimo_contexto")
        contexto_pronto = (
            isinstance(ctx_salvo, dict)
            and st.session_state.get("ia_escopo_contexto") == escopo_selecionado
        )
        if isinstance(ctx_salvo, dict):
            st.caption("Recorte de indicadores preparado para a conversa.")
        if isinstance(ctx_salvo, dict) and not contexto_pronto:
            st.info("O recorte foi alterado. Prepare novamente o contexto antes de conversar.")

        st.divider()

        if "chat_mensagens" not in st.session_state:
            st.session_state["chat_mensagens"] = [
                {
                    "autor": "ia",
                    "texto": (
                        "Oi! Como posso te ajudar? Posso explicar os indicadores disponíveis "
                        "e ajudar você a interpretá-los com cuidado."
                    ),
                }
            ]

        with st.container(key="assistente_mensagens"):
            for i, msg in enumerate(st.session_state["chat_mensagens"]):
                balao(msg["texto"], msg["autor"], i)

        with st.container(key="assistente_rodape"):
            c_anexo, c_conversa = st.columns([1.2, 6], gap="small")
            with c_anexo:
                with st.popover("Anexar", icon=":material/attach_file:"):
                    arquivos_carregados = st.file_uploader(
                        "Selecione arquivos para consultar",
                        type=["pdf", "docx", "txt", "csv", "xlsx"],
                        accept_multiple_files=True,
                        key=f"assistente_arquivos_{st.session_state['ia_conversation_id']}",
                        max_upload_size=5,
                    )
                    st.caption(
                        "PDF, DOCX, TXT, CSV ou XLSX; até 5 arquivos, 5 MB por arquivo "
                        "e 10 MB no total. Os anexos são processados temporariamente e "
                        "enviados ao Ollama local, que analisa até 6.000 caracteres no "
                        "total. Evite dados pessoais identificáveis."
                    )
                    if arquivos_carregados:
                        st.caption(
                            "Anexados: "
                            + ", ".join(arquivo.name for arquivo in arquivos_carregados)
                        )
                anexos_validos = (
                    len(arquivos_carregados or []) <= 5
                    and sum(arquivo.size for arquivo in (arquivos_carregados or []))
                    <= 10 * 1024 * 1024
                )
                if not anexos_validos:
                    st.error("Remova arquivos para respeitar o limite total de 5 arquivos e 10 MB.")
            with c_conversa:
                with st.form("form_chat_assistente", clear_on_submit=False):
                    c_input, c_btn = st.columns([5, 1])
                    with c_input:
                        pergunta = st.text_input(
                            "Pergunta",
                            key=f"ia_pergunta_{st.session_state['ia_formulario_versao']}",
                            label_visibility="collapsed",
                            placeholder="Pergunte sobre os indicadores do recorte preparado...",
                            disabled=(
                                not provedor_ativo
                                or not contexto_pronto
                                or "ia_pergunta_pendente" in st.session_state
                                or not anexos_validos
                            ),
                        )
                    with c_btn:
                        enviar = st.form_submit_button(
                            "Enviar",
                            disabled=(
                                not provedor_ativo
                                or not contexto_pronto
                                or "ia_pergunta_pendente" in st.session_state
                                or not anexos_validos
                            ),
                        )

            if enviar and pergunta.strip():
                mensagens_anteriores = [
                    {
                        "papel": "assistant" if mensagem["autor"] == "ia" else "user",
                        "conteudo": mensagem["texto"],
                    }
                    for mensagem in st.session_state["chat_mensagens"]
                    if not mensagem.get("erro")
                ][-12:]
                pergunta_enviada = pergunta.strip()
                st.session_state["chat_mensagens"].append(
                    {"autor": "usuario", "texto": pergunta_enviada}
                )
                st.session_state["ia_pergunta_pendente"] = {
                    "pergunta": pergunta_enviada,
                    "historico_mensagens": mensagens_anteriores,
                    "arquivos": [
                        (
                            arquivo.name,
                            arquivo.getvalue(),
                            arquivo.type or "application/octet-stream",
                        )
                        for arquivo in (arquivos_carregados or [])
                    ],
                }
                st.session_state["ia_formulario_versao"] += 1
                st.rerun()

            pergunta_pendente = st.session_state.get("ia_pergunta_pendente")
            if isinstance(pergunta_pendente, dict):
                with st.spinner(
                    "Consultando os indicadores e aguardando o assistente...",
                    show_time=True,
                ):
                    resposta = consultar_assistente_ia_api(
                        pergunta_usuario=pergunta_pendente["pergunta"],
                        tipo_contexto=nivel,
                        turma_id=escopo_selecionado["turma_id"],
                        estudante_id=escopo_selecionado["estudante_id"],
                        conversation_id=st.session_state["ia_conversation_id"],
                        historico_mensagens=pergunta_pendente["historico_mensagens"],
                        arquivos=pergunta_pendente["arquivos"],
                    )
                st.session_state.pop("ia_pergunta_pendente", None)
                texto_resposta = (
                    resposta.dados.get("resposta_texto")
                    if resposta.ok and isinstance(resposta.dados, dict)
                    else None
                )
                if isinstance(texto_resposta, str) and texto_resposta.strip():
                    texto_resposta = texto_resposta.strip()
                    fontes = resposta.dados.get("citacoes_fontes") or []
                    aviso = resposta.dados.get("aviso_responsavel")
                    if fontes:
                        texto_resposta += f"\n\nFontes: {', '.join(fontes)}."
                    if aviso:
                        texto_resposta += f"\n\n_{aviso}_"
                    st.session_state["chat_mensagens"].append(
                        {"autor": "ia", "texto": texto_resposta}
                    )
                else:
                    st.session_state["chat_mensagens"].append(
                        {
                            "autor": "ia",
                            "texto": (
                                "Não foi possível responder: "
                                + (
                                    resposta.erro
                                    or "o servidor não retornou uma resposta válida."
                                )
                            ),
                            "erro": True,
                        }
                    )
                st.rerun()
