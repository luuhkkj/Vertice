# Guia de Manutenção, Desenvolvimento e Operação — Projeto Vértice

Este manual documenta os fluxos internos de desenvolvimento, migrações de banco de dados, suítes de testes automatizados, linting, solução de problemas recorrentes, backup/restore e requisitos para ambientes de deploy.

---

## 1. Organização do Código e Responsabilidades

```text
Vertice/
├── .github/workflows/ci.yml               # Pipeline oficial (Ruff, SQLite, Postgres+Alembic, Frontend, Docker E2E)
├── pyproject.toml                         # Configuração de versão-alvo (py312) e regras do Ruff
├── docker-compose.yml                     # Stack padrão (PostgreSQL isolado internamente + Migrate + Backend + Frontend)
├── docker-compose.postgres-local.yml      # Override opcional expondo Postgres somente em 127.0.0.1
├── backend/
│   ├── app/
│   │   ├── main.py                        # App FastAPI, CORS, rotas raiz (/health) e router v1
│   │   ├── api/v1/router.py               # Agregador central dos prefixos de /api/v1
│   │   ├── core/                          # Settings Pydantic (config.py), JWT/Argon2 (security.py), RBAC (dependencies.py)
│   │   ├── database/                      # DeclarativeBase (base.py), SessionLocal/get_db (connection.py) e registro ORM (__init__.py)
│   │   ├── modules/                       # Domínios de negócio (router -> service -> repository -> models/schemas)
│   │   ├── integrations/
│   │   │   ├── prediction/                # Pipeline ML externo, credenciais X-Service-Token, append-only e anti-leakage
│   │   │   └── assistant/                 # Contexto estruturado autorizado, auditoria IA e ProvedorLLMBase
│   │   └── scripts/create_admin.py        # CLI oficial de bootstrap do administrador
│   ├── alembic/                           # Versões de migração e env.py conectado ao Base.metadata
│   ├── docs/                              # Contratos REST (API_ENDPOINTS.md) e arquitetura Fase 7
│   ├── tests/                             # Suíte SQLite + suíte PostgreSQL isolada (tests/postgres/)
│   ├── requirements.txt                   # Dependências de produção/testes
│   └── requirements-dev.txt               # Inclui requirements.txt + Ruff
└── Frontend vertice/
    ├── app.py                             # Controle de sessão e roteamento dinâmico por PapelUsuario
    ├── config.py                          # Leitura de VERTICE_API_URL
    ├── data/api_client.py                 # Cliente HTTP oficial único para comunicação com o FastAPI
    ├── data/mock_data.py                  # Legado vazio mantido apenas para teste retroativo (nunca importado em pages/)
    ├── components/                        # UI reutilizável (auth, gráficos, filtros, tabelas, layout)
    ├── pages/                             # Páginas Streamlit integradas aos endpoints reais
    ├── styles/ & utils/ & assets/         # Estilos visuais, validadores de upload e ícones
```

### 1.1 Regra de Ouro do Frontend (`Frontend vertice/data/api_client.py`)
- Toda chamada HTTP à API FastAPI deve passar exclusivamente por `Frontend vertice/data/api_client.py`.
- As páginas em `Frontend vertice/pages/` nunca devem instanciar `httpx` diretamente nem manter URLs ou cabeçalhos `Authorization` manualmente.
- Trate sempre os estados padronizados de `RespostaAPI` / contexto: `sessao_expirada` (`401`), `sem_permissao` (`403`) e erro de rede/conectividade sem simular sucesso nem exibir dados fictícios.

---

## 2. Passo a Passo para Adicionar Novas Funcionalidades

Ao estender o sistema com um novo módulo ou endpoint, siga esta sequência para preservar integridade de schema, RBAC e documentação:

1. **Modelo ORM (`backend/app/modules/<modulo>/models.py`):**
   - Herde de `Base` (`app.database.base`).
   - Utilize UUIDs (`uuid.UUID`), `DateTime(timezone=True)` e chaves estrangeiras explícitas (`escola_id`, `turma_id`, etc.) quando aplicável.
   - Garanta a importação explícita do novo modelo em `backend/app/database/__init__.py` para que o Alembic o detecte.
2. **Migração Alembic (`backend/alembic/versions/`):**
   - Gere e revise a migração (detalhes na seção 3).
3. **Schemas Pydantic (`schemas.py`):**
   - Separe entrada (`Create`/`Update`) e saída (`Response` com `ConfigDict(from_attributes=True)`). Nunca exponha hashes, segredos ou PII de estudantes.
4. **Repository (`repository.py`) e Service (`service.py`):**
   - Aplique validação estrita de escopo multi-escola (`usuario.escola_id` para `gestor`) e vínculo `ProfessorTurma` (incluindo suporte a `disciplina_id IS NULL`) na camada de serviço antes de persistir ou retornar dados.
5. **Router (`router.py`) e Registro (`backend/app/api/v1/router.py`):**
   - Proteja cada rota com a dependência correta de `app/core/dependencies.py` (`require_admin`, `require_gestor_ou_admin`, `require_importacao_datasets`, `require_acesso_pedagogico`, `require_qualquer_papel` ou `get_current_user`).
6. **Contrato de Documentação (`backend/docs/API_ENDPOINTS.md`):**
   - Documente o método, rota e payload na tabela correspondente. A suíte inclui o teste automatizado `backend/tests/test_api_docs_parity.py`, que **falhará** se houver rota no OpenAPI não documentada (ou rota documentada inexistente no app).
7. **Integração Frontend (`data/api_client.py` + `pages/`):**
   - Exponha funções encapsuladas em `api_client.py` e consuma na página respeitando o papel em `app.py`.
8. **Qualidade e Testes:**
   - Crie testes unitários/integração em `backend/tests/`, rode Ruff, SQLite e PostgreSQL antes de abrir PR/commit.

---

## 3. Manutenção de Banco de Dados e Migrações Alembic

### 3.1 Histórico Atual de Migrações (`backend/alembic/versions/`)
1. `cf6d26153444_fase2_estrutura_escolar_e_autenticacao.py`
2. `3b89a40eef44_auditoria_fase2_indices_e_escopo_escola.py`
3. `84432f883f08_fase3_estudantes_historico_e_importacao.py`
4. `6cae35b44675_fase4_avaliacoes_participacao_.py`
5. `895c2d02321f_fase7_previsoes_risco_e_auditoria_ia.py`
6. `fe9cc2998c62_fase7_auditoria_request_e_conversation_.py`

### 3.2 Fluxo Seguro de Alteração de Schema
Com o PostgreSQL de desenvolvimento ativo e configurado em `backend/.env`:

```bash
cd backend

# 1. Conferir se a base está na revisão mais recente
alembic current
alembic heads

# 2. Verificar se há desvios antes de alterar modelos
alembic check

# 3. Após alterar/criar modelos registrados em app/database/__init__.py:
alembic revision --autogenerate -m "descricao_objetiva_da_mudanca"

# 4. REVISAR o arquivo Python gerado em backend/alembic/versions/!
# Confirme downgrade(), enums PostgreSQL, constraints e índices parciais.

# 5. Aplicar migração localmente
alembic upgrade head

# 6. Validar reversibilidade (teste também em PostgreSQL isolado com pytest -m postgres)
alembic downgrade -1
alembic upgrade head
alembic check
```

> **Regra Inviolável:** jamais execute `CREATE TABLE`, `ALTER TABLE` ou edição manual de constraints diretamente no banco de homologação/produção fora de uma migração versionada pelo Alembic.

---

## 4. Rotina Oficial de Lint e Testes

### 4.1 Lint Estático (Ruff)
Configurado no arquivo raiz `pyproject.toml` (`target-version = "py312"`, verificando bugs de sintaxe/tipagem como nomes indefinidos `F821`, imports não usados `F401`, comparações/expressões inválidas `E7`/`E9` e armadilhas mutáveis `B`, exceto `B008` utilizado por `Depends`/`Query`/`File` do FastAPI).

```bash
# Instale as dependências de desenvolvimento na venv do backend:
pip install -r backend/requirements-dev.txt

# Executar da raiz do repositório Vertice/:
ruff check backend "Frontend vertice"
```

### 4.2 Compilação, Schema OpenAPI e Paridade de Documentação
```bash
cd backend
python -m compileall -q app tests
cd ..
python -m compileall -q "Frontend vertice"
```

### 4.3 Suíte Principal (SQLite em Memória — Sem Banco Externo)
Cada teste roda em um banco limpo via `backend/tests/conftest.py`:

```bash
cd backend
pytest -m "not postgres" -v
```

### 4.4 Suíte Real PostgreSQL + Ciclo Completo Alembic
Executa `alembic upgrade head -> downgrade base -> upgrade head -> check`, valida DDL, tipos nativos, FKs, índice único parcial `disciplina_id IS NULL`, idempotência, rollback em falhas e concorrência.

Por proteção, exige explicitamente um banco terminado em `_test` (ex: `vertice_test`) e **nunca altera o banco principal** da aplicação:

```powershell
cd backend
# Usando credenciais do backend/.env (cria e remove vertice_test automaticamente):
pytest tests/postgres/test_postgres_integracao.py -m postgres -v

# Ou informando URL dedicada (obrigatório terminar em _test):
$env:VERTICE_TEST_DATABASE_URL = "postgresql+psycopg://usuario:senha@localhost:5432/vertice_test"
pytest tests/postgres/test_postgres_integracao.py -m postgres -v
```

---

## 5. Diagnóstico e Solução de Falhas Comuns

| Sintoma / Erro | Causa Provável | Como Resolver |
| :--- | :--- | :--- |
| **`ValidationError` na subida do backend citando `SECRET_KEY` ou `DATABASE_URL`** | `.env` ausente, `SECRET_KEY < 32` chars, valor contendo placeholder (`change-this`) ou credencial PostgreSQL vazia | Gere chave com `secrets.token_urlsafe(48)` e preencha `POSTGRES_*` no `.env` correto |
| **`Configuração insegura: DEBUG=True não é permitido em produção`** | `ENVIRONMENT=production` combinado com `DEBUG=True`, `CORS=*`, SQLite ou senha fraca (`postgres`, `123456`, etc.) | Em produção use `DEBUG=False`, liste origens CORS explícitas e utilize senha forte no PostgreSQL |
| **`Failed to connect to dockerDesktopLinuxEngine` / Serviço Docker parado no Windows** | Docker Desktop fechado ou serviço `com.docker.service` parado | Abra o aplicativo **Docker Desktop**, aguarde o motor WSL2 ficar pronto e tente `docker compose ps` novamente |
| **`HTTP 403` em `/api/v1/importacoes/*`, `/api/v1/indicadores/*` ou `/api/v1/assistente/contexto` ao usar token de `administrador`** | Comportamento intencional de governança | Somente `gestor` (da escola) e `professor` (com vínculo em `professor_turmas`) acessam dados/importações pedagógicas |
| **Professor recebe lista vazia ou `HTTP 403` ao importar/listar turma** | Falta vínculo ativo em `professor_turmas`, turma/escola inativa, ou arquivo misturando turmas de duas escolas diferentes | Cadastre a atribuição em `POST /api/v1/atribuicoes` (ou UI *Atribuir turmas*) e separe planilhas por escola |
| **Erro na Etapa 1 (`validar`) acusando coluna ou padrão PII** | Planilha contém colunas como `nome`, `cpf`, `rg`, `email`, `telefone`, ou `codigo_anonimo` sem dígitos/separadores que parece nome próprio | Remova identificadores pessoais da planilha na escola e adote códigos anonimizados (`EST-2026-001`) |
| **`HTTP 409 Conflict` ao editar questão (`PATCH /api/v1/questoes/{id}`)** | A questão já possui respostas registradas | Por preservação histórica, `tipo_questao`, `alternativa_correta` e `valor_questao` ficam bloqueados após receber respostas |
| **`HTTP 503 Service Unavailable` em `POST /api/v1/assistente/consultar`** | Provedor LLM externo ainda não plugado | Comportamento esperado de `ProvedorLLMNaoConfigurado`; `/assistente/contexto` e `/assistente/auditoria` continuam plenamente funcionais |
| **Erro de CORS no navegador ao acessar backend em outro host/porta** | Origem do frontend ausente em `BACKEND_CORS_ORIGINS` | Adicione a origem exata (esquema + host + porta) em `BACKEND_CORS_ORIGINS` no `.env` |

---

## 6. Persistência, Backup e Restore do PostgreSQL

### 6.1 Comportamento de `down` vs `down -v` (Cuidado Crítico)
- **`docker compose down`**: interrompe e remove os containers/redes, mas **PRESERVA** integralmente o volume `vertice_postgres_data`. Ao subir novamente com `docker compose up -d`, todos os usuários, escolas, boletins e logs permanecem intactos.
- **`docker compose down -v`**: **APAGA PERMANENTE E IRREVERSIVELMENTE** o volume `vertice_postgres_data` e todo o banco de dados. Nunca use `-v` em ambiente com dados reais sem backup validado previamente.

### 6.2 Backup Lógico (`pg_dump`) via Docker Compose
Com o container `db` ativo (`-T` desabilita alocação de TTY):

```bash
# Gera dump comprimido em formato custom (-Fc) seguro no host:
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backup_vertice_$(date +%Y%m%d_%H%M).dump
```

*(No PowerShell do Windows, substitua `$(date +%Y%m%d_%H%M)` por `$(Get-Date -Format 'yyyyMMdd_HHmm')`.)*

### 6.3 Restore (`pg_restore`) em Banco Limpo ou de Homologação

```bash
# Garanta que backend esteja parado durante restore estrutural para evitar conexões concorrentes:
docker compose stop backend

docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < backup_vertice_20261113_1200.dump

docker compose exec backend alembic upgrade head
docker compose start backend
```

---

## 7. Ambientes de Deploy e Pendências Pré-Produção Real

### 7.1 Diferenças entre Ambientes

| Aspecto | Desenvolvimento Local | Homologação / Staging | Produção |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | `staging` | `production` |
| `DEBUG` | `True` (opcional) | `False` | **`False` (obrigatório no código)** |
| `BACKEND_CORS_ORIGINS` | `localhost:8501`, `127.0.0.1:8501` | Domínio de homologação HTTPS | **Domínios HTTPS explícitos (proibido `*`)** |
| **PostgreSQL** | Local ou `postgres-local.yml` em `127.0.0.1` | Container/serviço gerenciado sem porta pública | **Rede privada / gerenciado, sem porta exposta, SSL e backup** |
| **Docs OpenAPI (`/docs`, `/redoc`)** | Abertos para facilitar testes | Opcional / VPN | **Recomendado restringir via reverse proxy ou configuração** |

### 7.2 O que o Repositório Já Garante vs O que Falta para Produção Exposta na Internet

**Já garantido pelo código e infraestrutura atual:**
- Validação rigorosa em `config.py` bloqueando inicialização em `production` com `DEBUG=True`, `CORS=*`, SQLite, `SECRET_KEY` fraca/placeholder ou senha padrão de banco.
- Imagens Docker rodando com usuário de sistema não-root (`vertice`), multi-etapa controlada com `migrate` antes de `backend`, healthchecks e PostgreSQL isolado da rede externa no `docker-compose.yml`.
- Hashing de senhas com Argon2id (`pwdlib`), tokens de serviço ML armazenados apenas em SHA-256 (`vtx_ml_*`), histórico imutável de previsões e auditoria persistente de consultas IA sem PII.

**Pendências operacionais de infraestrutura a provisionar antes de ir ao ar na internet pública:**
1. **Reverse Proxy com HTTPS / TLS:** posicionar Nginx, Traefik, Caddy ou Load Balancer na frente das portas `8000` (API) e `8501` (Streamlit) terminando TLS com certificados válidos.
2. **Gestão de Segredos:** substituir `.env` em texto plano no servidor por um Secret Manager gerenciado (AWS Secrets Manager, GCP Secret Manager, Vault, Docker Secrets) e habilitar rotação periódica de `SECRET_KEY` e credenciais ML.
3. **Proteção de `/docs`, `/redoc` e `/api/v1/openapi.json`:** por conveniência de desenvolvimento/validação em `backend/app/main.py`, essas rotas ficam habilitadas por padrão mesmo com `DEBUG=False`; bloqueie ou proteja esses caminhos no reverse proxy em produção (ou condicione sua exposição antes do go-live).
4. **Backups Automatizados Externos e Monitoramento:** agendar `pg_dump` criptografado para armazenamento externo ao host (S3/Blob) com testes periódicos de restore, além de centralização de logs e métricas/alertas (Prometheus/Grafana ou equivalente).
5. **Rate Limiting / WAF e Provedor LLM:** aplicar proteção contra força bruta em `/api/v1/auth/login` no gateway/proxy e, quando o assistente generativo for ativado em produção, implementar uma classe concreta derivada de `ProvedorLLMBase` com variáveis próprias fora do código.
