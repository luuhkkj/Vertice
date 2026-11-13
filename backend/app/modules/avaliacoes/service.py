"""
Serviço de negócio para o módulo de Avaliações, Questões e Respostas (Bloco B — Fase 4).
Garante:
- Validação rigorosa de escopo (gestor limitado à própria escola; professor limitado a
  suas turmas e disciplinas em `ProfessorTurma`; bloqueio de administrador).
- Regras de questões FECHADAS vs ABERTAS, gabarito, peso e teto de nota obtida.
- Representação explícita de respostas em branco (`em_branco=True`) sem criar estudantes.
"""

from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import (
    garantir_escopo_importacao_usuario,
    garantir_escopo_pedagogico_turma_disciplina,
)
from app.modules.avaliacoes.models import (
    Avaliacao,
    QuestaoAvaliacao,
    RespostaAvaliacao,
    TipoQuestao,
)
from app.modules.avaliacoes.repository import AvaliacaoRepository
from app.modules.avaliacoes.schemas import (
    AvaliacaoCreate,
    AvaliacaoDetalhadaResponse,
    AvaliacaoResponse,
    AvaliacaoUpdate,
    QuestaoAvaliacaoCreate,
    QuestaoAvaliacaoResponse,
    QuestaoAvaliacaoUpdate,
    RespostaAvaliacaoCreate,
    RespostaAvaliacaoResponse,
)
from app.modules.estudantes.models import Estudante
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.usuarios.models import PapelUsuario, Usuario


class AvaliacaoService:
    """Regras de negócio para criação, consulta, edição e registro de respostas em avaliações."""

    @staticmethod
    def _serializar_avaliacao(av: Avaliacao) -> AvaliacaoResponse:
        return AvaliacaoResponse(
            id=av.id,
            codigo=av.codigo,
            titulo=av.titulo,
            escola_id=av.escola_id,
            turma_id=av.turma_id,
            turma_nome=av.turma.nome if av.turma else None,
            disciplina_id=av.disciplina_id,
            disciplina_codigo=av.disciplina.codigo if av.disciplina else None,
            disciplina_nome=av.disciplina.nome if av.disciplina else None,
            usuario_id=av.usuario_id,
            periodo_letivo=av.periodo_letivo,
            data_avaliacao=av.data_avaliacao,
            status=av.status,
            ativo=av.ativo,
            criado_em=av.criado_em,
            atualizado_em=av.atualizado_em,
        )

    @staticmethod
    def _serializar_avaliacao_detalhada(
        av: Avaliacao,
    ) -> AvaliacaoDetalhadaResponse:
        base = AvaliacaoService._serializar_avaliacao(av)
        questoes = [
            QuestaoAvaliacaoResponse.model_validate(q)
            for q in sorted(av.questoes or [], key=lambda x: x.codigo_questao)
        ]
        return AvaliacaoDetalhadaResponse(
            **base.model_dump(),
            questoes=questoes,
        )

    @staticmethod
    def _serializar_resposta(resp: RespostaAvaliacao) -> RespostaAvaliacaoResponse:
        return RespostaAvaliacaoResponse(
            id=resp.id,
            questao_id=resp.questao_id,
            codigo_questao=(
                resp.questao.codigo_questao if resp.questao else None
            ),
            estudante_id=resp.estudante_id,
            codigo_anonimo=(
                resp.estudante.codigo_anonimo if resp.estudante else None
            ),
            alternativa_marcada=resp.alternativa_marcada,
            em_branco=resp.em_branco,
            nota_obtida=resp.nota_obtida,
            acertou=resp.acertou,
            criado_em=resp.criado_em,
            atualizado_em=resp.atualizado_em,
        )

    @staticmethod
    def _verificar_acesso_avaliacao(
        db: Session,
        avaliacao: Optional[Avaliacao],
        usuario: Usuario,
    ) -> Avaliacao:
        garantir_escopo_importacao_usuario(usuario)
        if avaliacao is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avaliação não encontrada.",
            )

        # Valida se a turma e disciplina da avaliação pertencem ao escopo do usuário;
        # caso pertençam a outra escola ou professor sem vínculo, retorna 403/404.
        try:
            turma, _ = garantir_escopo_pedagogico_turma_disciplina(
                db=db,
                usuario=usuario,
                turma_id=avaliacao.turma_id,
                disciplina_id=avaliacao.disciplina_id,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                raise
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Avaliação não encontrada.",
            ) from exc

        if avaliacao.escola_id != turma.escola_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: inconsistência de escopo escolar na avaliação.",
            )
        return avaliacao

    @staticmethod
    def criar_avaliacao(
        db: Session,
        dados: AvaliacaoCreate,
        usuario_autenticado: Usuario,
    ) -> AvaliacaoResponse:
        turma, _ = garantir_escopo_pedagogico_turma_disciplina(
            db=db,
            usuario=usuario_autenticado,
            turma_id=dados.turma_id,
            disciplina_id=dados.disciplina_id,
        )

        codigo_limpo = (
            dados.codigo.strip()
            if dados.codigo and dados.codigo.strip()
            else f"AV-{uuid.uuid4().hex[:8].upper()}"
        )

        existente = AvaliacaoRepository.get_by_chave(
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
                    f"Já existe uma avaliação com o código '{codigo_limpo}' "
                    "para esta turma e disciplina."
                ),
            )

        avaliacao = Avaliacao(
            codigo=codigo_limpo,
            titulo=dados.titulo.strip(),
            escola_id=turma.escola_id,
            turma_id=turma.id,
            disciplina_id=dados.disciplina_id,
            usuario_id=usuario_autenticado.id,
            periodo_letivo=dados.periodo_letivo.strip(),
            data_avaliacao=dados.data_avaliacao,
            status=dados.status,
            ativo=True,
        )
        db.add(avaliacao)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao criar a avaliação.",
            ) from exc

        av_carregada = AvaliacaoRepository.get_by_id(db, avaliacao.id)
        assert av_carregada is not None
        return AvaliacaoService._serializar_avaliacao(av_carregada)

    @staticmethod
    def listar_avaliacoes(
        db: Session,
        usuario_autenticado: Usuario,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        periodo_letivo: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AvaliacaoResponse]:
        garantir_escopo_importacao_usuario(usuario_autenticado)

        if turma_id is not None or disciplina_id is not None:
            if turma_id is not None:
                garantir_escopo_pedagogico_turma_disciplina(
                    db=db,
                    usuario=usuario_autenticado,
                    turma_id=turma_id,
                    disciplina_id=disciplina_id,
                )

        if usuario_autenticado.papel == PapelUsuario.GESTOR:
            assert usuario_autenticado.escola_id is not None
            lista = AvaliacaoRepository.list_by_escola(
                db=db,
                escola_id=usuario_autenticado.escola_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                periodo_letivo=periodo_letivo,
                skip=skip,
                limit=limit,
            )
        else:
            lista = AvaliacaoRepository.list_by_professor(
                db=db,
                professor_id=usuario_autenticado.id,
                escola_id_professor=usuario_autenticado.escola_id,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
                periodo_letivo=periodo_letivo,
                skip=skip,
                limit=limit,
            )

        return [AvaliacaoService._serializar_avaliacao(av) for av in lista]

    @staticmethod
    def obter_avaliacao(
        db: Session,
        avaliacao_id: uuid.UUID,
        usuario_autenticado: Usuario,
    ) -> AvaliacaoDetalhadaResponse:
        av = AvaliacaoRepository.get_by_id(db, avaliacao_id)
        av = AvaliacaoService._verificar_acesso_avaliacao(
            db, av, usuario_autenticado
        )
        return AvaliacaoService._serializar_avaliacao_detalhada(av)

    @staticmethod
    def atualizar_avaliacao(
        db: Session,
        avaliacao_id: uuid.UUID,
        dados: AvaliacaoUpdate,
        usuario_autenticado: Usuario,
    ) -> AvaliacaoResponse:
        av = AvaliacaoRepository.get_by_id(db, avaliacao_id)
        av = AvaliacaoService._verificar_acesso_avaliacao(
            db, av, usuario_autenticado
        )

        if dados.titulo is not None:
            av.titulo = dados.titulo.strip()
        if dados.periodo_letivo is not None:
            av.periodo_letivo = dados.periodo_letivo.strip()
        if dados.data_avaliacao is not None:
            av.data_avaliacao = dados.data_avaliacao
        if dados.status is not None:
            av.status = dados.status
        if dados.ativo is not None:
            av.ativo = dados.ativo

        db.add(av)
        db.commit()
        db.refresh(av)
        return AvaliacaoService._serializar_avaliacao(av)

    @staticmethod
    def criar_questao(
        db: Session,
        avaliacao_id: uuid.UUID,
        dados: QuestaoAvaliacaoCreate,
        usuario_autenticado: Usuario,
    ) -> QuestaoAvaliacaoResponse:
        av = AvaliacaoRepository.get_by_id(db, avaliacao_id)
        av = AvaliacaoService._verificar_acesso_avaliacao(
            db, av, usuario_autenticado
        )

        codigo_q = dados.codigo_questao.strip().upper()
        existente = AvaliacaoRepository.get_questao_by_codigo(
            db, av.id, codigo_q
        )
        if existente is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe a questão '{codigo_q}' cadastrada nesta avaliação.",
            )

        questao = QuestaoAvaliacao(
            avaliacao_id=av.id,
            codigo_questao=codigo_q,
            tipo_questao=dados.tipo_questao,
            alternativa_correta=dados.alternativa_correta,
            valor_questao=round(float(dados.valor_questao), 2),
            faixa_dificuldade=dados.faixa_dificuldade,
            topico=dados.topico.strip() if dados.topico else None,
        )
        db.add(questao)
        try:
            db.commit()
            db.refresh(questao)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflito de integridade ao cadastrar questão '{codigo_q}'.",
            ) from exc

        return QuestaoAvaliacaoResponse.model_validate(questao)

    @staticmethod
    def listar_questoes(
        db: Session,
        avaliacao_id: uuid.UUID,
        usuario_autenticado: Usuario,
    ) -> list[QuestaoAvaliacaoResponse]:
        av = AvaliacaoRepository.get_by_id(db, avaliacao_id)
        av = AvaliacaoService._verificar_acesso_avaliacao(
            db, av, usuario_autenticado
        )
        questoes = AvaliacaoRepository.list_questoes_by_avaliacao(db, av.id)
        return [QuestaoAvaliacaoResponse.model_validate(q) for q in questoes]

    @staticmethod
    def atualizar_questao(
        db: Session,
        questao_id: uuid.UUID,
        dados: QuestaoAvaliacaoUpdate,
        usuario_autenticado: Usuario,
    ) -> QuestaoAvaliacaoResponse:
        questao = AvaliacaoRepository.get_questao_by_id(db, questao_id)
        if questao is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questão não encontrada.",
            )
        AvaliacaoService._verificar_acesso_avaliacao(
            db, questao.avaliacao, usuario_autenticado
        )

        novo_tipo = (
            dados.tipo_questao
            if dados.tipo_questao is not None
            else questao.tipo_questao
        )
        nova_alt = (
            dados.alternativa_correta
            if "alternativa_correta" in dados.model_fields_set
            else questao.alternativa_correta
        )
        novo_valor = (
            round(float(dados.valor_questao), 2)
            if dados.valor_questao is not None
            else round(float(questao.valor_questao), 2)
        )

        # Proteção de integridade histórica (Fase 5 — Item 6.3):
        # Se a questão já possui respostas registradas, alterações retroativas em
        # `tipo_questao`, `alternativa_correta` ou `valor_questao` corromperiam o histórico
        # de `acertou` e `nota_obtida` já persistidos.
        possui_respostas = bool(questao.respostas)
        if possui_respostas:
            alt_atual = (questao.alternativa_correta or "").strip().upper() or None
            alt_nova_norm = (nova_alt or "").strip().upper() or None
            valor_atual = round(float(questao.valor_questao), 2)
            if (
                novo_tipo != questao.tipo_questao
                or alt_nova_norm != alt_atual
                or abs(novo_valor - valor_atual) > 1e-6
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Não é permitido alterar 'tipo_questao', 'alternativa_correta' ou "
                        f"'valor_questao' da questão '{questao.codigo_questao}' porque ela "
                        "já possui respostas individuais registradas."
                    ),
                )

        if novo_tipo == TipoQuestao.FECHADA and not nova_alt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Questões FECHADAS exigem 'alternativa_correta' (A, B, C, D ou E).",
            )
        if novo_tipo == TipoQuestao.ABERTA and nova_alt is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Questões ABERTAS não devem possuir 'alternativa_correta'.",
            )

        if dados.codigo_questao is not None:
            novo_cod = dados.codigo_questao.strip().upper()
            if novo_cod.lower() != questao.codigo_questao.lower():
                colisao = AvaliacaoRepository.get_questao_by_codigo(
                    db, questao.avaliacao_id, novo_cod
                )
                if colisao is not None and colisao.id != questao.id:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Já existe outra questão com o código '{novo_cod}' nesta avaliação.",
                    )
            questao.codigo_questao = novo_cod

        questao.tipo_questao = novo_tipo
        questao.alternativa_correta = nova_alt
        questao.valor_questao = novo_valor
        if dados.faixa_dificuldade is not None:
            questao.faixa_dificuldade = dados.faixa_dificuldade
        if "topico" in dados.model_fields_set:
            questao.topico = dados.topico.strip() if dados.topico else None

        db.add(questao)
        db.commit()
        db.refresh(questao)
        return QuestaoAvaliacaoResponse.model_validate(questao)

    @staticmethod
    def calcular_resultado_resposta(
        questao: QuestaoAvaliacao,
        alternativa_marcada: Optional[str],
        em_branco_explicito: Optional[bool],
        nota_obtida_informada: Optional[float],
        acertou_informado: Optional[bool] = None,
    ) -> tuple[Optional[str], bool, float, Optional[bool]]:
        """
        Aplica as regras de correção e validação de nota/gabarito para uma resposta:
        - Impede nota negativa ou superior a `questao.valor_questao`.
        - Representa explicitamente respostas em branco (`em_branco=True`).
        - Em questões FECHADAS:
          * Se em branco (`alternativa_marcada` ausente ou `"BRANCO"` ou `em_branco=True`),
            define `alternativa_marcada="BRANCO"`, `em_branco=True`, `nota_obtida=0.0`, `acertou=False`.
          * Se assinalada A..E, compara com `questao.alternativa_correta`:
            se acertou, `acertou=True` e `nota_obtida = nota_obtida_informada ?? questao.valor_questao`;
            se errou, `acertou=False` e `nota_obtida = nota_obtida_informada ?? 0.0`.
        - Em questões ABERTAS:
          * Não exige alternativa marcada (`alternativa_marcada=None`).
          * Se `em_branco=True` ou (`nota_obtida_informada is None` e `alternativa_marcada == "BRANCO"`),
            marca `em_branco=True`, `nota_obtida=0.0`, `acertou=False`.
          * Caso contrário, exige `nota_obtida_informada` entre `0.0` e `questao.valor_questao`.
            Define `acertou` conforme `acertou_informado` ou critério documentado
            (`nota_obtida >= 0.6 * questao.valor_questao`, isto é, >= 60% do peso da questão).
        """
        valor_max = float(questao.valor_questao)

        if nota_obtida_informada is not None:
            if nota_obtida_informada < 0.0 or nota_obtida_informada > valor_max + 1e-6:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"A nota obtida ({nota_obtida_informada}) na questão '{questao.codigo_questao}' "
                        f"deve estar entre 0.0 e o valor da questão ({valor_max})."
                    ),
                )

        if questao.tipo_questao == TipoQuestao.FECHADA:
            alt_norm = (
                alternativa_marcada.strip().upper()
                if alternativa_marcada
                else None
            )
            if (
                em_branco_explicito is True
                or alt_norm is None
                or alt_norm == "BRANCO"
            ):
                if (
                    nota_obtida_informada is not None
                    and nota_obtida_informada > 0.0
                ):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"Questão fechada '{questao.codigo_questao}' deixada em branco "
                            "não pode receber nota positiva."
                        ),
                    )
                return "BRANCO", True, 0.0, False

            acertou_calc = alt_norm == (questao.alternativa_correta or "").upper()
            if nota_obtida_informada is not None:
                nota_final = round(float(nota_obtida_informada), 2)
            else:
                nota_final = round(valor_max if acertou_calc else 0.0, 2)
            return alt_norm, False, nota_final, acertou_calc

        # Questão ABERTA:
        alt_norm_aberta = (
            alternativa_marcada.strip().upper()
            if alternativa_marcada
            else None
        )
        if (
            em_branco_explicito is True
            or alt_norm_aberta == "BRANCO"
            or (nota_obtida_informada is None and em_branco_explicito is not False)
        ):
            if (
                nota_obtida_informada is not None
                and nota_obtida_informada > 0.0
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Questão aberta '{questao.codigo_questao}' marcada em branco "
                        "não pode ter nota positiva."
                    ),
                )
            return None, True, 0.0, False

        if alt_norm_aberta is not None and alt_norm_aberta != "BRANCO":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"A questão '{questao.codigo_questao}' é do tipo ABERTA e não aceita "
                    f"alternativa de múltipla escolha ('{alt_norm_aberta}')."
                ),
            )

        if nota_obtida_informada is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Questão aberta '{questao.codigo_questao}' exige 'nota_obtida' "
                    "quando não estiver em branco."
                ),
            )

        nota_final_aberta = round(float(nota_obtida_informada), 2)
        if acertou_informado is not None:
            acertou_aberta = bool(acertou_informado)
        else:
            # Critério documentado para questão aberta: aproveitamento >= 60% do valor da questão
            acertou_aberta = nota_final_aberta >= round(0.6 * valor_max, 4)

        return None, False, nota_final_aberta, acertou_aberta

    @staticmethod
    def _resolver_estudante_na_turma(
        db: Session,
        escola_id: uuid.UUID,
        turma_id: uuid.UUID,
        estudante_id: Optional[uuid.UUID],
        codigo_anonimo: Optional[str],
    ) -> Estudante:
        """
        Localiza um estudante já cadastrado na escola e verifica que ele pertence
        à turma da avaliação nos dados escolares existentes. Nunca cria estudantes.
        """
        estudante: Optional[Estudante] = None
        if estudante_id is not None:
            estudante = EstudanteRepository.get_by_id(db, estudante_id)
            if estudante is not None and estudante.escola_id != escola_id:
                estudante = None
        elif codigo_anonimo:
            estudante = EstudanteRepository.get_by_escola_e_codigo(
                db, escola_id, codigo_anonimo.strip()
            )

        if estudante is None or not estudante.ativo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Estudante não encontrado no cadastro da escola. "
                    "Estudantes não podem ser criados via avaliações."
                ),
            )

        if not AvaliacaoRepository.estudante_vinculado_a_turma(
            db=db,
            estudante_id=estudante.id,
            turma_id=turma_id,
            escola_id=escola_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"O estudante '{estudante.codigo_anonimo}' não possui vínculo "
                    "com a turma desta avaliação nos dados escolares."
                ),
            )
        return estudante

    @staticmethod
    def registrar_resposta_questao(
        db: Session,
        questao_id: uuid.UUID,
        dados: RespostaAvaliacaoCreate,
        usuario_autenticado: Usuario,
        permitir_atualizacao: bool = False,
    ) -> RespostaAvaliacaoResponse:
        questao = AvaliacaoRepository.get_questao_by_id(db, questao_id)
        if questao is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Questão não encontrada.",
            )
        av = AvaliacaoService._verificar_acesso_avaliacao(
            db, questao.avaliacao, usuario_autenticado
        )

        estudante = AvaliacaoService._resolver_estudante_na_turma(
            db=db,
            escola_id=av.escola_id,
            turma_id=av.turma_id,
            estudante_id=dados.estudante_id,
            codigo_anonimo=dados.codigo_anonimo,
        )

        alt_final, em_branco, nota_final, acertou_final = (
            AvaliacaoService.calcular_resultado_resposta(
                questao=questao,
                alternativa_marcada=dados.alternativa_marcada,
                em_branco_explicito=dados.em_branco,
                nota_obtida_informada=dados.nota_obtida,
                acertou_informado=dados.acertou,
            )
        )

        existente = AvaliacaoRepository.get_resposta_by_questao_e_estudante(
            db, questao.id, estudante.id
        )
        if existente is not None:
            if not permitir_atualizacao:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Já existe uma resposta registrada para o estudante "
                        f"'{estudante.codigo_anonimo}' na questão '{questao.codigo_questao}'."
                    ),
                )
            existente.alternativa_marcada = alt_final
            existente.em_branco = em_branco
            existente.nota_obtida = nota_final
            existente.acertou = acertou_final
            db.add(existente)
            db.commit()
            db.refresh(existente)
            return AvaliacaoService._serializar_resposta(existente)

        nova_resp = RespostaAvaliacao(
            questao_id=questao.id,
            estudante_id=estudante.id,
            alternativa_marcada=alt_final,
            em_branco=em_branco,
            nota_obtida=nota_final,
            acertou=acertou_final,
        )
        db.add(nova_resp)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resposta duplicada para este estudante e questão.",
            ) from exc

        resp_carregada = AvaliacaoRepository.get_resposta_by_questao_e_estudante(
            db, questao.id, estudante.id
        )
        assert resp_carregada is not None
        return AvaliacaoService._serializar_resposta(resp_carregada)

    @staticmethod
    def listar_respostas_avaliacao(
        db: Session,
        avaliacao_id: uuid.UUID,
        usuario_autenticado: Usuario,
        questao_id: Optional[uuid.UUID] = None,
        estudante_id: Optional[uuid.UUID] = None,
    ) -> list[RespostaAvaliacaoResponse]:
        av = AvaliacaoRepository.get_by_id(db, avaliacao_id)
        av = AvaliacaoService._verificar_acesso_avaliacao(
            db, av, usuario_autenticado
        )
        respostas = AvaliacaoRepository.list_respostas_by_avaliacao(
            db=db,
            avaliacao_id=av.id,
            questao_id=questao_id,
            estudante_id=estudante_id,
        )
        return [AvaliacaoService._serializar_resposta(r) for r in respostas]

