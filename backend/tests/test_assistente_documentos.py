import pytest
from fastapi import HTTPException

from app.integrations.assistant.documents import (
    MAX_BYTES_ARQUIVO_ASSISTENTE,
    extrair_documentos_assistente,
)


def test_extrai_texto_de_txt_e_csv_sem_persistir_arquivos() -> None:
    documentos = extrair_documentos_assistente(
        [
            ("resumo.txt", "Indicadores do período".encode("utf-8")),
            ("entregas.csv", "Turma,Taxa\nA,72".encode("utf-8")),
        ]
    )

    assert [documento.nome_arquivo for documento in documentos] == [
        "resumo.txt",
        "entregas.csv",
    ]
    assert "Indicadores do período" in documentos[0].conteudo
    assert "A | 72" in documentos[1].conteudo


def test_rejeita_extensao_nao_suportada() -> None:
    with pytest.raises(HTTPException) as erro:
        extrair_documentos_assistente([("imagem.png", b"conteudo")])

    assert erro.value.status_code == 415
    assert "Formato não suportado" in erro.value.detail


def test_rejeita_arquivo_acima_do_limite() -> None:
    with pytest.raises(HTTPException) as erro:
        extrair_documentos_assistente(
            [("grande.txt", b"a" * (MAX_BYTES_ARQUIVO_ASSISTENTE + 1))]
        )

    assert erro.value.status_code == 413
