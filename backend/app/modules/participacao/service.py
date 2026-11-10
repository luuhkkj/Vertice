"""
Serviço de negócio para o módulo de Participação, Atividades e Entregas (Bloco C — Fase 4).
Implementa:
- Criação e gestão de atividades vinculadas a turmas e disciplinas autorizadas.
- Geração idempotente de entregas esperadas (`gerar_entregas_esperadas_atividade`) para
  todos os estudantes já vinculados à turma na escola (sem criar estudantes novos).
- Cálculo determinístico do `status_entrega` (`ENTREGUE`, `ATRASADO`, `PENDENTE`, `NAO_ENTREGUE`)
  comparando `data_entrega` e `data_limite` (e a data de referência).
- Preservação de notas ausentes como `None` (`NULL`), sem convertê-las em zero.
"""

from datetime import date
from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import (
    garantir_escopo_importacao_usuario,
    garantir_escopo_pedagogico_turma_disciplina,
)
from app.modules.estudantes.models import Estudante
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.participacao.models import (
    Atividade,
    EntregaAtividade,
    StatusEntregaAtividade,
)
from app.modules.participacao.repository import ParticipacaoRepository
from app.modules.participacao.schemas import (
    AtividadeCreate,
    AtividadeResponse,
    AtividadeUpdate,
    EntregaAtividadeResponse,
    EntregaAtividadeUpdate,
    EntregaAtividadeUpsert,
    GeracaoEntregasEsperadasResponse,
)
from app.modules.usuarios.models import PapelUsuario, Usuario


class ParticipacaoService:
    """Regras de negócio de atividades, geração de entregas esperadas e registro de entregas."""

    @staticmethod
    def _serializar_atividade(at: Atividade) -> AtividadeResponse:
        return AtividadeResponse(
            id=at.id,
            codigo=at.codigo,
            titulo=at.titulo,
            escola_id=at.escola_id,
            turma_id=at.turma_id,
            turma_nome=at.turma.nome if at.turma else None,
            disciplina_id=at.disciplina_id,
            disciplina_codigo=at.disciplina.codigo if at.disciplina else None,
            disciplina_nome=at.disciplina.nome if at.disciplina else None,
            usuario_id=at.usuario_id,
            periodo_letivo=at.periodo_letivo,
            data_limite=at.data_limite,
            nota_maxima=at.nota_maxima,
            status=at.status,
            ativo=at.ativo,
            criado_em=at.criado_em,
            atualizado_em=at.atualizado_em,
        )

    @staticmethod
    def _serializar_entrega(ent: EntregaAtividade) -> EntregaAtividadeResponse:
        return EntregaAtividadeResponse(
            id=ent.id,
            atividade_id=ent.atividade_id,
            estudante_id=ent.estudante_id,
            codigo_anonimo=(
                ent.estudante.codigo_anonimo if ent.estudante else None
            ),
            data_entrega=ent.data_entrega,
            nota=ent.nota,
            status_entrega=ent.status_entrega,
            criado_em=ent.criado_em,
            atualizado_em=ent.atualizado_em,
        )

    @staticmethod
    def _verificar_acesso_atividade(
        db: Session,
        atividade: Optional[Atividade],
        usuario: Usuario,
    ) -> Atividade:
        garantir_escopo_importacao_usuario(usuario)
        if atividade is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Atividade não encontrada.",
            )

        try:
            turma, _ = garantir_escopo_pedagogico_turma_disciplina(
                db=db,
                usuario=usuario,
                turma_id=atividade.turma_id,
                disciplina_id=atividade.disciplina_id,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                raise
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Atividade não encontrada.",
            ) from exc

        if atividade.escola_id != turma.escola_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: inconsistência de escopo escolar na atividade.",
            )
        return atividade

    @staticmethod
    def resolver_status_entrega(
        data_limite: date,
        data_entrega: Optional[date],
        status_informado: Optional[StatusEntregaAtividade] = None,
        data_referencia: Optional[date] = None,
    ) -> StatusEntregaAtividade:
        """
        Determina ou valida de forma consistente o status de entrega considerando
        `data_limite` e `data_entrega`:
        - Se `data_entrega` foi informada:
          * `data_entrega <= data_limite` -> `ENTREGUE` (bloqueia se `status_informado` for `PENDENTE` ou `NAO_ENTREGUE`).
          * `data_entrega > data_limite` -> `ATRASADO` (bloqueia se `status_informado` for `ENTREGUE`, `PENDENTE` ou `NAO_ENTREGUE`).
        - Se `data_entrega` é `None` (ainda não entregou):
          * Se `status_informado` for `ENTREGUE` ou `ATRASADO`, rejeita por falta de `data_entrega`.
          * Se `status_informado` for explicitamente `NAO_ENTREGUE` ou `PENDENTE`, respeita se compatível
            ou deriva pela comparação entre `data_referencia` (default `date.today()`) e `data_limite`:
            `hoje <= data_limite` -> `PENDENTE`, `hoje > data_limite` -> `NAO_ENTREGUE`.
        """
        hoje = data_referencia or date.today()

        if data_entrega is not None:
            status_calculado = (
                StatusEntregaAtividade.ENTREGUE
                if data_entrega <= data_limite
                else StatusEntregaAtividade.ATRASADO
            )
            if (
                status_informado is not None
                and status_informado != status_calculado
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Status de entrega '{status_informado.value}' incompatível com "
                        f"data_entrega ({data_entrega}) e data_limite ({data_limite}). "
                        f"O status correto é '{status_calculado.value}'."
                    ),
                )
            return status_calculado

        # Sem data_entrega:
        if status_informado in (
            StatusEntregaAtividade.ENTREGUE,
            StatusEntregaAtividade.ATRASADO,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"O status '{status_informado.value}' exige o preenchimento de 'data_entrega'."
                ),
            )

        if status_informado is not None:
            return status_informado

        return (
            StatusEntregaAtividade.PENDENTE
            if hoje <= data_limite
            else StatusEntregaAtividade.NAO_ENTREGUE
        )

    @staticmethod
    def validar_nota_atividade(
        nota: Optional[float],
        nota_maxima: Optional[float],
    ) -> Optional[float]:
        """Valida que a nota (quando informada) não é negativa e não excede `nota_maxima`."""
        if nota is None:
            return None
        teto = float(nota_maxima) if nota_maxima is not None else 10.0
        if nota < 0.0 or nota > teto + 1e-6:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"A nota informada ({nota}) deve estar entre 0.0 e a nota máxima da atividade ({teto})."
                ),
            )
        return round(float(nota), 2)

    @staticmethod
    def criar_atividade(
        db: Session,
        dados: AtividadeCreate,
        usuario_autenticado: Usuario,
    ) -> AtividadeResponse:
        turma, _ = garantir_escopo_pedagogico_turma_disciplina(
            db=db,
            usuario=usuario_autenticado,
            turma_id=dados.turma_id,
            disciplina_id=dados.disciplina_id,
        )

        codigo_limpo = (
            dados.codigo.strip()
            if dados.codigo and dados.codigo.strip()
            else f"ATIV-{uuid.uuid4().hex[:8].upper()}"
        )

        existente = ParticipacaoRepository.get_atividade_by_chave(
            db=db,
            escola_id=turma.escola_id,
            turma_id=turma.id,
            disciplina_id=dados.disciplina_id,
            codigo=codigo_limpo,
        )
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Já existe uma atividade com o código '{codigo_limpo}' "
                    "para esta turma e disciplina."
                ),
            )

        atividade = Atividade(
            codigo=codigo_limpo,
            titulo=dados.titulo.strip(),
            escola_id=turma.escola_id,
            turma_id=turma.id,
            disciplina_id=dados.disciplina_id,
            usuario_id=usuario_autenticado.id,
            periodo_letivo=dados.periodo_letivo.strip(),
            data_limite=dados.data_limite,
            nota_maxima=(
                round(float(dados.nota_maxima), 2)
                if dados.nota_maxima is not None
                else None
            ),
            status=dados.status,
            ativo=True,
        )
        db.add(atividade)
        try:
            db.flush()
            if dados.gerar_entregas_esperadas:
                ParticipacaoService._executar_geracao_entregas_esperadas(
                    db=db,
                    atividade=atividade,
                )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao criar a atividade.",
            ) from exc

        at_carregada = ParticipacaoRepository.get_atividade_by_id(
            db, atividade.id
        )
        assert at_carregada is not None
        return ParticipacaoService._serializar_atividade(at_carregada)

    @staticmethod
    def _executar_geracao_entregas_esperadas(
        db: Session,
        atividade: Atividade,
        data_referencia: Optional[date] = None,
    ) -> tuple[int, int, int, int]:
        """
        Gera de forma idempotente os registros de entrega esperados para todos os estudantes
        ativos vinculados à turma da atividade.
        Política de integridade histórica para movimentação de estudantes:
        - Novos estudantes que entrarem na turma recebem registro esperado sem duplicar os existentes.
        - Registros de estudantes que já realizaram entrega ou já constavam na atividade nunca são apagados.
        - Registros `PENDENTE` sem entrega cujo prazo (`data_limite`) já venceu na `data_referencia`
          são atualizados para `NAO_ENTREGUE`.
        Retorna `(total_elegiveis, criadas, ja_existentes, atualizadas_nao_entregue)`.
        """
        hoje = data_referencia or date.today()
        estudantes_turma = ParticipacaoRepository.list_estudantes_elegiveis_turma(
            db=db,
            escola_id=atividade.escola_id,
            turma_id=atividade.turma_id,
        )
        entregas_atuais = ParticipacaoRepository.list_entregas_by_atividade(
            db=db,
            atividade_id=atividade.id,
        )
        mapa_existentes = {e.estudante_id: e for e in entregas_atuais}

        status_inicial_sem_entrega = (
            StatusEntregaAtividade.PENDENTE
            if hoje <= atividade.data_limite
            else StatusEntregaAtividade.NAO_ENTREGUE
        )

        criadas = 0
        ja_existentes = 0
        atualizadas_nao_entregue = 0

        for est in estudantes_turma:
            entrega_exist = mapa_existentes.get(est.id)
            if entrega_exist is None:
                nova = EntregaAtividade(
                    atividade_id=atividade.id,
                    estudante_id=est.id,
                    data_entrega=None,
                    nota=None,
                    status_entrega=status_inicial_sem_entrega,
                )
                db.add(nova)
                criadas += 1
            else:
                ja_existentes += 1
                if (
                    entrega_exist.data_entrega is None
                    and entrega_exist.status_entrega
                    == StatusEntregaAtividade.PENDENTE
                    and hoje > atividade.data_limite
                ):
                    entrega_exist.status_entrega = (
                        StatusEntregaAtividade.NAO_ENTREGUE
                    )
                    db.add(entrega_exist)
                    atualizadas_nao_entregue += 1

        db.flush()
        return (
            len(estudantes_turma),
            criadas,
            ja_existentes,
            atualizadas_nao_entregue,
        )

    @staticmethod
    def gerar_entregas_esperadas(
        db: Session,
        atividade_id: uuid.UUID,
        usuario_autenticado: Usuario,
        data_referencia: Optional[date] = None,
    ) -> GeracaoEntregasEsperadasResponse:
        atividade = ParticipacaoRepository.get_atividade_by_id(db, atividade_id)
        atividade = ParticipacaoService._verificar_acesso_atividade(
            db, atividade, usuario_autenticado
        )

        total_elegiveis, criadas, ja_existentes, atualizadas = (
            ParticipacaoService._executar_geracao_entregas_esperadas(
                db=db,
                atividade=atividade,
                data_referencia=data_referencia,
            )
        )
        db.commit()

        return GeracaoEntregasEsperadasResponse(
            atividade_id=atividade.id,
            turma_id=atividade.turma_id,
            total_estudantes_elegiveis=total_elegiveis,
            entregas_criadas=criadas,
            entregas_ja_existentes=ja_existentes,
            entregas_atualizadas_para_nao_entregue=atualizadas,
            mensagem=(
                f"Geração concluída com sucesso: {criadas} entrega(s) esperada(s) criada(s), "
                f"{ja_existentes} já existente(s)."
            ),
        )

    @staticmethod
    def listar_atividades(
        db: Session,
        usuario_autenticado: Usuario,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        periodo_letivo: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AtividadeResponse]:
        garantir_escopo_importacao_usuario(usuario_autenticado)

        if turma_id is not None:
            garantir_escopo_pedagogico_turma_disciplina(
                db=db,
                usuario=usuario_autenticado,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
            )

        if usuario_autenticado.papel == PapelUsuario.GESTOR:
            assert usuario_autenticado.escola_id is not None
            lista = ParticipacaoRepository.list_atividades_by_escola(
                db=db,
                escola_id=usuario_autenticado.escola_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                periodo_letivo=periodo_letivo,
                skip=skip,
                limit=limit,
            )
        else:
            lista = ParticipacaoRepository.list_atividades_by_professor(
                db=db,
                professor_id=usuario_autenticado.id,
                escola_id_professor=usuario_autenticado.escola_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                periodo_letivo=periodo_letivo,
                skip=skip,
                limit=limit,
            )

        return [ParticipacaoService._serializar_atividade(a) for a in lista]

    @staticmethod
    def obter_atividade(
        db: Session,
        atividade_id: uuid.UUID,
        usuario_autenticado: Usuario,
    ) -> AtividadeResponse:
        at = ParticipacaoRepository.get_atividade_by_id(db, atividade_id)
        at = ParticipacaoService._verificar_acesso_atividade(
            db, at, usuario_autenticado
        )
        return ParticipacaoService._serializar_atividade(at)

    @staticmethod
    def atualizar_atividade(
        db: Session,
        atividade_id: uuid.UUID,
        dados: AtividadeUpdate,
        usuario_autenticado: Usuario,
    ) -> AtividadeResponse:
        at = ParticipacaoRepository.get_atividade_by_id(db, atividade_id)
        at = ParticipacaoService._verificar_acesso_atividade(
            db, at, usuario_autenticado
        )

        if dados.titulo is not None:
            at.titulo = dados.titulo.strip()
        if dados.periodo_letivo is not None:
            at.periodo_letivo = dados.periodo_letivo.strip()
        if dados.data_limite is not None:
            at.data_limite = dados.data_limite
        if dados.nota_maxima is not None:
            at.nota_maxima = round(float(dados.nota_maxima), 2)
        if dados.status is not None:
            at.status = dados.status
        if dados.ativo is not None:
            at.ativo = dados.ativo

        db.add(at)
        db.commit()
        db.refresh(at)
        return ParticipacaoService._serializar_atividade(at)

    @staticmethod
    def registrar_ou_atualizar_entrega(
        db: Session,
        atividade_id: uuid.UUID,
        dados: EntregaAtividadeUpsert,
        usuario_autenticado: Usuario,
    ) -> EntregaAtividadeResponse:
        atividade = ParticipacaoRepository.get_atividade_by_id(db, atividade_id)
        atividade = ParticipacaoService._verificar_acesso_atividade(
            db, atividade, usuario_autenticado
        )

        estudante: Optional[Estudante] = None
        if dados.estudante_id is not None:
            estudante = EstudanteRepository.get_by_id(db, dados.estudante_id)
            if estudante is not None and estudante.escola_id != atividade.escola_id:
                estudante = None
        elif dados.codigo_anonimo:
            estudante = EstudanteRepository.get_by_escola_e_codigo(
                db, atividade.escola_id, dados.codigo_anonimo.strip()
            )

        if estudante is None or not estudante.ativo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Estudante não encontrado no cadastro da escola. "
                    "Estudantes não podem ser criados via atividades."
                ),
            )

        # Verifica vínculo do estudante com a turma da atividade
        elegiveis_ids = {
            e.id
            for e in ParticipacaoRepository.list_estudantes_elegiveis_turma(
                db, atividade.escola_id, atividade.turma_id
            )
        }
        if estudante.id not in elegiveis_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"O estudante '{estudante.codigo_anonimo}' não está vinculado "
                    "à turma desta atividade nos dados escolares."
                ),
            )

        nota_validada = ParticipacaoService.validar_nota_atividade(
            dados.nota, atividade.nota_maxima
        )
        status_final = ParticipacaoService.resolver_status_entrega(
            data_limite=atividade.data_limite,
            data_entrega=dados.data_entrega,
            status_informado=dados.status_entrega,
        )

        entrega = ParticipacaoRepository.get_entrega_by_atividade_e_estudante(
            db, atividade.id, estudante.id
        )
        if entrega is None:
            entrega = EntregaAtividade(
                atividade_id=atividade.id,
                estudante_id=estudante.id,
                data_entrega=dados.data_entrega,
                nota=nota_validada,
                status_entrega=status_final,
            )
            db.add(entrega)
        else:
            entrega.data_entrega = dados.data_entrega
            if "nota" in dados.model_fields_set:
                entrega.nota = nota_validada
            entrega.status_entrega = status_final
            db.add(entrega)

        db.commit()
        ent_carregada = ParticipacaoRepository.get_entrega_by_atividade_e_estudante(
            db, atividade.id, estudante.id
        )
        assert ent_carregada is not None
        return ParticipacaoService._serializar_entrega(ent_carregada)

    @staticmethod
    def atualizar_entrega_por_id(
        db: Session,
        entrega_id: uuid.UUID,
        dados: EntregaAtividadeUpdate,
        usuario_autenticado: Usuario,
    ) -> EntregaAtividadeResponse:
        entrega = ParticipacaoRepository.get_entrega_by_id(db, entrega_id)
        if entrega is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registro de entrega não encontrado.",
            )
        atividade = ParticipacaoService._verificar_acesso_atividade(
            db, entrega.atividade, usuario_autenticado
        )

        nova_data = (
            dados.data_entrega
            if "data_entrega" in dados.model_fields_set
            else entrega.data_entrega
        )
        nova_nota = (
            ParticipacaoService.validar_nota_atividade(
                dados.nota, atividade.nota_maxima
            )
            if "nota" in dados.model_fields_set
            else entrega.nota
        )
        novo_status = ParticipacaoService.resolver_status_entrega(
            data_limite=atividade.data_limite,
            data_entrega=nova_data,
            status_informado=dados.status_entrega,
        )

        entrega.data_entrega = nova_data
        entrega.nota = nova_nota
        entrega.status_entrega = novo_status
        db.add(entrega)
        db.commit()
        db.refresh(entrega)
        return ParticipacaoService._serializar_entrega(entrega)

    @staticmethod
    def listar_entregas_atividade(
        db: Session,
        atividade_id: uuid.UUID,
        usuario_autenticado: Usuario,
        estudante_id: Optional[uuid.UUID] = None,
    ) -> list[EntregaAtividadeResponse]:
        atividade = ParticipacaoRepository.get_atividade_by_id(db, atividade_id)
        atividade = ParticipacaoService._verificar_acesso_atividade(
            db, atividade, usuario_autenticado
        )
        entregas = ParticipacaoRepository.list_entregas_by_atividade(
            db=db,
            atividade_id=atividade.id,
            estudante_id=estudante_id,
        )
        return [ParticipacaoService._serializar_entrega(e) for e in entregas]

