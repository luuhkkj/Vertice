"""
Camada de serviço para regras de negócio de Usuários.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.modules.escolas.repository import EscolaRepository
from app.modules.usuarios.models import PapelUsuario, Usuario
from app.modules.usuarios.repository import UsuarioRepository
from app.modules.usuarios.schemas import UsuarioCreate, UsuarioUpdate


class UsuarioService:
    """Regras de negócio de criação, consulta e atualização de usuários."""

    @staticmethod
    def criar_usuario(db: Session, dados: UsuarioCreate) -> Usuario:
        """
        Cria um novo usuário garantindo unicidade de e-mail, validação de papel,
        existência da escola (se informada) e hash seguro de senha.
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

        if dados.escola_id is not None:
            escola = EscolaRepository.get_by_id(db, dados.escola_id)
            if escola is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Escola informada para vínculo do usuário não encontrada.",
                )

        novo_usuario = Usuario(
            nome=dados.nome.strip(),
            email=email_normalizado,
            senha_hash=get_password_hash(dados.senha),
            papel=papel_validado,
            escola_id=dados.escola_id,
            ativo=dados.ativo,
        )
        try:
            return UsuarioRepository.create(db, novo_usuario)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao criar usuário: e-mail já utilizado.",
            ) from exc

    @staticmethod
    def _garantir_escopo_consulta_gestor(
        current_user: Optional[Usuario],
        alvo: Optional[Usuario] = None,
    ) -> Optional[uuid.UUID]:
        """Valida que um gestor só acesse usuários da própria escola (ou professores multi-escola sem vínculo fixo)."""
        if current_user is None or current_user.papel == PapelUsuario.ADMINISTRADOR:
            return None
        if current_user.papel != PapelUsuario.GESTOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente para consultar usuários.",
            )
        if current_user.escola_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor sem unidade escolar vinculada não pode listar ou consultar usuários de escola.",
            )
        if alvo is not None:
            mesmo_escopo = alvo.escola_id == current_user.escola_id
            prof_multi = (
                alvo.papel == PapelUsuario.PROFESSOR and alvo.escola_id is None
            )
            if not (mesmo_escopo or prof_multi):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: usuário pertence a outro escopo escolar ou administrativo.",
                )
        return current_user.escola_id

    @staticmethod
    def obter_por_id(
        db: Session,
        usuario_id: uuid.UUID,
        current_user: Optional[Usuario] = None,
    ) -> Usuario:
        usuario = UsuarioRepository.get_by_id(db, usuario_id)
        if usuario is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado.",
            )
        UsuarioService._garantir_escopo_consulta_gestor(current_user, alvo=usuario)
        return usuario

    @staticmethod
    def listar_usuarios(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        current_user: Optional[Usuario] = None,
        papel: Optional[PapelUsuario] = None,
        apenas_ativos: bool = False,
    ) -> list[Usuario]:
        escola_escopo = UsuarioService._garantir_escopo_consulta_gestor(current_user)
        return UsuarioRepository.list_filtered(
            db,
            escola_id_escopo=escola_escopo,
            incluir_professores_sem_escola=(escola_escopo is not None),
            papel=papel,
            apenas_ativos=apenas_ativos,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    def atualizar_usuario(
        db: Session, usuario_id: uuid.UUID, dados: UsuarioUpdate
    ) -> Usuario:
        usuario = UsuarioService.obter_por_id(db, usuario_id)

        campos_enviados = dados.model_fields_set

        if "email" in campos_enviados and dados.email is not None:
            email_norm = dados.email.strip().lower()
            if email_norm != usuario.email:
                outro = UsuarioRepository.get_by_email(db, email_norm)
                if outro is not None and outro.id != usuario.id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Já existe outro usuário cadastrado com este endereço de e-mail.",
                    )
                usuario.email = email_norm

        if "nome" in campos_enviados and dados.nome is not None:
            usuario.nome = dados.nome.strip()

        if "senha" in campos_enviados and dados.senha is not None:
            usuario.senha_hash = get_password_hash(dados.senha)

        if "papel" in campos_enviados and dados.papel is not None:
            usuario.papel = dados.papel

        if "escola_id" in campos_enviados:
            if dados.escola_id is not None:
                escola = EscolaRepository.get_by_id(db, dados.escola_id)
                if escola is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Escola informada não encontrada.",
                    )
            usuario.escola_id = dados.escola_id

        if "ativo" in campos_enviados and dados.ativo is not None:
            usuario.ativo = dados.ativo

        try:
            return UsuarioRepository.update(db, usuario)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao atualizar usuário.",
            ) from exc
