"""
Serviço de negócio para Importação de Datasets Escolares em Duas Etapas (Fase 3).
Etapa 1: Upload, validação completa, verificação de escopo e geração de prévia (sem gravar dados acadêmicos).
Etapa 2: Revalidação de identidade/escopo e confirmação em transação atômica com rollback integral em falhas.
"""

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import garantir_escopo_importacao_usuario
from app.modules.atribuicoes.models import ProfessorTurma
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
    ler_dataframe_bruto,
    processar_e_validar_dataframe,
    validar_arquivo_upload,
)
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
    ) -> LoteImportacaoPreviaResponse:
        """
        Etapa 1: Valida extensão, tamanho, colunas, anonimização e vínculos do usuário autenticado.
        Registra o lote de auditoria (`validado` ou `com_erros`), mas NÃO persiste nenhum
        dado de estudante, boletim ou nota no banco de dados.
        """
        garantir_escopo_importacao_usuario(usuario_autenticado)

        extensao = validar_arquivo_upload(nome_arquivo, conteudo_bytes)
        hash_sha256 = sha256(conteudo_bytes).hexdigest()
        df = ler_dataframe_bruto(conteudo_bytes, extensao)

        agora = datetime.now(timezone.utc)
        escola_id, relatorio, previa_registros = processar_e_validar_dataframe(
            db=db,
            df=df,
            usuario=usuario_autenticado,
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
            tipo_importacao=TipoImportacao.DADOS_ESCOLARES,
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
        registros_previa: list[dict[str, Any]],
    ) -> None:
        """
        Revalida no momento da confirmação se o usuário autenticado continua possuindo
        todos os vínculos de escola, turma e disciplina exigidos pelos registros do lote.
        """
        garantir_escopo_importacao_usuario(usuario)

        if usuario.papel == PapelUsuario.GESTOR:
            escola_gestor = usuario.escola_id
            for reg in registros_previa:
                turma_id = uuid.UUID(str(reg["turma_id"]))
                stmt_t = select(Turma).where(
                    Turma.id == turma_id,
                    Turma.ativo.is_(True),
                )
                turma = db.execute(stmt_t).scalar_one_or_none()
                if turma is None or turma.escola_id != escola_gestor:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Autorização negada na confirmação: a turma '{reg.get('turma_nome')}' "
                            "não está ativa ou não pertence à escola vinculada ao gestor."
                        ),
                    )
            return

        if usuario.papel == PapelUsuario.PROFESSOR:
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
                disc_id_raw = reg.get("disciplina_id")
                disc_id = uuid.UUID(str(disc_id_raw)) if disc_id_raw else None

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
            db, usuario_autenticado, registros_previa
        )

        inseridos = 0
        atualizados = 0

        try:
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

