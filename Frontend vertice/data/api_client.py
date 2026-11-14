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
    r"(Bearer\s+[A-Za-z0-9\-_\.]+|eyJ[A-Za-z0-9\-_\.]+|vtx_ml_[A-Za-z0-9\-_]+)",
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
    headers: Optional[dict[str, str]] = None


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


def registrar_usuario_sessao(
    usuario: Any,
    email_fallback: Optional[str] = None,
) -> str:
    """Armazena os dados canônicos do usuário autenticado em `st.session_state` sem alterar o papel do backend."""
    usuario_dict = usuario if isinstance(usuario, dict) else {}
    papel = str(usuario_dict.get("papel") or "").strip().lower()
    if papel not in ("administrador", "gestor", "professor"):
        papel = "professor"

    nome = str(
        usuario_dict.get("nome")
        or usuario_dict.get("nome_completo")
        or ""
    ).strip()
    email = str(usuario_dict.get("email") or email_fallback or "").strip().lower()
    escola_id = usuario_dict.get("escola_id")

    st.session_state["usuario_api"] = usuario_dict
    st.session_state["perfil"] = papel
    st.session_state["papel_api"] = papel
    st.session_state["nome_atual"] = nome or email
    st.session_state["professor_atual"] = nome if papel == "professor" else None
    st.session_state["email_atual"] = email
    st.session_state["escola_id_atual"] = str(escola_id) if escola_id else None
    st.session_state.pop("escola_nome_atual", None)
    return papel


def limpar_estado_sessao() -> None:
    """Remove todos os dados de autenticação e contexto pessoal da sessão atual."""
    for chave in (
        "access_token",
        "usuario_api",
        "perfil",
        "papel_api",
        "nome_atual",
        "professor_atual",
        "email_atual",
        "escola_id_atual",
        "escola_nome_atual",
        "sessao_api_expirada",
        "mensagem_sessao_expirada",
        "entrada_lote_atual",
        "entrada_resultado",
    ):
        st.session_state.pop(chave, None)


def limpar_sessao_expirada(mensagem: Optional[str] = None) -> None:
    """Remove credenciais expiradas da sessão e registra aviso claro de expiração."""
    st.session_state.pop("access_token", None)
    st.session_state.pop("usuario_api", None)
    st.session_state["logado"] = False
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
    headers_resp = {
        str(k).lower(): str(v)
        for k, v in (getattr(resp, "headers", None) or {}).items()
    }
    payload: Any = None
    json_invalido = False
    if getattr(resp, "content", b""):
        try:
            payload = resp.json()
        except Exception:
            payload = None
            json_invalido = True

    if 200 <= status_code < 300:
        if json_invalido and status_code != 204:
            return RespostaAPI(
                ok=False,
                status_code=status_code,
                erro="O servidor retornou uma resposta em formato inesperado.",
                headers=headers_resp,
            )
        st.session_state.pop("sessao_api_expirada", None)
        st.session_state.pop("mensagem_sessao_expirada", None)
        return RespostaAPI(
            ok=True,
            status_code=status_code,
            dados=payload,
            headers=headers_resp,
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
            headers=headers_resp,
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
            headers=headers_resp,
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
        headers=headers_resp,
    )


def requisitar_bytes_api(
    metodo: str,
    caminho: str,
    *,
    params: Optional[dict[str, Any]] = None,
    exigir_auth: bool = True,
    timeout: float = 15.0,
) -> RespostaAPI:
    """Executa requisição HTTP autenticada esperando conteúdo binário (ex.: download de CSV/XLSX)."""
    token = obter_token_sessao()
    if exigir_auth and not token:
        return RespostaAPI(
            ok=False,
            status_code=401,
            erro="Sessão não autenticada na API. Realize o login para continuar.",
            sessao_expirada=bool(st.session_state.get("sessao_api_expirada", False)),
        )

    headers: dict[str, str] = {"Accept": "*/*"}
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
            resp = _cliente_http_override(
                metodo.upper(),
                f"/api/v1{caminho_norm}",
                params=params_limpos,
                headers=headers,
            )
        else:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(
                    method=metodo.upper(),
                    url=f"{API_BASE_URL}{caminho_norm}",
                    params=params_limpos,
                    headers=headers,
                )
    except Exception:
        return RespostaAPI(
            ok=False,
            status_code=None,
            erro="Não foi possível conectar ao servidor do Vértice para baixar o arquivo.",
            indisponivel=True,
        )

    status_code = int(resp.status_code)
    headers_resp = {
        str(k).lower(): str(v)
        for k, v in (getattr(resp, "headers", None) or {}).items()
    }
    if 200 <= status_code < 300:
        return RespostaAPI(
            ok=True,
            status_code=status_code,
            dados=bytes(getattr(resp, "content", b"") or b""),
            headers=headers_resp,
        )

    payload: Any = None
    try:
        if getattr(resp, "content", b""):
            payload = resp.json()
    except Exception:
        payload = None

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
            headers=headers_resp,
        )
    if status_code == 403:
        return RespostaAPI(
            ok=False,
            status_code=403,
            erro=_extrair_detalhe_erro(payload, "Permissão insuficiente para baixar o modelo."),
            sem_permissao=True,
            headers=headers_resp,
        )
    return RespostaAPI(
        ok=False,
        status_code=status_code,
        erro=_extrair_detalhe_erro(
            payload,
            f"Falha ao baixar o arquivo solicitado (HTTP {status_code}).",
        ),
        headers=headers_resp,
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
            registrar_usuario_sessao(usuario, email_fallback=email)
            st.session_state.pop("sessao_api_expirada", None)
            st.session_state.pop("mensagem_sessao_expirada", None)
    return resposta


def obter_usuario_atual_api() -> RespostaAPI:
    """Consulta o perfil completo do usuário autenticado (`GET /api/v1/auth/me`)."""
    resposta = requisitar_api("GET", "/auth/me")
    if resposta.ok and isinstance(resposta.dados, dict):
        registrar_usuario_sessao(resposta.dados)
    return resposta


def encerrar_sessao_api() -> None:
    """Solicita encerramento lógico de sessão no backend (`POST /auth/logout`) e limpa o estado local."""
    if possui_sessao_api_ativa():
        requisitar_api("POST", "/auth/logout", exigir_auth=False, timeout=3.0)
    limpar_estado_sessao()
    st.session_state["logado"] = False


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


def listar_escolas_api(skip: int = 0, limit: int = 100) -> RespostaAPI:
    """Lista as escolas acessíveis ao usuário autenticado (`GET /api/v1/escolas`)."""
    return requisitar_api("GET", "/escolas", params={"skip": skip, "limit": limit})


def obter_escola_api(escola_id: str) -> RespostaAPI:
    """Obtém os detalhes de uma escola específica (`GET /api/v1/escolas/{id}`)."""
    return requisitar_api("GET", f"/escolas/{escola_id}")


def listar_usuarios_api(
    *,
    skip: int = 0,
    limit: int = 100,
    papel: Optional[str] = None,
    apenas_ativos: Optional[bool] = None,
) -> RespostaAPI:
    """Lista usuários permitidos para administrador ou gestor (`GET /api/v1/usuarios`)."""
    params: dict[str, Any] = {"skip": skip, "limit": limit}
    if papel:
        params["papel"] = papel
    if apenas_ativos is not None:
        params["apenas_ativos"] = str(apenas_ativos).lower()
    return requisitar_api("GET", "/usuarios", params=params)


def listar_turmas_api() -> RespostaAPI:
    """Lista as turmas autorizadas para o usuário autenticado (`GET /api/v1/turmas`)."""
    return requisitar_api("GET", "/turmas")


def listar_disciplinas_api() -> RespostaAPI:
    """Lista as disciplinas cadastradas (`GET /api/v1/disciplinas`)."""
    return requisitar_api("GET", "/disciplinas")


def listar_atribuicoes_api() -> RespostaAPI:
    """Lista os vínculos de turma e disciplina (`GET /api/v1/atribuicoes`)."""
    return requisitar_api("GET", "/atribuicoes")


def criar_atribuicao_api(
    *,
    professor_id: str,
    turma_id: str,
    disciplina_id: Optional[str] = None,
) -> RespostaAPI:
    """Cria uma atribuição docente em `POST /api/v1/atribuicoes`."""
    payload: dict[str, Any] = {
        "professor_id": professor_id,
        "turma_id": turma_id,
        "disciplina_id": disciplina_id if disciplina_id else None,
    }
    return requisitar_api("POST", "/atribuicoes", json_body=payload)


def remover_atribuicao_api(atribuicao_id: str) -> RespostaAPI:
    """Remove uma atribuição docente em `DELETE /api/v1/atribuicoes/{id}`."""
    return requisitar_api("DELETE", f"/atribuicoes/{atribuicao_id}")


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
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    estudante_id: Optional[str] = None,
    tipo_acao: str,
    descricao: str,
    origem: str = "MAPA_ACERTOS",
) -> RespostaAPI:
    """Registra uma ação pedagógica vinculada à avaliação, participação ou estudante (`POST /api/v1/acompanhamentos`)."""
    origem_limpa = str(origem).strip().upper()
    if origem_limpa == "AVALIACAO":
        origem_limpa = "MAPA_ACERTOS"
    payload: dict[str, Any] = {
        "origem": origem_limpa,
        "tipo_acao": tipo_acao.strip(),
        "descricao": descricao.strip(),
    }
    if turma_id:
        payload["turma_id"] = turma_id
    if disciplina_id:
        payload["disciplina_id"] = disciplina_id
    if estudante_id:
        payload["estudante_id"] = estudante_id
    return requisitar_api("POST", "/acompanhamentos", json_body=payload)


def validar_importacao_api(
    *,
    nome_arquivo: str,
    conteudo_bytes: bytes,
    tipo_importacao: Optional[str] = None,
) -> RespostaAPI:
    """Etapa 1: envia e valida um dataset sem persistir dados acadêmicos (`POST /api/v1/importacoes/validar`)."""
    mime_type = (
        "text/csv"
        if nome_arquivo.lower().endswith(".csv")
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    tipo_norm = (
        tipo_importacao.strip().upper().replace("-", "_")
        if isinstance(tipo_importacao, str) and tipo_importacao.strip()
        else None
    )
    params = {"tipo_importacao": tipo_norm} if tipo_norm else None
    return requisitar_api(
        "POST",
        "/importacoes/validar",
        params=params,
        files={"arquivo": (nome_arquivo, conteudo_bytes, mime_type)},
        timeout=30.0,
    )


def confirmar_importacao_api(lote_id: str) -> RespostaAPI:
    """Etapa 2: confirma explicitamente um lote validado (`POST /api/v1/importacoes/{id}/confirmar`)."""
    return requisitar_api("POST", f"/importacoes/{lote_id}/confirmar", timeout=30.0)


def descartar_importacao_api(lote_id: str) -> RespostaAPI:
    """Descarta explicitamente um lote pendente (`POST /api/v1/importacoes/{id}/descartar`)."""
    return requisitar_api("POST", f"/importacoes/{lote_id}/descartar")


def obter_previa_importacao_api(lote_id: str) -> RespostaAPI:
    """Consulta o relatório e a prévia de um lote (`GET /api/v1/importacoes/{id}/previa`)."""
    return requisitar_api("GET", f"/importacoes/{lote_id}/previa")


def listar_importacoes_api(skip: int = 0, limit: int = 50) -> RespostaAPI:
    """Lista o histórico real de lotes de importação no escopo do usuário (`GET /api/v1/importacoes`)."""
    return requisitar_api("GET", "/importacoes", params={"skip": skip, "limit": limit})


def baixar_modelo_importacao_api(
    tipo_modelo: str,
    formato: str = "csv",
) -> RespostaAPI:
    """Baixa o arquivo modelo oficial de planilha do backend (`GET /api/v1/importacoes/modelos/{tipo}`)."""
    rotas_modelos = {
        "avaliacoes": "/importacoes/modelos/avaliacoes",
        "dados_escolares": "/importacoes/modelos/dados-escolares",
        "dados-escolares": "/importacoes/modelos/dados-escolares",
        "atividades": "/importacoes/modelos/atividades",
    }
    rota = rotas_modelos.get(tipo_modelo.strip().lower())
    if not rota:
        return RespostaAPI(ok=False, status_code=400, erro="Tipo de modelo de planilha inválido.")
    return requisitar_bytes_api("GET", rota, params={"formato": formato})


def listar_atividades_api(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    periodo_letivo: Optional[str] = None,
    status: Optional[str] = None,
) -> RespostaAPI:
    """Lista atividades no escopo do usuário autenticado (`GET /api/v1/atividades`)."""
    return requisitar_api(
        "GET",
        "/atividades",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "periodo_letivo": periodo_letivo,
            "status": status,
        },
    )


def criar_atividade_api(
    *,
    codigo: str,
    titulo: str,
    turma_id: str,
    disciplina_id: str,
    periodo_letivo: str,
    data_limite: str,
    nota_maxima: Optional[float] = None,
    status: str = "ABERTA",
    gerar_entregas_esperadas: bool = True,
) -> RespostaAPI:
    """Cria uma atividade (`POST /api/v1/atividades`)."""
    payload: dict[str, Any] = {
        "codigo": codigo.strip(),
        "titulo": titulo.strip(),
        "turma_id": turma_id,
        "disciplina_id": disciplina_id,
        "periodo_letivo": periodo_letivo.strip(),
        "data_limite": data_limite,
        "status": str(status).upper(),
        "gerar_entregas_esperadas": gerar_entregas_esperadas,
    }
    if nota_maxima is not None:
        payload["nota_maxima"] = float(nota_maxima)
    return requisitar_api("POST", "/atividades", json_body=payload)


def atualizar_atividade_api(
    *,
    atividade_id: str,
    titulo: Optional[str] = None,
    periodo_letivo: Optional[str] = None,
    data_limite: Optional[str] = None,
    nota_maxima: Optional[float] = None,
    status: Optional[str] = None,
    ativo: Optional[bool] = None,
) -> RespostaAPI:
    """Atualiza dados cadastrais ou data limite de uma atividade (`PATCH /api/v1/atividades/{id}`)."""
    payload: dict[str, Any] = {}
    if titulo is not None:
        payload["titulo"] = titulo.strip()
    if periodo_letivo is not None:
        payload["periodo_letivo"] = periodo_letivo.strip()
    if data_limite is not None:
        payload["data_limite"] = data_limite
    if nota_maxima is not None:
        payload["nota_maxima"] = float(nota_maxima)
    if status is not None:
        payload["status"] = status
    if ativo is not None:
        payload["ativo"] = ativo
    return requisitar_api(
        "PATCH",
        f"/atividades/{atividade_id}",
        json_body=payload,
    )


def gerar_entregas_esperadas_api(
    atividade_id: str,
    *,
    data_referencia: Optional[str] = None,
) -> RespostaAPI:
    """Gera de forma idempotente as entregas esperadas da atividade (`POST /api/v1/atividades/{id}/gerar-entregas-esperadas`)."""
    return requisitar_api(
        "POST",
        f"/atividades/{atividade_id}/gerar-entregas-esperadas",
        params={"data_referencia": data_referencia},
    )


def listar_entregas_atividade_api(
    atividade_id: str,
    *,
    estudante_id: Optional[str] = None,
) -> RespostaAPI:
    """Lista entregas esperadas e realizadas de uma atividade (`GET /api/v1/atividades/{id}/entregas`)."""
    return requisitar_api(
        "GET",
        f"/atividades/{atividade_id}/entregas",
        params={"estudante_id": estudante_id},
    )


def registrar_entrega_atividade_api(
    *,
    atividade_id: str,
    estudante_id: Optional[str] = None,
    codigo_anonimo: Optional[str] = None,
    data_entrega: Optional[str] = None,
    nota: Optional[float] = None,
    status_entrega: Optional[str] = None,
    incluir_nota: bool = True,
) -> RespostaAPI:
    """Registra ou atualiza entrega por estudante (`POST /api/v1/atividades/{id}/entregas`)."""
    payload: dict[str, Any] = {
        "data_entrega": data_entrega,
    }
    if estudante_id:
        payload["estudante_id"] = estudante_id
    elif codigo_anonimo:
        payload["codigo_anonimo"] = codigo_anonimo.strip()
    if incluir_nota:
        payload["nota"] = nota
    if status_entrega:
        payload["status_entrega"] = status_entrega
    return requisitar_api(
        "POST",
        f"/atividades/{atividade_id}/entregas",
        json_body=payload,
    )


def atualizar_entrega_por_id_api(
    *,
    entrega_id: str,
    data_entrega: Optional[str] = None,
    nota: Optional[float] = None,
    status_entrega: Optional[str] = None,
    incluir_data_entrega: bool = True,
    incluir_nota: bool = True,
) -> RespostaAPI:
    """Atualiza entrega existente pelo ID (`PATCH /api/v1/entregas/{id}`)."""
    payload: dict[str, Any] = {}
    if incluir_data_entrega:
        payload["data_entrega"] = data_entrega
    if incluir_nota:
        payload["nota"] = nota
    if status_entrega:
        payload["status_entrega"] = status_entrega
    return requisitar_api(
        "PATCH",
        f"/entregas/{entrega_id}",
        json_body=payload,
    )


def consultar_indicadores_participacao(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    periodo_letivo: Optional[str] = None,
    atividade_id: Optional[str] = None,
    estudante_id: Optional[str] = None,
    ano_letivo: Optional[int] = None,
    data_referencia: Optional[str] = None,
) -> RespostaAPI:
    """Consulta `GET /api/v1/indicadores/participacao` com os filtros selecionados."""
    return requisitar_api(
        "GET",
        "/indicadores/participacao",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "periodo_letivo": periodo_letivo,
            "atividade_id": atividade_id,
            "estudante_id": estudante_id,
            "ano_letivo": ano_letivo,
            "data_referencia": data_referencia,
        },
    )


def listar_acompanhamentos_api(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    estudante_id: Optional[str] = None,
    origem: Optional[str] = None,
) -> RespostaAPI:
    """Lista acompanhamentos pedagógicos (`GET /api/v1/acompanhamentos`)."""
    return requisitar_api(
        "GET",
        "/acompanhamentos",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "estudante_id": estudante_id,
            "origem": origem,
        },
    )


# ==============================================================================
# FASE 7 — INTEGRAÇÃO PREDITIVA E CONTEXTO DE ASSISTENTE IA
# ==============================================================================


def consultar_indicadores_gerais_api(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    ano_letivo: Optional[int] = None,
    periodo_letivo: Optional[str] = None,
    modelo_nome: Optional[str] = None,
    modelo_versao: Optional[str] = None,
) -> RespostaAPI:
    """Consulta indicadores gerais consolidados (`GET /api/v1/indicadores/gerais`)."""
    return requisitar_api(
        "GET",
        "/indicadores/gerais",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "ano_letivo": ano_letivo,
            "periodo_letivo": periodo_letivo,
            "modelo_nome": modelo_nome,
            "modelo_versao": modelo_versao,
        },
    )


def listar_estudantes_api(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    ano_letivo: Optional[int] = None,
    periodo_letivo: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
) -> RespostaAPI:
    """Lista estudantes anonimizados no escopo autorizado (`GET /api/v1/estudantes`)."""
    return requisitar_api(
        "GET",
        "/estudantes",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "ano_letivo": ano_letivo,
            "periodo_letivo": periodo_letivo,
            "skip": skip,
            "limit": limit,
        },
    )


def obter_estudante_historico_api(estudante_id: str) -> RespostaAPI:
    """Obtém histórico escolar anonimizado de um estudante (`GET /api/v1/estudantes/{id}`)."""
    return requisitar_api("GET", f"/estudantes/{estudante_id}")


def consultar_resumo_previsoes_api(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    ano_letivo: Optional[int] = None,
    periodo_letivo: Optional[str] = None,
    tipo_previsao: Optional[str] = None,
    modelo_nome: Optional[str] = None,
    modelo_versao: Optional[str] = None,
) -> RespostaAPI:
    """Consulta resumo agregado de previsões de risco (`GET /api/v1/previsoes/resumo`)."""
    return requisitar_api(
        "GET",
        "/previsoes/resumo",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "ano_letivo": ano_letivo,
            "periodo_letivo": periodo_letivo,
            "tipo_previsao": tipo_previsao,
            "modelo_nome": modelo_nome,
            "modelo_versao": modelo_versao,
        },
    )


def listar_previsoes_api(
    *,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    ano_letivo: Optional[int] = None,
    periodo_letivo: Optional[str] = None,
    tipo_previsao: Optional[str] = None,
    faixa_risco: Optional[str] = None,
    modelo_nome: Optional[str] = None,
    modelo_versao: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
) -> RespostaAPI:
    """Lista previsões de risco autorizadas (`GET /api/v1/previsoes`)."""
    return requisitar_api(
        "GET",
        "/previsoes",
        params={
            "turma_id": turma_id,
            "disciplina_id": disciplina_id,
            "ano_letivo": ano_letivo,
            "periodo_letivo": periodo_letivo,
            "tipo_previsao": tipo_previsao,
            "faixa_risco": faixa_risco,
            "modelo_nome": modelo_nome,
            "modelo_versao": modelo_versao,
            "skip": skip,
            "limit": limit,
        },
    )


def consultar_previsoes_estudante_api(
    estudante_id: str,
    *,
    tipo_previsao: Optional[str] = None,
    modelo_nome: Optional[str] = None,
    modelo_versao: Optional[str] = None,
) -> RespostaAPI:
    """Consulta histórico append-only de previsões de um estudante (`GET /api/v1/previsoes/estudantes/{id}`)."""
    return requisitar_api(
        "GET",
        f"/previsoes/estudantes/{estudante_id}",
        params={
            "tipo_previsao": tipo_previsao,
            "modelo_nome": modelo_nome,
            "modelo_versao": modelo_versao,
        },
    )


def consultar_status_assistente_api() -> RespostaAPI:
    """Consulta prontidão arquitetural do Assistente IA (`GET /api/v1/assistente/status`)."""
    return requisitar_api("GET", "/assistente/status")


def construir_contexto_assistente_api(
    *,
    tipo_contexto: str,
    escola_id: Optional[str] = None,
    turma_id: Optional[str] = None,
    disciplina_id: Optional[str] = None,
    estudante_id: Optional[str] = None,
    ano_letivo: Optional[int] = None,
    periodo_letivo: Optional[str] = None,
    modelo_nome: Optional[str] = None,
    modelo_versao: Optional[str] = None,
    incluir_acompanhamentos: bool = True,
    conversation_id: Optional[str] = None,
) -> RespostaAPI:
    """Solicita montagem autorizada e auditada de contexto para IA (`POST /api/v1/assistente/contexto`)."""
    payload: dict[str, Any] = {
        "tipo_contexto": tipo_contexto,
        "incluir_acompanhamentos": incluir_acompanhamentos,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if escola_id:
        payload["escola_id"] = escola_id
    if turma_id:
        payload["turma_id"] = turma_id
    if disciplina_id:
        payload["disciplina_id"] = disciplina_id
    if estudante_id:
        payload["estudante_id"] = estudante_id
    if ano_letivo is not None:
        payload["ano_letivo"] = ano_letivo
    if periodo_letivo:
        payload["periodo_letivo"] = periodo_letivo
    if modelo_nome:
        payload["modelo_nome"] = modelo_nome
    if modelo_versao:
        payload["modelo_versao"] = modelo_versao
    return requisitar_api("POST", "/assistente/contexto", json_body=payload)



