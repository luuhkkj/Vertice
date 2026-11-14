# Guia de Instalação, Execução e Cold Start — Projeto Vértice

Este guia orienta passo a passo como colocar o sistema **Vértice** em funcionamento **do zero**, mesmo em uma máquina que nunca teve o repositório, Python, PostgreSQL ou Docker configurados antes.

---

## 1. Requisitos de Hardware e Sistema Operacional

| Perfil | CPU | Memória RAM | Espaço Livre em Disco | Sistemas Suportados |
| :--- | :--- | :--- | :--- | :--- |
| **Mínimo (Execução/Testes)** | 2 núcleos (x64 ou ARM64) | 8 GB | 5 GB (imagens Docker, dependências e banco) | Windows 10/11 (64 bits), Linux (Ubuntu/Debian/Fedora), macOS |
| **Recomendado (Desenvolvimento + Containers)** | 4 núcleos ou mais | 16 GB | 10 GB+ | Windows 11 + WSL2, Linux nativo, macOS |

---

## 2. Programas Necessários (Separados por Modo de Execução)

Escolha o modo que melhor atende ao seu objetivo:

### Modo A — Execução via Docker Compose (**Recomendado**)
Ideal para subir **PostgreSQL + Migrações + Backend + Frontend** em poucos comandos com comportamento idêntico ao CI e sem instalar Python/PostgreSQL globalmente no host.

| Programa | Versão Mínima / Recomendada | Obrigatório? | Observação |
| :--- | :--- | :--- | :--- |
| **Git** | 2.30+ | Sim | Para clonar o repositório |
| **Docker Engine / Docker Desktop** | 24.0+ | Sim | No Windows, requer suporte ao **WSL2** habilitado |
| **Docker Compose** | v2 (`docker compose`) | Sim | Já incluído nas instalações modernas do Docker Desktop e plugin Docker Linux |

> No **Modo A**, Python `3.12` e PostgreSQL `16` rodam isoladamente dentro dos containers; você **não precisa** instalá-los no sistema operacional para executar a aplicação.

### Modo B — Execução Local Direta (Sem Docker / Desenvolvimento com Hot-Reload)
Indicado para desenvolvimento diário de backend, frontend ou depuração de testes diretamente na máquina.

| Programa | Versão Oficial | Obrigatório? | Observação |
| :--- | :--- | :--- | :--- |
| **Git** | 2.30+ | Sim | Controle de versão |
| **Python** | **3.12** (padrão oficial dos Dockerfiles e CI) | Sim | Deve incluir `venv` e `pip` |
| **PostgreSQL** | **16** | Sim (para rodar a API e testes `postgres`) | Testes unitários em SQLite rodam sem PostgreSQL |
| **Ferramentas Python** | `backend/requirements.txt`, `backend/requirements-dev.txt`, `Frontend vertice/requirements.txt` | Sim | Instaladas nos ambientes virtuais `.venv` |

---

## 3. Instalação dos Pré-requisitos por Sistema Operacional

### Windows (10/11)
1. **Git:** baixe em [git-scm.com](https://git-scm.com/download/win) e instale com as opções padrão.
2. **WSL2 + Docker Desktop (Modo A):**
   - Abra o **PowerShell como Administrador** e execute:
     ```powershell
     wsl --install
     ```
   - Reinicie o computador se solicitado.
   - Baixe e instale o [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) mantendo o backend **WSL2** selecionado.
   - Antes de usar comandos `docker compose`, certifique-se de que o aplicativo **Docker Desktop** esteja aberto e com o motor iniciado (ícone verde no canto inferior esquerdo).
3. **Python 3.12 e PostgreSQL 16 (somente Modo B):**
   - Baixe Python 3.12 em [python.org](https://www.python.org/downloads/) marcando **"Add python.exe to PATH"**.
   - Baixe PostgreSQL 16 em [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) (ou utilize um banco local via `docker compose -f docker-compose.yml -f docker-compose.postgres-local.yml up -d db`).

### Linux (Ubuntu / Debian)
1. **Git e Docker:**
   ```bash
   sudo apt update && sudo apt install -y git curl ca-certificates
   # Siga a documentação oficial da Docker para instalar docker-ce e docker-compose-plugin
   ```
   Após instalar a Docker, adicione seu usuário ao grupo `docker` e reinicie a sessão:
   ```bash
   sudo usermod -aG docker "$USER"
   ```
2. **Python 3.12 e PostgreSQL 16 (somente Modo B):** install `python3.12`, `python3.12-venv`, `python3-pip` e `postgresql-16` pelo gerenciador da sua distribuição.

### macOS
1. Instale **Xcode Command Line Tools** / **Git**: `xcode-select --install` (ou via Homebrew: `brew install git`).
2. **Modo A:** instale o **Docker Desktop for Mac** e inicie o aplicativo.
3. **Modo B:** via Homebrew: `brew install python@3.12 postgresql@16`.

### Verificação Rápida dos Programas Instalados

```bash
git --version
docker --version
docker compose version
# Apenas se for usar o Modo B (sem Docker):
python --version   # esperado 3.12.x (ou python3 --version)
```

---

## 4. Clonar o Repositório

```bash
git clone https://github.com/luuhkkj/Vertice.git
cd Vertice
```

---

## 5. Configuração de Variáveis de Ambiente e Geração de Segredos

O projeto **não possui** senhas padrão nem `SECRET_KEY` embutida no código. A aplicação valida rigorosamente as variáveis na inicialização (`backend/app/core/config.py`) e **recusa subir** caso encontre segredos fracos ou incompletos.

### 5.1 Arquivos de Exemplo Existentes
- **Raiz (`.env.example`):** utilizado pelo `docker compose` (`db`, `migrate`, `backend`, `frontend`).
- **`backend/.env.example`:** utilizado quando o backend roda localmente sem Docker.

### 5.2 Referência Completa de Variáveis

| Variável | Onde se aplica | Obrigatória | Padrão | Descrição e Regras de Validação (`app/core/config.py`) |
| :--- | :--- | :--- | :--- | :--- |
| `POSTGRES_USER` | Compose / Backend local | Sim (ou `DATABASE_URL`) | `vertice` (Compose) / vazio (local) | Usuário do banco PostgreSQL |
| `POSTGRES_PASSWORD` | Compose / Backend local | **Sim** | **Sem padrão** | Senha do PostgreSQL. Em `ENVIRONMENT=production`, senhas fracas (`postgres`, `admin`, `password`, `123456`, `root`) são recusadas |
| `POSTGRES_DB` | Compose / Backend local | Sim | `vertice` (Compose) / vazio (local) | Nome do banco PostgreSQL da aplicação |
| `POSTGRES_SERVER` | Backend | Sim (via Compose é `db`) | `localhost` (local) / `db` (Compose) | Hostname do servidor PostgreSQL |
| `POSTGRES_PORT` | Backend | Não | `5432` | Porta interna do PostgreSQL |
| `POSTGRES_EXTERNAL_PORT` | Override Docker local | Não | `5432` | Usada **apenas** com `docker-compose.postgres-local.yml` (vinculada a `127.0.0.1`) |
| `DATABASE_URL` | Backend local (opcional) | Não | Vazio | URI completa SQLAlchemy (`postgresql+psycopg://...`). Sobrescreve campos `POSTGRES_*`. Em produção, `sqlite` é proibido |
| `SECRET_KEY` | Compose / Backend | **Sim** | **Sem padrão** | Chave de assinatura JWT. Deve ter **>= 32 caracteres** e não pode conter termos placeholder (`change-this`, `changeme`, `default`, `secret`, `password`) |
| `ALGORITHM` | Compose / Backend | Não | `HS256` | Algoritmo de assinatura JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Compose / Backend | Não | `60` | Tempo de vida do token JWT em minutos |
| `PROJECT_NAME` | Compose / Backend | Não | `Vértice Backend API` | Título exibido no OpenAPI/Swagger |
| `VERSION` | Compose / Backend | Não | `0.2.1` | Versão da API |
| `ENVIRONMENT` | Compose / Backend | Não | `production` (Compose) / `development` (`.env.example` local) | Aceita `development`, `dev`, `test`, `testing`, `staging`, `production`, `prod` |
| `DEBUG` | Compose / Backend | Não | `False` | Em `production`, **deve ser `False`** (caso contrário o backend recusa iniciar) |
| `API_V1_STR` | Compose / Backend | Não | `/api/v1` | Prefixo base das rotas REST v1 |
| `BACKEND_PORT` | Compose | Não | `8000` | Porta publicada no host para a API FastAPI |
| `BACKEND_CORS_ORIGINS` | Compose / Backend | Sim em produção | `http://localhost:8501,http://127.0.0.1:8501` | Lista JSON ou separada por vírgula. Em `production`, não pode ficar vazia nem conter `*` |
| `FRONTEND_PORT` | Compose | Não | `8501` | Porta publicada no host para o Streamlit |
| `VERTICE_API_URL` | Frontend | Sim | `http://backend:8000/api/v1` (Compose) / `http://127.0.0.1:8000/api/v1` (local) | Endpoint base consumido por `Frontend vertice/data/api_client.py` |
| `ADMIN_NOME`, `ADMIN_EMAIL`, `ADMIN_SENHA` | CLI `create_admin` (opcional) | Não | Prompt interativo | Permitem criar o 1º administrador sem digitação interativa |

### 5.3 Como Gerar uma `SECRET_KEY` Segura

Gere um segredo exclusivo de pelo menos 32 caracteres (o comando abaixo gera ~64 caracteres):

- **Se tiver Python local instalado:**
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- **Se estiver usando somente Docker (sem Python no host):**
  ```bash
  docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- **Alternativa com OpenSSL (Linux/macOS/Git Bash):**
  ```bash
  openssl rand -base64 48
  ```

> **Nunca** copie valores genéricos ou mantenha `change-this` na `SECRET_KEY` nem coloque senhas reais sob versionamento Git (`.env` e `*.env.local` estão no `.gitignore`).

---

## 6. Subindo a Aplicação via Docker Compose (Passo a Passo)

### 6.1 Preparar o arquivo `.env` na raiz

**Linux / macOS / Git Bash:**
```bash
cp .env.example .env
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

Abra `.env` na raiz e preencha **obrigatoriamente**:
- `POSTGRES_PASSWORD=` (ex: senha forte gerada localmente; nunca `postgres`, `admin`, `123456`, etc. porque o Compose usa `ENVIRONMENT=production` por padrão)
- `SECRET_KEY=` (cole a saída gerada na seção 5.3)

### 6.2 Construir as imagens e iniciar os serviços

```bash
docker compose up --build -d
```

**O que acontece automaticamente em sequência controlada:**
1. **`db` (`postgres:16-alpine`)** sobe e aguarda o healthcheck `pg_isready`. Por segurança, **não publica a porta `5432` externamente** por padrão; a comunicação ocorre apenas pela rede interna Docker.
2. **`migrate`** executa `alembic upgrade head` uma única vez após o banco estar saudável e encerra com código `0`.
3. **`backend` (FastAPI + Uvicorn)** só inicia depois que `db` está saudável **e** `migrate` concluiu com sucesso (`service_completed_successfully`). Fica acessível em `http://localhost:8000`.
4. **`frontend` (Streamlit)** só inicia depois que `backend` responde `healthy` em `/health`, conectando-se internamente via `http://backend:8000/api/v1`. Fica acessível em `http://localhost:8501`.

### 6.3 Validar se tudo subiu corretamente

```bash
docker compose ps
```

Você deve ver `db`, `backend` e `frontend` com status **`healthy`** (e `migrate` concluído). Para acompanhar logs em tempo real:

```bash
docker compose logs -f backend frontend
```

Endpoints para conferência rápida no navegador ou terminal:
- **Frontend Streamlit:** `http://localhost:8501`
- **Health Check Backend:** `http://localhost:8000/health` (esperado JSON com `"status": "healthy"`)
- **Swagger UI:** `http://localhost:8000/docs`
- **OpenAPI JSON:** `http://localhost:8000/api/v1/openapi.json`

> **Precisa conectar DBeaver/pgAdmin/psql do seu computador ao banco Docker?**
> Suba explicitamente com o override opcional que expõe a porta apenas em `127.0.0.1` (nunca `0.0.0.0`):
> ```bash
> docker compose -f docker-compose.yml -f docker-compose.postgres-local.yml up -d
> ```

---

## 7. Criação do Primeiro Usuário Administrador

Por segurança, **não existe cadastro público de usuário ou administrador** pela interface web ou rota aberta da API. O primeiro acesso exige a execução do script CLI `backend/app/scripts/create_admin.py`.

### Via Docker Compose (Modo Interativo)

```bash
docker compose exec backend python -m app.scripts.create_admin
```

O terminal solicitará:
1. Nome do administrador (mínimo 2 caracteres)
2. E-mail válido
3. Senha (mínimo 6 caracteres, digitada de forma oculta via `getpass`) + confirmação

### Via Variáveis de Ambiente (Não Interativo — útil em scripts/automação)

```bash
docker compose exec -T \
  -e ADMIN_NOME="Administrador Rede" \
  -e ADMIN_EMAIL="admin@escola.edu.br" \
  -e ADMIN_SENHA="SuaSenhaForteAqui123" \
  backend python -m app.scripts.create_admin
```

### Erros Comuns no `create_admin`
- **`relation "usuarios" does not exist`:** o banco ainda não recebeu as migrações Alembic (`docker compose ps` para checar o container `migrate`, ou rode `alembic upgrade head` no modo local).
- **`Erro ao criar administrador: Conflito de integridade / e-mail já utilizado`:** já existe um usuário cadastrado com esse e-mail; utilize outro e-mail.
- **`Erro de validação nos dados informados`:** nome com menos de 2 caracteres, e-mail inválido ou senha menor que 6 caracteres.
- **No TTY / Windows Git Bash:** se o prompt interativo falhar por falta de TTY, use o modo com variáveis de ambiente (`ADMIN_NOME`, `ADMIN_EMAIL`, `ADMIN_SENHA`) ou execute em um terminal PowerShell / cmd padrão.

---

## 8. Bootstrap Funcional Completo (Primeira Execução de Ponta a Ponta)

Com o sistema no ar e o administrador criado, siga esta ordem exata para deixar a plataforma operante com dados reais:

1. **Autenticar como `administrador` e cadastrar a estrutura inicial (via Swagger UI `http://localhost:8000/docs`):**
   - Faça login em `POST /api/v1/auth/login` e clique em **Authorize** no Swagger UI colando o `access_token`.
   - Crie uma **Escola**: `POST /api/v1/escolas` (anote o `id` retornado).
   - Crie os usuários pedagógicos em `POST /api/v1/usuarios`:
     - Um usuário **`gestor`** informando `escola_id` da escola criada.
     - Um ou mais usuários **`professor`** (com `escola_id` definida ou `null` para professores multi-escola).
   - Crie **Turmas** (`POST /api/v1/turmas`, ex.: `nome="Turma 1A"`, `serie="1º Ano"`, `turno="Matutino"`, `ano_letivo=2026`, vinculada ao `escola_id`) e **Disciplinas** (`POST /api/v1/disciplinas`, ex.: `nome="Matemática"`, `codigo="MAT"`).
2. **Vincular Professores às Turmas/Disciplinas:**
   - Faça login no Streamlit (`http://localhost:8501`) como **`administrador`** ou **`gestor`**, abra **Atribuir turmas**, selecione o professor, a disciplina (ou *"Todas / Polivalente"* para regente unidocente) e a turma, e clique em **Atribuir turma** (ou use `POST /api/v1/atribuicoes` via API).
3. **Importar Estudantes Anonimizados e Dados Escolares (Etapa obrigatória):**
   - **Atenção:** o Vértice **não possui endpoint ou tela de cadastro manual individual de estudante**; todo estudante anonimizado (`codigo_anonimo`) entra pela importação validada de **Dados Escolares** (sem PII/nomes).
   - Entre no Streamlit (`http://localhost:8501`) como **`gestor`** ou **`professor`** (o papel `administrador` **não** possui acesso às telas pedagógicas nem a `/api/v1/importacoes/*`, por design de governança).
   - Abra **Entrada de Dados** (ou **Modelos de Planilha**), baixe o modelo oficial de **Dados Escolares (14 colunas)** em CSV ou XLSX, preencha com os códigos anônimos (`EST-2026-001`, etc.), nome exato da turma/disciplina e `ano_letivo` correspondente.
   - Em **Entrada de Dados**:
     - **Etapa 1:** faça upload do arquivo e clique em validar para inspecionar a prévia e verificar se não há erros estruturais, PII ou vínculo inválido.
     - **Etapa 2:** confirme a importação para gravar `estudantes`, `boletins_periodo` e `notas_disciplinas` em transação atômica.
4. **Explorar Avaliações, Participação e Indicadores Reais:**
   - Importe planilhas de **Avaliações (16 colunas)** para alimentar o **Mapa de Acertos**.
   - Crie atividades em **Participação** (ou importe planilhas de **Atividades — 12 colunas**), gere entregas esperadas para estudantes elegíveis no período e registre entregas/notas e acompanhamentos pedagógicos.
   - Consulte **Visão geral**, **Estudantes** e **Assistente IA** (lembrando que `POST /api/v1/assistente/contexto` prepara o contexto auditado com dados reais, enquanto `POST /api/v1/assistente/consultar` retorna `HTTP 503` até que um provedor LLM externo implemente `ProvedorLLMBase`).

---

## 9. Execução Local Direta (Sem Docker — Passo a Passo)

Use esta opção se desejar rodar o backend Uvicorn e o frontend Streamlit diretamente no sistema operacional conectado a um PostgreSQL 16 local.

### Passo 1 — Criar banco de dados no PostgreSQL 16 local

No `psql` (ou ferramenta cliente conectada como superusuário), crie um usuário dedicado e um banco para o projeto:

```sql
CREATE USER vertice_dev WITH PASSWORD 'DefinaUmaSenhaSeguraAqui';
CREATE DATABASE vertice_dev OWNER vertice_dev;
```

### Passo 2 — Configurar e iniciar o Backend FastAPI

#### Windows (PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edite `backend\.env` preenchendo `POSTGRES_SERVER=localhost`, `POSTGRES_PORT=5432`, `POSTGRES_USER=vertice_dev`, `POSTGRES_PASSWORD=...`, `POSTGRES_DB=vertice_dev` e uma `SECRET_KEY` gerada via `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Em seguida, ainda na pasta `backend\` com a `.venv` ativa:
```powershell
alembic upgrade head
python -m app.scripts.create_admin
uvicorn app.main:app --reload --port 8000
```

#### Linux / macOS (Bash)
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
```

Edite `backend/.env` com os dados do PostgreSQL e `SECRET_KEY` segura e execute:
```bash
alembic upgrade head
python -m app.scripts.create_admin
uvicorn app.main:app --reload --port 8000
```

### Passo 3 — Configurar e iniciar o Frontend Streamlit (Em outro terminal)

Recomenda-se um ambiente virtual próprio na raiz do repositório (`.venv`) para não misturar dependências do Streamlit com o backend:

#### Windows (PowerShell)
```powershell
# A partir da raiz Vertice\
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r "Frontend vertice\requirements.txt"

cd "Frontend vertice"
$env:VERTICE_API_URL = "http://127.0.0.1:8000/api/v1"
streamlit run app.py
```

#### Linux / macOS (Bash)
```bash
# A partir da raiz Vertice/
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r "Frontend vertice/requirements.txt"

cd "Frontend vertice"
export VERTICE_API_URL="http://127.0.0.1:8000/api/v1"
streamlit run app.py
```

Acesse `http://localhost:8501` no navegador.
