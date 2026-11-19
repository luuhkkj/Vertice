"""Extração limitada de texto de anexos enviados ao Assistente IA."""

import csv
from io import BytesIO, StringIO
from pathlib import PurePath
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from fastapi import HTTPException, status
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.integrations.assistant.schemas import DocumentoAssistenteLLM

MAX_ARQUIVOS_ASSISTENTE = 5
MAX_BYTES_ARQUIVO_ASSISTENTE = 5 * 1024 * 1024
MAX_BYTES_TOTAL_ASSISTENTE = 10 * 1024 * 1024
MAX_CARACTERES_ARQUIVO_ASSISTENTE = 12_000
MAX_CARACTERES_TOTAL_ASSISTENTE = 30_000
EXTENSOES_ASSISTENTE = {".csv", ".docx", ".pdf", ".txt", ".xlsx"}


def _truncar(texto: str, limite: int) -> str:
    marcador = "\n[Conteúdo parcial: limite de extração atingido.]"
    if len(texto) <= limite:
        return texto
    return texto[: limite - len(marcador)].rstrip() + marcador


def _extrair_csv(conteudo: bytes, nome: str) -> str:
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"O arquivo {nome} não está codificado em UTF-8.",
        ) from exc

    linhas: list[str] = []
    truncado = False
    try:
        for indice, linha in enumerate(csv.reader(StringIO(texto)), start=1):
            if indice > 250:
                truncado = True
                break
            linhas.append(" | ".join(str(celula)[:500] for celula in linha[:30]))
    except csv.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Não foi possível interpretar o CSV {nome}.",
        ) from exc
    resultado = "\n".join(linhas)
    if truncado:
        resultado += "\n[Linhas adicionais não incluídas.]"
    return resultado


def _extrair_xlsx(conteudo: bytes, nome: str) -> str:
    try:
        planilha = load_workbook(BytesIO(conteudo), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Não foi possível interpretar a planilha {nome}.",
        ) from exc

    partes: list[str] = []
    try:
        for aba in planilha.worksheets[:10]:
            partes.append(f"[Aba: {aba.title}]")
            for indice, linha in enumerate(
                aba.iter_rows(max_col=30, values_only=True),
                start=1,
            ):
                if indice > 200:
                    partes.append("[Linhas adicionais não incluídas.]")
                    break
                partes.append(
                    " | ".join(
                        str(valor)[:500] if valor is not None else ""
                        for valor in linha
                    )
                )
    finally:
        planilha.close()
    return "\n".join(partes)


def _extrair_pdf(conteudo: bytes, nome: str) -> str:
    try:
        leitor = PdfReader(BytesIO(conteudo), strict=False)
        if leitor.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"O PDF {nome} está protegido por senha.",
            )
        partes: list[str] = []
        for indice, pagina in enumerate(leitor.pages):
            if indice >= 20:
                partes.append("[Páginas adicionais não incluídas.]")
                break
            partes.append(pagina.extract_text() or "")
    except (PdfReadError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Não foi possível interpretar o PDF {nome}.",
        ) from exc
    return "\n".join(partes)


def _extrair_docx(conteudo: bytes, nome: str) -> str:
    try:
        documento = Document(BytesIO(conteudo))
    except (BadZipFile, PackageNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Não foi possível interpretar o documento {nome}.",
        ) from exc

    partes = [paragrafo.text for paragrafo in documento.paragraphs]
    for tabela in documento.tables[:20]:
        for linha in tabela.rows[:200]:
            partes.append(" | ".join(celula.text[:500] for celula in linha.cells[:30]))
    return "\n".join(partes)


def extrair_documentos_assistente(
    arquivos: list[tuple[str, bytes]],
) -> list[DocumentoAssistenteLLM]:
    """Valida e extrai texto temporário sem persistir os anexos."""
    if not arquivos or len(arquivos) > MAX_ARQUIVOS_ASSISTENTE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Envie de 1 a {MAX_ARQUIVOS_ASSISTENTE} arquivos por consulta.",
        )

    total_bytes = sum(len(conteudo) for _, conteudo in arquivos)
    if total_bytes > MAX_BYTES_TOTAL_ASSISTENTE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="O tamanho total dos anexos excede 10 MB.",
        )

    documentos: list[DocumentoAssistenteLLM] = []
    caracteres_restantes = MAX_CARACTERES_TOTAL_ASSISTENTE
    for nome_original, conteudo in arquivos:
        nome = PurePath(nome_original.replace("\\", "/")).name
        extensao = PurePath(nome).suffix.lower()
        if extensao not in EXTENSOES_ASSISTENTE:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Formato não suportado para {nome}. Use PDF, DOCX, TXT, CSV ou XLSX.",
            )
        if len(conteudo) > MAX_BYTES_ARQUIVO_ASSISTENTE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"O arquivo {nome} excede o limite de 5 MB.",
            )
        if not conteudo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"O arquivo {nome} está vazio.",
            )

        if extensao == ".txt":
            try:
                texto = conteudo.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"O arquivo {nome} não está codificado em UTF-8.",
                ) from exc
        elif extensao == ".csv":
            texto = _extrair_csv(conteudo, nome)
        elif extensao == ".xlsx":
            texto = _extrair_xlsx(conteudo, nome)
        elif extensao == ".pdf":
            texto = _extrair_pdf(conteudo, nome)
        else:
            texto = _extrair_docx(conteudo, nome)

        texto = texto.strip()
        if not texto:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"O arquivo {nome} não contém texto legível.",
            )
        texto = _truncar(texto, min(MAX_CARACTERES_ARQUIVO_ASSISTENTE, caracteres_restantes))
        documentos.append(
            DocumentoAssistenteLLM(nome_arquivo=nome, conteudo=texto)
        )
        caracteres_restantes -= len(texto)
        if caracteres_restantes <= 0:
            break
    return documentos
