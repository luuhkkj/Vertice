"""
Repositório de acesso a dados para Participação, Atividades e Entregas (Bloco C — Fase 4).
"""

from typing import Optional
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    SituacaoFinalPeriodo,
)
from app.modules.participacao.models import Atividade, EntregaAtividade
from app.modules.turmas.models import Turma


class ParticipacaoRepository:
    """Consultas e persistência para Atividade e EntregaAtividade."""

    @staticmethod
    def get_atividade_by_id(
        db: Session, atividade_id: uuid.UUID
    ) -> Optional[Atividade]:
        stmt = (
            select(Atividade)
            .options(
                selectinload(Atividade.turma),
                selectinload(Atividade.disciplina),
                selectinload(Atividade.entregas).selectinload(
                    EntregaAtividade.estudante
                ),
            )
            .where(Atividade.id == atividade_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_atividade_by_chave(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: uuid.UUID,
        disciplina_id: uuid.UUID,
        codigo: str,
    ) -> Optional[Atividade]:
        stmt = (
            select(Atividade)
            .options(
                selectinload(Atividade.turma),
                selectinload(Atividade.disciplina),
            )
            .where(
                Atividade.escola_id == escola_id,
                Atividade.turma_id == turma_id,
                Atividade.disciplina_id == disciplina_id,
                func.lower(Atividade.codigo) == codigo.strip().lower(),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_atividades_by_escola(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        periodo_letivo: Optional[str] = None,
        apenas_ativas: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Atividade]:
        stmt = (
            select(Atividade)
            .join(Turma, Turma.id == Atividade.turma_id)
            .join(Disciplina, Disciplina.id == Atividade.disciplina_id)
            .options(
                selectinload(Atividade.turma),
                selectinload(Atividade.disciplina),
            )
            .where(
                Atividade.escola_id == escola_id,
                Turma.escola_id == escola_id,
                Turma.ativo.is_(True),
                Disciplina.ativo.is_(True),
            )
        )
        if apenas_ativas:
            stmt = stmt.where(Atividade.ativo.is_(True))
        if turma_id is not None:
            stmt = stmt.where(Atividade.turma_id == turma_id)
        if disciplina_id is not None:
            stmt = stmt.where(Atividade.disciplina_id == disciplina_id)
        if periodo_letivo is not None:
            stmt = stmt.where(
                Atividade.periodo_letivo == periodo_letivo.strip()
            )
        stmt = (
            stmt.order_by(Atividade.data_limite.desc(), Atividade.codigo)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_atividades_by_professor(
        db: Session,
        professor_id: uuid.UUID,
        escola_id_professor: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        periodo_letivo: Optional[str] = None,
        apenas_ativas: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Atividade]:
        subq_ids = (
            select(Atividade.id)
            .join(Turma, Turma.id == Atividade.turma_id)
            .join(Escola, Escola.id == Turma.escola_id)
            .join(Disciplina, Disciplina.id == Atividade.disciplina_id)
            .join(
                ProfessorTurma,
                ProfessorTurma.turma_id == Atividade.turma_id,
            )
            .where(
                ProfessorTurma.professor_id == professor_id,
                Atividade.escola_id == Turma.escola_id,
                Turma.ativo.is_(True),
                Escola.ativo.is_(True),
                Disciplina.ativo.is_(True),
                or_(
                    ProfessorTurma.disciplina_id.is_(None),
                    ProfessorTurma.disciplina_id == Atividade.disciplina_id,
                ),
            )
        )
        if escola_id_professor is not None:
            subq_ids = subq_ids.where(
                Atividade.escola_id == escola_id_professor,
                Turma.escola_id == escola_id_professor,
            )
        if apenas_ativas:
            subq_ids = subq_ids.where(Atividade.ativo.is_(True))
        if turma_id is not None:
            subq_ids = subq_ids.where(Atividade.turma_id == turma_id)
        if disciplina_id is not None:
            subq_ids = subq_ids.where(Atividade.disciplina_id == disciplina_id)
        if periodo_letivo is not None:
            subq_ids = subq_ids.where(
                Atividade.periodo_letivo == periodo_letivo.strip()
            )

        stmt = (
            select(Atividade)
            .options(
                selectinload(Atividade.turma),
                selectinload(Atividade.disciplina),
            )
            .where(Atividade.id.in_(subq_ids.distinct()))
            .order_by(Atividade.data_limite.desc(), Atividade.codigo)
            .offset(skip)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def get_entrega_by_id(
        db: Session, entrega_id: uuid.UUID
    ) -> Optional[EntregaAtividade]:
        stmt = (
            select(EntregaAtividade)
            .options(
                selectinload(EntregaAtividade.atividade).selectinload(
                    Atividade.turma
                ),
                selectinload(EntregaAtividade.atividade).selectinload(
                    Atividade.disciplina
                ),
                selectinload(EntregaAtividade.estudante),
            )
            .where(EntregaAtividade.id == entrega_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_entrega_by_atividade_e_estudante(
        db: Session,
        atividade_id: uuid.UUID,
        estudante_id: uuid.UUID,
    ) -> Optional[EntregaAtividade]:
        stmt = (
            select(EntregaAtividade)
            .options(
                selectinload(EntregaAtividade.atividade),
                selectinload(EntregaAtividade.estudante),
            )
            .where(
                EntregaAtividade.atividade_id == atividade_id,
                EntregaAtividade.estudante_id == estudante_id,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_entregas_by_atividade(
        db: Session,
        atividade_id: uuid.UUID,
        estudante_id: Optional[uuid.UUID] = None,
    ) -> list[EntregaAtividade]:
        stmt = (
            select(EntregaAtividade)
            .join(Estudante, Estudante.id == EntregaAtividade.estudante_id)
            .options(
                selectinload(EntregaAtividade.estudante),
                selectinload(EntregaAtividade.atividade),
            )
            .where(EntregaAtividade.atividade_id == atividade_id)
        )
        if estudante_id is not None:
            stmt = stmt.where(EntregaAtividade.estudante_id == estudante_id)
        stmt = stmt.order_by(Estudante.codigo_anonimo)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_estudantes_elegiveis_turma(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: uuid.UUID,
        periodo_letivo: Optional[str] = None,
        ano_letivo: Optional[int] = None,
    ) -> list[Estudante]:
        """
        Retorna os estudantes ativos elegíveis para entregas esperadas de uma turma.
        Regras de integridade histórica:
        - Quando houver registros em `boletins_periodo` para o `periodo_letivo` e
          `ano_letivo` da atividade, utiliza estritamente esse vínculo de período,
          evitando puxar retroativamente estudantes que só entraram em períodos futuros.
        - Quando o período letivo ainda não tiver boletins lançados (atividade em andamento),
          recorre aos estudantes da turma no mesmo `ano_letivo` (ou na turma em geral
          se não houver distinção de ano), excluindo quem já foi marcado como
          `Evadido` em período distinto ou já possui boletim no período alvo em outra turma.
        - Limitação conhecida: `boletins_periodo` registra granularidade por ano/período
          letivo e não data exata de matrícula/transferência no meio do bimestre.
        - Nunca cria novos estudantes.
        """
        ano_ref = ano_letivo
        if ano_ref is None:
            ano_ref = db.execute(
                select(Turma.ano_letivo).where(Turma.id == turma_id)
            ).scalar_one_or_none()

        periodo_limpo = periodo_letivo.strip() if periodo_letivo else None

        if periodo_limpo:
            filtros_periodo = [
                Estudante.escola_id == escola_id,
                Estudante.ativo.is_(True),
                BoletimPeriodo.escola_id == escola_id,
                BoletimPeriodo.turma_id == turma_id,
                BoletimPeriodo.periodo_letivo == periodo_limpo,
            ]
            if ano_ref is not None:
                filtros_periodo.append(BoletimPeriodo.ano_letivo == ano_ref)

            ids_periodo = list(
                db.execute(
                    select(Estudante.id)
                    .join(
                        BoletimPeriodo,
                        BoletimPeriodo.estudante_id == Estudante.id,
                    )
                    .where(*filtros_periodo)
                    .distinct()
                )
                .scalars()
                .all()
            )
            if ids_periodo:
                stmt_periodo = (
                    select(Estudante)
                    .where(Estudante.id.in_(ids_periodo))
                    .order_by(Estudante.codigo_anonimo)
                )
                return list(db.execute(stmt_periodo).scalars().all())

        # Fallback para turma quando o período específico ainda não possui boletins:
        filtros_ano = [
            Estudante.escola_id == escola_id,
            Estudante.ativo.is_(True),
            BoletimPeriodo.escola_id == escola_id,
            BoletimPeriodo.turma_id == turma_id,
        ]
        if ano_ref is not None:
            ids_ano = list(
                db.execute(
                    select(Estudante.id)
                    .join(
                        BoletimPeriodo,
                        BoletimPeriodo.estudante_id == Estudante.id,
                    )
                    .where(*filtros_ano, BoletimPeriodo.ano_letivo == ano_ref)
                    .distinct()
                )
                .scalars()
                .all()
            )
        else:
            ids_ano = []

        if not ids_ano:
            ids_ano = list(
                db.execute(
                    select(Estudante.id)
                    .join(
                        BoletimPeriodo,
                        BoletimPeriodo.estudante_id == Estudante.id,
                    )
                    .where(*filtros_ano)
                    .distinct()
                )
                .scalars()
                .all()
            )

        if not ids_ano:
            return []

        ids_excluir: set[uuid.UUID] = set()
        if periodo_limpo:
            # Exclui estudantes que já aparecem em outra turma no mesmo período/ano
            filtros_outra_turma = [
                BoletimPeriodo.escola_id == escola_id,
                BoletimPeriodo.turma_id != turma_id,
                BoletimPeriodo.periodo_letivo == periodo_limpo,
                BoletimPeriodo.estudante_id.in_(ids_ano),
            ]
            if ano_ref is not None:
                filtros_outra_turma.append(BoletimPeriodo.ano_letivo == ano_ref)
            ids_excluir.update(
                db.execute(
                    select(BoletimPeriodo.estudante_id)
                    .where(*filtros_outra_turma)
                    .distinct()
                )
                .scalars()
                .all()
            )

            # Exclui estudantes já marcados como EVADIDO na turma/ano em período distinto
            filtros_evadido = [
                BoletimPeriodo.escola_id == escola_id,
                BoletimPeriodo.turma_id == turma_id,
                BoletimPeriodo.periodo_letivo != periodo_limpo,
                BoletimPeriodo.situacao_final == SituacaoFinalPeriodo.EVADIDO,
                BoletimPeriodo.estudante_id.in_(ids_ano),
            ]
            if ano_ref is not None:
                filtros_evadido.append(BoletimPeriodo.ano_letivo == ano_ref)
            ids_excluir.update(
                db.execute(
                    select(BoletimPeriodo.estudante_id)
                    .where(*filtros_evadido)
                    .distinct()
                )
                .scalars()
                .all()
            )

        ids_finais = [eid for eid in ids_ano if eid not in ids_excluir]
        if not ids_finais:
            return []

        stmt = (
            select(Estudante)
            .where(Estudante.id.in_(ids_finais))
            .order_by(Estudante.codigo_anonimo)
        )
        return list(db.execute(stmt).scalars().all())

