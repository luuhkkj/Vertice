"""
Camada de serviço para regras de negócio de Atribuições (ProfessorTurma).
"""

from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import garantir_acesso_escola
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
    def criar_atribuicao(
        db: Session,
        dados: AtribuicaoCreate,
        usuario: Optional[Usuario] = None,
    ) -> ProfessorTurma:
        """
        Cria um vínculo entre professor, turma e disciplina após validar:
        1. Apenas `gestor` vinculado a escola pode gerenciar atribuições (admin e professor recebem 403).
        2. O usuário associado existe, está ativo e possui o papel `professor`.
        3. A turma existe, está ativa e pertence à escola do gestor.
        4. A disciplina (quando informada) existe e está ativa.
        5. Não existe vínculo duplicado para a mesma combinação (inclusive quando disciplina_id é NULL).
        """
        if usuario is not None:
            if usuario.papel != PapelUsuario.GESTOR:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: apenas gestores escolares podem gerenciar atribuições de turmas.",
                )
            if usuario.escola_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: gestor não possui uma unidade escolar vinculada.",
                )

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

        if usuario is not None:
            garantir_acesso_escola(usuario, turma.escola_id)

        if professor.escola_id is not None and professor.escola_id != turma.escola_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Professor vinculado a outra unidade escolar não pode ser associado a esta turma.",
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
        try:
            return AtribuicaoRepository.create(db, nova_atribuicao)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade: esta associação entre professor, turma e disciplina já existe.",
            ) from exc

    @staticmethod
    def listar_atribuicoes(
        db: Session, usuario: Usuario, skip: int = 0, limit: int = 100
    ) -> list[ProfessorTurma]:
        if usuario.papel == PapelUsuario.ADMINISTRADOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: perfil administrativo técnico não consulta atribuições pedagógicas.",
            )
        if usuario.papel == PapelUsuario.GESTOR:
            if usuario.escola_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: gestor não possui uma unidade escolar vinculada.",
                )
            return AtribuicaoRepository.list_by_escola(
                db, escola_id=usuario.escola_id, skip=skip, limit=limit
            )
        return AtribuicaoRepository.list_by_professor(
            db, professor_id=usuario.id, skip=skip, limit=limit
        )

    @staticmethod
    def remover_atribuicao(
        db: Session,
        atribuicao_id: uuid.UUID,
        usuario: Optional[Usuario] = None,
    ) -> None:
        if usuario is not None:
            if usuario.papel != PapelUsuario.GESTOR:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: apenas gestores escolares podem remover atribuições de turmas.",
                )
            if usuario.escola_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: gestor não possui uma unidade escolar vinculada.",
                )

        atribuicao = AtribuicaoRepository.get_by_id(db, atribuicao_id)
        if atribuicao is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Atribuição não encontrada.",
            )
        if usuario is not None:
            turma = TurmaRepository.get_by_id(db, atribuicao.turma_id)
            if turma is None or turma.escola_id != usuario.escola_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: atribuição pertence a outra unidade escolar.",
                )

        AtribuicaoRepository.delete(db, atribuicao)
