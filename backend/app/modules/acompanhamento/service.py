"""
Serviço de negócio para o módulo de Acompanhamento Pedagógico (Fase 4).
Garante:
- Identificação do usuário responsável exclusivamente pela sessão autenticada.
- Validação de estudante e/ou turma no escopo autorizado do usuário (gestor limitado à
  própria escola; professor limitado às turmas e disciplinas em que leciona).
- Preservação integral do histórico de edições (`historico_alteracoes`), impedindo que
  uma atualização apague silenciosamente o conteúdo anterior.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import (
    garantir_escopo_importacao_usuario,
    garantir_escopo_pedagogico_turma_disciplina,
)
from app.modules.acompanhamento.models import (
    AcompanhamentoPedagogico,
    OrigemAcompanhamento,
)
from app.modules.acompanhamento.repository import AcompanhamentoRepository
from app.modules.acompanhamento.schemas import (
    AcompanhamentoCreate,
    AcompanhamentoResponse,
    AcompanhamentoUpdate,
)
from app.modules.estudantes.models import BoletimPeriodo, Estudante
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.estudantes.service import EstudanteService
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario


class AcompanhamentoService:
    """Regras de negócio de criação, consulta, listagem e atualização auditada de acompanhamentos."""

    @staticmethod
    def _serializar(ac: AcompanhamentoPedagogico) -> AcompanhamentoResponse:
        return AcompanhamentoResponse(
            id=ac.id,
            escola_id=ac.escola_id,
            usuario_id=ac.usuario_id,
            usuario_nome=ac.usuario.nome if ac.usuario else None,
            estudante_id=ac.estudante_id,
            codigo_anonimo=(
                ac.estudante.codigo_anonimo if ac.estudante else None
            ),
            turma_id=ac.turma_id,
            turma_nome=ac.turma.nome if ac.turma else None,
            disciplina_id=ac.disciplina_id,
            disciplina_codigo=(
                ac.disciplina.codigo if ac.disciplina else None
            ),
            origem=ac.origem,
            tipo_acao=ac.tipo_acao,
            descricao=ac.descricao,
            historico_alteracoes=list(ac.historico_alteracoes or []),
            ativo=ac.ativo,
            data_registro=ac.data_registro,
            atualizado_em=ac.atualizado_em,
        )

    @staticmethod
    def _resolver_e_validar_escopo_alvo(
        db: Session,
        usuario: Usuario,
        estudante_id: Optional[uuid.UUID],
        codigo_anonimo: Optional[str],
        turma_id: Optional[uuid.UUID],
        disciplina_id: Optional[uuid.UUID],
    ) -> tuple[uuid.UUID, Optional[Estudante], Optional[Turma]]:
        """
        Valida o estudante e/ou a turma informados contra o escopo autorizado do usuário
        e retorna `(escola_id, estudante, turma)`.
        """
        garantir_escopo_importacao_usuario(usuario)

        turma_obj: Optional[Turma] = None
        if turma_id is not None:
            turma_obj, _ = garantir_escopo_pedagogico_turma_disciplina(
                db=db,
                usuario=usuario,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
            )

        estudante_obj: Optional[Estudante] = None
        if estudante_id is not None or (
            codigo_anonimo and codigo_anonimo.strip()
        ):
            if estudante_id is not None:
                estudante_obj = EstudanteRepository.get_by_id(db, estudante_id)
            else:
                assert codigo_anonimo is not None
                cod_limpo = codigo_anonimo.strip()
                if turma_obj is not None:
                    estudante_obj = EstudanteRepository.get_by_escola_e_codigo(
                        db, turma_obj.escola_id, cod_limpo
                    )
                elif usuario.escola_id is not None:
                    estudante_obj = EstudanteRepository.get_by_escola_e_codigo(
                        db, usuario.escola_id, cod_limpo
                    )
                else:
                    stmt_est = select(Estudante).where(
                        Estudante.codigo_anonimo == cod_limpo,
                        Estudante.ativo.is_(True),
                    )
                    cands = list(db.execute(stmt_est).scalars().all())
                    if len(cands) == 1:
                        estudante_obj = cands[0]

            if estudante_obj is None or not estudante_obj.ativo:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Estudante não encontrado.",
                )

            # Verifica se o usuário tem acesso autorizado a este estudante
            # (reaproveita a validação de escopo por escola e disciplina da Fase 3)
            try:
                EstudanteService.obter_estudante_com_historico(
                    db=db,
                    usuario_solicitante=usuario,
                    estudante_id=estudante_obj.id,
                )
            except HTTPException as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: o estudante informado não pertence ao escopo autorizado do usuário.",
                ) from exc

            if turma_obj is not None:
                if estudante_obj.escola_id != turma_obj.escola_id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="O estudante e a turma informados pertencem a escolas diferentes.",
                    )
                stmt_vinc = (
                    select(BoletimPeriodo.id)
                    .where(
                        BoletimPeriodo.estudante_id == estudante_obj.id,
                        BoletimPeriodo.turma_id == turma_obj.id,
                    )
                    .limit(1)
                )
                if db.execute(stmt_vinc).scalar_one_or_none() is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"O estudante '{estudante_obj.codigo_anonimo}' não está vinculado "
                            f"à turma '{turma_obj.nome}'."
                        ),
                    )

        escola_id = (
            turma_obj.escola_id
            if turma_obj is not None
            else estudante_obj.escola_id  # type: ignore[union-attr]
        )
        return escola_id, estudante_obj, turma_obj

    @staticmethod
    def _usuario_pode_acessar_registro(
        db: Session,
        usuario: Usuario,
        ac: AcompanhamentoPedagogico,
    ) -> bool:
        if usuario.papel == PapelUsuario.GESTOR:
            return (
                usuario.escola_id is not None
                and ac.escola_id == usuario.escola_id
            )

        if usuario.papel == PapelUsuario.PROFESSOR:
            if (
                usuario.escola_id is not None
                and ac.escola_id != usuario.escola_id
            ):
                return False
            if ac.usuario_id == usuario.id:
                return True
            if ac.turma_id is not None:
                try:
                    garantir_escopo_pedagogico_turma_disciplina(
                        db=db,
                        usuario=usuario,
                        turma_id=ac.turma_id,
                        disciplina_id=ac.disciplina_id,
                    )
                except HTTPException:
                    return False
                if ac.estudante_id is None:
                    return True
            if ac.estudante_id is not None:
                try:
                    EstudanteService.obter_estudante_com_historico(
                        db=db,
                        usuario_solicitante=usuario,
                        estudante_id=ac.estudante_id,
                    )
                    return True
                except HTTPException:
                    return False

        return False

    @staticmethod
    def criar_acompanhamento(
        db: Session,
        dados: AcompanhamentoCreate,
        usuario_autenticado: Usuario,
    ) -> AcompanhamentoResponse:
        escola_id, estudante_obj, turma_obj = (
            AcompanhamentoService._resolver_e_validar_escopo_alvo(
                db=db,
                usuario=usuario_autenticado,
                estudante_id=dados.estudante_id,
                codigo_anonimo=dados.codigo_anonimo,
                turma_id=dados.turma_id,
                disciplina_id=dados.disciplina_id,
            )
        )

        ac = AcompanhamentoPedagogico(
            escola_id=escola_id,
            usuario_id=usuario_autenticado.id,
            estudante_id=estudante_obj.id if estudante_obj else None,
            turma_id=turma_obj.id if turma_obj else None,
            disciplina_id=dados.disciplina_id,
            origem=dados.origem,
            tipo_acao=dados.tipo_acao.strip(),
            descricao=dados.descricao.strip(),
            historico_alteracoes=[],
            ativo=True,
        )
        db.add(ac)
        db.commit()

        ac_carregado = AcompanhamentoRepository.get_by_id(db, ac.id)
        assert ac_carregado is not None
        return AcompanhamentoService._serializar(ac_carregado)

    @staticmethod
    def listar_acompanhamentos(
        db: Session,
        usuario_autenticado: Usuario,
        turma_id: Optional[uuid.UUID] = None,
        estudante_id: Optional[uuid.UUID] = None,
        origem: Optional[OrigemAcompanhamento] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AcompanhamentoResponse]:
        garantir_escopo_importacao_usuario(usuario_autenticado)

        if turma_id is not None:
            garantir_escopo_pedagogico_turma_disciplina(
                db=db,
                usuario=usuario_autenticado,
                turma_id=turma_id,
            )
        if estudante_id is not None:
            try:
                EstudanteService.obter_estudante_com_historico(
                    db=db,
                    usuario_solicitante=usuario_autenticado,
                    estudante_id=estudante_id,
                )
            except HTTPException as exc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: estudante fora do escopo autorizado.",
                ) from exc

        if usuario_autenticado.papel == PapelUsuario.GESTOR:
            assert usuario_autenticado.escola_id is not None
            registros = AcompanhamentoRepository.list_by_escola(
                db=db,
                escola_id=usuario_autenticado.escola_id,
                turma_id=turma_id,
                estudante_id=estudante_id,
                origem=origem,
            )
            filtrados = registros[skip : skip + limit]
            return [AcompanhamentoService._serializar(r) for r in filtrados]

        # Professor: busca nas escolas autorizadas e filtra estritamente pelo escopo do professor
        mapa_vinculos = EstudanteService._obter_mapa_vinculos_professor(
            db,
            usuario_autenticado.id,
            escola_id_professor=usuario_autenticado.escola_id,
        )
        if not mapa_vinculos:
            return []
        stmt_esc = (
            select(Turma.escola_id)
            .where(Turma.id.in_(list(mapa_vinculos.keys())))
            .distinct()
        )
        escolas_prof = set(db.execute(stmt_esc).scalars().all())
        todos: list[AcompanhamentoPedagogico] = []
        for esc_id in escolas_prof:
            todos.extend(
                AcompanhamentoRepository.list_by_escola(
                    db=db,
                    escola_id=esc_id,
                    turma_id=turma_id,
                    estudante_id=estudante_id,
                    origem=origem,
                )
            )
        todos.sort(key=lambda x: x.data_registro, reverse=True)
        autorizados = [
            ac
            for ac in todos
            if AcompanhamentoService._usuario_pode_acessar_registro(
                db, usuario_autenticado, ac
            )
        ]
        paginados = autorizados[skip : skip + limit]
        return [AcompanhamentoService._serializar(r) for r in paginados]

    @staticmethod
    def obter_acompanhamento(
        db: Session,
        acompanhamento_id: uuid.UUID,
        usuario_autenticado: Usuario,
    ) -> AcompanhamentoResponse:
        garantir_escopo_importacao_usuario(usuario_autenticado)
        ac = AcompanhamentoRepository.get_by_id(db, acompanhamento_id)
        if ac is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de acompanhamento não encontrado.",
            )
        if not AcompanhamentoService._usuario_pode_acessar_registro(
            db, usuario_autenticado, ac
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: registro de acompanhamento fora do seu escopo autorizado.",
            )
        return AcompanhamentoService._serializar(ac)

    @staticmethod
    def atualizar_acompanhamento(
        db: Session,
        acompanhamento_id: uuid.UUID,
        dados: AcompanhamentoUpdate,
        usuario_autenticado: Usuario,
    ) -> AcompanhamentoResponse:
        garantir_escopo_importacao_usuario(usuario_autenticado)
        ac = AcompanhamentoRepository.get_by_id(db, acompanhamento_id)
        if ac is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de acompanhamento não encontrado.",
            )
        if not AcompanhamentoService._usuario_pode_acessar_registro(
            db, usuario_autenticado, ac
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: você não possui autorização para alterar este acompanhamento.",
            )

        # Preserva snapshot do estado anterior antes de aplicar alterações
        alterou = False
        snapshot_anterior = {
            "alterado_em": datetime.now(timezone.utc).isoformat(),
            "alterado_por_usuario_id": str(usuario_autenticado.id),
            "origem_anterior": ac.origem.value,
            "tipo_acao_anterior": ac.tipo_acao,
            "descricao_anterior": ac.descricao,
            "ativo_anterior": ac.ativo,
        }

        if dados.origem is not None and dados.origem != ac.origem:
            ac.origem = dados.origem
            alterou = True
        if (
            dados.tipo_acao is not None
            and dados.tipo_acao.strip() != ac.tipo_acao
        ):
            ac.tipo_acao = dados.tipo_acao.strip()
            alterou = True
        if (
            dados.descricao is not None
            and dados.descricao.strip() != ac.descricao
        ):
            ac.descricao = dados.descricao.strip()
            alterou = True
        if dados.ativo is not None and dados.ativo != ac.ativo:
            ac.ativo = dados.ativo
            alterou = True

        if alterou:
            historico_atual = list(ac.historico_alteracoes or [])
            historico_atual.append(snapshot_anterior)
            ac.historico_alteracoes = historico_atual
            db.add(ac)
            db.commit()
            db.refresh(ac)

        return AcompanhamentoService._serializar(ac)
