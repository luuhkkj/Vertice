"""
Camada de serviço para regras de negócio de Escolas.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.escolas.models import Escola
from app.modules.escolas.repository import EscolaRepository
from app.modules.escolas.schemas import EscolaCreate, EscolaUpdate


class EscolaService:
    """Regras de negócio para cadastro e consulta de escolas."""

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
        return EscolaRepository.create(db, nova_escola)

    @staticmethod
    def obter_por_id(db: Session, escola_id: uuid.UUID) -> Escola:
        escola = EscolaRepository.get_by_id(db, escola_id)
        if escola is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escola não encontrada.",
            )
        return escola

    @staticmethod
    def listar_escolas(db: Session, skip: int = 0, limit: int = 100) -> list[Escola]:
        return EscolaRepository.list_all(db, skip=skip, limit=limit)

    @staticmethod
    def atualizar_escola(
        db: Session, escola_id: uuid.UUID, dados: EscolaUpdate
    ) -> Escola:
        escola = EscolaService.obter_por_id(db, escola_id)

        if dados.codigo is not None and dados.codigo != escola.codigo:
            outro = EscolaRepository.get_by_codigo(db, dados.codigo)
            if outro is not None and outro.id != escola.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Já existe outra escola com este código.",
                )
            escola.codigo = dados.codigo

        if dados.nome is not None:
            escola.nome = dados.nome.strip()

        if dados.ativo is not None:
            escola.ativo = dados.ativo

        return EscolaRepository.update(db, escola)

