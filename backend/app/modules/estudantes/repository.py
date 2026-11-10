"""
Repositório de acesso a dados para Estudantes, Boletins por Período e Notas por Disciplina.
Todas as consultas aplicam filtragem estrita de escopo (escola para gestores,
vínculo turma/disciplina em `ProfessorTurma` para professores).
"""

from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    NotaDisciplina,
)


class EstudanteRepository:
    """Operações de consulta e busca de estudantes e históricos escolares."""

    @staticmethod
    def get_by_id(db: Session, estudante_id: uuid.UUID) -> Optional[Estudante]:
        stmt = (
            select(Estudante)
            .options(
                selectinload(Estudante.boletins).selectinload(
                    BoletimPeriodo.notas_disciplina
                )
            )
            .where(Estudante.id == estudante_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_escola_e_codigo(
        db: Session,
        escola_id: uuid.UUID,
        codigo_anonimo: str,
    ) -> Optional[Estudante]:
        stmt = select(Estudante).where(
            Estudante.escola_id == escola_id,
            Estudante.codigo_anonimo == codigo_anonimo.strip(),
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_escola(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Estudante]:
        stmt = select(Estudante).where(Estudante.escola_id == escola_id)
        if turma_id is not None or ano_letivo is not None or periodo_letivo is not None:
            stmt = stmt.join(
                BoletimPeriodo, BoletimPeriodo.estudante_id == Estudante.id
            )
            if turma_id is not None:
                stmt = stmt.where(BoletimPeriodo.turma_id == turma_id)
            if ano_letivo is not None:
                stmt = stmt.where(BoletimPeriodo.ano_letivo == ano_letivo)
            if periodo_letivo is not None:
                stmt = stmt.where(
                    BoletimPeriodo.periodo_letivo == periodo_letivo.strip()
                )
            stmt = stmt.distinct()

        stmt = stmt.order_by(Estudante.codigo_anonimo).offset(skip).limit(limit)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_by_professor(
        db: Session,
        professor_id: uuid.UUID,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Estudante]:
        """
        Lista apenas os estudantes que possuem registros em turmas (e disciplinas)
        às quais o professor está efetivamente vinculado em `professor_turmas`.
        """
        stmt = (
            select(Estudante)
            .join(BoletimPeriodo, BoletimPeriodo.estudante_id == Estudante.id)
            .join(
                ProfessorTurma,
                ProfessorTurma.turma_id == BoletimPeriodo.turma_id,
            )
            .where(ProfessorTurma.professor_id == professor_id)
        )

        if turma_id is not None:
            stmt = stmt.where(BoletimPeriodo.turma_id == turma_id)
        if ano_letivo is not None:
            stmt = stmt.where(BoletimPeriodo.ano_letivo == ano_letivo)
        if periodo_letivo is not None:
            stmt = stmt.where(
                BoletimPeriodo.periodo_letivo == periodo_letivo.strip()
            )
        if disciplina_id is not None:
            stmt = stmt.join(
                NotaDisciplina,
                NotaDisciplina.boletim_id == BoletimPeriodo.id,
            ).where(
                NotaDisciplina.disciplina_id == disciplina_id,
                (ProfessorTurma.disciplina_id == disciplina_id)
                | (ProfessorTurma.disciplina_id.is_(None)),
            )

        stmt = (
            stmt.distinct()
            .order_by(Estudante.codigo_anonimo)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_boletim_by_chave(
        db: Session,
        estudante_id: uuid.UUID,
        escola_id: uuid.UUID,
        turma_id: uuid.UUID,
        ano_letivo: int,
        periodo_letivo: str,
    ) -> Optional[BoletimPeriodo]:
        stmt = select(BoletimPeriodo).where(
            BoletimPeriodo.estudante_id == estudante_id,
            BoletimPeriodo.escola_id == escola_id,
            BoletimPeriodo.turma_id == turma_id,
            BoletimPeriodo.ano_letivo == ano_letivo,
            BoletimPeriodo.periodo_letivo == periodo_letivo.strip(),
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_nota_disciplina(
        db: Session,
        boletim_id: uuid.UUID,
        disciplina_id: uuid.UUID,
    ) -> Optional[NotaDisciplina]:
        stmt = select(NotaDisciplina).where(
            NotaDisciplina.boletim_id == boletim_id,
            NotaDisciplina.disciplina_id == disciplina_id,
        )
        return db.execute(stmt).scalar_one_or_none()

