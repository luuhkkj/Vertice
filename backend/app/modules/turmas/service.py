"""
Camada de serviço para regras de negócio e controle de escopo de Turmas.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import garantir_acesso_turma
from app.modules.escolas.repository import EscolaRepository
from app.modules.turmas.models import Turma
from app.modules.turmas.repository import TurmaRepository
from app.modules.turmas.schemas import TurmaCreate, TurmaUpdate
from app.modules.usuarios.models import PapelUsuario, Usuario


class TurmaService:
    """Regras de negócio de criação, listagem filtrada por papel e acesso a turmas."""

    @staticmethod
    def criar_turma(db: Session, dados: TurmaCreate) -> Turma:
        escola = EscolaRepository.get_by_id(db, dados.escola_id)
        if escola is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escola informada não encontrada.",
            )
        if not escola.ativo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível cadastrar turma em uma escola inativa.",
            )

        existente = TurmaRepository.get_by_chave_unica(
            db=db,
            escola_id=dados.escola_id,
            nome=dados.nome,
            serie=dados.serie,
            turno=dados.turno,
            ano_letivo=dados.ano_letivo,
        )
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma turma com este nome, série, turno e ano letivo nesta escola.",
            )

        nova_turma = Turma(
            nome=dados.nome.strip(),
            serie=dados.serie.strip(),
            turno=dados.turno.strip(),
            ano_letivo=dados.ano_letivo,
            escola_id=dados.escola_id,
            ativo=dados.ativo,
        )
        return TurmaRepository.create(db, nova_turma)

    @staticmethod
    def obter_turma_autorizada(
        db: Session, turma_id: uuid.UUID, usuario: Usuario
    ) -> Turma:
        """
        Obtém uma turma verificando primeiro se o usuário (ex: professor) tem vínculo com ela.
        """
        turma = TurmaRepository.get_by_id(db, turma_id)
        if turma is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Turma não encontrada.",
            )

        garantir_acesso_turma(db=db, usuario=usuario, turma_id=turma.id)
        return turma

    @staticmethod
    def listar_turmas_por_escopo(
        db: Session, usuario: Usuario, skip: int = 0, limit: int = 100
    ) -> list[Turma]:
        """
        Retorna todas as turmas para administradores/gestores, ou apenas as turmas
        vinculadas para professores.
        """
        if usuario.papel in (PapelUsuario.ADMINISTRADOR, PapelUsuario.GESTOR):
            return TurmaRepository.list_all(db, skip=skip, limit=limit)
        return TurmaRepository.list_by_professor(
            db, professor_id=usuario.id, skip=skip, limit=limit
        )

    @staticmethod
    def atualizar_turma(
        db: Session, turma_id: uuid.UUID, dados: TurmaUpdate
    ) -> Turma:
        turma = TurmaRepository.get_by_id(db, turma_id)
        if turma is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Turma não encontrada.",
            )

        if dados.nome is not None:
            turma.nome = dados.nome.strip()
        if dados.serie is not None:
            turma.serie = dados.serie.strip()
        if dados.turno is not None:
            turma.turno = dados.turno.strip()
        if dados.ano_letivo is not None:
            turma.ano_letivo = dados.ano_letivo
        if dados.ativo is not None:
            turma.ativo = dados.ativo

        return TurmaRepository.update(db, turma)

