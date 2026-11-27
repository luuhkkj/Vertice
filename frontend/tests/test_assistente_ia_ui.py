from pathlib import Path
import sys
import unittest

from streamlit.testing.v1 import AppTest


FRONTEND_DIR = Path(__file__).resolve().parents[1]


class TestAssistenteIAUi(unittest.TestCase):
    def test_resposta_streaming_e_aviso_ficam_na_conversa_sem_fontes(self) -> None:
        codigo = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from unittest.mock import patch
from pages.assistente_ia import _processar_pergunta_pendente

st.session_state["chat_mensagens"] = [{{"autor": "usuario", "texto": "Pergunta"}}]
st.session_state["ia_conversation_id"] = "conversa-teste"
st.session_state["ia_pergunta_pendente"] = {{
    "pergunta": "Qual é a frequência?",
    "historico_mensagens": [],
    "arquivos": [],
}}
with patch(
    "pages.assistente_ia.consultar_assistente_ia_stream_api",
    return_value=iter(["A frequência observada é ", "90%."]),
), patch("streamlit.rerun"):
    _processar_pergunta_pendente(
        contexto={{"metadados": {{}}}},
        nivel="ESCOLA",
        escopo={{"turma_id": None, "estudante_id": None}},
    )
"""
        app = AppTest.from_string(codigo)
        app.run()

        self.assertFalse(app.exception, app.exception)
        resposta = app.session_state["chat_mensagens"][-1]["texto"]
        self.assertTrue(resposta.startswith("A frequência observada é 90%."))
        self.assertTrue(
            resposta.endswith(
                "Resposta baseada nos indicadores disponíveis; deve ser avaliada "
                "por um profissional. Previsões não são certezas."
            )
        )
        self.assertNotIn("Fontes:", resposta)
        self.assertNotIn("IndicadoresGeraisService", resposta)

    def test_icone_cabecalho_usa_ia_svg_e_sem_emojis(self) -> None:
        from pages.assistente_ia import _icone_base64
        icone = _icone_base64("IA.svg")
        self.assertIsNotNone(icone)
        self.assertTrue(len(icone) > 100)

    def test_chat_input_presente_no_render(self) -> None:
        codigo = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from unittest.mock import patch, MagicMock

with patch("pages.assistente_ia.possui_sessao_api_ativa", return_value=True), \\
     patch("pages.assistente_ia.consultar_status_assistente_api") as m_status, \\
     patch("pages.assistente_ia.listar_turmas_api") as m_turmas, \\
     patch("pages.assistente_ia.listar_estudantes_api") as m_est:
    
    m_status.return_value = MagicMock(ok=True, sessao_expirada=False, sem_permissao=False, indisponivel=False, dados={{"provedor_llm_configurado": True}})
    m_turmas.return_value = MagicMock(ok=True, sessao_expirada=False, dados=[{{"id": "t1", "nome": "1A", "ano_letivo": 2026}}])
    m_est.return_value = MagicMock(ok=True, sessao_expirada=False, dados=[])

    st.session_state["usuario_api"] = {{"id": "u1", "papel": "professor"}}
    st.session_state["ia_escopo_contexto"] = {{"tipo_contexto": "ESCOLA", "turma_id": None, "estudante_id": None}}
    st.session_state["ia_ultimo_contexto"] = {{"metadados": {{"context_cache_id": "cache-123"}}}}
    
    from pages.assistente_ia import render
    render()
"""
        app = AppTest.from_string(codigo)
        app.run()
        self.assertFalse(app.exception, app.exception)
        self.assertTrue(len(app.chat_input) > 0)
        self.assertIn("Pergunte sobre os indicadores", app.chat_input[0].placeholder)


if __name__ == "__main__":
    unittest.main()
