# Vértice - Backend API

Backend RESTful do sistema **Vértice** para gestão e análise de dados educacionais, acompanhamento pedagógico, indicadores de desempenho, modelos preditivos e assistente de IA.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.11+
- **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/)
- **Validação e Tipagem:** [Pydantic v2](https://docs.pydantic.dev/) e `pydantic-settings`
- **Banco de Dados & ORM:** PostgreSQL, [SQLAlchemy 2](https://docs.sqlalchemy.org/) e `psycopg 3`
- **Migrações:** [Alembic](https://alembic.sqlalchemy.org/)
- **Segurança & Tokens:** [PyJWT](https://pyjwt.readthedocs.io/) e [pwdlib](https://frankie567.github.io/pwdlib/) (Argon2)
- **Testes Automatizados:** [pytest](https://docs.pytest.org/) e [HTTPX](https://www.python-httpx.org/)

---

## 📂 Estrutura do Projeto

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Inicialização do FastAPI, CORS, handlers de erro e rotas raiz
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Configurações centralizadas via pydantic-settings
│   │   ├── security.py             # Hashing de senhas (Argon2) e assinatura/validação de JWT
│   │   └── dependencies.py         # Dependências de autenticação, RBAC e verificação de vínculo
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py                 # DeclarativeBase do SQLAlchemy 2
│   │   └── connection.py           # Engine, SessionLocal e dependência get_db com rollback seguro
│   ├── scripts/
│   │   ├── __init__.py
│   │   └── create_admin.py         # Script CLI seguro para criação do primeiro administrador
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py           # Roteador central /api/v1
│   ├── modules/                    # Módulos de domínio de negócio
│   │   ├── __init__.py
│   │   ├── auth/                   # Login JWT, /me, /logout e /refresh
│   │   ├── usuarios/               # Modelo Usuario, CRUD e controle de ativação/papel
│   │   ├── escolas/                # Modelo Escola e gestão de unidades escolares
│   │   ├── turmas/                 # Modelo Turma e filtragem por escopo do professor
│   │   ├── disciplinas/            # Modelo Disciplina e catálogo curricular
│   │   ├── atribuicoes/            # Modelo ProfessorTurma e vínculo professor-turma-disciplina
│   │   ├── estudantes/             # Reservado para próximas fases
│   │   ├── importacao/             # Reservado para próximas fases
│   │   ├── avaliacoes/             # Reservado para próximas fases
│   │   ├── participacao/           # Reservado para próximas fases
│   │   ├── indicadores/            # Reservado para próximas fases
│   │   └── acompanhamento/         # Reservado para próximas fases
│   └── integrations/               # Serviços externos e inteligência
│       ├── __init__.py
│       ├── prediction/             # Modelos de Machine Learning preditivos
│       └── assistant/              # Integração com assistente inteligente (LLMs)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Fixtures pytest com banco isolado em memória
│   ├── test_health.py              # Testes de inicialização, health check e utilitários de segurança
│   └── test_auth_and_models.py     # Testes de persistência, autenticação, RBAC e vínculos
├── alembic/
│   ├── versions/                   # Migrações versionadas do banco de dados
│   ├── env.py                      # Script de execução do Alembic conectado ao Base.metadata
│   ├── script.py.mako              # Template de migração
│   └── README
├── .env.example                    # Modelo de variáveis de ambiente
├── .gitignore                      # Regras de exclusão do Git
├── alembic.ini                     # Configuração base do Alembic
├── requirements.txt                # Dependências do projeto
└── README.md                       # Documentação do backend
```

---

## ⚙️ Configuração do Ambiente e PostgreSQL

### 1. Criar e Ativar o Ambiente Virtual

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configurar as Variáveis de Ambiente (`.env`)

Copie o arquivo `.env.example` para `.env`:

```powershell
Copy-Item .env.example .env
```

Edite o arquivo `backend/.env` com as credenciais do seu servidor PostgreSQL local (`localhost:5432`) e gere um segredo criptográfico exclusivo:

```powershell
# Gerar uma chave secreta aleatória criptograficamente segura (64+ caracteres)
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Exemplo de `backend/.env`:

```env
PROJECT_NAME="Vértice Backend API"
VERSION="0.2.0"
ENVIRONMENT="development"
DEBUG=True
API_V1_STR="/api/v1"

BACKEND_CORS_ORIGINS=["http://localhost:8501","http://127.0.0.1:8501","http://localhost:3000"]

POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=SUA_SENHA_DO_POSTGRES
POSTGRES_DB=postgres

SECRET_KEY=cole-aqui-a-chave-gerada-pelo-comando-secrets-token-urlsafe
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

> **Regras de Segurança de Inicialização (`app/core/config.py`):**
> - Não existem chaves `SECRET_KEY` ou senhas de banco padrão fixas no código.
> - `SECRET_KEY` deve possuir no mínimo **32 caracteres** e não pode usar valores de exemplo.
> - Em ambiente de produção (`ENVIRONMENT=production`), a aplicação recusa a inicialização caso `DEBUG=True`, caso `BACKEND_CORS_ORIGINS` contenha `"*"`, caso utilize banco em memória/SQLite ou caso a senha do PostgreSQL seja fraca/padrão.

---

## 🗄️ Execução das Migrações (Alembic)

Nenhuma tabela deve ser criada manualmente fora do fluxo de migrações. Com o PostgreSQL ativo e configurado no `.env`, execute a partir da pasta `backend/`:

```powershell
# Aplicar todas as migrações pendentes no banco de dados
alembic upgrade head

# Verificar revisão atual aplicada
alembic current

# Gerar nova migração após futuras alterações nos modelos ORM
alembic revision --autogenerate -m "descricao_da_alteracao"
```

---

## 👤 Criação do Administrador Inicial

Por segurança, **não existe endpoint público de auto-cadastro de administradores** e **não há credenciais padrão fixas no código**.

Para criar o primeiro usuário com papel `administrador`, execute o script CLI seguro a partir da pasta `backend/`:

### Opção A — Modo Interativo (Entrada Protegida)

```powershell
python -m app.scripts.create_admin
```

O script solicitará nome, e-mail e senha (com confirmação oculta no terminal via `getpass`).

### Opção B — Via Variáveis de Ambiente

```powershell
$env:ADMIN_NOME="Administrador Vértice"
$env:ADMIN_EMAIL="admin@vertice.edu.br"
$env:ADMIN_SENHA="SuaSenhaForteAqui"
python -m app.scripts.create_admin
```

---

## 🔐 Autenticação e Uso do Token JWT

### Endpoints de Autenticação

| Método | Rota | Descrição | Autenticação |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Autentica com `email` e `senha` e retorna `access_token` | Pública |
| `GET` | `/api/v1/auth/me` | Retorna os dados do usuário autenticado | Bearer JWT |
| `POST` | `/api/v1/auth/logout` | Orienta o descarte do token stateless pelo cliente | Bearer JWT |
| `POST` | `/api/v1/auth/refresh` | Reservado para futura estratégia de refresh token (HTTP 501) | — |

### 1. Como Obter o Token (`POST /api/v1/auth/login`)

Envie uma requisição `POST` para `/api/v1/auth/login`:

```json
{
  "email": "admin@vertice.edu.br",
  "senha": "SuaSenhaForteAqui"
}
```

Resposta (`200 OK`):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "usuario": {
    "id": "b17a541a-88eb-49f1-84c6-28d984c6514b",
    "nome": "Administrador Vértice",
    "email": "admin@vertice.edu.br",
    "papel": "administrador",
    "ativo": true
  }
}
```

### 2. Como Utilizar o Token nas Requisições

Inclua o cabeçalho HTTP `Authorization` em todas as chamadas protegidas:

```http
Authorization: Bearer <access_token>
```

No **Swagger UI** (`http://localhost:8000/docs`), clique no botão **Authorize** no topo direito, cole o valor de `access_token` e confirme.

---

## 🛡️ Papéis e Regras de Autorização (RBAC)

A validação de permissões ocorre integralmente no backend através das dependências em `app/core/dependencies.py`:

| Papel | Permissões no Sistema |
| :--- | :--- |
| **`administrador`** | Acesso administrativo total: cria e atualiza usuários (`POST /api/v1/usuarios`, `PATCH /api/v1/usuarios/{id}`), gerencia escolas, turmas, disciplinas e atribuições, e está autorizado por padrão para futuras importações de datasets escolares (`PAPEIS_AUTORIZADOS_IMPORTACAO`). |
| **`gestor`** | Acesso de gestão pedagógica: consulta usuários, cadastra e atualiza escolas, turmas, disciplinas e atribuições de professores. Se o gestor possuir `escola_id` vinculado no seu cadastro, seu acesso de leitura e escrita fica restrito exclusivamente àquela unidade escolar (`garantir_acesso_escola`). |
| **`professor`** | Acesso restrito ao seu escopo pedagógico: visualiza apenas as turmas e atribuições às quais está vinculado na tabela `professor_turmas`. Tentativas de acessar turmas sem vínculo retornam `HTTP 403 Forbidden`. |

> **Nota Arquitetural sobre `gestor` vs `coordenador`:** A documentação inicial do projeto cita o perfil `COORDENADOR` (responsável pela importação de datasets em CSV/XLSX), enquanto a especificação da Fase 2 definiu os papéis `administrador`, `gestor` e `professor`. Não foi assumida equivalência implícita entre `gestor` e `coordenador`. A dependência `require_importacao_datasets` (`PAPEIS_AUTORIZADOS_IMPORTACAO`) encontra-se isolada em `app/core/dependencies.py`, aguardando decisão formal do responsável pelo projeto antes da Fase 3.

---

## 🚀 Iniciando o Servidor e Executando os Testes

### Iniciar o Servidor

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Executar a Suíte de Testes Automatizados

Os testes utilizam banco SQLite em memória isolado por função de teste, não exigindo PostgreSQL ativo para execução da suíte unitária:

```powershell
cd backend
pytest -v
```
