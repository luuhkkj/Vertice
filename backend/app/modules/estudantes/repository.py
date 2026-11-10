"""
Repositório de acesso a dados para Estudantes, Boletins por Período e Notas por Disciplina.
Todas as consultas aplicam filtragem estrita de escopo no próprio banco de dados:
- Escola para gestores (`BoletimPeriodo.escola_id == escola_id` e `Turma.ativo == True`).
- Vínculo real de turma E disciplina em `ProfessorTurma` para professores, respeitando
  a semântica explícita de `ProfessorTurma.disciplina_id IS NULL` (vínculo geral na turma)
  versus `ProfessorTurma.disciplina_id == NotaDisciplina.disciplina_id` (vínculo por disciplina).
"""

from typing import Optional
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import Select

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    NotaDisciplina,
)
from app.modules.turmas.models import Turma


class EstudanteRepository:
    """Operações de consulta e busca de estudantes e históricos escolares."""

    @staticmethod
    def get_by_id(db: Session, estudante_id: uuid.UUID) -> Optional[Estudante]:
        stmt = (
            select(Estudante)
            .options(
                selectinload(Estudante.boletins).selectinload(
                    BoletimPeriodo.turma
                ),
                selectinload(Estudante.boletins)
                .selectinload(BoletimPeriodo.notas_disciplina)
                .selectinload(NotaDisciplina.disciplina),
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
    def _build_escola_query(
        escola_id: uuid.UUID,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> Select[tuple[uuid.UUID]]:
        """Constrói subquery de IDs únicos de estudantes no escopo de uma escola."""
        stmt = select(Estudante.id).where(Estudante.escola_id == escola_id)
        if (
            turma_id is not None
            or disciplina_id is not None
            or ano_letivo is not None
            or periodo_letivo is not None
        ):
            stmt = stmt.join(
                BoletimPeriodo, BoletimPeriodo.estudante_id == Estudante.id
            ).join(Turma, Turma.id == BoletimPeriodo.turma_id)
            stmt = stmt.where(
                BoletimPeriodo.escola_id == escola_id,
                Turma.escola_id == escola_id,
                Turma.ativo.is_(True),
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
                ).where(NotaDisciplina.disciplina_id == disciplina_id)

        return stmt.distinct()

    @staticmethod
    def list_by_escola(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Estudante]:
        ids_subq = EstudanteRepository._build_escola_query(
            escola_id=escola_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            ano_letivo=ano_letivo,
            periodo_letivo=periodo_letivo,
        )
        stmt = (
            select(Estudante)
            .where(Estudante.id.in_(ids_subq))
            .order_by(Estudante.codigo_anonimo)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def count_by_escola(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> int:
        ids_subq = EstudanteRepository._build_escola_query(
            escola_id=escola_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            ano_letivo=ano_letivo,
            periodo_letivo=periodo_letivo,
        ).subquery()
        stmt = select(func.count()).select_from(ids_subq)
        return int(db.execute(stmt).scalar_one())

    @staticmethod
    def _build_professor_query(
        professor_id: uuid.UUID,
        escola_id_professor: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> Select[tuple[uuid.UUID]]:
        """
        Constrói subquery de IDs únicos de estudantes estritamente dentro do escopo de
        escola, turma E disciplina do professor em `ProfessorTurma`:
        - Se `ProfessorTurma.disciplina_id IS NOT NULL`, exige que exista `NotaDisciplina`
          com `NotaDisciplina.disciplina_id == ProfessorTurma.disciplina_id` e que a disciplina esteja ativa.
          Assim, estudantes que possuem notas apenas em outras disciplinas na mesma turma NÃO vazam.
        - Se `ProfessorTurma.disciplina_id IS NULL` (vínculo geral explícito na turma), autoriza os
          boletins daquela turma ativa.
        """
        stmt = (
            select(Estudante.id)
            .join(BoletimPeriodo, BoletimPeriodo.estudante_id == Estudante.id)
            .join(Turma, Turma.id == BoletimPeriodo.turma_id)
            .join(Escola, Escola.id == Turma.escola_id)
            .join(
                ProfessorTurma,
                ProfessorTurma.turma_id == BoletimPeriodo.turma_id,
            )
            .outerjoin(
                NotaDisciplina,
                NotaDisciplina.boletim_id == BoletimPeriodo.id,
            )
            .outerjoin(
                Disciplina,
                Disciplina.id == NotaDisciplina.disciplina_id,
            )
            .where(
                ProfessorTurma.professor_id == professor_id,
                Turma.ativo.is_(True),
                Escola.ativo.is_(True),
                Estudante.escola_id == Turma.escola_id,
                BoletimPeriodo.escola_id == Turma.escola_id,
                or_(
                    ProfessorTurma.disciplina_id.is_(None),
                    (
                        (NotaDisciplina.disciplina_id == ProfessorTurma.disciplina_id)
                        & (Disciplina.ativo.is_(True))
                    ),
                ),
            )
        )

        if escola_id_professor is not None:
            stmt = stmt.where(
                Turma.escola_id == escola_id_professor,
                Estudante.escola_id == escola_id_professor,
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
            stmt = stmt.where(
                NotaDisciplina.disciplina_id == disciplina_id,
                Disciplina.ativo.is_(True),
                or_(
                    ProfessorTurma.disciplina_id == disciplina_id,
                    ProfessorTurma.disciplina_id.is_(None),
                ),
            )

        return stmt.distinct()

    @staticmethod
    def list_by_professor(
        db: Session,
        professor_id: uuid.UUID,
        escola_id_professor: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Estudante]:
        """
        Lista apenas os estudantes que possuem registros nas combinações exatas de
        escola, turma e disciplina às quais o professor está efetivamente vinculado,
        aplicando paginação (`skip`/`limit`) sobre o conjunto já filtrado e distinto.
        """
        ids_subq = EstudanteRepository._build_professor_query(
            professor_id=professor_id,
            escola_id_professor=escola_id_professor,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            ano_letivo=ano_letivo,
            periodo_letivo=periodo_letivo,
        )
        stmt = (
            select(Estudante)
            .where(Estudante.id.in_(ids_subq))
            .order_by(Estudante.codigo_anonimo)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def count_by_professor(
        db: Session,
        professor_id: uuid.UUID,
        escola_id_professor: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> int:
        """Retorna a contagem total exata de estudantes distintos no escopo do professor."""
        ids_subq = EstudanteRepository._build_professor_query(
            professor_id=professor_id,
            escola_id_professor=escola_id_professor,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            ano_letivo=ano_letivo,
            periodo_letivo=periodo_letivo,
        ).subquery()
        stmt = select(func.count()).select_from(ids_subq)
        return int(db.execute(stmt).scalar_one())

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
