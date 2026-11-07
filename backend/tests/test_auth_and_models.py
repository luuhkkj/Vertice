"""
Suíte de testes da Fase 2:
- Persistência e regras de negócio de Usuário, Escola, Turma, Disciplina e ProfessorTurma.
- Autenticação JWT, hash de senha, expiração e rejeição de usuário inativo.
- Controle de acesso baseado em papéis (RBAC) e vínculo de professor com turma.
"""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.modules.usuarios.models import PapelUsuario
from app.modules.usuarios.schemas import UsuarioCreate
from app.modules.usuarios.service import UsuarioService
from app.scripts.create_admin import criar_administrador_inicial


def _obter_headers_auth(client: TestClient, email: str, senha: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "senha": senha},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_criar_usuario_e_armazenar_senha_como_hash(db_session: Session) -> None:
    """Verifica criação de usuário e garante que a senha é salva apenas como hash."""
    senha_plana = "SegredoForte#2026"
    usuario = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Maria Gestora",
            email="Maria.Gestora@Escola.edu.br",
            senha=senha_plana,
            papel=PapelUsuario.GESTOR,
        ),
    )

    assert usuario.id is not None
    assert usuario.email == "maria.gestora@escola.edu.br"
    assert usuario.papel == PapelUsuario.GESTOR
    assert usuario.ativo is True
    assert usuario.senha_hash != senha_plana
    assert verify_password(senha_plana, usuario.senha_hash) is True


def test_impedir_email_duplicado(
    client: TestClient, db_session: Session
) -> None:
    """Verifica que o sistema impede o cadastro de dois usuários com o mesmo e-mail."""
    criar_administrador_inicial(
        db_session, "Admin Root", "admin@vertice.edu.br", "Admin@123"
    )
    headers = _obter_headers_auth(client, "admin@vertice.edu.br", "Admin@123")

    payload = {
        "nome": "Prof João",
        "email": "joao@vertice.edu.br",
        "senha": "Password123",
        "papel": "professor",
    }
    r1 = client.post("/api/v1/usuarios", json=payload, headers=headers)
    assert r1.status_code == 201

    # Tentativa duplicada (mesmo com letras maiúsculas)
    payload_dup = {
        "nome": "Outro João",
        "email": "JOAO@vertice.edu.br",
        "senha": "Password456",
        "papel": "professor",
    }
    r2 = client.post("/api/v1/usuarios", json=payload_dup, headers=headers)
    assert r2.status_code == 409
    assert "e-mail" in r2.json()["detail"].lower()


def test_autenticar_com_senha_correta_e_obter_me(
    client: TestClient, db_session: Session
) -> None:
    """Verifica login com credenciais válidas e consulta ao endpoint /api/v1/auth/me."""
    UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Carlos Professor",
            email="carlos@vertice.edu.br",
            senha="SenhaCorreta123",
            papel=PapelUsuario.PROFESSOR,
        ),
    )

    resp_login = client.post(
        "/api/v1/auth/login",
        json={"email": "carlos@vertice.edu.br", "senha": "SenhaCorreta123"},
    )
    assert resp_login.status_code == 200
    body = resp_login.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["usuario"]["email"] == "carlos@vertice.edu.br"
    assert body["usuario"]["papel"] == "professor"
    assert "senha" not in body["usuario"]
    assert "senha_hash" not in body["usuario"]

    # Valida /api/v1/auth/me com o token recebido
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    resp_me = client.get("/api/v1/auth/me", headers=headers)
    assert resp_me.status_code == 200
    me_data = resp_me.json()
    assert me_data["email"] == "carlos@vertice.edu.br"
    assert me_data["nome"] == "Carlos Professor"


def test_rejeitar_senha_incorreta(
    client: TestClient, db_session: Session
) -> None:
    """Verifica que senha incorreta retorna HTTP 401."""
    UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Ana Professora",
            email="ana@vertice.edu.br",
            senha="SenhaCorreta123",
            papel=PapelUsuario.PROFESSOR,
        ),
    )

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "ana@vertice.edu.br", "senha": "SenhaErrada999"},
    )
    assert resp.status_code == 401


def test_rejeitar_usuario_inativo_no_login_e_no_token(
    client: TestClient, db_session: Session
) -> None:
    """Verifica que usuário inativo não pode autenticar nem usar um token já emitido."""
    usuario = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Pedro Inativo",
            email="pedro@vertice.edu.br",
            senha="Senha12345",
            papel=PapelUsuario.PROFESSOR,
            ativo=False,
        ),
    )

    # 1. Tentativa de login deve ser rejeitada
    resp_login = client.post(
        "/api/v1/auth/login",
        json={"email": "pedro@vertice.edu.br", "senha": "Senha12345"},
    )
    assert resp_login.status_code == 403

    # 2. Mesmo com um token assinado manualmente, o acesso a rotas protegidas deve ser negado
    token_manual = create_access_token(subject=str(usuario.id))
    resp_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_manual}"},
    )
    assert resp_me.status_code == 403


def test_rejeitar_token_invalido_ou_expirado(
    client: TestClient, db_session: Session
) -> None:
    """Verifica rejeição de token ausente, adulterado ou expirado."""
    usuario = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Julia Ativa",
            email="julia@vertice.edu.br",
            senha="SenhaJulia123",
            papel=PapelUsuario.PROFESSOR,
        ),
    )

    # Sem token
    resp_sem = client.get("/api/v1/auth/me")
    assert resp_sem.status_code == 401

    # Token malformado / assinatura inválida
    resp_invalido = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer token.invalido.assinatura"},
    )
    assert resp_invalido.status_code == 401

    # Token expirado
    token_expirado = create_access_token(
        subject=str(usuario.id),
        expires_delta=timedelta(minutes=-5),
    )
    resp_expirado = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_expirado}"},
    )
    assert resp_expirado.status_code == 401
    assert "expirado" in resp_expirado.json()["detail"].lower()


def test_verificar_acesso_por_papel_rbac(
    client: TestClient, db_session: Session
) -> None:
    """
    Verifica controle de acesso por papel:
    - Professor não pode criar usuários nem criar escolas.
    - Gestor pode listar usuários e criar escolas, mas não pode criar novos usuários.
    - Administrador pode criar usuários e gerenciar recursos.
    """
    criar_administrador_inicial(
        db_session, "Admin", "admin@vertice.edu.br", "AdminSenha123"
    )
    UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Gestor Escolar",
            email="gestor@vertice.edu.br",
            senha="GestorSenha123",
            papel=PapelUsuario.GESTOR,
        ),
    )
    UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Professor Comum",
            email="prof@vertice.edu.br",
            senha="ProfSenha123",
            papel=PapelUsuario.PROFESSOR,
        ),
    )

    headers_admin = _obter_headers_auth(
        client, "admin@vertice.edu.br", "AdminSenha123"
    )
    headers_gestor = _obter_headers_auth(
        client, "gestor@vertice.edu.br", "GestorSenha123"
    )
    headers_prof = _obter_headers_auth(
        client, "prof@vertice.edu.br", "ProfSenha123"
    )

    novo_user_payload = {
        "nome": "Novo Docente",
        "email": "novo.docente@vertice.edu.br",
        "senha": "SenhaDocente123",
        "papel": "professor",
    }

    # Professor tentando criar usuário -> 403
    assert (
        client.post(
            "/api/v1/usuarios", json=novo_user_payload, headers=headers_prof
        ).status_code
        == 403
    )

    # Gestor tentando criar usuário -> 403
    assert (
        client.post(
            "/api/v1/usuarios", json=novo_user_payload, headers=headers_gestor
        ).status_code
        == 403
    )

    # Administrador criando usuário -> 201
    assert (
        client.post(
            "/api/v1/usuarios", json=novo_user_payload, headers=headers_admin
        ).status_code
        == 201
    )

    # Professor tentando criar escola -> 403
    escola_payload = {"nome": "Escola Estadual Vértice", "codigo": "EEV-01"}
    assert (
        client.post(
            "/api/v1/escolas", json=escola_payload, headers=headers_prof
        ).status_code
        == 403
    )

    # Gestor criando escola -> 201
    assert (
        client.post(
            "/api/v1/escolas", json=escola_payload, headers=headers_gestor
        ).status_code
        == 201
    )


def test_fluxo_completo_escola_turma_disciplina_atribuicao_e_vinculo_professor(
    client: TestClient, db_session: Session
) -> None:
    """
    Valida:
    1. Criação de escola, turma e disciplina.
    2. Associação entre professor, turma e disciplina (e bloqueio de duplicatas).
    3. Impedimento de associar usuário que não seja professor.
    4. Permissão para o professor acessar turma com vínculo e bloqueio (403) para turma sem vínculo.
    """
    criar_administrador_inicial(
        db_session, "Admin", "admin@vertice.edu.br", "AdminSenha123"
    )
    gestor = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Gestor",
            email="gestor@vertice.edu.br",
            senha="GestorSenha123",
            papel=PapelUsuario.GESTOR,
        ),
    )
    prof = UsuarioService.criar_usuario(
        db_session,
        UsuarioCreate(
            nome="Prof Matemática",
            email="prof.mat@vertice.edu.br",
            senha="ProfSenha123",
            papel=PapelUsuario.PROFESSOR,
        ),
    )

    headers_gestor = _obter_headers_auth(
        client, "gestor@vertice.edu.br", "GestorSenha123"
    )
    headers_prof = _obter_headers_auth(
        client, "prof.mat@vertice.edu.br", "ProfSenha123"
    )

    # 1. Criar Escola
    resp_escola = client.post(
        "/api/v1/escolas",
        json={"nome": "Colégio Estadual Central", "codigo": "CEC-2026"},
        headers=headers_gestor,
    )
    assert resp_escola.status_code == 201
    escola_id = resp_escola.json()["id"]

    # 2. Criar duas Turmas (Turma A e Turma B)
    resp_turma_a = client.post(
        "/api/v1/turmas",
        json={
            "nome": "Turma A",
            "serie": "1ª Série",
            "turno": "Matutino",
            "ano_letivo": 2026,
            "escola_id": escola_id,
        },
        headers=headers_gestor,
    )
    assert resp_turma_a.status_code == 201
    turma_a_id = resp_turma_a.json()["id"]

    resp_turma_b = client.post(
        "/api/v1/turmas",
        json={
            "nome": "Turma B",
            "serie": "2ª Série",
            "turno": "Vespertino",
            "ano_letivo": 2026,
            "escola_id": escola_id,
        },
        headers=headers_gestor,
    )
    assert resp_turma_b.status_code == 201
    turma_b_id = resp_turma_b.json()["id"]

    # 3. Criar Disciplina
    resp_disc = client.post(
        "/api/v1/disciplinas",
        json={"nome": "Matemática", "codigo": "MAT"},
        headers=headers_gestor,
    )
    assert resp_disc.status_code == 201
    disciplina_id = resp_disc.json()["id"]

    # 4. Tentar associar usuário com papel de GESTOR como professor -> deve falhar (400)
    resp_atrib_invalida = client.post(
        "/api/v1/atribuicoes",
        json={
            "professor_id": str(gestor.id),
            "turma_id": turma_a_id,
            "disciplina_id": disciplina_id,
        },
        headers=headers_gestor,
    )
    assert resp_atrib_invalida.status_code == 400
    assert "professor" in resp_atrib_invalida.json()["detail"].lower()

    # 5. Associar o Professor à Turma A com a disciplina Matemática -> deve funcionar (201)
    resp_atrib = client.post(
        "/api/v1/atribuicoes",
        json={
            "professor_id": str(prof.id),
            "turma_id": turma_a_id,
            "disciplina_id": disciplina_id,
        },
        headers=headers_gestor,
    )
    assert resp_atrib.status_code == 201

    # 6. Tentar duplicar a mesma atribuição -> deve retornar 409 Conflict
    resp_atrib_dup = client.post(
        "/api/v1/atribuicoes",
        json={
            "professor_id": str(prof.id),
            "turma_id": turma_a_id,
            "disciplina_id": disciplina_id,
        },
        headers=headers_gestor,
    )
    assert resp_atrib_dup.status_code == 409

    # 7. Professor lista turmas -> só deve ver a Turma A (à qual tem vínculo)
    resp_lista_prof = client.get("/api/v1/turmas", headers=headers_prof)
    assert resp_lista_prof.status_code == 200
    turmas_visiveis = resp_lista_prof.json()
    assert len(turmas_visiveis) == 1
    assert turmas_visiveis[0]["id"] == turma_a_id

    # 8. Professor acessa detalhes da Turma A -> permitido (200)
    resp_acesso_a = client.get(
        f"/api/v1/turmas/{turma_a_id}", headers=headers_prof
    )
    assert resp_acesso_a.status_code == 200

    # 9. Professor tenta acessar detalhes da Turma B (sem vínculo) -> bloqueado (403)
    resp_acesso_b = client.get(
        f"/api/v1/turmas/{turma_b_id}", headers=headers_prof
    )
    assert resp_acesso_b.status_code == 403
    assert "vínculo" in resp_acesso_b.json()["detail"].lower()

