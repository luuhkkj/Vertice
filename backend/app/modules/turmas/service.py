"""
Camada de serviço para regras de negócio e controle de escopo de Turmas.
"""

from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import garantir_acesso_escola, garantir_acesso_turma
from app.modules.escolas.repository import EscolaRepository
from app.modules.turmas.models import Turma
from app.modules.turmas.repository import TurmaRepository
from app.modules.turmas.schemas import TurmaCreate, TurmaUpdate
from app.modules.usuarios.models import PapelUsuario, Usuario


class TurmaService:
    """Regras de negócio de criação, listagem filtrada por papel/escola e acesso a turmas."""

    @staticmethod
    def criar_turma(
        db: Session,
        dados: TurmaCreate,
        usuario: Optional[Usuario] = None,
    ) -> Turma:
        if usuario is not None:
            garantir_acesso_escola(usuario, dados.escola_id)

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
        try:
            return TurmaRepository.create(db, nova_turma)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade: turma duplicada para esta escola e ano letivo.",
            ) from exc

    @staticmethod
    def obter_turma_autorizada(
        db: Session, turma_id: uuid.UUID, usuario: Usuario
    ) -> Turma:
        """
        Obtém uma turma verificando primeiro se o usuário tem escopo autorizado sobre ela.
        """
        turma = TurmaRepository.get_by_id(db, turma_id)
        if turma is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Turma não encontrada.",
            )

        garantir_acesso_turma(
            db=db,
            usuario=usuario,
            turma_id=turma.id,
            escola_id=turma.escola_id,
        )
        return turma

    @staticmethod
    def listar_turmas_por_escopo(
        db: Session, usuario: Usuario, skip: int = 0, limit: int = 100
    ) -> list[Turma]:
        """
        Retorna as turmas conforme o escopo do usuário:
        - Administrador: todas as turmas.
        - Gestor vinculado a uma escola: apenas as turmas de sua escola (ou todas se não tiver escola restrita).
        - Professor: exclusivamente as turmas às quais está associado.
        """
        if usuario.papel == PapelUsuario.ADMINISTRADOR:
            return TurmaRepository.list_all(db, skip=skip, limit=limit)
        if usuario.papel == PapelUsuario.GESTOR:
            if usuario.escola_id is not None:
                return TurmaRepository.list_by_escola(
                    db, escola_id=usuario.escola_id, skip=skip, limit=limit
                )
            return TurmaRepository.list_all(db, skip=skip, limit=limit)
        return TurmaRepository.list_by_professor(
            db, professor_id=usuario.id, skip=skip, limit=limit
        )

    @staticmethod
    def atualizar_turma(
        db: Session,
        turma_id: uuid.UUID,
        dados: TurmaUpdate,
        usuario: Optional[Usuario] = None,
    ) -> Turma:
        turma = TurmaRepository.get_by_id(db, turma_id)
        if turma is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Turma não encontrada.",
            )

        if usuario is not None:
            garantir_acesso_turma(
                db=db,
                usuario=usuario,
                turma_id=turma.id,
                escola_id=turma.escola_id,
            )

        campos = dados.model_fields_set
        novo_nome = dados.nome.strip() if "nome" in campos and dados.nome is not None else turma.nome
        nova_serie = dados.serie.strip() if "serie" in campos and dados.serie is not None else turma.serie
        novo_turno = dados.turno.strip() if "turno" in campos and dados.turno is not None else turma.turno
        novo_ano = dados.ano_letivo if "ano_letivo" in campos and dados.ano_letivo is not None else turma.ano_letivo

        if (novo_nome, nova_serie, novo_turno, novo_ano) != (
            turma.nome,
            turma.serie,
            turma.turno,
            turma.ano_letivo,
        ):
            conflito = TurmaRepository.get_by_chave_unica(
                db=db,
                escola_id=turma.escola_id,
                nome=novo_nome,
                serie=nova_serie,
                turno=novo_turno,
                ano_letivo=novo_ano,
            )
            if conflito is not None and conflito.id != turma.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Já existe outra turma com este nome, série, turno e ano letivo nesta escola.",
                )

        turma.nome = novo_nome
        turma.serie = nova_serie
        turma.turno = novo_turno
        turma.ano_letivo = novo_ano

        if "ativo" in campos and dados.ativo is not None:
            turma.ativo = dados.ativo

        try:
            return TurmaRepository.update(db, turma)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao atualizar turma.",
            ) from exc
