"""
Camada de acesso a dados (Repository) para o módulo de Previsões Preditivas (Fase 7).
"""

from datetime import datetime, timezone
from typing import Optional, Sequence
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.integrations.prediction.models import (
    CredencialIntegracaoPredicao,
    FaixaRisco,
    PrevisaoRisco,
    TipoPrevisao,
)


class PredictionRepository:
    """Consultas e persistência para credenciais técnicas e previsões append-only."""

    @staticmethod
    def create_credencial(
        db: Session,
        credencial: CredencialIntegracaoPredicao,
    ) -> CredencialIntegracaoPredicao:
        db.add(credencial)
        db.flush()
        return credencial

    @staticmethod
    def get_credencial_by_id(
        db: Session,
        credencial_id: uuid.UUID,
    ) -> Optional[CredencialIntegracaoPredicao]:
        stmt = select(CredencialIntegracaoPredicao).where(
            CredencialIntegracaoPredicao.id == credencial_id
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_credencial_by_hash(
        db: Session,
        hash_chave: str,
    ) -> Optional[CredencialIntegracaoPredicao]:
        stmt = select(CredencialIntegracaoPredicao).where(
            CredencialIntegracaoPredicao.hash_chave == hash_chave
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_credenciais(
        db: Session,
        escola_id: Optional[uuid.UUID] = None,
        apenas_ativas: Optional[bool] = None,
    ) -> list[CredencialIntegracaoPredicao]:
        stmt = select(CredencialIntegracaoPredicao)
        if escola_id is not None:
            stmt = stmt.where(CredencialIntegracaoPredicao.escola_id == escola_id)
        if apenas_ativas is True:
            stmt = stmt.where(CredencialIntegracaoPredicao.ativo.is_(True))
        elif apenas_ativas is False:
            stmt = stmt.where(CredencialIntegracaoPredicao.ativo.is_(False))
        stmt = stmt.order_by(desc(CredencialIntegracaoPredicao.criado_em))
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def registrar_uso_credencial(
        db: Session,
        credencial: CredencialIntegracaoPredicao,
    ) -> None:
        credencial.ultimo_uso_em = datetime.now(timezone.utc)
        db.add(credencial)

    @staticmethod
    def buscar_assinaturas_existentes(
        db: Session,
        assinaturas: Sequence[str],
    ) -> set[str]:
        if not assinaturas:
            return set()
        stmt = select(PrevisaoRisco.assinatura_idempotencia).where(
            PrevisaoRisco.assinatura_idempotencia.in_(list(assinaturas))
        )
        return set(db.execute(stmt).scalars().all())

    @staticmethod
    def add_all_previsoes(
        db: Session,
        previsoes: Sequence[PrevisaoRisco],
    ) -> list[PrevisaoRisco]:
        db.add_all(list(previsoes))
        db.flush()
        return list(previsoes)

    @staticmethod
    def get_previsao_by_id(
        db: Session,
        previsao_id: uuid.UUID,
    ) -> Optional[PrevisaoRisco]:
        stmt = (
            select(PrevisaoRisco)
            .options(
                selectinload(PrevisaoRisco.estudante),
                selectinload(PrevisaoRisco.turma),
            )
            .where(PrevisaoRisco.id == previsao_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_previsoes_by_ids(
        db: Session,
        ids: Sequence[uuid.UUID],
    ) -> list[PrevisaoRisco]:
        if not ids:
            return []
        stmt = (
            select(PrevisaoRisco)
            .options(
                selectinload(PrevisaoRisco.estudante),
                selectinload(PrevisaoRisco.turma),
            )
            .where(PrevisaoRisco.id.in_(list(ids)))
        )
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def list_previsoes_escopo(
        db: Session,
        escola_ids: Optional[Sequence[uuid.UUID]] = None,
        estudante_ids: Optional[Sequence[uuid.UUID]] = None,
        turma_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        tipo_previsao: Optional[TipoPrevisao] = None,
        faixa_risco: Optional[FaixaRisco] = None,
        modelo_nome: Optional[str] = None,
        modelo_versao: Optional[str] = None,
        limit: Optional[int] = None,
        skip: int = 0,
    ) -> list[PrevisaoRisco]:
        if escola_ids is not None and len(escola_ids) == 0:
            return []
        if estudante_ids is not None and len(estudante_ids) == 0:
            return []

        stmt = select(PrevisaoRisco).options(
            selectinload(PrevisaoRisco.estudante),
            selectinload(PrevisaoRisco.turma),
        )

        if escola_ids is not None:
            stmt = stmt.where(PrevisaoRisco.escola_id.in_(list(escola_ids)))
        if estudante_ids is not None:
            stmt = stmt.where(PrevisaoRisco.estudante_id.in_(list(estudante_ids)))
        if turma_id is not None:
            stmt = stmt.where(PrevisaoRisco.turma_id == turma_id)
        if ano_letivo is not None:
            stmt = stmt.where(PrevisaoRisco.ano_letivo == ano_letivo)
        if periodo_letivo is not None and periodo_letivo.strip():
            stmt = stmt.where(PrevisaoRisco.periodo_letivo == periodo_letivo.strip())
        if tipo_previsao is not None:
            stmt = stmt.where(PrevisaoRisco.tipo_previsao == tipo_previsao)
        if faixa_risco is not None:
            stmt = stmt.where(PrevisaoRisco.faixa_risco == faixa_risco)
        if modelo_nome is not None and modelo_nome.strip():
            stmt = stmt.where(PrevisaoRisco.modelo_nome == modelo_nome.strip())
        if modelo_versao is not None and modelo_versao.strip():
            stmt = stmt.where(PrevisaoRisco.modelo_versao == modelo_versao.strip())

        stmt = stmt.order_by(
            desc(PrevisaoRisco.gerado_em),
            desc(PrevisaoRisco.recebido_em),
            desc(PrevisaoRisco.criado_em),
        )
        if skip:
            stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(db.execute(stmt).scalars().all())
