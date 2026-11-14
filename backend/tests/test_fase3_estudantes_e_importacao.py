"""
Suíte de testes automatizados da Fase 3:
- Módulo de Estudantes, Histórico Escolar Longitudinal (BoletimPeriodo) e Notas por Disciplina (NotaDisciplina).
- Importação automatizada de datasets escolares em duas etapas (validação/prévia e confirmação atômica).
- Autorização rigorosa (gestor com escola vinculada vs professor restrito a turma+disciplina em ProfessorTurma; bloqueio de administrador).
- Privacidade e anonimização (rejeição de colunas e dados pessoais proibidos pela LGPD / RN01).
- Isolamento de consultas e prevenção de acesso horizontal por troca de IDs.
"""

from typing import Any
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    NotaDisciplina,
    SituacaoFinalPeriodo,
)
from app.modules.importacao.models import LoteImportacao, StatusLoteImportacao
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario
from app.modules.usuarios.schemas import UsuarioCreate
from app.modules.usuarios.service import UsuarioService
from app.scripts.create_admin import criar_administrador_inicial


def _login_headers(client: TestClient, email: str, senha: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": senha},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _criar_cenario_base(db_session: Session) -> dict[str, Any]:
    """
    Cria estrutura escolar completa para testes da Fase 3:
    - Escola A (com Turmas 1A, 2A, 1B e 3A) e Escola B (com Turma 1A-Sul).
    - Disciplinas: Matemática (MAT), Física (FIS) e Química (QUI).
    - Usuários:
      - Admin (`admin@vertice.edu.br`)
      - Gestor Escola A (`gestor.a@vertice.edu.br`, vinculado à Escola A)
      - Gestor Escola B (`gestor.b@vertice.edu.br`, vinculado à Escola B)
      - Gestor Sem Escola (`gestor.sem@vertice.edu.br`, `escola_id=None`)
      - Professor 1 (`prof1@vertice.edu.br`): vinculado a:
          * Matemática — Turma 1A
          * Matemática — Turma 2A
          * Física — Turma 1B
      - Professor 2 (`prof2@vertice.edu.br`): vinculado a:
          * Química — Turma 3A
    """
    admin = criar_administrador_inicial(
        db_session, "Admin Root", "admin@vertice.edu.br", "SenhaForte@123"
    )

    escola_a = Escola(nome="Escola Estadual Norte", codigo="EEN-01", ativo=True)
    escola_b = Escola(nome="Escola Estadual Sul", codigo="EES-02", ativo=True)
    db_session.add_all([escola_a, escola_b])
    db_session.flush()

    turma_1a = Turma(
        nome="Turma 1A",
        serie="1ª Série",
        turno="Matutino",
        ano_letivo=2026,
        escola_id=escola_a.id,
        ativo=True,
    )
    turma_2a = Turma(
        nome="Turma 2A",
        serie="2ª Série",
        turno="Matutino",
        ano_letivo=2026,
        escola_id=escola_a.id,
        ativo=True,
    )
    turma_1b = Turma(
        nome="Turma 1B",
        serie="1ª Série",
        turno="Vespertino",
        ano_letivo=2026,
        escola_id=escola_a.id,
        ativo=True,
    )
    turma_3a = Turma(
        nome="Turma 3A",
        serie="3ª Série",
        turno="Noturno",
        ano_letivo=2026,
        escola_id=escola_a.id,
        ativo=True,
    )
    turma_escola_b = Turma(
        nome="Turma 1A-Sul",
        serie="1ª Série",
        turno="Matutino",
        ano_letivo=2026,
        escola_id=escola_b.id,
        ativo=True,
    )
    db_session.add_all([turma_1a, turma_2a, turma_1b, turma_3a, turma_escola_b])
    db_session.flush()

    disc_mat = Disciplina(nome="Matemática", codigo="MAT", ativo=True)
    disc_fis = Disciplina(nome="Física", codigo="FIS", ativo=True)
    disc_qui = Disciplina(nome="Química", codigo="QUI", ativo=True)
    db_session.add_all([disc_mat, disc_fis, disc_qui])
    db_session.flush()

    gestor_a = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Gestor Escola A",
            email="gestor.a@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.GESTOR,
            escola_id=escola_a.id,
        ),
    )
    gestor_b = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Gestor Escola B",
            email="gestor.b@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.GESTOR,
            escola_id=escola_b.id,
        ),
    )
    gestor_sem_escola = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Gestor Sem Escola",
            email="gestor.sem@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.GESTOR,
            escola_id=None,
        ),
    )
    prof1 = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Professor João",
            email="prof1@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.PROFESSOR,
            escola_id=escola_a.id,
        ),
    )
    prof2 = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Professora Carla",
            email="prof2@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.PROFESSOR,
            escola_id=escola_a.id,
        ),
    )

    # Vínculos do Professor 1: MAT-1A, MAT-2A, FIS-1B
    db_session.add_all(
        [
            ProfessorTurma(
                professor_id=prof1.id,
                turma_id=turma_1a.id,
                disciplina_id=disc_mat.id,
            ),
            ProfessorTurma(
                professor_id=prof1.id,
                turma_id=turma_2a.id,
                disciplina_id=disc_mat.id,
            ),
            ProfessorTurma(
                professor_id=prof1.id,
                turma_id=turma_1b.id,
                disciplina_id=disc_fis.id,
            ),
            # Vínculo da Professora 2: QUI-3A
            ProfessorTurma(
                professor_id=prof2.id,
                turma_id=turma_3a.id,
                disciplina_id=disc_qui.id,
            ),
        ]
    )
    db_session.commit()

    return {
        "admin": admin,
        "gestor_a": gestor_a,
        "gestor_b": gestor_b,
        "gestor_sem_escola": gestor_sem_escola,
        "prof1": prof1,
        "prof2": prof2,
        "escola_a": escola_a,
        "escola_b": escola_b,
        "turma_1a": turma_1a,
        "turma_2a": turma_2a,
        "turma_1b": turma_1b,
        "turma_3a": turma_3a,
        "turma_escola_b": turma_escola_b,
        "disc_mat": disc_mat,
        "disc_fis": disc_fis,
        "disc_qui": disc_qui,
    }


# ==============================================================================
# 13.1. TESTES DE AUTORIZAÇÃO
# ==============================================================================


def test_autorizacao_perfis_e_bloqueio_admin_e_nao_autenticado(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica:
    - Usuário não autenticado -> 401 Unauthorized.
    - Administrador NÃO recebe permissão de importação automaticamente -> 403 Forbidden.
    - Gestor sem escola vinculada NÃO consegue importar -> 403 Forbidden.
    """
    _criar_cenario_base(db_session)
    csv_valido = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-001,Turma 1A,MAT,2026,1º Bimestre,92.5,8.0\n"
    ).encode("utf-8")

    # 1. Sem autenticação -> 401
    resp_unauth = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("dados.csv", csv_valido, "text/csv")},
    )
    assert resp_unauth.status_code == 401

    # 2. Administrador -> 403 Forbidden
    headers_admin = _login_headers(
        client, "admin@vertice.edu.br", "SenhaForte@123"
    )
    resp_admin = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("dados.csv", csv_valido, "text/csv")},
        headers=headers_admin,
    )
    assert resp_admin.status_code == 403

    # 3. Gestor sem escola vinculada -> 403 Forbidden
    headers_gestor_sem = _login_headers(
        client, "gestor.sem@vertice.edu.br", "SenhaForte@123"
    )
    resp_gestor_sem = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("dados.csv", csv_valido, "text/csv")},
        headers=headers_gestor_sem,
    )
    assert resp_gestor_sem.status_code == 403
    assert "escola" in resp_gestor_sem.json()["detail"].lower()


def test_gestor_importa_propria_escola_e_bloqueia_outra_escola(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica:
    - Gestor consegue validar e confirmar importação de turmas de sua própria escola.
    - Gestor NÃO consegue importar dados de turma pertencente a outra escola.
    """
    cenario = _criar_cenario_base(db_session)
    headers_gestor_a = _login_headers(
        client, "gestor.a@vertice.edu.br", "SenhaForte@123"
    )

    # 1. Gestor A importa Turma 3A (pertence à Escola A) -> válido e confirmado
    csv_escola_a = (
        "codigo_anonimo,turma,ano_letivo,periodo_letivo,frequencia,media_geral,historico_reprovacoes,situacao_final\n"
        "EST-101,Turma 3A,2026,1º Bimestre,88.0,7.5,1,\n"
    ).encode("utf-8")

    resp_val = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("boletim_escola_a.csv", csv_escola_a, "text/csv")},
        headers=headers_gestor_a,
    )
    assert resp_val.status_code == 201, resp_val.text
    body_val = resp_val.json()
    assert body_val["pode_confirmar"] is True
    assert body_val["usuario_id"] == str(cenario["gestor_a"].id)
    assert body_val["escola_id"] == str(cenario["escola_a"].id)

    lote_id = body_val["id"]
    resp_conf = client.post(
        f"/api/v1/importacoes/{lote_id}/confirmar",
        headers=headers_gestor_a,
    )
    assert resp_conf.status_code == 200
    assert resp_conf.json()["status"] == "confirmado"
    assert resp_conf.json()["registros_inseridos"] == 1

    # 2. Gestor A tenta importar dados da 'Turma 1A-Sul' (pertence à Escola B)
    csv_escola_b = (
        "codigo_anonimo,turma,ano_letivo,periodo_letivo,frequencia,media_geral\n"
        "EST-999,Turma 1A-Sul,2026,1º Bimestre,90.0,8.0\n"
    ).encode("utf-8")

    resp_outra = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("outra_escola.csv", csv_escola_b, "text/csv")},
        headers=headers_gestor_a,
    )
    assert resp_outra.status_code == 201
    dados_outra = resp_outra.json()
    assert dados_outra["status"] == "com_erros"
    assert dados_outra["pode_confirmar"] is False
    assert len(dados_outra["relatorio_validacao"]["problemas_autorizacao"]) == 1

    # Tentativa de forçar confirmação do lote com erro de autorização -> 409
    resp_conf_bloqueada = client.post(
        f"/api/v1/importacoes/{dados_outra['id']}/confirmar",
        headers=headers_gestor_a,
    )
    assert resp_conf_bloqueada.status_code == 409


# ==============================================================================
# 13.2. AUTOMAÇÃO E RESTRIÇÃO DE ESCOPO POR PROFESSOR
# ==============================================================================


def test_professor_importa_multiplas_turmas_autorizadas_e_ignora_professor_id_csv(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica:
    - O usuário autenticado é identificado automaticamente pela sessão.
    - O lote registra o `usuario_id` do professor autenticado, mesmo se o CSV trouxer
      uma coluna `professor_id` apontando para outro usuário (gera aviso e ignora a coluna).
    - O professor consegue importar um arquivo com múltiplas combinações turma+disciplina
      desde que todas pertençam ao seu escopo (MAT — Turma 1A, MAT — Turma 2A, FIS — Turma 1B).
    - Na Turma 1B, onde o professor só leciona Física (FIS), a disciplina pode inclusive ser
      inferida quando omitida na linha sem ambiguidade.
    """
    cenario = _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )

    outro_prof_id = str(cenario["prof2"].id)
    csv_prof1 = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota,nota_prova,nota_trabalho,professor_id\n"
        f"EST-001,Turma 1A,MAT,2026,1º Bimestre,95.0,8.5,8.0,9.0,{outro_prof_id}\n"
        f"EST-002,Turma 2A,Matemática,2026,1º Bimestre,85.0,7.0,6.5,7.5,{outro_prof_id}\n"
        f"EST-003,Turma 1B,,2026,1º Bimestre,90.0,9.0,9.0,9.0,{outro_prof_id}\n"
    ).encode("utf-8")

    resp_val = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("notas_prof1.csv", csv_prof1, "text/csv")},
        headers=headers_prof1,
    )
    assert resp_val.status_code == 201, resp_val.text
    previa = resp_val.json()

    # Autoria vem exclusivamente do token JWT de prof1, nunca da coluna professor_id do CSV
    assert previa["usuario_id"] == str(cenario["prof1"].id)
    assert previa["usuario_id"] != outro_prof_id
    assert previa["status"] == "validado"
    assert previa["pode_confirmar"] is True
    assert previa["registros_validos"] == 3
    assert previa["quantidade_avisos"] == 1
    assert (
        previa["relatorio_validacao"]["avisos"][0]["categoria"]
        == "autoria_ignorada"
    )

    # Verifica que a linha 3 (Turma 1B sem coluna disciplina preenchida) inferiu Física (FIS)
    item_1b = [
        r for r in previa["previa_registros"] if r["codigo_anonimo"] == "EST-003"
    ][0]
    assert item_1b["disciplina_codigo"] == "FIS"

    # Antes da confirmação, nenhum estudante deve existir no banco
    total_estudantes_antes = (
        db_session.execute(select(Estudante)).scalars().all()
    )
    assert len(total_estudantes_antes) == 0

    # Confirmação da importação
    resp_conf = client.post(
        f"/api/v1/importacoes/{previa['id']}/confirmar",
        headers=headers_prof1,
    )
    assert resp_conf.status_code == 200
    dados_conf = resp_conf.json()
    assert dados_conf["status"] == "confirmado"
    assert dados_conf["usuario_id"] == str(cenario["prof1"].id)
    assert dados_conf["registros_inseridos"] == 3


def test_professor_bloqueado_para_turma_ou_disciplina_sem_vinculo(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica exatamente o exemplo da especificação:
    Professor 1 (vinculado a MAT-1A, MAT-2A, FIS-1B) NÃO pode importar:
    - Matemática — Turma 3A (turma sem vínculo);
    - Física — Turma 2A (disciplina sem vínculo naquela turma);
    - Química — Turma 1A (disciplina sem vínculo);
    - Turma 1A-Sul (outra escola).
    Todos os registros fora do escopo devem aparecer em `problemas_autorizacao` com número da linha.
    """
    _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )

    csv_nao_autorizado = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-001,Turma 1A,MAT,2026,1º Bimestre,95.0,8.5\n"
        "EST-002,Turma 3A,MAT,2026,1º Bimestre,90.0,7.0\n"
        "EST-003,Turma 2A,FIS,2026,1º Bimestre,88.0,6.5\n"
        "EST-004,Turma 1A,QUI,2026,1º Bimestre,80.0,7.5\n"
        "EST-005,Turma 1A-Sul,MAT,2026,1º Bimestre,92.0,9.0\n"
    ).encode("utf-8")

    resp = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("tentativa_escopo_invalido.csv", csv_nao_autorizado, "text/csv")},
        headers=headers_prof1,
    )
    assert resp.status_code == 201
    dados = resp.json()
    assert dados["status"] == "com_erros"
    assert dados["pode_confirmar"] is False
    assert dados["registros_validos"] == 1
    assert dados["quantidade_erros"] == 4

    probs_aut = dados["relatorio_validacao"]["problemas_autorizacao"]
    linhas_bloqueadas = [p["linha"] for p in probs_aut]
    assert linhas_bloqueadas == [3, 4, 5, 6]

    # Tentar confirmar lote com linhas fora do escopo -> bloqueado (409)
    resp_conf = client.post(
        f"/api/v1/importacoes/{dados['id']}/confirmar",
        headers=headers_prof1,
    )
    assert resp_conf.status_code == 409


def test_revalidacao_de_vinculo_no_momento_da_confirmacao(
    client: TestClient, db_session: Session
) -> None:
    """
    Garante que se o vínculo `ProfessorTurma` do professor for revogado ENTRE a Etapa 1 (prévia)
    e a Etapa 2 (confirmação), a confirmação é negada com HTTP 403 e nenhum dado é gravado.
    """
    cenario = _criar_cenario_base(db_session)
    headers_prof2 = _login_headers(
        client, "prof2@vertice.edu.br", "SenhaForte@123"
    )

    csv_prof2 = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-301,Turma 3A,QUI,2026,1º Bimestre,91.0,8.0\n"
    ).encode("utf-8")

    resp_previa = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("qui_3a.csv", csv_prof2, "text/csv")},
        headers=headers_prof2,
    )
    assert resp_previa.status_code == 201
    lote_id = resp_previa.json()["id"]
    assert resp_previa.json()["pode_confirmar"] is True

    # Revoga o vínculo da Professora 2 com a Turma 3A antes da confirmação
    stmt_atrib = select(ProfessorTurma).where(
        ProfessorTurma.professor_id == cenario["prof2"].id
    )
    atrib = db_session.execute(stmt_atrib).scalar_one()
    db_session.delete(atrib)
    db_session.commit()

    # Tenta confirmar o lote já validado -> deve falhar na revalidação (HTTP 403)
    resp_conf = client.post(
        f"/api/v1/importacoes/{lote_id}/confirmar",
        headers=headers_prof2,
    )
    assert resp_conf.status_code == 403
    assert "vínculo" in resp_conf.json()["detail"].lower()

    # Garante que o estudante EST-301 não foi persistido
    est = (
        db_session.execute(
            select(Estudante).where(Estudante.codigo_anonimo == "EST-301")
        )
        .scalar_one_or_none()
    )
    assert est is None


# ==============================================================================
# 13.3. TESTES DE VALIDAÇÃO, FORMATO E ANONIMIZAÇÃO (LGPD / RN01)
# ==============================================================================


def test_validacao_formato_tamanho_vazio_colunas_e_pii(
    client: TestClient, db_session: Session
) -> None:
    """
    Testa:
    - Formato não suportado (.txt / .pdf) -> 415 Unsupported Media Type.
    - Arquivo acima de 10 MB -> 413 Content Too Large.
    - Arquivo vazio -> 400 Bad Request.
    - Colunas obrigatórias ausentes -> status `com_erros` e `colunas_ausentes`.
    - Colunas pessoais proibidas (ex: `nome_estudante`, `cpf`) -> bloqueado na validação.
    - Identificador contendo CPF, e-mail ou nome completo -> bloqueado em `problemas_anonimizacao`.
    """
    _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )

    # 1. Formato não suportado (.txt) -> 415
    resp_415 = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("dados.txt", b"conteudo qualquer", "text/plain")},
        headers=headers_prof1,
    )
    assert resp_415.status_code == 415

    # 2. Arquivo vazio -> 400
    resp_vazio = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("vazio.csv", b"", "text/csv")},
        headers=headers_prof1,
    )
    assert resp_vazio.status_code == 400

    # 3. Arquivo maior que 10 MB -> 413
    payload_grande = b"a" * (10 * 1024 * 1024 + 100)
    resp_413 = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("grande.csv", payload_grande, "text/csv")},
        headers=headers_prof1,
    )
    assert resp_413.status_code == 413

    # 4. Colunas obrigatórias ausentes (sem `periodo_letivo`)
    csv_sem_col = (
        "codigo_anonimo,turma,disciplina,ano_letivo,nota\n"
        "EST-001,Turma 1A,MAT,2026,8.0\n"
    ).encode("utf-8")
    resp_col = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("sem_coluna.csv", csv_sem_col, "text/csv")},
        headers=headers_prof1,
    )
    assert resp_col.status_code == 201
    rel_col = resp_col.json()["relatorio_validacao"]
    assert "periodo_letivo" in rel_col["colunas_ausentes"]
    assert resp_col.json()["pode_confirmar"] is False

    # 5. Colunas pessoais proibidas no cabeçalho (`nome_aluno`, `cpf`)
    csv_col_pii = (
        "codigo_anonimo,nome_aluno,cpf,turma,disciplina,ano_letivo,periodo_letivo\n"
        "EST-001,Maria Silva,123.456.789-00,Turma 1A,MAT,2026,1º Bimestre\n"
    ).encode("utf-8")
    resp_pii = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("com_pii.csv", csv_col_pii, "text/csv")},
        headers=headers_prof1,
    )
    assert resp_pii.status_code == 201
    rel_pii = resp_pii.json()["relatorio_validacao"]
    assert len(rel_pii["colunas_proibidas_pii"]) == 2
    assert resp_pii.json()["pode_confirmar"] is False

    # 6. Valores de CPF, e-mail ou nome pessoal na coluna `codigo_anonimo`
    csv_id_invalido = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,nota\n"
        "123.456.789-00,Turma 1A,MAT,2026,1º Bimestre,8.0\n"
        "aluno@escola.br,Turma 1A,MAT,2026,1º Bimestre,7.5\n"
        "Maria da Silva,Turma 1A,MAT,2026,1º Bimestre,9.0\n"
    ).encode("utf-8")
    resp_anon = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("id_pessoal.csv", csv_id_invalido, "text/csv")},
        headers=headers_prof1,
    )
    assert resp_anon.status_code == 201
    rel_anon = resp_anon.json()["relatorio_validacao"]
    assert len(rel_anon["problemas_anonimizacao"]) == 3
    # Verifica que o relatório de validação NÃO vaza o CPF ou nome pessoal nas mensagens
    mensagens_concat = " ".join(
        p["mensagem"] for p in rel_anon["problemas_anonimizacao"]
    )
    assert "123.456.789-00" not in mensagens_concat
    assert "Maria da Silva" not in mensagens_concat


def test_validacao_tipos_intervalos_duplicidades_e_entidades_inexistentes(
    client: TestClient, db_session: Session
) -> None:
    """
    Testa detecção de:
    - Frequência > 100 ou < 0;
    - Nota > 10 ou não numérica;
    - Duplicidade de (estudante, turma, disciplina, ano, período) no mesmo arquivo;
    - Turma inexistente e disciplina inexistente.
    """
    _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )

    csv_erros = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-001,Turma 1A,MAT,2026,1º Bimestre,120.0,8.0\n"
        "EST-002,Turma 1A,MAT,2026,1º Bimestre,90.0,15.5\n"
        "EST-003,Turma Inexistente,MAT,2026,1º Bimestre,85.0,7.0\n"
        "EST-004,Turma 1A,BIOLOGIA_99,2026,1º Bimestre,85.0,7.0\n"
        "EST-005,Turma 1A,MAT,2026,1º Bimestre,90.0,8.0\n"
        "EST-005,Turma 1A,MAT,2026,1º Bimestre,88.0,7.5\n"
    ).encode("utf-8")

    resp = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("erros_dados.csv", csv_erros, "text/csv")},
        headers=headers_prof1,
    )
    assert resp.status_code == 201
    dados = resp.json()
    assert dados["status"] == "com_erros"
    assert dados["pode_confirmar"] is False
    rel = dados["relatorio_validacao"]
    assert len(rel["valores_invalidos"]) == 4
    assert len(rel["duplicidades"]) == 1
    assert rel["duplicidades"][0]["linha"] == 7


# ==============================================================================
# 13.4. PERSISTÊNCIA, HISTÓRICO LONGITUDINAL, IDEMPOTÊNCIA E TRANSAÇÃO ATÔMICA
# ==============================================================================


def test_historico_longitudinal_idempotencia_e_protecao_situacao_final(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica:
    1. Importação do 1º Bimestre com `situacao_final` vazia (`None` preservado, sem inventar valor).
    2. Importação do 2º Bimestre para o mesmo estudante preserva o 1º Bimestre intacto.
    3. Importação de fechamento do 1º Bimestre com `situacao_final="Aprovado"` atualiza o registro existente.
    4. Reimportação posterior do 1º Bimestre com `situacao_final` em branco NÃO substitui
       `"Aprovado"` por `None` e não duplica registros.
    5. Confirmação repetida do mesmo lote é bloqueada com HTTP 409.
    """
    _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )

    # Passo 1: Importa 1º Bimestre (em andamento -> situacao_final vazia, faltas vazias)
    csv_bim1 = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota,situacao_final\n"
        "EST-500,Turma 1A,MAT,2026,1º Bimestre,92.0,7.5,\n"
    ).encode("utf-8")
    lote1 = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("bim1.csv", csv_bim1, "text/csv")},
        headers=headers_prof1,
    ).json()
    assert lote1["registros_novos"] == 1
    resp_c1 = client.post(
        f"/api/v1/importacoes/{lote1['id']}/confirmar",
        headers=headers_prof1,
    )
    assert resp_c1.status_code == 200

    # Tentar confirmar o mesmo lote novamente -> 409 Conflict
    resp_c1_dup = client.post(
        f"/api/v1/importacoes/{lote1['id']}/confirmar",
        headers=headers_prof1,
    )
    assert resp_c1_dup.status_code == 409

    # Passo 2: Importa 2º Bimestre para o mesmo estudante EST-500
    csv_bim2 = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota,situacao_final\n"
        "EST-500,Turma 1A,MAT,2026,2º Bimestre,96.0,8.5,\n"
    ).encode("utf-8")
    lote2 = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("bim2.csv", csv_bim2, "text/csv")},
        headers=headers_prof1,
    ).json()
    assert lote2["registros_novos"] == 1
    client.post(
        f"/api/v1/importacoes/{lote2['id']}/confirmar",
        headers=headers_prof1,
    )

    # Passo 3: Atualiza 1º Bimestre consolidando situacao_final = Aprovado
    csv_bim1_consolidado = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota,situacao_final\n"
        "EST-500,Turma 1A,MAT,2026,1º Bimestre,92.0,8.0,Aprovado\n"
    ).encode("utf-8")
    lote3 = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("bim1_cons.csv", csv_bim1_consolidado, "text/csv")},
        headers=headers_prof1,
    ).json()
    assert lote3["registros_existentes"] == 1
    assert lote3["registros_novos"] == 0
    resp_c3 = client.post(
        f"/api/v1/importacoes/{lote3['id']}/confirmar",
        headers=headers_prof1,
    ).json()
    assert resp_c3["registros_atualizados"] == 1
    assert resp_c3["registros_inseridos"] == 0

    # Passo 4: Reimporta 1º Bimestre com situacao_final vazia -> NÃO pode apagar "Aprovado"
    csv_bim1_sem_situacao = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota,situacao_final\n"
        "EST-500,Turma 1A,MAT,2026,1º Bimestre,93.0,8.2,\n"
    ).encode("utf-8")
    lote4 = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("bim1_reimp.csv", csv_bim1_sem_situacao, "text/csv")},
        headers=headers_prof1,
    ).json()
    client.post(
        f"/api/v1/importacoes/{lote4['id']}/confirmar",
        headers=headers_prof1,
    )

    # Verifica estado no banco: 1 único estudante EST-500, 2 boletins (1º e 2º Bimestre)
    estudantes = (
        db_session.execute(
            select(Estudante).where(Estudante.codigo_anonimo == "EST-500")
        )
        .scalars()
        .all()
    )
    assert len(estudantes) == 1
    est_obj = estudantes[0]

    boletins = (
        db_session.execute(
            select(BoletimPeriodo).where(
                BoletimPeriodo.estudante_id == est_obj.id
            )
        )
        .scalars()
        .all()
    )
    assert len(boletins) == 2
    mapa_bol = {b.periodo_letivo: b for b in boletins}

    # 1º Bimestre preservou situacao_final = Aprovado e faltas = None (não virou zero)
    assert (
        mapa_bol["1º Bimestre"].situacao_final
        == SituacaoFinalPeriodo.APROVADO
    )
    assert mapa_bol["1º Bimestre"].faltas is None

    # 2º Bimestre permaneceu com situacao_final = None
    assert mapa_bol["2º Bimestre"].situacao_final is None


def test_rollback_atomico_em_caso_de_falha_na_confirmacao(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verifica que se ocorrer uma falha inesperada no meio da gravação do lote,
    toda a transação sofre rollback e nenhum registro parcial é persistido.
    """
    _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )

    csv_duas_linhas = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-701,Turma 1A,MAT,2026,1º Bimestre,90.0,8.0\n"
        "EST-702,Turma 1A,MAT,2026,1º Bimestre,85.0,7.5\n"
    ).encode("utf-8")

    lote = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("atomico.csv", csv_duas_linhas, "text/csv")},
        headers=headers_prof1,
    ).json()

    from app.modules.estudantes.repository import EstudanteRepository

    chamadas = {"count": 0}
    orig_get_nota = EstudanteRepository.get_nota_disciplina

    def _falhar_na_segunda_linha(db: Session, boletim_id: uuid.UUID, disciplina_id: uuid.UUID):  # type: ignore[no-untyped-def]
        chamadas["count"] += 1
        if chamadas["count"] == 2:
            raise RuntimeError("Erro simulado de banco no meio da transação")
        return orig_get_nota(db, boletim_id, disciplina_id)

    monkeypatch.setattr(
        EstudanteRepository, "get_nota_disciplina", _falhar_na_segunda_linha
    )

    resp_conf = client.post(
        f"/api/v1/importacoes/{lote['id']}/confirmar",
        headers=headers_prof1,
    )
    assert resp_conf.status_code == 500

    # Verifica que nem EST-701 nem EST-702 foram gravados (rollback integral)
    restantes = (
        db_session.execute(
            select(Estudante).where(
                Estudante.codigo_anonimo.in_(["EST-701", "EST-702"])
            )
        )
        .scalars()
        .all()
    )
    assert len(restantes) == 0


# ==============================================================================
# 13.5. ISOLAMENTO DE CONSULTAS E DESCARTE DE LOTES
# ==============================================================================


def test_isolamento_consultas_estudantes_e_lotes_entre_professores_e_gestores(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica:
    - Professor 1 visualiza apenas os estudantes e notas de suas turmas e disciplinas.
    - Professor 1 NÃO consegue consultar estudantes ou lotes da Professora 2 (Turma 3A - QUI)
      nem passando IDs diretamente na URL (retorna 404/403).
    - Gestor A visualiza todos os estudantes da Escola A, mas NÃO visualiza estudantes ou
      lotes da Escola B.
    - Descarte de lote funciona para lotes pendentes e bloqueia confirmação posterior.
    """
    cenario = _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )
    headers_prof2 = _login_headers(
        client, "prof2@vertice.edu.br", "SenhaForte@123"
    )
    headers_gestor_a = _login_headers(
        client, "gestor.a@vertice.edu.br", "SenhaForte@123"
    )
    headers_gestor_b = _login_headers(
        client, "gestor.b@vertice.edu.br", "SenhaForte@123"
    )

    # Professor 1 importa estudante EST-P1 na Turma 1A (MAT)
    csv_p1 = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-P1,Turma 1A,MAT,2026,1º Bimestre,95.0,9.0\n"
    ).encode("utf-8")
    lote_p1 = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("p1.csv", csv_p1, "text/csv")},
        headers=headers_prof1,
    ).json()
    client.post(
        f"/api/v1/importacoes/{lote_p1['id']}/confirmar", headers=headers_prof1
    )

    # Professora 2 importa estudante EST-P2 na Turma 3A (QUI)
    csv_p2 = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-P2,Turma 3A,QUI,2026,1º Bimestre,88.0,7.5\n"
    ).encode("utf-8")
    lote_p2 = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("p2.csv", csv_p2, "text/csv")},
        headers=headers_prof2,
    ).json()
    client.post(
        f"/api/v1/importacoes/{lote_p2['id']}/confirmar", headers=headers_prof2
    )

    # 1. Professor 1 lista estudantes -> só vê EST-P1
    lista_p1 = client.get("/api/v1/estudantes", headers=headers_prof1).json()
    assert len(lista_p1) == 1
    assert lista_p1[0]["codigo_anonimo"] == "EST-P1"

    # 2. Professor 1 tenta filtrar por turma_id da Turma 3A (sem vínculo) -> 403 Forbidden
    resp_filtro_proibido = client.get(
        f"/api/v1/estudantes?turma_id={cenario['turma_3a'].id}",
        headers=headers_prof1,
    )
    assert resp_filtro_proibido.status_code == 403

    # 3. Professor 1 tenta acessar por ID o estudante EST-P2 (Turma 3A) -> 404 Not Found
    lista_p2 = client.get("/api/v1/estudantes", headers=headers_prof2).json()
    est_p2_id = lista_p2[0]["id"]
    resp_detalhe_proibido = client.get(
        f"/api/v1/estudantes/{est_p2_id}", headers=headers_prof1
    )
    assert resp_detalhe_proibido.status_code == 404

    # 4. Professor 1 tenta acessar o lote da Professora 2 -> 404 Not Found
    assert (
        client.get(
            f"/api/v1/importacoes/{lote_p2['id']}", headers=headers_prof1
        ).status_code
        == 404
    )

    # 5. Gestor A vê ambos os estudantes da Escola A (EST-P1 e EST-P2)
    lista_gestor_a = client.get(
        "/api/v1/estudantes", headers=headers_gestor_a
    ).json()
    assert len(lista_gestor_a) == 2

    # 6. Gestor B (Escola B) não vê estudantes nem lotes da Escola A
    lista_gestor_b = client.get(
        "/api/v1/estudantes", headers=headers_gestor_b
    ).json()
    assert len(lista_gestor_b) == 0
    assert (
        client.get(
            f"/api/v1/importacoes/{lote_p1['id']}", headers=headers_gestor_b
        ).status_code
        == 404
    )

    # 7. Teste de descarte de lote pendente
    lote_descarte = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("descarte.csv", csv_p1, "text/csv")},
        headers=headers_prof1,
    ).json()
    resp_desc = client.post(
        f"/api/v1/importacoes/{lote_descarte['id']}/descartar",
        headers=headers_prof1,
    )
    assert resp_desc.status_code == 200
    assert resp_desc.json()["status"] == "descartado"

    # Confirmar lote descartado -> 409 Conflict
    assert (
        client.post(
            f"/api/v1/importacoes/{lote_descarte['id']}/confirmar",
            headers=headers_prof1,
        ).status_code
        == 409
    )


# ==============================================================================
# 13.6. CORREÇÕES PONTUAIS DA FASE 3 (ESCOPO ESCOLAR, REVALIDAÇÃO, DISCIPLINA E PII)
# ==============================================================================


def test_professor_multi_escola_e_isolamento_de_escopo_escolar(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica:
    1. Professor com `usuario.escola_id = None` e vínculos `ProfessorTurma` em duas escolas
       distintas (Escola A - Turma 1A/MAT e Escola B - Turma 1A-Sul/MAT) pode importar um lote
       válido para a Escola A e outro lote válido para a Escola B (sem usar arbitrariamente
       apenas a primeira escola em ordem de UUID).
    2. Se o professor enviar um único lote CSV misturando turmas da Escola A e da Escola B,
       o sistema registra erro de `autorizacao` (conflito de escopo escolar no lote) e
       bloqueia a confirmação (`pode_confirmar=False`).
    3. Se o professor multi-escola enviar um CSV onde nenhuma turma válida permite determinar
       a escola alvo do lote, a requisição falha com HTTP 400.
    4. Se um professor possuir `usuario.escola_id` fixado na Escola A, qualquer vínculo
       `ProfessorTurma` apontando para turma da Escola B é ignorado/bloqueado.
    """
    cenario = _criar_cenario_base(db_session)

    # Professor multi-escola (escola_id = None) com vínculo na Escola A (Turma 1A - MAT)
    # e na Escola B (Turma 1A-Sul - MAT)
    prof_multi = Usuario(
        nome="Professor Multi-Escola",
        email="prof.multi@vertice.edu.br",
        senha_hash=get_password_hash("SenhaForte@123"),
        papel=PapelUsuario.PROFESSOR,
        escola_id=None,
        ativo=True,
    )
    db_session.add(prof_multi)
    db_session.flush()

    db_session.add_all(
        [
            ProfessorTurma(
                professor_id=prof_multi.id,
                turma_id=cenario["turma_1a"].id,
                disciplina_id=cenario["disc_mat"].id,
            ),
            ProfessorTurma(
                professor_id=prof_multi.id,
                turma_id=cenario["turma_escola_b"].id,
                disciplina_id=cenario["disc_mat"].id,
            ),
        ]
    )
    db_session.commit()

    headers_multi = _login_headers(
        client, "prof.multi@vertice.edu.br", "SenhaForte@123"
    )

    # 1A. Importação válida apenas para Escola A (Turma 1A)
    csv_escola_a = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-MA-01,Turma 1A,MAT,2026,1º Bimestre,92.0,8.5\n"
    ).encode("utf-8")
    resp_a = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("lote_escola_a.csv", csv_escola_a, "text/csv")},
        headers=headers_multi,
    )
    assert resp_a.status_code == 201
    dados_a = resp_a.json()
    assert dados_a["pode_confirmar"] is True
    assert dados_a["escola_id"] == str(cenario["escola_a"].id)

    # 1B. Importação válida apenas para Escola B (Turma 1A-Sul) — prova que não ficou preso à 1ª escola
    csv_escola_b = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-MB-01,Turma 1A-Sul,MAT,2026,1º Bimestre,90.0,7.8\n"
    ).encode("utf-8")
    resp_b = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("lote_escola_b.csv", csv_escola_b, "text/csv")},
        headers=headers_multi,
    )
    assert resp_b.status_code == 201
    dados_b = resp_b.json()
    assert dados_b["pode_confirmar"] is True
    assert dados_b["escola_id"] == str(cenario["escola_b"].id)
    resp_conf_b = client.post(
        f"/api/v1/importacoes/{dados_b['id']}/confirmar",
        headers=headers_multi,
    )
    assert resp_conf_b.status_code == 200

    # 2. Lote misturando turmas da Escola A (Turma 1A) e Escola B (Turma 1A-Sul) no mesmo arquivo
    csv_misto = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-MA-02,Turma 1A,MAT,2026,1º Bimestre,90.0,8.0\n"
        "EST-MB-02,Turma 1A-Sul,MAT,2026,1º Bimestre,85.0,7.5\n"
    ).encode("utf-8")
    resp_misto = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("lote_misto.csv", csv_misto, "text/csv")},
        headers=headers_multi,
    )
    assert resp_misto.status_code == 201
    dados_misto = resp_misto.json()
    assert dados_misto["status"] == "com_erros"
    assert dados_misto["pode_confirmar"] is False
    assert len(dados_misto["relatorio_validacao"]["problemas_autorizacao"]) >= 1
    assert (
        "conflito de escopo escolar"
        in dados_misto["relatorio_validacao"]["problemas_autorizacao"][0]["mensagem"].lower()
    )

    # 3. Professor multi-escola envia CSV apenas com turma inexistente -> impossível determinar escola única (400)
    csv_sem_escola = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-X-01,Turma Fantasma,MAT,2026,1º Bimestre,90.0,8.0\n"
    ).encode("utf-8")
    resp_sem_escola = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("sem_escola.csv", csv_sem_escola, "text/csv")},
        headers=headers_multi,
    )
    assert resp_sem_escola.status_code == 400

    # 4. Professor 1 (fixado na Escola A via usuario.escola_id) recebe um vínculo inconsistente
    # apontando para Turma 1A-Sul (Escola B) -> o sistema deve bloquear a importação da Turma 1A-Sul
    db_session.add(
        ProfessorTurma(
            professor_id=cenario["prof1"].id,
            turma_id=cenario["turma_escola_b"].id,
            disciplina_id=cenario["disc_mat"].id,
        )
    )
    db_session.commit()

    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )
    resp_prof1_escola_b = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("prof1_escola_b.csv", csv_escola_b, "text/csv")},
        headers=headers_prof1,
    )
    assert resp_prof1_escola_b.status_code == 201
    dados_p1_b = resp_prof1_escola_b.json()
    assert dados_p1_b["pode_confirmar"] is False
    assert dados_p1_b["status"] == "com_erros"


def test_revalidacao_completa_na_confirmacao_turma_inativa_escola_alterada_disciplina_inativa(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica que na Etapa 2 (`POST /api/v1/importacoes/{lote_id}/confirmar`),
    o sistema revalida integralmente:
    1. Se a Turma foi desativada (`turma.ativo = False`) após a prévia -> HTTP 403 e zero gravações.
    2. Se a Turma teve sua escola alterada (`turma.escola_id != lote.escola_id`) após a prévia -> HTTP 403.
    3. Se a Disciplina foi desativada (`disc.ativo = False`) após a prévia -> HTTP 403.
    4. Se a Escola foi desativada (`escola.ativo = False`) após a prévia -> HTTP 403.
    """
    cenario = _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )

    csv_valido = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-REV-01,Turma 1A,MAT,2026,1º Bimestre,91.0,8.0\n"
    ).encode("utf-8")

    # Cria 4 lotes previamente validados enquanto tudo estava ativo e consistente
    lote_turma_inativa = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("rev1.csv", csv_valido, "text/csv")},
        headers=headers_prof1,
    ).json()["id"]

    lote_escola_trocada = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("rev2.csv", csv_valido, "text/csv")},
        headers=headers_prof1,
    ).json()["id"]

    lote_disc_inativa = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("rev3.csv", csv_valido, "text/csv")},
        headers=headers_prof1,
    ).json()["id"]

    lote_escola_inativa = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("rev4.csv", csv_valido, "text/csv")},
        headers=headers_prof1,
    ).json()["id"]

    # Caso 1: Desativa a Turma 1A antes da confirmação
    turma_1a = db_session.get(Turma, cenario["turma_1a"].id)
    assert turma_1a is not None
    turma_1a.ativo = False
    db_session.commit()

    resp1 = client.post(
        f"/api/v1/importacoes/{lote_turma_inativa}/confirmar",
        headers=headers_prof1,
    )
    assert resp1.status_code == 403
    assert "desativada" in resp1.json()["detail"].lower()

    # Reativa Turma 1A e testa Caso 2: Altera a escola da Turma 1A para Escola B antes da confirmação
    turma_1a.ativo = True
    turma_1a.escola_id = cenario["escola_b"].id
    db_session.commit()

    resp2 = client.post(
        f"/api/v1/importacoes/{lote_escola_trocada}/confirmar",
        headers=headers_prof1,
    )
    assert resp2.status_code == 403
    assert "escola" in resp2.json()["detail"].lower()

    # Restaura escola da Turma 1A e testa Caso 3: Desativa a Disciplina MAT antes da confirmação
    turma_1a.escola_id = cenario["escola_a"].id
    disc_mat = db_session.get(Disciplina, cenario["disc_mat"].id)
    assert disc_mat is not None
    disc_mat.ativo = False
    db_session.commit()

    resp3 = client.post(
        f"/api/v1/importacoes/{lote_disc_inativa}/confirmar",
        headers=headers_prof1,
    )
    assert resp3.status_code == 403
    assert "disciplina" in resp3.json()["detail"].lower()

    # Restaura Disciplina MAT e testa Caso 4: Desativa a Escola A antes da confirmação
    disc_mat.ativo = True
    escola_a = db_session.get(Escola, cenario["escola_a"].id)
    assert escola_a is not None
    escola_a.ativo = False
    db_session.commit()

    resp4 = client.post(
        f"/api/v1/importacoes/{lote_escola_inativa}/confirmar",
        headers=headers_prof1,
    )
    assert resp4.status_code == 403
    assert "escola" in resp4.json()["detail"].lower()

    # Garante que EST-REV-01 nunca foi persistido em nenhuma das 4 tentativas bloqueadas
    est = db_session.execute(
        select(Estudante).where(Estudante.codigo_anonimo == "EST-REV-01")
    ).scalar_one_or_none()
    assert est is None


def test_isolamento_estrito_por_disciplina_na_mesma_turma_paginacao_contagem_e_vinculo_geral(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica na mesma turma (`Turma 1A`):
    1. Professor 1 tem vínculo apenas com `MAT` na `Turma 1A`.
    2. Professora 2 recebe vínculo apenas com `QUI` na mesma `Turma 1A`.
    3. Professor 3 recebe vínculo geral (`disciplina_id = None`) na `Turma 1A`.
    4. Professor 1 importa `EST-MAT-1` e `EST-MAT-2` (apenas com notas em MAT).
    5. Professora 2 importa `EST-QUI-1` (apenas com nota em QUI na mesma Turma 1A)
       e também adiciona nota de `QUI` para `EST-MAT-1`.
    6. Quando Professor 1 chama `GET /api/v1/estudantes` (MESMO SEM passar `disciplina_id` na query):
       - Vê apenas `EST-MAT-1` e `EST-MAT-2` (`X-Total-Count == "2"`).
       - NUNCA vê `EST-QUI-1` (que só tem nota em QUI).
       - Ao consultar o detalhe de `EST-MAT-1`, vê apenas a nota de `MAT` (a nota de `QUI` é filtrada).
       - Ao tentar consultar `GET /api/v1/estudantes/{id_est_qui_1}`, recebe `404 Not Found`.
       - A paginação (`skip=0&limit=1` e `skip=1&limit=1`) retorna exatamente 1 estudante por página
         e mantém `X-Total-Count == "2"`.
    7. Quando Professora 2 chama `GET /api/v1/estudantes` (sem `disciplina_id`):
       - Vê apenas `EST-MAT-1` e `EST-QUI-1` (`X-Total-Count == "2"`), pois ambos têm nota em QUI;
       - NUNCA vê `EST-MAT-2` (que só tem nota em MAT).
    8. Quando Professor 3 (`disciplina_id = None`, vínculo geral na Turma 1A) chama `GET /api/v1/estudantes`:
       - Vê todos os 3 estudantes da Turma 1A (`EST-MAT-1`, `EST-MAT-2`, `EST-QUI-1`, `X-Total-Count == "3"`).
    """
    cenario = _criar_cenario_base(db_session)

    # Vincula Professora 2 também à Turma 1A, porém exclusivamente na disciplina QUI
    db_session.add(
        ProfessorTurma(
            professor_id=cenario["prof2"].id,
            turma_id=cenario["turma_1a"].id,
            disciplina_id=cenario["disc_qui"].id,
        )
    )

    # Cria Professor 3 com vínculo geral na Turma 1A (disciplina_id = None)
    prof_geral = Usuario(
        nome="Professor Regente Geral 1A",
        email="prof.geral@vertice.edu.br",
        senha_hash=get_password_hash("SenhaForte@123"),
        papel=PapelUsuario.PROFESSOR,
        escola_id=cenario["escola_a"].id,
        ativo=True,
    )
    db_session.add(prof_geral)
    db_session.flush()
    db_session.add(
        ProfessorTurma(
            professor_id=prof_geral.id,
            turma_id=cenario["turma_1a"].id,
            disciplina_id=None,
        )
    )
    db_session.commit()

    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )
    headers_prof2 = _login_headers(
        client, "prof2@vertice.edu.br", "SenhaForte@123"
    )
    headers_prof_geral = _login_headers(
        client, "prof.geral@vertice.edu.br", "SenhaForte@123"
    )

    # Professor 1 importa EST-MAT-1 e EST-MAT-2 em MAT na Turma 1A
    csv_mat = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-MAT-1,Turma 1A,MAT,2026,1º Bimestre,95.0,9.0\n"
        "EST-MAT-2,Turma 1A,MAT,2026,1º Bimestre,88.0,7.5\n"
    ).encode("utf-8")
    lote_mat = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("mat_1a.csv", csv_mat, "text/csv")},
        headers=headers_prof1,
    ).json()
    client.post(
        f"/api/v1/importacoes/{lote_mat['id']}/confirmar", headers=headers_prof1
    )

    # Professora 2 importa EST-QUI-1 (exclusivo de QUI) e EST-MAT-1 (nota de QUI) na mesma Turma 1A
    csv_qui = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia,nota\n"
        "EST-QUI-1,Turma 1A,QUI,2026,1º Bimestre,90.0,8.0\n"
        "EST-MAT-1,Turma 1A,QUI,2026,1º Bimestre,95.0,6.5\n"
    ).encode("utf-8")
    lote_qui = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("qui_1a.csv", csv_qui, "text/csv")},
        headers=headers_prof2,
    ).json()
    client.post(
        f"/api/v1/importacoes/{lote_qui['id']}/confirmar", headers=headers_prof2
    )

    # 1. Consulta do Professor 1 SEM passar disciplina_id -> deve filtrar automaticamente por MAT
    resp_p1 = client.get("/api/v1/estudantes", headers=headers_prof1)
    assert resp_p1.status_code == 200
    assert resp_p1.headers.get("X-Total-Count") == "2"
    codigos_p1 = [e["codigo_anonimo"] for e in resp_p1.json()]
    assert codigos_p1 == ["EST-MAT-1", "EST-MAT-2"]
    assert "EST-QUI-1" not in codigos_p1

    # 2. Paginação consistente para Professor 1
    resp_p1_pag1 = client.get(
        "/api/v1/estudantes?skip=0&limit=1", headers=headers_prof1
    )
    assert resp_p1_pag1.status_code == 200
    assert resp_p1_pag1.headers.get("X-Total-Count") == "2"
    assert len(resp_p1_pag1.json()) == 1
    assert resp_p1_pag1.json()[0]["codigo_anonimo"] == "EST-MAT-1"

    resp_p1_pag2 = client.get(
        "/api/v1/estudantes?skip=1&limit=1", headers=headers_prof1
    )
    assert resp_p1_pag2.status_code == 200
    assert resp_p1_pag2.headers.get("X-Total-Count") == "2"
    assert len(resp_p1_pag2.json()) == 1
    assert resp_p1_pag2.json()[0]["codigo_anonimo"] == "EST-MAT-2"

    # 3. Detalhe de EST-MAT-1 visto pelo Professor 1 -> deve exibir apenas a nota de MAT, ocultando QUI
    id_est_mat_1 = resp_p1_pag1.json()[0]["id"]
    detalhe_p1 = client.get(
        f"/api/v1/estudantes/{id_est_mat_1}", headers=headers_prof1
    ).json()
    assert len(detalhe_p1["boletins"]) == 1
    notas_vistas_p1 = detalhe_p1["boletins"][0]["notas_disciplina"]
    assert len(notas_vistas_p1) == 1
    assert notas_vistas_p1[0]["disciplina_codigo"] == "MAT"

    # 4. Consulta da Professora 2 SEM passar disciplina_id -> vê apenas EST-MAT-1 e EST-QUI-1
    resp_p2 = client.get("/api/v1/estudantes", headers=headers_prof2)
    assert resp_p2.status_code == 200
    assert resp_p2.headers.get("X-Total-Count") == "2"
    codigos_p2 = [e["codigo_anonimo"] for e in resp_p2.json()]
    assert codigos_p2 == ["EST-MAT-1", "EST-QUI-1"]
    assert "EST-MAT-2" not in codigos_p2

    # 5. Professor 1 tenta acessar diretamente o ID de EST-QUI-1 (mesma Turma 1A, mas outra disciplina) -> 404
    id_est_qui_1 = [
        e["id"] for e in resp_p2.json() if e["codigo_anonimo"] == "EST-QUI-1"
    ][0]
    resp_p1_acessa_qui = client.get(
        f"/api/v1/estudantes/{id_est_qui_1}", headers=headers_prof1
    )
    assert resp_p1_acessa_qui.status_code == 404

    # 6. Professor Geral (disciplina_id = None na Turma 1A) vê todos os 3 estudantes da Turma 1A
    resp_geral = client.get("/api/v1/estudantes", headers=headers_prof_geral)
    assert resp_geral.status_code == 200
    assert resp_geral.headers.get("X-Total-Count") == "3"
    codigos_geral = [e["codigo_anonimo"] for e in resp_geral.json()]
    assert codigos_geral == ["EST-MAT-1", "EST-MAT-2", "EST-QUI-1"]


def test_privacidade_headers_alternativos_padroes_pii_e_nao_exposicao_de_valores(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica o fortalecimento da validação de privacidade (LGPD / RN01):
    1. Cabeçalhos alternativos com variações de caixa, acentuação e separadores
       (`Nome Completo`, `ALUNO_NOME`, `Estudante-Nome`, `CPF_ do_Aluno`, `E-mail_Estudante`,
       `Telefone Responsável`, `Data de Nascimento`) são detectados e bloqueados.
    2. Valores com padrão de CPF (formatado ou 11 dígitos), e-mail, telefone ou nome pessoal
       (mesmo um único prenome alfabético como `Mariana` ou nome composto) em `codigo_anonimo`
       ou em colunas extras são rejeitados.
    3. Nenhum dado pessoal sensível presente no CSV é reproduzido nas mensagens de erro do relatório.
    """
    _criar_cenario_base(db_session)
    headers_prof1 = _login_headers(
        client, "prof1@vertice.edu.br", "SenhaForte@123"
    )

    # 1. Cabeçalhos alternativos proibidos
    csv_headers_alt = (
        "codigo_anonimo,Nome Completo,ALUNO_NOME,CPF-do-Aluno,E-mail do Estudante,Telefone_Responsavel,turma,disciplina,ano_letivo,periodo_letivo\n"
        "EST-001,Joao Pereira,Joao,123.456.789-00,joao@gmail.com,(11) 98765-4321,Turma 1A,MAT,2026,1º Bimestre\n"
    ).encode("utf-8")
    resp_h = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("headers_alt.csv", csv_headers_alt, "text/csv")},
        headers=headers_prof1,
    )
    assert resp_h.status_code == 201
    rel_h = resp_h.json()["relatorio_validacao"]
    assert resp_h.json()["pode_confirmar"] is False
    assert len(rel_h["colunas_proibidas_pii"]) == 5

    # 2. Valores PII em `codigo_anonimo` e em coluna extra arbitrária (`observacao_interna`)
    csv_valores_pii = (
        "codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,nota,observacao_interna\n"
        "12345678901,Turma 1A,MAT,2026,1º Bimestre,8.0,ok\n"
        "Carlos Eduardo,Turma 1A,MAT,2026,1º Bimestre,7.5,ok\n"
        "Mariana,Turma 1A,MAT,2026,1º Bimestre,9.0,ok\n"
        "(11) 99887-6655,Turma 1A,MAT,2026,1º Bimestre,8.5,ok\n"
        "EST-900,Turma 1A,MAT,2026,1º Bimestre,8.0,Contato: maria.souza@escola.org ou 987.654.321-11\n"
    ).encode("utf-8")
    resp_v = client.post(
        "/api/v1/importacoes/validar",
        files={"arquivo": ("valores_pii.csv", csv_valores_pii, "text/csv")},
        headers=headers_prof1,
    )
    assert resp_v.status_code == 201
    dados_v = resp_v.json()
    assert dados_v["pode_confirmar"] is False
    rel_v = dados_v["relatorio_validacao"]
    assert len(rel_v["problemas_anonimizacao"]) >= 5

    # Garante que NENHUM valor sensível foi ecoado no JSON de resposta
    corpo_str = resp_v.text
    for segredo_pii in [
        "12345678901",
        "Carlos Eduardo",
        "Mariana",
        "99887-6655",
        "maria.souza@escola.org",
        "987.654.321-11",
    ]:
        assert segredo_pii not in corpo_str


def test_integracao_postgres_fase3_importacao_isolamento_e_revalidacao() -> None:
    """
    Teste de integração real na instância PostgreSQL local (`localhost:5432`),
    verificando em banco PostgreSQL real:
    - Validação e confirmação de lote por professor;
    - Isolamento estrito de consultas por disciplina (`list_by_professor` e `count_by_professor`)
      sem vazamento de estudantes de outras disciplinas na mesma turma;
    - Revalidação de turma ativa na confirmação.
    """
    from pathlib import Path
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import ENV_FILE_PATH, Settings
    from app.modules.estudantes.service import EstudanteService
    from app.modules.importacao.service import ImportacaoService

    if not Path(ENV_FILE_PATH).exists():
        pytest.skip("Arquivo .env não encontrado para teste de integração PostgreSQL.")

    pg_settings = Settings(_env_file=str(ENV_FILE_PATH), DATABASE_URL=None)  # type: ignore[call-arg]
    pg_engine = create_engine(pg_settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
    PgSession = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    with pg_engine.connect() as conn:
        trans = conn.begin()
        session = PgSession(bind=conn)
        try:
            escola = Escola(
                nome="Escola PG Fase 3", codigo="PG-F3-001", ativo=True
            )
            disc_mat = Disciplina(
                nome="Matemática PG", codigo="MAT-PG", ativo=True
            )
            disc_qui = Disciplina(
                nome="Química PG", codigo="QUI-PG", ativo=True
            )
            session.add_all([escola, disc_mat, disc_qui])
            session.flush()

            turma = Turma(
                nome="Turma PG 1A",
                serie="1ª Série",
                turno="Matutino",
                ano_letivo=2026,
                escola_id=escola.id,
                ativo=True,
            )
            prof_mat = Usuario(
                nome="Prof Mat PG",
                email="prof.mat.pg.f3@vertice.edu.br",
                senha_hash=get_password_hash("SenhaForte@123"),
                papel=PapelUsuario.PROFESSOR,
                escola_id=escola.id,
                ativo=True,
            )
            prof_qui = Usuario(
                nome="Prof Qui PG",
                email="prof.qui.pg.f3@vertice.edu.br",
                senha_hash=get_password_hash("SenhaForte@123"),
                papel=PapelUsuario.PROFESSOR,
                escola_id=escola.id,
                ativo=True,
            )
            session.add_all([turma, prof_mat, prof_qui])
            session.flush()

            session.add_all(
                [
                    ProfessorTurma(
                        professor_id=prof_mat.id,
                        turma_id=turma.id,
                        disciplina_id=disc_mat.id,
                    ),
                    ProfessorTurma(
                        professor_id=prof_qui.id,
                        turma_id=turma.id,
                        disciplina_id=disc_qui.id,
                    ),
                ]
            )
            session.flush()

            # Cria estudante com nota apenas em MAT e outro estudante com nota apenas em QUI na mesma turma
            est_mat = Estudante(
                escola_id=escola.id,
                codigo_anonimo="EST-PG-MAT-01",
                historico_reprovacoes=0,
                ativo=True,
            )
            est_qui = Estudante(
                escola_id=escola.id,
                codigo_anonimo="EST-PG-QUI-01",
                historico_reprovacoes=0,
                ativo=True,
            )
            session.add_all([est_mat, est_qui])
            session.flush()

            bol_mat = BoletimPeriodo(
                estudante_id=est_mat.id,
                escola_id=escola.id,
                turma_id=turma.id,
                ano_letivo=2026,
                periodo_letivo="1º Bimestre",
                frequencia_percentual=94.0,
                historico_reprovacoes=0,
            )
            bol_qui = BoletimPeriodo(
                estudante_id=est_qui.id,
                escola_id=escola.id,
                turma_id=turma.id,
                ano_letivo=2026,
                periodo_letivo="1º Bimestre",
                frequencia_percentual=91.0,
                historico_reprovacoes=0,
            )
            session.add_all([bol_mat, bol_qui])
            session.flush()

            session.add_all(
                [
                    NotaDisciplina(
                        boletim_id=bol_mat.id,
                        disciplina_id=disc_mat.id,
                        nota=8.5,
                    ),
                    NotaDisciplina(
                        boletim_id=bol_qui.id,
                        disciplina_id=disc_qui.id,
                        nota=7.5,
                    ),
                ]
            )
            session.flush()

            # Consulta via PostgreSQL real para Prof MAT sem filtro explícito de disciplina
            lista_mat = EstudanteService.listar_estudantes(session, prof_mat)
            total_mat = EstudanteService.contar_estudantes(session, prof_mat)
            assert total_mat == 1
            assert len(lista_mat) == 1
            assert lista_mat[0].codigo_anonimo == "EST-PG-MAT-01"

            # Revalidação de confirmação em PostgreSQL quando a turma é desativada
            turma.ativo = False
            session.flush()

            from fastapi import HTTPException

            lote_pg = LoteImportacao(
                usuario_id=prof_mat.id,
                escola_id=escola.id,
                nome_arquivo="teste_pg.csv",
                hash_arquivo="abc123hash",
                status=StatusLoteImportacao.VALIDADO,
                total_linhas=1,
                registros_validos=1,
            )
            session.add(lote_pg)
            session.flush()

            with pytest.raises(HTTPException) as exc_info:
                ImportacaoService._revalidar_autorizacao_na_confirmacao(
                    session,
                    prof_mat,
                    lote_pg,
                    [
                        {
                            "escola_id": str(escola.id),
                            "turma_id": str(turma.id),
                            "turma_nome": turma.nome,
                            "disciplina_id": str(disc_mat.id),
                            "disciplina_nome": disc_mat.nome,
                        }
                    ],
                )
            assert exc_info.value.status_code == 403
        finally:
            session.close()
            if trans.is_active:
                trans.rollback()
            pg_engine.dispose()



