"""
Motor de leitura, sanitização, verificação de privacidade (LGPD/RN01),
validação de escopo de autorização (gestor vs professor) e geração de prévia
para importação de datasets escolares do Vértice.
"""

from io import BytesIO
import re
from typing import Any, Optional
import unicodedata
import uuid

from fastapi import HTTPException, status
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.atribuicoes.models import ProfessorTurma
from app.modules.disciplinas.models import Disciplina
from app.modules.estudantes.models import SituacaoFinalPeriodo
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.importacao.schemas import (
    ItemProblemaValidacao,
    RelatorioValidacaoSchema,
)
from app.modules.turmas.models import Turma
from app.modules.usuarios.models import PapelUsuario, Usuario

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
EXTENSOES_SUPORTADAS = {".csv", ".xlsx"}

# Mapeamento de aliases normalizados para nomes canônicos de colunas
MAPA_COLUNAS_CANONICAS: dict[str, str] = {
    "codigo_anonimo": "codigo_anonimo",
    "id_estudante": "codigo_anonimo",
    "estudante_id": "codigo_anonimo",
    "identificador": "codigo_anonimo",
    "identificador_anonimo": "codigo_anonimo",
    "codigo_estudante": "codigo_anonimo",
    "turma": "turma",
    "nome_turma": "turma",
    "codigo_turma": "turma",
    "turma_id": "turma",
    "id_turma": "turma",
    "disciplina": "disciplina",
    "codigo_disciplina": "disciplina",
    "nome_disciplina": "disciplina",
    "disciplina_id": "disciplina",
    "id_disciplina": "disciplina",
    "ano_letivo": "ano_letivo",
    "ano": "ano_letivo",
    "periodo_letivo": "periodo_letivo",
    "periodo": "periodo_letivo",
    "bimestre": "periodo_letivo",
    "etapa": "periodo_letivo",
    "serie": "serie",
    "turno": "turno",
    "frequencia": "frequencia_percentual",
    "frequencia_percentual": "frequencia_percentual",
    "presenca": "frequencia_percentual",
    "faltas": "faltas",
    "quantidade_faltas": "faltas",
    "qtd_faltas": "faltas",
    "media_geral": "media_geral",
    "media": "media_geral",
    "nota": "nota",
    "nota_disciplina": "nota",
    "media_disciplina": "nota",
    "nota_prova": "nota_prova",
    "prova": "nota_prova",
    "nota_trabalho": "nota_trabalho",
    "trabalho": "nota_trabalho",
    "historico_reprovacoes": "historico_reprovacoes",
    "historico_reprovacao": "historico_reprovacoes",
    "reprovacoes": "historico_reprovacoes",
    "participacao_recuperacao": "participacao_recuperacao",
    "recuperacao": "participacao_recuperacao",
    "em_recuperacao": "participacao_recuperacao",
    "situacao_final": "situacao_final",
    "situacao": "situacao_final",
    "idade": "idade",
    "notas_baixas": "notas_baixas",
    "atrasos": "atrasos",
}

COLUNAS_OBRIGATORIAS = (
    "codigo_anonimo",
    "turma",
    "ano_letivo",
    "periodo_letivo",
)

# Colunas de identificação pessoal direta estritamente proibidas pela LGPD / RN01
PADROES_COLUNAS_PII_PROIBIDAS = {
    "nome",
    "nome_completo",
    "nome_estudante",
    "nome_aluno",
    "aluno",
    "cpf",
    "rg",
    "documento",
    "endereco",
    "logradouro",
    "telefone",
    "celular",
    "whatsapp",
    "email",
    "e_mail",
    "email_pessoal",
    "email_aluno",
    "email_estudante",
    "biometria",
    "digital",
    "data_nascimento",
    "nascimento",
    "filiacao",
    "nome_mae",
    "nome_pai",
    "responsavel",
}

# Colunas de autoria manual que nunca devem alterar o responsável pela importação
COLUNAS_AUTORIA_IGNORADAS = {
    "professor_id",
    "id_professor",
    "usuario_id",
    "id_usuario",
    "professor",
    "email_professor",
    "escola_id",
    "id_escola",
}

REGEX_CPF = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$")
REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REGEX_CODIGO_ANONIMO_VALIDO = re.compile(r"^[A-Za-z0-9_\-\.]{2,50}$")
# Nome pessoal composto apenas por letras e espaços (sem dígitos), ex: "Maria da Silva"
REGEX_NOME_PESSOAL = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ]+)+$")


def normalizar_identificador_coluna(nome: str) -> str:
    """Remove acentos, espaços extras e converte para snake_case minúsculo."""
    sem_acento = "".join(
        c
        for c in unicodedata.normalize("NFKD", str(nome).strip())
        if not unicodedata.combining(c)
    )
    limpo = re.sub(r"[^a-zA-Z0-9]+", "_", sem_acento).strip("_").lower()
    return limpo


def validar_arquivo_upload(
    nome_arquivo: Optional[str],
    conteudo_bytes: bytes,
) -> str:
    """
    Valida nome, extensão (.csv ou .xlsx) e limite de tamanho (10 MB).
    Retorna a extensão em minúsculo ou lança HTTPException adequada (400, 413, 415).
    """
    if not nome_arquivo or not nome_arquivo.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome do arquivo não informado.",
        )

    nome_limpo = nome_arquivo.strip()
    ext = ""
    if "." in nome_limpo:
        ext = "." + nome_limpo.rsplit(".", 1)[-1].lower()

    if ext not in EXTENSOES_SUPORTADAS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Formato de arquivo não suportado ('{ext or 'sem extensão'}'). "
                "Envie um arquivo .csv ou .xlsx."
            ),
        )

    if len(conteudo_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo enviado está vazio.",
        )

    if len(conteudo_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="O arquivo ultrapassa o tamanho máximo permitido de 10 MB.",
        )

    return ext


def ler_dataframe_bruto(conteudo_bytes: bytes, extensao: str) -> pd.DataFrame:
    """Carrega um DataFrame pandas preservando strings originais sem converter vazios em zero."""
    buffer = BytesIO(conteudo_bytes)
    try:
        if extensao == ".csv":
            try:
                df = pd.read_csv(
                    buffer,
                    sep=None,
                    engine="python",
                    encoding="utf-8-sig",
                    dtype=str,
                    keep_default_na=False,
                )
            except UnicodeDecodeError:
                buffer.seek(0)
                df = pd.read_csv(
                    buffer,
                    sep=None,
                    engine="python",
                    encoding="latin-1",
                    dtype=str,
                    keep_default_na=False,
                )
        else:
            df = pd.read_excel(
                buffer,
                dtype=str,
                engine="openpyxl",
                keep_default_na=False,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não foi possível processar o arquivo enviado. Verifique se o formato CSV/XLSX é válido.",
        ) from exc

    if df.empty or len(df.index) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo não contém registros de dados para importação.",
        )

    return df


def _parse_float_opcional(
    valor_raw: Any,
    campo: str,
    linha_num: int,
    minimo: float,
    maximo: float,
    problemas_valores: list[ItemProblemaValidacao],
) -> Optional[float]:
    texto = str(valor_raw).strip() if valor_raw is not None else ""
    if not texto or texto.lower() in ("null", "none", "nan", "-"):
        return None
    texto_num = texto.replace(",", ".")
    try:
        numero = float(texto_num)
    except ValueError:
        problemas_valores.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="valor_invalido",
                campo=campo,
                mensagem=f"Valor numérico inválido em '{campo}'. Esperado número entre {minimo} e {maximo}.",
            )
        )
        return None

    if numero < minimo or numero > maximo:
        problemas_valores.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="valor_invalido",
                campo=campo,
                mensagem=f"Valor fora do intervalo permitido em '{campo}' ({numero}). Deve estar entre {minimo} e {maximo}.",
            )
        )
        return None

    return round(numero, 2)


def _parse_int_opcional(
    valor_raw: Any,
    campo: str,
    linha_num: int,
    minimo: int,
    maximo: int,
    problemas_valores: list[ItemProblemaValidacao],
    obrigatorio: bool = False,
) -> Optional[int]:
    texto = str(valor_raw).strip() if valor_raw is not None else ""
    if not texto or texto.lower() in ("null", "none", "nan", "-"):
        if obrigatorio:
            problemas_valores.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo=campo,
                    mensagem=f"O campo obrigatório '{campo}' está vazio.",
                )
            )
        return None

    texto_num = texto.replace(",", ".")
    try:
        fl = float(texto_num)
        if not fl.is_integer():
            raise ValueError("Não é inteiro")
        numero = int(fl)
    except ValueError:
        problemas_valores.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="valor_invalido",
                campo=campo,
                mensagem=f"Valor inválido em '{campo}'. Esperado número inteiro.",
            )
        )
        return None

    if numero < minimo or numero > maximo:
        problemas_valores.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="valor_invalido",
                campo=campo,
                mensagem=f"Valor fora do intervalo permitido em '{campo}' ({numero}). Deve estar entre {minimo} e {maximo}.",
            )
        )
        return None

    return numero


def _parse_bool_opcional(
    valor_raw: Any,
    campo: str,
    linha_num: int,
    problemas_valores: list[ItemProblemaValidacao],
) -> Optional[bool]:
    texto = str(valor_raw).strip().lower() if valor_raw is not None else ""
    if not texto or texto in ("null", "none", "nan", "-"):
        return None
    if texto in ("true", "1", "sim", "s", "yes", "y", "verdadeiro"):
        return True
    if texto in ("false", "0", "nao", "não", "n", "no", "falso"):
        return False

    problemas_valores.append(
        ItemProblemaValidacao(
            linha=linha_num,
            categoria="valor_invalido",
            campo=campo,
            mensagem=f"Valor booleano inválido em '{campo}'. Use Sim/Não, True/False ou 1/0.",
        )
    )
    return None


def _parse_situacao_final_opcional(
    valor_raw: Any,
    linha_num: int,
    problemas_valores: list[ItemProblemaValidacao],
) -> Optional[str]:
    texto = str(valor_raw).strip() if valor_raw is not None else ""
    if not texto or texto.lower() in (
        "null",
        "none",
        "nan",
        "-",
        "em andamento",
        "cursando",
    ):
        return None

    mapa_situacoes = {
        "aprovado": SituacaoFinalPeriodo.APROVADO.value,
        "aprovada": SituacaoFinalPeriodo.APROVADO.value,
        "reprovado": SituacaoFinalPeriodo.REPROVADO.value,
        "reprovada": SituacaoFinalPeriodo.REPROVADO.value,
        "evadido": SituacaoFinalPeriodo.EVADIDO.value,
        "evadida": SituacaoFinalPeriodo.EVADIDO.value,
        "evasao": SituacaoFinalPeriodo.EVADIDO.value,
        "evasão": SituacaoFinalPeriodo.EVADIDO.value,
    }
    chave = texto.lower()
    if chave not in mapa_situacoes:
        problemas_valores.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="valor_invalido",
                campo="situacao_final",
                mensagem=(
                    "Valor inválido em 'situacao_final'. "
                    "Valores permitidos: Aprovado, Reprovado, Evadido ou vazio (em andamento)."
                ),
            )
        )
        return None

    return mapa_situacoes[chave]


def validar_codigo_anonimo(
    valor_raw: Any,
    linha_num: int,
    problemas_anonimizacao: list[ItemProblemaValidacao],
) -> Optional[str]:
    """
    Verifica se o identificador do estudante é um código anônimo válido e não contém
    CPF, e-mail ou nome pessoal completo (proteção de privacidade LGPD / RN01).
    Nunca inclui o dado pessoal sensível na mensagem de erro.
    """
    texto = str(valor_raw).strip() if valor_raw is not None else ""
    if not texto or texto.lower() in ("null", "none", "nan"):
        problemas_anonimizacao.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="anonimizacao",
                campo="codigo_anonimo",
                mensagem="Identificador anônimo do estudante ausente.",
            )
        )
        return None

    if REGEX_CPF.match(texto) or (texto.isdigit() and len(texto) == 11):
        problemas_anonimizacao.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="anonimizacao",
                campo="codigo_anonimo",
                mensagem=(
                    "Violação de privacidade detectada: o identificador do estudante "
                    "parece conter um CPF. Utilize apenas códigos anônimos (ex: EST-001)."
                ),
            )
        )
        return None

    if REGEX_EMAIL.match(texto):
        problemas_anonimizacao.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="anonimizacao",
                campo="codigo_anonimo",
                mensagem=(
                    "Violação de privacidade detectada: o identificador do estudante "
                    "contém um endereço de e-mail. Utilize apenas códigos anônimos."
                ),
            )
        )
        return None

    if REGEX_NOME_PESSOAL.match(texto):
        problemas_anonimizacao.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="anonimizacao",
                campo="codigo_anonimo",
                mensagem=(
                    "Violação de privacidade detectada: o identificador do estudante "
                    "parece ser um nome pessoal. Utilize apenas códigos anônimos alfanuméricos."
                ),
            )
        )
        return None

    if not REGEX_CODIGO_ANONIMO_VALIDO.match(texto):
        problemas_anonimizacao.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="anonimizacao",
                campo="codigo_anonimo",
                mensagem=(
                    "Formato de identificador anônimo inválido. Use entre 2 e 50 caracteres "
                    "alfanuméricos, hífens ou sublinhados (ex: EST-2026-001)."
                ),
            )
        )
        return None

    return texto


def _carregar_contexto_autorizacao(
    db: Session,
    usuario: Usuario,
) -> tuple[
    uuid.UUID,
    list[Turma],
    dict[uuid.UUID, set[Optional[uuid.UUID]]],
    dict[uuid.UUID, Disciplina],
]:
    """
    Determina a escola escopo do usuário autenticado, as turmas da escola,
    o mapa de vínculos `(turma_id -> {disciplina_id})` quando for professor,
    e o catálogo ativo de disciplinas.
    """
    stmt_discs = select(Disciplina).where(Disciplina.ativo.is_(True))
    disciplinas_ativas = list(db.execute(stmt_discs).scalars().all())
    mapa_disciplinas_por_id = {d.id: d for d in disciplinas_ativas}

    if usuario.papel == PapelUsuario.GESTOR:
        if usuario.escola_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: gestor não possui uma unidade escolar vinculada.",
            )
        escola_id = usuario.escola_id
        stmt_turmas = select(Turma).where(
            Turma.escola_id == escola_id,
            Turma.ativo.is_(True),
        )
        turmas_escola = list(db.execute(stmt_turmas).scalars().all())
        return escola_id, turmas_escola, {}, mapa_disciplinas_por_id

    if usuario.papel == PapelUsuario.PROFESSOR:
        stmt_atrib = (
            select(ProfessorTurma, Turma)
            .join(Turma, ProfessorTurma.turma_id == Turma.id)
            .where(
                ProfessorTurma.professor_id == usuario.id,
                Turma.ativo.is_(True),
            )
        )
        rows = db.execute(stmt_atrib).all()
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: professor não possui vínculos ativos com turmas para realizar importação.",
            )

        mapa_vinculos: dict[uuid.UUID, set[Optional[uuid.UUID]]] = {}
        escolas_vinculadas: set[uuid.UUID] = set()
        for atrib, turma in rows:
            mapa_vinculos.setdefault(turma.id, set()).add(atrib.disciplina_id)
            escolas_vinculadas.add(turma.escola_id)

        escola_id = (
            usuario.escola_id
            if usuario.escola_id is not None
            else sorted(escolas_vinculadas, key=str)[0]
        )

        # Carrega todas as turmas das escolas vinculadas e de todas as escolas para distinguir
        # "turma não vinculada" de "turma inexistente"
        stmt_todas_turmas = select(Turma).where(Turma.ativo.is_(True))
        todas_turmas = list(db.execute(stmt_todas_turmas).scalars().all())
        return escola_id, todas_turmas, mapa_vinculos, mapa_disciplinas_por_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado: seu perfil não possui autorização para importar datasets.",
    )


def _resolver_turma(
    valor_turma_raw: str,
    ano_letivo: Optional[int],
    serie_raw: Optional[str],
    turno_raw: Optional[str],
    usuario: Usuario,
    escola_id_contexto: uuid.UUID,
    turmas_candidatas: list[Turma],
    mapa_vinculos_prof: dict[uuid.UUID, set[Optional[uuid.UUID]]],
) -> tuple[Optional[Turma], Optional[str], Optional[str]]:
    """
    Localiza a turma a partir do identificador/nome no CSV.
    Retorna `(turma, categoria_erro, mensagem_erro)`.
    """
    chave = valor_turma_raw.strip()
    if not chave:
        return None, "valor_invalido", "Identificação da turma está vazia."

    # 1. Tenta casar por UUID exato
    correspondencias: list[Turma] = []
    try:
        turma_uuid = uuid.UUID(chave)
        correspondencias = [t for t in turmas_candidatas if t.id == turma_uuid]
    except ValueError:
        correspondencias = [
            t
            for t in turmas_candidatas
            if t.nome.strip().lower() == chave.lower()
        ]

    if ano_letivo is not None and len(correspondencias) > 1:
        filtradas_ano = [
            t for t in correspondencias if t.ano_letivo == ano_letivo
        ]
        if filtradas_ano:
            correspondencias = filtradas_ano

    if serie_raw and len(correspondencias) > 1:
        filtradas_serie = [
            t
            for t in correspondencias
            if t.serie.strip().lower() == serie_raw.strip().lower()
        ]
        if filtradas_serie:
            correspondencias = filtradas_serie

    if turno_raw and len(correspondencias) > 1:
        filtradas_turno = [
            t
            for t in correspondencias
            if t.turno.strip().lower() == turno_raw.strip().lower()
        ]
        if filtradas_turno:
            correspondencias = filtradas_turno

    if usuario.papel == PapelUsuario.GESTOR:
        # Gestor: verifica se a turma existe na própria escola
        na_escola = [
            t for t in correspondencias if t.escola_id == escola_id_contexto
        ]
        if not na_escola:
            # Verifica se existe em outra escola para reportar violação de autorização
            stmt_outra = select(Turma).where(
                (Turma.nome.ilike(chave))
                | (
                    Turma.id == uuid.UUID(chave)
                    if _is_uuid(chave)
                    else False
                )
            )
            _ = stmt_outra  # consulta feita pelo service se necessário
            return (
                None,
                "valor_invalido_ou_escopo",
                f"Turma '{chave}' não encontrada ou não pertence à escola vinculada ao gestor.",
            )
        if len(na_escola) > 1:
            return (
                None,
                "valor_invalido",
                f"Ambiguidade ao identificar a turma '{chave}'. Especifique ano_letivo, serie ou turno.",
            )
        return na_escola[0], None, None

    # Professor:
    if not correspondencias:
        return (
            None,
            "valor_invalido",
            f"Turma '{chave}' não encontrada no cadastro do sistema.",
        )

    # Prioriza verificar se alguma correspondência está vinculada ao professor
    vinculadas = [
        t for t in correspondencias if t.id in mapa_vinculos_prof
    ]
    if not vinculadas:
        return (
            None,
            "autorizacao",
            f"Professor não possui vínculo autorizado com a turma '{chave}'.",
        )
    if len(vinculadas) > 1:
        return (
            None,
            "valor_invalido",
            f"Múltiplas turmas vinculadas com o nome '{chave}'. Especifique ano_letivo, serie ou turno.",
        )
    return vinculadas[0], None, None


def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except ValueError:
        return False


def _resolver_disciplina(
    valor_disc_raw: Optional[str],
    turma: Turma,
    usuario: Usuario,
    mapa_vinculos_prof: dict[uuid.UUID, set[Optional[uuid.UUID]]],
    mapa_disciplinas_por_id: dict[uuid.UUID, Disciplina],
) -> tuple[Optional[Disciplina], Optional[str], Optional[str]]:
    """
    Localiza e valida a disciplina informada no CSV (ou infere de forma não ambígua
    a partir do vínculo único do professor na turma).
    Retorna `(disciplina, categoria_erro, mensagem_erro)`.
    """
    texto = valor_disc_raw.strip() if valor_disc_raw else ""

    if texto:
        # Procura por UUID, código ou nome
        disc_encontrada: Optional[Disciplina] = None
        if _is_uuid(texto):
            disc_encontrada = mapa_disciplinas_por_id.get(uuid.UUID(texto))
        if disc_encontrada is None:
            for d in mapa_disciplinas_por_id.values():
                if (
                    d.codigo.strip().lower() == texto.lower()
                    or d.nome.strip().lower() == texto.lower()
                ):
                    disc_encontrada = d
                    break

        if disc_encontrada is None:
            return (
                None,
                "valor_invalido",
                f"Disciplina '{texto}' não encontrada no catálogo ativo.",
            )

        if usuario.papel == PapelUsuario.PROFESSOR:
            discs_autorizadas = mapa_vinculos_prof.get(turma.id, set())
            if (
                None not in discs_autorizadas
                and disc_encontrada.id not in discs_autorizadas
            ):
                return (
                    None,
                    "autorizacao",
                    (
                        f"Professor não possui vínculo autorizado com a disciplina "
                        f"'{disc_encontrada.nome}' ({disc_encontrada.codigo}) na turma '{turma.nome}'."
                    ),
                )

        return disc_encontrada, None, None

    # Quando a coluna disciplina não está preenchida na linha:
    if usuario.papel == PapelUsuario.PROFESSOR:
        discs_autorizadas = mapa_vinculos_prof.get(turma.id, set())
        discs_nao_nulas = [d_id for d_id in discs_autorizadas if d_id is not None]
        if len(discs_nao_nulas) == 1 and None not in discs_autorizadas:
            # Inferência segura e não ambígua a partir do vínculo único do professor na turma
            disc_inferida = mapa_disciplinas_por_id.get(discs_nao_nulas[0])
            return disc_inferida, None, None
        if len(discs_nao_nulas) > 1:
            return (
                None,
                "valor_invalido",
                (
                    f"Ambiguidade de disciplina na turma '{turma.nome}': o professor possui vínculo "
                    "com múltiplas disciplinas nesta turma. Informe a coluna 'disciplina' no arquivo."
                ),
            )
        # Vínculo geral na turma (disciplina_id IS NULL)
        return None, None, None

    # Gestor sem disciplina especificada -> boletim geral do período
    return None, None, None


def processar_e_validar_dataframe(
    db: Session,
    df: pd.DataFrame,
    usuario: Usuario,
) -> tuple[uuid.UUID, RelatorioValidacaoSchema, list[dict[str, Any]]]:
    """
    Executa todas as verificações de cabeçalho, privacidade (PII), tipos, intervalos,
    duplicidades, vínculos de turma/disciplina e classifica registros em novos vs existentes.
    Não persiste nenhum dado acadêmico no banco de dados.
    """
    escola_id_contexto, turmas_candidatas, mapa_vinculos_prof, mapa_disciplinas_por_id = (
        _carregar_contexto_autorizacao(db, usuario)
    )

    # Verifica também todas as turmas do banco para detectar tentativa de gestor importar de outra escola
    stmt_todas_turmas_banco = select(Turma).where(Turma.ativo.is_(True))
    todas_turmas_banco = list(db.execute(stmt_todas_turmas_banco).scalars().all())

    relatorio = RelatorioValidacaoSchema(total_linhas=len(df.index))
    previa_registros: list[dict[str, Any]] = []

    # 1. Mapeamento e inspeção das colunas do cabeçalho
    colunas_originais = list(df.columns)
    mapa_orig_para_canon: dict[str, str] = {}
    colunas_pii_detectadas: list[str] = []
    colunas_autoria_detectadas: list[str] = []

    for col_orig in colunas_originais:
        norm = normalizar_identificador_coluna(col_orig)
        if norm in PADROES_COLUNAS_PII_PROIBIDAS:
            colunas_pii_detectadas.append(str(col_orig))
            continue
        if norm in COLUNAS_AUTORIA_IGNORADAS:
            colunas_autoria_detectadas.append(str(col_orig))
            continue
        if norm in MAPA_COLUNAS_CANONICAS:
            mapa_orig_para_canon[col_orig] = MAPA_COLUNAS_CANONICAS[norm]

    if colunas_pii_detectadas:
        relatorio.colunas_proibidas_pii = colunas_pii_detectadas
        for col_pii in colunas_pii_detectadas:
            prob = ItemProblemaValidacao(
                linha=1,
                categoria="pii_proibido",
                campo=col_pii,
                mensagem=(
                    f"Coluna pessoal proibida detectada no cabeçalho ('{col_pii}'). "
                    "O Vértice opera apenas com dados anonimizados (LGPD / RN01)."
                ),
            )
            relatorio.problemas_anonimizacao.append(prob)
            relatorio.erros.append(prob)

    if colunas_autoria_detectadas:
        for col_aut in colunas_autoria_detectadas:
            relatorio.avisos.append(
                ItemProblemaValidacao(
                    linha=1,
                    categoria="autoria_ignorada",
                    campo=col_aut,
                    mensagem=(
                        f"A coluna '{col_aut}' foi ignorada: o usuário responsável pela importação "
                        "e o escopo escolar são determinados exclusivamente pela sessão autenticada."
                    ),
                )
            )

    colunas_canonicas_presentes = set(mapa_orig_para_canon.values())
    faltantes = [
        col for col in COLUNAS_OBRIGATORIAS if col not in colunas_canonicas_presentes
    ]
    if faltantes:
        relatorio.colunas_ausentes = faltantes
        for col_faltante in faltantes:
            prob = ItemProblemaValidacao(
                linha=1,
                categoria="coluna_ausente",
                campo=col_faltante,
                mensagem=f"Coluna obrigatória ausente no arquivo: '{col_faltante}'.",
            )
            relatorio.erros.append(prob)

    # Se faltam colunas obrigatórias ou há colunas PII proibidas no cabeçalho, encerra validação estrutural
    if relatorio.colunas_ausentes or relatorio.colunas_proibidas_pii:
        relatorio.quantidade_erros = len(relatorio.erros)
        relatorio.quantidade_avisos = len(relatorio.avisos)
        return escola_id_contexto, relatorio, []

    # Inverte mapeamento canônico -> coluna original
    canon_para_orig: dict[str, str] = {}
    for orig, canon in mapa_orig_para_canon.items():
        if canon not in canon_para_orig:
            canon_para_orig[canon] = orig

    chaves_vistas_no_arquivo: dict[tuple[str, uuid.UUID, Optional[uuid.UUID], int, str], int] = {}
    turmas_identificadas_set: set[str] = set()
    disciplinas_identificadas_set: set[str] = set()
    escola_inferida_professor: Optional[uuid.UUID] = None

    for idx, row in df.iterrows():
        linha_num = int(idx) + 2  # Cabeçalho é linha 1
        erros_linha_inicio = (
            len(relatorio.problemas_autorizacao)
            + len(relatorio.valores_invalidos)
            + len(relatorio.duplicidades)
            + len(relatorio.problemas_anonimizacao)
        )

        # 1. Código anônimo do estudante
        codigo_anonimo = validar_codigo_anonimo(
            row.get(canon_para_orig["codigo_anonimo"], ""),
            linha_num,
            relatorio.problemas_anonimizacao,
        )

        # 2. Ano letivo e Período letivo
        ano_letivo = _parse_int_opcional(
            row.get(canon_para_orig["ano_letivo"], ""),
            "ano_letivo",
            linha_num,
            minimo=2000,
            maximo=2100,
            problemas_valores=relatorio.valores_invalidos,
            obrigatorio=True,
        )

        periodo_raw = str(row.get(canon_para_orig["periodo_letivo"], "")).strip()
        if not periodo_raw or periodo_raw.lower() in ("null", "none", "nan"):
            relatorio.valores_invalidos.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo="periodo_letivo",
                    mensagem="O campo obrigatório 'periodo_letivo' está vazio.",
                )
            )
            periodo_letivo: Optional[str] = None
        elif len(periodo_raw) > 30:
            relatorio.valores_invalidos.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo="periodo_letivo",
                    mensagem="O campo 'periodo_letivo' excede 30 caracteres.",
                )
            )
            periodo_letivo = None
        else:
            periodo_letivo = periodo_raw

        # 3. Resolução e autorização da Turma
        turma_raw = str(row.get(canon_para_orig["turma"], "")).strip()
        serie_raw = (
            str(row.get(canon_para_orig["serie"], "")).strip()
            if "serie" in canon_para_orig
            else None
        )
        turno_raw = (
            str(row.get(canon_para_orig["turno"], "")).strip()
            if "turno" in canon_para_orig
            else None
        )

        turma_obj: Optional[Turma] = None
        if usuario.papel == PapelUsuario.GESTOR:
            turma_obj, cat_erro, msg_erro = _resolver_turma(
                valor_turma_raw=turma_raw,
                ano_letivo=ano_letivo,
                serie_raw=serie_raw,
                turno_raw=turno_raw,
                usuario=usuario,
                escola_id_contexto=escola_id_contexto,
                turmas_candidatas=turmas_candidatas,
                mapa_vinculos_prof=mapa_vinculos_prof,
            )
            if turma_obj is None and msg_erro:
                # Distingue se a turma pertence a outra escola (violação de autorização) ou não existe
                existe_outra_escola = any(
                    (
                        t.nome.strip().lower() == turma_raw.lower()
                        or (_is_uuid(turma_raw) and t.id == uuid.UUID(turma_raw))
                    )
                    and t.escola_id != escola_id_contexto
                    for t in todas_turmas_banco
                )
                if existe_outra_escola:
                    relatorio.problemas_autorizacao.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="autorizacao",
                            campo="turma",
                            mensagem=f"Acesso negado: a turma '{turma_raw}' pertence a outra unidade escolar.",
                        )
                    )
                else:
                    relatorio.valores_invalidos.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="valor_invalido",
                            campo="turma",
                            mensagem=f"Turma '{turma_raw}' não encontrada na unidade escolar.",
                        )
                    )
        else:
            turma_obj, cat_erro, msg_erro = _resolver_turma(
                valor_turma_raw=turma_raw,
                ano_letivo=ano_letivo,
                serie_raw=serie_raw,
                turno_raw=turno_raw,
                usuario=usuario,
                escola_id_contexto=escola_id_contexto,
                turmas_candidatas=turmas_candidatas,
                mapa_vinculos_prof=mapa_vinculos_prof,
            )
            if turma_obj is None and msg_erro:
                if cat_erro == "autorizacao":
                    relatorio.problemas_autorizacao.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="autorizacao",
                            campo="turma",
                            mensagem=msg_erro,
                        )
                    )
                else:
                    relatorio.valores_invalidos.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="valor_invalido",
                            campo="turma",
                            mensagem=msg_erro,
                        )
                    )

        if (
            turma_obj is not None
            and ano_letivo is not None
            and turma_obj.ano_letivo != ano_letivo
        ):
            relatorio.valores_invalidos.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo="ano_letivo",
                    mensagem=(
                        f"Inconsistência: o ano_letivo informado ({ano_letivo}) diverge do ano letivo "
                        f"da turma '{turma_obj.nome}' ({turma_obj.ano_letivo})."
                    ),
                )
            )

        # 4. Resolução e autorização da Disciplina
        disc_raw = (
            str(row.get(canon_para_orig["disciplina"], "")).strip()
            if "disciplina" in canon_para_orig
            else None
        )
        disc_obj: Optional[Disciplina] = None
        if turma_obj is not None:
            disc_obj, cat_disc, msg_disc = _resolver_disciplina(
                valor_disc_raw=disc_raw,
                turma=turma_obj,
                usuario=usuario,
                mapa_vinculos_prof=mapa_vinculos_prof,
                mapa_disciplinas_por_id=mapa_disciplinas_por_id,
            )
            if msg_disc:
                if cat_disc == "autorizacao":
                    relatorio.problemas_autorizacao.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="autorizacao",
                            campo="disciplina",
                            mensagem=msg_disc,
                        )
                    )
                else:
                    relatorio.valores_invalidos.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="valor_invalido",
                            campo="disciplina",
                            mensagem=msg_disc,
                        )
                    )
        elif disc_raw:
            # Mesmo que a turma tenha falhado, valida se a disciplina existe no catálogo
            disc_temp: Optional[Disciplina] = None
            if _is_uuid(disc_raw):
                disc_temp = mapa_disciplinas_por_id.get(uuid.UUID(disc_raw))
            if disc_temp is None:
                for d in mapa_disciplinas_por_id.values():
                    if (
                        d.codigo.strip().lower() == disc_raw.lower()
                        or d.nome.strip().lower() == disc_raw.lower()
                    ):
                        disc_temp = d
                        break
            if disc_temp is None:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="disciplina",
                        mensagem=f"Disciplina '{disc_raw}' não encontrada no catálogo ativo.",
                    )
                )

        # 5. Campos numéricos, booleanos e situação final
        frequencia = (
            _parse_float_opcional(
                row.get(canon_para_orig["frequencia_percentual"]),
                "frequencia_percentual",
                linha_num,
                0.0,
                100.0,
                relatorio.valores_invalidos,
            )
            if "frequencia_percentual" in canon_para_orig
            else None
        )

        faltas = (
            _parse_int_opcional(
                row.get(canon_para_orig["faltas"]),
                "faltas",
                linha_num,
                0,
                1000,
                relatorio.valores_invalidos,
            )
            if "faltas" in canon_para_orig
            else None
        )

        media_geral = (
            _parse_float_opcional(
                row.get(canon_para_orig["media_geral"]),
                "media_geral",
                linha_num,
                0.0,
                10.0,
                relatorio.valores_invalidos,
            )
            if "media_geral" in canon_para_orig
            else None
        )

        nota_disc = (
            _parse_float_opcional(
                row.get(canon_para_orig["nota"]),
                "nota",
                linha_num,
                0.0,
                10.0,
                relatorio.valores_invalidos,
            )
            if "nota" in canon_para_orig
            else None
        )

        nota_prova = (
            _parse_float_opcional(
                row.get(canon_para_orig["nota_prova"]),
                "nota_prova",
                linha_num,
                0.0,
                10.0,
                relatorio.valores_invalidos,
            )
            if "nota_prova" in canon_para_orig
            else None
        )

        nota_trabalho = (
            _parse_float_opcional(
                row.get(canon_para_orig["nota_trabalho"]),
                "nota_trabalho",
                linha_num,
                0.0,
                10.0,
                relatorio.valores_invalidos,
            )
            if "nota_trabalho" in canon_para_orig
            else None
        )

        historico_reprovacoes = (
            _parse_int_opcional(
                row.get(canon_para_orig["historico_reprovacoes"]),
                "historico_reprovacoes",
                linha_num,
                0,
                50,
                relatorio.valores_invalidos,
            )
            if "historico_reprovacoes" in canon_para_orig
            else None
        )

        participacao_recuperacao = (
            _parse_bool_opcional(
                row.get(canon_para_orig["participacao_recuperacao"]),
                "participacao_recuperacao",
                linha_num,
                relatorio.valores_invalidos,
            )
            if "participacao_recuperacao" in canon_para_orig
            else None
        )

        situacao_final = (
            _parse_situacao_final_opcional(
                row.get(canon_para_orig["situacao_final"]),
                linha_num,
                relatorio.valores_invalidos,
            )
            if "situacao_final" in canon_para_orig
            else None
        )

        idade = (
            _parse_int_opcional(
                row.get(canon_para_orig["idade"]),
                "idade",
                linha_num,
                5,
                100,
                relatorio.valores_invalidos,
            )
            if "idade" in canon_para_orig
            else None
        )

        notas_baixas = (
            _parse_int_opcional(
                row.get(canon_para_orig["notas_baixas"]),
                "notas_baixas",
                linha_num,
                0,
                50,
                relatorio.valores_invalidos,
            )
            if "notas_baixas" in canon_para_orig
            else None
        )

        atrasos = (
            _parse_int_opcional(
                row.get(canon_para_orig["atrasos"]),
                "atrasos",
                linha_num,
                0,
                1000,
                relatorio.valores_invalidos,
            )
            if "atrasos" in canon_para_orig
            else None
        )

        # Se há uma disciplina associada e o usuário informou apenas `media_geral` (sem coluna `nota`),
        # mapeia a nota para a disciplina mantendo também o boletim consistente
        if disc_obj is not None and nota_disc is None and media_geral is not None:
            nota_disc = media_geral

        # 6. Detecção de duplicidade dentro do próprio arquivo
        if (
            codigo_anonimo is not None
            and turma_obj is not None
            and ano_letivo is not None
            and periodo_letivo is not None
        ):
            chave_linha = (
                codigo_anonimo,
                turma_obj.id,
                disc_obj.id if disc_obj else None,
                ano_letivo,
                periodo_letivo,
            )
            if chave_linha in chaves_vistas_no_arquivo:
                linha_anterior = chaves_vistas_no_arquivo[chave_linha]
                relatorio.duplicidades.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="duplicidade",
                        campo="codigo_anonimo",
                        mensagem=(
                            f"Registro duplicado no arquivo para o estudante '{codigo_anonimo}' "
                            f"na turma '{turma_obj.nome}' e período '{periodo_letivo}' "
                            f"(já informado na linha {linha_anterior})."
                        ),
                    )
                )
            else:
                chaves_vistas_no_arquivo[chave_linha] = linha_num

        erros_linha_fim = (
            len(relatorio.problemas_autorizacao)
            + len(relatorio.valores_invalidos)
            + len(relatorio.duplicidades)
            + len(relatorio.problemas_anonimizacao)
        )

        if (
            erros_linha_fim == erros_linha_inicio
            and codigo_anonimo is not None
            and turma_obj is not None
            and ano_letivo is not None
            and periodo_letivo is not None
        ):
            if escola_inferida_professor is None:
                escola_inferida_professor = turma_obj.escola_id

            turmas_identificadas_set.add(turma_obj.nome)
            if disc_obj is not None:
                disciplinas_identificadas_set.add(
                    f"{disc_obj.nome} ({disc_obj.codigo})"
                )

            # Verifica se o registro corresponde a dado já existente no banco ou se é novo
            estudante_existente = EstudanteRepository.get_by_escola_e_codigo(
                db, turma_obj.escola_id, codigo_anonimo
            )
            existe_registro = False
            if estudante_existente is not None:
                boletim_existente = EstudanteRepository.get_boletim_by_chave(
                    db=db,
                    estudante_id=estudante_existente.id,
                    escola_id=turma_obj.escola_id,
                    turma_id=turma_obj.id,
                    ano_letivo=ano_letivo,
                    periodo_letivo=periodo_letivo,
                )
                if boletim_existente is not None:
                    if disc_obj is not None:
                        nota_existente = EstudanteRepository.get_nota_disciplina(
                            db, boletim_existente.id, disc_obj.id
                        )
                        existe_registro = nota_existente is not None
                    else:
                        existe_registro = True

            if existe_registro:
                relatorio.registros_existentes += 1
                operacao_prevista = "atualizacao"
            else:
                relatorio.registros_novos += 1
                operacao_prevista = "insercao"

            relatorio.registros_validos += 1
            previa_registros.append(
                {
                    "linha": linha_num,
                    "codigo_anonimo": codigo_anonimo,
                    "escola_id": str(turma_obj.escola_id),
                    "turma_id": str(turma_obj.id),
                    "turma_nome": turma_obj.nome,
                    "disciplina_id": str(disc_obj.id) if disc_obj else None,
                    "disciplina_codigo": disc_obj.codigo if disc_obj else None,
                    "disciplina_nome": disc_obj.nome if disc_obj else None,
                    "ano_letivo": ano_letivo,
                    "periodo_letivo": periodo_letivo,
                    "idade": idade,
                    "frequencia_percentual": frequencia,
                    "faltas": faltas,
                    "media_geral": media_geral,
                    "nota_disciplina": nota_disc,
                    "nota_prova": nota_prova,
                    "nota_trabalho": nota_trabalho,
                    "notas_baixas": notas_baixas,
                    "historico_reprovacoes": historico_reprovacoes,
                    "participacao_recuperacao": participacao_recuperacao,
                    "atrasos": atrasos,
                    "situacao_final": situacao_final,
                    "operacao_prevista": operacao_prevista,
                }
            )

    # Consolida todas as listas de erros no relatório
    relatorio.erros = (
        list(relatorio.problemas_autorizacao)
        + list(relatorio.problemas_anonimizacao)
        + list(relatorio.valores_invalidos)
        + list(relatorio.duplicidades)
    )
    relatorio.quantidade_erros = len(relatorio.erros)
    relatorio.quantidade_avisos = len(relatorio.avisos)
    relatorio.turmas_identificadas = sorted(turmas_identificadas_set)
    relatorio.disciplinas_identificadas = sorted(disciplinas_identificadas_set)

    escola_final = (
        escola_inferida_professor
        if usuario.papel == PapelUsuario.PROFESSOR
        and escola_inferida_professor is not None
        else escola_id_contexto
    )
    return escola_final, relatorio, previa_registros

