# Vértice - Backend API

Fundação da API RESTful do sistema Vértice para gestão e análise de dados educacionais, acompanhamento pedagógico, indicadores de desempenho, modelos preditivos e assistente de IA.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.11+ (Recomendado: Python 3.12)
- **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/)
- **Validação e Tipagem:** [Pydantic v2](https://docs.pydantic.dev/) e `pydantic-settings`
- **Banco de Dados & ORM:** PostgreSQL, [SQLAlchemy 2](https://docs.sqlalchemy.org/) e `psycopg 3`
- **Migrações:** [Alembic](https://alembic.sqlalchemy.org/)
- **Segurança & Tokens:** [PyJWT](https://pyjwt.readthedocs.io/) e [pwdlib](https://frankie567.github.io/pwdlib/) (com suporte nativo a Argon2)
- **Testes Automatizados:** [pytest](https://docs.pytest.org/) e [HTTPX](https://www.python-httpx.org/)

---

## 📂 Estrutura do Projeto

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # Inicialização do FastAPI, CORS, middlewares e rotas raiz
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Configurações centralizadas via pydantic-settings
│   │   └── security.py             # Funções de hashing de senhas e geração/validação de JWT
│   ├── database/
│   │   ├── __init__.py
│   │   ├── base.py                 # DeclarativeBase do SQLAlchemy 2
│   │   └── connection.py           # Engine, SessionLocal e dependência get_db
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── router.py           # Roteador central /api/v1
│   ├── modules/                    # Módulos de domínio de negócio
│   │   ├── __init__.py
│   │   ├── auth/                   # Autenticação e tokens
│   │   ├── usuarios/               # Gestão de usuários e permissões
│   │   ├── estudantes/             # Cadastro e dados de estudantes
│   │   ├── turmas/                 # Turmas e enturmações
│   │   ├── importacao/             # Upload e processamento de planilhas
│   │   ├── avaliacoes/             # Provas, gabaritos e notas
│   │   ├── participacao/           # Frequência e taxas de engajamento
│   │   ├── indicadores/            # Agregações estatísticas e KPIs
│   │   └── acompanhamento/         # Planos de intervenção pedagógica
│   └── integrations/               # Serviços externos e inteligência
│       ├── __init__.py
│       ├── prediction/             # Modelos de Machine Learning preditivos
│       └── assistant/              # Integração com assistente inteligente (LLMs)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Fixtures pytest e TestClient
│   └── test_health.py              # Testes de inicialização, health check e segurança
├── alembic/
│   ├── versions/                   # Histórico de revisões de migrações
│   ├── env.py                      # Script de execução do Alembic
│   ├── script.py.mako              # Template de migração
│   └── README
├── .env.example                    # Modelo de variáveis de ambiente
├── .env                            # Arquivo de variáveis local
├── .gitignore                      # Regras de exclusão do Git
├── alembic.ini                     # Configuração base do Alembic
├── requirements.txt                # Dependências fixadas do projeto
└── README.md                       # Documentação do backend
```

---

## 🚀 Como Executar o Projeto Localmente

### 1. Pré-requisitos

- Python 3.11 ou superior instalado na máquina.
- PostgreSQL (opcional para testes básicos de inicialização).

### 2. Criar e Ativar o Ambiente Virtual

Acesse a pasta do backend:

```bash
cd backend
```

Crie o ambiente virtual:

- **Linux / macOS:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- **Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```

- **Windows (Prompt de Comando):**
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate.bat
  ```

### 3. Instalar as Dependências

Com o ambiente virtual ativo:

```bash
pip install -r requirements.txt
```

### 4. Configurar as Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env`:

- **Linux / macOS:**
  ```bash
  cp .env.example .env
  ```

- **Windows:**
  ```powershell
  Copy-Item .env.example .env
  ```

Ajuste as configurações no `.env` conforme seu ambiente de banco de dados e chave secreta (`SECRET_KEY`).

### 5. Iniciar o Servidor de Desenvolvimento

Execute o servidor Uvicorn a partir do diretório `backend`:

```bash
uvicorn app.main:app --reload --port 8000
```

O servidor iniciará em: [http://localhost:8000](http://localhost:8000)

---

## 📖 Documentação Interativa da API (Swagger & Redoc)

Com o servidor em execução, acesse pelo navegador:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Esquema OpenAPI JSON:** [http://localhost:8000/api/v1/openapi.json](http://localhost:8000/api/v1/openapi.json)

---

## 🧪 Executando os Testes Automatizados

Os testes automatizados verificam o funcionamento da API sem depender de um banco PostgreSQL em execução:

A partir da pasta `backend`:

```bash
pytest -v
```

Ou a partir da raiz do repositório:

```bash
pytest backend/tests -v
```

---

## 🗄️ Migrações de Banco de Dados com Alembic

Para gerar uma nova migração com base nos modelos ORM:

```bash
alembic revision --autogenerate -m "descricao_da_migracao"
```

Para aplicar as migrações no banco configurado:

```bash
alembic upgrade head
```

---

## 🔜 Próximas Etapas de Desenvolvimento

1. **Mapeamento de Entidades ORM e Migração Inicial:**
   - Modelos de Usuários (`Usuario`), Estudantes (`Estudante`), Turmas (`Turma`), Avaliações (`Avaliacao`, `Questao`, `Nota`).
2. **Autenticação e Autorização:**
   - Endpoint de login `/api/v1/auth/token` gerando JWT.
   - Dependência `get_current_user` com verificação de papéis (RBAC).
3. **Módulo de Importação:**
   - Ingestão de planilhas de notas e presenças (`.xlsx`, `.csv`).
4. **Módulo de Indicadores & Estatísticas:**
   - Agregações para abastecer os gráficos do frontend Streamlit.
5. **Integrações Inteligentes:**
   - Modelos preditivos de risco e assistente pedagógico com IA.

