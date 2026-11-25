"""Testes end-to-end reais do frontend Streamlit (`AppTest`) cobrindo BUG-02, BUG-03 e escolas sem dados."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

import httpx
from streamlit.testing.v1 import AppTest

FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

import data.api_client as api_client  # noqa: E402
from components import auth_animada  # noqa: E402


def _resposta_padrao_escola_vazia(
    papel: str = "gestor",
    escola_id: str | None = "escola-vazia-1",
    nome_escola: str = "Escola Nova Sem Dados",
    com_boletim_sem_metrica: bool = False,
    indicadores_custom: dict | None = None,
    turmas_custom: list | None = None,
    disciplinas_custom: list | None = None,
    atividades_custom: list | None = None,
    previsoes_custom: list | None = None,
):
    """Retorna um transporte HTTPX determinístico para o `AppTest` de ponta a ponta."""
    uid = "user-teste-1"

    def _handler(
        method: str,
        url: str,
        *,
        headers=None,
        params=None,
        json=None,
        files=None,
        timeout: float = 15.0,
    ) -> httpx.Response:
        _ = (headers, params, json, files, timeout)
        path = httpx.URL(url).path

        if path.endswith("/auth/me"):
            return httpx.Response(
                200,
                json={
                    "id": uid,
                    "nome": f"Usuário {papel.title()}",
                    "email": f"{papel}@vertice.edu.br",
                    "papel": papel,
                    "escola_id": escola_id,
                    "ativo": True,
                },
            )
        if path.endswith("/admin/resumo-operacional"):
            return httpx.Response(
                200,
                json={
                    "total_usuarios": 3,
                    "usuarios_ativos": 3,
                    "usuarios_por_papel": {"administrador": 1, "gestor": 1, "professor": 1},
                    "total_escolas": 1,
                    "escolas_ativas": 1,
                    "total_turmas": 1,
                    "turmas_ativas": 1,
                    "total_disciplinas": 1,
                    "disciplinas_ativas": 1,
                    "total_credenciais_ml": 0,
                    "credenciais_ml_ativas": 0,
                    "total_eventos_auditoria_tecnica": 1,
                    "total_eventos_auditoria_ia": 0,
                    "provedor_llm_configurado": False,
                },
            )
        if path.endswith("/admin/auditoria-tecnica"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "aud-1",
                        "usuario_ator_id": uid,
                        "papel_ator": "administrador",
                        "acao": "USUARIO_CRIADO",
                        "entidade": "usuario",
                        "entidade_id": uid,
                        "detalhes": {"papel": "gestor", "ativo": True},
                        "criado_em": "2026-11-18T00:00:00Z",
                    }
                ],
            )
        if path.endswith("/usuarios"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": uid,
                        "nome": "Admin Rede",
                        "email": "admin@vertice.edu.br",
                        "papel": "administrador",
                        "escola_id": None,
                        "ativo": True,
                    }
                ],
            )
        if path.endswith("/previsoes/credenciais"):
            return httpx.Response(200, json=[])
        if path.endswith("/assistente/auditoria"):
            return httpx.Response(200, json=[])
        if "/escolas/" in path:
            return httpx.Response(
                200,
                json={
                    "id": escola_id or "escola-1",
                    "nome": nome_escola,
                    "codigo": "ESC01",
                    "ativo": True,
                },
            )
        if path.endswith("/escolas"):
            return httpx.Response(
                200,
                json=[{"id": "escola-1", "nome": nome_escola, "codigo": "ESC01", "ativo": True}],
            )
        if path.endswith("/turmas"):
            return httpx.Response(200, json=turmas_custom if turmas_custom is not None else [])
        if path.endswith("/disciplinas"):
            return httpx.Response(200, json=disciplinas_custom if disciplinas_custom is not None else [])
        if path.endswith("/indicadores/gerais"):
            if indicadores_custom is not None:
                return httpx.Response(200, json=indicadores_custom)
            if com_boletim_sem_metrica:
                return httpx.Response(
                    200,
                    json={
                        "total_estudantes_distintos": 2,
                        "total_registros_boletim": 2,
                        "frequencia_media": None,
                        "media_geral": None,
                        "distribuicao_por_serie": [
                            {
                                "chave": "1º Ano",
                                "total_estudantes": 2,
                                "percentual_estudantes": 100.0,
                                "frequencia_media": None,
                                "media_geral": None,
                            }
                        ],
                        "distribuicao_por_turma": [],
                        "distribuicao_por_turno": [],
                        "evolucao_por_periodo": [],
                        "possui_previsoes_risco": False,
                        "distribuicao_faixas_risco": [],
                    },
                )
            return httpx.Response(
                200,
                json={
                    "total_estudantes_distintos": 0,
                    "total_registros_boletim": 0,
                    "frequencia_media": None,
                    "media_geral": None,
                    "distribuicao_por_serie": [],
                    "distribuicao_por_turma": [],
                    "distribuicao_por_turno": [],
                    "evolucao_por_periodo": [],
                    "possui_previsoes_risco": False,
                    "distribuicao_faixas_risco": [],
                },
            )
        if path.endswith("/indicadores/participacao"):
            return httpx.Response(
                200,
                json={
                    "total_atividades": len(atividades_custom or []),
                    "total_entregas_esperadas": 0,
                    "entregas_realizadas": 0,
                    "entregas_no_prazo": 0,
                    "entregas_atrasadas": 0,
                    "nao_entregas_apos_prazo": 0,
                    "atividades_pendentes_antes_prazo": 0,
                    "taxa_entrega_geral_percentual": None,
                    "media_notas_disponiveis": None,
                    "taxa_por_atividade": [],
                    "taxa_por_turma": [],
                    "percentual_por_estudante": [],
                    "evolucao_participacao": [],
                },
            )
        if path.endswith("/atividades"):
            return httpx.Response(200, json=atividades_custom if atividades_custom is not None else [])
        if path.endswith("/previsoes"):
            return httpx.Response(200, json=previsoes_custom if previsoes_custom is not None else [])
        if path.endswith("/assistente/status"):
            return httpx.Response(
                200,
                json={
                    "provedor_llm_configurado": False,
                    "modo_operacao": "preparacao_contexto",
                    "niveis_contexto_suportados": ["ESCOLA", "TURMA", "INDIVIDUAL"],
                    "auditoria_ativa": True,
                    "mensagem": "Contexto estruturado ativo.",
                },
            )
        return httpx.Response(200, json=[])

    return _handler


def _iniciar_app_autenticado(
    papel: str,
    transport_fn,
    *,
    escola_id: str | None = "escola-vazia-1",
    url_path: str | None = None,
) -> AppTest:
    """Inicializa `app.py` no `AppTest` com sessão autenticada para o papel informado."""
    api_client.configurar_cliente_http_teste(transport_fn)
    kwargs = {"default_timeout": 15}
    at = AppTest.from_file(str(FRONTEND_DIR / "app.py"), **kwargs)
    at.session_state["logado"] = True
    at.session_state["access_token"] = f"tok-{papel}-{uuid.uuid4()}"
    at.session_state["usuario_api"] = {
        "id": "user-teste-1",
        "nome": f"Usuário {papel.title()}",
        "email": f"{papel}@vertice.edu.br",
        "papel": papel,
        "escola_id": escola_id,
        "ativo": True,
    }
    at.session_state["perfil"] = papel
    at.session_state["papel_api"] = papel
    if escola_id:
        at.session_state["escola_id_atual"] = escola_id
    if url_path:
        at.query_params.clear()
        at._page = url_path
    return at


def _iniciar_perfil_autenticado(papel: str, transport_fn, escola_id: str | None) -> AppTest:
    """Renderiza somente a tela de perfil no AppTest com identidade autenticada."""
    api_client.configurar_cliente_http_teste(transport_fn)
    snippet = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from pages import perfil
perfil.render()
"""
    at = AppTest.from_string(snippet, default_timeout=10)
    at.session_state["logado"] = True
    at.session_state["access_token"] = f"tok-{papel}-{uuid.uuid4()}"
    at.session_state["usuario_api"] = {
        "id": "user-teste-1",
        "nome": f"Usuário {papel.title()}",
        "email": f"{papel}@vertice.edu.br",
        "papel": papel,
        "escola_id": escola_id,
        "ativo": True,
    }
    at.session_state["perfil"] = papel
    at.session_state["papel_api"] = papel
    at.run()
    return at


def _chaves_blocos(at: AppTest) -> list[str]:
    return [getattr(bloco, "key", None) for bloco in at.main if getattr(bloco, "key", None)]


class TestFrontendStreamlitE2E(unittest.TestCase):
    """Suíte real com Streamlit `AppTest` validando UI, cartões, perfis e navegação."""

    def tearDown(self) -> None:
        api_client.configurar_cliente_http_teste(None)

    def test_autenticacao_publica_mantem_apenas_login(self) -> None:
        interface = auth_animada.HTML + auth_animada.JS

        self.assertIn('id="v-login-email"', interface)
        self.assertIn('id="v-login-senha"', interface)
        self.assertIn('id="v-entrar"', interface)
        self.assertNotIn("cadastro", interface.lower())

    def test_criar_avaliacao_envia_status_aceito_pela_api(self) -> None:
        with patch("data.api_client.requisitar_api") as requisitar:
            api_client.criar_avaliacao_api(
                titulo="Prova de Matemática",
                turma_id="turma-1",
                disciplina_id="disciplina-1",
                periodo_letivo="1º Bimestre",
                data_avaliacao="2026-11-24",
            )

        payload = requisitar.call_args.kwargs["json_body"]
        self.assertEqual(payload["status"], "PUBLICADA")

    def test_componente_card_renderiza_titulo_subtitulo_e_rejeita_vazio(self) -> None:
        snippet = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from components.cards import card

with card("Frequência observada por série"):
    st.write("Conteúdo 1")

with card("Atividade ATV-01", subtitulo="Turma 1A | MAT", chave="atividade_detalhe"):
    st.write("Conteúdo 2")
"""
        at = AppTest.from_string(snippet, default_timeout=10)
        at.run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(
            [s.value for s in at.subheader],
            ["Frequência observada por série", "Atividade ATV-01"],
        )
        self.assertEqual([c.value for c in at.caption], ["Turma 1A | MAT"])
        keys = _chaves_blocos(at)
        self.assertIn("card_frequencia_observada_por_serie", keys)
        self.assertIn("card_atividade_detalhe", keys)

        from components.cards import card

        with self.assertRaises(TypeError):
            card()  # type: ignore[call-arg]
        with self.assertRaises(ValueError):
            card("   ")

    def test_administrador_menu_personalizado_e_perfil(self) -> None:
        transport = _resposta_padrao_escola_vazia(
            papel="administrador",
            escola_id=None,
            turmas_custom=[{"id": "t1", "nome": "1A", "serie": "1º Ano", "turno": "Matutino", "ano_letivo": 2026, "escola_id": "escola-1", "ativo": True}],
        )
        at = _iniciar_app_autenticado("administrador", transport, escola_id=None)
        at.run()
        self.assertFalse(at.exception, at.exception)
        keys = _chaves_blocos(at)
        self.assertIn("cabecalho", keys)
        self.assertIn("vertice_menu_lateral", keys)
        self.assertIn("menu_ativo_visao_geral", keys)
        for item in (
            "menu_usuarios_e_contas",
            "menu_escolas_turmas_disciplinas",
            "menu_credenciais_ml",
            "menu_auditoria_tecnica_ia",
        ):
            self.assertIn(item, keys)
        self.assertIn("menu_meu_perfil", keys)
        self.assertNotIn("menu_atribuir_turmas", keys)
        self.assertNotIn("menu_entrada_de_dados", keys)
        self.assertIn("Visão geral", [t.value for t in at.title])
        self.assertIn("admin_workspace", keys)

        paginas_admin = (
            ("usuarios-e-contas", "Usuários e Contas", "Contas cadastradas na plataforma"),
            (
                "escolas-turmas-disciplinas",
                "Escolas, Turmas e Disciplinas",
                "Unidades Escolares",
            ),
            ("credenciais-ml", "Credenciais ML", "Emitir nova credencial ML"),
            (
                "auditoria-tecnica-ia",
                "Auditoria Técnica e IA",
                "Trilha de auditoria técnica administrativa",
            ),
        )
        for url_path, titulo, secao in paginas_admin:
            page_link = next(
                link
                for link in at.page_link
                if link.value == titulo
            )
            at._page_hash = page_link.proto.page_script_hash
            at.run()
            self.assertFalse(at.exception, at.exception)
            self.assertIn(titulo, [item.value for item in at.title])
            self.assertIn(secao, [item.value for item in at.subheader])
            self.assertIn(
                f"menu_ativo_{url_path.replace('-', '_')}",
                _chaves_blocos(at),
            )

        self.assertIn("Meu Perfil", [link.value for link in at.page_link])
        self.assertNotIn("botao_perfil_cabecalho", [button.key for button in at.button])
        at_perfil = _iniciar_perfil_autenticado("administrador", transport, escola_id=None)
        self.assertFalse(at_perfil.exception, at_perfil.exception)
        self.assertIn("Meu Perfil", [item.value for item in at_perfil.title])
        self.assertIn("perfil_informacoes", _chaves_blocos(at_perfil))

    def test_gestor_escola_sem_dados_e_navegacao_completa(self) -> None:
        transport = _resposta_padrao_escola_vazia(papel="gestor")
        at = _iniciar_app_autenticado("gestor", transport)
        at.run()
        self.assertFalse(at.exception, at.exception)

        keys = _chaves_blocos(at)
        self.assertEqual(keys.count("cabecalho"), 1)
        self.assertEqual(keys.count("vertice_menu_lateral"), 1)
        self.assertIn("gestor_workspace", keys)
        self.assertIn("menu_ativo_visao_geral", keys)
        for esperado in (
            "menu_estudantes",
            "menu_entrada_de_dados",
            "menu_assistente_ia",
            "menu_atribuir_turmas",
            "menu_meu_perfil",
        ):
            self.assertIn(esperado, keys)
        self.assertNotIn("menu_mapa_de_acertos", keys)
        self.assertNotIn("menu_participacao", keys)
        self.assertNotIn("Mapa de Acertos", [link.value for link in at.page_link])
        self.assertNotIn("Participação", [link.value for link in at.page_link])

        # Visão Geral sem dados: 4 cartões com títulos únicos (sem duplicação) e mensagens informativas
        subheaders = [s.value for s in at.subheader]
        self.assertEqual(
            subheaders,
            [
                "Frequência observada por série",
                "Distribuição preditiva de risco",
                "Média observada por série",
                "Evolução longitudinal observada",
            ],
        )
        self.assertTrue(
            any("Ainda não há dados escolares importados" in info.value for info in at.info)
        )

        # Navega para todas as páginas autorizadas do Gestor em escola vazia via st.navigation
        for titulo, url_path, mod_nome in [
            ("Estudantes", "estudantes", "estudantes"),
            ("Entrada de Dados", "entrada-de-dados", "entrada_dados"),
            ("Assistente IA", "assistente-ia", "assistente_ia"),
            ("Atribuir turmas", "atribuir-turmas", "atribuicao"),
            ("Meu Perfil", "perfil", "perfil"),
        ]:
            snippet = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from components.estilos import carregar_estilos
from components.layout import render_header, render_sidebar
from pages import {mod_nome} as pagina_modulo

st.set_page_config(page_title="Vértice", layout="wide")
carregar_estilos()
pagina_atual = st.Page(pagina_modulo.render, title={titulo!r}, url_path={url_path!r}, default=True)
paginas_menu = [pagina_atual, st.Page(lambda: None, title="Meu Perfil", url_path="perfil")] if {url_path!r} != "perfil" else [pagina_atual]
st.navigation([pagina_atual], position="hidden")
render_header(paginas_menu)
render_sidebar(paginas_menu, pagina_atual)
pagina_atual.run()
"""
            at_sub = AppTest.from_string(snippet, default_timeout=15)
            at_sub.session_state["logado"] = True
            at_sub.session_state["access_token"] = "tok-gestor-sub"
            at_sub.session_state["usuario_api"] = {
                "id": "user-teste-1",
                "nome": "Usuário Gestor",
                "email": "gestor@vertice.edu.br",
                "papel": "gestor",
                "escola_id": "escola-vazia-1",
                "ativo": True,
            }
            at_sub.session_state["perfil"] = "gestor"
            at_sub.session_state["papel_api"] = "gestor"
            at_sub.session_state["escola_id_atual"] = "escola-vazia-1"
            at_sub.run()
            self.assertFalse(
                at_sub.exception,
                f"Falha ao renderizar {mod_nome} para Gestor sem dados: {at_sub.exception}",
            )
            keys_sub = _chaves_blocos(at_sub)
            self.assertIn("cabecalho", keys_sub)
            self.assertIn("vertice_menu_lateral", keys_sub)

    def test_visao_geral_com_dados_e_risco_preditivo_e_sem_metricas_nulas(self) -> None:
        # 1) Escola com dados e previsões (cobre também grafico_rosca com 4 argumentos!)
        indicadores_cheios = {
            "total_estudantes_distintos": 45,
            "total_registros_boletim": 90,
            "frequencia_media": 88.5,
            "media_geral": 7.4,
            "distribuicao_por_serie": [
                {
                    "chave": "1º Ano",
                    "total_estudantes": 25,
                    "percentual_estudantes": 55.6,
                    "frequencia_media": 90.0,
                    "media_geral": 7.8,
                },
                {
                    "chave": "2º Ano",
                    "total_estudantes": 20,
                    "percentual_estudantes": 44.4,
                    "frequencia_media": 86.5,
                    "media_geral": 6.9,
                },
            ],
            "evolucao_por_periodo": [
                {
                    "ano_letivo": 2026,
                    "periodo_letivo": "1º Bimestre",
                    "total_estudantes": 45,
                    "frequencia_media": 88.5,
                    "media_geral": 7.4,
                }
            ],
            "possui_previsoes_risco": True,
            "distribuicao_faixas_risco": [
                {"faixa": "BAIXO", "quantidade": 20, "percentual": 44.4},
                {"faixa": "MODERADO", "quantidade": 17, "percentual": 37.8},
                {"faixa": "ALTO", "quantidade": 6, "percentual": 13.3},
                {"faixa": "CRITICO", "quantidade": 2, "percentual": 4.5},
            ],
            "modelo_nome_vigente": "XGBoost-Vertice",
            "modelo_versao_vigente": "1.2",
            "ultima_previsao_em": "2026-11-10T10:00:00Z",
        }
        previsoes = [
            {
                "estudante_id": "e1",
                "codigo_anonimo": "EST-001",
                "turma_nome": "1º Ano A",
                "ano_letivo": 2026,
                "periodo_letivo": "1º Bimestre",
                "faixa_risco": "CRITICO",
                "pontuacao_risco": 0.912,
                "modelo_nome": "XGBoost-Vertice",
                "modelo_versao": "1.2",
            }
        ]
        transport_cheio = _resposta_padrao_escola_vazia(
            papel="gestor",
            indicadores_custom=indicadores_cheios,
            previsoes_custom=previsoes,
            turmas_custom=[{"id": "t1", "nome": "1º Ano A", "ano_letivo": 2026}],
            disciplinas_custom=[{"id": "d1", "nome": "Matemática", "codigo": "MAT"}],
        )
        at = _iniciar_app_autenticado("gestor", transport_cheio)
        at.run()
        self.assertFalse(at.exception, at.exception)
        metricas = {m.label: m.value for m in at.metric}
        self.assertEqual(metricas["Estudantes distintos"], "45")
        self.assertEqual(metricas["Frequência média observada"], "88,5%")
        self.assertEqual(metricas["Média geral observada"], "7,4")
        self.assertEqual(metricas["Risco elevado (preditivo)"], "8")
        self.assertEqual(metricas["Frequência média"], "88.5%")
        self.assertEqual(metricas["Média geral"], "7.40")
        self.assertTrue(
            any(
                "A tendência será exibida quando houver mais períodos" in c.value
                for c in at.caption
            )
        )
        self.assertEqual(
            [s.value for s in at.subheader],
            [
                "Frequência observada por série",
                "Distribuição preditiva de risco",
                "Média observada por série",
                "Evolução longitudinal observada",
                "Estudantes com estimativa preditiva de risco elevado",
            ],
        )

        # 2) Boletins importados sem frequência/média numérica: não inventa 0.0% nem falha
        transport_nulo = _resposta_padrao_escola_vazia(
            papel="gestor",
            com_boletim_sem_metrica=True,
        )
        at_nulo = _iniciar_app_autenticado("gestor", transport_nulo)
        at_nulo.run()
        self.assertFalse(at_nulo.exception, at_nulo.exception)
        self.assertTrue(
            any("Sem boletins com registros de frequência" in i.value for i in at_nulo.info)
        )
        self.assertTrue(
            any("Sem registros de médias por série" in i.value for i in at_nulo.info)
        )

        # 3) Resposta vazia `{}` da API de indicadores: carrega sem exceção
        transport_vazio = _resposta_padrao_escola_vazia(
            papel="gestor",
            indicadores_custom={},
        )
        at_vazio = _iniciar_app_autenticado("gestor", transport_vazio)
        at_vazio.run()
        self.assertFalse(at_vazio.exception, at_vazio.exception)

    def test_professor_renderiza_menu_visao_geral_participacao_e_perfil(self) -> None:
        ativs = [
            {
                "id": "atv-1",
                "codigo": "ATV-01",
                "titulo": "Lista 1",
                "turma_id": "t1",
                "disciplina_id": "d1",
                "turma_nome": "1A",
                "disciplina_codigo": "MAT",
                "periodo_letivo": "1º Bimestre",
                "data_limite": "2026-06-01",
                "nota_maxima": 10.0,
                "status": "ABERTA",
            }
        ]
        transport = _resposta_padrao_escola_vazia(
            papel="professor",
            turmas_custom=[{"id": "t1", "nome": "1A", "serie": "1º Ano", "ano_letivo": 2026, "ativo": True}],
            disciplinas_custom=[{"id": "d1", "nome": "Matemática", "codigo": "MAT", "ativo": True}],
            atividades_custom=ativs,
        )
        at = _iniciar_app_autenticado("professor", transport)
        at.run()
        self.assertFalse(at.exception, at.exception)
        keys = _chaves_blocos(at)
        self.assertIn("cabecalho", keys)
        self.assertIn("vertice_menu_lateral", keys)
        self.assertIn("menu_ativo_visao_geral", keys)
        self.assertIn("professor_workspace", keys)
        self.assertNotIn("menu_administracao_tecnica", keys)
        self.assertNotIn("menu_entrada_de_dados", keys)
        self.assertNotIn("menu_atribuir_turmas", keys)
        self.assertIn("menu_mapa_de_acertos", keys)
        self.assertIn("menu_participacao", keys)
        self.assertIn("menu_meu_perfil", keys)

        self.assertIn("Meu Perfil", [link.value for link in at.page_link])
        self.assertIn("Mapa de Acertos", [link.value for link in at.page_link])
        self.assertIn("Participação", [link.value for link in at.page_link])
        self.assertNotIn("botao_perfil_cabecalho", [button.key for button in at.button])
        at_perfil = _iniciar_perfil_autenticado("professor", transport, escola_id="escola-vazia-1")
        self.assertFalse(at_perfil.exception, at_perfil.exception)
        self.assertIn("Meu Perfil", [item.value for item in at_perfil.title])

        # Renderiza Participação com atividade real (exercita card(titulo, subtitulo=...) e card_kpi!)
        snippet_part = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from components.estilos import carregar_estilos
from components.layout import render_header, render_sidebar
from pages import participacao, perfil

st.set_page_config(page_title="Vértice", layout="wide")
carregar_estilos()
pagina_part = st.Page(participacao.render, title="Participação", url_path="participacao", default=True)
paginas_menu = [pagina_part, st.Page(perfil.render, title="Meu Perfil", url_path="perfil")]
st.navigation([pagina_part], position="hidden")
render_header(paginas_menu)
render_sidebar(paginas_menu, pagina_part)
pagina_part.run()
"""
        at_part = AppTest.from_string(snippet_part, default_timeout=15)
        at_part.session_state["logado"] = True
        at_part.session_state["access_token"] = "tok-prof-part"
        at_part.session_state["usuario_api"] = {
            "id": "user-teste-1",
            "nome": "Usuário Professor",
            "email": "professor@vertice.edu.br",
            "papel": "professor",
            "escola_id": "escola-vazia-1",
            "ativo": True,
        }
        at_part.session_state["perfil"] = "professor"
        at_part.session_state["papel_api"] = "professor"
        at_part.session_state["escola_id_atual"] = "escola-vazia-1"
        at_part.run()
        self.assertFalse(at_part.exception, at_part.exception)
        self.assertIn("card_atividade_detalhe", _chaves_blocos(at_part))
        self.assertEqual([c.value for c in at_part.caption if "Turma: 1A" in c.value], ["Turma: 1A | Disciplina: MAT | Período: 1º Bimestre"])

    def test_excecao_em_pagina_preserva_menu_lateral_e_cabecalho_no_apptest(self) -> None:
        transport = _resposta_padrao_escola_vazia(papel="gestor")
        with patch("pages.visao_geral.render", side_effect=RuntimeError("Falha simulada na página")):
            at = _iniciar_app_autenticado("gestor", transport)
            at.run()
            self.assertFalse(at.exception, at.exception)
            keys = _chaves_blocos(at)
            self.assertEqual(keys.count("cabecalho"), 1)
            self.assertEqual(keys.count("vertice_menu_lateral"), 1)
            self.assertIn("menu_ativo_visao_geral", keys)
            self.assertIn("menu_meu_perfil", keys)
            self.assertTrue(
                any("Ocorreu um erro inesperado ao carregar esta página." in e.value for e in at.error)
            )
            self.assertTrue(
                any("RuntimeError" in c.value and "Falha simulada na página" in c.value for c in at.caption)
            )

    def test_bloqueio_visual_por_papel_em_paginas_restritas(self) -> None:
        transport_gestor = _resposta_padrao_escola_vazia(papel="gestor")
        api_client.configurar_cliente_http_teste(transport_gestor)
        snippet_admin_page = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from pages import administracao_tecnica
st.session_state["logado"] = True
st.session_state["usuario_api"] = {{"id": "u1", "papel": "gestor", "escola_id": "e1"}}
st.session_state["perfil"] = "gestor"
administracao_tecnica.render()
"""
        at_g = AppTest.from_string(snippet_admin_page, default_timeout=10)
        at_g.run()
        self.assertFalse(at_g.exception, at_g.exception)
        self.assertTrue(any("Permissão insuficiente" in e.value for e in at_g.error))

        snippet_atrib_adm = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from pages import atribuicao
st.session_state["logado"] = True
st.session_state["usuario_api"] = {{"id": "u0", "papel": "administrador", "escola_id": None}}
st.session_state["perfil"] = "administrador"
atribuicao.render()
"""
        at_a = AppTest.from_string(snippet_atrib_adm, default_timeout=10)
        at_a.run()
        self.assertFalse(at_a.exception, at_a.exception)
        self.assertTrue(any("Permissão insuficiente" in e.value for e in at_a.error))

        snippet_entrada_prof = f"""
import sys
sys.path.insert(0, {str(FRONTEND_DIR)!r})
import streamlit as st
from pages import entrada_dados
st.session_state["logado"] = True
st.session_state["usuario_api"] = {{"id": "u2", "papel": "professor"}}
st.session_state["perfil"] = "professor"
entrada_dados.render()
"""
        at_p = AppTest.from_string(snippet_entrada_prof, default_timeout=10)
        at_p.run()
        self.assertFalse(at_p.exception, at_p.exception)
        self.assertTrue(any("Permissão insuficiente" in e.value for e in at_p.error))


if __name__ == "__main__":
    unittest.main()
