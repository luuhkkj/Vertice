"""
Camada de regras de negócio para o módulo de Integração Preditiva (Fase 7).

Responsabilidades:
- Gerenciar credenciais técnicas de serviço dedicadas ao pipeline de ML (hash SHA-256).
- Receber previsões unitárias e em lote atômico com prevenção estrita de Data Leakage,
  validação referencial e idempotência append-only.
- Disponibilizar consultas, histórico por estudante e distribuição agregada por faixa de
  risco sob isolamento rigoroso de perfil, escola, turma e disciplina, com política
  explícita de versão única de modelo.
"""

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import secrets
from typing import Any, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import require_acesso_pedagogico
from app.integrations.prediction.leakage import (
    CAMPOS_PROIBIDOS_PREDICAO,
    CATALOGO_VARIAVEIS_PREDITIVAS,
    ResultadoValidacaoLeakage,
    validar_variaveis_contra_leakage,
)
from app.integrations.prediction.models import (
    CredencialIntegracaoPredicao,
    FaixaRisco,
    PrevisaoRisco,
    TipoPrevisao,
)
from app.integrations.prediction.repository import PredictionRepository
from app.integrations.prediction.schemas import (
    AVISO_METODOLOGICO_PADRAO,
    CatalogoVariaveisResponse,
    CredencialIntegracaoCreate,
    CredencialIntegracaoCriadaResponse,
    CredencialIntegracaoResponse,
    FaixaDistribuicaoPrevisaoSchema,
    HistoricoPrevisoesEstudanteResponse,
    PrevisaoLoteResponse,
    PrevisaoRecebimentoItem,
    PrevisaoRecebimentoLoteRequest,
    PrevisaoResponse,
    ResumoPrevisoesRiscoResponse,
    ValidarVariaveisRequest,
    VersaoModeloDisponivelSchema,
)
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import BoletimPeriodo, Estudante
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.estudantes.service import EstudanteService
from app.modules.indicadores.repository import IndicadoresRepository
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario

PREFIXO_TOKEN_SERVICO = "vtx_ml_"
ORDEM_FAIXAS_RISCO: tuple[FaixaRisco, ...] = (
    FaixaRisco.BAIXO,
    FaixaRisco.MODERADO,
    FaixaRisco.ALTO,
    FaixaRisco.CRITICO,
)


def _garantir_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hash_token_servico(token_bruto: str) -> str:
    return hashlib.sha256(token_bruto.encode("utf-8")).hexdigest()


def _calcular_assinatura_idempotencia(
    estudante_id: uuid.UUID,
    turma_id: Optional[uuid.UUID],
    ano_letivo: int,
    periodo_letivo: str,
    tipo_previsao: TipoPrevisao,
    modelo_nome: str,
    modelo_versao: str,
    gerado_em: datetime,
    lote_externo_id: Optional[str],
) -> str:
    gerado_utc = _garantir_utc(gerado_em).isoformat()
    base = "|".join(
        [
            str(estudante_id),
            str(turma_id) if turma_id else "",
            str(ano_letivo),
            periodo_letivo.strip(),
            tipo_previsao.value,
            modelo_nome.strip(),
            modelo_versao.strip(),
            gerado_utc,
            (lote_externo_id or "").strip(),
        ]
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class PredictionService:
    """Regras de negócio de credenciais, ingestão e consulta de previsões de risco."""

    # ------------------------------------------------------------------
    # Contrato de variáveis e validação anti-leakage
    # ------------------------------------------------------------------
    @staticmethod
    def obter_catalogo_variaveis() -> CatalogoVariaveisResponse:
        return CatalogoVariaveisResponse(
            politica_anti_leakage_ativa=True,
            campos_proibidos_base=dict(CAMPOS_PROIBIDOS_PREDICAO),
            variaveis_elegiveis=list(CATALOGO_VARIAVEIS_PREDITIVAS),
        )

    @staticmethod
    def inspecionar_variaveis_entrada(
        dados: ValidarVariaveisRequest,
    ) -> ResultadoValidacaoLeakage:
        return validar_variaveis_contra_leakage(
            dados.variaveis,
            campos_proibidos_extras=dados.campos_proibidos_extras,
            lancar_excecao=False,
        )

    # ------------------------------------------------------------------
    # Credenciais dedicadas de integração preditiva (somente Admin)
    # ------------------------------------------------------------------
    @staticmethod
    def criar_credencial_integracao(
        db: Session,
        dados: CredencialIntegracaoCreate,
        usuario_admin: Usuario,
    ) -> CredencialIntegracaoCriadaResponse:
        if usuario_admin.papel != PapelUsuario.ADMINISTRADOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: apenas administradores podem emitir credenciais preditivas.",
            )

        if dados.escola_id is not None:
            escola = db.execute(
                select(Escola).where(Escola.id == dados.escola_id)
            ).scalar_one_or_none()
            if escola is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Escola vinculada à credencial não encontrada.",
                )

        segredo_puro = f"{PREFIXO_TOKEN_SERVICO}{secrets.token_urlsafe(32)}"
        prefixo = segredo_puro[:14]
        hash_chave = _hash_token_servico(segredo_puro)

        expira_utc = _garantir_utc(dados.expira_em) if dados.expira_em else None

        cred = CredencialIntegracaoPredicao(
            nome=dados.nome,
            prefixo_chave=prefixo,
            hash_chave=hash_chave,
            escola_id=dados.escola_id,
            modelos_permitidos=dados.modelos_permitidos,
            criado_por_usuario_id=usuario_admin.id,
            ativo=True,
            expira_em=expira_utc,
        )
        PredictionRepository.create_credencial(db, cred)
        db.commit()
        db.refresh(cred)

        return CredencialIntegracaoCriadaResponse(
            id=cred.id,
            nome=cred.nome,
            prefixo_chave=cred.prefixo_chave,
            escola_id=cred.escola_id,
            modelos_permitidos=cred.modelos_permitidos,
            criado_por_usuario_id=cred.criado_por_usuario_id,
            ativo=cred.ativo,
            expira_em=cred.expira_em,
            ultimo_uso_em=cred.ultimo_uso_em,
            criado_em=cred.criado_em,
            atualizado_em=cred.atualizado_em,
            chave_secreta=segredo_puro,
        )

    @staticmethod
    def listar_credenciais_integracao(
        db: Session,
        usuario_admin: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        apenas_ativas: Optional[bool] = None,
    ) -> list[CredencialIntegracaoResponse]:
        if usuario_admin.papel != PapelUsuario.ADMINISTRADOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: apenas administradores podem listar credenciais preditivas.",
            )
        regs = PredictionRepository.list_credenciais(
            db=db,
            escola_id=escola_id,
            apenas_ativas=apenas_ativas,
        )
        return [CredencialIntegracaoResponse.model_validate(r) for r in regs]

    @staticmethod
    def revogar_credencial_integracao(
        db: Session,
        credencial_id: uuid.UUID,
        usuario_admin: Usuario,
    ) -> CredencialIntegracaoResponse:
        if usuario_admin.papel != PapelUsuario.ADMINISTRADOR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: apenas administradores podem revogar credenciais preditivas.",
            )
        cred = PredictionRepository.get_credencial_by_id(db, credencial_id)
        if cred is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credencial de integração preditiva não encontrada.",
            )
        cred.ativo = False
        db.add(cred)
        db.commit()
        db.refresh(cred)
        return CredencialIntegracaoResponse.model_validate(cred)

    @staticmethod
    def autenticar_credencial_servico(
        db: Session,
        token_bruto: Optional[str],
    ) -> CredencialIntegracaoPredicao:
        """
        Valida o segredo técnico de serviço de predição.
        Tokens comuns de usuário (JWT) NÃO autorizam envio de previsões e são rejeitados com 403.
        """
        if not token_bruto or not token_bruto.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Credencial técnica de integração preditiva obrigatória no cabeçalho `X-Service-Token`."
                ),
            )

        token_limpo = token_bruto.strip()
        if not token_limpo.startswith(PREFIXO_TOKEN_SERVICO):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Acesso negado: o recebimento de previsões exige credencial técnica dedicada "
                    "de serviço preditivo; tokens comuns de usuário não autorizam esta operação."
                ),
            )

        cred = PredictionRepository.get_credencial_by_hash(
            db, _hash_token_servico(token_limpo)
        )
        if cred is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencial de serviço preditivo inválida.",
            )
        if not cred.ativo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Credencial de serviço preditivo revogada.",
            )
        if cred.expira_em is not None:
            expira = _garantir_utc(cred.expira_em)
            if expira <= datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Credencial de serviço preditivo expirada.",
                )
        return cred

    # ------------------------------------------------------------------
    # Ingestão unitária e em lote atômico
    # ------------------------------------------------------------------
    @staticmethod
    def _serializar_previsao(p: PrevisaoRisco) -> PrevisaoResponse:
        return PrevisaoResponse(
            id=p.id,
            estudante_id=p.estudante_id,
            codigo_anonimo=p.estudante.codigo_anonimo if p.estudante else None,
            escola_id=p.escola_id,
            turma_id=p.turma_id,
            turma_nome=p.turma.nome if p.turma else None,
            ano_letivo=p.ano_letivo,
            periodo_letivo=p.periodo_letivo,
            tipo_previsao=p.tipo_previsao,
            pontuacao_risco=round(float(p.pontuacao_risco), 6),
            faixa_risco=p.faixa_risco,
            politica_classificacao_versao=p.politica_classificacao_versao,
            modelo_nome=p.modelo_nome,
            modelo_versao=p.modelo_versao,
            gerado_em=_garantir_utc(p.gerado_em),
            recebido_em=_garantir_utc(p.recebido_em),
            lote_externo_id=p.lote_externo_id,
            assinatura_idempotencia=p.assinatura_idempotencia,
            metadados_tecnicos=p.metadados_tecnicos,
            aviso_metodologico=AVISO_METODOLOGICO_PADRAO,
        )

    @staticmethod
    def _validar_e_construir_entidade(
        db: Session,
        item: PrevisaoRecebimentoItem,
        credencial: CredencialIntegracaoPredicao,
        lote_externo_id_pai: Optional[str] = None,
    ) -> PrevisaoRisco:
        # 1) Bloqueio rigoroso contra Data Leakage e PII em variáveis e metadados
        if item.variaveis_utilizadas is not None:
            validar_variaveis_contra_leakage(
                item.variaveis_utilizadas,
                lancar_excecao=True,
            )
        if item.metadados_tecnicos is not None:
            validar_variaveis_contra_leakage(
                item.metadados_tecnicos,
                lancar_excecao=True,
            )

        # 2) Autorização da credencial para o modelo informado
        if (
            credencial.modelos_permitidos is not None
            and item.modelo_nome not in credencial.modelos_permitidos
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Credencial de serviço não autorizada a enviar previsões para o modelo `{item.modelo_nome}`."
                ),
            )

        # 3) Resolução e validação de estudante anonimizado
        estudante: Optional[Estudante] = None
        if item.estudante_id is not None:
            estudante = EstudanteRepository.get_by_id(db, item.estudante_id)
            if estudante is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Estudante `{item.estudante_id}` não encontrado.",
                )
            if item.escola_id is not None and estudante.escola_id != item.escola_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Estudante informado não pertence à `escola_id` especificada.",
                )
            if (
                item.codigo_anonimo is not None
                and estudante.codigo_anonimo != item.codigo_anonimo
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="`codigo_anonimo` divergente para o `estudante_id` informado.",
                )
        else:
            assert item.escola_id is not None and item.codigo_anonimo is not None
            estudante = EstudanteRepository.get_by_escola_e_codigo(
                db, item.escola_id, item.codigo_anonimo
            )
            if estudante is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Estudante `{item.codigo_anonimo}` não encontrado na escola informada."
                    ),
                )

        if not estudante.ativo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Estudante `{estudante.codigo_anonimo}` encontra-se inativo.",
            )

        escola_id_final = estudante.escola_id
        if (
            credencial.escola_id is not None
            and credencial.escola_id != escola_id_final
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Credencial de serviço não autorizada para a escola do estudante informado.",
            )

        # 4) Validação de turma e coerência com ano/período letivo
        if item.turma_id is not None:
            turma = db.execute(
                select(Turma).where(Turma.id == item.turma_id)
            ).scalar_one_or_none()
            if turma is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Turma `{item.turma_id}` não encontrada.",
                )
            if turma.escola_id != escola_id_final:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Turma informada não pertence à escola do estudante.",
                )
            if turma.ano_letivo != item.ano_letivo:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Ano letivo `{item.ano_letivo}` incompatível com a turma `{turma.nome}` ({turma.ano_letivo})."
                    ),
                )
            # Se o estudante já possui boletins no mesmo ano/período, verifica vínculo coerente
            boletins_periodo = [
                b
                for b in (estudante.boletins or [])
                if b.ano_letivo == item.ano_letivo
                and b.periodo_letivo == item.periodo_letivo
            ]
            if boletins_periodo and not any(
                b.turma_id == item.turma_id for b in boletins_periodo
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "Estudante não possui vínculo registrado na turma informada para o ano/período letivo."
                    ),
                )

        lote_resolvido = item.lote_externo_id or lote_externo_id_pai
        assinatura = _calcular_assinatura_idempotencia(
            estudante_id=estudante.id,
            turma_id=item.turma_id,
            ano_letivo=item.ano_letivo,
            periodo_letivo=item.periodo_letivo,
            tipo_previsao=item.tipo_previsao,
            modelo_nome=item.modelo_nome,
            modelo_versao=item.modelo_versao,
            gerado_em=item.gerado_em,
            lote_externo_id=lote_resolvido,
        )

        return PrevisaoRisco(
            estudante_id=estudante.id,
            escola_id=escola_id_final,
            turma_id=item.turma_id,
            ano_letivo=item.ano_letivo,
            periodo_letivo=item.periodo_letivo,
            tipo_previsao=item.tipo_previsao,
            pontuacao_risco=item.pontuacao_risco,
            faixa_risco=item.faixa_risco,
            politica_classificacao_versao=item.politica_classificacao_versao,
            modelo_nome=item.modelo_nome,
            modelo_versao=item.modelo_versao,
            gerado_em=_garantir_utc(item.gerado_em),
            lote_externo_id=lote_resolvido,
            assinatura_idempotencia=assinatura,
            metadados_tecnicos=item.metadados_tecnicos,
            credencial_integracao_id=credencial.id,
            enviado_por_usuario_id=None,
        )

    @staticmethod
    def registrar_previsao_unica(
        db: Session,
        item: PrevisaoRecebimentoItem,
        credencial: CredencialIntegracaoPredicao,
    ) -> PrevisaoResponse:
        lote = PredictionService.registrar_lote_previsoes(
            db=db,
            dados=PrevisaoRecebimentoLoteRequest(
                lote_externo_id=item.lote_externo_id,
                itens=[item],
            ),
            credencial=credencial,
        )
        return lote.itens[0]

    @staticmethod
    def registrar_lote_previsoes(
        db: Session,
        dados: PrevisaoRecebimentoLoteRequest,
        credencial: CredencialIntegracaoPredicao,
    ) -> PrevisaoLoteResponse:
        """
        Processa lote de previsões de forma estritamente atômica:
        qualquer falha de validação, leakage, escopo ou duplicidade aborta todo o lote.
        """
        entidades: list[PrevisaoRisco] = []
        assinaturas_lote: set[str] = set()

        for item in dados.itens:
            ent = PredictionService._validar_e_construir_entidade(
                db=db,
                item=item,
                credencial=credencial,
                lote_externo_id_pai=dados.lote_externo_id,
            )
            if ent.assinatura_idempotencia in assinaturas_lote:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Lote rejeitado: há previsões duplicadas dentro do mesmo envio.",
                )
            assinaturas_lote.add(ent.assinatura_idempotencia)
            entidades.append(ent)

        existentes = PredictionRepository.buscar_assinaturas_existentes(
            db, list(assinaturas_lote)
        )
        if existentes:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Previsão duplicada detectada (`assinatura_idempotencia` já registrada). "
                    "Para preservar o histórico append-only, atualizações devem usar novo timestamp, "
                    "nova versão de modelo ou novo `lote_externo_id`."
                ),
            )

        try:
            PredictionRepository.add_all_previsoes(db, entidades)
            PredictionRepository.registrar_uso_credencial(db, credencial)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflito de integridade/duplicidade ao persistir lote de previsões.",
            ) from exc

        carregadas = PredictionRepository.list_previsoes_by_ids(
            db, [e.id for e in entidades]
        )
        mapa = {p.id: p for p in carregadas}
        ordenadas = [mapa[e.id] for e in entidades if e.id in mapa]
        return PrevisaoLoteResponse(
            quantidade_recebida=len(ordenadas),
            lote_externo_id=dados.lote_externo_id,
            itens=[PredictionService._serializar_previsao(p) for p in ordenadas],
        )

    # ------------------------------------------------------------------
    # Resolução de escopo pedagógico autorizado para leitura
    # ------------------------------------------------------------------
    @staticmethod
    def _resolver_escopo_leitura(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
    ) -> tuple[list[uuid.UUID], Optional[list[uuid.UUID]]]:
        """
        Retorna `(escolas_autorizadas, estudante_ids_autorizados)` respeitando:
        - `ADMINISTRADOR` bloqueado em rotas pedagógicas (`require_acesso_pedagogico` / 403).
        - `GESTOR`: restrito à própria escola; se `turma_id` ou `disciplina_id` forem informados,
          filtra estudantes via boletins daquela turma/disciplina.
        - `PROFESSOR`: restrito às turmas/disciplinas em `ProfessorTurma`.
        """
        if usuario.papel not in {PapelUsuario.GESTOR, PapelUsuario.PROFESSOR}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Acesso negado: apenas gestores e professores possuem acesso pedagógico às previsões."
                ),
            )

        escolas_aut = IndicadoresRepository.validar_filtros_escopo(
            db=db,
            usuario=usuario,
            escola_id=escola_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
        )
        if not escolas_aut:
            return [], []
        escolas_lista = sorted(escolas_aut)

        if usuario.papel == PapelUsuario.GESTOR:
            if disciplina_id is None:
                return escolas_lista, None
            boletins, _ = IndicadoresRepository.listar_boletins_escopo(
                db=db,
                usuario=usuario,
                escolas_autorizadas=escolas_aut,
                turma_id=turma_id,
                disciplina_id=disciplina_id,
            )
            ids_est = sorted({b.estudante_id for b in boletins})
            return escolas_lista, ids_est

        # PROFESSOR: deriva estritamente dos boletins autorizados ao professor
        boletins_prof, _ = IndicadoresRepository.listar_boletins_escopo(
            db=db,
            usuario=usuario,
            escolas_autorizadas=escolas_aut,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
        )
        ids_prof = sorted({b.estudante_id for b in boletins_prof})
        return escolas_lista, ids_prof

    # ------------------------------------------------------------------
    # Consultas de previsões e agregação com política explícita de versão única
    # ------------------------------------------------------------------
    @staticmethod
    def listar_previsoes(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        tipo_previsao: Optional[TipoPrevisao] = None,
        faixa_risco: Optional[FaixaRisco] = None,
        modelo_nome: Optional[str] = None,
        modelo_versao: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PrevisaoResponse]:
        escolas_aut, estudantes_aut = PredictionService._resolver_escopo_leitura(
            db=db,
            usuario=usuario,
            escola_id=escola_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
        )
        if not escolas_aut or (estudantes_aut is not None and not estudantes_aut):
            return []

        registros = PredictionRepository.list_previsoes_escopo(
            db=db,
            escola_ids=escolas_aut,
            estudante_ids=estudantes_aut,
            turma_id=turma_id,
            ano_letivo=ano_letivo,
            periodo_letivo=periodo_letivo,
            tipo_previsao=tipo_previsao,
            faixa_risco=faixa_risco,
            modelo_nome=modelo_nome,
            modelo_versao=modelo_versao,
            skip=skip,
            limit=limit,
        )
        return [PredictionService._serializar_previsao(r) for r in registros]

    @staticmethod
    def obter_historico_estudante(
        db: Session,
        estudante_id: uuid.UUID,
        usuario: Usuario,
        tipo_previsao: Optional[TipoPrevisao] = None,
        modelo_nome: Optional[str] = None,
        modelo_versao: Optional[str] = None,
    ) -> HistoricoPrevisoesEstudanteResponse:
        if usuario.papel not in {PapelUsuario.GESTOR, PapelUsuario.PROFESSOR}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: perfil sem acesso pedagógico ao histórico preditivo.",
            )

        estudante = EstudanteRepository.get_by_id(db, estudante_id)
        if estudante is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estudante não encontrado.",
            )

        try:
            EstudanteService.obter_estudante_com_historico(
                db=db,
                estudante_id=estudante_id,
                usuario_solicitante=usuario,
            )
        except HTTPException as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: estudante fora do escopo autorizado.",
            ) from exc

        registros = PredictionRepository.list_previsoes_escopo(
            db=db,
            escola_ids=[estudante.escola_id],
            estudante_ids=[estudante.id],
            tipo_previsao=tipo_previsao,
            modelo_nome=modelo_nome,
            modelo_versao=modelo_versao,
        )
        itens = [PredictionService._serializar_previsao(r) for r in registros]
        return HistoricoPrevisoesEstudanteResponse(
            estudante_id=estudante.id,
            codigo_anonimo=estudante.codigo_anonimo,
            escola_id=estudante.escola_id,
            total_previsoes=len(itens),
            previsao_mais_recente=itens[0] if itens else None,
            historico=itens,
            aviso_metodologico=AVISO_METODOLOGICO_PADRAO,
        )

    @staticmethod
    def _agregar_versao_unica(
        registros_escopo: list[PrevisaoRisco],
        modelo_nome: Optional[str] = None,
        modelo_versao: Optional[str] = None,
    ) -> ResumoPrevisoesRiscoResponse:
        """
        Aplica política explícita de versão única:
        - Lista todas as versões `(modelo_nome, modelo_versao, tipo_previsao)` disponíveis no recorte.
        - Seleciona a versão solicitada ou a mais recente (por maior `gerado_em`/`recebido_em`).
        - Considera apenas a previsão mais recente de cada estudante nessa versão, evitando
          misturar previsões de versões diferentes ou contar o mesmo estudante em duplicidade.
        """
        if not registros_escopo:
            return ResumoPrevisoesRiscoResponse(possui_previsoes=False)

        agrup_versoes: dict[tuple[str, str, str], list[PrevisaoRisco]] = defaultdict(list)
        for p in registros_escopo:
            chave = (p.modelo_nome, p.modelo_versao, p.tipo_previsao.value)
            agrup_versoes[chave].append(p)

        versoes_disponiveis: list[VersaoModeloDisponivelSchema] = []
        for (m_nome, m_versao, t_prev), regs in agrup_versoes.items():
            ultima = max(_garantir_utc(r.gerado_em) for r in regs)
            versoes_disponiveis.append(
                VersaoModeloDisponivelSchema(
                    modelo_nome=m_nome,
                    modelo_versao=m_versao,
                    tipo_previsao=t_prev,
                    total_registros=len(regs),
                    ultima_previsao_em=ultima,
                )
            )
        versoes_disponiveis.sort(key=lambda v: v.ultima_previsao_em, reverse=True)

        # Seleciona registros filtrados pela versão solicitada ou pela versão mais recente
        filtrados = list(registros_escopo)
        if modelo_nome and modelo_nome.strip():
            filtrados = [r for r in filtrados if r.modelo_nome == modelo_nome.strip()]
        if modelo_versao and modelo_versao.strip():
            filtrados = [
                r for r in filtrados if r.modelo_versao == modelo_versao.strip()
            ]

        if not filtrados:
            return ResumoPrevisoesRiscoResponse(
                possui_previsoes=False,
                total_previsoes_registradas=len(registros_escopo),
                versoes_disponiveis=versoes_disponiveis,
            )

        # Ordenado do mais recente para o mais antigo: primeiro registro define versão vigente
        filtrados.sort(
            key=lambda r: (
                _garantir_utc(r.gerado_em),
                _garantir_utc(r.recebido_em),
            ),
            reverse=True,
        )
        nome_vigente = filtrados[0].modelo_nome
        versao_vigente = filtrados[0].modelo_versao
        tipo_vigente = filtrados[0].tipo_previsao

        da_versao = [
            r
            for r in filtrados
            if r.modelo_nome == nome_vigente
            and r.modelo_versao == versao_vigente
            and r.tipo_previsao == tipo_vigente
        ]

        # Última previsão por estudante dentro dessa versão única
        por_estudante: dict[uuid.UUID, PrevisaoRisco] = {}
        for r in da_versao:
            if r.estudante_id not in por_estudante:
                por_estudante[r.estudante_id] = r

        contagens: dict[FaixaRisco, int] = {f: 0 for f in ORDEM_FAIXAS_RISCO}
        for r in por_estudante.values():
            contagens[r.faixa_risco] += 1

        total_est = len(por_estudante)
        distribuicao: list[FaixaDistribuicaoPrevisaoSchema] = []
        for faixa in ORDEM_FAIXAS_RISCO:
            qtd = contagens[faixa]
            pct = round((qtd / total_est) * 100.0, 2) if total_est > 0 else 0.0
            distribuicao.append(
                FaixaDistribuicaoPrevisaoSchema(
                    faixa=faixa.value,
                    quantidade=qtd,
                    percentual=pct,
                )
            )

        ultima_dt = max(_garantir_utc(r.gerado_em) for r in da_versao)
        return ResumoPrevisoesRiscoResponse(
            possui_previsoes=total_est > 0,
            total_previsoes_registradas=len(registros_escopo),
            total_estudantes_avaliados=total_est,
            modelo_nome_vigente=nome_vigente,
            modelo_versao_vigente=versao_vigente,
            ultima_previsao_em=ultima_dt,
            distribuicao_faixas=distribuicao,
            versoes_disponiveis=versoes_disponiveis,
            aviso_metodologico=AVISO_METODOLOGICO_PADRAO,
        )

    @staticmethod
    def obter_resumo_previsoes(
        db: Session,
        usuario: Usuario,
        escola_id: Optional[uuid.UUID] = None,
        turma_id: Optional[uuid.UUID] = None,
        disciplina_id: Optional[uuid.UUID] = None,
        ano_letivo: Optional[int] = None,
        periodo_letivo: Optional[str] = None,
        tipo_previsao: Optional[TipoPrevisao] = None,
        modelo_nome: Optional[str] = None,
        modelo_versao: Optional[str] = None,
    ) -> ResumoPrevisoesRiscoResponse:
        escolas_aut, estudantes_aut = PredictionService._resolver_escopo_leitura(
            db=db,
            usuario=usuario,
            escola_id=escola_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
        )
        if not escolas_aut or (estudantes_aut is not None and not estudantes_aut):
            return ResumoPrevisoesRiscoResponse(possui_previsoes=False)

        registros_base = PredictionRepository.list_previsoes_escopo(
            db=db,
            escola_ids=escolas_aut,
            estudante_ids=estudantes_aut,
            turma_id=turma_id,
            ano_letivo=ano_letivo,
            periodo_letivo=periodo_letivo,
            tipo_previsao=tipo_previsao,
        )
        return PredictionService._agregar_versao_unica(
            registros_base,
            modelo_nome=modelo_nome,
            modelo_versao=modelo_versao,
        )
