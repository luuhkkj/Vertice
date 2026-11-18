"""
Camada de serviço para regras de negócio de Disciplinas.
"""

from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.admin.service import AdminAuditService
from app.modules.disciplinas.models import Disciplina
from app.modules.disciplinas.repository import DisciplinaRepository
from app.modules.disciplinas.schemas import DisciplinaCreate, DisciplinaUpdate
from app.modules.usuarios.models import PapelUsuario, Usuario


def _validar_escrita_disciplina(usuario: Optional[Usuario]) -> None:
    if usuario is None:
        return
    if usuario.papel == PapelUsuario.ADMINISTRADOR:
        return
    if usuario.papel == PapelUsuario.GESTOR:
        if usuario.escola_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Gestor sem escola vinculada não possui permissão para gerenciar disciplinas.",
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado: perfil sem permissão para gerenciar disciplinas.",
    )


class DisciplinaService:
    """Regras de negócio para cadastro, atualização e consulta de disciplinas."""

    @staticmethod
    def criar_disciplina(
        db: Session,
        dados: DisciplinaCreate,
        usuario: Optional[Usuario] = None,
    ) -> Disciplina:
        _validar_escrita_disciplina(usuario)
        codigo_normalizado = dados.codigo.strip().upper()
        existente = DisciplinaRepository.get_by_codigo(db, codigo_normalizado)
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma disciplina cadastrada com este código.",
            )

        nova_disciplina = Disciplina(
            nome=dados.nome.strip(),
            codigo=codigo_normalizado,
            ativo=dados.ativo,
        )
        try:
            disciplina_criada = DisciplinaRepository.create(db, nova_disciplina)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade: código de disciplina já cadastrado.",
            ) from exc

        if usuario is not None:
            AdminAuditService.registrar_evento(
                db,
                acao="DISCIPLINA_CRIADA",
                entidade="disciplina",
                entidade_id=disciplina_criada.id,
                usuario_ator=usuario,
                detalhes={
                    "codigo": disciplina_criada.codigo,
                    "ativo": disciplina_criada.ativo,
                },
            )
        return disciplina_criada

    @staticmethod
    def obter_por_id(db: Session, disciplina_id: uuid.UUID) -> Disciplina:
        disciplina = DisciplinaRepository.get_by_id(db, disciplina_id)
        if disciplina is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Disciplina não encontrada.",
            )
        return disciplina

    @staticmethod
    def listar_disciplinas(
        db: Session, skip: int = 0, limit: int = 100
    ) -> list[Disciplina]:
        return DisciplinaRepository.list_all(db, skip=skip, limit=limit)

    @staticmethod
    def atualizar_disciplina(
        db: Session,
        disciplina_id: uuid.UUID,
        dados: DisciplinaUpdate,
        usuario: Optional[Usuario] = None,
    ) -> Disciplina:
        _validar_escrita_disciplina(usuario)
        disciplina = DisciplinaService.obter_por_id(db, disciplina_id)
        campos = dados.model_fields_set

        if "codigo" in campos and dados.codigo is not None and dados.codigo != disciplina.codigo:
            outro = DisciplinaRepository.get_by_codigo(db, dados.codigo)
            if outro is not None and outro.id != disciplina.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Já existe outra disciplina com este código.",
                )
            disciplina.codigo = dados.codigo

        if "nome" in campos and dados.nome is not None:
            disciplina.nome = dados.nome.strip()

        if "ativo" in campos and dados.ativo is not None:
            disciplina.ativo = dados.ativo

        try:
            disciplina_atualizada = DisciplinaRepository.update(db, disciplina)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao atualizar disciplina.",
            ) from exc

        if usuario is not None:
            AdminAuditService.registrar_evento(
                db,
                acao="DISCIPLINA_ATUALIZADA",
                entidade="disciplina",
                entidade_id=disciplina_atualizada.id,
                usuario_ator=usuario,
                detalhes={
                    "campos_alterados": sorted(campos),
                    "codigo": disciplina_atualizada.codigo,
                    "ativo": disciplina_atualizada.ativo,
                },
            )
        return disciplina_atualizada
