"""
Camada de serviço para regras de negócio de Atribuições (ProfessorTurma).
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.atribuicoes.repository import AtribuicaoRepository
from app.modules.atribuicoes.schemas import AtribuicaoCreate
from app.modules.disciplinas.repository import DisciplinaRepository
from app.modules.turmas.repository import TurmaRepository
from app.modules.usuarios.models import PapelUsuario, Usuario
from app.modules.usuarios.repository import UsuarioRepository


class AtribuicaoService:
    """Regras de negócio para vínculo entre professores, turmas e disciplinas."""

    @staticmethod
    def criar_atribuicao(db: Session, dados: AtribuicaoCreate) -> ProfessorTurma:
        """
        Cria um vínculo entre professor, turma e disciplina após validar:
        1. O usuário existe, está ativo e possui o papel `professor`.
        2. A turma existe e está ativa.
        3. A disciplina (quando informada) existe e está ativa.
        4. Não existe vínculo duplicado para a mesma combinação.
        """
        professor = UsuarioRepository.get_by_id(db, dados.professor_id)
        if professor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Professor informado não encontrado.",
            )
        if not professor.ativo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível associar um usuário inativo a uma turma.",
            )
        if professor.papel != PapelUsuario.PROFESSOR:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O usuário associado deve possuir o papel de professor.",
            )

        turma = TurmaRepository.get_by_id(db, dados.turma_id)
        if turma is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Turma informada não encontrada.",
            )
        if not turma.ativo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível associar professor a uma turma inativa.",
            )

        if dados.disciplina_id is not None:
            disciplina = DisciplinaRepository.get_by_id(db, dados.disciplina_id)
            if disciplina is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Disciplina informada não encontrada.",
                )
            if not disciplina.ativo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Não é possível associar uma disciplina inativa.",
                )

        existente = AtribuicaoRepository.get_by_composicao(
            db=db,
            professor_id=dados.professor_id,
            turma_id=dados.turma_id,
            disciplina_id=dados.disciplina_id,
        )
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta associação entre professor, turma e disciplina já está cadastrada.",
            )

        nova_atribuicao = ProfessorTurma(
            professor_id=dados.professor_id,
            turma_id=dados.turma_id,
            disciplina_id=dados.disciplina_id,
        )
        return AtribuicaoRepository.create(db, nova_atribuicao)

    @staticmethod
    def listar_atribuicoes(
        db: Session, usuario: Usuario, skip: int = 0, limit: int = 100
    ) -> list[ProfessorTurma]:
        if usuario.papel in (PapelUsuario.ADMINISTRADOR, PapelUsuario.GESTOR):
            return AtribuicaoRepository.list_all(db, skip=skip, limit=limit)
        return AtribuicaoRepository.list_by_professor(
            db, professor_id=usuario.id, skip=skip, limit=limit
        )

    @staticmethod
    def remover_atribuicao(db: Session, atribuicao_id: uuid.UUID) -> None:
        atribuicao = AtribuicaoRepository.get_by_id(db, atribuicao_id)
        if atribuicao is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Atribuição não encontrada.",
            )
        AtribuicaoRepository.delete(db, atribuicao)

