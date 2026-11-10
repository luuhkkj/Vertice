"""
Serviço de consulta de Estudantes e Histórico Escolar com isolamento rigoroso de escopo.
Não revela a existência de registros de outras escolas ou turmas/disciplinas sem vínculo.
"""

from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
)
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.estudantes.schemas import (
    BoletimPeriodoResponse,
    EstudanteHistoricoDetalhadoResponse,
    NotaDisciplinaResponse,
)
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario


class EstudanteService:
    """Regras de negócio e isolamento de acesso para consultas de estudantes e boletins."""

    @staticmethod
    def _obter_mapa_vinculos_professor(
        db: Session,
        professor_id: uuid.UUID,
        escola_id_professor: Optional[uuid.UUID] = None,
    ) -> dict[uuid.UUID, set[Optional[uuid.UUID]]]:
        """
        Retorna um dicionário `{turma_id: {disciplina_id_1, disciplina_id_2, ...}}`
        contendo apenas vínculos em turmas ativas e escolas ativas (e disciplinas ativas,
        quando `disciplina_id` não for `None`).
        Se `escola_id_professor` estiver definido no perfil do professor, restringe às
        turmas daquela escola.
        Semântica de `None` no conjunto: representa um vínculo geral explícito
        (`ProfessorTurma.disciplina_id IS NULL`) naquela turma.
        """
        stmt_discs = select(Disciplina.id).where(Disciplina.ativo.is_(True))
        disciplinas_ativas_ids = set(db.execute(stmt_discs).scalars().all())

        stmt = (
            select(ProfessorTurma, Turma, Escola)
            .join(Turma, ProfessorTurma.turma_id == Turma.id)
            .join(Escola, Turma.escola_id == Escola.id)
            .where(
                ProfessorTurma.professor_id == professor_id,
                Turma.ativo.is_(True),
                Escola.ativo.is_(True),
            )
        )
        if escola_id_professor is not None:
            stmt = stmt.where(Turma.escola_id == escola_id_professor)

        rows = db.execute(stmt).all()
        mapa: dict[uuid.UUID, set[Optional[uuid.UUID]]] = {}
        for atrib, turma, _escola in rows:
            if (
                atrib.disciplina_id is not None
                and atrib.disciplina_id not in disciplinas_ativas_ids
            ):
                continue
            mapa.setdefault(turma.id, set()).add(atrib.disciplina_id)
        return mapa

    @staticmethod
    def listar_estudantes(
        db: Session,
        usuario_solicitante: Usuario,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Estudante]:
        """
        Lista estudantes respeitando estritamente o escopo do usuário autenticado:
        - Gestor: filtra exclusivamente pela escola vinculada (`usuario.escola_id`).
        - Professor: filtra exclusivamente pelas turmas E disciplinas em que possui vínculo ativo.
          A ausência do filtro `disciplina_id` na requisição NUNCA amplia o acesso para outras
          disciplinas da mesma turma.
        """
        if usuario_solicitante.papel == PapelUsuario.GESTOR:
            if usuario_solicitante.escola_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: gestor não possui escola vinculada.",
                )
            if turma_id is not None:
                stmt_t = select(Turma).where(Turma.id == turma_id)
                turma_obj = db.execute(stmt_t).scalar_one_or_none()
                if (
                    turma_obj is None
                    or turma_obj.escola_id != usuario_solicitante.escola_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Acesso negado: turma não pertence à escola vinculada ao gestor.",
                    )
            return EstudanteRepository.list_by_escola(
                db=db,
                escola_id=usuario_solicitante.escola_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                ano_letivo=ano_letivo,
                periodo_letivo=periodo_letivo,
                skip=skip,
                limit=limit,
            )

        if usuario_solicitante.papel == PapelUsuario.PROFESSOR:
            mapa_vinculos = EstudanteService._obter_mapa_vinculos_professor(
                db,
                usuario_solicitante.id,
                escola_id_professor=usuario_solicitante.escola_id,
            )
            if not mapa_vinculos:
                return []

            if turma_id is not None and turma_id not in mapa_vinculos:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: você não possui vínculo autorizado para consultar esta turma.",
                )

            if disciplina_id is not None:
                if turma_id is not None:
                    discs_turma = mapa_vinculos.get(turma_id, set())
                    if None not in discs_turma and disciplina_id not in discs_turma:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Acesso negado: você não possui vínculo autorizado para esta disciplina na turma.",
                        )
                else:
                    # Verifica se o professor possui vínculo com essa disciplina (ou vínculo geral) em alguma turma
                    autorizado_em_alguma = any(
                        (None in discs) or (disciplina_id in discs)
                        for discs in mapa_vinculos.values()
                    )
                    if not autorizado_em_alguma:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Acesso negado: você não possui vínculo autorizado para consultar esta disciplina.",
                        )

            return EstudanteRepository.list_by_professor(
                db=db,
                professor_id=usuario_solicitante.id,
                escola_id_professor=usuario_solicitante.escola_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                ano_letivo=ano_letivo,
                periodo_letivo=periodo_letivo,
                skip=skip,
                limit=limit,
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado para este perfil.",
        )

    @staticmethod
    def contar_estudantes(
        db: Session,
        usuario_solicitante: Usuario,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
    ) -> int:
        """Retorna a contagem total de estudantes distintos dentro do escopo autorizado."""
        if usuario_solicitante.papel == PapelUsuario.GESTOR:
            if usuario_solicitante.escola_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: gestor não possui escola vinculada.",
                )
            return EstudanteRepository.count_by_escola(
                db=db,
                escola_id=usuario_solicitante.escola_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                ano_letivo=ano_letivo,
                periodo_letivo=periodo_letivo,
            )

        if usuario_solicitante.papel == PapelUsuario.PROFESSOR:
            mapa_vinculos = EstudanteService._obter_mapa_vinculos_professor(
                db,
                usuario_solicitante.id,
                escola_id_professor=usuario_solicitante.escola_id,
            )
            if not mapa_vinculos:
                return 0
            return EstudanteRepository.count_by_professor(
                db=db,
                professor_id=usuario_solicitante.id,
                escola_id_professor=usuario_solicitante.escola_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                ano_letivo=ano_letivo,
                periodo_letivo=periodo_letivo,
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado para este perfil.",
        )

    @staticmethod
    def obter_estudante_com_historico(
        db: Session,
        estudante_id: uuid.UUID,
        usuario_solicitante: Usuario,
    ) -> EstudanteHistoricoDetalhadoResponse:
        """
        Retorna os dados anônimos e o histórico de boletins de um estudante,
        filtrando tanto os boletins quanto as notas por disciplina pelo escopo do solicitante:
        - Se o professor possui vínculo específico por disciplina (`disciplina_id IS NOT NULL`),
          só autoriza boletins que possuam nota naquela disciplina específica (não vaza boletins
          vazios nem boletins com notas apenas de outras disciplinas).
        - Se o professor possui vínculo geral na turma (`disciplina_id IS NULL`), autoriza os
          boletins daquela turma ativa.
        Retorna 404 caso o estudante não exista ou esteja fora do escopo autorizado.
        """
        estudante = EstudanteRepository.get_by_id(db, estudante_id)
        if estudante is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estudante não encontrado.",
            )

        if usuario_solicitante.papel == PapelUsuario.GESTOR:
            if (
                usuario_solicitante.escola_id is None
                or estudante.escola_id != usuario_solicitante.escola_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Estudante não encontrado.",
                )
            boletins_ativos = [
                b
                for b in estudante.boletins
                if b.escola_id == usuario_solicitante.escola_id
                and (b.turma is None or b.turma.ativo)
            ]
            boletins_filtrados = EstudanteService._serializar_boletins(
                estudante,
                boletins_ativos,
                filtro_disciplinas_por_turma=None,
            )
            return EstudanteHistoricoDetalhadoResponse(
                id=estudante.id,
                codigo_anonimo=estudante.codigo_anonimo,
                escola_id=estudante.escola_id,
                historico_reprovacoes=estudante.historico_reprovacoes,
                ativo=estudante.ativo,
                criado_em=estudante.criado_em,
                atualizado_em=estudante.atualizado_em,
                boletins=boletins_filtrados,
            )

        if usuario_solicitante.papel == PapelUsuario.PROFESSOR:
            if (
                usuario_solicitante.escola_id is not None
                and estudante.escola_id != usuario_solicitante.escola_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Estudante não encontrado.",
                )

            mapa_vinculos = EstudanteService._obter_mapa_vinculos_professor(
                db,
                usuario_solicitante.id,
                escola_id_professor=usuario_solicitante.escola_id,
            )
            boletins_autorizados: list[BoletimPeriodo] = []
            for bol in estudante.boletins:
                if bol.turma_id not in mapa_vinculos:
                    continue
                if bol.turma is not None and not bol.turma.ativo:
                    continue
                discs_autorizadas = mapa_vinculos[bol.turma_id]
                if None in discs_autorizadas:
                    # Vínculo geral explícito na turma (disciplina_id IS NULL)
                    boletins_autorizados.append(bol)
                else:
                    # Vínculo específico por disciplina: exige que o boletim possua ao menos
                    # um registro de NotaDisciplina em disciplina autorizada para este professor
                    notas_autorizadas = [
                        n
                        for n in bol.notas_disciplina
                        if n.disciplina_id in discs_autorizadas
                    ]
                    if notas_autorizadas:
                        boletins_autorizados.append(bol)

            if not boletins_autorizados:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Estudante não encontrado.",
                )

            boletins_serializados = EstudanteService._serializar_boletins(
                estudante,
                boletins_autorizados,
                filtro_disciplinas_por_turma=mapa_vinculos,
            )
            return EstudanteHistoricoDetalhadoResponse(
                id=estudante.id,
                codigo_anonimo=estudante.codigo_anonimo,
                escola_id=estudante.escola_id,
                historico_reprovacoes=estudante.historico_reprovacoes,
                ativo=estudante.ativo,
                criado_em=estudante.criado_em,
                atualizado_em=estudante.atualizado_em,
                boletins=boletins_serializados,
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado para este perfil.",
        )

    @staticmethod
    def _serializar_boletins(
        estudante: Estudante,
        boletins: list[BoletimPeriodo],
        filtro_disciplinas_por_turma: Optional[
            dict[uuid.UUID, set[Optional[uuid.UUID]]]
        ] = None,
    ) -> list[BoletimPeriodoResponse]:
        resultado: list[BoletimPeriodoResponse] = []
        for bol in sorted(
            boletins,
            key=lambda b: (b.ano_letivo, b.periodo_letivo),
            reverse=True,
        ):
            notas_resp: list[NotaDisciplinaResponse] = []
            for n in bol.notas_disciplina:
                if filtro_disciplinas_por_turma is not None:
                    discs_aut = filtro_disciplinas_por_turma.get(
                        bol.turma_id, set()
                    )
                    if None not in discs_aut and n.disciplina_id not in discs_aut:
                        continue
                notas_resp.append(
                    NotaDisciplinaResponse(
                        id=n.id,
                        boletim_id=n.boletim_id,
                        disciplina_id=n.disciplina_id,
                        disciplina_codigo=(
                            n.disciplina.codigo if n.disciplina else None
                        ),
                        disciplina_nome=(
                            n.disciplina.nome if n.disciplina else None
                        ),
                        nota=n.nota,
                        nota_prova=n.nota_prova,
                        nota_trabalho=n.nota_trabalho,
                        frequencia_percentual=n.frequencia_percentual,
                        faltas=n.faltas,
                        em_recuperacao=n.em_recuperacao,
                        criado_em=n.criado_em,
                        atualizado_em=n.atualizado_em,
                    )
                )

            resultado.append(
                BoletimPeriodoResponse(
                    id=bol.id,
                    estudante_id=bol.estudante_id,
                    codigo_anonimo=estudante.codigo_anonimo,
                    escola_id=bol.escola_id,
                    turma_id=bol.turma_id,
                    turma_nome=bol.turma.nome if bol.turma else None,
                    ano_letivo=bol.ano_letivo,
                    periodo_letivo=bol.periodo_letivo,
                    idade=bol.idade,
                    frequencia_percentual=bol.frequencia_percentual,
                    faltas=bol.faltas,
                    media_geral=bol.media_geral,
                    notas_baixas=bol.notas_baixas,
                    historico_reprovacoes=bol.historico_reprovacoes,
                    participacao_recuperacao=bol.participacao_recuperacao,
                    atrasos=bol.atrasos,
                    situacao_final=bol.situacao_final,
                    notas_disciplina=notas_resp,
                    criado_em=bol.criado_em,
                    atualizado_em=bol.atualizado_em,
                )
            )
        return resultado
