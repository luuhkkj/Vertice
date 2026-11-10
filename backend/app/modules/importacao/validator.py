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
from app.modules.escolas.models import Escola
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

# Colunas exatas de identificação pessoal direta estritamente proibidas pela LGPD / RN01
PADROES_COLUNAS_PII_PROIBIDAS = {
    "nome",
    "nome_completo",
    "nome_estudante",
    "estudante_nome",
    "nome_do_estudante",
    "nome_aluno",
    "aluno_nome",
    "nome_do_aluno",
    "nome_discente",
    "discente_nome",
    "primeiro_nome",
    "sobrenome",
    "nome_social",
    "aluno",
    "estudante",
    "discente",
    "cpf",
    "cpf_aluno",
    "aluno_cpf",
    "cpf_estudante",
    "estudante_cpf",
    "nr_cpf",
    "numero_cpf",
    "rg",
    "rg_aluno",
    "documento",
    "cns",
    "nis",
    "inep_aluno",
    "endereco",
    "endereco_aluno",
    "logradouro",
    "cep",
    "bairro",
    "telefone",
    "telefone_aluno",
    "celular",
    "celular_aluno",
    "whatsapp",
    "contato",
    "email",
    "e_mail",
    "email_pessoal",
    "email_aluno",
    "aluno_email",
    "email_estudante",
    "estudante_email",
    "biometria",
    "digital",
    "data_nascimento",
    "dt_nascimento",
    "nascimento",
    "filiacao",
    "nome_mae",
    "mae",
    "nome_pai",
    "pai",
    "responsavel",
    "nome_responsavel",
    "cpf_responsavel",
    "telefone_responsavel",
}

# Tokens que, quando presentes em qualquer coluna que não seja alias técnico válido
# (como nome_turma / nome_disciplina / email_professor), indicam coluna de dado pessoal
TOKENS_PII_SENSIVEIS = {
    "cpf",
    "rg",
    "endereco",
    "logradouro",
    "telefone",
    "celular",
    "whatsapp",
    "biometria",
    "filiacao",
    "nascimento",
    "sobrenome",
    "mae",
    "pai",
    "responsavel",
}

# Colunas de autoria manual que nunca devem alterar o responsável pela importação
COLUNAS_AUTORIA_IGNORADAS = {
    "professor_id",
    "id_professor",
    "usuario_id",
    "id_usuario",
    "professor",
    "nome_professor",
    "professor_nome",
    "email_professor",
    "professor_email",
    "escola_id",
    "id_escola",
}

REGEX_CPF_EXATO = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}[-\.]?\d{2}$")
REGEX_CPF_EMBUTIDO = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
REGEX_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
REGEX_TELEFONE_BR = re.compile(
    r"^(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]\d{4}$"
)
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


def _eh_coluna_pii_proibida(norm_col: str) -> bool:
    """
    Avalia se um nome de coluna normalizado representa informação pessoal proibida (PII).
    Reconhece tanto nomes exatos quanto combinações por tokens (ex: `aluno_nome`, `cpf_do_estudante`,
    `email_pessoal_aluno`, `telefone_contato`), preservando colunas técnicas legítimas
    (`nome_turma`, `nome_disciplina`, `email_professor`).
    """
    if norm_col in MAPA_COLUNAS_CANONICAS or norm_col in COLUNAS_AUTORIA_IGNORADAS:
        return False
    if norm_col in PADROES_COLUNAS_PII_PROIBIDAS:
        return True

    tokens = set(norm_col.split("_"))
    if tokens & TOKENS_PII_SENSIVEIS:
        return True
    if "nome" in tokens and tokens not in (
        {"nome", "turma"},
        {"turma", "nome"},
        {"nome", "disciplina"},
        {"disciplina", "nome"},
        {"nome", "escola"},
        {"escola", "nome"},
    ):
        return True
    if ("email" in tokens or "mail" in tokens) and "professor" not in tokens:
        return True

    return False


def _valor_contem_padrao_pii(valor_raw: Any) -> Optional[str]:
    """
    Verifica se o valor textual de qualquer célula contém padrão explícito de CPF,
    e-mail ou telefone pessoal. Retorna o tipo de padrão detectado ('CPF', 'e-mail', 'telefone')
    sem incluir o valor sensível.
    """
    texto = str(valor_raw).strip() if valor_raw is not None else ""
    if not texto or texto.lower() in ("null", "none", "nan", "-"):
        return None
    if REGEX_CPF_EXATO.match(texto) or REGEX_CPF_EMBUTIDO.search(texto) or (
        texto.isdigit() and len(texto) == 11
    ):
        return "CPF"
    if REGEX_EMAIL.search(texto):
        return "endereço de e-mail"
    if REGEX_TELEFONE_BR.match(texto):
        return "número de telefone"
    return None


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
    CPF, e-mail, telefone ou nome pessoal completo (proteção de privacidade LGPD / RN01).
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

    tipo_pii = _valor_contem_padrao_pii(texto)
    if tipo_pii is not None:
        problemas_anonimizacao.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="anonimizacao",
                campo="codigo_anonimo",
                mensagem=(
                    f"Violação de privacidade detectada em 'codigo_anonimo': o valor apresenta "
                    f"padrão de {tipo_pii}. Utilize apenas códigos anônimos (ex: EST-001)."
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
                    "Violação de privacidade detectada em 'codigo_anonimo': o valor "
                    "parece ser um nome pessoal. Utilize apenas códigos anônimos alfanuméricos."
                ),
            )
        )
        return None

    # Exige ao menos um caractere numérico no código anônimo para evitar nomes simples (ex: "Maria")
    if texto.isalpha():
        problemas_anonimizacao.append(
            ItemProblemaValidacao(
                linha=linha_num,
                categoria="anonimizacao",
                campo="codigo_anonimo",
                mensagem=(
                    "Formato de identificador anônimo inválido em 'codigo_anonimo': "
                    "identificadores puramente alfabéticos não são permitidos por risco de exposição "
                    "de nomes pessoais. Utilize um código alfanumérico (ex: EST-001)."
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
    set[uuid.UUID],
    list[Turma],
    dict[uuid.UUID, set[Optional[uuid.UUID]]],
    dict[uuid.UUID, Disciplina],
]:
    """
    Determina o conjunto de escolas autorizadas para o usuário autenticado,
    as turmas ativas, o mapa de vínculos `(turma_id -> {disciplina_id})` quando for professor,
    e o catálogo ativo de disciplinas.

    Regras de escopo escolar do professor:
    - O professor só pode importar para turmas ativas e pertencentes a escolas ativas
      onde possua vínculo válido em `ProfessorTurma`.
    - Se `usuario.escola_id` estiver definido no cadastro do professor, apenas turmas
      dessa escola específica são consideradas autorizadas.
    - Se `usuario.escola_id` for `None`, o professor pode possuir vínculos em uma ou mais
      escolas ativas (`escolas_autorizadas`), mas cada lote de importação deve referenciar
      turmas de uma única escola de forma inequívoca.
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
        stmt_escola = select(Escola).where(
            Escola.id == usuario.escola_id,
            Escola.ativo.is_(True),
        )
        escola_ativa = db.execute(stmt_escola).scalar_one_or_none()
        if escola_ativa is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: a unidade escolar vinculada ao gestor não está ativa.",
            )

        escola_id = usuario.escola_id
        stmt_turmas = select(Turma).where(
            Turma.escola_id == escola_id,
            Turma.ativo.is_(True),
        )
        turmas_escola = list(db.execute(stmt_turmas).scalars().all())
        return {escola_id}, turmas_escola, {}, mapa_disciplinas_por_id

    if usuario.papel == PapelUsuario.PROFESSOR:
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
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado: professor não possui vínculos ativos com turmas para realizar importação.",
            )

        mapa_vinculos: dict[uuid.UUID, set[Optional[uuid.UUID]]] = {}
        escolas_autorizadas: set[uuid.UUID] = set()
        for atrib, turma, _escola in rows:
            # Se o professor tiver escola_id definida no seu perfil, restringe seus vínculos
            # de importação exclusivamente às turmas daquela escola
            if usuario.escola_id is not None and turma.escola_id != usuario.escola_id:
                continue
            # Se o vínculo especifica uma disciplina, exige que ela esteja ativa no catálogo
            if (
                atrib.disciplina_id is not None
                and atrib.disciplina_id not in mapa_disciplinas_por_id
            ):
                continue
            mapa_vinculos.setdefault(turma.id, set()).add(atrib.disciplina_id)
            escolas_autorizadas.add(turma.escola_id)

        if not mapa_vinculos or not escolas_autorizadas:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Acesso negado: professor não possui vínculos válidos na escola autorizada "
                    "para realizar importação."
                ),
            )

        stmt_todas_turmas = select(Turma).where(Turma.ativo.is_(True))
        todas_turmas = list(db.execute(stmt_todas_turmas).scalars().all())
        return escolas_autorizadas, todas_turmas, mapa_vinculos, mapa_disciplinas_por_id

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
    escolas_autorizadas: set[uuid.UUID],
    turmas_candidatas: list[Turma],
    mapa_vinculos_prof: dict[uuid.UUID, set[Optional[uuid.UUID]]],
) -> tuple[Optional[Turma], Optional[str], Optional[str]]:
    """
    Localiza a turma a partir do identificador/nome no CSV e garante explicitamente
    que ela pertence a uma escola autorizada e ao escopo de vínculos do usuário.
    Retorna `(turma, categoria_erro, mensagem_erro)`.
    """
    chave = valor_turma_raw.strip()
    if not chave:
        return None, "valor_invalido", "Identificação da turma está vazia."

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
        na_escola = [
            t for t in correspondencias if t.escola_id in escolas_autorizadas
        ]
        if not na_escola:
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
            f"Turma '{chave}' não encontrada no cadastro ativo do sistema.",
        )

    # Filtra turmas nas quais o professor possui vínculo E que pertencem a escola autorizada
    vinculadas_autorizadas = [
        t
        for t in correspondencias
        if t.id in mapa_vinculos_prof and t.escola_id in escolas_autorizadas
    ]
    if not vinculadas_autorizadas:
        # Distingue tentativa de importar turma de outra escola sem autorização vs turma sem vínculo
        em_outra_escola = any(
            t.escola_id not in escolas_autorizadas for t in correspondencias
        )
        if em_outra_escola:
            return (
                None,
                "autorizacao",
                (
                    f"Acesso negado: a turma '{chave}' pertence a uma unidade escolar "
                    "fora do escopo autorizado do professor."
                ),
            )
        return (
            None,
            "autorizacao",
            f"Professor não possui vínculo autorizado com a turma '{chave}'.",
        )

    if len(vinculadas_autorizadas) > 1:
        return (
            None,
            "valor_invalido",
            (
                f"Ambiguidade ao identificar a turma '{chave}': o professor possui vínculo com "
                "múltiplas turmas de mesmo nome (ou em escolas distintas). Utilize o UUID da turma "
                "ou especifique ano_letivo, serie e turno."
            ),
        )
    return vinculadas_autorizadas[0], None, None


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
        # Vínculo geral explícito na turma (disciplina_id IS NULL)
        return None, None, None

    return None, None, None


def processar_e_validar_dataframe(
    db: Session,
    df: pd.DataFrame,
    usuario: Usuario,
) -> tuple[uuid.UUID, RelatorioValidacaoSchema, list[dict[str, Any]]]:
    """
    Executa todas as verificações de cabeçalho, privacidade (PII), tipos, intervalos,
    duplicidades, vínculos de turma/disciplina e consistência de escola única por lote.
    Não persiste nenhum dado acadêmico no banco de dados.
    """
    escolas_autorizadas, turmas_candidatas, mapa_vinculos_prof, mapa_disciplinas_por_id = (
        _carregar_contexto_autorizacao(db, usuario)
    )

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
        if _eh_coluna_pii_proibida(norm):
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

    # Se faltam colunas obrigatórias ou há colunas PII proibidas no cabeçalho,
    # encerra validação estrutural. Se o professor tiver múltiplas escolas e o cabeçalho falhou,
    # exige que o escopo seja determinável ou retorna 400 se ambíguo.
    if relatorio.colunas_ausentes or relatorio.colunas_proibidas_pii:
        relatorio.quantidade_erros = len(relatorio.erros)
        relatorio.quantidade_avisos = len(relatorio.avisos)
        if len(escolas_autorizadas) == 1:
            escola_fallback = next(iter(escolas_autorizadas))
        elif usuario.escola_id is not None and usuario.escola_id in escolas_autorizadas:
            escola_fallback = usuario.escola_id
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Não foi possível determinar uma escola única para o lote: o arquivo possui "
                    "erros estruturais de cabeçalho e o professor possui vínculos em múltiplas escolas."
                ),
            )
        return escola_fallback, relatorio, []

    canon_para_orig: dict[str, str] = {}
    for orig, canon in mapa_orig_para_canon.items():
        if canon not in canon_para_orig:
            canon_para_orig[canon] = orig

    # Colunas extras não mapeadas também são inspecionadas linha a linha contra vazamento de PII
    colunas_extras = [
        str(col_orig)
        for col_orig in colunas_originais
        if col_orig not in mapa_orig_para_canon
        and normalizar_identificador_coluna(col_orig) not in COLUNAS_AUTORIA_IGNORADAS
    ]

    chaves_vistas_no_arquivo: dict[
        tuple[str, uuid.UUID, Optional[uuid.UUID], int, str], int
    ] = {}
    turmas_identificadas_set: set[str] = set()
    disciplinas_identificadas_set: set[str] = set()
    escolas_no_lote: set[uuid.UUID] = set()
    primeira_escola_lote: Optional[uuid.UUID] = None

    for idx, row in df.iterrows():
        linha_num = int(idx) + 2  # Cabeçalho é linha 1
        erros_linha_inicio = (
            len(relatorio.problemas_autorizacao)
            + len(relatorio.valores_invalidos)
            + len(relatorio.duplicidades)
            + len(relatorio.problemas_anonimizacao)
        )

        # 0. Inspeção de privacidade (PII) em todas as células de colunas não-código
        for col_inspecao in colunas_originais:
            if col_inspecao == canon_para_orig.get("codigo_anonimo"):
                continue
            if (
                normalizar_identificador_coluna(col_inspecao)
                in COLUNAS_AUTORIA_IGNORADAS
            ):
                continue
            val_celula = row.get(col_inspecao, "")
            tipo_pii_cel = _valor_contem_padrao_pii(val_celula)
            if tipo_pii_cel is not None:
                relatorio.problemas_anonimizacao.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="pii_proibido",
                        campo=str(col_inspecao),
                        mensagem=(
                            f"Violação de privacidade detectada na coluna '{col_inspecao}': "
                            f"o valor informado apresenta padrão de dado pessoal ({tipo_pii_cel})."
                        ),
                    )
                )
            elif (
                str(col_inspecao) in colunas_extras
                and REGEX_NOME_PESSOAL.match(str(val_celula).strip())
            ):
                relatorio.problemas_anonimizacao.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="pii_proibido",
                        campo=str(col_inspecao),
                        mensagem=(
                            f"Violação de privacidade detectada na coluna '{col_inspecao}': "
                            "o valor informado parece conter um nome pessoal."
                        ),
                    )
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
                escolas_autorizadas=escolas_autorizadas,
                turmas_candidatas=turmas_candidatas,
                mapa_vinculos_prof=mapa_vinculos_prof,
            )
            if turma_obj is None and msg_erro:
                existe_outra_escola = any(
                    (
                        t.nome.strip().lower() == turma_raw.lower()
                        or (_is_uuid(turma_raw) and t.id == uuid.UUID(turma_raw))
                    )
                    and t.escola_id not in escolas_autorizadas
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
                escolas_autorizadas=escolas_autorizadas,
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

        # Verifica consistência de escola única dentro do mesmo lote de importação
        if turma_obj is not None:
            escolas_no_lote.add(turma_obj.escola_id)
            if primeira_escola_lote is None:
                primeira_escola_lote = turma_obj.escola_id
            elif turma_obj.escola_id != primeira_escola_lote:
                relatorio.problemas_autorizacao.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="autorizacao",
                        campo="turma",
                        mensagem=(
                            f"Conflito de escopo escolar no lote: a turma '{turma_obj.nome}' "
                            "pertence a uma escola diferente das linhas anteriores. "
                            "Cada lote de importação deve conter turmas de uma única escola."
                        ),
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
            turmas_identificadas_set.add(turma_obj.nome)
            if disc_obj is not None:
                disciplinas_identificadas_set.add(
                    f"{disc_obj.nome} ({disc_obj.codigo})"
                )

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

    # Determinação inequívoca da escola do lote (nunca escolhe arbitrariamente entre múltiplas escolas)
    if len(escolas_no_lote) == 1:
        escola_final = next(iter(escolas_no_lote))
    elif len(escolas_no_lote) > 1:
        # Lote contém turmas de múltiplas escolas (já registrado em problemas_autorizacao)
        escola_final = primeira_escola_lote  # type: ignore[assignment]
    elif len(escolas_autorizadas) == 1:
        escola_final = next(iter(escolas_autorizadas))
    elif usuario.escola_id is not None and usuario.escola_id in escolas_autorizadas:
        escola_final = usuario.escola_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível determinar uma unidade escolar única e inequívoca para este lote: "
                "o professor possui vínculos em mais de uma escola e nenhuma turma válida foi identificada no arquivo."
            ),
        )

    return escola_final, relatorio, previa_registros
