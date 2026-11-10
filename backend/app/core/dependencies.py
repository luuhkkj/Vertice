"""
Dependências de autenticação, autorização baseada em papéis (RBAC),
escopo de escola para gestores e vínculo de turmas para professores.
"""

from typing import Callable, Optional
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.connection import get_db
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Recupera e valida o usuário autenticado a partir do token JWT Bearer.
    Rejeita tokens ausentes, inválidos, expirados ou pertencentes a usuários inativos.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: identificador ausente.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = uuid.UUID(str(sub))
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    stmt = select(Usuario).where(Usuario.id == user_id)
    usuario = db.execute(stmt).scalar_one_or_none()

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo. Autenticação não permitida.",
        )

    return usuario


def require_roles(*allowed_roles: PapelUsuario) -> Callable[[Usuario], Usuario]:
    """
    Fábrica de dependências para exigir que o usuário autenticado possua um dos papéis informados.
    """

    def role_checker(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.papel not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: você não possui permissão para realizar esta ação.",
            )
        return current_user

    return role_checker


# Dependências reutilizáveis por papel
require_admin = require_roles(PapelUsuario.ADMINISTRADOR)
require_gestor_ou_admin = require_roles(
    PapelUsuario.ADMINISTRADOR, PapelUsuario.GESTOR
)
require_qualquer_papel = require_roles(
    PapelUsuario.ADMINISTRADOR,
    PapelUsuario.GESTOR,
    PapelUsuario.PROFESSOR,
)

# Política explícita para importação de datasets escolares (Fase 3) e acesso pedagógico (Fase 4):
# O perfil 'gestor' representa a coordenação escolar e os professores importam e gerenciam
# dados exclusivamente de suas turmas e disciplinas vinculadas.
# Administradores NÃO recebem permissão pedagógica ou de importação automaticamente.
PAPEIS_AUTORIZADOS_IMPORTACAO: tuple[PapelUsuario, ...] = (
    PapelUsuario.GESTOR,
    PapelUsuario.PROFESSOR,
)
PAPEIS_AUTORIZADOS_PEDAGOGICO: tuple[PapelUsuario, ...] = (
    PapelUsuario.GESTOR,
    PapelUsuario.PROFESSOR,
)
require_importacao_datasets = require_roles(*PAPEIS_AUTORIZADOS_IMPORTACAO)
require_acesso_pedagogico = require_roles(*PAPEIS_AUTORIZADOS_PEDAGOGICO)


def garantir_escopo_importacao_usuario(usuario: Usuario) -> None:
    """
    Valida pré-requisitos de escopo para operações de importação e módulos pedagógicos:
    - Apenas GESTOR e PROFESSOR são autorizados (ADMINISTRADOR é bloqueado).
    - Se o usuário for GESTOR, exige que possua uma escola válida vinculada (`escola_id`).
    """
    if usuario.papel not in PAPEIS_AUTORIZADOS_IMPORTACAO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: seu perfil não possui autorização pedagógica ou de importação.",
        )

    if usuario.papel == PapelUsuario.GESTOR and usuario.escola_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: gestor não possui uma unidade escolar vinculada.",
        )


def garantir_escopo_pedagogico_turma_disciplina(
    db: Session,
    usuario: Usuario,
    turma_id: uuid.UUID,
    disciplina_id: Optional[uuid.UUID] = None,
) -> tuple[Turma, Optional[uuid.UUID]]:
    """
    Valida rigorosamente o escopo pedagógico (Fase 4) sobre uma turma e disciplina:
    - Bloqueia ADMINISTRADOR.
    - Exige que a Turma e sua Escola existam e estejam ativas (`ativo=True`).
    - Se `disciplina_id` for informada, exige que a Disciplina exista e esteja ativa.
    - Para GESTOR: exige que `turma.escola_id == usuario.escola_id`.
    - Para PROFESSOR:
      * Se `usuario.escola_id` estiver definido, exige `turma.escola_id == usuario.escola_id`.
      * Exige vínculo em `ProfessorTurma` para a turma:
        - Se `disciplina_id` for informada, exige vínculo explícito com `disciplina_id`
          ou vínculo geral na turma (`ProfessorTurma.disciplina_id IS NULL`).
        - Se `disciplina_id` for `None`, exige ao menos um vínculo ativo na turma.
    Retorna `(turma, disciplina_id)`.
    """
    from app.modules.disciplinas.models import Disciplina
    from app.modules.escolas.models import Escola

    garantir_escopo_importacao_usuario(usuario)

    stmt_turma = (
        select(Turma, Escola)
        .join(Escola, Turma.escola_id == Escola.id)
        .where(Turma.id == turma_id)
    )
    row = db.execute(stmt_turma).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Turma não encontrada.",
        )
    turma, escola = row
    if not turma.ativo or not escola.ativo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A turma ou unidade escolar informada está inativa.",
        )

    if disciplina_id is not None:
        stmt_disc = select(Disciplina).where(Disciplina.id == disciplina_id)
        disc = db.execute(stmt_disc).scalar_one_or_none()
        if disc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Disciplina não encontrada.",
            )
        if not disc.ativo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A disciplina informada está inativa.",
            )

    if usuario.papel == PapelUsuario.GESTOR:
        if usuario.escola_id != turma.escola_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: esta turma pertence a outra unidade escolar.",
            )
        return turma, disciplina_id

    if usuario.papel == PapelUsuario.PROFESSOR:
        if usuario.escola_id is not None and usuario.escola_id != turma.escola_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: esta turma pertence a uma escola fora do escopo do professor.",
            )

        stmt_atrib = select(ProfessorTurma).where(
            ProfessorTurma.professor_id == usuario.id,
            ProfessorTurma.turma_id == turma.id,
        )
        atribuicoes = list(db.execute(stmt_atrib).scalars().all())
        if not atribuicoes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: professor não possui vínculo autorizado com esta turma.",
            )

        if disciplina_id is not None:
            discs_vinculadas = {a.disciplina_id for a in atribuicoes}
            if None not in discs_vinculadas and disciplina_id not in discs_vinculadas:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: professor não possui vínculo autorizado com esta disciplina na turma.",
                )
        return turma, disciplina_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado.",
    )


def verificar_vinculo_professor_turma_disciplina(
    db: Session,
    professor_id: uuid.UUID,
    turma_id: uuid.UUID,
    disciplina_id: Optional[uuid.UUID] = None,
) -> bool:
    """
    Verifica no banco de dados se o professor possui vínculo autorizado com a combinação
    de turma e disciplina em `professor_turmas`.
    - Se `disciplina_id` for informada, exige vínculo explícito com `(professor_id, turma_id, disciplina_id)`.
    - Se `disciplina_id` for `None`, verifica se há vínculo geral na turma (`disciplina_id IS NULL`).
    """
    if disciplina_id is not None:
        stmt = (
            select(ProfessorTurma.id)
            .where(
                ProfessorTurma.professor_id == professor_id,
                ProfessorTurma.turma_id == turma_id,
                ProfessorTurma.disciplina_id == disciplina_id,
            )
            .limit(1)
        )
    else:
        stmt = (
            select(ProfessorTurma.id)
            .where(
                ProfessorTurma.professor_id == professor_id,
                ProfessorTurma.turma_id == turma_id,
                ProfessorTurma.disciplina_id.is_(None),
            )
            .limit(1)
        )
    return db.execute(stmt).scalar_one_or_none() is not None


def garantir_acesso_escola(
    usuario: Usuario,
    escola_id: uuid.UUID,
) -> None:
    """
    Verifica se o usuário possui escopo autorizado sobre a escola informada.
    - Administrador: acesso irrestrito a qualquer escola.
    - Gestor vinculado a uma escola (`usuario.escola_id is not None`):
      restrito exclusivamente à sua própria escola.
    """
    if usuario.papel == PapelUsuario.ADMINISTRADOR:
        return

    if usuario.papel == PapelUsuario.GESTOR:
        if usuario.escola_id is not None and usuario.escola_id != escola_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: gestor vinculado a outra unidade escolar.",
            )
        return


def verificar_vinculo_professor_turma(
    db: Session,
    professor_id: uuid.UUID,
    turma_id: uuid.UUID,
) -> bool:
    """
    Verifica no banco de dados se um professor possui vínculo ativo com uma determinada turma.
    """
    stmt = (
        select(ProfessorTurma.id)
        .where(
            ProfessorTurma.professor_id == professor_id,
            ProfessorTurma.turma_id == turma_id,
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def garantir_acesso_turma(
    db: Session,
    usuario: Usuario,
    turma_id: uuid.UUID,
    escola_id: Optional[uuid.UUID] = None,
) -> None:
    """
    Valida se o usuário tem autorização para acessar uma turma específica.
    - Administradores possuem acesso irrestrito.
    - Gestores com `escola_id` vinculado só podem acessar turmas de sua própria escola.
    - Professores só podem acessar turmas às quais estão vinculados em `professor_turmas`.
    Lança HTTPException 403 em caso de violação de escopo.
    """
    if usuario.papel == PapelUsuario.ADMINISTRADOR:
        return

    if usuario.papel == PapelUsuario.GESTOR:
        if usuario.escola_id is not None:
            target_escola_id = escola_id
            if target_escola_id is None:
                stmt = select(Turma.escola_id).where(Turma.id == turma_id)
                target_escola_id = db.execute(stmt).scalar_one_or_none()
            if target_escola_id is not None and target_escola_id != usuario.escola_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: gestor não possui permissão para turmas de outra escola.",
                )
        return

    if not verificar_vinculo_professor_turma(db, usuario.id, turma_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: professor não possui vínculo com esta turma.",
        )
