"""
Camada de serviço para regras de negócio de Usuários.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.modules.usuarios.models import PapelUsuario, Usuario
from app.modules.usuarios.repository import UsuarioRepository
from app.modules.usuarios.schemas import UsuarioCreate, UsuarioUpdate


class UsuarioService:
    """Regras de negócio de criação, consulta e atualização de usuários."""

    @staticmethod
    def criar_usuario(db: Session, dados: UsuarioCreate) -> Usuario:
        """
        Cria um novo usuário garantindo unicidade de e-mail, validação de papel e hash de senha.
        """
        email_normalizado = dados.email.strip().lower()
        existente = UsuarioRepository.get_by_email(db, email_normalizado)
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe um usuário cadastrado com este endereço de e-mail.",
            )

        if not isinstance(dados.papel, PapelUsuario):
            try:
                papel_validado = PapelUsuario(dados.papel)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Papel de usuário inválido.",
                ) from exc
        else:
            papel_validado = dados.papel

        novo_usuario = Usuario(
            nome=dados.nome.strip(),
            email=email_normalizado,
            senha_hash=get_password_hash(dados.senha),
            papel=papel_validado,
            ativo=dados.ativo,
        )
        return UsuarioRepository.create(db, novo_usuario)

    @staticmethod
    def obter_por_id(db: Session, usuario_id: uuid.UUID) -> Usuario:
        usuario = UsuarioRepository.get_by_id(db, usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado.",
            )
        return usuario

    @staticmethod
    def listar_usuarios(db: Session, skip: int = 0, limit: int = 100) -> list[Usuario]:
        return UsuarioRepository.list_all(db, skip=skip, limit=limit)

    @staticmethod
    def atualizar_usuario(
        db: Session, usuario_id: uuid.UUID, dados: UsuarioUpdate
    ) -> Usuario:
        usuario = UsuarioService.obter_por_id(db, usuario_id)

        if dados.email is not None and dados.email != usuario.email:
            outro = UsuarioRepository.get_by_email(db, dados.email)
            if outro is not None and outro.id != usuario.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Já existe outro usuário cadastrado com este endereço de e-mail.",
                )
            usuario.email = dados.email

        if dados.nome is not None:
            usuario.nome = dados.nome.strip()

        if dados.senha is not None:
            usuario.senha_hash = get_password_hash(dados.senha)

        if dados.papel is not None:
            usuario.papel = dados.papel

        if dados.ativo is not None:
            usuario.ativo = dados.ativo

        return UsuarioRepository.update(db, usuario)

