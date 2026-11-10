"""
Camada de serviço para regras de negócio de Disciplinas.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.disciplinas.models import Disciplina
from app.modules.disciplinas.repository import DisciplinaRepository
from app.modules.disciplinas.schemas import DisciplinaCreate, DisciplinaUpdate


class DisciplinaService:
    """Regras de negócio para cadastro, atualização e consulta de disciplinas."""

    @staticmethod
    def criar_disciplina(db: Session, dados: DisciplinaCreate) -> Disciplina:
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
            return DisciplinaRepository.create(db, nova_disciplina)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade: código de disciplina já cadastrado.",
            ) from exc

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
        db: Session, disciplina_id: uuid.UUID, dados: DisciplinaUpdate
    ) -> Disciplina:
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
            return DisciplinaRepository.update(db, disciplina)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao atualizar disciplina.",
            ) from exc
