"""
Testes de alinhamento definitivo de perfis, navegação e autorizações (Backend + Frontend).

Cobre integralmente os cenários obrigatórios de separação de responsabilidades:
1. Administrador acessando endpoints técnicos e sendo bloqueado (403) de atribuições e rotas pedagógicas.
2. Gestor/Coordenador restrito à própria escola (`escola_id`), incluindo rejeição (403) quando sem escola.
3. Professor restrito às próprias turmas e disciplinas vinculadas (`ProfessorTurma`).
4. Tentativas de escalação de privilégio ou adulteração de papel/ID pelo cliente (`coordenador`, auto-desativação, spoofing).
5. Auditoria persistente de operações técnicas sensíveis sem vazamento de senhas ou segredos ML.
6. Consistência dos menus, páginas e rótulos no Streamlit (`Administração Técnica`, `Gestor/Coordenador`, sem papel `coordenador`).
"""

from __future__ import annotations

from datetime import date
import importlib
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.modules.admin.models import AuditoriaOperacaoTecnica
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.avaliacoes.models import Avaliacao, QuestaoAvaliacao, StatusAvaliacao, TipoQuestao
from app.modules.participacao.models import Atividade, EntregaAtividade, StatusAtividade
from app.modules.usuarios.models import PapelUsuario, Usuario
from tests.test_fase4_modulos_pedagogicos import _criar_cenario_fase4
from tests.test_fase8_integracao_final import _carregar_frontend_app, _preparar_frontend


def _login_headers(client: TestClient, email: str, senha: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": senha},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _criar_recursos_pedagogicos_escola_a(db_session: Session, cenario: dict) -> dict:
    """Cria avaliação, questão, atividade e entrega na Escola A para testar bloqueios reais por ID."""
    avaliacao = Avaliacao(
        codigo="AV-SEC-01",
        titulo="Avaliação Segurança RBAC",
        escola_id=cenario["escola_a"].id,
        turma_id=cenario["turma_1a"].id,
        disciplina_id=cenario["disc_mat"].id,
        usuario_id=cenario["gestor_a"].id,
        periodo_letivo="1º Bimestre",
        data_avaliacao=date(2026, 4, 15),
        status=StatusAvaliacao.PUBLICADA,
    )
    db_session.add(avaliacao)
    db_session.flush()

    questao = QuestaoAvaliacao(
        avaliacao_id=avaliacao.id,
        codigo_questao="Q01",
        tipo_questao=TipoQuestao.FECHADA,
        alternativa_correta="A",
        valor_questao=1.0,
        topico="Álgebra",
    )
    db_session.add(questao)

    atividade = Atividade(
        codigo="ATV-SEC-01",
        titulo="Atividade Segurança RBAC",
        escola_id=cenario["escola_a"].id,
        turma_id=cenario["turma_1a"].id,
        disciplina_id=cenario["disc_mat"].id,
        usuario_id=cenario["gestor_a"].id,
        periodo_letivo="1º Bimestre",
        data_limite=date(2026, 5, 1),
        nota_maxima=10.0,
        status=StatusAtividade.ABERTA,
    )
    db_session.add(atividade)
    db_session.flush()

    entrega = EntregaAtividade(
        atividade_id=atividade.id,
        estudante_id=cenario["est1"].id,
    )
    db_session.add(entrega)
    db_session.commit()

    return {
        "avaliacao": avaliacao,
        "questao": questao,
        "atividade": atividade,
        "entrega": entrega,
    }


def test_administrador_acesso_tecnico_permitido_e_bloqueio_total_pedagogico_e_atribuicoes(
    client: TestClient,
    db_session: Session,
) -> None:
    """Cenários 1 e 2: Admin acessa apenas rotas técnicas e recebe 403 em TODAS as rotas pedagógicas/atribuições."""
    cenario = _criar_cenario_fase4(db_session)
    recursos = _criar_recursos_pedagogicos_escola_a(db_session, cenario)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_gestor_a = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")

    atrib_a = (
        db_session.query(ProfessorTurma)
        .filter(ProfessorTurma.professor_id == cenario["prof1"].id)
        .first()
    )
    assert atrib_a is not None

    # 1. Rotas técnicas permitidas ao Administrador
    for metodo, rota in [
        ("GET", "/api/v1/admin/resumo-operacional"),
        ("GET", "/api/v1/admin/auditoria-tecnica"),
        ("GET", "/api/v1/usuarios"),
        ("GET", "/api/v1/escolas"),
        ("GET", "/api/v1/turmas"),
        ("GET", "/api/v1/disciplinas"),
        ("GET", "/api/v1/previsoes/credenciais"),
        ("GET", "/api/v1/assistente/auditoria"),
    ]:
        resp = client.request(metodo, rota, headers=headers_admin)
        assert resp.status_code == 200, f"{metodo} {rota}: {resp.text}"

    resumo = client.get("/api/v1/admin/resumo-operacional", headers=headers_admin).json()
    assert resumo["total_escolas"] >= 2
    assert set(resumo["usuarios_por_papel"].keys()) == {"administrador", "gestor", "professor"}
    assert "estudantes" not in resumo

    # 2. Administrador recebe HTTP 403 em TODAS as rotas de atribuições e dados pedagógicos
    lote_exemplo = uuid.uuid4()
    rotas_proibidas_admin = [
        ("GET", "/api/v1/atribuicoes", None),
        (
            "POST",
            "/api/v1/atribuicoes",
            {
                "professor_id": str(cenario["prof1"].id),
                "turma_id": str(cenario["turma_3a"].id),
                "disciplina_id": str(cenario["disc_mat"].id),
            },
        ),
        ("DELETE", f"/api/v1/atribuicoes/{atrib_a.id}", None),
        ("GET", "/api/v1/estudantes", None),
        ("GET", f"/api/v1/estudantes/{cenario['est1'].id}", None),
        ("GET", "/api/v1/importacoes", None),
        ("GET", "/api/v1/importacoes/modelos/dados-escolares", None),
        ("GET", "/api/v1/importacoes/modelos/avaliacoes", None),
        ("GET", "/api/v1/importacoes/modelos/atividades", None),
        ("GET", f"/api/v1/importacoes/{lote_exemplo}", None),
        ("GET", f"/api/v1/importacoes/{lote_exemplo}/previa", None),
        ("POST", f"/api/v1/importacoes/{lote_exemplo}/confirmar", None),
        ("POST", f"/api/v1/importacoes/{lote_exemplo}/descartar", None),
        ("GET", "/api/v1/avaliacoes", None),
        ("GET", f"/api/v1/avaliacoes/{recursos['avaliacao'].id}", None),
        ("GET", f"/api/v1/avaliacoes/{recursos['avaliacao'].id}/questoes", None),
        ("GET", f"/api/v1/avaliacoes/{recursos['avaliacao'].id}/respostas", None),
        (
            "POST",
            "/api/v1/avaliacoes",
            {
                "titulo": "Tentativa Admin",
                "turma_id": str(cenario["turma_1a"].id),
                "disciplina_id": str(cenario["disc_mat"].id),
                "periodo_letivo": "2º Bimestre",
                "data_avaliacao": "2026-06-01",
            },
        ),
        (
            "PATCH",
            f"/api/v1/questoes/{recursos['questao'].id}",
            {"topico": "Alteração indevida"},
        ),
        (
            "POST",
            f"/api/v1/questoes/{recursos['questao'].id}/respostas",
            {"estudante_id": str(cenario["est1"].id), "alternativa_marcada": "A"},
        ),
        ("GET", "/api/v1/atividades", None),
        ("GET", f"/api/v1/atividades/{recursos['atividade'].id}", None),
        ("GET", f"/api/v1/atividades/{recursos['atividade'].id}/entregas", None),
        (
            "POST",
            "/api/v1/atividades",
            {
                "titulo": "Atividade Admin Proibida",
                "turma_id": str(cenario["turma_1a"].id),
                "disciplina_id": str(cenario["disc_mat"].id),
                "periodo_letivo": "2º Bimestre",
                "data_limite": "2026-06-15",
            },
        ),
        (
            "PATCH",
            f"/api/v1/entregas/{recursos['entrega'].id}",
            {"nota": 9.0},
        ),
        ("GET", "/api/v1/acompanhamentos", None),
        (
            "POST",
            "/api/v1/acompanhamentos",
            {
                "estudante_id": str(cenario["est1"].id),
                "origem": "ESTUDANTES",
                "tipo_acao": "INTERVENCAO",
                "descricao": "Tentativa indevida de administrador",
            },
        ),
        ("GET", "/api/v1/indicadores/gerais", None),
        ("GET", "/api/v1/indicadores/avaliacoes", None),
        ("GET", "/api/v1/indicadores/participacao", None),
        ("GET", "/api/v1/previsoes", None),
        ("GET", "/api/v1/previsoes/resumo", None),
        ("GET", f"/api/v1/previsoes/estudantes/{cenario['est1'].id}", None),
        (
            "POST",
            "/api/v1/assistente/contexto",
            {"tipo_contexto": "ESCOLA", "escola_id": str(cenario["escola_a"].id)},
        ),
        (
            "POST",
            "/api/v1/assistente/consultar",
            {
                "tipo_contexto": "ESCOLA",
                "escola_id": str(cenario["escola_a"].id),
                "pergunta_usuario": "Quais estudantes têm risco?",
            },
        ),
    ]

    for metodo, rota, body in rotas_proibidas_admin:
        resp = client.request(metodo, rota, json=body, headers=headers_admin)
        assert resp.status_code == 403, f"Admin deveria receber 403 em {metodo} {rota}, recebeu {resp.status_code}: {resp.text}"

    # Verifica que gestor da escola continua conseguindo criar e remover atribuições normalmente
    r_atrib = client.post(
        "/api/v1/atribuicoes",
        json={
            "professor_id": str(cenario["prof1"].id),
            "turma_id": str(cenario["turma_3a"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
        },
        headers=headers_gestor_a,
    )
    assert r_atrib.status_code == 201
    assert client.delete(f"/api/v1/atribuicoes/{r_atrib.json()['id']}", headers=headers_gestor_a).status_code == 204


def test_gestor_escopo_estrito_e_bloqueio_sem_escola_vinculada(
    client: TestClient,
    db_session: Session,
) -> None:
    """Cenários 3, 4, 5 e 6: Gestor atua apenas na própria escola, nunca em outra escola, nunca sem escola_id e nunca em rotas Admin."""
    cenario = _criar_cenario_fase4(db_session)

    # Cria gestor sem escola_id vinculada (erro operacional que não pode liberar bypass!)
    gestor_sem_escola = Usuario(
        nome="Gestor Sem Escola",
        email="gestor.sem.escola@vertice.edu.br",
        senha_hash=get_password_hash("SenhaForte@123"),
        papel=PapelUsuario.GESTOR,
        escola_id=None,
        ativo=True,
    )
    db_session.add(gestor_sem_escola)
    db_session.commit()

    headers_ga = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")
    headers_g_sem = _login_headers(client, "gestor.sem.escola@vertice.edu.br", "SenhaForte@123")

    # Gestor A acessa sua escola e suas atribuições, bloqueado na Escola B
    assert client.get("/api/v1/escolas", headers=headers_ga).status_code == 200
    assert len(client.get("/api/v1/escolas", headers=headers_ga).json()) == 1
    assert client.get(f"/api/v1/escolas/{cenario['escola_b'].id}", headers=headers_ga).status_code == 403
    assert client.patch(
        f"/api/v1/escolas/{cenario['escola_b'].id}",
        json={"nome": "Invasão"},
        headers=headers_ga,
    ).status_code == 403
    # Gestor já vinculado a escola_a não pode criar uma segunda escola
    assert client.post(
        "/api/v1/escolas",
        json={"nome": "Outra Unidade", "codigo": "OU-99"},
        headers=headers_ga,
    ).status_code == 403
    # Gestor A não cria turma nem atribuição na Escola B
    assert client.post(
        "/api/v1/turmas",
        json={
            "nome": "Turma Invasora",
            "serie": "1ª Série",
            "turno": "Matutino",
            "ano_letivo": 2026,
            "escola_id": str(cenario["escola_b"].id),
        },
        headers=headers_ga,
    ).status_code == 403
    assert client.post(
        "/api/v1/atribuicoes",
        json={
            "professor_id": str(cenario["prof1"].id),
            "turma_id": str(cenario["turma_escola_b"].id),
            "disciplina_id": str(cenario["disc_mat"].id),
        },
        headers=headers_ga,
    ).status_code == 403

    # Gestor A não acessa rotas exclusivas de Administrador
    for metodo, rota, body in [
        ("GET", "/api/v1/admin/resumo-operacional", None),
        ("GET", "/api/v1/admin/auditoria-tecnica", None),
        (
            "POST",
            "/api/v1/usuarios",
            {
                "nome": "Conta Indevida",
                "email": "indevida@vertice.edu.br",
                "senha": "SenhaForte@123",
                "papel": "professor",
            },
        ),
        ("PATCH", f"/api/v1/usuarios/{cenario['prof1'].id}", {"ativo": False}),
        ("GET", "/api/v1/previsoes/credenciais", None),
        ("POST", "/api/v1/previsoes/credenciais", {"nome": "ML Fake"}),
    ]:
        assert client.request(metodo, rota, json=body, headers=headers_ga).status_code == 403

    # Gestor SEM escola vinculada (escola_id=None) NÃO contorna restrições -> 403
    atrib_a = db_session.query(ProfessorTurma).first()
    assert atrib_a is not None
    rotas_bloqueadas_gestor_sem_escola = [
        ("GET", "/api/v1/escolas", None),
        ("GET", f"/api/v1/escolas/{cenario['escola_a'].id}", None),
        ("PATCH", f"/api/v1/escolas/{cenario['escola_a'].id}", {"nome": "Alterar"}),
        ("GET", "/api/v1/turmas", None),
        ("GET", f"/api/v1/turmas/{cenario['turma_1a'].id}", None),
        (
            "POST",
            "/api/v1/turmas",
            {
                "nome": "Sem Escopo",
                "serie": "1ª Série",
                "turno": "Matutino",
                "ano_letivo": 2026,
                "escola_id": str(cenario["escola_a"].id),
            },
        ),
        ("PATCH", f"/api/v1/turmas/{cenario['turma_1a'].id}", {"nome": "Hack"}),
        ("POST", "/api/v1/disciplinas", {"nome": "Artes", "codigo": "ART"}),
        ("PATCH", f"/api/v1/disciplinas/{cenario['disc_mat'].id}", {"nome": "Hack"}),
        ("GET", "/api/v1/atribuicoes", None),
        (
            "POST",
            "/api/v1/atribuicoes",
            {
                "professor_id": str(cenario["prof1"].id),
                "turma_id": str(cenario["turma_1a"].id),
                "disciplina_id": str(cenario["disc_mat"].id),
            },
        ),
        ("DELETE", f"/api/v1/atribuicoes/{atrib_a.id}", None),
        ("GET", "/api/v1/usuarios", None),
        ("GET", "/api/v1/estudantes", None),
        ("GET", "/api/v1/indicadores/gerais", None),
        ("GET", "/api/v1/avaliacoes", None),
        ("GET", "/api/v1/atividades", None),
        ("GET", "/api/v1/importacoes", None),
    ]
    for metodo, rota, body in rotas_bloqueadas_gestor_sem_escola:
        resp = client.request(metodo, rota, json=body, headers=headers_g_sem)
        assert resp.status_code == 403, f"Gestor sem escola deveria receber 403 em {metodo} {rota}, recebeu {resp.status_code}"


def test_professor_escopo_turma_disciplina_e_bloqueios(
    client: TestClient,
    db_session: Session,
) -> None:
    """Cenários 7 e 8: Professor acessa apenas vínculos próprios e recebe 403 em recursos alheios, usuários e gestão de atribuições."""
    cenario = _criar_cenario_fase4(db_session)
    headers_p1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # Professor lê apenas as próprias atribuições
    resp_atribs = client.get("/api/v1/atribuicoes", headers=headers_p1)
    assert resp_atribs.status_code == 200
    atribs = resp_atribs.json()
    assert len(atribs) == 2
    assert all(item["professor_id"] == str(cenario["prof1"].id) for item in atribs)

    # Acessa turma atribuída e é bloqueado (403) em turma não atribuída
    assert client.get(f"/api/v1/turmas/{cenario['turma_1a'].id}", headers=headers_p1).status_code == 200
    assert client.get(f"/api/v1/turmas/{cenario['turma_3a'].id}", headers=headers_p1).status_code == 403
    assert client.get(f"/api/v1/turmas/{cenario['turma_escola_b'].id}", headers=headers_p1).status_code == 403

    # Bloqueado de criar/excluir atribuições, listar usuários e operar cadastros administrativos/técnicos
    atrib_id = atribs[0]["id"]
    for metodo, rota, body in [
        (
            "POST",
            "/api/v1/atribuicoes",
            {
                "professor_id": str(cenario["prof1"].id),
                "turma_id": str(cenario["turma_3a"].id),
                "disciplina_id": str(cenario["disc_qui"].id),
            },
        ),
        ("DELETE", f"/api/v1/atribuicoes/{atrib_id}", None),
        ("GET", "/api/v1/usuarios", None),
        ("GET", f"/api/v1/usuarios/{cenario['prof2'].id}", None),
        ("POST", "/api/v1/usuarios", {"nome": "X", "email": "x@x.com", "senha": "SenhaForte@123", "papel": "administrador"}),
        ("POST", "/api/v1/escolas", {"nome": "E", "codigo": "E-01"}),
        ("POST", "/api/v1/disciplinas", {"nome": "D", "codigo": "D-01"}),
        ("GET", "/api/v1/admin/resumo-operacional", None),
        ("GET", "/api/v1/admin/auditoria-tecnica", None),
        ("GET", "/api/v1/previsoes/credenciais", None),
    ]:
        assert client.request(metodo, rota, json=body, headers=headers_p1).status_code == 403


def test_prevencao_escalacao_privilegio_adulteracao_cliente_e_sem_papel_coordenador(
    client: TestClient,
    db_session: Session,
) -> None:
    """Cenários 9 e 12: Bloqueia papel coordenador, escalação pelo cliente, spoofing de IDs e auto-lockout do admin."""
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")
    headers_ga = _login_headers(client, "gestor.a@vertice.edu.br", "SenhaForte@123")
    headers_p1 = _login_headers(client, "prof1@vertice.edu.br", "SenhaForte@123")

    # 1. Enum canônico permanece estrito e 'coordenador' é rejeitado com 422 pela API
    assert {p.value for p in PapelUsuario} == {"administrador", "gestor", "professor"}
    resp_coord = client.post(
        "/api/v1/usuarios",
        json={
            "nome": "Tentativa Coordenador",
            "email": "coord@vertice.edu.br",
            "senha": "SenhaForte@123",
            "papel": "coordenador",
        },
        headers=headers_admin,
    )
    assert resp_coord.status_code == 422

    # 2. Administrador não pode rebaixar ou desativar a própria conta
    assert (
        client.patch(
            f"/api/v1/usuarios/{cenario['admin'].id}",
            json={"ativo": False},
            headers=headers_admin,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/v1/usuarios/{cenario['admin'].id}",
            json={"papel": "professor"},
            headers=headers_admin,
        ).status_code
        == 400
    )

    # 3. Gestor e Professor tentando promover a si próprios para administrador -> 403
    assert (
        client.patch(
            f"/api/v1/usuarios/{cenario['gestor_a'].id}",
            json={"papel": "administrador"},
            headers=headers_ga,
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/usuarios/{cenario['prof1'].id}",
            json={"papel": "administrador"},
            headers=headers_p1,
        ).status_code
        == 403
    )

    # 4. Spoofing de escola_id no Assistente ou Avaliações é bloqueado pelo escopo da sessão
    assert (
        client.post(
            "/api/v1/assistente/contexto",
            json={"tipo_contexto": "ESCOLA", "escola_id": str(cenario["escola_b"].id)},
            headers=headers_ga,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/avaliacoes",
            json={
                "titulo": "Spoof Turma Não Vinculada",
                "turma_id": str(cenario["turma_3a"].id),
                "disciplina_id": str(cenario["disc_qui"].id),
                "periodo_letivo": "1º Bimestre",
                "data_avaliacao": "2026-05-10",
            },
            headers=headers_p1,
        ).status_code
        == 403
    )


def test_auditoria_tecnica_persistente_sem_vazamento_segredos(
    client: TestClient,
    db_session: Session,
) -> None:
    """Cenário 10: Ações administrativas sensíveis ficam gravadas em auditoria sem senhas, hashes ou tokens."""
    cenario = _criar_cenario_fase4(db_session)
    headers_admin = _login_headers(client, "admin@vertice.edu.br", "SenhaForte@123")

    senha_secreta = "SegredoUltra@987"
    r_user = client.post(
        "/api/v1/usuarios",
        json={
            "nome": "Novo Docente Auditado",
            "email": "docente.audit@vertice.edu.br",
            "senha": senha_secreta,
            "papel": "professor",
            "escola_id": str(cenario["escola_a"].id),
        },
        headers=headers_admin,
    )
    assert r_user.status_code == 201
    uid = r_user.json()["id"]

    assert (
        client.patch(
            f"/api/v1/usuarios/{uid}",
            json={"nome": "Docente Auditado Editado", "senha": "OutroSegredo@777", "ativo": False},
            headers=headers_admin,
        ).status_code
        == 200
    )

    r_cred = client.post(
        "/api/v1/previsoes/credenciais",
        json={"nome": "Pipeline Auditoria", "escola_id": str(cenario["escola_a"].id)},
        headers=headers_admin,
    )
    assert r_cred.status_code == 201
    cred_id = r_cred.json()["id"]
    segredo_ml = r_cred.json()["chave_secreta"]

    assert (
        client.patch(
            f"/api/v1/previsoes/credenciais/{cred_id}/revogar",
            headers=headers_admin,
        ).status_code
        == 200
    )

    resp_aud = client.get("/api/v1/admin/auditoria-tecnica", headers=headers_admin)
    assert resp_aud.status_code == 200
    eventos = resp_aud.json()
    acoes = {ev["acao"] for ev in eventos}
    assert {
        "USUARIO_CRIADO",
        "USUARIO_ATUALIZADO",
        "CREDENCIAL_ML_EMITIDA",
        "CREDENCIAL_ML_REVOGADA",
    }.issubset(acoes)

    serializado = str(eventos)
    assert senha_secreta not in serializado
    assert "OutroSegredo@777" not in serializado
    assert segredo_ml not in serializado
    assert db_session.query(AuditoriaOperacaoTecnica).count() >= 4


def test_streamlit_menus_e_permissoes_alinhados_por_papel() -> None:
    """Cenário 11 e 12: Verifica alinhamento real entre `app.py`, menu lateral, guards visuais e papel canônico."""
    fe_app = _carregar_frontend_app()
    st = _preparar_frontend()
    import pages.administracao_tecnica as pg_admin
    import pages.atribuicao as pg_atrib
    import pages.perfil as pg_perfil

    for mod in (pg_admin, pg_atrib, pg_perfil):
        importlib.reload(mod)

    try:
        # Administrador: somente Administração Técnica (default) + Meu Perfil
        st.session_state["usuario_api"] = {"papel": "administrador"}
        st.session_state["perfil"] = "administrador"
        nav_adm, menu_adm = fe_app.montar_paginas_internas()
        assert [p.title for p in menu_adm] == ["Administração Técnica", "Meu Perfil"]
        assert [p.url_path for p in nav_adm] == ["administracao-tecnica", "perfil"]

        # Gestor/Coordenador: possui Atribuir turmas + páginas pedagógicas
        st.session_state["usuario_api"] = {"papel": "gestor"}
        st.session_state["perfil"] = "gestor"
        _, menu_gestor = fe_app.montar_paginas_internas()
        titulos_gestor = [p.title for p in menu_gestor]
        assert "Visão geral" in titulos_gestor
        assert "Atribuir turmas" in titulos_gestor
        assert "Administração Técnica" not in titulos_gestor
        assert pg_perfil._ROTULOS_PAPEL["gestor"] == "Gestor/Coordenador"

        # Professor: páginas pedagógicas próprias, sem Atribuir turmas e sem Administração Técnica
        st.session_state["usuario_api"] = {"papel": "professor"}
        st.session_state["perfil"] = "professor"
        _, menu_prof = fe_app.montar_paginas_internas()
        titulos_prof = [p.title for p in menu_prof]
        assert "Visão geral" in titulos_prof
        assert "Atribuir turmas" not in titulos_prof
        assert "Administração Técnica" not in titulos_prof

        # Guards diretos nas páginas
        erros_registrados: list[str] = []
        st.error = lambda msg, **_kw: erros_registrados.append(str(msg))
        st.session_state["logado"] = True

        st.session_state["usuario_api"] = {"papel": "gestor"}
        st.session_state["perfil"] = "gestor"
        pg_admin.render()

        st.session_state["usuario_api"] = {"papel": "administrador"}
        st.session_state["perfil"] = "administrador"
        pg_atrib.render()

        assert len(erros_registrados) == 2
        assert all("Permissão insuficiente" in msg for msg in erros_registrados)
    finally:
        st.session_state.clear()
