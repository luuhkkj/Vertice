"""Cliente HTTP centralizado do frontend Streamlit para comunicação com a API do Vértice.

Garante:
- Comunicação HTTP autenticada via Bearer token da sessão (`st.session_state["access_token"]`).
- Proteção de credenciais: tokens e senhas NUNCA são exibidos na interface, logs ou mensagens de erro.
- Tratamento explícito de erros HTTP:
  * 401 (Sessão expirada ou inválida): limpa o token da sessão e retorna status `sessao_expirada`.
  * 403 (Permissão insuficiente): retorna mensagem clara de acesso restrito ao escopo.
  * Falha de rede / servidor indisponível: retorna status `indisponivel` sem produzir dados fictícios.
"""

from dataclasses import dataclass
from typing import Any, Callable, Optional
import re

import httpx
import streamlit as st

from config import API_BASE_URL


_PADRAO_TOKEN_SENSIVEL = re.compile(
    r"(Bearer\s+[A-Za-z0-9\-_\.]+|eyJ[A-Za-z0-9\-_\.]+)",
    re.IGNORECASE,
)


def sanitizar_mensagem_erro(mensagem: Any) -> str:
    """Remove qualquer possível token JWT ou cabeçalho de autorização de mensagens de erro."""
    texto = str(mensagem or "").strip()
    if not texto:
        return "Não foi possível concluir a comunicação com o servidor."
    texto_limpo = _PADRAO_TOKEN_SENSIVEL.sub("[TOKEN_OCULTO]", texto)
    return texto_limpo


@dataclass
class RespostaAPI:
    """Envelope padronizado de resposta da API para consumo seguro nas páginas do frontend."""

    ok: bool
    status_code: Optional[int] = None
    dados: Any = None
    erro: Optional[str] = None
    sessao_expirada: bool = False
    sem_permissao: bool = False
    indisponivel: bool = False


# Hook opcional para injeção de transporte/cliente em testes automatizados (ex.: FastAPI TestClient)
_cliente_http_override: Optional[Callable[..., Any]] = None


def configurar_cliente_http_teste(cliente_fn: Optional[Callable[..., Any]]) -> None:
    """Permite injetar um cliente HTTP (como `TestClient` ou `httpx.Client`) durante testes."""
    global _cliente_http_override
    _cliente_http_override = cliente_fn


def obter_token_sessao() -> Optional[str]:
    """Retorna o token JWT armazenado na sessão atual do Streamlit, se existir."""
    token = st.session_state.get("access_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def possui_sessao_api_ativa() -> bool:
    """Indica se o usuário possui um token de autenticação ativo para chamadas à API."""
    return obter_token_sessao() is not None


def limpar_sessao_expirada(mensagem: Optional[str] = None) -> None:
    """Remove credenciais expiradas da sessão e registra aviso claro de expiração."""
    st.session_state.pop("access_token", None)
    st.session_state.pop("usuario_api", None)
    st.session_state["sessao_api_expirada"] = True
    st.session_state["mensagem_sessao_expirada"] = (
        mensagem
        or "Sua sessão expirou ou é inválida. Faça login novamente para atualizar os dados."
    )


def _extrair_detalhe_erro( payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return sanitizar_mensagem_erro(detail)
        if isinstance(detail, list) and detail:
            partes = []
            for item in detail:
                if isinstance(item, dict) and item.get("msg"):
                    partes.append(str(item["msg"]))
            if partes:
                return sanitizar_mensagem_erro("; ".join(partes))
    return sanitizar_mensagem_erro(fallback)


def requisitar_api(
    metodo: str,
    caminho: str,
    *,
    params: Optional[dict[str, Any]] = None,
    json_body: Optional[dict[str, Any]] = None,
    files: Optional[dict[str, Any]] = None,
    exigir_auth: bool = True,
    timeout: float = 10.0,
) -> RespostaAPI:
    """Executa uma requisição HTTP autenticada à API v1 do Vértice com tratamento seguro."""
    token = obter_token_sessao()
    if exigir_auth and not token:
        return RespostaAPI(
            ok=False,
            status_code=401,
            erro="Sessão não autenticada na API. Realize o login para carregar os dados reais.",
            sessao_expirada=bool(st.session_state.get("sessao_api_expirada", False)),
        )

    headers: dict[str, str] = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    caminho_norm = caminho if caminho.startswith("/") else f"/{caminho}"
    params_limpos = (
        {k: str(v) for k, v in params.items() if v is not None and str(v) != ""}
        if params
        else None
    )

    try:
        if _cliente_http_override is not None:
            url_teste = f"/api/v1{caminho_norm}"
            resp = _cliente_http_override(
                metodo.upper(),
                url_teste,
                params=params_limpos,
                json=json_body,
                files=files,
                headers=headers,
            )
        else:
            url_completa = f"{API_BASE_URL}{caminho_norm}"
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(
                    method=metodo.upper(),
                    url=url_completa,
                    params=params_limpos,
                    json=json_body,
                    files=files,
                    headers=headers,
                )
    except Exception:
        return RespostaAPI(
            ok=False,
            status_code=None,
            erro=(
                "Não foi possível conectar ao servidor do Vértice no momento. "
                "Verifique se o backend está em execução e tente novamente."
            ),
            indisponivel=True,
        )

    status_code = int(resp.status_code)
    payload: Any = None
    try:
        if resp.content:
            payload = resp.json()
    except Exception:
        payload = None

    if 200 <= status_code < 300:
        st.session_state.pop("sessao_api_expirada", None)
        st.session_state.pop("mensagem_sessao_expirada", None)
        return RespostaAPI(
            ok=True,
            status_code=status_code,
            dados=payload,
        )

    if status_code == 401:
        msg_401 = _extrair_detalhe_erro(
            payload,
            "Sua sessão expirou ou suas credenciais não são mais válidas. Faça login novamente.",
        )
        if exigir_auth:
            limpar_sessao_expirada(msg_401)
        return RespostaAPI(
            ok=False,
            status_code=401,
            erro=msg_401,
            sessao_expirada=True,
        )

    if status_code == 403:
        msg_403 = _extrair_detalhe_erro(
            payload,
            "Permissão insuficiente para acessar os dados solicitados neste recorte.",
        )
        return RespostaAPI(
            ok=False,
            status_code=403,
            erro=msg_403,
            sem_permissao=True,
        )

    msg_erro = _extrair_detalhe_erro(
        payload,
        f"O servidor retornou um erro ao processar a solicitação (HTTP {status_code}).",
    )
    return RespostaAPI(
        ok=False,
        status_code=status_code,
        dados=payload,
        erro=msg_erro,
    )


def autenticar_usuario_api(email: str, senha: str) -> RespostaAPI:
    """Autentica o usuário em `POST /api/v1/auth/login` e armazena o token na sessão."""
    resposta = requisitar_api(
        "POST",
        "/auth/login",
        json_body={"email": email.strip(), "senha": senha},
        exigir_auth=False,
    )
    if resposta.ok and isinstance(resposta.dados, dict):
        token = resposta.dados.get("access_token")
        usuario = resposta.dados.get("usuario") or {}
        if isinstance(token, str) and token.strip():
            st.session_state["access_token"] = token.strip()
            st.session_state["usuario_api"] = usuario
            st.session_state.pop("sessao_api_expirada", None)
            st.session_state.pop("mensagem_sessao_expirada", None)
    return resposta


def consultar_indicadores_avaliacoes(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    periodo_letivo: Optional[str] = None,
    avaliacao_id: Optional[str] = None,
    ano_letivo: Optional[int] = None,
) -> RespostaAPI:
    """Consulta `GET /api/v1/indicadores/avaliacoes` aplicando os filtros selecionados."""
    return requisitar_api(
        "GET",
        "/indicadores/avaliacoes",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "periodo_letivo": periodo_letivo,
            "avaliacao_id": avaliacao_id,
            "ano_letivo": ano_letivo,
        },
    )


def listar_avaliacoes_api(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    periodo_letivo: Optional[str] = None,
) -> RespostaAPI:
    """Lista as avaliações disponíveis no escopo do usuário autenticado (`GET /api/v1/avaliacoes`)."""
    return requisitar_api(
        "GET",
        "/avaliacoes",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "periodo_letivo": periodo_letivo,
        },
    )


def listar_turmas_api() -> RespostaAPI:
    """Lista as turmas autorizadas para o usuário autenticado (`GET /api/v1/turmas`)."""
    return requisitar_api("GET", "/turmas")


def listar_disciplinas_api() -> RespostaAPI:
    """Lista as disciplinas cadastradas (`GET /api/v1/disciplinas`)."""
    return requisitar_api("GET", "/disciplinas")


def listar_atribuicoes_api() -> RespostaAPI:
    """Lista os vínculos de turma e disciplina (`GET /api/v1/atribuicoes`)."""
    return requisitar_api("GET", "/atribuicoes")


def criar_avaliacao_api(
    *,
    titulo: str,
    turma_id: str,
    disciplina_id: str,
    periodo_letivo: str,
    data_avaliacao: str,
    codigo: Optional[str] = None,
) -> RespostaAPI:
    """Cadastra uma nova avaliação no backend (`POST /api/v1/avaliacoes`)."""
    payload: dict[str, Any] = {
        "titulo": titulo.strip(),
        "turma_id": turma_id,
        "disciplina_id": disciplina_id,
        "periodo_letivo": periodo_letivo.strip(),
        "data_avaliacao": data_avaliacao,
        "status": "publicada",
    }
    if codigo and codigo.strip():
        payload["codigo"] = codigo.strip()
    return requisitar_api("POST", "/avaliacoes", json_body=payload)


def registrar_acompanhamento_pedagogico_api(
    *,
    turma_id: str,
    disciplina_id: Optional[str],
    tipo_acao: str,
    descricao: str,
    origem: str = "avaliacao",
) -> RespostaAPI:
    """Registra uma ação pedagógica vinculada à avaliação/questão (`POST /api/v1/acompanhamentos`)."""
    payload: dict[str, Any] = {
        "turma_id": turma_id,
        "origem": origem,
        "tipo_acao": tipo_acao.strip(),
        "descricao": descricao.strip(),
    }
    if disciplina_id:
        payload["disciplina_id"] = disciplina_id
    return requisitar_api("POST", "/acompanhamentos", json_body=payload)


def validar_e_confirmar_importacao_api(
    *,
    nome_arquivo: str,
    conteudo_bytes: bytes,
    tipo_importacao: str,
) -> RespostaAPI:
    """Executa a validação (`POST /api/v1/importacoes/validar`) e confirmação (`POST /api/v1/importacoes/{id}/confirmar`)."""
    mime_type = (
        "text/csv"
        if nome_arquivo.lower().endswith(".csv")
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp_val = requisitar_api(
        "POST",
        "/importacoes/validar",
        params={"tipo_importacao": tipo_importacao},
        files={"arquivo": (nome_arquivo, conteudo_bytes, mime_type)},
    )
    if not resp_val.ok or not isinstance(resp_val.dados, dict):
        return resp_val

    lote_id = resp_val.dados.get("id")
    pode_confirmar = bool(resp_val.dados.get("pode_confirmar"))
    if not pode_confirmar or not lote_id:
        return resp_val

    return requisitar_api(
        "POST",
        f"/importacoes/{lote_id}/confirmar",
    )

