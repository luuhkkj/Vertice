"""
Camada de serviço para regras de negócio de Escolas.
"""

from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import garantir_acesso_escola
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.escolas.models import Escola
from app.modules.escolas.repository import EscolaRepository
from app.modules.escolas.schemas import EscolaCreate, EscolaUpdate
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario


def _escola_ids_autorizadas_professor(db: Session, professor: Usuario) -> set[uuid.UUID]:
    """Retorna os IDs de escola vinculados diretamente ao professor ou às suas turmas."""
    permitidas: set[uuid.UUID] = set()
    if professor.escola_id is not None:
        permitidas.add(professor.escola_id)
    stmt = (
        select(Turma.escola_id)
        .join(ProfessorTurma, ProfessorTurma.turma_id == Turma.id)
        .where(ProfessorTurma.professor_id == professor.id)
    )
    permitidas.update(db.execute(stmt).scalars().all())
    return permitidas


class EscolaService:
    """Regras de negócio para cadastro, atualização e consulta de escolas."""

    @staticmethod
    def criar_escola(db: Session, dados: EscolaCreate) -> Escola:
        codigo_normalizado = dados.codigo.strip().upper()
        existente = EscolaRepository.get_by_codigo(db, codigo_normalizado)
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma escola cadastrada com este código.",
            )

        nova_escola = Escola(
            nome=dados.nome.strip(),
            codigo=codigo_normalizado,
            ativo=dados.ativo,
        )
        try:
            return EscolaRepository.create(db, nova_escola)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade: já existe uma escola com este código.",
            ) from exc

    @staticmethod
    def _garantir_leitura_escola(
        db: Session, usuario: Usuario, escola_id: uuid.UUID
    ) -> None:
        if usuario.papel == PapelUsuario.ADMINISTRADOR:
            return
        if usuario.papel == PapelUsuario.GESTOR:
            garantir_acesso_escola(usuario, escola_id)
            return
        if escola_id not in _escola_ids_autorizadas_professor(db, usuario):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: escola fora do seu escopo institucional.",
            )

    @staticmethod
    def obter_por_id(
        db: Session,
        escola_id: uuid.UUID,
        usuario: Optional[Usuario] = None,
    ) -> Escola:
        escola = EscolaRepository.get_by_id(db, escola_id)
        if escola is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escola não encontrada.",
            )
        if usuario is not None:
            EscolaService._garantir_leitura_escola(db, usuario, escola.id)
        return escola

    @staticmethod
    def listar_escolas(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        usuario: Optional[Usuario] = None,
    ) -> list[Escola]:
        if usuario is None or usuario.papel == PapelUsuario.ADMINISTRADOR:
            return EscolaRepository.list_all(db, skip=skip, limit=limit)

        if usuario.papel == PapelUsuario.GESTOR:
            if usuario.escola_id is None:
                return EscolaRepository.list_all(db, skip=skip, limit=limit)
            stmt = (
                select(Escola)
                .where(Escola.id == usuario.escola_id)
                .order_by(Escola.nome)
                .offset(skip)
                .limit(limit)
            )
            return list(db.execute(stmt).scalars().all())

        escola_ids = _escola_ids_autorizadas_professor(db, usuario)
        if not escola_ids:
            return []
        stmt = (
            select(Escola)
            .where(Escola.id.in_(escola_ids))
            .order_by(Escola.nome)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def atualizar_escola(
        db: Session,
        escola_id: uuid.UUID,
        dados: EscolaUpdate,
        usuario: Optional[Usuario] = None,
    ) -> Escola:
        escola = EscolaService.obter_por_id(db, escola_id)
        if usuario is not None:
            garantir_acesso_escola(usuario, escola.id)

        campos = dados.model_fields_set

        if "codigo" in campos and dados.codigo is not None and dados.codigo != escola.codigo:
            outro = EscolaRepository.get_by_codigo(db, dados.codigo)
            if outro is not None and outro.id != escola.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Já existe outra escola com este código.",
                )
            escola.codigo = dados.codigo

        if "nome" in campos and dados.nome is not None:
            escola.nome = dados.nome.strip()

        if "ativo" in campos and dados.ativo is not None:
            escola.ativo = dados.ativo

        try:
            return EscolaRepository.update(db, escola)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao atualizar escola.",
            ) from exc
