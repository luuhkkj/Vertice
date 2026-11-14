# Vértice — Sistema Preditivo de Risco de Evasão e Reprovação Escolar

Plataforma educacional orientada a dados para acompanhamento longitudinal de estudantes anonimizados, análise de avaliações (Mapa de Acertos), controle de participação e entregas de atividades, registro pedagógico, ingestão auditada de previsões de risco (Machine Learning) e construção segura de contexto para Assistente IA.

---

## Visão Geral da Arquitetura

- **Backend API (`backend/`)**: FastAPI, Pydantic v2, SQLAlchemy 2 (`postgresql+psycopg`) e migrações versionadas com Alembic.
- **Banco de Dados**: PostgreSQL 16 (produção/homologação e suíte de integração dedicada em banco isolado `*_test`).
- **Frontend Web (`Frontend vertice/`)**: Aplicação Streamlit integrada integralmente à API REST via `Frontend vertice/data/api_client.py` (sem dados mockados nas telas de produção).
- **CI/CD e Containers**: `docker-compose.yml`, `backend/Dockerfile`, `Frontend vertice/Dockerfile` e `.github/workflows/ci.yml`.

### Estrutura Principal do Repositório

```text
Vertice/
├── .env.example                     # Modelo de variáveis de ambiente para Docker Compose
├── .dockerignore
├── .github/workflows/ci.yml         # Pipeline CI (Ruff, SQLite, PostgreSQL + Alembic, Frontend, Compose E2E)
├── docker-compose.yml               # Orquestração PostgreSQL (isolado) + Migrate + Backend + Frontend
├── docker-compose.postgres-local.yml # Override opcional expondo PostgreSQL apenas em 127.0.0.1
├── pyproject.toml                   # Configuração global do linter Ruff (Python 3.12)
├── docs/
│   ├── INSTALACAO_E_COLD_START.md   # Guia de instalação e bootstrap do zero
│   ├── MANUTENCAO_E_DESENVOLVIMENTO.md # Fluxo de desenvolvimento, Alembic, backup e deploy
│   └── ARQUITETURA_E_COMPATIBILIDADE.md # Autoridade técnica, RBAC, fluxos e compatibilidade
├── backend/
│   ├── alembic/versions/            # Migrações Alembic (Fases 2, 3, 4 e 7)
│   ├── app/
│   │   ├── core/                    # Config Pydantic Settings, JWT/Argon2 e RBAC
│   │   ├── database/                # Base ORM e sessão SQLAlchemy
│   │   ├── integrations/
│   │   │   ├── prediction/          # Previsões append-only, X-Service-Token e anti-leakage
│   │   │   └── assistant/           # Contexto IA escopado, auditoria e abstração LLM
│   │   ├── modules/                 # auth, usuarios, escolas, turmas, disciplinas,
│   │   │                            # atribuicoes, estudantes, importacao, avaliacoes,
│   │   │                            # participacao, acompanhamento, indicadores
│   │   └── scripts/create_admin.py  # CLI para criação do primeiro administrador
│   ├── docs/
│   │   ├── API_ENDPOINTS.md         # Referência completa dos endpoints REST v1
│   │   └── FASE7_INTEGRACAO_PREDITIVA_E_IA.md
│   ├── .env.example
│   ├── Dockerfile
│   ├── pytest.ini                   # Registro do marker `postgres`
│   ├── requirements.txt
│   ├── requirements-dev.txt         # Inclui Ruff para lint local e CI
│   └── tests/                       # Suíte SQLite, paridade OpenAPI e tests/postgres/
└── Frontend vertice/
    ├── app.py                       # Ponto de entrada Streamlit e roteamento por papel
    ├── config.py                    # Configuração de `VERTICE_API_URL`
    ├── components/                  # Auth UI, cards, chat, filtros, gráficos, layout, tabelas
    ├── data/api_client.py           # Cliente HTTP oficial para a API FastAPI
    ├── pages/                       # Telas integradas ao backend real
    └── Dockerfile
```

---

## Segurança, RBAC e Governança de Dados

1. **Papéis Canônicos (`PapelUsuario`)**: exclusivamente `administrador`, `gestor` e `professor`.
2. **Isolamento Multi-escola e por Vínculo**:
   - `administrador`: gerencia usuários, escolas, turmas, disciplinas, atribuições, credenciais de serviço ML e auditoria de rede, sem acesso direto a telas/rotas estritamente pedagógicas (`403` em `/api/v1/indicadores/*`, `/api/v1/importacoes/*`, `/api/v1/assistente/contexto`).
   - `gestor`: restrito à sua `escola_id` em listagens, cadastros, indicadores, importações e auditoria.
   - `professor`: restrito às escolas, turmas e disciplinas vinculadas em `professor_turmas` (suporta unidocência/polivalência com `disciplina_id = NULL`, protegido por índice único parcial no PostgreSQL).
3. **LGPD e Anonimização**: estudantes são identificados exclusivamente por `id` (UUID) e `codigo_anonimo`. A importação bloqueia planilhas com colunas nominais ou dados pessoais identificáveis (nome, CPF, e-mail, telefone, etc.).
4. **Importação em Duas Etapas**:
   - Etapa 1 (`POST /api/v1/importacoes/validar`): valida formato, vínculos, PII e gera prévia sem persistir dados pedagógicos.
   - Etapa 2 (`POST /api/v1/importacoes/{lote_id}/confirmar`): efetiva inserções/atualizações em transação atômica única com rollback integral em falhas.
5. **Anti-Data Leakage e Auditoria IA**:
   - Variáveis usadas em modelos externos passam por contrato fechado (`situacao_final` reservada exclusivamente como futuro alvo supervisionado; campos pós-desfecho, PII e variáveis desconhecidas sem contrato são rejeitados com `HTTP 422`).
   - Solicitações de contexto IA (`POST /api/v1/assistente/contexto`) registram auditoria em `auditoria_consultas_ia` com `request_id` gerado no backend. Enquanto não houver LLM externo conectado, `/api/v1/assistente/consultar` retorna `HTTP 503` de forma controlada.

---

## Documentação Detalhada

- **Guia Completo de Instalação e Cold Start (Docker e Local):** [docs/INSTALACAO_E_COLD_START.md](docs/INSTALACAO_E_COLD_START.md)
- **Guia de Manutenção, Migrações, Testes e Deploy:** [docs/MANUTENCAO_E_DESENVOLVIMENTO.md](docs/MANUTENCAO_E_DESENVOLVIMENTO.md)
- **Arquitetura, Matriz RBAC e Compatibilidade Histórica:** [docs/ARQUITETURA_E_COMPATIBILIDADE.md](docs/ARQUITETURA_E_COMPATIBILIDADE.md)
- **Guia do Backend:** [backend/README.md](backend/README.md)
- **Referência Completa de Endpoints (`v1`):** [backend/docs/API_ENDPOINTS.md](backend/docs/API_ENDPOINTS.md)
- **Arquitetura Preditiva e Assistente IA (Fase 7):** [backend/docs/FASE7_INTEGRACAO_PREDITIVA_E_IA.md](backend/docs/FASE7_INTEGRACAO_PREDITIVA_E_IA.md)

---

## Como Executar com Docker Compose (Recomendado)

### 1. Configurar variáveis de ambiente na raiz

```bash
cp .env.example .env
```

Gere uma `SECRET_KEY` forte (`>= 32` caracteres) e defina uma `POSTGRES_PASSWORD` segura no arquivo `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. Construir e iniciar os serviços

```bash
docker compose up --build -d
```

Ordem controlada de inicialização definida no `docker-compose.yml`:
1. `db` (`postgres:16-alpine`) inicia e aguarda `pg_isready` saudável.
2. `migrate` executa `alembic upgrade head` uma única vez e encerra (`service_completed_successfully`).
3. `backend` (FastAPI/Uvicorn na porta `8000`) sobe após `db` + `migrate` e expõe `/health`.
4. `frontend` (Streamlit na porta `8501`, configurado com `VERTICE_API_URL=http://backend:8000/api/v1`) sobe após `backend` saudável.

### 3. Criar o primeiro administrador

```bash
docker compose exec backend python -m app.scripts.create_admin
```

Acessos locais:
- **Frontend Streamlit**: `http://localhost:8501`
- **API Backend (Health)**: `http://localhost:8000/health`
- **Swagger UI / ReDoc / OpenAPI** (habilitados por padrão em `backend/app/main.py`; restrinja externamente em produção): `http://localhost:8000/docs` | `/redoc` | `/api/v1/openapi.json`

> Por segurança, o `docker-compose.yml` **não publica a porta `5432` do PostgreSQL no host** por padrão. Caso precise conectar ferramentas locais (`psql`, DBeaver, pgAdmin), utilize o override vinculado apenas a `127.0.0.1`:
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.postgres-local.yml up -d
> ```

---

## Como Executar Localmente (Sem Docker)

> Requer **Python 3.12** e **PostgreSQL 16**. Consulte o passo a passo completo para PowerShell e Bash em [docs/INSTALACAO_E_COLD_START.md](docs/INSTALACAO_E_COLD_START.md).

### 1. Backend FastAPI + PostgreSQL

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edite `backend/.env` com os dados do seu PostgreSQL local (`POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) e uma `SECRET_KEY` segura, e execute:

```powershell
alembic upgrade head
python -m app.scripts.create_admin
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Streamlit

Em outro terminal (com ambiente virtual que possua as dependências de `Frontend vertice/requirements.txt`):

```powershell
cd "Frontend vertice"
pip install -r requirements.txt
$env:VERTICE_API_URL = "http://127.0.0.1:8000/api/v1"
streamlit run app.py
```

---

## Execução de Lint e Testes Automatizados

### 1. Lint Estático (Ruff — Backend e Frontend)

```powershell
# A partir da raiz do repositório (após instalar backend/requirements-dev.txt)
ruff check backend "Frontend vertice"
```

### 2. Suíte Principal (SQLite em memória, sem dependência externa)

```powershell
cd backend
pytest -m "not postgres" -v
```

### 3. Suíte Real de PostgreSQL + Ciclo Completo Alembic

Executa `alembic upgrade head -> downgrade base -> upgrade head -> check`, valida DDL, tipos nativos, chaves estrangeiras, índice único parcial (`disciplina_id IS NULL`), idempotência, rollback atômico e concorrência entre sessões em banco **isolado** com sufixo `_test` (nunca utiliza o banco principal configurado no `.env`):

```powershell
cd backend
# Opção A: usando credenciais do backend/.env (cria e remove automaticamente o banco efêmero `vertice_test`)
pytest tests/postgres/test_postgres_integracao.py -m postgres -v

# Opção B: informando URL dedicada terminado obrigatoriamente em `_test`
$env:VERTICE_TEST_DATABASE_URL = "postgresql+psycopg://usuario:senha@localhost:5432/vertice_test"
pytest tests/postgres/test_postgres_integracao.py -m postgres -v
```

---

## Licença

Consulte o arquivo [LICENSE](LICENSE).
