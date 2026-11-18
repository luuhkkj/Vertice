"""
Testes automatizados de estabilidade do frontend:
- Contrato e chamadas de `card()`, `card_kpi()` e `grafico_rosca()` (BUG-02 e correlatos)
- Proteção do cabeçalho e menu lateral personalizado em `app.py` (BUG-03)
- Comportamento da `Visão geral` com dados reais, escola sem dados e respostas vazias/nulas
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.escolas.models import Escola
from app.modules.usuarios.models import PapelUsuario, Usuario
from app.core.security import get_password_hash
from tests.test_fase4_modulos_pedagogicos import _criar_cenario_fase4
from tests.test_fase8_integracao_final import (
    _adaptar_testclient_completo,
    _carregar_frontend_app,
    _preparar_frontend,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "Frontend vertice"


def _instalar_metodos_container_stub(st_mod: Any) -> list[dict[str, Any]]:
    """Instrumenta `st.container`, `subheader`, `caption`, `metric`, `info/error` e `go.Figure`."""
    registros: list[dict[str, Any]] = []

    go_mod = sys.modules.get("plotly.graph_objects")
    if go_mod is not None and not hasattr(go_mod, "Figure"):

        class _FakeGoFigure:
            def __init__(self, *_a: Any, **_kw: Any) -> None:
                self.layout: dict[str, Any] = {}

            def update_layout(self, **kwargs: Any) -> "_FakeGoFigure":
                self.layout.update(kwargs)
                return self

        go_mod.Figure = _FakeGoFigure

    class _BoxStub:
        def __init__(self, key: str | None = None, border: bool | None = None) -> None:
            self.key = key
            self.border = border
            self.subheaders: list[str] = []
            self.captions: list[str] = []
            self.metrics: list[tuple[Any, Any]] = []

        def __enter__(self) -> "_BoxStub":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def subheader(self, texto: Any, **_kw: Any) -> None:
            self.subheaders.append(str(texto))

        def caption(self, texto: Any, **_kw: Any) -> None:
            self.captions.append(str(texto))

        def metric(self, *, label: Any, value: Any) -> None:
            self.metrics.append((label, value))

    def _container(*, key: str | None = None, border: bool | None = None, **_kw: Any) -> _BoxStub:
        box = _BoxStub(key=key, border=border)
        registros.append({"tipo": "container", "key": key, "box": box})
        return box

    def _registrar(tipo: str):
        def _fn(msg: Any = "", *args: Any, **kwargs: Any) -> Any:
            registros.append({"tipo": tipo, "mensagem": msg, "args": args, "kwargs": kwargs})
            return None

        return _fn

    st_mod.container = _container
    st_mod.columns = lambda spec, **_kw: [
        _BoxStub(key=f"col_{i}") for i in range(spec if isinstance(spec, int) else len(spec))
    ]
    st_mod.metric = lambda *, label, value, **_kw: registros.append(
        {"tipo": "metric", "label": label, "value": value}
    )
    st_mod.selectbox = lambda label, options=(), **_kw: (list(options)[0] if options else None)
    st_mod.text_input = lambda label, value="", **_kw: value
    st_mod.plotly_chart = _registrar("plotly_chart")
    st_mod.dataframe = _registrar("dataframe")
    st_mod.caption = _registrar("caption")
    st_mod.subheader = _registrar("subheader")
    st_mod.info = _registrar("info")
    st_mod.warning = _registrar("warning")
    st_mod.error = _registrar("error")
    st_mod.title = _registrar("title")
    st_mod.markdown = _registrar("markdown")
    st_mod.page_link = _registrar("page_link")
    st_mod.button = lambda *_a, **_kw: False
    st_mod.switch_page = _registrar("switch_page")
    return registros


# ==============================================================================
# 1. CONTRATO ESTÁTICO E EM TEMPO DE EXECUÇÃO DE `card()`, `card_kpi()`, `grafico_rosca()`
# ==============================================================================


def test_ast_todas_chamadas_componentes_frontend_sem_divergencia_de_assinatura() -> None:
    """Garante que todas as chamadas de componentes em `Frontend vertice/` respeitam suas assinaturas."""
    definicoes: dict[str, tuple[str, int, int, list[str], list[str], set[str], bool, bool]] = {}
    for subpasta in ("components", "data", "utils"):
        for arq in (FRONTEND_DIR / subpasta).glob("*.py"):
            arvore = ast.parse(arq.read_text(encoding="utf-8"))
            for node in arvore.body:
                if isinstance(node, ast.FunctionDef):
                    pos_args = [a.arg for a in node.args.args]
                    kw_args = [a.arg for a in node.args.kwonlyargs]
                    mn_pos = len(pos_args) - len(node.args.defaults)
                    req_kw = [
                        a.arg
                        for a, d in zip(
                            node.args.kwonlyargs,
                            node.args.kw_defaults,
                            strict=True,
                        )
                        if d is None
                    ]
                    definicoes[node.name] = (
                        f"{subpasta}/{arq.name}",
                        mn_pos,
                        len(pos_args),
                        pos_args,
                        req_kw,
                        set(pos_args + kw_args),
                        bool(node.args.vararg),
                        bool(node.args.kwarg),
                    )

    alvos = (
        list((FRONTEND_DIR / "pages").glob("*.py"))
        + list((FRONTEND_DIR / "components").glob("*.py"))
        + [FRONTEND_DIR / "app.py"]
    )
    erros: list[str] = []
    chamadas_card_vg = 0

    for arq in sorted(alvos):
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for node in ast.walk(arvore):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in definicoes
            ):
                nome_fn = node.func.id
                _, mn_pos, mx_pos, pos_args, req_kw, all_set, has_va, has_kw = definicoes[nome_fn]
                n_pos = len(node.args)
                kws = [k.arg for k in node.keywords if k.arg]
                if not has_va and n_pos > mx_pos:
                    erros.append(f"{arq.name}:{node.lineno} {nome_fn}: {n_pos} posicionais (max {mx_pos})")
                if not has_kw:
                    ruins = [k for k in kws if k not in all_set]
                    if ruins:
                        erros.append(f"{arq.name}:{node.lineno} {nome_fn}: kwargs inválidos {ruins}")
                cobertos = set(pos_args[:n_pos]) | set(kws)
                faltando = [a for a in (pos_args[:mn_pos] + req_kw) if a not in cobertos]
                if faltando and not any(isinstance(a, ast.Starred) for a in node.args):
                    erros.append(f"{arq.name}:{node.lineno} {nome_fn}: faltando {faltando}")
                if arq.name == "visao_geral.py" and nome_fn == "card":
                    chamadas_card_vg += 1

    assert not erros, "Divergências de assinatura encontradas:\n" + "\n".join(erros)
    assert chamadas_card_vg == 5

    # Garante que `visao_geral.py` não duplica título com `st.subheader` dentro de `with card(...)`
    vg_tree = ast.parse((FRONTEND_DIR / "pages" / "visao_geral.py").read_text(encoding="utf-8"))
    subheaders_em_card = []
    for node in ast.walk(vg_tree):
        if isinstance(node, ast.With):
            eh_card = any(
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Name)
                and item.context_expr.func.id == "card"
                for item in node.items
            )
            if eh_card:
                for sub in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                    if (
                        isinstance(sub, ast.Attribute)
                        and sub.attr == "subheader"
                    ):
                        subheaders_em_card.append(sub.lineno)
    assert not subheaders_em_card, f"`st.subheader` duplicado dentro de `card()` em visao_geral.py: {subheaders_em_card}"


def test_componente_card_renderiza_titulo_chaves_unicas_e_valida_entrada() -> None:
    st_mod = _preparar_frontend()
    registros = _instalar_metodos_container_stub(st_mod)

    import components.cards as cards_mod

    importlib.reload(cards_mod)

    with cards_mod.card("Frequência observada por série"):
        pass

    with cards_mod.card(
        "ATV-01 • Lista 1",
        subtitulo="Turma 1A | MAT",
        chave="atividade_detalhe",
    ):
        pass

    boxes = [r["box"] for r in registros if r["tipo"] == "container"]
    assert len(boxes) == 2
    assert boxes[0].key == "card_frequencia_observada_por_serie"
    assert boxes[0].subheaders == ["Frequência observada por série"]
    assert boxes[0].captions == []

    assert boxes[1].key == "card_atividade_detalhe"
    assert boxes[1].subheaders == ["ATV-01 • Lista 1"]
    assert boxes[1].captions == ["Turma 1A | MAT"]

    with pytest.raises(TypeError):
        cards_mod.card()  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        cards_mod.card("   ")


def test_participacao_chaves_kpi_distintas_sem_colisao() -> None:
    """Confirma que `participacao.py` não passa rótulos invertidos nem gera chaves duplicadas em `card_kpi`."""
    part_src = (FRONTEND_DIR / "pages" / "participacao.py").read_text(encoding="utf-8")
    tree = ast.parse(part_src)
    chaves_kpi: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "card_kpi"
        ):
            kw_map = {k.arg: k.value for k in node.keywords if k.arg}
            chave_node = kw_map.get("chave")
            rotulo_node = node.args[1] if len(node.args) > 1 else kw_map.get("rotulo")
            assert isinstance(rotulo_node, ast.Constant) and isinstance(rotulo_node.value, str)
            alvo = (
                chave_node.value
                if isinstance(chave_node, ast.Constant) and isinstance(chave_node.value, str)
                else rotulo_node.value
            )
            chaves_kpi.append(alvo)

    assert len(chaves_kpi) == 10
    assert len(set(chaves_kpi)) == 10


# ==============================================================================
# 2. NAVEGAÇÃO POR PAPEL E PRESERVAÇÃO DO MENU EM EXCEÇÃO (BUG-03)
# ==============================================================================


def test_navegacao_ordem_renderizacao_e_menu_preservado_quando_pagina_falha(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fe_app = _carregar_frontend_app()
    st_mod = sys.modules["streamlit"]
    registros = _instalar_metodos_container_stub(st_mod)

    eventos: list[str] = []

    def _header_spy(paginas: Any = None) -> None:
        eventos.append(f"header:{len(paginas or [])}")

    def _sidebar_spy(paginas: Any, pagina_atual: Any) -> None:
        eventos.append(f"sidebar:{getattr(pagina_atual, 'url_path', '')}:{len(paginas or [])}")

    fe_app.render_header = _header_spy
    fe_app.render_sidebar = _sidebar_spy

    # Valida que para Administrador, Gestor e Professor header + sidebar são chamados ANTES da página
    for papel, esperado_default in [
        ("administrador", "atribuir-turmas"),
        ("gestor", "visao-geral"),
        ("professor", "visao-geral"),
    ]:
        eventos.clear()
        st_mod.session_state.clear()
        st_mod.session_state["logado"] = True
        st_mod.session_state["usuario_api"] = {"papel": papel}
        st_mod.session_state["perfil"] = papel

        def _fake_nav(paginas: list[Any], position: str = "hidden") -> Any:
            assert position == "hidden"
            atual = next((p for p in paginas if getattr(p, "default", False)), paginas[0])
            return SimpleNamespace(
                title=atual.title,
                url_path=atual.url_path,
                run=lambda: eventos.append(f"page:{atual.url_path}"),
            )

        st_mod.navigation = _fake_nav
        fe_app.executar_navegacao_autenticada()
        assert len(eventos) == 3
        assert eventos[0].startswith("header:")
        assert eventos[1].startswith(f"sidebar:{esperado_default}:")
        assert eventos[2] == f"page:{esperado_default}"

    # Se a página lançar TypeError/RuntimeError, cabeçalho e menu já renderizaram e o erro é exibido
    eventos.clear()
    registros.clear()

    def _pagina_com_falha() -> None:
        eventos.append("page_error_start")
        raise TypeError("card() missing 1 required positional argument: 'titulo'")

    st_mod.session_state["usuario_api"] = {"papel": "professor"}
    st_mod.navigation = lambda paginas, position="hidden": SimpleNamespace(
        title="Visão geral",
        url_path="visao-geral",
        run=_pagina_com_falha,
    )

    with caplog.at_level(logging.ERROR):
        fe_app.executar_navegacao_autenticada()

    assert eventos == ["header:7", "sidebar:visao-geral:7", "page_error_start"]
    erros_ui = [r["mensagem"] for r in registros if r["tipo"] == "error"]
    assert any("Ocorreu um erro inesperado ao carregar esta página." in str(m) for m in erros_ui)
    assert any("TypeError" in str(r["mensagem"]) for r in registros if r["tipo"] == "caption")
    assert any("Erro inesperado ao renderizar a página" in rec.message for rec in caplog.records)

    # Exceções de controle de fluxo do Streamlit (`RerunException`, `StopException`) NÃO são suprimidas
    class RerunException(Exception):
        pass

    st_mod.navigation = lambda paginas, position="hidden": SimpleNamespace(
        title="Visão geral",
        url_path="visao-geral",
        run=lambda: (_ for _ in ()).throw(RerunException("rerun")),
    )
    with pytest.raises(RerunException):
        fe_app.executar_navegacao_autenticada()


# ==============================================================================
# 3. VISÃO GERAL INTEGRADA AO BACKEND REAL (COM DADOS E ESCOLA SEM DADOS)
# ==============================================================================


def test_visao_geral_com_backend_real_escola_com_dados_sem_dados_e_sem_previsoes(
    client: TestClient,
    db_session: Session,
) -> None:
    """Testa `visao_geral.render()` ponta a ponta com FastAPI real em cenários completos e vazios."""
    cenario = _criar_cenario_fase4(db_session)

    # Cria uma segunda escola vazia (sem turmas, sem boletins, sem avaliações, sem previsões)
    escola_vazia = Escola(nome="Escola Recém-Criada Vazia", codigo="ERCV-01", ativo=True)
    db_session.add(escola_vazia)
    db_session.flush()
    gestor_vazio = Usuario(
        nome="Gestor Escola Vazia",
        email="gestor.vazio@vertice.edu.br",
        senha_hash=get_password_hash("SenhaForte@123"),
        papel=PapelUsuario.GESTOR,
        escola_id=escola_vazia.id,
        ativo=True,
    )
    prof_sem_turma = Usuario(
        nome="Professor Sem Turma",
        email="prof.sem.turma@vertice.edu.br",
        senha_hash=get_password_hash("SenhaForte@123"),
        papel=PapelUsuario.PROFESSOR,
        escola_id=escola_vazia.id,
        ativo=True,
    )
    db_session.add_all([gestor_vazio, prof_sem_turma])
    db_session.commit()

    # Vincula prof1 também sem erro (já vinculado no cenario da Escola A)
    assert db_session.query(ProfessorTurma).filter_by(professor_id=cenario["prof1"].id).count() >= 1

    st_mod = _preparar_frontend()
    registros = _instalar_metodos_container_stub(st_mod)

    import components.cards as cards_mod
    import components.graficos as graficos_mod
    import data.api_client as api_client
    import pages.visao_geral as pg_vg

    importlib.reload(cards_mod)
    importlib.reload(graficos_mod)
    importlib.reload(api_client)
    importlib.reload(pg_vg)
    api_client.configurar_cliente_http_teste(_adaptar_testclient_completo(client))

    try:
        # 1) Gestor de escola COM dados observados e SEM previsões de risco
        registros.clear()
        assert api_client.autenticar_usuario_api("gestor.a@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        pg_vg.render()

        chaves_cards = [
            r["key"]
            for r in registros
            if r["tipo"] == "container" and str(r["key"] or "").startswith("card_")
        ]
        assert chaves_cards == [
            "card_frequencia_observada_por_serie",
            "card_distribuicao_preditiva_de_risco",
            "card_media_observada_por_serie",
            "card_evolucao_longitudinal_observada",
        ]
        # Não exibe gráfico inventado de risco quando não há previsões
        infos = [str(r["mensagem"]) for r in registros if r["tipo"] == "info"]
        assert any("Nenhuma previsão de risco" in msg for msg in infos)

        # 2) Gestor de escola SEM NENHUM DADO (0 boletins, 0 turmas, 0 avaliações, 0 previsões)
        registros.clear()
        assert api_client.autenticar_usuario_api("gestor.vazio@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        pg_vg.render()

        infos_vazia = [str(r["mensagem"]) for r in registros if r["tipo"] == "info"]
        assert any("Ainda não há dados escolares importados" in msg for msg in infos_vazia)
        chaves_vazia = [
            r["key"]
            for r in registros
            if r["tipo"] == "container" and str(r["key"] or "").startswith("card_")
        ]
        assert len(chaves_vazia) == 4
        erros_vazia = [r["mensagem"] for r in registros if r["tipo"] == "error"]
        assert not erros_vazia

        # 3) Professor (inclusive sem dados na escola) renderiza sem erro de `card()`
        registros.clear()
        assert api_client.autenticar_usuario_api("prof.sem.turma@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        pg_vg.render()
        assert not [r for r in registros if r["tipo"] == "error"]
    finally:
        api_client.configurar_cliente_http_teste(None)
        st_mod.session_state.clear()
