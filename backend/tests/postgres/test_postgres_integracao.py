"""
Suíte dedicada de testes reais em PostgreSQL isolado (Fase 8).

Características de segurança e isolamento:
- Nunca opera sobre o banco principal configurado em `.env` ou sobre `postgres`.
- Utiliza `VERTICE_TEST_DATABASE_URL` (quando informada, ex.: CI) ou cria/gerencia o banco
  efêmero dedicado `vertice_test` (exigindo sufixo `_test` no nome do banco).
- Executa o ciclo real do Alembic (`upgrade head`, `downgrade base`, `upgrade head`, `check`),
  valida DDL, tipos nativos, FKs, índices, constraints parciais, atomicidade, rollback e
  concorrência entre sessões independentes.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Generator
import uuid

from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.database.connection import get_db
from app.integrations.prediction.models import PrevisaoRisco
from app.main import app
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.avaliacoes.models import Avaliacao, QuestaoAvaliacao
from app.modules.estudantes.models import Estudante
from app.modules.importacao.service import ImportacaoService
from app.modules.importacao.validator import (
    COLUNAS_MODELO_ATIVIDADES,
    COLUNAS_MODELO_AVALIACOES,
    COLUNAS_MODELO_DADOS_ESCOLARES,
)
from tests.test_fase4_modulos_pedagogicos import _criar_cenario_fase4, _login_headers

pytestmark = pytest.mark.postgres

BACKEND_DIR = Path(__file__).resolve().parents[2]
POSTGRES_TEST_DB_DEFAULT = "vertice_test"


def _resolver_config_postgres_teste() -> tuple[str, bool]:
    """
    Resolve a URL de conexão com PostgreSQL isolado para testes.
    Retorna `(url_sqlalchemy, gerenciar_ciclo_banco)`.
    """
    env_url = os.getenv("VERTICE_TEST_DATABASE_URL", "").strip()
    if env_url:
        parsed = make_url(env_url)
        db_name = (parsed.database or "").strip()
        if not db_name.endswith("_test"):
            raise RuntimeError(
                f"Banco de teste inválido em VERTICE_TEST_DATABASE_URL: '{db_name}'. "
                "Por segurança, o nome do banco deve terminar com '_test'."
            )
        return env_url, False

    if not (settings.POSTGRES_USER and settings.POSTGRES_PASSWORD):
        pytest.skip(
            "Credenciais PostgreSQL não configuradas e VERTICE_TEST_DATABASE_URL ausente."
        )

    test_url = URL.create(
        drivername="postgresql+psycopg",
        username=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        database=POSTGRES_TEST_DB_DEFAULT,
    )
    return test_url.render_as_string(hide_password=False), True


def _liberar_conexoes_e_executar_ddl(
    admin_kwargs: dict[str, Any],
    db_name: str,
    *,
    criar: bool,
    dropar: bool,
) -> None:
    """Cria ou remove o banco isolado `*_test` via conexão administrativa em `postgres`."""
    with psycopg.connect(autocommit=True, **admin_kwargs) as conn:
        if dropar:
            conn.execute(
                text_or_sql := sql.SQL(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()"
                ),
                (db_name,),
            )
            del text_or_sql
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
        if criar:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))


def _executar_alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Executa comando CLI do Alembic apontando exclusivamente para `url` de teste."""
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["ALEMBIC_DATABASE_URL"] = url
    parsed = make_url(url)
    if parsed.database:
        env["POSTGRES_DB"] = parsed.database
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _limpar_todas_tabelas_pg(engine: Engine) -> None:
    """Trunca todas as tabelas de domínio mantendo a estrutura migrada pelo Alembic."""
    with engine.begin() as conn:
        tabelas = conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).scalars().all()
        if tabelas:
            nomes = ", ".join(f'"{t}"' for t in tabelas)
            conn.execute(text(f"TRUNCATE TABLE {nomes} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="module")
def pg_test_env() -> Generator[tuple[str, Engine], None, None]:
    """Provisiona banco PostgreSQL isolado, aplica migrações e limpa ao finalizar."""
    url_teste, gerenciar_banco = _resolver_config_postgres_teste()
    parsed = make_url(url_teste)
    db_name = parsed.database or POSTGRES_TEST_DB_DEFAULT

    admin_kwargs = {
        "host": parsed.host or settings.POSTGRES_SERVER,
        "port": parsed.port or settings.POSTGRES_PORT,
        "user": parsed.username or settings.POSTGRES_USER,
        "password": parsed.password or settings.POSTGRES_PASSWORD,
        "dbname": "postgres",
        "connect_timeout": 3,
    }

    try:
        if gerenciar_banco:
            _liberar_conexoes_e_executar_ddl(
                admin_kwargs, db_name, criar=True, dropar=True
            )
        else:
            with psycopg.connect(
                host=admin_kwargs["host"],
                port=admin_kwargs["port"],
                user=admin_kwargs["user"],
                password=admin_kwargs["password"],
                dbname=db_name,
                connect_timeout=3,
            ) as conn_check:
                conn_check.execute("SELECT 1")
    except Exception as exc:
        pytest.skip(f"PostgreSQL indisponível para testes integrados isolados: {exc}")

    engine = create_engine(url_teste, pool_pre_ping=True)
    if not gerenciar_banco:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))

    try:
        res_up = _executar_alembic(url_teste, "upgrade", "head")
        assert res_up.returncode == 0, res_up.stdout + "\n" + res_up.stderr
        yield url_teste, engine
    finally:
        engine.dispose()
        if gerenciar_banco:
            try:
                _liberar_conexoes_e_executar_ddl(
                    admin_kwargs, db_name, criar=False, dropar=True
                )
            except Exception:
                pass


@pytest.fixture()
def pg_client_e_session_factory(
    pg_test_env: tuple[str, Engine],
) -> Generator[tuple[TestClient, sessionmaker[Session], Engine], None, None]:
    """Fornece TestClient e SessionLocal conectados exclusivamente ao PostgreSQL isolado."""
    _url, engine = pg_test_env
    _limpar_todas_tabelas_pg(engine)
    PgSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )

    def _override_get_db() -> Generator[Session, None, None]:
        db = PgSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client, PgSession, engine
    app.dependency_overrides.clear()
    _limpar_todas_tabelas_pg(engine)


# ==============================================================================
# 1. CICLO ALEMBIC COMPLETO + INSPEÇÃO DE DDL, TIPOS E ÍNDICES NO POSTGRESQL
# ==============================================================================
def test_pg_alembic_upgrade_downgrade_upgrade_e_check(
    pg_test_env: tuple[str, Engine],
) -> None:
    url_teste, engine = pg_test_env

    res_cur = _executar_alembic(url_teste, "current")
    assert res_cur.returncode == 0, res_cur.stderr
    assert "(head)" in res_cur.stdout

    res_down = _executar_alembic(url_teste, "downgrade", "base")
    assert res_down.returncode == 0, res_down.stdout + "\n" + res_down.stderr

    insp_vazio = inspect(engine)
    assert set(insp_vazio.get_table_names(schema="public")) <= {"alembic_version"}

    res_up2 = _executar_alembic(url_teste, "upgrade", "head")
    assert res_up2.returncode == 0, res_up2.stdout + "\n" + res_up2.stderr

    res_chk = _executar_alembic(url_teste, "check")
    assert res_chk.returncode == 0, res_chk.stdout + "\n" + res_chk.stderr

    insp = inspect(engine)
    tabelas = set(insp.get_table_names(schema="public"))
    esperadas = {
        "escolas",
        "usuarios",
        "turmas",
        "disciplinas",
        "professor_turmas",
        "estudantes",
        "boletins_periodo",
        "notas_disciplina",
        "lotes_importacao",
        "avaliacoes",
        "questoes_avaliacao",
        "respostas_avaliacao",
        "atividades",
        "entregas_atividade",
        "acompanhamentos_pedagogicos",
        "credenciais_integracao_predicao",
        "previsoes_risco",
        "auditoria_consultas_ia",
        "alembic_version",
    }
    assert esperadas.issubset(tabelas)

    # Verifica índices críticos diretamente em pg_indexes
    with engine.connect() as conn:
        indices = set(
            conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
            )
            .scalars()
            .all()
        )
    assert "ix_uq_professor_turma_sem_disciplina" in indices
    assert any("escola_id" in idx for idx in indices)
    assert any("codigo_anonimo" in idx for idx in indices)


# ==============================================================================
# 2. TIPOS NATIVOS, FKS, ÍNDICE PARCIAL E CONFLITOS REALISTAS VIA API NO POSTGRES
# ==============================================================================
def test_pg_tipos_nativos_fk_indice_parcial_e_conflitos(
    pg_client_e_session_factory: tuple[TestClient, sessionmaker[Session], Engine],
) -> None:
    client, PgSession, _engine = pg_client_e_session_factory
    with PgSession() as db:
        cenario_raw = _criar_cenario_fase4(db)
        ids = {k: v.id for k, v in cenario_raw.items()}

    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")

    # 1. Índice parcial PostgreSQL (`disciplina_id IS NULL`) impede vínculo duplicado (409)
    payload_polivalente = {
        "professor_id": str(ids["prof2"]),
        "turma_id": str(ids["turma_1a"]),
        "disciplina_id": None,
    }
    r1 = client.post("/api/v1/atribuicoes", headers=headers_gestor_a, json=payload_polivalente)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/v1/atribuicoes", headers=headers_gestor_a, json=payload_polivalente)
    assert r2.status_code == 409, r2.text

    # Também bloqueia diretamente em nível de tabela via IntegrityError
    with PgSession() as db_fk:
        db_fk.add(
            ProfessorTurma(
                professor_id=ids["prof2"],
                turma_id=ids["turma_1a"],
                disciplina_id=None,
            )
        )
        with pytest.raises(IntegrityError):
            db_fk.commit()
        db_fk.rollback()

        # FK inválida em turma_id deve falhar no banco real PostgreSQL
        db_fk.add(
            Avaliacao(
                codigo="AV-FK-BAD",
                titulo="Avaliação FK Inválida",
                escola_id=ids["escola_a"],
                turma_id=uuid.uuid4(),
                disciplina_id=ids["disc_mat"],
                usuario_id=ids["prof1"],
                periodo_letivo="1º Bimestre",
                data_avaliacao=date(2026, 5, 10),
                status="PUBLICADA",
            )
        )
        with pytest.raises(IntegrityError):
            db_fk.commit()
        db_fk.rollback()

    # 2. Persistência nativa de UUID, JSON/JSONB, Date, Timestamp e unique de idempotência ML
    cred = client.post(
        "/api/v1/previsoes/credenciais",
        headers=headers_admin,
        json={"nome": "ML PG Integracao"},
    ).json()
    payload_ml = {
        "estudante_id": str(ids["est1"]),
        "turma_id": str(ids["turma_1a"]),
        "ano_letivo": 2026,
        "periodo_letivo": "1º Bimestre",
        "tipo_previsao": "EVASAO",
        "pontuacao_risco": 0.68,
        "faixa_risco": "ALTO",
        "modelo_nome": "xgb_pg",
        "modelo_versao": "1.0.0",
        "gerado_em": "2026-06-10T10:00:00Z",
        "variaveis_utilizadas": ["frequencia_percentual", "media_geral"],
        "metadados_tecnicos": {
            "framework_ml": "xgboost",
            "janela_corte_dias": 60,
            "calibracao_aplicada": True,
        },
    }
    r_ml1 = client.post(
        "/api/v1/previsoes",
        headers={"X-Service-Token": cred["chave_secreta"]},
        json=payload_ml,
    )
    assert r_ml1.status_code == 201, r_ml1.text

    r_ml_dup = client.post(
        "/api/v1/previsoes",
        headers={"X-Service-Token": cred["chave_secreta"]},
        json=payload_ml,
    )
    assert r_ml_dup.status_code == 409

    with PgSession() as db_ver:
        prev = db_ver.query(PrevisaoRisco).one()
        assert isinstance(prev.id, uuid.UUID)
        assert isinstance(prev.gerado_em, datetime)
        assert prev.gerado_em.tzinfo is not None
        assert prev.metadados_tecnicos == {
            "framework_ml": "xgboost",
            "janela_corte_dias": 60,
            "calibracao_aplicada": True,
        }


# ==============================================================================
# 3. IMPORTAÇÃO 2 ETAPAS, ROLLBACK ATÔMICO E CONCORRÊNCIA ENTRE SESSÕES POSTGRESQL
# ==============================================================================
def test_pg_importacoes_atomicidade_rollback_e_concorrencia(
    pg_client_e_session_factory: tuple[TestClient, sessionmaker[Session], Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, PgSession, _engine = pg_client_e_session_factory
    with PgSession() as db:
        cenario_raw = _criar_cenario_fase4(db)
        ids = {k: v.id for k, v in cenario_raw.items()}

    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # 1. Importação real dos 3 tipos em PostgreSQL (Etapa 1 -> Etapa 2)
    csv_de = (
        ",".join(COLUNAS_MODELO_DADOS_ESCOLARES)
        + "\nEST-PG-01,Turma 1A,MAT,2026,1º Bimestre,94.0,2,8.4,8.6,8.5,8.7,0,Não,Aprovado\n"
    ).encode("utf-8")
    l_de = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("pg_de.csv", csv_de, "text/csv")},
    ).json()
    assert l_de["pode_confirmar"] is True
    assert client.post(f"/api/v1/importacoes/{l_de['id']}/confirmar", headers=headers_prof1).status_code == 200

    csv_av = (
        ",".join(COLUNAS_MODELO_AVALIACOES)
        + "\nAV-PG-01,Prova PG,MAT,Turma 1A,1º Bimestre,2026-05-11,Q01,FECHADA,2.0,A,EST-PG-01,A,Não,,Fácil,Matrizes\n"
    ).encode("utf-8")
    l_av = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("pg_av.csv", csv_av, "text/csv")},
    ).json()
    assert l_av["pode_confirmar"] is True

    # 2. Falha no meio da Etapa 2 no PostgreSQL deve fazer rollback completo
    def _falha_pg(*_a: Any, **kw: Any) -> Any:
        db_tx = kw["db"]
        db_tx.add(
            Avaliacao(
                codigo="AV-PG-ROLLBACK",
                titulo="Não pode ficar no PG",
                escola_id=ids["escola_a"],
                turma_id=ids["turma_1a"],
                disciplina_id=ids["disc_mat"],
                usuario_id=ids["prof1"],
                periodo_letivo="1º Bimestre",
                data_avaliacao=date(2026, 5, 11),
                status="PUBLICADA",
            )
        )
        db_tx.flush()
        raise RuntimeError("Falha simulada PostgreSQL")

    monkeypatch.setattr(
        ImportacaoService,
        "_persistir_confirmacao_avaliacoes",
        staticmethod(_falha_pg),
    )
    r_fail = client.post(f"/api/v1/importacoes/{l_av['id']}/confirmar", headers=headers_prof1)
    assert r_fail.status_code == 500
    monkeypatch.undo()

    with PgSession() as db_chk:
        assert db_chk.query(Avaliacao).count() == 0
        assert db_chk.query(QuestaoAvaliacao).count() == 0
        assert db_chk.query(Estudante).filter(Estudante.codigo_anonimo == "EST-PG-01").count() == 1

    # 3. Dupla confirmação / concorrência lógica: primeira confirma (200), segunda falha com 409 sem duplicar
    assert client.post(f"/api/v1/importacoes/{l_av['id']}/confirmar", headers=headers_prof1).status_code == 200
    assert client.post(f"/api/v1/importacoes/{l_av['id']}/confirmar", headers=headers_prof1).status_code == 409

    csv_at = (
        ",".join(COLUNAS_MODELO_ATIVIDADES)
        + "\nATV-PG-01,Lista PG,MAT,Turma 1A,1º Bimestre,2026,2026-05-20,10.0,EST-PG-01,ENTREGUE,2026-05-19,9.5\n"
    ).encode("utf-8")
    l_at = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("pg_at.csv", csv_at, "text/csv")},
    ).json()
    assert client.post(f"/api/v1/importacoes/{l_at['id']}/confirmar", headers=headers_prof1).status_code == 200

    # 4. Concorrência entre duas sessões PostgreSQL independentes gravando mesma atribuição
    with PgSession() as sess_a, PgSession() as sess_b:
        sess_a.add(
            ProfessorTurma(
                professor_id=ids["prof2"],
                turma_id=ids["turma_1b"],
                disciplina_id=ids["disc_fis"],
            )
        )
        sess_a.commit()

        sess_b.add(
            ProfessorTurma(
                professor_id=ids["prof2"],
                turma_id=ids["turma_1b"],
                disciplina_id=ids["disc_fis"],
            )
        )
        with pytest.raises(IntegrityError):
            sess_b.commit()
        sess_b.rollback()
