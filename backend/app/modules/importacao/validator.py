"""
Motor de leitura, sanitização, verificação de privacidade (LGPD/RN01),
validação de escopo de autorização (gestor vs professor) e geração de prévia
para importação de datasets escolares do Vértice.
"""

from datetime import date, datetime
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
from app.modules.avaliacoes.models import (
    FaixaDificuldadeQuestao,
    StatusAvaliacao,
    TipoQuestao,
)
from app.modules.avaliacoes.repository import AvaliacaoRepository
from app.modules.avaliacoes.service import AvaliacaoService
from app.modules.disciplinas.models import Disciplina
from app.modules.escolas.models import Escola
from app.modules.estudantes.models import SituacaoFinalPeriodo
from app.modules.estudantes.repository import EstudanteRepository
from app.modules.importacao.models import TipoImportacao
from app.modules.importacao.schemas import (
    ItemProblemaValidacao,
    RelatorioValidacaoSchema,
)
from app.modules.participacao.models import (
    StatusAtividade,
    StatusEntregaAtividade,
)
from app.modules.participacao.repository import ParticipacaoRepository
from app.modules.participacao.service import ParticipacaoService
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
    # Colunas canônicas de Avaliações (Bloco B — Fase 4)
    "id_avaliacao": "id_avaliacao",
    "codigo_avaliacao": "id_avaliacao",
    "avaliacao_id": "id_avaliacao",
    "avaliacao": "id_avaliacao",
    "titulo_avaliacao": "titulo_avaliacao",
    "nome_avaliacao": "titulo_avaliacao",
    "data_avaliacao": "data_avaliacao",
    "id_questao": "id_questao",
    "codigo_questao": "id_questao",
    "questao_id": "id_questao",
    "questao": "id_questao",
    "tipo_questao": "tipo_questao",
    "faixa_dificuldade": "faixa_dificuldade",
    "dificuldade": "faixa_dificuldade",
    "valor_questao": "valor_questao",
    "peso_questao": "valor_questao",
    "alternativa_correta": "alternativa_correta",
    "gabarito": "alternativa_correta",
    "alternativa_marcada": "alternativa_marcada",
    "resposta_marcada": "alternativa_marcada",
    "nota_obtida": "nota_obtida",
    "topico": "topico",
    "assunto": "topico",
    "em_branco": "em_branco",
    "acertou": "acertou",
    # Colunas canônicas de Atividades / Participação (Bloco C — Fase 4)
    "id_atividade": "id_atividade",
    "codigo_atividade": "id_atividade",
    "atividade_id": "id_atividade",
    "titulo_atividade": "titulo_atividade",
    "data_limite": "data_limite",
    "prazo_entrega": "data_limite",
    "data_entrega": "data_entrega",
    "status_entrega": "status_entrega",
    "nota_maxima": "nota_maxima",
}

COLUNAS_OBRIGATORIAS = (
    "codigo_anonimo",
    "turma",
    "ano_letivo",
    "periodo_letivo",
)

COLUNAS_OBRIGATORIAS_AVALIACOES = (
    "id_avaliacao",
    "turma",
    "id_questao",
    "codigo_anonimo",
    "alternativa_marcada",
)

COLUNAS_MODELO_AVALIACOES: tuple[str, ...] = (
    "id_avaliacao",
    "titulo_avaliacao",
    "disciplina",
    "turma",
    "periodo_letivo",
    "data_avaliacao",
    "id_questao",
    "tipo_questao",
    "valor_questao",
    "alternativa_correta",
    "codigo_anonimo",
    "alternativa_marcada",
    "em_branco",
    "nota_obtida",
    "faixa_dificuldade",
    "topico",
)

COLUNAS_OBRIGATORIAS_ATIVIDADES = (
    "id_atividade",
    "turma",
    "codigo_anonimo",
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


def gerar_arquivo_modelo_avaliacoes(formato: str = "csv") -> tuple[bytes, str, str]:
    """
    Gera o arquivo modelo oficial de importação de avaliações e respostas individuais
    em CSV ou XLSX com todas as 16 colunas obrigatórias do modelo.
    Retorna `(conteudo_bytes, media_type, nome_arquivo)`.
    """
    fmt_limpo = formato.strip().lower().lstrip(".")
    df_modelo = pd.DataFrame(columns=list(COLUNAS_MODELO_AVALIACOES))

    if fmt_limpo == "csv":
        conteudo = df_modelo.to_csv(index=False, sep=";").encode("utf-8-sig")
        return (
            conteudo,
            "text/csv; charset=utf-8",
            "modelo_resultados_avaliacoes.csv",
        )

    if fmt_limpo in ("xlsx", "excel"):
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_modelo.to_excel(writer, index=False, sheet_name="Modelo")
        return (
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "modelo_resultados_avaliacoes.xlsx",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Formato de modelo inválido. Use 'csv' ou 'xlsx'.",
    )


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


def identificar_tipo_importacao(
    df: pd.DataFrame,
    tipo_informado: Optional[TipoImportacao] = None,
) -> TipoImportacao:
    """
    Identifica o tipo de dataset enviado a partir do parâmetro explícito ou
    pelas colunas normalizadas do cabeçalho.
    """
    if tipo_informado is not None:
        return tipo_informado

    colunas_canonicas = {
        MAPA_COLUNAS_CANONICAS.get(normalizar_identificador_coluna(c))
        for c in df.columns
    }
    colunas_canonicas.discard(None)

    if (
        "id_avaliacao" in colunas_canonicas
        or "id_questao" in colunas_canonicas
        or "acertou" in colunas_canonicas
    ):
        return TipoImportacao.AVALIACOES

    if (
        "id_atividade" in colunas_canonicas
        or "data_limite" in colunas_canonicas
        or "status_entrega" in colunas_canonicas
    ):
        return TipoImportacao.ATIVIDADES

    return TipoImportacao.DADOS_ESCOLARES


def _parse_date_opcional(
    valor_raw: Any,
    campo: str,
    linha_num: int,
    problemas_valores: list[ItemProblemaValidacao],
    obrigatorio: bool = False,
) -> Optional[date]:
    texto = str(valor_raw).strip() if valor_raw is not None else ""
    if not texto or texto.lower() in ("null", "none", "nan", "-"):
        if obrigatorio:
            problemas_valores.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo=campo,
                    mensagem=f"O campo obrigatório de data '{campo}' está vazio.",
                )
            )
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto[:10], fmt).date()
        except ValueError:
            continue

    problemas_valores.append(
        ItemProblemaValidacao(
            linha=linha_num,
            categoria="valor_invalido",
            campo=campo,
            mensagem=f"Data inválida em '{campo}' ('{texto}'). Utilize o formato YYYY-MM-DD ou DD/MM/YYYY.",
        )
    )
    return None


def processar_e_validar_dataframe_avaliacoes(
    db: Session,
    df: pd.DataFrame,
    usuario: Usuario,
) -> tuple[uuid.UUID, RelatorioValidacaoSchema, list[dict[str, Any]]]:
    """
    Valida um arquivo CSV/XLSX de Avaliações, Questões e Respostas (Bloco B — Fase 4).
    Regras obrigatórias:
    - Rejeita PII proibida (LGPD / RN01).
    - Valida escopo de turma e disciplina (gestor vs professor).
    - NUNCA cria estudantes: exige que cada estudante já exista no cadastro da escola
      e possua vínculo com a turma da avaliação.
    - Valida coerência de tipo_questao (FECHADA / ABERTA), gabarito, valor_questao,
      nota_obtida e respostas em branco.
    - Detecta duplicidade de (id_avaliacao, id_questao, codigo_anonimo) no arquivo.
    """
    escolas_autorizadas, turmas_candidatas, mapa_vinculos_prof, mapa_disciplinas_por_id = (
        _carregar_contexto_autorizacao(db, usuario)
    )

    stmt_todas_turmas_banco = select(Turma).where(Turma.ativo.is_(True))
    todas_turmas_banco = list(db.execute(stmt_todas_turmas_banco).scalars().all())

    relatorio = RelatorioValidacaoSchema(total_linhas=len(df.index))
    previa_registros: list[dict[str, Any]] = []

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
    possui_coluna_acertou = "acertou" in colunas_canonicas_presentes

    if possui_coluna_acertou and (
        "alternativa_marcada" not in colunas_canonicas_presentes
        or "alternativa_correta" not in colunas_canonicas_presentes
    ):
        prob_legado = ItemProblemaValidacao(
            linha=1,
            categoria="formato_desatualizado",
            campo="acertou",
            mensagem=(
                "O formato da planilha de avaliações foi atualizado. "
                "Arquivos antigos que contenham apenas o resultado binário 'Acertou' "
                "não são mais aceitos; informe as colunas 'alternativa_marcada' e "
                "'alternativa_correta' (gabarito) para que o sistema calcule os resultados."
            ),
        )
        relatorio.valores_invalidos.append(prob_legado)
        relatorio.erros.append(prob_legado)
    elif possui_coluna_acertou:
        relatorio.avisos.append(
            ItemProblemaValidacao(
                linha=1,
                categoria="campo_ignorado",
                campo="acertou",
                mensagem=(
                    "A coluna binária 'acertou' enviada no arquivo foi ignorada: "
                    "o resultado é calculado automaticamente pelo backend a partir de "
                    "'alternativa_marcada', 'alternativa_correta' e 'nota_obtida'."
                ),
            )
        )

    faltantes = [
        col
        for col in COLUNAS_OBRIGATORIAS_AVALIACOES
        if col not in colunas_canonicas_presentes
    ]
    if faltantes:
        relatorio.colunas_ausentes = faltantes
        for col_faltante in faltantes:
            prob = ItemProblemaValidacao(
                linha=1,
                categoria="coluna_ausente",
                campo=col_faltante,
                mensagem=f"Coluna obrigatória ausente no arquivo de avaliações: '{col_faltante}'.",
            )
            relatorio.erros.append(prob)

    if (
        relatorio.colunas_ausentes
        or relatorio.colunas_proibidas_pii
        or relatorio.valores_invalidos
    ):
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
                    "Não foi possível determinar uma escola única para o lote de avaliações: "
                    "o arquivo possui erros estruturais de cabeçalho e o professor possui vínculos em múltiplas escolas."
                ),
            )
        return escola_fallback, relatorio, []

    canon_para_orig: dict[str, str] = {}
    for orig, canon in mapa_orig_para_canon.items():
        if canon not in canon_para_orig:
            canon_para_orig[canon] = orig

    chaves_vistas_no_arquivo: dict[
        tuple[str, uuid.UUID, uuid.UUID, str, str], int
    ] = {}
    # Metadados consistentes por questão dentro do mesmo arquivo:
    # (codigo_avaliacao, turma_id, disc_id, codigo_questao) -> (tipo_questao, valor_questao, alternativa_correta)
    definicoes_questoes_no_arquivo: dict[
        tuple[str, uuid.UUID, uuid.UUID, str],
        tuple[TipoQuestao, float, Optional[str]],
    ] = {}

    turmas_identificadas_set: set[str] = set()
    disciplinas_identificadas_set: set[str] = set()
    escolas_no_lote: set[uuid.UUID] = set()
    primeira_escola_lote: Optional[uuid.UUID] = None

    for idx, row in df.iterrows():
        linha_num = int(idx) + 2
        erros_linha_inicio = (
            len(relatorio.problemas_autorizacao)
            + len(relatorio.valores_invalidos)
            + len(relatorio.duplicidades)
            + len(relatorio.problemas_anonimizacao)
        )

        # 0. Inspeção de privacidade (PII) nas células
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

        # 1. Código anônimo do estudante
        codigo_anonimo = validar_codigo_anonimo(
            row.get(canon_para_orig["codigo_anonimo"], ""),
            linha_num,
            relatorio.problemas_anonimizacao,
        )

        # 2. Ano letivo (opcional se turma única) e Turma
        ano_letivo = (
            _parse_int_opcional(
                row.get(canon_para_orig["ano_letivo"], ""),
                "ano_letivo",
                linha_num,
                minimo=2000,
                maximo=2100,
                problemas_valores=relatorio.valores_invalidos,
                obrigatorio=False,
            )
            if "ano_letivo" in canon_para_orig
            else None
        )
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
        turma_raw = str(row.get(canon_para_orig["turma"], "")).strip()

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
            if usuario.papel == PapelUsuario.GESTOR:
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
                            "pertence a uma escola diferente das linhas anteriores."
                        ),
                    )
                )

        # 3. Disciplina (obrigatória para avaliações, ou inferida se vínculo único do professor)
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
            elif disc_obj is None:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="disciplina",
                        mensagem="A identificação da disciplina é obrigatória para importação de avaliações.",
                    )
                )

        # 4. Identificação da Avaliação e Questão
        codigo_avaliacao = str(row.get(canon_para_orig["id_avaliacao"], "")).strip()
        if not codigo_avaliacao:
            relatorio.valores_invalidos.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo="id_avaliacao",
                    mensagem="O identificador da avaliação ('id_avaliacao') está vazio.",
                )
            )

        codigo_questao = (
            str(row.get(canon_para_orig["id_questao"], "")).strip().upper()
        )
        if not codigo_questao:
            relatorio.valores_invalidos.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo="id_questao",
                    mensagem="O identificador da questão ('id_questao') está vazio.",
                )
            )

        avaliacao_existente = None
        if turma_obj is not None and disc_obj is not None and codigo_avaliacao:
            if _is_uuid(codigo_avaliacao):
                av_cand = AvaliacaoRepository.get_by_id(
                    db, uuid.UUID(codigo_avaliacao)
                )
                if (
                    av_cand is not None
                    and av_cand.escola_id == turma_obj.escola_id
                    and av_cand.turma_id == turma_obj.id
                    and av_cand.disciplina_id == disc_obj.id
                ):
                    avaliacao_existente = av_cand
            if avaliacao_existente is None:
                avaliacao_existente = AvaliacaoRepository.get_by_chave(
                    db=db,
                    escola_id=turma_obj.escola_id,
                    turma_id=turma_obj.id,
                    disciplina_id=disc_obj.id,
                    codigo=codigo_avaliacao,
                )

        titulo_avaliacao_raw = (
            str(row.get(canon_para_orig["titulo_avaliacao"], "")).strip()
            if "titulo_avaliacao" in canon_para_orig
            else ""
        )
        titulo_avaliacao = (
            titulo_avaliacao_raw
            or (avaliacao_existente.titulo if avaliacao_existente else "")
            or f"Avaliação {codigo_avaliacao}"
        )

        periodo_raw = (
            str(row.get(canon_para_orig["periodo_letivo"], "")).strip()
            if "periodo_letivo" in canon_para_orig
            else ""
        )
        periodo_letivo = periodo_raw or (
            avaliacao_existente.periodo_letivo if avaliacao_existente else "1º Bimestre"
        )

        data_avaliacao = (
            _parse_date_opcional(
                row.get(canon_para_orig["data_avaliacao"]),
                "data_avaliacao",
                linha_num,
                relatorio.valores_invalidos,
                obrigatorio=False,
            )
            if "data_avaliacao" in canon_para_orig
            else None
        )
        if data_avaliacao is None:
            data_avaliacao = (
                avaliacao_existente.data_avaliacao
                if avaliacao_existente is not None
                else date.today()
            )

        # Questão existente ou metadados no CSV
        questao_existente = (
            AvaliacaoRepository.get_questao_by_codigo(
                db, avaliacao_existente.id, codigo_questao
            )
            if avaliacao_existente is not None and codigo_questao
            else None
        )

        tipo_questao_raw = (
            str(row.get(canon_para_orig["tipo_questao"], "")).strip().upper()
            if "tipo_questao" in canon_para_orig
            else ""
        )
        tipo_questao_enum: Optional[TipoQuestao] = None
        if tipo_questao_raw:
            if tipo_questao_raw in ("FECHADA", "MULTIPLA_ESCOLHA", "OBJETIVA"):
                tipo_questao_enum = TipoQuestao.FECHADA
            elif tipo_questao_raw in ("ABERTA", "DISCURSIVA"):
                tipo_questao_enum = TipoQuestao.ABERTA
            else:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="tipo_questao",
                        mensagem=f"Tipo de questão inválido ('{tipo_questao_raw}'). Use FECHADA ou ABERTA.",
                    )
                )
        elif questao_existente is not None:
            tipo_questao_enum = questao_existente.tipo_questao
        else:
            tipo_questao_enum = TipoQuestao.FECHADA

        valor_questao = (
            _parse_float_opcional(
                row.get(canon_para_orig["valor_questao"]),
                "valor_questao",
                linha_num,
                minimo=0.01,
                maximo=100.0,
                problemas_valores=relatorio.valores_invalidos,
            )
            if "valor_questao" in canon_para_orig
            else None
        )
        if valor_questao is None:
            valor_questao = (
                float(questao_existente.valor_questao)
                if questao_existente is not None
                else 1.0
            )

        alt_correta_raw = (
            str(row.get(canon_para_orig["alternativa_correta"], "")).strip().upper()
            if "alternativa_correta" in canon_para_orig
            else ""
        )
        if alt_correta_raw in ("NULL", "NONE", "NAN", "-"):
            alt_correta_raw = ""
        alternativa_correta: Optional[str] = alt_correta_raw or (
            questao_existente.alternativa_correta
            if questao_existente is not None
            else None
        )

        if tipo_questao_enum == TipoQuestao.FECHADA:
            if not alternativa_correta or alternativa_correta not in {
                "A",
                "B",
                "C",
                "D",
                "E",
            }:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="alternativa_correta",
                        mensagem=(
                            f"Questão FECHADA '{codigo_questao}' exige 'alternativa_correta' "
                            "entre A, B, C, D ou E."
                        ),
                    )
                )
        elif tipo_questao_enum == TipoQuestao.ABERTA:
            if alt_correta_raw:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="alternativa_correta",
                        mensagem=f"Questão ABERTA '{codigo_questao}' não deve possuir 'alternativa_correta'.",
                    )
                )
            alternativa_correta = None

        faixa_raw = (
            str(row.get(canon_para_orig["faixa_dificuldade"], "")).strip()
            if "faixa_dificuldade" in canon_para_orig
            else ""
        )
        faixa_enum: Optional[FaixaDificuldadeQuestao] = None
        if faixa_raw and faixa_raw.lower() not in ("null", "none", "nan", "-"):
            mapa_faixa = {
                "facil": FaixaDificuldadeQuestao.FACIL,
                "fácil": FaixaDificuldadeQuestao.FACIL,
                "adequada": FaixaDificuldadeQuestao.ADEQUADA,
                "atencao": FaixaDificuldadeQuestao.ATENCAO,
                "atenção": FaixaDificuldadeQuestao.ATENCAO,
                "dificil": FaixaDificuldadeQuestao.DIFICIL,
                "difícil": FaixaDificuldadeQuestao.DIFICIL,
            }
            faixa_enum = mapa_faixa.get(faixa_raw.lower())
            if faixa_enum is None:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="faixa_dificuldade",
                        mensagem=(
                            f"Faixa de dificuldade inválida ('{faixa_raw}'). "
                            "Valores permitidos: Fácil, Adequada, Atenção, Difícil."
                        ),
                    )
                )
        elif questao_existente is not None:
            faixa_enum = questao_existente.faixa_dificuldade

        topico_raw = (
            str(row.get(canon_para_orig["topico"], "")).strip()
            if "topico" in canon_para_orig
            else ""
        )
        topico = topico_raw or (
            questao_existente.topico if questao_existente is not None else None
        )

        # Consistência da questão dentro do mesmo arquivo
        if (
            turma_obj is not None
            and disc_obj is not None
            and codigo_avaliacao
            and codigo_questao
            and tipo_questao_enum is not None
        ):
            chave_q_arq = (
                codigo_avaliacao,
                turma_obj.id,
                disc_obj.id,
                codigo_questao,
            )
            def_atual = (tipo_questao_enum, valor_questao, alternativa_correta)
            if chave_q_arq in definicoes_questoes_no_arquivo:
                if definicoes_questoes_no_arquivo[chave_q_arq] != def_atual:
                    relatorio.valores_invalidos.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="valor_invalido",
                            campo="id_questao",
                            mensagem=(
                                f"Inconsistência na definição da questão '{codigo_questao}' da avaliação "
                                f"'{codigo_avaliacao}': tipo, peso ou gabarito divergem de linhas anteriores."
                            ),
                        )
                    )
            else:
                definicoes_questoes_no_arquivo[chave_q_arq] = def_atual

        # 5. Validação do Estudante existente e vinculado à turma (NUNCA cria estudante)
        estudante_obj = None
        if codigo_anonimo and turma_obj is not None:
            estudante_obj = EstudanteRepository.get_by_escola_e_codigo(
                db, turma_obj.escola_id, codigo_anonimo
            )
            if estudante_obj is None or not estudante_obj.ativo:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="estudante_inexistente",
                        campo="codigo_anonimo",
                        mensagem=(
                            f"Estudante '{codigo_anonimo}' não encontrado no cadastro da escola. "
                            "Importações de avaliações não podem criar estudantes novos."
                        ),
                    )
                )
            elif not AvaliacaoRepository.estudante_vinculado_a_turma(
                db=db,
                estudante_id=estudante_obj.id,
                turma_id=turma_obj.id,
                escola_id=turma_obj.escola_id,
            ):
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="estudante_fora_da_turma",
                        campo="codigo_anonimo",
                        mensagem=(
                            f"O estudante '{codigo_anonimo}' não está vinculado à turma '{turma_obj.nome}' "
                            "nos dados escolares."
                        ),
                    )
                )

        # 6. Validação da Resposta e Nota Obtida
        alt_marcada_raw = (
            str(row.get(canon_para_orig["alternativa_marcada"], "")).strip().upper()
            if "alternativa_marcada" in canon_para_orig
            else ""
        )
        if alt_marcada_raw in ("NULL", "NONE", "NAN", "-"):
            alt_marcada_raw = ""

        em_branco_bool = (
            _parse_bool_opcional(
                row.get(canon_para_orig["em_branco"]),
                "em_branco",
                linha_num,
                relatorio.valores_invalidos,
            )
            if "em_branco" in canon_para_orig
            else None
        )

        nota_obtida_val = (
            _parse_float_opcional(
                row.get(canon_para_orig["nota_obtida"]),
                "nota_obtida",
                linha_num,
                minimo=0.0,
                maximo=float(valor_questao),
                problemas_valores=relatorio.valores_invalidos,
            )
            if "nota_obtida" in canon_para_orig
            else None
        )

        alt_final: Optional[str] = None
        em_branco_final = False
        nota_final = 0.0
        acertou_final: Optional[bool] = False

        if tipo_questao_enum == TipoQuestao.FECHADA:
            if em_branco_bool is True and alt_marcada_raw in {"A", "B", "C", "D", "E"}:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="alternativa_marcada",
                        mensagem=(
                            f"Inconsistência na questão fechada '{codigo_questao}': "
                            f"'em_branco' foi marcado como verdadeiro, mas 'alternativa_marcada' "
                            f"foi preenchida com '{alt_marcada_raw}'."
                        ),
                    )
                )
            elif em_branco_bool is False and (
                not alt_marcada_raw or alt_marcada_raw == "BRANCO"
            ):
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="alternativa_marcada",
                        mensagem=(
                            f"Inconsistência na questão fechada '{codigo_questao}': "
                            "'em_branco' foi indicado como falso, mas nenhuma alternativa válida (A-E) "
                            "foi informada em 'alternativa_marcada'."
                        ),
                    )
                )
            elif em_branco_bool is True or alt_marcada_raw == "BRANCO":
                if nota_obtida_val is not None and nota_obtida_val > 0.0:
                    relatorio.valores_invalidos.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="valor_invalido",
                            campo="nota_obtida",
                            mensagem=f"Questão fechada '{codigo_questao}' deixada em branco não pode ter nota positiva.",
                        )
                    )
                alt_final = "BRANCO"
                em_branco_final = True
                nota_final = 0.0
                acertou_final = False
            elif not alt_marcada_raw:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="alternativa_marcada",
                        mensagem=(
                            f"O campo 'alternativa_marcada' é obrigatório para a questão fechada '{codigo_questao}'. "
                            "Informe A, B, C, D, E ou represente a omissão explicitamente com 'BRANCO' "
                            "(ou 'em_branco' = Sim/True)."
                        ),
                    )
                )
            elif alt_marcada_raw not in {"A", "B", "C", "D", "E"}:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="alternativa_marcada",
                        mensagem=(
                            f"Alternativa marcada inválida ('{alt_marcada_raw}') na questão '{codigo_questao}'. "
                            "Use A, B, C, D, E ou BRANCO."
                        ),
                    )
                )
            else:
                alt_final = alt_marcada_raw
                em_branco_final = False
                acertou_final = alt_final == (alternativa_correta or "").upper()
                if not acertou_final and nota_obtida_val is not None and nota_obtida_val > 0.0:
                    relatorio.valores_invalidos.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="valor_invalido",
                            campo="nota_obtida",
                            mensagem=(
                                f"A resposta marcada ('{alt_final}') na questão fechada '{codigo_questao}' "
                                f"diverge do gabarito ('{alternativa_correta}') e não pode ter nota positiva ({nota_obtida_val})."
                            ),
                        )
                    )
                nota_final = (
                    round(float(nota_obtida_val), 2)
                    if nota_obtida_val is not None and acertou_final
                    else round(float(valor_questao) if acertou_final else 0.0, 2)
                )
        elif tipo_questao_enum == TipoQuestao.ABERTA:
            if alt_marcada_raw and alt_marcada_raw != "BRANCO":
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="alternativa_marcada",
                        mensagem=f"Questão ABERTA '{codigo_questao}' não aceita alternativa '{alt_marcada_raw}'.",
                    )
                )
            elif em_branco_bool is True or alt_marcada_raw == "BRANCO":
                if nota_obtida_val is not None and nota_obtida_val > 0.0:
                    relatorio.valores_invalidos.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="valor_invalido",
                            campo="nota_obtida",
                            mensagem=f"Questão aberta '{codigo_questao}' em branco não pode ter nota positiva.",
                        )
                    )
                alt_final = None
                em_branco_final = True
                nota_final = 0.0
                acertou_final = False
            elif nota_obtida_val is None:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="nota_obtida",
                        mensagem=(
                            f"Questão ABERTA '{codigo_questao}' exige 'nota_obtida' entre 0 e {valor_questao} "
                            "quando não estiver explicitamente marcada em branco ('em_branco'=Sim ou 'alternativa_marcada'=BRANCO)."
                        ),
                    )
                )
            else:
                alt_final = None
                em_branco_final = False
                nota_final = round(float(nota_obtida_val), 2)
                acertou_final = nota_final >= round(0.6 * float(valor_questao), 4)

        # 7. Duplicidade dentro do arquivo
        if (
            codigo_anonimo
            and turma_obj is not None
            and disc_obj is not None
            and codigo_avaliacao
            and codigo_questao
        ):
            chave_resp = (
                codigo_avaliacao,
                turma_obj.id,
                disc_obj.id,
                codigo_questao,
                codigo_anonimo,
            )
            if chave_resp in chaves_vistas_no_arquivo:
                linha_ant = chaves_vistas_no_arquivo[chave_resp]
                relatorio.duplicidades.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="duplicidade",
                        campo="id_questao",
                        mensagem=(
                            f"Resposta duplicada no arquivo para o estudante '{codigo_anonimo}' "
                            f"na questão '{codigo_questao}' da avaliação '{codigo_avaliacao}' "
                            f"(já informada na linha {linha_ant})."
                        ),
                    )
                )
            else:
                chaves_vistas_no_arquivo[chave_resp] = linha_num

        erros_linha_fim = (
            len(relatorio.problemas_autorizacao)
            + len(relatorio.valores_invalidos)
            + len(relatorio.duplicidades)
            + len(relatorio.problemas_anonimizacao)
        )

        if (
            erros_linha_fim == erros_linha_inicio
            and codigo_anonimo is not None
            and estudante_obj is not None
            and turma_obj is not None
            and disc_obj is not None
            and codigo_avaliacao
            and codigo_questao
            and tipo_questao_enum is not None
        ):
            turmas_identificadas_set.add(turma_obj.nome)
            disciplinas_identificadas_set.add(
                f"{disc_obj.nome} ({disc_obj.codigo})"
            )

            existe_resposta = False
            if questao_existente is not None:
                resp_exist = AvaliacaoRepository.get_resposta_by_questao_e_estudante(
                    db, questao_existente.id, estudante_obj.id
                )
                existe_resposta = resp_exist is not None

            if existe_resposta:
                relatorio.registros_existentes += 1
                operacao_prevista = "atualizacao"
            else:
                relatorio.registros_novos += 1
                operacao_prevista = "insercao"

            relatorio.registros_validos += 1
            previa_registros.append(
                {
                    "linha": linha_num,
                    "escola_id": str(turma_obj.escola_id),
                    "turma_id": str(turma_obj.id),
                    "turma_nome": turma_obj.nome,
                    "disciplina_id": str(disc_obj.id),
                    "disciplina_codigo": disc_obj.codigo,
                    "disciplina_nome": disc_obj.nome,
                    "codigo_avaliacao": codigo_avaliacao,
                    "titulo_avaliacao": titulo_avaliacao,
                    "periodo_letivo": periodo_letivo,
                    "data_avaliacao": data_avaliacao.isoformat(),
                    "codigo_questao": codigo_questao,
                    "tipo_questao": tipo_questao_enum.value,
                    "valor_questao": valor_questao,
                    "alternativa_correta": alternativa_correta,
                    "faixa_dificuldade": (
                        faixa_enum.value if faixa_enum is not None else None
                    ),
                    "topico": topico,
                    "estudante_id": str(estudante_obj.id),
                    "codigo_anonimo": codigo_anonimo,
                    "alternativa_marcada": alt_final,
                    "em_branco": em_branco_final,
                    "nota_obtida": nota_final,
                    "acertou": acertou_final,
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

    if len(escolas_no_lote) == 1:
        escola_final = next(iter(escolas_no_lote))
    elif len(escolas_no_lote) > 1:
        escola_final = primeira_escola_lote  # type: ignore[assignment]
    elif len(escolas_autorizadas) == 1:
        escola_final = next(iter(escolas_autorizadas))
    elif usuario.escola_id is not None and usuario.escola_id in escolas_autorizadas:
        escola_final = usuario.escola_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível determinar uma unidade escolar única para o lote de avaliações."
            ),
        )

    return escola_final, relatorio, previa_registros


def processar_e_validar_dataframe_atividades(
    db: Session,
    df: pd.DataFrame,
    usuario: Usuario,
) -> tuple[uuid.UUID, RelatorioValidacaoSchema, list[dict[str, Any]]]:
    """
    Valida um arquivo CSV/XLSX de Atividades e Entregas (Bloco C — Fase 4).
    Regras obrigatórias:
    - Rejeita PII proibida (LGPD / RN01).
    - Valida escopo de turma e disciplina (gestor vs professor).
    - NUNCA cria estudantes: exige que cada estudante já exista no cadastro da escola
      e possua vínculo com a turma da atividade.
    - Valida `data_limite`, `data_entrega`, `nota` (mantendo `None` quando ausente)
      e `status_entrega` (`ENTREGUE`, `ATRASADO`, `PENDENTE`, `NAO_ENTREGUE`).
    """
    escolas_autorizadas, turmas_candidatas, mapa_vinculos_prof, mapa_disciplinas_por_id = (
        _carregar_contexto_autorizacao(db, usuario)
    )

    stmt_todas_turmas_banco = select(Turma).where(Turma.ativo.is_(True))
    todas_turmas_banco = list(db.execute(stmt_todas_turmas_banco).scalars().all())

    relatorio = RelatorioValidacaoSchema(total_linhas=len(df.index))
    previa_registros: list[dict[str, Any]] = []

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
        col
        for col in COLUNAS_OBRIGATORIAS_ATIVIDADES
        if col not in colunas_canonicas_presentes
    ]
    if faltantes:
        relatorio.colunas_ausentes = faltantes
        for col_faltante in faltantes:
            prob = ItemProblemaValidacao(
                linha=1,
                categoria="coluna_ausente",
                campo=col_faltante,
                mensagem=f"Coluna obrigatória ausente no arquivo de atividades: '{col_faltante}'.",
            )
            relatorio.erros.append(prob)

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
                    "Não foi possível determinar uma escola única para o lote de atividades: "
                    "o arquivo possui erros estruturais de cabeçalho e o professor possui vínculos em múltiplas escolas."
                ),
            )
        return escola_fallback, relatorio, []

    canon_para_orig: dict[str, str] = {}
    for orig, canon in mapa_orig_para_canon.items():
        if canon not in canon_para_orig:
            canon_para_orig[canon] = orig

    chaves_vistas_no_arquivo: dict[
        tuple[str, uuid.UUID, uuid.UUID, str], int
    ] = {}
    turmas_identificadas_set: set[str] = set()
    disciplinas_identificadas_set: set[str] = set()
    escolas_no_lote: set[uuid.UUID] = set()
    primeira_escola_lote: Optional[uuid.UUID] = None

    for idx, row in df.iterrows():
        linha_num = int(idx) + 2
        erros_linha_inicio = (
            len(relatorio.problemas_autorizacao)
            + len(relatorio.valores_invalidos)
            + len(relatorio.duplicidades)
            + len(relatorio.problemas_anonimizacao)
        )

        # 0. Inspeção de privacidade (PII)
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

        # 1. Código anônimo do estudante
        codigo_anonimo = validar_codigo_anonimo(
            row.get(canon_para_orig["codigo_anonimo"], ""),
            linha_num,
            relatorio.problemas_anonimizacao,
        )

        # 2. Ano letivo e Turma
        ano_letivo = (
            _parse_int_opcional(
                row.get(canon_para_orig["ano_letivo"], ""),
                "ano_letivo",
                linha_num,
                minimo=2000,
                maximo=2100,
                problemas_valores=relatorio.valores_invalidos,
                obrigatorio=False,
            )
            if "ano_letivo" in canon_para_orig
            else None
        )
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
        turma_raw = str(row.get(canon_para_orig["turma"], "")).strip()

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
            if usuario.papel == PapelUsuario.GESTOR:
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
                            "pertence a uma escola diferente das linhas anteriores."
                        ),
                    )
                )

        # 3. Disciplina
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
            elif disc_obj is None:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="disciplina",
                        mensagem="A identificação da disciplina é obrigatória para importação de atividades.",
                    )
                )

        # 4. Atividade (existente ou nova no lote)
        codigo_atividade = str(row.get(canon_para_orig["id_atividade"], "")).strip()
        if not codigo_atividade:
            relatorio.valores_invalidos.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo="id_atividade",
                    mensagem="O identificador da atividade ('id_atividade') está vazio.",
                )
            )

        atividade_existente = None
        if turma_obj is not None and disc_obj is not None and codigo_atividade:
            if _is_uuid(codigo_atividade):
                at_cand = ParticipacaoRepository.get_atividade_by_id(
                    db, uuid.UUID(codigo_atividade)
                )
                if (
                    at_cand is not None
                    and at_cand.escola_id == turma_obj.escola_id
                    and at_cand.turma_id == turma_obj.id
                    and at_cand.disciplina_id == disc_obj.id
                ):
                    atividade_existente = at_cand
            if atividade_existente is None:
                atividade_existente = ParticipacaoRepository.get_atividade_by_chave(
                    db=db,
                    escola_id=turma_obj.escola_id,
                    turma_id=turma_obj.id,
                    disciplina_id=disc_obj.id,
                    codigo=codigo_atividade,
                )

        titulo_raw = (
            str(row.get(canon_para_orig["titulo_atividade"], "")).strip()
            if "titulo_atividade" in canon_para_orig
            else ""
        )
        titulo_atividade = (
            titulo_raw
            or (atividade_existente.titulo if atividade_existente else "")
            or f"Atividade {codigo_atividade}"
        )

        periodo_raw = (
            str(row.get(canon_para_orig["periodo_letivo"], "")).strip()
            if "periodo_letivo" in canon_para_orig
            else ""
        )
        periodo_letivo = periodo_raw or (
            atividade_existente.periodo_letivo
            if atividade_existente
            else "1º Bimestre"
        )

        data_limite = (
            _parse_date_opcional(
                row.get(canon_para_orig["data_limite"]),
                "data_limite",
                linha_num,
                relatorio.valores_invalidos,
                obrigatorio=(atividade_existente is None),
            )
            if "data_limite" in canon_para_orig
            else None
        )
        if data_limite is None and atividade_existente is not None:
            data_limite = atividade_existente.data_limite
        elif data_limite is None and "data_limite" not in canon_para_orig:
            relatorio.valores_invalidos.append(
                ItemProblemaValidacao(
                    linha=linha_num,
                    categoria="valor_invalido",
                    campo="data_limite",
                    mensagem=(
                        f"A atividade '{codigo_atividade}' ainda não está cadastrada; "
                        "informe a coluna 'data_limite' no arquivo."
                    ),
                )
            )

        nota_maxima = (
            _parse_float_opcional(
                row.get(canon_para_orig["nota_maxima"]),
                "nota_maxima",
                linha_num,
                minimo=0.01,
                maximo=100.0,
                problemas_valores=relatorio.valores_invalidos,
            )
            if "nota_maxima" in canon_para_orig
            else None
        )
        if nota_maxima is None:
            nota_maxima = (
                float(atividade_existente.nota_maxima)
                if atividade_existente is not None
                and atividade_existente.nota_maxima is not None
                else 10.0
            )

        # 5. Estudante existente e vinculado à turma (NUNCA cria estudante)
        estudante_obj = None
        if codigo_anonimo and turma_obj is not None:
            estudante_obj = EstudanteRepository.get_by_escola_e_codigo(
                db, turma_obj.escola_id, codigo_anonimo
            )
            if estudante_obj is None or not estudante_obj.ativo:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="estudante_inexistente",
                        campo="codigo_anonimo",
                        mensagem=(
                            f"Estudante '{codigo_anonimo}' não encontrado no cadastro da escola. "
                            "Importações de atividades não podem criar estudantes novos."
                        ),
                    )
                )
            else:
                elegiveis_ids = {
                    e.id
                    for e in ParticipacaoRepository.list_estudantes_elegiveis_turma(
                        db, turma_obj.escola_id, turma_obj.id
                    )
                }
                if estudante_obj.id not in elegiveis_ids:
                    relatorio.valores_invalidos.append(
                        ItemProblemaValidacao(
                            linha=linha_num,
                            categoria="estudante_fora_da_turma",
                            campo="codigo_anonimo",
                            mensagem=(
                                f"O estudante '{codigo_anonimo}' não está vinculado à turma '{turma_obj.nome}' "
                                "nos dados escolares."
                            ),
                        )
                    )

        # 6. Data de entrega, Nota (mantendo None quando vazia) e Status
        data_entrega = (
            _parse_date_opcional(
                row.get(canon_para_orig["data_entrega"]),
                "data_entrega",
                linha_num,
                relatorio.valores_invalidos,
                obrigatorio=False,
            )
            if "data_entrega" in canon_para_orig
            else None
        )

        nota_val = (
            _parse_float_opcional(
                row.get(canon_para_orig["nota"]),
                "nota",
                linha_num,
                minimo=0.0,
                maximo=float(nota_maxima),
                problemas_valores=relatorio.valores_invalidos,
            )
            if "nota" in canon_para_orig
            else None
        )

        status_raw = (
            str(row.get(canon_para_orig["status_entrega"], "")).strip().upper()
            if "status_entrega" in canon_para_orig
            else ""
        )
        if status_raw in ("NULL", "NONE", "NAN", "-"):
            status_raw = ""

        status_informado: Optional[StatusEntregaAtividade] = None
        if status_raw:
            mapa_status = {
                "ENTREGUE": StatusEntregaAtividade.ENTREGUE,
                "ATRASADO": StatusEntregaAtividade.ATRASADO,
                "ATRASADA": StatusEntregaAtividade.ATRASADO,
                "PENDENTE": StatusEntregaAtividade.PENDENTE,
                "NAO_ENTREGUE": StatusEntregaAtividade.NAO_ENTREGUE,
                "NÃO_ENTREGUE": StatusEntregaAtividade.NAO_ENTREGUE,
                "NAO ENTREGUE": StatusEntregaAtividade.NAO_ENTREGUE,
                "NÃO ENTREGUE": StatusEntregaAtividade.NAO_ENTREGUE,
            }
            status_informado = mapa_status.get(status_raw)
            if status_informado is None:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="status_entrega",
                        mensagem=(
                            f"Status de entrega inválido ('{status_raw}'). "
                            "Valores permitidos: ENTREGUE, ATRASADO, PENDENTE, NAO_ENTREGUE."
                        ),
                    )
                )

        status_final: Optional[StatusEntregaAtividade] = None
        if data_limite is not None:
            try:
                status_final = ParticipacaoService.resolver_status_entrega(
                    data_limite=data_limite,
                    data_entrega=data_entrega,
                    status_informado=status_informado,
                )
            except HTTPException as exc:
                relatorio.valores_invalidos.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="valor_invalido",
                        campo="status_entrega",
                        mensagem=str(exc.detail),
                    )
                )

        # 7. Duplicidade no arquivo
        if (
            codigo_anonimo
            and turma_obj is not None
            and disc_obj is not None
            and codigo_atividade
        ):
            chave_ent = (
                codigo_atividade,
                turma_obj.id,
                disc_obj.id,
                codigo_anonimo,
            )
            if chave_ent in chaves_vistas_no_arquivo:
                linha_ant = chaves_vistas_no_arquivo[chave_ent]
                relatorio.duplicidades.append(
                    ItemProblemaValidacao(
                        linha=linha_num,
                        categoria="duplicidade",
                        campo="id_atividade",
                        mensagem=(
                            f"Entrega duplicada no arquivo para o estudante '{codigo_anonimo}' "
                            f"na atividade '{codigo_atividade}' (já informada na linha {linha_ant})."
                        ),
                    )
                )
            else:
                chaves_vistas_no_arquivo[chave_ent] = linha_num

        erros_linha_fim = (
            len(relatorio.problemas_autorizacao)
            + len(relatorio.valores_invalidos)
            + len(relatorio.duplicidades)
            + len(relatorio.problemas_anonimizacao)
        )

        if (
            erros_linha_fim == erros_linha_inicio
            and codigo_anonimo is not None
            and estudante_obj is not None
            and turma_obj is not None
            and disc_obj is not None
            and codigo_atividade
            and data_limite is not None
            and status_final is not None
        ):
            turmas_identificadas_set.add(turma_obj.nome)
            disciplinas_identificadas_set.add(
                f"{disc_obj.nome} ({disc_obj.codigo})"
            )

            existe_entrega = False
            if atividade_existente is not None:
                ent_exist = ParticipacaoRepository.get_entrega_by_atividade_e_estudante(
                    db, atividade_existente.id, estudante_obj.id
                )
                existe_entrega = ent_exist is not None

            if existe_entrega:
                relatorio.registros_existentes += 1
                operacao_prevista = "atualizacao"
            else:
                relatorio.registros_novos += 1
                operacao_prevista = "insercao"

            relatorio.registros_validos += 1
            previa_registros.append(
                {
                    "linha": linha_num,
                    "escola_id": str(turma_obj.escola_id),
                    "turma_id": str(turma_obj.id),
                    "turma_nome": turma_obj.nome,
                    "disciplina_id": str(disc_obj.id),
                    "disciplina_codigo": disc_obj.codigo,
                    "disciplina_nome": disc_obj.nome,
                    "codigo_atividade": codigo_atividade,
                    "titulo_atividade": titulo_atividade,
                    "periodo_letivo": periodo_letivo,
                    "data_limite": data_limite.isoformat(),
                    "nota_maxima": nota_maxima,
                    "estudante_id": str(estudante_obj.id),
                    "codigo_anonimo": codigo_anonimo,
                    "data_entrega": (
                        data_entrega.isoformat() if data_entrega is not None else None
                    ),
                    "nota": nota_val,
                    "status_entrega": status_final.value,
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

    if len(escolas_no_lote) == 1:
        escola_final = next(iter(escolas_no_lote))
    elif len(escolas_no_lote) > 1:
        escola_final = primeira_escola_lote  # type: ignore[assignment]
    elif len(escolas_autorizadas) == 1:
        escola_final = next(iter(escolas_autorizadas))
    elif usuario.escola_id is not None and usuario.escola_id in escolas_autorizadas:
        escola_final = usuario.escola_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível determinar uma unidade escolar única para o lote de atividades."
            ),
        )

    return escola_final, relatorio, previa_registros

