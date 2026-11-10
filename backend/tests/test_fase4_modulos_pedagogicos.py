"""
Suíte completa de testes automatizados da Fase 4:
- Módulo de Avaliações, Questões e Respostas (Bloco B — Mapa de Acertos).
- Módulo de Participação, Atividades e Entregas (Bloco C — Geração de Entregas Esperadas).
- Módulo de Acompanhamento Pedagógico (Registros individuais/coletivos e trilha de auditoria).
- Módulo de Indicadores (Gerais, Avaliações e Participação).
- Extensão do fluxo de Importação de Datasets em Duas Etapas (`AVALIACOES` e `ATIVIDADES`).
- Controle de acesso (RBAC), isolamento multi-escola e por turma+disciplina, e integração real PostgreSQL.
"""

from datetime import date, timedelta
from typing import Any
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.database.connection import engine as pg_engine
from app.modules.acompanhamento.models import (
    AcompanhamentoPedagogico,
    OrigemAcompanhamento,
)
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.avaliacoes.models import (
    Avaliacao,
    FaixaDificuldadeQuestao,
    QuestaoAvaliacao,
    RespostaAvaliacao,
    TipoQuestao,
)
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    NotaDisciplina,
    SituacaoFinalPeriodo,
)
from app.modules.importacao.models import StatusLoteImportacao, TipoImportacao
from app.modules.participacao.models import (
    Atividade,
    EntregaAtividade,
    StatusEntregaAtividade,
)
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario
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


def _criar_cenario_fase4(db_session: Session) -> dict[str, Any]:
    """
    Cria estrutura escolar completa com:
    - Escola A (Turmas 1A, 1B e 3A) e Escola B (Turma 1A-Sul).
    - Disciplinas: Matemática (MAT), Física (FIS) e Química (QUI).
    - Usuários: Admin, Gestor A, Gestor B, Professor 1 (MAT em 1A, FIS em 1B), Professor 2 (QUI em 3A).
    - Estudantes pré-cadastrados (via modelo de dados escolares):
      * EST-001, EST-002 e EST-003 vinculados à Turma 1A (Escola A) no 1º Bimestre de 2026.
      * EST-004 vinculado à Turma 3A (Escola A) no 1º Bimestre de 2026.
      * EST-B01 vinculado à Turma 1A-Sul (Escola B) no 1º Bimestre de 2026.
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
    db_session.add_all([turma_1a, turma_1b, turma_3a, turma_escola_b])
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
            nome="Professora Ana",
            email="prof2@vertice.edu.br",
            senha="SenhaForte@123",
            papel=PapelUsuario.PROFESSOR,
            escola_id=escola_a.id,
        ),
    )

    db_session.add_all(
        [
            ProfessorTurma(
                professor_id=prof1.id,
                turma_id=turma_1a.id,
                disciplina_id=disc_mat.id,
            ),
            ProfessorTurma(
                professor_id=prof1.id,
                turma_id=turma_1b.id,
                disciplina_id=disc_fis.id,
            ),
            ProfessorTurma(
                professor_id=prof2.id,
                turma_id=turma_3a.id,
                disciplina_id=disc_qui.id,
            ),
        ]
    )
    db_session.flush()

    # Estudantes da Turma 1A (Escola A)
    est1 = Estudante(
        codigo_anonimo="EST-001",
        escola_id=escola_a.id,
        historico_reprovacoes=0,
        ativo=True,
    )
    est2 = Estudante(
        codigo_anonimo="EST-002",
        escola_id=escola_a.id,
        historico_reprovacoes=1,
        ativo=True,
    )
    est3 = Estudante(
        codigo_anonimo="EST-003",
        escola_id=escola_a.id,
        historico_reprovacoes=0,
        ativo=True,
    )
    # Estudante da Turma 3A (Escola A)
    est4 = Estudante(
        codigo_anonimo="EST-004",
        escola_id=escola_a.id,
        historico_reprovacoes=0,
        ativo=True,
    )
    # Estudante da Turma 1A-Sul (Escola B)
    est_b1 = Estudante(
        codigo_anonimo="EST-B01",
        escola_id=escola_b.id,
        historico_reprovacoes=0,
        ativo=True,
    )
    db_session.add_all([est1, est2, est3, est4, est_b1])
    db_session.flush()

    b1 = BoletimPeriodo(
        estudante_id=est1.id,
        escola_id=escola_a.id,
        turma_id=turma_1a.id,
        ano_letivo=2026,
        periodo_letivo="1º Bimestre",
        frequencia_percentual=92.0,
        faltas=2,
        media_geral=8.5,
        situacao_final=SituacaoFinalPeriodo.APROVADO,
    )
    b2 = BoletimPeriodo(
        estudante_id=est2.id,
        escola_id=escola_a.id,
        turma_id=turma_1a.id,
        ano_letivo=2026,
        periodo_letivo="1º Bimestre",
        frequencia_percentual=70.0,
        faltas=12,
        media_geral=4.5,
        situacao_final=SituacaoFinalPeriodo.REPROVADO,
    )
    b3 = BoletimPeriodo(
        estudante_id=est3.id,
        escola_id=escola_a.id,
        turma_id=turma_1a.id,
        ano_letivo=2026,
        periodo_letivo="1º Bimestre",
        frequencia_percentual=60.0,
        faltas=20,
        media_geral=5.0,
        situacao_final=SituacaoFinalPeriodo.EVADIDO,
    )
    b4 = BoletimPeriodo(
        estudante_id=est4.id,
        escola_id=escola_a.id,
        turma_id=turma_3a.id,
        ano_letivo=2026,
        periodo_letivo="1º Bimestre",
        frequencia_percentual=88.0,
        faltas=4,
        media_geral=7.0,
        situacao_final=SituacaoFinalPeriodo.APROVADO,
    )
    b_sul = BoletimPeriodo(
        estudante_id=est_b1.id,
        escola_id=escola_b.id,
        turma_id=turma_escola_b.id,
        ano_letivo=2026,
        periodo_letivo="1º Bimestre",
        frequencia_percentual=95.0,
        faltas=1,
        media_geral=9.0,
        situacao_final=SituacaoFinalPeriodo.APROVADO,
    )
    db_session.add_all([b1, b2, b3, b4, b_sul])
    db_session.flush()

    db_session.add_all(
        [
            NotaDisciplina(
                boletim_id=b1.id,
                disciplina_id=disc_mat.id,
                nota=8.5,
                frequencia_percentual=92.0,
            ),
            NotaDisciplina(
                boletim_id=b2.id,
                disciplina_id=disc_mat.id,
                nota=4.5,
                frequencia_percentual=70.0,
            ),
            NotaDisciplina(
                boletim_id=b3.id,
                disciplina_id=disc_mat.id,
                nota=5.0,
                frequencia_percentual=60.0,
            ),
            NotaDisciplina(
                boletim_id=b4.id,
                disciplina_id=disc_qui.id,
                nota=7.0,
                frequencia_percentual=88.0,
            ),
        ]
    )
    db_session.commit()

    return {
        "admin": admin,
        "escola_a": escola_a,
        "escola_b": escola_b,
        "turma_1a": turma_1a,
        "turma_1b": turma_1b,
        "turma_3a": turma_3a,
        "turma_escola_b": turma_escola_b,
        "disc_mat": disc_mat,
        "disc_fis": disc_fis,
        "disc_qui": disc_qui,
        "gestor_a": gestor_a,
        "gestor_b": gestor_b,
        "prof1": prof1,
        "prof2": prof2,
        "est1": est1,
        "est2": est2,
        "est3": est3,
        "est4": est4,
        "est_b1": est_b1,
    }


# ==============================================================================
# 1. TESTES DO MÓDULO DE AVALIAÇÕES, QUESTÕES E RESPOSTAS (BLOCO B)
# ==============================================================================
def test_avaliacoes_fluxo_completo_questoes_e_respostas(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Testa:
    - Criação de avaliação por professor autorizado na turma+disciplina.
    - Bloqueio de criação em turma/disciplina sem vínculo (403) e por administrador (403).
    - Cadastro de questões FECHADA e ABERTA, validação de gabarito e pesos.
    - Registro de respostas válidas, respostas em branco (`em_branco=True`) e bloqueio de duplicidade (409).
    - Validação de nota > valor_questao (422) e estudante inexistente (404).
    - Isolamento entre professores e entre escolas.
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_prof2 = _login_headers(client, "prof2@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")
    headers_gestor_b = _login_headers(client, "gestor.b@vertice.edu.br", "SenhaForte@123")
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")

    # Administrador não pode criar avaliações operacionais (403)
    resp_admin = client.post(
        "/api/v1/avaliacoes",
        headers=headers_admin,
        json={
            "codigo": "AV-ADMIN",
            "titulo": "Prova Admin",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_avaliacao": "2026-04-10",
        },
    )
    assert resp_admin.status_code == 403

    # Professor 1 tenta criar avaliação em Física na Turma 1A (só tem vínculo de MAT em 1A) -> 403
    resp_sem_vinc_disc = client.post(
        "/api/v1/avaliacoes",
        headers=headers_prof1,
        json={
            "codigo": "AV-PROIBIDA",
            "titulo": "Prova de Física 1A",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_fis"].id),
            "periodo_letivo": "1º Bimestre",
            "data_avaliacao": "2026-04-10",
        },
    )
    assert resp_sem_vinc_disc.status_code == 403

    # Professor 1 tenta criar avaliação na Turma 3A (não vinculada) -> 403
    resp_sem_vinc_turma = client.post(
        "/api/v1/avaliacoes",
        headers=headers_prof1,
        json={
            "codigo": "AV-PROIBIDA-3A",
            "titulo": "Prova 3A",
            "turma_id": str(cenario["turma_3a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_avaliacao": "2026-04-10",
        },
    )
    assert resp_sem_vinc_turma.status_code == 403

    # Professor 1 cria avaliação válida em Matemática na Turma 1A -> 201
    resp_av = client.post(
        "/api/v1/avaliacoes",
        headers=headers_prof1,
        json={
            "codigo": "AV-MAT-01",
            "titulo": "Avaliação Bimestral de Matemática",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_avaliacao": "2026-04-10",
        },
    )
    assert resp_av.status_code == 201, resp_av.text
    av_data = resp_av.json()
    avaliacao_id = av_data["id"]
    assert av_data["usuario_id"] == str(cenario["prof1"].id)
    assert av_data["escola_id"] == str(cenario["escola_a"].id)

    # Questão FECHADA sem alternativa_correta deve ser rejeitada (422)
    resp_q_invalida = client.post(
        f"/api/v1/avaliacoes/{avaliacao_id}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q01",
            "tipo_questao": "FECHADA",
            "valor_questao": 2.0,
        },
    )
    assert resp_q_invalida.status_code == 422

    # Questão ABERTA com alternativa_correta preenchida deve ser rejeitada (422)
    resp_q_aberta_invalida = client.post(
        f"/api/v1/avaliacoes/{avaliacao_id}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q02",
            "tipo_questao": "ABERTA",
            "alternativa_correta": "A",
            "valor_questao": 3.0,
        },
    )
    assert resp_q_aberta_invalida.status_code == 422

    # Cria Questão Q01 (FECHADA, gabarito B, peso 2.0)
    resp_q1 = client.post(
        f"/api/v1/avaliacoes/{avaliacao_id}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q01",
            "tipo_questao": "FECHADA",
            "alternativa_correta": "B",
            "valor_questao": 2.0,
            "faixa_dificuldade": "Adequada",
            "topico": "Funções Afins",
        },
    )
    assert resp_q1.status_code == 201, resp_q1.text
    q1_id = resp_q1.json()["id"]

    # Cria Questão Q02 (ABERTA, peso 3.0)
    resp_q2 = client.post(
        f"/api/v1/avaliacoes/{avaliacao_id}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q02",
            "tipo_questao": "ABERTA",
            "valor_questao": 3.0,
            "faixa_dificuldade": "Difícil",
            "topico": "Resolução de Problemas",
        },
    )
    assert resp_q2.status_code == 201, resp_q2.text
    q2_id = resp_q2.json()["id"]

    # Registra resposta de EST-001 na Q01 (acertou B -> nota_obtida = 2.0, acertou = True)
    resp_r1 = client.post(
        f"/api/v1/questoes/{q1_id}/respostas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "alternativa_marcada": "B",
        },
    )
    assert resp_r1.status_code == 201, resp_r1.text
    r1_data = resp_r1.json()
    assert r1_data["acertou"] is True
    assert r1_data["em_branco"] is False
    assert r1_data["nota_obtida"] == 2.0

    # Duplicidade de resposta para o mesmo estudante e questão é bloqueada (409)
    resp_dup = client.post(
        f"/api/v1/questoes/{q1_id}/respostas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "alternativa_marcada": "A",
        },
    )
    assert resp_dup.status_code == 409

    # Registra resposta em branco de EST-002 na Q01
    resp_r2_branco = client.post(
        f"/api/v1/questoes/{q1_id}/respostas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-002",
            "alternativa_marcada": "BRANCO",
        },
    )
    assert resp_r2_branco.status_code == 201, resp_r2_branco.text
    r2_data = resp_r2_branco.json()
    assert r2_data["em_branco"] is True
    assert r2_data["alternativa_marcada"] == "BRANCO"
    assert r2_data["nota_obtida"] == 0.0
    assert r2_data["acertou"] is False

    # Registra resposta errada de EST-003 na Q01 (marcou D -> nota 0.0, acertou False)
    resp_r3_erro = client.post(
        f"/api/v1/questoes/{q1_id}/respostas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-003",
            "alternativa_marcada": "D",
        },
    )
    assert resp_r3_erro.status_code == 201
    assert resp_r3_erro.json()["acertou"] is False
    assert resp_r3_erro.json()["em_branco"] is False
    assert resp_r3_erro.json()["nota_obtida"] == 0.0

    # Nota superior ao valor da questão aberta (3.0) deve falhar (422)
    resp_nota_acima = client.post(
        f"/api/v1/questoes/{q2_id}/respostas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "nota_obtida": 3.5,
        },
    )
    assert resp_nota_acima.status_code == 422

    # Registra resposta aberta válida para EST-001 (nota 2.5 de 3.0 -> >= 60%, acertou=True)
    resp_q2_r1 = client.post(
        f"/api/v1/questoes/{q2_id}/respostas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "nota_obtida": 2.5,
        },
    )
    assert resp_q2_r1.status_code == 201
    assert resp_q2_r1.json()["acertou"] is True
    assert resp_q2_r1.json()["nota_obtida"] == 2.5

    # Estudante inexistente nunca deve ser criado via avaliações (404)
    resp_est_inex = client.post(
        f"/api/v1/questoes/{q1_id}/respostas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-999",
            "alternativa_marcada": "B",
        },
    )
    assert resp_est_inex.status_code == 404

    # Isolamento: Professor 2 (vinculado apenas à Turma 3A) não pode acessar avaliação da Turma 1A
    resp_prof2_get = client.get(
        f"/api/v1/avaliacoes/{avaliacao_id}",
        headers=headers_prof2,
    )
    assert resp_prof2_get.status_code == 403

    # Isolamento entre escolas: Gestor B não pode acessar avaliação da Escola A
    resp_gestor_b = client.get(
        f"/api/v1/avaliacoes/{avaliacao_id}",
        headers=headers_gestor_b,
    )
    assert resp_gestor_b.status_code == 403

    # Gestor A (mesma escola) pode consultar a avaliação e suas respostas
    resp_gestor_a = client.get(
        f"/api/v1/avaliacoes/{avaliacao_id}/respostas",
        headers=headers_gestor_a,
    )
    assert resp_gestor_a.status_code == 200
    assert len(resp_gestor_a.json()) == 4


# ==============================================================================
# 2. TESTES DO MÓDULO DE PARTICIPAÇÃO, ATIVIDADES E ENTREGAS ESPERADAS (BLOCO C)
# ==============================================================================
def test_participacao_geracao_entregas_esperadas_e_status(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Testa:
    - Criação de atividade e geração obrigatória e idempotente de entregas esperadas.
    - Nenhum estudante novo é criado; apenas estudantes elegíveis da turma (EST-001, EST-002, EST-003).
    - Notas ausentes permanecem `None` (`null`), nunca convertidas em `0`.
    - Status de entrega calculados/validados (`ENTREGUE` no prazo, `ATRASADO` após prazo,
      `PENDENTE` antes do prazo, `NAO_ENTREGUE` após vencimento).
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_prof2 = _login_headers(client, "prof2@vertice.edu.br", "SenhaForte@123")

    prazo_futuro = (date.today() + timedelta(days=5)).isoformat()

    # Cria atividade sem gerar automaticamente na criação para testar o endpoint explícito
    resp_ativ = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-MAT-01",
            "titulo": "Lista de Exercícios 01",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": prazo_futuro,
            "nota_maxima": 10.0,
            "gerar_entregas_esperadas": False,
        },
    )
    assert resp_ativ.status_code == 201, resp_ativ.text
    atividade_id = resp_ativ.json()["id"]

    # Geração explícita de entregas esperadas (1ª execução -> cria 3 entregas PENDENTES com nota=None)
    resp_gen1 = client.post(
        f"/api/v1/atividades/{atividade_id}/gerar-entregas-esperadas",
        headers=headers_prof1,
    )
    assert resp_gen1.status_code == 200, resp_gen1.text
    gen1_data = resp_gen1.json()
    assert gen1_data["total_estudantes_elegiveis"] == 3
    assert gen1_data["entregas_criadas"] == 3
    assert gen1_data["entregas_ja_existentes"] == 0

    # Idempotência: 2ª execução -> 0 criadas, 3 já existentes
    resp_gen2 = client.post(
        f"/api/v1/atividades/{atividade_id}/gerar-entregas-esperadas",
        headers=headers_prof1,
    )
    assert resp_gen2.status_code == 200
    assert resp_gen2.json()["entregas_criadas"] == 0
    assert resp_gen2.json()["entregas_ja_existentes"] == 3

    # Verifica que todas as 3 entregas esperadas têm status PENDENTE e nota=None (nunca 0)
    resp_lista = client.get(
        f"/api/v1/atividades/{atividade_id}/entregas",
        headers=headers_prof1,
    )
    assert resp_lista.status_code == 200
    entregas = resp_lista.json()
    assert len(entregas) == 3
    for ent in entregas:
        assert ent["status_entrega"] == "PENDENTE"
        assert ent["nota"] is None
        assert ent["data_entrega"] is None

    # Registra entrega no prazo para EST-001 (sem informar nota -> nota deve continuar None)
    resp_ent1 = client.post(
        f"/api/v1/atividades/{atividade_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": date.today().isoformat(),
        },
    )
    assert resp_ent1.status_code == 201, resp_ent1.text
    assert resp_ent1.json()["status_entrega"] == "ENTREGUE"
    assert resp_ent1.json()["nota"] is None

    # Registra entrega com atraso para EST-002 (data_entrega > data_limite) e nota 7.5
    data_atrasada = (date.today() + timedelta(days=7)).isoformat()
    resp_ent2 = client.post(
        f"/api/v1/atividades/{atividade_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-002",
            "data_entrega": data_atrasada,
            "nota": 7.5,
        },
    )
    assert resp_ent2.status_code == 201, resp_ent2.text
    assert resp_ent2.json()["status_entrega"] == "ATRASADO"
    assert resp_ent2.json()["nota"] == 7.5

    # Simula passagem do prazo (data_referencia após data_limite): EST-003 passa de PENDENTE para NAO_ENTREGUE
    data_pos_prazo = (date.today() + timedelta(days=10)).isoformat()
    resp_gen3 = client.post(
        f"/api/v1/atividades/{atividade_id}/gerar-entregas-esperadas?data_referencia={data_pos_prazo}",
        headers=headers_prof1,
    )
    assert resp_gen3.status_code == 200
    assert resp_gen3.json()["entregas_atualizadas_para_nao_entregue"] == 1

    # Isolamento: Professor 2 não pode acessar atividade da Turma 1A
    resp_prof2 = client.get(
        f"/api/v1/atividades/{atividade_id}/entregas",
        headers=headers_prof2,
    )
    assert resp_prof2.status_code == 403


# ==============================================================================
# 3. TESTES DO MÓDULO DE ACOMPANHAMENTO PEDAGÓGICO
# ==============================================================================
def test_acompanhamento_pedagogico_individual_coletivo_e_historico(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Testa:
    - Criação de registro individual (`estudante_id`) e coletivo (`turma_id`).
    - Rejeição quando nem `estudante_id` nem `turma_id` são informados (422).
    - Autor identificado exclusivamente pela sessão JWT (ignorando `usuario_id` falsificado).
    - Bloqueio entre escolas e fora do vínculo do professor.
    - Preservação do histórico de alterações em `PATCH /api/v1/acompanhamentos/{id}` sem apagar descrição anterior.
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_prof2 = _login_headers(client, "prof2@vertice.edu.br", "SenhaForte@123")
    headers_gestor_b = _login_headers(client, "gestor.b@vertice.edu.br", "SenhaForte@123")

    # Sem estudante_id nem turma_id -> 422
    resp_vazio = client.post(
        "/api/v1/acompanhamentos",
        headers=headers_prof1,
        json={
            "origem": "ESTUDANTES",
            "tipo_acao": "Reunião",
            "descricao": "Tentativa inválida sem alvo.",
        },
    )
    assert resp_vazio.status_code == 422

    # Registro individual válido para EST-002 na Turma 1A (tentando injetar usuario_id de outro usuário)
    resp_ind = client.post(
        "/api/v1/acompanhamentos",
        headers=headers_prof1,
        json={
            "estudante_id": str(cenario["est2"].id),
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "origem": "MAPA_ACERTOS",
            "tipo_acao": "Atendimento Individual",
            "descricao": "Orientação inicial sobre dificuldade em funções afins.",
            "usuario_id": str(cenario["prof2"].id),  # Deve ser ignorado
        },
    )
    assert resp_ind.status_code == 201, resp_ind.text
    acomp_data = resp_ind.json()
    acomp_id = acomp_data["id"]
    assert acomp_data["usuario_id"] == str(cenario["prof1"].id)
    assert acomp_data["codigo_anonimo"] == "EST-002"
    assert acomp_data["historico_alteracoes"] == []

    # Registro coletivo para a Turma 1A (sem estudante_id)
    resp_col = client.post(
        "/api/v1/acompanhamentos",
        headers=headers_prof1,
        json={
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "origem": "PARTICIPACAO",
            "tipo_acao": "Intervenção Coletiva na Turma",
            "descricao": "Revisão coletiva sobre prazos de entrega de listas.",
        },
    )
    assert resp_col.status_code == 201, resp_col.text
    assert resp_col.json()["estudante_id"] is None
    assert resp_col.json()["turma_id"] == str(cenario["turma_1a"].id)

    # Atualização do acompanhamento preserva histórico anterior em `historico_alteracoes`
    resp_patch = client.patch(
        f"/api/v1/acompanhamentos/{acomp_id}",
        headers=headers_prof1,
        json={
            "tipo_acao": "Atendimento Individual + Monitoria",
            "descricao": "Estudante encaminhado para monitoria no contraturno.",
        },
    )
    assert resp_patch.status_code == 200, resp_patch.text
    patch_data = resp_patch.json()
    assert patch_data["descricao"] == "Estudante encaminhado para monitoria no contraturno."
    assert len(patch_data["historico_alteracoes"]) == 1
    hist_item = patch_data["historico_alteracoes"][0]
    assert hist_item["descricao_anterior"] == "Orientação inicial sobre dificuldade em funções afins."
    assert hist_item["tipo_acao_anterior"] == "Atendimento Individual"
    assert hist_item["alterado_por_usuario_id"] == str(cenario["prof1"].id)

    # Professor 2 não pode registrar acompanhamento para estudante da Turma 1A (403)
    resp_prof2_proibido = client.post(
        "/api/v1/acompanhamentos",
        headers=headers_prof2,
        json={
            "estudante_id": str(cenario["est1"].id),
            "turma_id": str(cenario["turma_1a"].id),
            "origem": "ESTUDANTES",
            "tipo_acao": "Ação indevida",
            "descricao": "Tentativa fora do vínculo.",
        },
    )
    assert resp_prof2_proibido.status_code == 403

    # Gestor da Escola B não pode visualizar acompanhamento da Escola A (403)
    resp_gestor_b = client.get(
        f"/api/v1/acompanhamentos/{acomp_id}",
        headers=headers_gestor_b,
    )
    assert resp_gestor_b.status_code == 403


# ==============================================================================
# 4. TESTES DO MÓDULO DE INDICADORES (GERAIS, AVALIAÇÕES E PARTICIPAÇÃO)
# ==============================================================================
def test_indicadores_gerais_avaliacoes_e_participacao(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Testa os cálculos exatos, denominadores, ausência de duplicação de estudantes
    e isolamento de escopo nos endpoints:
    - GET /api/v1/indicadores/gerais
    - GET /api/v1/indicadores/avaliacoes
    - GET /api/v1/indicadores/participacao
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")

    # 1. Indicadores Gerais da Turma 1A:
    # Estudantes em 1A: EST-001 (Aprovado, 8.5, 92%), EST-002 (Reprovado, 4.5, 70%), EST-003 (Evadido, 5.0, 60%)
    # Total estudantes distintos = 3
    # Média geral = (8.5 + 4.5 + 5.0)/3 = 6.0
    # Frequência média = (92 + 70 + 60)/3 = 74.0
    resp_gerais = client.get(
        f"/api/v1/indicadores/gerais?turma_id={cenario['turma_1a'].id}",
        headers=headers_prof1,
    )
    assert resp_gerais.status_code == 200, resp_gerais.text
    g = resp_gerais.json()
    assert g["total_estudantes_distintos"] == 3
    assert g["total_registros_boletim"] == 3
    assert g["media_geral"] == 6.0
    assert g["frequencia_media"] == 74.0
    assert len(g["distribuicao_por_turma"]) == 1
    assert g["distribuicao_por_turma"][0]["total_estudantes"] == 3
    # Indicadores de ML preditivo ainda não implementados na Fase 4 -> possui_previsoes_risco False
    assert g["possui_previsoes_risco"] is False
    assert g["distribuicao_faixas_risco"] == []

    # 2. Indicadores de Avaliações (cria avaliação com 2 questões e respostas para os 3 estudantes)
    av_resp = client.post(
        "/api/v1/avaliacoes",
        headers=headers_prof1,
        json={
            "codigo": "AV-IND-01",
            "titulo": "Prova Indicadores",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_avaliacao": "2026-04-12",
        },
    )
    av_id = av_resp.json()["id"]
    q1 = client.post(
        f"/api/v1/avaliacoes/{av_id}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q01",
            "tipo_questao": "FECHADA",
            "alternativa_correta": "A",
            "valor_questao": 5.0,
            "faixa_dificuldade": "Fácil",
        },
    ).json()
    q2 = client.post(
        f"/api/v1/avaliacoes/{av_id}/questoes",
        headers=headers_prof1,
        json={
            "codigo_questao": "Q02",
            "tipo_questao": "FECHADA",
            "alternativa_correta": "C",
            "valor_questao": 5.0,
            "faixa_dificuldade": "Difícil",
        },
    ).json()

    # EST-001 acerta Q01 (5.0) e acerta Q02 (5.0) -> soma 10.0
    # EST-002 acerta Q01 (5.0) e erra Q02 (0.0) -> soma 5.0
    # EST-003 acerta Q01 (5.0) e deixa Q02 em branco (0.0) -> soma 5.0
    client.post(
        f"/api/v1/questoes/{q1['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-001", "alternativa_marcada": "A"},
    )
    client.post(
        f"/api/v1/questoes/{q2['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-001", "alternativa_marcada": "C"},
    )
    client.post(
        f"/api/v1/questoes/{q1['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-002", "alternativa_marcada": "A"},
    )
    client.post(
        f"/api/v1/questoes/{q2['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-002", "alternativa_marcada": "B"},
    )
    client.post(
        f"/api/v1/questoes/{q1['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-003", "alternativa_marcada": "A"},
    )
    client.post(
        f"/api/v1/questoes/{q2['id']}/respostas",
        headers=headers_prof1,
        json={"codigo_anonimo": "EST-003", "alternativa_marcada": "BRANCO"},
    )

    resp_ind_av = client.get(
        f"/api/v1/indicadores/avaliacoes?avaliacao_id={av_id}",
        headers=headers_prof1,
    )
    assert resp_ind_av.status_code == 200, resp_ind_av.text
    ind_av = resp_ind_av.json()
    assert ind_av["total_avaliacoes"] == 1
    assert ind_av["total_questoes"] == 2
    assert ind_av["soma_pesos_avaliacao"] == 10.0
    assert ind_av["media_pontos_obtidos"] == 6.67
    assert ind_av["media_avaliacao_ponderada"] == 6.67
    assert ind_av["questao_maior_taxa_acerto"]["codigo_questao"] == "Q01"
    assert ind_av["questao_maior_taxa_acerto"]["taxa_acerto_percentual"] == 100.0
    assert ind_av["questao_maior_taxa_acerto"]["faixa_desempenho_observada"] == "Fácil"
    assert ind_av["questao_menor_taxa_acerto"]["codigo_questao"] == "Q02"
    assert ind_av["questao_menor_taxa_acerto"]["taxa_acerto_percentual"] == 33.33
    assert ind_av["questao_menor_taxa_acerto"]["faixa_desempenho_observada"] == "Atenção"
    assert ind_av["questao_menor_taxa_acerto"]["quantidade_em_branco"] == 1

    # 3. Indicadores de Participação
    ativ_resp = client.post(
        "/api/v1/atividades",
        headers=headers_prof1,
        json={
            "codigo": "ATIV-IND-01",
            "titulo": "Trabalho Bimestral",
            "turma_id": str(cenario["turma_1a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
            "periodo_letivo": "1º Bimestre",
            "data_limite": "2026-04-10",
            "nota_maxima": 10.0,
            "gerar_entregas_esperadas": True,
        },
    )
    ativ_id = ativ_resp.json()["id"]
    # Registra: EST-001 ENTREGUE no prazo (nota 9.0), EST-002 ATRASADO (nota 7.0), EST-003 fica NAO_ENTREGUE (nota None)
    client.post(
        f"/api/v1/atividades/{ativ_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-001",
            "data_entrega": "2026-04-09",
            "nota": 9.0,
        },
    )
    client.post(
        f"/api/v1/atividades/{ativ_id}/entregas",
        headers=headers_prof1,
        json={
            "codigo_anonimo": "EST-002",
            "data_entrega": "2026-04-12",
            "nota": 7.0,
        },
    )

    resp_ind_part = client.get(
        f"/api/v1/indicadores/participacao?atividade_id={ativ_id}&data_referencia=2026-04-15",
        headers=headers_gestor_a,
    )
    assert resp_ind_part.status_code == 200, resp_ind_part.text
    ind_part = resp_ind_part.json()
    assert ind_part["total_atividades"] == 1
    assert ind_part["total_entregas_esperadas"] == 3
    assert ind_part["entregas_realizadas"] == 2
    assert ind_part["entregas_no_prazo"] == 1
    assert ind_part["entregas_atrasadas"] == 1
    assert ind_part["nao_entregas_apos_prazo"] == 1
    assert ind_part["atividades_pendentes_antes_prazo"] == 0
    assert ind_part["taxa_entrega_geral_percentual"] == 66.67  # (1 entregue + 1 atrasada) / 3
    # Média das notas das entregas avaliadas: (9.0 + 7.0) / 2 = 8.0 (EST-003 com nota None não vira zero)
    assert ind_part["media_notas_disponiveis"] == 8.0
    assert len(ind_part["percentual_por_estudante"]) == 3


# ==============================================================================
# 5. TESTES DE IMPORTAÇÃO EM DUAS ETAPAS DE AVALIAÇÕES E ATIVIDADES
# ==============================================================================
def test_importacao_avaliacoes_e_atividades_duas_etapas(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Testa o fluxo de importação em 2 etapas (`/validar` e `/{lote_id}/confirmar`)
    para datasets de `AVALIACOES` e `ATIVIDADES`:
    - Detecção automática do tipo de dataset.
    - Bloqueio se o CSV referenciar estudante que não existe no cadastro da escola.
    - Confirmação atômica criando avaliação, questões e respostas (Bloco B).
    - Confirmação atômica criando atividade, gerando entregas esperadas para toda a turma
      e atualizando as entregas enviadas mantendo notas vazias como `None` (Bloco C).
    """
    cenario = _criar_cenario_fase4(db_session)
    headers_prof1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # 1. Tentativa de importar avaliação com estudante inexistente (EST-999) -> status COM_ERROS
    csv_av_erro = (
        "id_avaliacao,titulo_avaliacao,disciplina,ano_letivo,serie,turma,turno,periodo,data_avaliacao,"
        "id_questao,tipo_questao,faixa_dificuldade,valor_questao,alternativa_correta,id_estudante,alternativa_marcada,nota_obtida\n"
        "AV-CSV-01,Prova CSV,MAT,2026,1ª Série,Turma 1A,Matutino,1º Bimestre,2026-04-15,"
        "Q01,FECHADA,Adequada,2.0,A,EST-999,A,2.0\n"
    ).encode("utf-8")

    resp_val_erro = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("avaliacao_invalida.csv", csv_av_erro, "text/csv")},
    )
    assert resp_val_erro.status_code == 201, resp_val_erro.text
    val_erro_data = resp_val_erro.json()
    assert val_erro_data["tipo_importacao"] == "AVALIACOES"
    assert val_erro_data["status"] == "com_erros"
    assert val_erro_data["pode_confirmar"] is False
    assert val_erro_data["quantidade_erros"] == 1

    # 2. Importação válida de AVALIACOES (2 questões, estudantes existentes EST-001 e EST-002)
    csv_av_valido = (
        "id_avaliacao,titulo_avaliacao,disciplina,ano_letivo,serie,turma,turno,periodo,data_avaliacao,"
        "id_questao,tipo_questao,faixa_dificuldade,valor_questao,alternativa_correta,id_estudante,alternativa_marcada,nota_obtida\n"
        "AV-CSV-01,Prova CSV 1,MAT,2026,1ª Série,Turma 1A,Matutino,1º Bimestre,2026-04-15,"
        "Q01,FECHADA,Fácil,2.0,A,EST-001,A,2.0\n"
        "AV-CSV-01,Prova CSV 1,MAT,2026,1ª Série,Turma 1A,Matutino,1º Bimestre,2026-04-15,"
        "Q01,FECHADA,Fácil,2.0,A,EST-002,BRANCO,0.0\n"
        "AV-CSV-01,Prova CSV 1,MAT,2026,1ª Série,Turma 1A,Matutino,1º Bimestre,2026-04-15,"
        "Q02,ABERTA,Difícil,3.0,,EST-001,,2.5\n"
    ).encode("utf-8")

    resp_val_av = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("avaliacao_valida.csv", csv_av_valido, "text/csv")},
    )
    assert resp_val_av.status_code == 201, resp_val_av.text
    lote_av = resp_val_av.json()
    assert lote_av["tipo_importacao"] == "AVALIACOES"
    assert lote_av["status"] == "validado"
    assert lote_av["pode_confirmar"] is True
    assert lote_av["registros_validos"] == 3

    resp_conf_av = client.post(
        f"/api/v1/importacoes/{lote_av['id']}/confirmar",
        headers=headers_prof1,
    )
    assert resp_conf_av.status_code == 200, resp_conf_av.text
    assert resp_conf_av.json()["registros_inseridos"] == 3

    # 3. Importação válida de ATIVIDADES (enviando entregas de EST-001 e EST-002; EST-003 deve receber entrega esperada automática)
    csv_ativ_valido = (
        "id_atividade,titulo_atividade,disciplina,turma,periodo,data_limite,nota_maxima,id_estudante,data_entrega,nota,status_entrega\n"
        "ATIV-CSV-01,Trabalho CSV,MAT,Turma 1A,1º Bimestre,2026-04-20,10.0,EST-001,2026-04-18,9.5,ENTREGUE\n"
        "ATIV-CSV-01,Trabalho CSV,MAT,Turma 1A,1º Bimestre,2026-04-20,10.0,EST-002,2026-04-22,,ATRASADO\n"
    ).encode("utf-8")

    resp_val_ativ = client.post(
        "/api/v1/importacoes/validar",
        headers=headers_prof1,
        files={"arquivo": ("atividades_validas.csv", csv_ativ_valido, "text/csv")},
    )
    assert resp_val_ativ.status_code == 201, resp_val_ativ.text
    lote_ativ = resp_val_ativ.json()
    assert lote_ativ["tipo_importacao"] == "ATIVIDADES"
    assert lote_ativ["status"] == "validado"
    assert lote_ativ["pode_confirmar"] is True

    resp_conf_ativ = client.post(
        f"/api/v1/importacoes/{lote_ativ['id']}/confirmar",
        headers=headers_prof1,
    )
    assert resp_conf_ativ.status_code == 200, resp_conf_ativ.text
    assert resp_conf_ativ.json()["registros_inseridos"] == 2

    # Verifica que a atividade criada possui 3 registros de entrega no total (incluindo EST-003 esperado)
    # e que a nota ausente de EST-002 permaneceu None
    ativ_criada = db_session.execute(
        select(Atividade).where(Atividade.codigo == "ATIV-CSV-01")
    ).scalar_one()
    entregas_db = list(
        db_session.execute(
            select(EntregaAtividade).where(
                EntregaAtividade.atividade_id == ativ_criada.id
            )
        ).scalars().all()
    )
    assert len(entregas_db) == 3
    mapa_por_est = {e.estudante_id: e for e in entregas_db}
    assert mapa_por_est[cenario["est1"].id].nota == 9.5
    assert mapa_por_est[cenario["est2"].id].nota is None
    assert (
        mapa_por_est[cenario["est2"].id].status_entrega
        == StatusEntregaAtividade.ATRASADO
    )
    assert mapa_por_est[cenario["est3"].id].nota is None


# ==============================================================================
# 6. TESTE DE INTEGRAÇÃO REAL COM POSTGRESQL (DDL / CONSTRAINTS DA FASE 4)
# ==============================================================================
def test_integracao_postgresql_tabelas_e_constraints_fase4() -> None:
    """
    Verifica diretamente no PostgreSQL local se a migração Alembic da Fase 4
    criou todas as tabelas, chaves estrangeiras e constraints de unicidade.
    """
    from pathlib import Path
    import pytest
    from sqlalchemy import create_engine

    from app.core.config import ENV_FILE_PATH, Settings

    if not Path(ENV_FILE_PATH).exists():
        pytest.skip("Arquivo .env não encontrado para teste de integração PostgreSQL.")

    pg_settings = Settings(_env_file=str(ENV_FILE_PATH), DATABASE_URL=None)  # type: ignore[call-arg]
    live_pg_engine = create_engine(pg_settings.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)
    try:
        insp = inspect(live_pg_engine)
        tabelas = set(insp.get_table_names())
        tabelas_esperadas_fase4 = {
            "avaliacoes",
            "questoes_avaliacao",
            "respostas_avaliacao",
            "atividades",
            "entregas_atividade",
            "acompanhamentos_pedagogicos",
        }
        assert tabelas_esperadas_fase4.issubset(tabelas)

        uqs_respostas = {
            uq["name"] for uq in insp.get_unique_constraints("respostas_avaliacao")
        }
        assert "uq_resposta_avaliacao_questao_estudante" in uqs_respostas

        uqs_entregas = {
            uq["name"] for uq in insp.get_unique_constraints("entregas_atividade")
        }
        assert "uq_entrega_atividade_estudante" in uqs_entregas
    finally:
        live_pg_engine.dispose()
