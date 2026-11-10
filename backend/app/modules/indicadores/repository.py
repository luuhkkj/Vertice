"""
Repositório de acesso a dados para o módulo de Indicadores (Fase 4).
Garante que todos os recortes respeitem o escopo de escola (para gestor) e os vínculos
reais em `ProfessorTurma` (para professor), nunca permitindo que um filtro de query
amplie o escopo autorizado do usuário.
"""

from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import (
    garantir_escopo_importacao_usuario,
    garantir_escopo_pedagogico_turma_disciplina,
)
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.avaliacoes.models import (
    Avaliacao,
    QuestaoAvaliacao,
    RespostaAvaliacao,
)
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    NotaDisciplina,
)
from app.modules.participacao.models import Atividade, EntregaAtividade
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario


class IndicadoresRepository:
    """Consultas filtradas e isoladas para alimentar os cálculos de indicadores."""

    @staticmethod
    def validar_filtros_escopo(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
    ) -> set[uuid.UUID]:
        """
        Valida se os filtros solicitados (`escola_id`, `turma_id`, `disciplina_id`)
        pertencem ao escopo autorizado do usuário autenticado.
        Retorna o conjunto de `escola_id` autorizados para a consulta.
        """
        garantir_escopo_importacao_usuario(usuario)

        if usuario.papel == PapelUsuario.GESTOR:
            assert usuario.escola_id is not None
            if escola_id is not None and escola_id != usuario.escola_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: gestor não pode consultar indicadores de outra escola.",
                )
            if turma_id is not None:
                garantir_escopo_pedagogico_turma_disciplina(
                    db=db,
                    usuario=usuario,
                    turma_id=turma_id,
                    disciplina_id=disciplina_id,
                )
            return {usuario.escola_id}

        # Professor:
        stmt_atrib = (
            select(ProfessorTurma, Turma, Escola)
            .join(Turma, ProfessorTurma.turma_id == Turma.id)
            .join(Escola, Turma.escola_id == Escola.id)
            .where(
                ProfessorTurma.professor_id == usuario.id,
                Turma.ativo.is_(True),
                Escola.ativo.is_(True),
            )
        )
        rows = db.execute(stmt_atrib).all()
        escolas_prof: set[uuid.UUID] = set()
        discs_prof: set[Optional[uuid.UUID]] = set()
        for atrib, turma, _esc in rows:
            if (
                usuario.escola_id is not None
                and turma.escola_id != usuario.escola_id
            ):
                continue
            escolas_prof.add(turma.escola_id)
            discs_prof.add(atrib.disciplina_id)

        if escola_id is not None:
            if escola_id not in escolas_prof:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: professor não possui vínculo com a escola solicitada.",
                )
            escolas_prof = {escola_id}

        if turma_id is not None:
            garantir_escopo_pedagogico_turma_disciplina(
                db=db,
                usuario=usuario,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
            )
        elif disciplina_id is not None:
            if None not in discs_prof and disciplina_id not in discs_prof:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: professor não possui vínculo com a disciplina solicitada.",
                )

        return escolas_prof

    @staticmethod
    def listar_boletins_escopo(
        db: Session,
        usuario: Usuario,
        escolas_autorizadas: set[uuid.UUID],
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> tuple[list[BoletimPeriodo], dict[uuid.UUID, set[Optional[uuid.UUID]]]]:
        """
        Retorna os boletins dentro do escopo autorizado e o mapa de vínculos do professor
        (`turma_id -> {disciplina_id}`) para cálculo de médias e frequências sem vazamento.
        """
        if not escolas_autorizadas:
            return [], {}

        mapa_vinculos_prof: dict[uuid.UUID, set[Optional[uuid.UUID]]] = {}
        if usuario.papel == PapelUsuario.PROFESSOR:
            stmt_atrib = (
                select(ProfessorTurma, Turma)
                .join(Turma, ProfessorTurma.turma_id == Turma.id)
                .where(
                    ProfessorTurma.professor_id == usuario.id,
                    Turma.escola_id.in_(escolas_autorizadas),
                    Turma.ativo.is_(True),
                )
            )
            for atrib, _t in db.execute(stmt_atrib).all():
                mapa_vinculos_prof.setdefault(atrib.turma_id, set()).add(
                    atrib.disciplina_id
                )
            if not mapa_vinculos_prof:
                return [], {}

        stmt = (
            select(BoletimPeriodo)
            .join(Turma, Turma.id == BoletimPeriodo.turma_id)
            .join(Estudante, Estudante.id == BoletimPeriodo.estudante_id)
            .options(
                selectinload(BoletimPeriodo.turma),
                selectinload(BoletimPeriodo.estudante),
                selectinload(BoletimPeriodo.notas_disciplina).selectinload(
                    NotaDisciplina.disciplina
                ),
            )
            .where(
                BoletimPeriodo.escola_id.in_(escolas_autorizadas),
                Turma.escola_id.in_(escolas_autorizadas),
                Turma.ativo.is_(True),
                Estudante.ativo.is_(True),
            )
        )
        if turma_id is not None:
            stmt = stmt.where(BoletimPeriodo.turma_id == turma_id)
        if ano_letivo is not None:
            stmt = stmt.where(BoletimPeriodo.ano_letivo == ano_letivo)
        if periodo_letivo is not None:
            stmt = stmt.where(
                BoletimPeriodo.periodo_letivo == periodo_letivo.strip()
            )

        if usuario.papel == PapelUsuario.PROFESSOR:
            stmt = stmt.where(
                BoletimPeriodo.turma_id.in_(set(mapa_vinculos_prof.keys()))
            )

        boletins_brutos = list(db.execute(stmt).scalars().all())

        # Filtra rigorosamente por disciplina quando aplicável
        boletins_filtrados: list[BoletimPeriodo] = []
        for bol in boletins_brutos:
            if usuario.papel == PapelUsuario.PROFESSOR:
                discs_aut = mapa_vinculos_prof.get(bol.turma_id, set())
                notas_aut = [
                    nd
                    for nd in bol.notas_disciplina
                    if (nd.disciplina is None or nd.disciplina.ativo)
                    and (
                        None in discs_aut
                        or nd.disciplina_id in discs_aut
                    )
                    and (
                        disciplina_id is None
                        or nd.disciplina_id == disciplina_id
                    )
                ]
                if None not in discs_aut or disciplina_id is not None:
                    if not notas_aut:
                        continue
            else:
                if disciplina_id is not None:
                    notas_disc = [
                        nd
                        for nd in bol.notas_disciplina
                        if nd.disciplina_id == disciplina_id
                        and (nd.disciplina is None or nd.disciplina.ativo)
                    ]
                    if not notas_disc:
                        continue

            boletins_filtrados.append(bol)

        return boletins_filtrados, mapa_vinculos_prof

    @staticmethod
    def listar_avaliacoes_escopo(
        db: Session,
        usuario: Usuario,
        escolas_autorizadas: set[uuid.UUID],
        avaliacao_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> list[Avaliacao]:
        if not escolas_autorizadas:
            return []

        stmt = (
            select(Avaliacao)
            .join(Turma, Turma.id == Avaliacao.turma_id)
            .join(Disciplina, Disciplina.id == Avaliacao.disciplina_id)
            .options(
                selectinload(Avaliacao.turma),
                selectinload(Avaliacao.disciplina),
                selectinload(Avaliacao.questoes)
                .selectinload(QuestaoAvaliacao.respostas)
                .selectinload(RespostaAvaliacao.estudante),
            )
            .where(
                Avaliacao.escola_id.in_(escolas_autorizadas),
                Avaliacao.ativo.is_(True),
                Turma.ativo.is_(True),
                Disciplina.ativo.is_(True),
            )
        )
        if avaliacao_id is not None:
            stmt = stmt.where(Avaliacao.id == avaliacao_id)
        if turma_id is not None:
            stmt = stmt.where(Avaliacao.turma_id == turma_id)
        if disciplina_id is not None:
            stmt = stmt.where(Avaliacao.disciplina_id == disciplina_id)
        if ano_letivo is not None:
            stmt = stmt.where(Turma.ano_letivo == ano_letivo)
        if periodo_letivo is not None:
            stmt = stmt.where(
                Avaliacao.periodo_letivo == periodo_letivo.strip()
            )

        if usuario.papel == PapelUsuario.PROFESSOR:
            subq_prof = (
                select(Avaliacao.id)
                .join(
                    ProfessorTurma,
                    ProfessorTurma.turma_id == Avaliacao.turma_id,
                )
                .where(
                    ProfessorTurma.professor_id == usuario.id,
                    or_(
                        ProfessorTurma.disciplina_id.is_(None),
                        ProfessorTurma.disciplina_id == Avaliacao.disciplina_id,
                    ),
                )
            )
            stmt = stmt.where(Avaliacao.id.in_(subq_prof))

        stmt = stmt.order_by(Avaliacao.data_avaliacao.asc(), Avaliacao.codigo)
        return list(db.execute(stmt).scalars().all())

    @staticmethod
    def listar_atividades_escopo(
        db: Session,
        usuario: Usuario,
        escolas_autorizadas: set[uuid.UUID],
        atividade_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> list[Atividade]:
        if not escolas_autorizadas:
            return []

        stmt = (
            select(Atividade)
            .join(Turma, Turma.id == Atividade.turma_id)
            .join(Disciplina, Disciplina.id == Atividade.disciplina_id)
            .options(
                selectinload(Atividade.turma),
                selectinload(Atividade.disciplina),
                selectinload(Atividade.entregas).selectinload(
                    EntregaAtividade.estudante
                ),
            )
            .where(
                Atividade.escola_id.in_(escolas_autorizadas),
                Atividade.ativo.is_(True),
                Turma.ativo.is_(True),
                Disciplina.ativo.is_(True),
            )
        )
        if atividade_id is not None:
            stmt = stmt.where(Atividade.id == atividade_id)
        if turma_id is not None:
            stmt = stmt.where(Atividade.turma_id == turma_id)
        if disciplina_id is not None:
            stmt = stmt.where(Atividade.disciplina_id == disciplina_id)
        if ano_letivo is not None:
            stmt = stmt.where(Turma.ano_letivo == ano_letivo)
        if periodo_letivo is not None:
            stmt = stmt.where(
                Atividade.periodo_letivo == periodo_letivo.strip()
            )

        if usuario.papel == PapelUsuario.PROFESSOR:
            subq_prof = (
                select(Atividade.id)
                .join(
                    ProfessorTurma,
                    ProfessorTurma.turma_id == Atividade.turma_id,
                )
                .where(
                    ProfessorTurma.professor_id == usuario.id,
                    or_(
                        ProfessorTurma.disciplina_id.is_(None),
                        ProfessorTurma.disciplina_id == Atividade.disciplina_id,
                    ),
                )
            )
            stmt = stmt.where(Atividade.id.in_(subq_prof))

        stmt = stmt.order_by(Atividade.data_limite.asc(), Atividade.codigo)
        return list(db.execute(stmt).scalars().all())

