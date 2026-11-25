# Tutorial Completo — Executando o Vértice Sem Docker

Este tutorial orienta passo a passo como instalar os pré-requisitos, configurar variáveis de ambiente e colocar **todo o ecossistema do Vértice** em funcionamento diretamente no sistema operacional (**sem Docker**), contemplando:

- **PostgreSQL 16+** (banco de dados relacional)
- **Backend FastAPI + Alembic** (API REST, autenticação, migrações e auditoria)
- **Frontend Streamlit** (interface web por perfil RBAC)
- **Pipeline Automatizado de Machine Learning** (extração, inferência e persistência de previsões com token único)
- **Assistente de IA Local com Ollama** *(opcional)*

---

## 1. Requisitos do Sistema

### 1.1 Hardware
| Cenário | CPU | Memória RAM | Espaço Livre em Disco | Sistemas Suportados |
| :--- | :--- | :--- | :--- | :--- |
| **Mínimo (sem IA local)** | 2 núcleos (64 bits) | 8 GB | 5 GB | Windows 10/11, Linux (Ubuntu/Debian/Fedora), macOS |
| **Recomendado (com Assistente IA / Ollama)** | 4+ núcleos | 16 GB | 10 GB+ | Windows 10/11, Linux, macOS |

### 1.2 Softwares Obrigatórios
1. **Git (`2.30+`)**
   - Windows: https://git-scm.com/download/win
   - Linux (Ubuntu/Debian): `sudo apt update && sudo apt install -y git`
2. **Python (`3.12+`)** *(versão oficial de referência do projeto: `3.12`)*
   - Windows: https://www.python.org/downloads/ — **marque a opção `"Add python.exe to PATH"`** durante a instalação.
   - Linux (Ubuntu/Debian): `sudo apt install -y python3.12 python3.12-venv python3-pip`
   - macOS (Homebrew): `brew install python@3.12`
3. **PostgreSQL (`16+`)**
   - Windows: https://www.postgresql.org/download/windows/ (mantenha a porta padrão `5432` e anote a senha definida para o superusuário `postgres`).
   - Linux (Ubuntu/Debian): `sudo apt install -y postgresql-16`
   - macOS (Homebrew): `brew install postgresql@16`

### 1.3 Software Opcional (Apenas para o Assistente de IA)
- **Ollama** (gratuito e local): https://ollama.com/download
  - Se não desejar utilizar o Assistente de IA no momento, mantenha `ASSISTENTE_LLM_PROVEDOR=desativado` no `backend/.env` — todo o restante da plataforma funcionará normalmente.

### 1.4 Dependências Python (instaladas nos ambientes virtuais)
- **Backend** (`backend/requirements.txt` e `backend/requirements-dev.txt`): FastAPI, Uvicorn, SQLAlchemy 2, Alembic, `psycopg[binary]`, Pydantic v2, PyJWT, `pwdlib[argon2]`, Pandas, OpenPyXL, `python-docx`, `pypdf`, HTTPX, `joblib==1.6.0`, `scikit-learn==1.9.1`, Pytest e Ruff.
- **Frontend** (`Frontend vertice/requirements.txt`): Streamlit (`>=1.50`), HTTPX, Pandas, Plotly, NumPy e OpenPyXL.

### 1.5 Conferência rápida dos programas no terminal
```powershell
git --version
python --version
psql --version
```
*(No Windows, se `psql` não estiver no `PATH`, utilize o aplicativo **SQL Shell (psql)** ou o **pgAdmin 4** instalados junto com o PostgreSQL.)*

> **Permissão de scripts no Windows PowerShell:** caso apareça bloqueio ao ativar a `.venv` (`Activate.ps1`), execute uma única vez no PowerShell:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

## 2. Passo 1 — Clonar o Repositório

```powershell
git clone https://github.com/luuhkkj/Vertice.git
cd Vertice
```

---

## 3. Passo 2 — Criar o Usuário e o Banco no PostgreSQL

Certifique-se de que o serviço do PostgreSQL está ativo na porta `5432`. Conecte-se como superusuário (`postgres`) via **SQL Shell (psql)**, terminal ou **pgAdmin 4**:

```bash
psql -U postgres -h localhost -p 5432
```

No console SQL, crie o usuário e o banco de dados dedicados (substituindo pela senha desejada):

```sql
CREATE USER vertice_dev WITH PASSWORD 'DefinaUmaSenhaForteAqui';
CREATE DATABASE vertice_dev OWNER vertice_dev;
GRANT ALL PRIVILEGES ON DATABASE vertice_dev TO vertice_dev;
\q
```

---

## 4. Passo 3 — Configurar o Backend (Terminal 1)

Abra o **Terminal 1** na raiz do repositório (`Vertice/`) e configure o ambiente virtual do backend:

### Windows (PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

### Linux / macOS (Bash)
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
```

### Gerar uma `SECRET_KEY` segura
O Vértice recusa iniciar se `SECRET_KEY` estiver vazia, tiver menos de 32 caracteres ou usar termos inseguros (`secret`, `change-this`, `default`, `password`). Gere uma chave exclusiva com:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Preencher o arquivo `backend/.env`
Edite `backend/.env` com os dados do banco criado no Passo 2 e a `SECRET_KEY` gerada:

```env
PROJECT_NAME="Vértice Backend API"
VERSION="0.2.1"
ENVIRONMENT="development"
DEBUG=True
API_V1_STR="/api/v1"

BACKEND_CORS_ORIGINS=["http://localhost:8501","http://127.0.0.1:8501"]

POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=vertice_dev
POSTGRES_PASSWORD=DefinaUmaSenhaForteAqui
POSTGRES_DB=vertice_dev

SECRET_KEY=COLE_AQUI_O_VALOR_GERADO_ACIMA
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

ASSISTENTE_LLM_PROVEDOR=desativado
ASSISTENTE_OLLAMA_BASE_URL=http://127.0.0.1:11434
ASSISTENTE_OLLAMA_MODELO=qwen2.5:3b
ASSISTENTE_OLLAMA_TIMEOUT_SEGUNDOS=180
```

---

## 5. Passo 4 — Aplicar Migrações, Validar o Modelo ML e Criar o 1º Administrador

Ainda no **Terminal 1**, dentro de `backend/` com a `.venv` ativada (`(.venv)` visível no prompt):

1. **Executar as migrações Alembic para criar o schema completo no PostgreSQL:**
   ```powershell
   alembic upgrade head
   ```

2. **Conferir (ou gerar) o artefato local do modelo de Machine Learning:**
   ```powershell
   python -m app.integrations.prediction.pipeline --check-model
   ```
   - Se retornar `"status": "ok"`, o artefato `backend/artifacts/modelo_risco_academico_v1.joblib` já está disponível.
   - Se retornar `"status": "indisponivel"`, treine e gere o artefato executando:
     ```powershell
     python -m app.integrations.prediction.treinar_modelo_risco
     ```

3. **Criar o primeiro usuário Administrador:**
   *(Por segurança, não há auto-cadastro público na interface nem na API.)*
   ```powershell
   python -m app.scripts.create_admin
   ```
   Preencha quando solicitado:
   - **Nome** (mínimo 2 caracteres)
   - **E-mail** (ex.: `admin@vertice.edu.br`)
   - **Senha** (mínimo 6 caracteres) + confirmação

---

## 6. Passo 5 — Iniciar o Backend FastAPI (Terminal 1)

Ainda no **Terminal 1** (`backend/` com `.venv` ativa), inicie o servidor da API:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Deixe esse terminal em execução e valide no navegador:
- **Healthcheck:** `http://127.0.0.1:8000/health` *(esperado `"status": "healthy"`)*
- **Swagger UI:** `http://127.0.0.1:8000/docs`

---

## 7. Passo 6 — Configurar e Iniciar o Frontend Streamlit (Terminal 2)

Abra um **segundo terminal (Terminal 2)** na raiz do projeto (`Vertice/`) para criar um ambiente virtual dedicado ao frontend:

### Windows (PowerShell)
```powershell
# Na pasta raiz Vertice\
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r "Frontend vertice\requirements.txt"

cd "Frontend vertice"
$env:VERTICE_API_URL = "http://127.0.0.1:8000/api/v1"
streamlit run app.py
```

### Linux / macOS (Bash)
```bash
# Na pasta raiz Vertice/
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r "Frontend vertice/requirements.txt"

cd "Frontend vertice"
export VERTICE_API_URL="http://127.0.0.1:8000/api/v1"
streamlit run app.py
```

Deixe o **Terminal 2** em execução e acesse no navegador:
- **Interface Vértice:** `http://localhost:8501`

---

## 8. Passo 7 — Primeiro Uso e Importação de Dados (Governança de Perfis)

Por regra de governança RBAC, o **Administrador** gerencia apenas estrutura e contas técnicas, enquanto **Gestor** e **Professor** operam os dados pedagógicos:

1. **Cadastrar estrutura e contas técnicas (perfil `Administrador`):**
   - Faça login em `http://localhost:8501` com o administrador criado no Passo 4.
   - Em **Escolas, Turmas e Disciplinas**:
     1. Cadastre uma **Escola** ativa.
     2. Cadastre as **Turmas** vinculadas à escola (ex.: `ano_letivo = 2026`).
     3. Cadastre as **Disciplinas** (ex.: `Matemática` / `MAT`).
   - Em **Usuários e Contas**:
     - Crie um usuário **Gestor/Coordenador (`gestor`)** vinculado à escola criada.
     - Crie usuários **Professor (`professor`)**.

2. **Vincular turmas e importar estudantes/notas (perfil `Gestor`):**
   - Saia da conta de Administrador e autentique-se como **Gestor**.
   - Em **Atribuir turmas**, vincule os professores às turmas e disciplinas.
   - Em **Modelos de Planilha**, baixe a planilha modelo de **Dados Escolares** (CSV ou XLSX).
   - Preencha os registros com `codigo_anonimo` (sem nomes civis ou PII), usando o nome exato da turma/disciplina, ano letivo e período (`1º Bimestre`).
   - Em **Entrada de Dados**, valide o arquivo (Etapa 1) e confirme a importação (Etapa 2).

---

## 9. Passo 8 — Emitir Credencial e Executar o Pipeline de Machine Learning (Terminal 3)

Com os estudantes e notas do `1º Bimestre` importados para a escola:

1. **Emitir o token técnico manualmente na tela administrativa:**
   - Entre como **Administrador** em `http://localhost:8501` e abra **Credenciais ML**.
   - Preencha a identificação do serviço, selecione a **Escola** e selecione o **Modelo de Machine Learning** (`Risco Acadêmico — Regressão Logística (1º Período)`).
   - Clique em **Emitir token técnico** e **copie imediatamente o token `vtx_ml_...`** (ele é exibido uma única vez).

2. **Executar o pipeline em um Terminal 3 (na pasta `backend/` com `.venv` ativa):**

   ### Windows (PowerShell)
   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1

   $env:VERTICE_API_URL = "http://127.0.0.1:8000"
   $env:VERTICE_ML_SERVICE_TOKEN = "vtx_ml_COLE_SEU_TOKEN_AQUI"

   # 1) Validar conectividade, credencial, escola vinculada e modelo local:
   python -m app.integrations.prediction.pipeline.executor --check-config

   # 2) (Opcional) Testar extração e inferência sem gravar no banco:
   python -m app.integrations.prediction.pipeline.executor --dry-run --json

   # 3) Extrair dados, executar inferência e persistir previsões na API:
   python -m app.integrations.prediction.pipeline.executor --send --json
   ```

   ### Linux / macOS (Bash)
   ```bash
   cd backend
   source .venv/bin/activate

   export VERTICE_API_URL="http://127.0.0.1:8000"
   export VERTICE_ML_SERVICE_TOKEN="vtx_ml_COLE_SEU_TOKEN_AQUI"

   python -m app.integrations.prediction.pipeline.executor --check-config
   python -m app.integrations.prediction.pipeline.executor --send --json
   ```

3. **Visualizar os resultados na plataforma:**
   - Entre como **Gestor** ou **Professor** da escola correspondente e abra **Visão geral** para consultar os indicadores e gráficos de risco preenchidos.
   - *(Opcional)* Para manter o pipeline executando periodicamente em segundo plano no Terminal 3:
     ```powershell
     $env:VERTICE_ML_SCHEDULER_ENABLED = "true"
     $env:VERTICE_ML_SCHEDULER_INTERVAL_SECONDS = "3600"
     python -m app.integrations.prediction.pipeline.agendador
     ```

---

## 10. Passo 9 (Opcional) — Habilitar o Assistente de IA Local com Ollama

Para habilitar o chat do **Assistente IA** sem Docker:

1. Instale o **Ollama** nativo para seu sistema operacional: https://ollama.com/download
2. Em um terminal, baixe o modelo configurado por padrão:
   ```powershell
   ollama pull qwen2.5:3b
   ```
   *(O serviço local do Ollama responde em `http://127.0.0.1:11434`.)*
3. Edite `backend/.env` alterando:
   ```env
   ASSISTENTE_LLM_PROVEDOR=ollama
   ```
4. Reinicie o servidor `uvicorn` no **Terminal 1** (`Ctrl+C` e execute novamente o comando do Passo 5).
5. Acesse **Assistente IA** no menu lateral com um perfil **Gestor** ou **Professor**.

---

## 11. Passo 10 — Como Executar os Testes Automatizados Localmente

- **Suíte do Backend** (na pasta `backend/` com `.venv` ativa):
  ```powershell
  pytest -v
  ```
- **Suíte do Frontend** (na pasta `Frontend vertice/` usando a `.venv` da raiz):
  ```powershell
  ..\.venv\Scripts\python.exe -m unittest discover -s tests -v
  ```

---

## 12. Solução Rápida de Problemas Comuns (Sem Docker)

| Problema / Mensagem | Causa Provável | Solução |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'joblib'` (ou `'fastapi'`, `'streamlit'`) | Comando executado com o `python` global do sistema em vez da `.venv` | Ative a `.venv` da respectiva pasta (`.\.venv\Scripts\Activate.ps1` ou `source .venv/bin/activate`) antes de rodar o comando |
| Backend recusa iniciar citando `SECRET_KEY` | `SECRET_KEY` ausente, curta (< 32 caracteres) ou com padrão inseguro | Gere uma chave nova com `python -c "import secrets; print(secrets.token_urlsafe(48))"` e salve em `backend/.env` |
| Erro de conexão na porta `5432` ao rodar `alembic upgrade head` | Serviço do PostgreSQL parado ou usuário/senha/banco divergentes em `backend/.env` | Inicie o serviço PostgreSQL (`services.msc` no Windows ou `sudo systemctl start postgresql` no Linux) e confira `POSTGRES_*` |
| `relation "usuarios" does not exist` ao rodar `create_admin` | Migrações ainda não foram aplicadas | Execute `alembic upgrade head` na pasta `backend/` antes do `create_admin` |
| `Variável VERTICE_ML_SERVICE_TOKEN não configurada` no CLI do pipeline | O executor CLI lê as variáveis da sessão do terminal (`os.environ`) | Exporte `$env:VERTICE_ML_SERVICE_TOKEN = "vtx_ml_..."` no mesmo terminal antes de executar o comando |
| Credencial retorna `HTTP 403` na extração (`Somente envio`) | Token legado ou criado com escopo global (*"Todas as escolas"*) | Emita uma nova credencial em **Credenciais ML** selecionando uma **escola específica** e um **modelo** (`Permissão = Extração + Envio`) |
| Frontend exibe *"Não foi possível conectar ao servidor do Vértice"* | Backend parado no Terminal 1 ou `VERTICE_API_URL` não definida | Verifique se `uvicorn` está rodando em `127.0.0.1:8000` e defina `$env:VERTICE_API_URL = "http://127.0.0.1:8000/api/v1"` antes do `streamlit run app.py` |
