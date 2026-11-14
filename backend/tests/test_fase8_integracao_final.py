"""
Suíte abrangente da Fase 8 — Integração Final, Qualidade, Fluxos Ponta a Ponta e Falhas.

Cobre sistematicamente:
9.1. Autenticação real e papéis canônicos (`administrador`, `gestor`, `professor`), bloqueio de
     promoção indevida de `gestor` para `administrador`, expiração de sessão (`401`) e logout.
9.2. Matriz completa de permissões RBAC e isolamento por escola, turma, disciplina e usuário,
     incluindo escopo de `GET /api/v1/usuarios`, `POST /api/v1/atribuicoes` e `GET /api/v1/importacoes`.
9.3. Importações dos 3 tipos (`dados_escolares`, `avaliacoes`, `atividades`) em CSV e XLSX,
     downloads dos 3 modelos oficiais no backend e validações/rejeições de erro (PII, legado `Acertou`,
     colunas ausentes, estudante inexistente, valores inválidos e escopo cruzado).
9.4. Fluxo estrito em 2 etapas (Etapa 1 nunca persiste domínio; Etapa 2 confirma atomicamente ou
     descarta limpando lote pendente; revalidação de permissão entre etapas; rollback atômico;
     rejeição `409` para lote já confirmado/descartado; histórico via `GET /api/v1/importacoes`).
9.5 & 9.6. Integração Frontend <-> Backend sem mocks (`api_client`, `login`, `cadastro`, `perfil`,
     `atribuicao`, `entrada_dados`, `modelos_prova`, `mapa_acertos`, `participacao`, `visao_geral`,
     `estudantes`, `assistente_ia`), incluindo paginação servidor com `X-Total-Count` e ausência
     de fallbacks fictícios/sessão local acadêmica.
9.7. Tratamento de falhas (`ConnectError`, `ReadTimeout`, `401`, `403`, `422`, `500`, `503` e JSON
     inválido) com sanitização de segredos e zero exposição de tokens ou PII.
"""

from __future__ import annotations

from datetime import date
import importlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
import httpx
import openpyxl
import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app as fastapi_app  # noqa: F401 - garante ordem segura de importação ORM
from app.modules.acompanhamento.models import AcompanhamentoPedagogico
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.avaliacoes.models import Avaliacao, QuestaoAvaliacao, RespostaAvaliacao
from app.modules.estudantes.models import BoletimPeriodo, Estudante
from app.modules.importacao.models import StatusLoteImportacao
from app.modules.importacao.service import ImportacaoService
from app.modules.importacao.validator import (
    COLUNAS_MODELO_ATIVIDADES,
    COLUNAS_MODELO_AVALIACOES,
    COLUNAS_MODELO_DADOS_ESCOLARES,
)
from app.modules.participacao.models import Atividade
from app.modules.usuarios.models import PapelUsuario
from app.modules.usuarios.schemas import UsuarioCreate
from app.modules.usuarios.service import UsuarioService
from tests.test_fase4_modulos_pedagogicos import (
    _criar_cenario_fase4,
    _login_headers,
)
from tests.test_fase5_mapa_acertos_e_frontend import (
    _garantir_ambiente_frontend_para_teste,
)
from tests.test_fase6_participacao import _adaptar_client_para_api_client

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "Frontend vertice"


def _preparar_frontend() -> Any:
    """Inicializa stubs mínimos de Streamlit/Plotly e garante `Frontend vertice` no `sys.path`."""
    if str(FRONTEND_DIR) not in sys.path:
        sys.path.insert(0, str(FRONTEND_DIR))
    st_mod = _garantir_ambiente_frontend_para_teste()
    if not hasattr(st_mod, "components"):
        st_mod.components = SimpleNamespace(
            v2=SimpleNamespace(
                component=lambda *_a, **_kw: (lambda *_a2, **_kw2: None),
            ),
            v1=SimpleNamespace(
                html=lambda *_a, **_kw: None,
            ),
        )
    for attr_fn in (
        "set_page_config",
        "logo",
        "subheader",
        "divider",
        "write",
        "stop",
        "rerun",
    ):
        if not hasattr(st_mod, attr_fn):
            setattr(st_mod, attr_fn, lambda *_a, **_kw: None)
    if not hasattr(st_mod, "Page"):
        st_mod.Page = lambda fn, title="", url_path="", default=False: SimpleNamespace(
            fn=fn,
            title=title,
            url_path=url_path,
            default=default,
        )
    if not hasattr(st_mod, "navigation"):
        st_mod.navigation = lambda _pages, position="hidden": SimpleNamespace(
            run=lambda: None
        )
    st_mod.session_state.clear()
    return st_mod


def _carregar_frontend_app() -> Any:
    """Importa `Frontend vertice/app.py` com namespace único sem colidir com `backend/app`."""
    _preparar_frontend()
    spec = importlib.util.spec_from_file_location(
        "vertice_frontend_app_teste",
        FRONTEND_DIR / "app.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _adaptar_testclient_completo(client: TestClient) -> Any:
    """Adapta `TestClient` preservando query strings, headers (`X-Total-Count`), binários e arquivos."""
    base_adapter = _adaptar_client_para_api_client(client)

    def _adapter(
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> Any:
        parsed = httpx.URL(url)
        caminho = parsed.path
        if parsed.query:
            caminho = f"{caminho}?{parsed.query.decode('utf-8')}"
        return base_adapter(
            method,
            caminho,
            headers=headers,
            params=params,
            json=json,
            files=files,
            timeout=timeout,
        )

    return _adapter


def _gerar_xlsx_bytes(colunas: tuple[str, ...] | list[str], linhas: list[list[Any]]) -> bytes:
    """Gera bytes XLSX válidos a partir de cabeçalho e linhas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(list(colunas))
    for linha in linhas:
        ws.append(linha)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv_dados_escolares_valido(codigo_anonimo: str = "EST-090") -> bytes:
    cabecalho = ",".join(COLUNAS_MODELO_DADOS_ESCOLARES)
    linha = (
        f"{codigo_anonimo},Turma 1A,MAT,2026,1º Bimestre,92.5,3,8.1,8.5,8.0,9.0,0,Não,Aprovado"
    )
    return f"{cabecalho}\n{linha}\n".encode("utf-8")


def _csv_avaliacoes_valido(id_avaliacao: str = "AV-FASE8-01") -> bytes:
    cabecalho = ",".join(COLUNAS_MODELO_AVALIACOES)
    linha = (
        f"{id_avaliacao},Simulado Fase 8,MAT,Turma 1A,1º Bimestre,2026-05-10,"
        "Q01,FECHADA,2.5,B,EST-001,B,Não,,Adequada,Álgebra"
    )
    return f"{cabecalho}\n{linha}\n".encode("utf-8")


def _csv_atividades_valido(
    id_atividade: str = "ATV-FASE8-01",
    codigo_anonimo: str = "EST-001",
) -> bytes:
    cabecalho = ",".join(COLUNAS_MODELO_ATIVIDADES)
    linha = (
        f"{id_atividade},Lista Integrada,MAT,Turma 1A,1º Bimestre,2026,"
        f"2026-05-15,10.0,{codigo_anonimo},ENTREGUE,2026-05-14,9.5"
    )
    return f"{cabecalho}\n{linha}\n".encode("utf-8")


# ==============================================================================
# 9.1. AUTENTICAÇÃO REAL, PAPÉIS CANÔNICOS E CICLO DE SESSÃO
# ==============================================================================
def test_fase8_autenticacao_papeis_canonicos_e_expiracao_sessao(
    client: TestClient,
    db_session: Session,
) -> None:
    _criar_cenario_fase4(db_session)
    st = _preparar_frontend()
    import data.api_client as api_client

    importlib.reload(api_client)
    api_client.configurar_cliente_http_teste(_adaptar_testclient_completo(client))
    try:
        fe_app = _carregar_frontend_app()

        for email, papel_esperado, nome_esperado in [
            ("admin@vertice.edu.br", "administrador", "Admin Root"),
            ("gestor.a@vertice.edu.br", "gestor", "Gestor Escola A"),
            ("prof1@vertice.edu.br", "professor", "Professor João"),
        ]:
            st.session_state.clear()
            resp_login = api_client.autenticar_usuario_api(email, "SenhaForte@123")
            assert resp_login.ok is True, resp_login.erro
            resp_me = api_client.obter_usuario_atual_api()
            assert resp_me.ok is True
            assert resp_me.dados["papel"] == papel_esperado

            api_client.registrar_usuario_sessao(resp_me.dados)
            st.session_state["logado"] = True
            assert st.session_state["perfil"] == papel_esperado
            assert st.session_state["papel_api"] == papel_esperado
            assert st.session_state["nome_atual"] == nome_esperado
            assert fe_app.obter_papel_canonico() == papel_esperado

        # Menu por papel respeita arquitetura e nunca converte gestor em administrador
        titulos_por_papel: dict[str, set[str]] = {}
        for papel in ("administrador", "gestor", "professor"):
            st.session_state["usuario_api"] = {"papel": papel}
            st.session_state["perfil"] = papel
            _, paginas_menu = fe_app.montar_paginas_internas()
            titulos_por_papel[papel] = {p.title for p in paginas_menu}

        assert "Entrada de Dados" not in titulos_por_papel["administrador"]
        assert "Visão Geral" not in titulos_por_papel["administrador"]
        assert "Atribuir turmas" in titulos_por_papel["administrador"]
        assert "Entrada de Dados" in titulos_por_papel["gestor"]
        assert "Atribuir turmas" in titulos_por_papel["gestor"]
        assert "Entrada de Dados" in titulos_por_papel["professor"]
        assert "Atribuir turmas" not in titulos_por_papel["professor"]

        # Logout limpa toda a sessão
        api_client.encerrar_sessao_api()
        assert st.session_state.get("logado") is False
        assert api_client.obter_token_sessao() is None
        assert "perfil" not in st.session_state

        # Token inválido/expirado em endpoint protegido dispara limpeza de sessão (`401`)
        st.session_state["access_token"] = "token-invalido-expirado"
        st.session_state["logado"] = True
        resp_401 = api_client.obter_usuario_atual_api()
        assert resp_401.ok is False
        assert resp_401.status_code == 401
        assert st.session_state.get("logado") is False
        assert api_client.obter_token_sessao() is None
        assert st.session_state.get("sessao_api_expirada") is True
        assert "mensagem_sessao_expirada" in st.session_state

        # Cadastro / Auth animada sem perfil fictício `coordenador` nem seletor enganoso de perfil no login
        auth_anim_src = (FRONTEND_DIR / "components" / "auth_animada.py").read_text(encoding="utf-8")
        cad_src = (FRONTEND_DIR / "pages" / "cadastro.py").read_text(encoding="utf-8")
        assert "v-login-perfil" not in auth_anim_src
        assert "coordenador" not in auth_anim_src.lower()
        assert "coordenador" not in cad_src.lower()
    finally:
        api_client.configurar_cliente_http_teste(None)
        st.session_state.clear()


# ==============================================================================
# 9.2. MATRIZ DE PERMISSÕES RBAC E ESCOPO MULTI-ESCOLA / TURMA / DISCIPLINA
# ==============================================================================
def test_fase8_matriz_rbac_usuarios_atribuicoes_escolas_e_operacional(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)

    # Professor adicional na Escola B e professor multi-escola (escola_id=None)
    prof_b = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Professor Escola B",
            email="prof.b@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.PROFESSOR,
            escola_id=cenario["escola_b"].id,
        ),
    )
    prof_livre = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Professor Sem Escola Fixa",
            email="prof.livre@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.PROFESSOR,
            escola_id=None,
        ),
    )
    db_session.commit()

    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")
    headers_gestor_b = _login_headers(client, "gestor.b@vertice.edu.br", "SenhaForte@123")
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # 1. Administrador: enxerga escolas/usuários/atribuições e NÃO entra em fluxos pedagógicos
    assert client.get("/api/v1/escolas", headers=headers_admin).status_code == 200
    assert client.get("/api/v1/usuarios", headers=headers_admin).status_code == 200
    assert client.get("/api/v1/atribuicoes", headers=headers_admin).status_code == 200
    for rota_pedagogica in [
        "/api/v1/estudantes",
        "/api/v1/avaliacoes",
        "/api/v1/atividades",
        "/api/v1/indicadores/gerais",
        "/api/v1/importacoes",
    ]:
        assert client.get(rota_pedagogica, headers=headers_admin).status_code == 403, rota_pedagogica

    # 2. Gestor A: lista usuários apenas da Escola A (+ professores sem escola fixa), nunca Escola B/admin
    resp_users_ga = client.get("/api/v1/usuarios", headers=headers_gestor_a)
    assert resp_users_ga.status_code == 200
    emails_ga = {u["email"] for u in resp_users_ga.json()}
    assert "gestor.a@vertice.edu.br" in emails_ga
    assert "prof1@vertice.edu.br" in emails_ga
    assert "prof.livre@vertice.edu.br" in emails_ga
    assert "gestor.b@vertice.edu.br" not in emails_ga
    assert "prof.b@vertice.edu.br" not in emails_ga
    assert "admin@vertice.edu.br" not in emails_ga

    assert client.get(f"/api/v1/usuarios/{cenario['gestor_b'].id}", headers=headers_gestor_a).status_code == 403
    assert client.get(f"/api/v1/usuarios/{cenario['admin'].id}", headers=headers_gestor_a).status_code == 403
    assert client.get(f"/api/v1/escolas/{cenario['escola_a'].id}", headers=headers_gestor_a).status_code == 200
    assert client.get(f"/api/v1/escolas/{cenario['escola_b'].id}", headers=headers_gestor_a).status_code == 403

    # Atribuição cruzada entre escolas é bloqueada (prof_b -> turma_1a da Escola A)
    resp_atrib_cross = client.post(
        "/api/v1/atribuicoes",
        headers=headers_gestor_a,
        json={
            "professor_id": str(prof_b.id),
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
        },
    )
    assert resp_atrib_cross.status_code == 403

    # Professor com escola_id=None pode ser atribuído à Escola A; ciclo completo criar/remover funciona
    resp_atrib_ok = client.post(
        "/api/v1/atribuicoes",
        headers=headers_gestor_a,
        json={
            "professor_id": str(prof_livre.id),
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_qui"].id),
        },
    )
    assert resp_atrib_ok.status_code == 201, resp_atrib_ok.text
    atrib_id = resp_atrib_ok.json()["id"]
    assert client.delete(f"/api/v1/atribuicoes/{atrib_id}", headers=headers_gestor_a).status_code == 204

    # Gestor B não remove atribuição da Escola A
    atrib_escola_a = db_session.execute(
        select(ProfessorTurma).where(ProfessorTurma.turma_id == cenario["turma_1a"].id)
    ).scalars().first()
    assert atrib_escola_a is not None
    assert client.delete(f"/api/v1/atribuicoes/{atrib_escola_a.id}", headers=headers_gestor_b).status_code == 403

    # 3. Professor: sem acesso a usuários nem gestão de atribuições; só vê suas turmas/estudantes
    assert client.get("/api/v1/usuarios", headers=headers_prof1).status_code == 403
    assert (
        client.post(
            "/api/v1/atribuicoes",
            headers=headers_prof1,
            json={
                "professor_id": str(cenario["prof1"].id),
                "turma_id": str(cenario["turma_3a"].id),
                "disciplina_id": str(cenario["disc_qui"].id),
            },
        ).status_code
        == 403
    )
    # Estudante fora do escopo do professor retorna 404 (proteção contra enumeração de IDs)
    assert client.get(f"/api/v1/estudantes/{cenario['est4'].id}", headers=headers_prof1).status_code == 404
    assert client.get(f"/api/v1/estudantes/{cenario['est1'].id}", headers=headers_prof1).status_code == 200


# ==============================================================================
# 9.3. IMPORTAÇÕES DOS 3 TIPOS (CSV/XLSX), MODELOS OFICIAIS E REJEIÇÕES
# ==============================================================================
def test_fase8_modelos_oficiais_e_validacoes_todos_tipos_csv_e_xlsx(
    client: TestClient,
    db_session: Session,
) -> None:
    _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # Downloads dos 3 modelos oficiais (CSV + XLSX) para gestor/professor, 403 para admin
    contratos = [
        ("dados-escolares", COLUNAS_MODELO_DADOS_ESCOLARES),
        ("avaliacoes", COLUNAS_MODELO_AVALIACOES),
        ("atividades", COLUNAS_MODELO_ATIVIDADES),
    ]
    for rota, colunas_esperadas in contratos:
        assert (
            client.get(f"/api/v1/importacoes/modelos/{rota}?formato=csv", headers=headers_admin).status_code
            == 403
        )
        r_csv = client.get(f"/api/v1/importacoes/modelos/{rota}?formato=csv", headers=headers_prof1)
        assert r_csv.status_code == 200, r_csv.text
        df_csv = pd.read_csv(io.BytesIO(r_csv.content), sep=";")
        assert list(df_csv.columns) == list(colunas_esperadas)

        r_xlsx = client.get(f"/api/v1/importacoes/modelos/{rota}?formato=xlsx", headers=headers_gestor_a)
        assert r_xlsx.status_code == 200, r_xlsx.text
        wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.content))
        ws = wb.active
        assert ws is not None
        cabecalho_xlsx = [cell.value for cell in ws[1]]
        assert cabecalho_xlsx == list(colunas_esperadas)

    # Validação bem-sucedida em XLSX para os 3 tipos
    xlsx_de = _gerar_xlsx_bytes(
        COLUNAS_MODELO_DADOS_ESCOLARES,
        [["EST-091", "Turma 1A", "MAT", 2026, "1º Bimestre", 91.0, 4, 7.8, 8.0, 8.0, 8.0, 0, "Não", "Aprovado"]],
    )
    r_val_de = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("dados.xlsx", xlsx_de, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r_val_de.status_code == 201, r_val_de.text
    assert r_val_de.json()["pode_confirmar"] is True
    assert r_val_de.json()["tipo_importacao"] == "DADOS_ESCOLARES"

    xlsx_av = _gerar_xlsx_bytes(
        COLUNAS_MODELO_AVALIACOES,
        [["AV-XLSX-1", "Prova XLSX", "MAT", "Turma 1A", "1º Bimestre", "2026-05-12", "Q01", "FECHADA", 2.0, "C", "EST-001", "C", "Não", None, "Fácil", "Funções"]],
    )
    r_val_av = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("avaliacoes.xlsx", xlsx_av, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r_val_av.status_code == 201, r_val_av.text
    assert r_val_av.json()["pode_confirmar"] is True
    assert r_val_av.json()["tipo_importacao"] == "AVALIACOES"

    xlsx_at = _gerar_xlsx_bytes(
        COLUNAS_MODELO_ATIVIDADES,
        [["ATV-XLSX-1", "Tarefa XLSX", "MAT", "Turma 1A", "1º Bimestre", 2026, "2026-05-18", 10.0, "EST-001", "ENTREGUE", "2026-05-17", 9.0]],
    )
    r_val_at = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("atividades.xlsx", xlsx_at, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r_val_at.status_code == 201, r_val_at.text
    assert r_val_at.json()["pode_confirmar"] is True
    assert r_val_at.json()["tipo_importacao"] == "ATIVIDADES"

    # Rejeições obrigatórias:
    # a) PII explícita (`nome_completo`)
    csv_pii = (
        "codigo_anonimo,nome_completo,turma,disciplina,ano_letivo,periodo_letivo,"
        "frequencia_percentual,faltas,media_geral,nota,nota_prova,nota_trabalho,"
        "historico_reprovacoes,participacao_recuperacao,situacao_final\n"
        "EST-092,Maria Souza,Turma 1A,MAT,2026,1º Bimestre,90,2,8.0,8.0,8.0,8.0,0,Não,Aprovado\n"
    ).encode("utf-8")
    r_pii = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("com_pii.csv", csv_pii, "text/csv")},
    ).json()
    assert r_pii["pode_confirmar"] is False
    assert r_pii["relatorio_validacao"]["colunas_proibidas_pii"]

    # b) Formato legado `Acertou` rejeitado em Avaliações
    csv_legado = (
        "Avaliação,Disciplina,Turma,Identificador,Questão,Acertou\n"
        "Prova 1,MAT,Turma 1A,EST-001,Q01,Sim\n"
    ).encode("utf-8")
    r_leg = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("legado.csv", csv_legado, "text/csv")},
    ).json()
    assert r_leg["pode_confirmar"] is False
    assert r_leg["status"] == "com_erros"

    # c) Estudante inexistente em Atividades
    r_est_inex = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("atv_desconhecido.csv", _csv_atividades_valido(codigo_anonimo="EST-INEXISTENTE"), "text/csv")},
    ).json()
    assert r_est_inex["pode_confirmar"] is False
    assert r_est_inex["quantidade_erros"] >= 1

    # d) Valor inválido (frequência > 100) em Dados Escolares
    csv_freq_inv = _csv_dados_escolares_valido("EST-093").decode("utf-8").replace(",92.5,", ",140.0,").encode("utf-8")
    r_freq = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("freq_inv.csv", csv_freq_inv, "text/csv")},
    ).json()
    assert r_freq["pode_confirmar"] is False
    assert r_freq["relatorio_validacao"]["valores_invalidos"]


# ==============================================================================
# 9.4. FLUXO ESTRITO EM 2 ETAPAS, ATOMICIDADE, REVALIDAÇÃO E HISTÓRICO
# ==============================================================================
def test_fase8_fluxo_duas_etapas_descarte_rollback_revalidacao_e_historico(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")
    headers_gestor_b = _login_headers(client, "gestor.b@vertice.edu.br", "SenhaForte@123")
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_prof2 = _login_headers(client, "prof2@vertice.edu.br", "SenhaForte@123")

    qtd_est_ini = db_session.query(Estudante).count()
    qtd_bol_ini = db_session.query(BoletimPeriodo).count()
    qtd_av_ini = db_session.query(Avaliacao).count()
    qtd_atv_ini = db_session.query(Atividade).count()

    # Etapa 1 para os 3 tipos NÃO persiste registros definitivos
    lote_de = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("de.csv", _csv_dados_escolares_valido("EST-F8-STAGE"), "text/csv")},
    ).json()
    lote_av = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("av.csv", _csv_avaliacoes_valido("AV-F8-STAGE"), "text/csv")},
    ).json()
    lote_at = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("at.csv", _csv_atividades_valido("ATV-F8-STAGE"), "text/csv")},
    ).json()
    assert lote_de["pode_confirmar"] and lote_av["pode_confirmar"] and lote_at["pode_confirmar"]

    db_session.expire_all()
    assert db_session.query(Estudante).count() == qtd_est_ini
    assert db_session.query(BoletimPeriodo).count() == qtd_bol_ini
    assert db_session.query(Avaliacao).count() == qtd_av_ini
    assert db_session.query(Atividade).count() == qtd_atv_ini

    # Descartar lote mantém domínio limpo e impede confirmação posterior (409)
    r_desc = client.post(f"/api/v1/importacoes/{lote_de['id']}/descartar", headers=headers_prof1)
    assert r_desc.status_code == 200, r_desc.text
    assert r_desc.json()["status"] == StatusLoteImportacao.DESCARTADO.value
    assert client.post(f"/api/v1/importacoes/{lote_de['id']}/confirmar", headers=headers_prof1).status_code == 409
    assert db_session.query(Estudante).count() == qtd_est_ini

    # Rollback atômico em falha simulada na Etapa 2 (Avaliação parcialmente escrita deve ser revertida)
    def _falha_transacional(*_a: Any, **kw: Any) -> Any:
        db_tx = kw["db"]
        db_tx.add(
            Avaliacao(
                codigo="AV-ROLLBACK-PARCIAL",
                titulo="Não deve persistir",
                escola_id=cenario["escola_a"].id,
                turma_id=cenario["turma_1a"].id,
                disciplina_id=cenario["disc_mat"].id,
                usuario_id=cenario["prof1"].id,
                periodo_letivo="1º Bimestre",
                data_avaliacao=date(2026, 5, 10),
                status="PUBLICADA",
            )
        )
        db_tx.flush()
        raise RuntimeError("Falha simulada durante persistência da Etapa 2")

    monkeypatch.setattr(
        ImportacaoService,
        "_persistir_confirmacao_avaliacoes",
        staticmethod(_falha_transacional),
    )
    r_falha_etapa2 = client.post(
        f"/api/v1/importacoes/{lote_av['id']}/confirmar",
        headers=headers_prof1,
    )
    assert r_falha_etapa2.status_code == 500, r_falha_etapa2.text
    assert "rollback" in r_falha_etapa2.json()["detail"].lower()
    db_session.expire_all()
    assert db_session.query(Avaliacao).count() == qtd_av_ini
    assert db_session.query(Avaliacao).filter(Avaliacao.codigo == "AV-ROLLBACK-PARCIAL").first() is None
    assert db_session.query(QuestaoAvaliacao).count() == 0
    assert db_session.query(RespostaAvaliacao).count() == 0
    monkeypatch.undo()

    # Confirmação explícita de Avaliações e Atividades persiste exatamente os registros esperados
    r_conf_av = client.post(f"/api/v1/importacoes/{lote_av['id']}/confirmar", headers=headers_prof1)
    assert r_conf_av.status_code == 200, r_conf_av.text
    r_conf_at = client.post(f"/api/v1/importacoes/{lote_at['id']}/confirmar", headers=headers_prof1)
    assert r_conf_at.status_code == 200, r_conf_at.text
    assert db_session.query(Avaliacao).count() == qtd_av_ini + 1
    assert db_session.query(Atividade).count() == qtd_atv_ini + 1

    # Lote já confirmado não pode ser confirmado nem descartado novamente (409)
    assert client.post(f"/api/v1/importacoes/{lote_av['id']}/confirmar", headers=headers_prof1).status_code == 409
    assert client.post(f"/api/v1/importacoes/{lote_av['id']}/descartar", headers=headers_prof1).status_code == 409

    # Revalidação de permissão entre Etapa 1 e Etapa 2: vínculo revogado bloqueia confirmação (403)
    lote_revogado = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("rev.csv", _csv_dados_escolares_valido("EST-REV-1"), "text/csv")},
    ).json()
    atrib_mat = db_session.execute(
        select(ProfessorTurma).where(
            ProfessorTurma.professor_id == cenario["prof1"].id,
            ProfessorTurma.turma_id == cenario["turma_1a"].id,
            ProfessorTurma.disciplina_id == cenario["disc_mat"].id,
        )
    ).scalar_one()
    assert client.delete(f"/api/v1/atribuicoes/{atrib_mat.id}", headers=headers_gestor_a).status_code == 204
    r_conf_rev = client.post(f"/api/v1/importacoes/{lote_revogado['id']}/confirmar", headers=headers_prof1)
    assert r_conf_rev.status_code == 403
    assert db_session.query(Estudante).filter(Estudante.codigo_anonimo == "EST-REV-1").first() is None

    # Histórico GET /api/v1/importacoes respeita escopo
    hist_prof1 = client.get("/api/v1/importacoes", headers=headers_prof1)
    hist_prof2 = client.get("/api/v1/importacoes", headers=headers_prof2)
    hist_ga = client.get("/api/v1/importacoes", headers=headers_gestor_a)
    hist_gb = client.get("/api/v1/importacoes", headers=headers_gestor_b)
    assert hist_prof1.status_code == 200 and len(hist_prof1.json()) == 4
    assert hist_prof2.status_code == 200 and len(hist_prof2.json()) == 0
    assert hist_ga.status_code == 200 and len(hist_ga.json()) == 4
    assert hist_gb.status_code == 200 and len(hist_gb.json()) == 0


# ==============================================================================
# 9.5 & 9.6. INTEGRAÇÃO COMPLETA DO FRONTEND COM BACKEND REAL (SEM MOCKS)
# ==============================================================================
def test_fase8_frontend_integrado_sem_mocks_fluxo_completo(
    client: TestClient,
    db_session: Session,
) -> None:
    cenario = _criar_cenario_fase4(db_session)
    st = _preparar_frontend()
    import data.api_client as api_client
    import pages.assistente_ia as pg_assistente
    import pages.atribuicao as pg_atribuicao
    import pages.entrada_dados as pg_entrada
    import pages.estudantes as pg_estudantes
    import pages.mapa_acertos as pg_mapa
    import pages.modelos_prova as pg_modelos
    import pages.participacao as pg_participacao
    import pages.perfil as pg_perfil
    import pages.visao_geral as pg_visao_geral

    for mod in (
        api_client,
        pg_assistente,
        pg_atribuicao,
        pg_entrada,
        pg_estudantes,
        pg_mapa,
        pg_modelos,
        pg_participacao,
        pg_perfil,
        pg_visao_geral,
    ):
        importlib.reload(mod)

    api_client.configurar_cliente_http_teste(_adaptar_testclient_completo(client))
    try:
        # 1) Perfil real (gestor, administrador e professor)
        assert api_client.autenticar_usuario_api("gestor.a@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        ctx_perfil_ga = pg_perfil.carregar_perfil_api()
        assert ctx_perfil_ga["usuario"]["email"] == "gestor.a@vertice.edu.br"
        assert ctx_perfil_ga["escola"]["nome"] == "Escola Estadual Norte"

        assert api_client.autenticar_usuario_api("admin@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        ctx_perfil_adm = pg_perfil.carregar_perfil_api()
        assert ctx_perfil_adm["usuario"]["papel"] == "administrador"
        ctx_atrib_adm = pg_atribuicao.carregar_contexto_atribuicoes_api()
        assert len(ctx_atrib_adm["escolas"]) >= 2

        assert api_client.autenticar_usuario_api("prof1@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        ctx_perfil_prof = pg_perfil.carregar_perfil_api()
        assert ctx_perfil_prof["usuario"]["papel"] == "professor"
        assert ctx_perfil_prof["escola"]["nome"] == "Escola Estadual Norte"
        assert len(ctx_perfil_prof["atribuicoes"]) >= 2

        # 2) Atribuição real (carrega contexto e cria/remove vínculo no banco)
        assert api_client.autenticar_usuario_api("gestor.a@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        ctx_atrib = pg_atribuicao.carregar_contexto_atribuicoes_api()
        assert len(ctx_atrib["professores"]) >= 2
        assert len(ctx_atrib["turmas"]) >= 3
        r_nova = api_client.criar_atribuicao_api(
            professor_id=str(cenario["prof1"].id),
            turma_id=str(cenario["turma_3a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
        )
        assert r_nova.ok is True and r_nova.status_code == 201
        assert api_client.remover_atribuicao_api(r_nova.dados["id"]).ok is True

        # 3) Entrada de Dados (2 etapas reais via helpers do módulo + histórico + download oficial)
        assert api_client.autenticar_usuario_api("prof1@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)

        bytes_modelo = pg_entrada._obter_conteudo_modelo_oficial("Resultados de avaliações", "csv")
        assert list(pd.read_csv(io.BytesIO(bytes_modelo), sep=";").columns) == list(
            COLUNAS_MODELO_AVALIACOES
        )

        qtd_av_antes = db_session.query(Avaliacao).count()
        r_fe_val = pg_entrada.enviar_validacao_importacao_api(
            "simulado_fe.csv",
            _csv_avaliacoes_valido("AV-FE-2ETAPAS"),
            "Resultados de avaliações",
        )
        assert r_fe_val.ok is True and r_fe_val.dados["pode_confirmar"] is True
        # Etapa 1 não gravou avaliação ainda
        assert db_session.query(Avaliacao).count() == qtd_av_antes

        r_fe_conf = pg_entrada.confirmar_lote_importacao_api(r_fe_val.dados["id"])
        assert r_fe_conf.ok is True
        assert db_session.query(Avaliacao).count() == qtd_av_antes + 1

        # Descartar lote via helper frontend
        r_fe_val2 = pg_entrada.enviar_validacao_importacao_api(
            "descarte_fe.csv",
            _csv_dados_escolares_valido("EST-DESC-FE"),
            "Dados escolares",
        )
        assert r_fe_val2.ok is True
        assert pg_entrada.descartar_lote_importacao_api(r_fe_val2.dados["id"]).ok is True
        r_hist_fe = pg_entrada.carregar_historico_importacoes_api()
        assert r_hist_fe.ok is True and len(r_hist_fe.dados) == 2

        # 4) Modelos de Planilha utilitário (sem persistência em sessão)
        modelos_por_tipo = {m["tipo_api"]: m for m in pg_modelos.MODELOS_OFICIAIS}
        assert set(modelos_por_tipo) == {"avaliacoes", "dados_escolares", "atividades"}
        bytes_mp_de = pg_modelos._obter_bytes_modelo(modelos_por_tipo["dados_escolares"], "csv")
        bytes_mp_at = pg_modelos._obter_bytes_modelo(modelos_por_tipo["atividades"], "xlsx")
        assert list(pd.read_csv(io.BytesIO(bytes_mp_de), sep=";").columns) == list(
            COLUNAS_MODELO_DADOS_ESCOLARES
        )
        wb_mp = openpyxl.load_workbook(io.BytesIO(bytes_mp_at))
        assert [c.value for c in wb_mp.active[1]] == list(COLUNAS_MODELO_ATIVIDADES)

        # 5) Mapa de Acertos e Acompanhamento Pedagógico via API
        ctx_mapa = pg_mapa._carregar_contexto_api()
        assert len(ctx_mapa["avaliacoes"]) >= 1
        r_acomp = api_client.registrar_acompanhamento_pedagogico_api(
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
            origem="MAPA_ACERTOS",
            tipo_acao="Revisão em grupo",
            descricao="Reforço sobre álgebra linear básica",
        )
        assert r_acomp.ok is True
        assert db_session.query(AcompanhamentoPedagogico).count() == 1

        # 6) Participação: atividade + entregas + indicadores reais
        ctx_part = pg_participacao.carregar_contexto_participacao_api()
        assert len(ctx_part["turmas"]) >= 2
        r_atv = api_client.criar_atividade_api(
            codigo="ATV-FE-PART",
            titulo="Atividade Frontend Real",
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
            periodo_letivo="1º Bimestre",
            data_limite="2026-06-01",
            nota_maxima=10.0,
        )
        assert r_atv.ok is True
        r_ind_part = api_client.consultar_indicadores_participacao(
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
        )
        assert r_ind_part.ok is True and r_ind_part.dados["total_atividades"] >= 1

        # 7) Estudantes com paginação server-side e header `X-Total-Count`
        assert api_client.autenticar_usuario_api("gestor.a@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        r_ests_pag = api_client.listar_estudantes_api(
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
            skip=0,
            limit=2,
        )
        assert r_ests_pag.ok is True
        assert len(r_ests_pag.dados) == 2
        assert r_ests_pag.headers is not None
        assert r_ests_pag.headers.get("x-total-count") == "3"

        # 8) Visão Geral com filtro por disciplina e período
        r_vg = api_client.consultar_indicadores_gerais_api(
            turma_id=str(cenario["turma_1a"].id),
            disciplina_id=str(cenario["disc_mat"].id),
            periodo_letivo="1º Bimestre",
        )
        assert r_vg.ok is True and r_vg.dados["total_estudantes_distintos"] == 3

        # 9) Assistente IA com contexto real (e bloqueio para administrador)
        r_ia_status = api_client.consultar_status_assistente_api()
        assert r_ia_status.ok is True
        r_ia_ctx = api_client.construir_contexto_assistente_api(
            tipo_contexto="TURMA",
            turma_id=str(cenario["turma_1a"].id),
        )
        assert r_ia_ctx.ok is True
        resumo_ia = pg_assistente.montar_resumo_contexto_ui(r_ia_ctx.dados)
        assert resumo_ia["tipo_contexto"] == "TURMA"
        assert resumo_ia["auditoria_id"] is not None

        assert api_client.autenticar_usuario_api("admin@vertice.edu.br", "SenhaForte@123").ok
        api_client.registrar_usuario_sessao(api_client.obter_usuario_atual_api().dados)
        r_ia_admin = api_client.construir_contexto_assistente_api(
            tipo_contexto="ESCOLA",
            escola_id=str(cenario["escola_a"].id),
        )
        assert r_ia_admin.ok is False and r_ia_admin.status_code == 403

        # Verificações estruturais contra regressão para mocks/sessão acadêmica local
        for rel_path, proibidos in [
            ("pages/entrada_dados.py", ["mock_data", "validar_e_confirmar_importacao_api", "avaliacoes_registradas", "entregas_registradas", "dados_escolares_importados"]),
            ("pages/atribuicao.py", ["mock_data", "data.atribuicoes"]),
            ("pages/perfil.py", ["data.atribuicoes", "aguardam integração"]),
            ("pages/modelos_prova.py", ["modelos_prova_cadastrados"]),
            ("pages/mapa_acertos.py", ["mock_data", "ma_acoes", "ma_avaliacoes_criadas", "_atribuicoes_permitidas"]),
        ]:
            conteudo = (FRONTEND_DIR / rel_path).read_text(encoding="utf-8")
            for termo in proibidos:
                assert termo not in conteudo, f"Termo proibido '{termo}' encontrado em {rel_path}"

        # Participação não usa kwargs inválidos (`titulo=` / `itens_por_pagina=`) em `tabela_paginada`
        part_src = (FRONTEND_DIR / "pages" / "participacao.py").read_text(encoding="utf-8")
        assert "itens_por_pagina=" not in part_src
    finally:
        api_client.configurar_cliente_http_teste(None)
        st.session_state.clear()


# ==============================================================================
# 9.7. TRATAMENTO DE FALHAS HTTP / REDE / JSON MALFORMADO E SANITIZAÇÃO
# ==============================================================================
def test_fase8_falhas_http_timeout_json_invalido_e_sanitizacao_segredos() -> None:
    st = _preparar_frontend()
    import data.api_client as api_client

    importlib.reload(api_client)
    st.session_state["access_token"] = "jwt-secreto-sessao-atual"

    class _FakeResp:
        def __init__(
            self,
            status_code: int,
            *,
            payload: Any = None,
            raw_text: str = "",
            raise_json: bool = False,
            headers: dict[str, str] | None = None,
        ) -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = raw_text
            if payload is not None and not raw_text:
                self.content = json.dumps(payload).encode("utf-8")
            else:
                self.content = raw_text.encode("utf-8")
            self._raise_json = raise_json
            self.headers = headers or {}

        def json(self) -> Any:
            if self._raise_json:
                raise ValueError("JSON inválido")
            return self._payload

    try:
        # 1) ConnectError -> indisponivel=True
        api_client.configurar_cliente_http_teste(
            lambda *_a, **_kw: (_ for _ in ()).throw(httpx.ConnectError("connection refused"))
        )
        r_conn = api_client.listar_turmas_api()
        assert r_conn.ok is False and r_conn.indisponivel is True

        # 2) ReadTimeout -> indisponivel=True com mensagem sanitizada amigável
        api_client.configurar_cliente_http_teste(
            lambda *_a, **_kw: (_ for _ in ()).throw(httpx.ReadTimeout("timeout"))
        )
        r_to = api_client.listar_turmas_api()
        assert r_to.ok is False and r_to.indisponivel is True
        assert r_to.erro and "ReadTimeout" not in r_to.erro

        # 3) 403 / 422 / 500 / 503 com vazamento simulado de token -> nunca expõe segredo e mascara tokens
        for code in (403, 422, 500, 503):
            api_client.configurar_cliente_http_teste(
                lambda *_a, _c=code, **_kw: _FakeResp(
                    _c,
                    payload={"detail": f"Falha {_c} Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig vtx_ml_segredo123"},
                )
            )
            r_err = api_client.listar_turmas_api()
            assert r_err.ok is False
            assert r_err.status_code == code
            assert "eyJhbGciOiJIUzI1NiJ9" not in (r_err.erro or "")
            assert "vtx_ml_segredo123" not in (r_err.erro or "")
            assert "[TOKEN_OCULTO]" in (r_err.erro or "")
            if code == 403:
                assert r_err.sem_permissao is True

        # 4) 200 com JSON malformado -> erro tratado sem exception não capturada
        api_client.configurar_cliente_http_teste(
            lambda *_a, **_kw: _FakeResp(200, raw_text="{html-quebrado", raise_json=True)
        )
        r_bad_json = api_client.listar_turmas_api()
        assert r_bad_json.ok is False and r_bad_json.status_code == 200
        assert "formato inesperado" in (r_bad_json.erro or "").lower()
    finally:
        api_client.configurar_cliente_http_teste(None)
        st.session_state.clear()
