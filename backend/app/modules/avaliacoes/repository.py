"""
Repositório de acesso a dados para Avaliações, Questões e Respostas (Bloco B — Fase 4).
Todas as consultas aplicam filtragem estrita de escopo (escola para gestor,
vínculo `ProfessorTurma` com turma + disciplina para professor).
"""

from typing import Optional
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.avaliacoes.models import (
    Avaliacao,
    QuestaoAvaliacao,
    RespostaAvaliacao,
)
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import BoletimPeriodo
from app.modules.turmas.models import Turma


class AvaliacaoRepository:
    """Consultas e persistência para Avaliacao, QuestaoAvaliacao e RespostaAvaliacao."""

    @staticmethod
    def get_by_id(
        db: Session, avaliacao_id: uuid.UUID
    ) -> Optional[Avaliacao]:
        stmt = (
            select(Avaliacao)
            .options(
                selectinload(Avaliacao.turma),
                selectinload(Avaliacao.disciplina),
                selectinload(Avaliacao.questoes),
            )
            .where(Avaliacao.id == avaliacao_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_chave(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: uuid.UUID,
        disciplina_id: uuid.UUID,
        codigo: str,
    ) -> Optional[Avaliacao]:
        stmt = (
            select(Avaliacao)
            .options(
                selectinload(Avaliacao.turma),
                selectinload(Avaliacao.disciplina),
                selectinload(Avaliacao.questoes),
            )
            .where(
                Avaliacao.escola_id == escola_id,
                Avaliacao.turma_id == turma_id,
                Avaliacao.disciplina_id == disciplina_id,
                func.lower(Avaliacao.codigo) == codigo.strip().lower(),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_escola(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        periodo_letivo: Optional[str] = None,
        apenas_ativas: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Avaliacao]:
        stmt = (
            select(Avaliacao)
            .join(Turma, Turma.id == Avaliacao.turma_id)
            .join(Disciplina, Disciplina.id == Avaliacao.disciplina_id)
            .options(
                selectinload(Avaliacao.turma),
                selectinload(Avaliacao.disciplina),
            )
            .where(
                Avaliacao.escola_id == escola_id,
                Turma.escola_id == escola_id,
                Turma.ativo.is_(True),
                Disciplina.ativo.is_(True),
            )
        )
        if apenas_ativas:
            stmt = stmt.where(Avaliacao.ativo.is_(True))
        if turma_id is not None:
            stmt = stmt.where(Avaliacao.turma_id == turma_id)
        if disciplina_id is not None:
            stmt = stmt.where(Avaliacao.disciplina_id == disciplina_id)
        if periodo_letivo is not None:
            stmt = stmt.where(
                Avaliacao.periodo_letivo == periodo_letivo.strip()
            )
        stmt = (
            stmt.order_by(Avaliacao.data_avaliacao.desc(), Avaliacao.codigo)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_by_professor(
        db: Session,
        professor_id: uuid.UUID,
        escola_id_professor: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        periodo_letivo: Optional[str] = None,
        apenas_ativas: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Avaliacao]:
        subq_ids = (
            select(Avaliacao.id)
            .join(Turma, Turma.id == Avaliacao.turma_id)
            .join(Escola, Escola.id == Turma.escola_id)
            .join(Disciplina, Disciplina.id == Avaliacao.disciplina_id)
            .join(
                ProfessorTurma,
                ProfessorTurma.turma_id == Avaliacao.turma_id,
            )
            .where(
                ProfessorTurma.professor_id == professor_id,
                Avaliacao.escola_id == Turma.escola_id,
                Turma.ativo.is_(True),
                Escola.ativo.is_(True),
                Disciplina.ativo.is_(True),
                or_(
                    ProfessorTurma.disciplina_id.is_(None),
                    ProfessorTurma.disciplina_id == Avaliacao.disciplina_id,
                ),
            )
        )
        if escola_id_professor is not None:
            subq_ids = subq_ids.where(
                Avaliacao.escola_id == escola_id_professor,
                Turma.escola_id == escola_id_professor,
            )
        if apenas_ativas:
            subq_ids = subq_ids.where(Avaliacao.ativo.is_(True))
        if turma_id is not None:
            subq_ids = subq_ids.where(Avaliacao.turma_id == turma_id)
        if disciplina_id is not None:
            subq_ids = subq_ids.where(Avaliacao.disciplina_id == disciplina_id)
        if periodo_letivo is not None:
            subq_ids = subq_ids.where(
                Avaliacao.periodo_letivo == periodo_letivo.strip()
            )

        stmt = (
            select(Avaliacao)
            .options(
                selectinload(Avaliacao.turma),
                selectinload(Avaliacao.disciplina),
            )
            .where(Avaliacao.id.in_(subq_ids.distinct()))
            .order_by(Avaliacao.data_avaliacao.desc(), Avaliacao.codigo)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_questao_by_id(
        db: Session, questao_id: uuid.UUID
    ) -> Optional[QuestaoAvaliacao]:
        stmt = (
            select(QuestaoAvaliacao)
            .options(
                selectinload(QuestaoAvaliacao.avaliacao).selectinload(
                    Avaliacao.turma
                ),
                selectinload(QuestaoAvaliacao.avaliacao).selectinload(
                    Avaliacao.disciplina
                ),
            )
            .where(QuestaoAvaliacao.id == questao_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_questao_by_codigo(
        db: Session,
        avaliacao_id: uuid.UUID,
        codigo_questao: str,
    ) -> Optional[QuestaoAvaliacao]:
        stmt = select(QuestaoAvaliacao).where(
            QuestaoAvaliacao.avaliacao_id == avaliacao_id,
            func.lower(QuestaoAvaliacao.codigo_questao)
            == codigo_questao.strip().lower(),
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_questoes_by_avaliacao(
        db: Session, avaliacao_id: uuid.UUID
    ) -> list[QuestaoAvaliacao]:
        stmt = (
            select(QuestaoAvaliacao)
            .where(QuestaoAvaliacao.avaliacao_id == avaliacao_id)
            .order_by(QuestaoAvaliacao.codigo_questao)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_resposta_by_questao_e_estudante(
        db: Session,
        questao_id: uuid.UUID,
        estudante_id: uuid.UUID,
    ) -> Optional[RespostaAvaliacao]:
        stmt = (
            select(RespostaAvaliacao)
            .options(
                selectinload(RespostaAvaliacao.questao),
                selectinload(RespostaAvaliacao.estudante),
            )
            .where(
                RespostaAvaliacao.questao_id == questao_id,
                RespostaAvaliacao.estudante_id == estudante_id,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_respostas_by_avaliacao(
        db: Session,
        avaliacao_id: uuid.UUID,
        questao_id: Optional[uuid.UUID] = None,
        estudante_id: Optional[uuid.UUID] = None,
    ) -> list[RespostaAvaliacao]:
        stmt = (
            select(RespostaAvaliacao)
            .join(
                QuestaoAvaliacao,
                QuestaoAvaliacao.id == RespostaAvaliacao.questao_id,
            )
            .options(
                selectinload(RespostaAvaliacao.questao),
                selectinload(RespostaAvaliacao.estudante),
            )
            .where(QuestaoAvaliacao.avaliacao_id == avaliacao_id)
        )
        if questao_id is not None:
            stmt = stmt.where(RespostaAvaliacao.questao_id == questao_id)
        if estudante_id is not None:
            stmt = stmt.where(RespostaAvaliacao.estudante_id == estudante_id)
        stmt = stmt.order_by(
            QuestaoAvaliacao.codigo_questao, RespostaAvaliacao.criado_em
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def estudante_vinculado_a_turma(
        db: Session,
        estudante_id: uuid.UUID,
        turma_id: uuid.UUID,
        escola_id: uuid.UUID,
    ) -> bool:
        """
        Verifica se o estudante anonimizado já possui histórico/boletim vinculado
        àquela turma e escola nos dados escolares existentes.
        """
        stmt = (
            select(BoletimPeriodo.id)
            .where(
                BoletimPeriodo.estudante_id == estudante_id,
                BoletimPeriodo.turma_id == turma_id,
                BoletimPeriodo.escola_id == escola_id,
            )
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none() is not None

