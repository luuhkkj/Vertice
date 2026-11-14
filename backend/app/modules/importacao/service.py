"""
Serviço de negócio para Importação de Datasets Escolares em Duas Etapas (Fase 3).
Etapa 1: Upload, validação completa, verificação de escopo e geração de prévia (sem gravar dados acadêmicos).
Etapa 2: Revalidação de identidade/escopo e confirmação em transação atômica com rollback integral em falhas.
"""

from datetime import date, datetime, timezone
from hashlib import sha256
from typing import Any, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import garantir_escopo_importacao_usuario
from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.avaliacoes.models import (
    Avaliacao,
    FaixaDificuldadeQuestao,
    QuestaoAvaliacao,
    RespostaAvaliacao,
    StatusAvaliacao,
    TipoQuestao,
)
from app.modules.avaliacoes.repository import AvaliacaoRepository
from app.modules.avaliacoes.service import AvaliacaoService
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import (
    BoletimPeriodo,
    Estudante,
    NotaDisciplina,
    SituacaoFinalPeriodo,
)
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.importacao.models import (
    LoteImportacao,
    StatusLoteImportacao,
    TipoImportacao,
)
from app.modules.importacao.repository import ImportacaoRepository
from app.modules.importacao.schemas import (
    ConfirmacaoImportacaoResponse,
    LoteImportacaoPreviaResponse,
    LoteImportacaoResumoResponse,
    RelatorioValidacaoSchema,
)
from app.modules.importacao.validator import (
    identificar_tipo_importacao,
    ler_dataframe_bruto,
    processar_e_validar_dataframe,
    processar_e_validar_dataframe_atividades,
    processar_e_validar_dataframe_avaliacoes,
    validar_arquivo_upload,
)
from app.modules.participacao.models import (
    Atividade,
    EntregaAtividade,
    StatusAtividade,
    StatusEntregaAtividade,
)
from app.modules.participacao.repository import ParticipacaoRepository
from app.modules.participacao.service import ParticipacaoService
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario


class ImportacaoService:
    """Orquestra validação, pré-visualização, confirmação atômica e descarte de lotes."""

    @staticmethod
    def _verificar_acesso_lote(
        lote: Optional[LoteImportacao],
        usuario: Usuario,
    ) -> LoteImportacao:
        """
        Verifica se o lote existe e pertence ao escopo autorizado do usuário autenticado.
        Retorna HTTP 404 para lotes inexistentes ou de outras escolas/usuários,
        não revelando a existência de registros fora do escopo.
        """
        garantir_escopo_importacao_usuario(usuario)

        if lote is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lote de importação não encontrado.",
            )

        if usuario.papel == PapelUsuario.PROFESSOR:
            if lote.usuario_id != usuario.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Lote de importação não encontrado.",
                )
        elif usuario.papel == PapelUsuario.GESTOR:
            if usuario.escola_id is None or lote.escola_id != usuario.escola_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Lote de importação não encontrado.",
                )

        return lote

    @staticmethod
    def validar_e_gerar_previa(
        db: Session,
        nome_arquivo: Optional[str],
        conteudo_bytes: bytes,
        usuario_autenticado: Usuario,
        tipo_importacao: Optional[TipoImportacao] = None,
    ) -> LoteImportacaoPreviaResponse:
        """
        Etapa 1: Valida extensão, tamanho, colunas, anonimização e vínculos do usuário autenticado.
        Suporta `DADOS_ESCOLARES` (Fase 3), `AVALIACOES` (Bloco B) e `ATIVIDADES` (Bloco C).
        Registra o lote de auditoria (`validado` ou `com_erros`), mas NÃO persiste nenhum
        dado acadêmico, de avaliação ou de atividade no banco de dados.
        """
        garantir_escopo_importacao_usuario(usuario_autenticado)

        extensao = validar_arquivo_upload(nome_arquivo, conteudo_bytes)
        hash_sha256 = sha256(conteudo_bytes).hexdigest()
        df = ler_dataframe_bruto(conteudo_bytes, extensao)

        tipo_resolvido = identificar_tipo_importacao(df, tipo_importacao)

        agora = datetime.now(timezone.utc)
        if tipo_resolvido == TipoImportacao.AVALIACOES:
            escola_id, relatorio, previa_registros = (
                processar_e_validar_dataframe_avaliacoes(
                    db=db,
                    df=df,
                    usuario=usuario_autenticado,
                )
            )
        elif tipo_resolvido == TipoImportacao.ATIVIDADES:
            escola_id, relatorio, previa_registros = (
                processar_e_validar_dataframe_atividades(
                    db=db,
                    df=df,
                    usuario=usuario_autenticado,
                )
            )
        else:
            escola_id, relatorio, previa_registros = (
                processar_e_validar_dataframe(
                    db=db,
                    df=df,
                    usuario=usuario_autenticado,
                )
            )

        status_lote = (
            StatusLoteImportacao.VALIDADO
            if relatorio.quantidade_erros == 0 and relatorio.registros_validos > 0
            else StatusLoteImportacao.COM_ERROS
        )

        lote = LoteImportacao(
            usuario_id=usuario_autenticado.id,
            escola_id=escola_id,
            nome_arquivo=(nome_arquivo or "dataset.csv").strip()[:255],
            tipo_importacao=tipo_resolvido,
            hash_arquivo=hash_sha256,
            status=status_lote,
            total_linhas=relatorio.total_linhas,
            registros_validos=relatorio.registros_validos,
            quantidade_erros=relatorio.quantidade_erros,
            quantidade_avisos=relatorio.quantidade_avisos,
            registros_novos=relatorio.registros_novos,
            registros_existentes=relatorio.registros_existentes,
            registros_inseridos=0,
            registros_atualizados=0,
            relatorio_validacao=relatorio.model_dump(mode="json"),
            dados_previa=previa_registros if status_lote == StatusLoteImportacao.VALIDADO else [],
            enviado_em=agora,
            validado_em=datetime.now(timezone.utc),
        )
        lote_salvo = ImportacaoRepository.create(db, lote)

        return ImportacaoService._construir_resposta_previa(lote_salvo)

    @staticmethod
    def listar_lotes(
        db: Session,
        usuario_autenticado: Usuario,
        skip: int = 0,
        limit: int = 50,
    ) -> list[LoteImportacaoResumoResponse]:
        """Lista lotes de importação visíveis para o usuário autenticado conforme seu escopo."""
        garantir_escopo_importacao_usuario(usuario_autenticado)

        if usuario_autenticado.papel == PapelUsuario.GESTOR:
            assert usuario_autenticado.escola_id is not None
            lotes = ImportacaoRepository.list_by_escola(
                db, usuario_autenticado.escola_id, skip=skip, limit=limit
            )
        else:
            lotes = ImportacaoRepository.list_by_usuario(
                db, usuario_autenticado.id, skip=skip, limit=limit
            )

        return [LoteImportacaoResumoResponse.model_validate(lote) for lote in lotes]

    @staticmethod
    def obter_resumo_lote(
        db: Session,
        lote_id: uuid.UUID,
        usuario_autenticado: Usuario,
    ) -> LoteImportacaoResumoResponse:
        lote = ImportacaoRepository.get_by_id(db, lote_id)
        lote = ImportacaoService._verificar_acesso_lote(lote, usuario_autenticado)
        return LoteImportacaoResumoResponse.model_validate(lote)

    @staticmethod
    def obter_previa_lote(
        db: Session,
        lote_id: uuid.UUID,
        usuario_autenticado: Usuario,
    ) -> LoteImportacaoPreviaResponse:
        lote = ImportacaoRepository.get_by_id(db, lote_id)
        lote = ImportacaoService._verificar_acesso_lote(lote, usuario_autenticado)
        return ImportacaoService._construir_resposta_previa(lote)

    @staticmethod
    def descartar_lote(
        db: Session,
        lote_id: uuid.UUID,
        usuario_autenticado: Usuario,
    ) -> LoteImportacaoResumoResponse:
        """Descarta um lote que ainda não tenha sido confirmado."""
        lote = ImportacaoRepository.get_by_id(db, lote_id, for_update=True)
        lote = ImportacaoService._verificar_acesso_lote(lote, usuario_autenticado)

        if lote.status == StatusLoteImportacao.CONFIRMADO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível descartar um lote que já foi confirmado.",
            )
        if lote.status == StatusLoteImportacao.DESCARTADO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este lote já foi descartado anteriormente.",
            )

        lote.status = StatusLoteImportacao.DESCARTADO
        lote.dados_previa = []
        lote_atualizado = ImportacaoRepository.update(db, lote)
        return LoteImportacaoResumoResponse.model_validate(lote_atualizado)

    @staticmethod
    def _revalidar_autorizacao_na_confirmacao(
        db: Session,
        usuario: Usuario,
        lote: LoteImportacao,
        registros_previa: list[dict[str, Any]],
    ) -> None:
        """
        Revalida integralmente no momento da confirmação (Etapa 2):
        1. Se o usuário responsável continua ativo e com perfil autorizado.
        2. Se a escola do lote existe, continua ativa e pertence ao escopo autorizado do usuário.
        3. Se cada turma ainda existe, continua ativa (`Turma.ativo == True`) e continua pertencendo
           à escola autorizada do lote (`turma.escola_id == lote.escola_id`).
        4. Se cada disciplina (quando informada) ainda existe e continua ativa (`Disciplina.ativo == True`).
        5. Para professores, se o vínculo em `ProfessorTurma` continua existindo para a combinação
           exata de `(turma_id, disciplina_id)` (ou vínculo geral `disciplina_id IS NULL`).
        """
        if not usuario.ativo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Autorização negada na confirmação: usuário inativo.",
            )
        garantir_escopo_importacao_usuario(usuario)

        stmt_escola = select(Escola).where(
            Escola.id == lote.escola_id,
            Escola.ativo.is_(True),
        )
        escola_lote = db.execute(stmt_escola).scalar_one_or_none()
        if escola_lote is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Autorização negada na confirmação: a unidade escolar do lote não existe ou foi desativada.",
            )

        if usuario.papel == PapelUsuario.GESTOR:
            if usuario.escola_id is None or usuario.escola_id != lote.escola_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Autorização negada na confirmação: gestor não pertence à unidade escolar deste lote.",
                )
            for reg in registros_previa:
                turma_id = uuid.UUID(str(reg["turma_id"]))
                reg_escola_id = uuid.UUID(str(reg["escola_id"]))
                disc_id_raw = reg.get("disciplina_id")
                disc_id = uuid.UUID(str(disc_id_raw)) if disc_id_raw else None

                stmt_t = select(Turma).where(Turma.id == turma_id)
                turma = db.execute(stmt_t).scalar_one_or_none()
                if (
                    turma is None
                    or not turma.ativo
                    or turma.escola_id != lote.escola_id
                    or reg_escola_id != lote.escola_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Autorização negada na confirmação: a turma '{reg.get('turma_nome')}' "
                            "não existe, foi desativada ou não pertence à escola vinculada ao gestor."
                        ),
                    )
                if disc_id is not None:
                    stmt_d = select(Disciplina).where(
                        Disciplina.id == disc_id,
                        Disciplina.ativo.is_(True),
                    )
                    if db.execute(stmt_d).scalar_one_or_none() is None:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=(
                                f"Autorização negada na confirmação: a disciplina '{reg.get('disciplina_nome')}' "
                                "não existe ou foi desativada."
                            ),
                        )
            return

        if usuario.papel == PapelUsuario.PROFESSOR:
            if usuario.escola_id is not None and usuario.escola_id != lote.escola_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Autorização negada na confirmação: o lote não pertence à escola autorizada do professor.",
                )

            stmt_atrib = select(ProfessorTurma).where(
                ProfessorTurma.professor_id == usuario.id
            )
            atribuicoes = list(db.execute(stmt_atrib).scalars().all())
            mapa_vinculos: dict[uuid.UUID, set[Optional[uuid.UUID]]] = {}
            for atrib in atribuicoes:
                mapa_vinculos.setdefault(atrib.turma_id, set()).add(
                    atrib.disciplina_id
                )

            for reg in registros_previa:
                turma_id = uuid.UUID(str(reg["turma_id"]))
                reg_escola_id = uuid.UUID(str(reg["escola_id"]))
                disc_id_raw = reg.get("disciplina_id")
                disc_id = uuid.UUID(str(disc_id_raw)) if disc_id_raw else None

                stmt_t = select(Turma).where(Turma.id == turma_id)
                turma = db.execute(stmt_t).scalar_one_or_none()
                if turma is None or not turma.ativo:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Autorização negada na confirmação: a turma '{reg.get('turma_nome')}' "
                            "não existe ou foi desativada."
                        ),
                    )

                if (
                    turma.escola_id != lote.escola_id
                    or reg_escola_id != lote.escola_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Autorização negada na confirmação: a turma '{reg.get('turma_nome')}' "
                            "não pertence à unidade escolar autorizada para o lote."
                        ),
                    )

                if (
                    usuario.escola_id is not None
                    and turma.escola_id != usuario.escola_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Autorização negada na confirmação: a turma '{reg.get('turma_nome')}' "
                            "pertence a uma escola fora do escopo do professor."
                        ),
                    )

                if turma_id not in mapa_vinculos:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Autorização negada na confirmação: o professor não possui vínculo ativo "
                            f"com a turma '{reg.get('turma_nome')}'."
                        ),
                    )

                discs_aut = mapa_vinculos[turma_id]
                if None not in discs_aut and disc_id not in discs_aut:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Autorização negada na confirmação: o professor não possui vínculo ativo "
                            f"com a disciplina '{reg.get('disciplina_nome')}' na turma '{reg.get('turma_nome')}'."
                        ),
                    )

                if disc_id is not None:
                    stmt_d = select(Disciplina).where(
                        Disciplina.id == disc_id,
                        Disciplina.ativo.is_(True),
                    )
                    if db.execute(stmt_d).scalar_one_or_none() is None:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=(
                                f"Autorização negada na confirmação: a disciplina '{reg.get('disciplina_nome')}' "
                                "não existe ou foi desativada."
                            ),
                        )
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado para confirmar importação.",
        )

    @staticmethod
    def confirmar_importacao(
        db: Session,
        lote_id: uuid.UUID,
        usuario_autenticado: Usuario,
    ) -> ConfirmacaoImportacaoResponse:
        """
        Etapa 2: Confirma e persiste os registros validados em uma única transação atômica.
        - Revalida identidade, permissões e vínculos atuais (`ProfessorTurma` / escola do gestor).
        - Bloqueia lotes já confirmados, com erros ou descartados (HTTP 409).
        - Preserva histórico longitudinal (não sobrescreve períodos anteriores nem substitui
          uma `situacao_final` consolidada por `NULL`).
        - Executa rollback completo em caso de qualquer erro.
        """
        lote = ImportacaoRepository.get_by_id(db, lote_id, for_update=True)
        lote = ImportacaoService._verificar_acesso_lote(lote, usuario_autenticado)

        # Somente o próprio autor do lote (ou gestor da mesma escola para lotes da escola)
        # pode confirmar; para professores, exige ser o próprio autor autenticado
        if lote.usuario_id != usuario_autenticado.id:
            if usuario_autenticado.papel != PapelUsuario.GESTOR or (
                lote.escola_id != usuario_autenticado.escola_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acesso negado: você não tem permissão para confirmar este lote.",
                )

        if lote.status == StatusLoteImportacao.CONFIRMADO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este lote de importação já foi confirmado anteriormente.",
            )

        if lote.status == StatusLoteImportacao.DESCARTADO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este lote foi descartado e não pode ser confirmado.",
            )

        if lote.status != StatusLoteImportacao.VALIDADO or lote.quantidade_erros > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Apenas lotes validados sem erros podem ser confirmados.",
            )

        registros_previa = lote.dados_previa or []
        if not registros_previa:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O lote não possui registros válidos para confirmação.",
            )

        # Revalida vínculos de autorização no momento exato da confirmação
        ImportacaoService._revalidar_autorizacao_na_confirmacao(
            db, usuario_autenticado, lote, registros_previa
        )

        inseridos = 0
        atualizados = 0

        try:
            if lote.tipo_importacao == TipoImportacao.AVALIACOES:
                inseridos, atualizados = (
                    ImportacaoService._persistir_confirmacao_avaliacoes(
                        db=db,
                        lote=lote,
                        usuario=usuario_autenticado,
                        registros_previa=registros_previa,
                    )
                )
            elif lote.tipo_importacao == TipoImportacao.ATIVIDADES:
                inseridos, atualizados = (
                    ImportacaoService._persistir_confirmacao_atividades(
                        db=db,
                        lote=lote,
                        usuario=usuario_autenticado,
                        registros_previa=registros_previa,
                    )
                )
            else:
                inseridos, atualizados = (
                    ImportacaoService._persistir_confirmacao_dados_escolares(
                        db=db,
                        registros_previa=registros_previa,
                    )
                )

            agora_conf = datetime.now(timezone.utc)
            lote.status = StatusLoteImportacao.CONFIRMADO
            lote.registros_inseridos = inseridos
            lote.registros_atualizados = atualizados
            lote.confirmado_em = agora_conf
            db.add(lote)
            db.commit()
            db.refresh(lote)

        except HTTPException:
            db.rollback()
            raise
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade ao persistir o lote de importação. Nenhuma alteração foi gravada.",
            ) from exc
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao confirmar a importação. A transação foi integralmente revertida (rollback).",
            ) from exc

        return ConfirmacaoImportacaoResponse(
            lote_id=lote.id,
            status=lote.status,
            usuario_id=lote.usuario_id,
            escola_id=lote.escola_id,
            registros_inseridos=lote.registros_inseridos,
            registros_atualizados=lote.registros_atualizados,
            confirmado_em=lote.confirmado_em or datetime.now(timezone.utc),
            mensagem=(
                f"Importação confirmada com sucesso: {lote.registros_inseridos} registro(s) inserido(s) "
                f"e {lote.registros_atualizados} registro(s) atualizado(s)."
            ),
        )

    @staticmethod
    def _persistir_confirmacao_dados_escolares(
        db: Session,
        registros_previa: list[dict[str, Any]],
    ) -> tuple[int, int]:
        inseridos = 0
        atualizados = 0
        for reg in registros_previa:
            escola_id = uuid.UUID(str(reg["escola_id"]))
            turma_id = uuid.UUID(str(reg["turma_id"]))
            disc_id_raw = reg.get("disciplina_id")
            disc_id = uuid.UUID(str(disc_id_raw)) if disc_id_raw else None
            codigo_anonimo = str(reg["codigo_anonimo"]).strip()
            ano_letivo = int(reg["ano_letivo"])
            periodo_letivo = str(reg["periodo_letivo"]).strip()

            # 1. Busca ou cria o Estudante anônimo na escola
            estudante = EstudanteRepository.get_by_escola_e_codigo(
                db, escola_id, codigo_anonimo
            )
            hist_reprov = reg.get("historico_reprovacoes")
            if estudante is None:
                estudante = Estudante(
                    codigo_anonimo=codigo_anonimo,
                    escola_id=escola_id,
                    historico_reprovacoes=(
                        int(hist_reprov) if hist_reprov is not None else 0
                    ),
                    ativo=True,
                )
                db.add(estudante)
                db.flush()
            else:
                if (
                    hist_reprov is not None
                    and int(hist_reprov) > estudante.historico_reprovacoes
                ):
                    estudante.historico_reprovacoes = int(hist_reprov)
                    db.flush()

            # 2. Busca ou cria o BoletimPeriodo para (estudante, escola, turma, ano_letivo, periodo_letivo)
            boletim = EstudanteRepository.get_boletim_by_chave(
                db=db,
                estudante_id=estudante.id,
                escola_id=escola_id,
                turma_id=turma_id,
                ano_letivo=ano_letivo,
                periodo_letivo=periodo_letivo,
            )

            situacao_str = reg.get("situacao_final")
            situacao_enum = (
                SituacaoFinalPeriodo(situacao_str)
                if situacao_str
                else None
            )

            boletim_era_novo = False
            if boletim is None:
                boletim_era_novo = True
                boletim = BoletimPeriodo(
                    estudante_id=estudante.id,
                    escola_id=escola_id,
                    turma_id=turma_id,
                    ano_letivo=ano_letivo,
                    periodo_letivo=periodo_letivo,
                    idade=reg.get("idade"),
                    frequencia_percentual=reg.get("frequencia_percentual"),
                    faltas=reg.get("faltas"),
                    media_geral=reg.get("media_geral"),
                    notas_baixas=reg.get("notas_baixas"),
                    historico_reprovacoes=(
                        int(hist_reprov)
                        if hist_reprov is not None
                        else estudante.historico_reprovacoes
                    ),
                    participacao_recuperacao=reg.get(
                        "participacao_recuperacao"
                    ),
                    atrasos=reg.get("atrasos"),
                    situacao_final=situacao_enum,
                )
                db.add(boletim)
                db.flush()
            else:
                # Atualiza campos informados sem sobrescrever valores existentes por NULL indevidamente
                if reg.get("idade") is not None:
                    boletim.idade = int(reg["idade"])
                if (
                    reg.get("frequencia_percentual") is not None
                    and disc_id is None
                ):
                    boletim.frequencia_percentual = float(
                        reg["frequencia_percentual"]
                    )
                elif (
                    reg.get("frequencia_percentual") is not None
                    and boletim.frequencia_percentual is None
                ):
                    boletim.frequencia_percentual = float(
                        reg["frequencia_percentual"]
                    )
                if reg.get("faltas") is not None and disc_id is None:
                    boletim.faltas = int(reg["faltas"])
                elif reg.get("faltas") is not None and boletim.faltas is None:
                    boletim.faltas = int(reg["faltas"])
                if reg.get("media_geral") is not None:
                    boletim.media_geral = float(reg["media_geral"])
                if reg.get("notas_baixas") is not None:
                    boletim.notas_baixas = int(reg["notas_baixas"])
                if hist_reprov is not None:
                    boletim.historico_reprovacoes = int(hist_reprov)
                if reg.get("participacao_recuperacao") is not None:
                    boletim.participacao_recuperacao = bool(
                        reg["participacao_recuperacao"]
                    )
                if reg.get("atrasos") is not None:
                    boletim.atrasos = int(reg["atrasos"])
                # Regra crítica: uma situação final válida NÃO deve ser substituída por NULL
                if situacao_enum is not None:
                    boletim.situacao_final = situacao_enum
                db.flush()

            # 3. Se houver disciplina associada, insere ou atualiza NotaDisciplina
            if disc_id is not None:
                nota_disc_obj = EstudanteRepository.get_nota_disciplina(
                    db, boletim.id, disc_id
                )
                if nota_disc_obj is None:
                    nota_disc_obj = NotaDisciplina(
                        boletim_id=boletim.id,
                        disciplina_id=disc_id,
                        nota=reg.get("nota_disciplina"),
                        nota_prova=reg.get("nota_prova"),
                        nota_trabalho=reg.get("nota_trabalho"),
                        frequencia_percentual=reg.get(
                            "frequencia_percentual"
                        ),
                        faltas=reg.get("faltas"),
                        em_recuperacao=reg.get("participacao_recuperacao"),
                    )
                    db.add(nota_disc_obj)
                    db.flush()
                    inseridos += 1
                else:
                    if reg.get("nota_disciplina") is not None:
                        nota_disc_obj.nota = float(reg["nota_disciplina"])
                    if reg.get("nota_prova") is not None:
                        nota_disc_obj.nota_prova = float(reg["nota_prova"])
                    if reg.get("nota_trabalho") is not None:
                        nota_disc_obj.nota_trabalho = float(
                            reg["nota_trabalho"]
                        )
                    if reg.get("frequencia_percentual") is not None:
                        nota_disc_obj.frequencia_percentual = float(
                            reg["frequencia_percentual"]
                        )
                    if reg.get("faltas") is not None:
                        nota_disc_obj.faltas = int(reg["faltas"])
                    if reg.get("participacao_recuperacao") is not None:
                        nota_disc_obj.em_recuperacao = bool(
                            reg["participacao_recuperacao"]
                        )
                    db.flush()
                    atualizados += 1

                # Recalcula media_geral do boletim quando não informada explicitamente
                if boletim.media_geral is None:
                    stmt_notas = select(NotaDisciplina.nota).where(
                        NotaDisciplina.boletim_id == boletim.id,
                        NotaDisciplina.nota.is_not(None),
                    )
                    valores_notas = [
                        float(n)
                        for n in db.execute(stmt_notas).scalars().all()
                        if n is not None
                    ]
                    if valores_notas:
                        boletim.media_geral = round(
                            sum(valores_notas) / len(valores_notas), 2
                        )
                        db.flush()
            else:
                if boletim_era_novo:
                    inseridos += 1
                else:
                    atualizados += 1

        return inseridos, atualizados

    @staticmethod
    def _persistir_confirmacao_avaliacoes(
        db: Session,
        lote: LoteImportacao,
        usuario: Usuario,
        registros_previa: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """
        Persiste respostas de avaliações (Bloco B) de forma atômica e idempotente.
        NUNCA cria estudantes: revalida que cada estudante permanece ativo e vinculado à turma.
        """
        inseridos = 0
        atualizados = 0

        for reg in registros_previa:
            escola_id = uuid.UUID(str(reg["escola_id"]))
            turma_id = uuid.UUID(str(reg["turma_id"]))
            disc_id = uuid.UUID(str(reg["disciplina_id"]))
            codigo_avaliacao = str(reg["codigo_avaliacao"]).strip()
            titulo_avaliacao = str(reg["titulo_avaliacao"]).strip()
            periodo_letivo = str(reg["periodo_letivo"]).strip()
            data_avaliacao = date.fromisoformat(str(reg["data_avaliacao"]))
            codigo_questao = str(reg["codigo_questao"]).strip().upper()
            tipo_questao = TipoQuestao(str(reg["tipo_questao"]))
            valor_questao = round(float(reg["valor_questao"]), 2)
            alt_correta = reg.get("alternativa_correta")
            faixa_str = reg.get("faixa_dificuldade")
            faixa_enum = (
                FaixaDificuldadeQuestao(faixa_str) if faixa_str else None
            )
            topico = reg.get("topico")
            estudante_id = uuid.UUID(str(reg["estudante_id"]))
            codigo_anonimo = str(reg["codigo_anonimo"]).strip()

            # Revalida existência do estudante e vínculo na turma (nunca cria estudante)
            estudante = AvaliacaoService._resolver_estudante_na_turma(
                db=db,
                escola_id=escola_id,
                turma_id=turma_id,
                estudante_id=estudante_id,
                codigo_anonimo=codigo_anonimo,
            )

            # 1. Busca ou cria Avaliação
            avaliacao = AvaliacaoRepository.get_by_chave(
                db=db,
                escola_id=escola_id,
                turma_id=turma_id,
                disciplina_id=disc_id,
                codigo=codigo_avaliacao,
            )
            if avaliacao is None:
                avaliacao = Avaliacao(
                    codigo=codigo_avaliacao,
                    titulo=titulo_avaliacao,
                    escola_id=escola_id,
                    turma_id=turma_id,
                    disciplina_id=disc_id,
                    usuario_id=usuario.id,
                    periodo_letivo=periodo_letivo,
                    data_avaliacao=data_avaliacao,
                    status=StatusAvaliacao.PUBLICADA,
                    ativo=True,
                )
                db.add(avaliacao)
                db.flush()

            # 2. Busca ou cria Questão na avaliação
            questao = AvaliacaoRepository.get_questao_by_codigo(
                db, avaliacao.id, codigo_questao
            )
            if questao is None:
                questao = QuestaoAvaliacao(
                    avaliacao_id=avaliacao.id,
                    codigo_questao=codigo_questao,
                    tipo_questao=tipo_questao,
                    alternativa_correta=alt_correta,
                    valor_questao=valor_questao,
                    faixa_dificuldade=faixa_enum,
                    topico=topico,
                )
                db.add(questao)
                db.flush()
            else:
                # Proteção de integridade do gabarito e histórico (Fase 5 — Item 6.2 e 6.3):
                # Nunca sobrescreve silenciosamente tipo, valor ou gabarito de uma questão existente.
                alt_exist_norm = (
                    (questao.alternativa_correta or "").strip().upper() or None
                )
                alt_lote_norm = (alt_correta or "").strip().upper() or None
                if (
                    questao.tipo_questao != tipo_questao
                    or abs(round(float(questao.valor_questao), 2) - round(float(valor_questao), 2)) > 1e-6
                    or (
                        alt_exist_norm is not None
                        and alt_lote_norm is not None
                        and alt_exist_norm != alt_lote_norm
                    )
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Conflito de integridade ao confirmar lote na questão '{codigo_questao}': "
                            "tipo, valor ou gabarito divergem da questão já cadastrada no banco."
                        ),
                    )
                if faixa_enum is not None:
                    questao.faixa_dificuldade = faixa_enum
                if topico:
                    questao.topico = topico
                db.flush()

            # 3. Insere ou atualiza Resposta do estudante de forma idempotente
            alt_final, em_branco, nota_final, acertou_final = (
                AvaliacaoService.calcular_resultado_resposta(
                    questao=questao,
                    alternativa_marcada=reg.get("alternativa_marcada"),
                    em_branco_explicito=reg.get("em_branco"),
                    nota_obtida_informada=reg.get("nota_obtida"),
                    acertou_informado=None,
                )
            )

            resp = AvaliacaoRepository.get_resposta_by_questao_e_estudante(
                db, questao.id, estudante.id
            )
            if resp is None:
                resp = RespostaAvaliacao(
                    questao_id=questao.id,
                    estudante_id=estudante.id,
                    alternativa_marcada=alt_final,
                    em_branco=em_branco,
                    nota_obtida=nota_final,
                    acertou=acertou_final,
                )
                db.add(resp)
                db.flush()
                inseridos += 1
            else:
                resp.alternativa_marcada = alt_final
                resp.em_branco = em_branco
                resp.nota_obtida = nota_final
                resp.acertou = acertou_final
                db.add(resp)
                db.flush()
                atualizados += 1

        return inseridos, atualizados

    @staticmethod
    def _persistir_confirmacao_atividades(
        db: Session,
        lote: LoteImportacao,
        usuario: Usuario,
        registros_previa: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """
        Persiste atividades e entregas (Bloco C) de forma atômica e idempotente.
        Gera entregas esperadas para todos os estudantes elegíveis da turma de cada atividade
        e aplica as entregas informadas no lote, nunca criando estudantes e preservando
        notas ausentes como `None`.
        """
        inseridos = 0
        atualizados = 0
        atividades_com_esperadas_geradas: set[uuid.UUID] = set()

        for reg in registros_previa:
            escola_id = uuid.UUID(str(reg["escola_id"]))
            turma_id = uuid.UUID(str(reg["turma_id"]))
            disc_id = uuid.UUID(str(reg["disciplina_id"]))
            codigo_atividade = str(reg["codigo_atividade"]).strip()
            titulo_atividade = str(reg["titulo_atividade"]).strip()
            periodo_letivo = str(reg["periodo_letivo"]).strip()
            data_limite = date.fromisoformat(str(reg["data_limite"]))
            nota_maxima = (
                round(float(reg["nota_maxima"]), 2)
                if reg.get("nota_maxima") is not None
                else 10.0
            )
            estudante_id = uuid.UUID(str(reg["estudante_id"]))
            codigo_anonimo = str(reg["codigo_anonimo"]).strip()
            data_entrega_str = reg.get("data_entrega")
            data_entrega = (
                date.fromisoformat(str(data_entrega_str))
                if data_entrega_str
                else None
            )
            nota_val = (
                round(float(reg["nota"]), 2)
                if reg.get("nota") is not None
                else None
            )
            status_entrega = StatusEntregaAtividade(str(reg["status_entrega"]))
            era_insercao_prevista = reg.get("operacao_prevista") == "insercao"

            # Revalida existência do estudante e vínculo na turma (nunca cria estudante)
            estudante = EstudanteRepository.get_by_id(db, estudante_id)
            if (
                estudante is None
                or not estudante.ativo
                or estudante.escola_id != escola_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Estudante '{codigo_anonimo}' não encontrado ou inativo na escola no momento da confirmação."
                    ),
                )

            elegiveis_ids = {
                e.id
                for e in ParticipacaoRepository.list_estudantes_elegiveis_turma(
                    db, escola_id, turma_id
                )
            }
            if estudante.id not in elegiveis_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"O estudante '{codigo_anonimo}' não pertence à turma informada no momento da confirmação."
                    ),
                )

            # 1. Busca ou cria Atividade
            atividade = ParticipacaoRepository.get_atividade_by_chave(
                db=db,
                escola_id=escola_id,
                turma_id=turma_id,
                disciplina_id=disc_id,
                codigo=codigo_atividade,
            )
            if atividade is None:
                atividade = Atividade(
                    codigo=codigo_atividade,
                    titulo=titulo_atividade,
                    escola_id=escola_id,
                    turma_id=turma_id,
                    disciplina_id=disc_id,
                    usuario_id=usuario.id,
                    periodo_letivo=periodo_letivo,
                    data_limite=data_limite,
                    nota_maxima=nota_maxima,
                    status=StatusAtividade.ABERTA,
                    ativo=True,
                )
                db.add(atividade)
                db.flush()

            # 2. Estabelece entregas esperadas da turma (idempotente)
            if atividade.id not in atividades_com_esperadas_geradas:
                ParticipacaoService._executar_geracao_entregas_esperadas(
                    db=db,
                    atividade=atividade,
                )
                atividades_com_esperadas_geradas.add(atividade.id)

            # 3. Atualiza/insere a entrega do estudante mantendo nota=None quando ausente
            entrega = ParticipacaoRepository.get_entrega_by_atividade_e_estudante(
                db, atividade.id, estudante.id
            )
            if entrega is None:
                entrega = EntregaAtividade(
                    atividade_id=atividade.id,
                    estudante_id=estudante.id,
                    data_entrega=data_entrega,
                    nota=nota_val,
                    status_entrega=status_entrega,
                )
                db.add(entrega)
                db.flush()
                inseridos += 1
            else:
                entrega.data_entrega = data_entrega
                if nota_val is not None:
                    entrega.nota = nota_val
                entrega.status_entrega = status_entrega
                db.add(entrega)
                db.flush()
                if era_insercao_prevista:
                    inseridos += 1
                else:
                    atualizados += 1

        return inseridos, atualizados

    @staticmethod
    def _construir_resposta_previa(
        lote: LoteImportacao,
    ) -> LoteImportacaoPreviaResponse:
        relatorio_dict = lote.relatorio_validacao or {}
        relatorio_schema = RelatorioValidacaoSchema.model_validate(
            relatorio_dict
        )
        pode_confirmar = (
            lote.status == StatusLoteImportacao.VALIDADO
            and lote.quantidade_erros == 0
            and lote.registros_validos > 0
        )
        return LoteImportacaoPreviaResponse(
            id=lote.id,
            usuario_id=lote.usuario_id,
            escola_id=lote.escola_id,
            nome_arquivo=lote.nome_arquivo,
            tipo_importacao=lote.tipo_importacao,
            hash_arquivo=lote.hash_arquivo,
            status=lote.status,
            total_linhas=lote.total_linhas,
            registros_validos=lote.registros_validos,
            quantidade_erros=lote.quantidade_erros,
            quantidade_avisos=lote.quantidade_avisos,
            registros_novos=lote.registros_novos,
            registros_existentes=lote.registros_existentes,
            registros_inseridos=lote.registros_inseridos,
            registros_atualizados=lote.registros_atualizados,
            enviado_em=lote.enviado_em,
            validado_em=lote.validado_em,
            confirmado_em=lote.confirmado_em,
            atualizado_em=lote.atualizado_em,
            pode_confirmar=pode_confirmar,
            relatorio_validacao=relatorio_schema,
            previa_registros=lote.dados_previa or [],
        )

