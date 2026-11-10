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
│   │   ├── estudantes/             # Modelos Estudante, BoletimPeriodo, NotaDisciplina e consultas isoladas
│   │   ├── importacao/             # Motor de validação CSV/XLSX (dados escolares, avaliações, atividades) e lotes
│   │   ├── avaliacoes/             # Bloco B: Avaliacao, QuestaoAvaliacao, RespostaAvaliacao e Mapa de Acertos
│   │   ├── participacao/           # Bloco C: Atividade, EntregaAtividade e geração de entregas esperadas
│   │   ├── indicadores/            # Serviços de Indicadores Gerais, Avaliações e Participação
│   │   └── acompanhamento/         # AcompanhamentoPedagogico individual/coletivo com trilha de auditoria
│   └── integrations/               # Serviços externos e inteligência
│       ├── __init__.py
│       ├── prediction/             # Modelos de Machine Learning preditivos
│       └── assistant/              # Integração com assistente inteligente (LLMs)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Fixtures pytest com banco isolado em memória
│   ├── test_health.py              # Testes de inicialização, health check e utilitários de segurança
│   ├── test_auth_and_models.py     # Testes de persistência, autenticação, RBAC e vínculos
│   ├── test_fase3_estudantes_e_importacao.py # Testes de importação em 2 etapas, autorização, LGPD e histórico
│   └── test_fase4_modulos_pedagogicos.py     # Testes de avaliações, participação, acompanhamento e indicadores
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
| **`administrador`** | Acesso administrativo de infraestrutura: cria e atualiza usuários (`POST /api/v1/usuarios`, `PATCH /api/v1/usuarios/{id}`) e gerencia cadastros estruturais (escolas, turmas, disciplinas e atribuições). **Não** possui permissão automática para importar datasets escolares. |
| **`gestor`** | Representa a coordenação escolar: consulta usuários, gerencia turmas/atribuições de sua escola e realiza importação e consulta de datasets escolares exclusivamente para as turmas pertencentes à escola à qual está vinculado (`usuario.escola_id`). Gestores sem escola vinculada têm a importação bloqueada (`HTTP 403`). |
| **`professor`** | Acesso restrito ao seu escopo pedagógico: importa datasets e consulta estudantes/históricos **exclusivamente** para as combinações de turma e disciplina às quais está vinculado em `professor_turmas`. Tentativas de importar ou acessar turmas/disciplinas sem vínculo retornam erro de autorização. |

---

## 📥 Módulo de Estudantes e Importação Automatizada de Datasets (Fase 3)

### 1. Objetivo e Fluxo em Duas Etapas

A entrada de dados de estudantes e históricos escolares ocorre por meio de importação automatizada em **duas etapas** (`CSV` ou `XLSX`, até **10 MB**):

1. **Etapa 1 — Upload, Validação e Prévia (`POST /api/v1/importacoes/validar`)**:
   - Identifica automaticamente o usuário responsável a partir do token JWT da sessão autenticada (nunca confia em colunas `professor_id` ou `escola_id` do CSV).
   - Verifica extensão (`.csv` ou `.xlsx`), tamanho máximo (`10 MB`), colunas obrigatórias, regras de anonimização (LGPD/RN01), tipos de dados, duplicidades e autorização por linha contra `ProfessorTurma` (para professores) ou `usuario.escola_id` (para gestores).
   - Registra o lote na tabela `lotes_importacao` (`status="validado"` ou `status="com_erros"`) e retorna o relatório detalhado e a prévia dos registros. **Nenhum dado acadêmico definitivo é persistido nesta etapa.**
2. **Etapa 2 — Confirmação e Persistência Atômica (`POST /api/v1/importacoes/{lote_id}/confirmar`)**:
   - Revalida a identidade, as permissões e os vínculos ativos (`ProfessorTurma` / escola do gestor) no momento exato da confirmação.
   - Grava `Estudante`, `BoletimPeriodo` e `NotaDisciplina` em uma **transação atômica única** (`commit` integral ou `rollback` completo em caso de falha).
   - Preserva o histórico longitudinal: períodos anteriores nunca são sobrescritos por novos períodos, importações repetidas atualizam registros de forma idempotente sem duplicar e uma `situacao_final` consolidada (`Aprovado`, `Reprovado`, `Evadido`) nunca é substituída por `NULL`.

### 2. Regras de Privacidade e Anonimização (LGPD / RN01) e Suas Limitações

- O Vértice trabalha **exclusivamente com estudantes anonimizados** (`codigo_anonimo`, ex: `EST-2026-001`).
- **Inspeção de Cabeçalhos:** O validador bloqueia colunas pessoais proibidas tanto por correspondência exata normalizada quanto por inspeção de tokens compostos (independentemente de acentuação, caixa alta/baixa ou separadores `_`, `-` e espaços), incluindo variações como `nome`, `nome_aluno`, `nome_estudante`, `nome_completo`, `aluno_nome`, `estudante_nome`, `cpf_do_aluno`, `rg`, `endereco`, `telefone_responsavel`, `email_estudante`, `data_nascimento`, `filiacao`, entre outras.
- **Inspeção de Valores por Linha:** Todas as células da planilha são inspecionadas contra padrões explícitos de CPF (formatado `000.000.000-00` ou sequência de 11 dígitos), endereços de e-mail e números de telefone. Adicionalmente, a coluna `codigo_anonimo` exige um identificador alfanumérico estruturado (contendo ao menos um dígito ou separador técnico) e rejeita cadeias puramente alfabéticas (como nomes ou prenomes isolados) ou nomes compostos.
- **Não Exposição de Dados Sensíveis:** Quando um padrão de dado pessoal é detectado, o relatório aponta a linha e a coluna afetadas sem jamais reproduzir ou registrar em log o conteúdo sensível rejeitado.
- **Limitações Conhecidas da Detecção Heurística:** As verificações baseadas em expressões regulares e heurísticas léxicas bloqueiam os padrões estruturados mais comuns de identificação civil e contato, mas não substituem a governança na origem dos dados — textos livres não estruturados ou códigos maliciosamente codificados fora dos padrões conhecidos ainda dependem da preparação prévia de planilhas anonimizadas pela unidade escolar.

### 3. Escopo de Autorização do Professor, Multi-Escola, `disciplina_id = NULL` e Revalidação na Confirmação

1. **Escopo de Autorização do Professor (`ProfessorTurma`):**
   - A identidade e o perfil do usuário são extraídos exclusivamente do token JWT autenticado (colunas de autoria no CSV são proibidas).
   - O professor somente pode importar dados e consultar estudantes/boletins de turmas ativas (`Turma.ativo = True`), pertencentes a escolas ativas (`Escola.ativo = True`), nas quais possua vínculo registrado em `professor_turmas`.
   - Caso o cadastro do professor possua `usuario.escola_id` preenchido, seu escopo é adicionalmente restrito às turmas daquela escola específica.
2. **Tratamento de Professores com Vínculos em Múltiplas Escolas:**
   - Quando um professor possui `usuario.escola_id = NULL` e leciona em turmas vinculadas a mais de uma escola ativa, o sistema **não** escolhe arbitrariamente a primeira escola.
   - A escola do lote (`LoteImportacao.escola_id`) é determinada de forma unívoca a partir das turmas autorizadas referenciadas no arquivo CSV/XLSX.
   - Cada lote de importação deve corresponder a **uma única escola**: caso um mesmo arquivo misture turmas de escolas diferentes, o validador registra erro de `autorizacao` (*conflito de escopo escolar no lote*) e bloqueia a confirmação (`pode_confirmar = false`). Caso nenhuma turma válida permita identificar a escola do lote, a requisição é rejeitada com `HTTP 400`.
3. **Semântica de `ProfessorTurma.disciplina_id = NULL` vs. Disciplina Específica:**
   - **`disciplina_id = UUID` (vínculo por disciplina):** Representa a atribuição padrão do professor a uma disciplina específica naquela turma (ex: Matemática na Turma 1A). Tanto na importação quanto nas consultas (`GET /api/v1/estudantes` e `GET /api/v1/estudantes/{id}`), mesmo quando o parâmetro `disciplina_id` não é enviado na URL, o professor visualiza **exclusivamente** os estudantes e boletins que possuem registro em `notas_disciplinas` para as disciplinas ativas às quais está vinculado, com paginação (`skip`/`limit`) e contagem (`X-Total-Count`) calculadas estritamente sobre esse conjunto filtrado.
   - **`disciplina_id = NULL` (vínculo geral na turma):** Representa uma atribuição pedagógica geral à turma (ex: professor regente/conselheiro de turma). Autoriza a importação de boletins gerais da turma (sem exigir coluna de disciplina) e a visualização de todos os estudantes e boletins ativos daquela turma.
4. **Revalidação Integral na Confirmação (`POST /api/v1/importacoes/{lote_id}/confirmar`):**
   - Antes de abrir a transação de escrita da Etapa 2, o serviço `_revalidar_autorizacao_na_confirmacao` verifica novamente no banco de dados se: (a) o usuário segue ativo e com papel autorizado; (b) a escola do lote (`lote.escola_id`) segue existente e ativa; (c) cada turma referenciada no lote segue existente, ativa (`Turma.ativo = True`) e vinculada à mesma `lote.escola_id` (e `usuario.escola_id`, se aplicável); (d) para professores, o vínculo `ProfessorTurma` exato para `(turma_id, disciplina_id)` continua existindo; e (e) cada disciplina referenciada segue existente e ativa (`Disciplina.ativo = True`). Qualquer revogação ou desativação ocorrida entre a prévia e a confirmação aborta a operação com `HTTP 403` sem gravar nenhum registro.

### 4. Formato Esperado do CSV / XLSX

#### Colunas Obrigatórias
- `codigo_anonimo` (aliases aceitos: `id_estudante`, `identificador`, `identificador_anonimo`): código alfanumérico anônimo do estudante (2 a 50 caracteres, ex: `EST-001`).
- `turma` (aliases: `nome_turma`, `codigo_turma`, `id_turma`): nome ou UUID da turma cadastrada.
- `ano_letivo` (alias: `ano`): ano letivo inteiro (deve coincidir com o `ano_letivo` da turma).
- `periodo_letivo` (aliases: `periodo`, `bimestre`, `etapa`): identificação do período (ex: `1º Bimestre`, `2º Bimestre`, `Anual`).

#### Colunas Opcionais
- `disciplina` (aliases: `codigo_disciplina`, `nome_disciplina`): código ou nome da disciplina (ex: `MAT` ou `Matemática`). Se omitida por um professor que leciona apenas uma disciplina naquela turma, o sistema infere a disciplina automaticamente de forma segura; se o professor lecionar múltiplas disciplinas na turma, o sistema exige a coluna explícita.
- `frequencia_percentual` (aliases: `frequencia`, `presenca`): número de `0` a `100` (aceita ponto ou vírgula). Ausência permanece `NULL` (não é convertida em zero).
- `faltas` (alias: `quantidade_faltas`): inteiro `>= 0`.
- `nota` (alias: `nota_disciplina`): nota na disciplina de `0` a `10`.
- `nota_prova` (alias: `prova`): nota de avaliação/prova de `0` a `10`.
- `nota_trabalho` (alias: `trabalho`): nota de trabalho/atividade de `0` a `10`.
- `media_geral` (alias: `media`): média consolidada no período de `0` a `10`.
- `historico_reprovacoes` (alias: `historico_reprovacao`): inteiro `>= 0` (acumulado de reprovações anteriores).
- `participacao_recuperacao` (aliases: `recuperacao`, `em_recuperacao`): booleano (`Sim`/`Não`, `True`/`False`, `1`/`0`).
- `situacao_final` (alias: `situacao`): `Aprovado`, `Reprovado`, `Evadido` ou vazio (`NULL` quando o período ainda está em andamento).

#### Exemplo de CSV Fictício Anonimizado

```csv
codigo_anonimo,turma,disciplina,ano_letivo,periodo_letivo,frequencia_percentual,faltas,nota,nota_prova,nota_trabalho,historico_reprovacoes,participacao_recuperacao,situacao_final
EST-2026-001,Turma 1A,MAT,2026,1º Bimestre,95.0,2,8.5,8.0,9.0,0,Nao,
EST-2026-002,Turma 1A,MAT,2026,1º Bimestre,78.5,8,5.5,5.0,6.0,1,Sim,
EST-2026-003,Turma 2A,MAT,2026,1º Bimestre,92.0,3,9.0,9.5,8.5,0,Nao,Aprovado
```

### 5. Endpoints de Importação e Estudantes

| Método | Rota | Descrição | Perfis Autorizados |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/importacoes/validar` | Upload (`multipart/form-data`, campo `arquivo`), validação de escopo/LGPD e geração de prévia | `gestor`, `professor` |
| `GET` | `/api/v1/importacoes/{lote_id}` | Consulta o status e resumo de auditoria do lote | `gestor`, `professor` (escopo próprio) |
| `GET` | `/api/v1/importacoes/{lote_id}/previa` | Retorna o relatório completo de validação e a prévia dos registros | `gestor`, `professor` (escopo próprio) |
| `POST` | `/api/v1/importacoes/{lote_id}/confirmar` | Revalida vínculos e confirma a persistência em transação atômica | `gestor`, `professor` (autor/escopo) |
| `POST` | `/api/v1/importacoes/{lote_id}/descartar` | Descarta um lote ainda não confirmado | `gestor`, `professor` (autor/escopo) |
| `GET` | `/api/v1/estudantes` | Lista estudantes anonimizados filtrados pelo escopo do usuário (retorna total filtrado no header `X-Total-Count`) | `gestor`, `professor` |
| `GET` | `/api/v1/estudantes/{estudante_id}` | Retorna estudante e seu histórico longitudinal de boletins e disciplinas | `gestor`, `professor` |

#### Exemplo de Resposta de Validação (`POST /api/v1/importacoes/validar` — `201 Created`)

```json
{
  "id": "e4d909c2-90d0-4fb1-9ef6-3f1d8c22a1b3",
  "usuario_id": "a12b34c5-d6e7-4f89-8012-3456789abcde",
  "escola_id": "f98e76d5-c4b3-4a21-9087-654321fedcba",
  "nome_arquivo": "notas_1bim_mat.csv",
  "tipo_importacao": "DADOS_ESCOLARES",
  "hash_arquivo": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "status": "validado",
  "total_linhas": 2,
  "registros_validos": 2,
  "quantidade_erros": 0,
  "quantidade_avisos": 0,
  "registros_novos": 2,
  "registros_existentes": 0,
  "registros_inseridos": 0,
  "registros_atualizados": 0,
  "pode_confirmar": true,
  "relatorio_validacao": {
    "total_linhas": 2,
    "registros_validos": 2,
    "quantidade_erros": 0,
    "quantidade_avisos": 0,
    "registros_novos": 2,
    "registros_existentes": 0,
    "turmas_identificadas": ["Turma 1A"],
    "disciplinas_identificadas": ["Matemática (MAT)"],
    "colunas_ausentes": [],
    "colunas_proibidas_pii": [],
    "problemas_autorizacao": [],
    "valores_invalidos": [],
    "duplicidades": [],
    "problemas_anonimizacao": [],
    "erros": [],
    "avisos": []
  },
  "previa_registros": [
    {
      "linha": 2,
      "codigo_anonimo": "EST-2026-001",
      "turma_nome": "Turma 1A",
      "disciplina_codigo": "MAT",
      "ano_letivo": 2026,
      "periodo_letivo": "1º Bimestre",
      "frequencia_percentual": 95.0,
      "nota_disciplina": 8.5,
      "operacao_prevista": "insercao"
    }
  ]
}
```

---

## 📊 Módulos Pedagógicos e Analíticos da Fase 4

### 1. Avaliações, Questões e Mapa de Acertos (Bloco B)
- **Modelos (`app/modules/avaliacoes/models.py`):** `Avaliacao`, `QuestaoAvaliacao` (`FECHADA`, `ABERTA`; `FaixaDificuldadeQuestao`: `Fácil`, `Adequada`, `Atenção`, `Difícil`) e `RespostaAvaliacao`.
- **Regras de Negócio:**
  - Questões `FECHADAS` exigem gabarito (`A`, `B`, `C`, `D` ou `E`); questões `ABERTAS` não possuem gabarito de alternativa e são corrigidas por nota atribuída (`0 <= nota_obtida <= valor_questao`, com acerto quando `nota_obtida >= 60%` do valor da questão).
  - Respostas deixadas em branco são representadas explicitamente (`em_branco=True` e `alternativa_marcada="BRANCO"` em questões fechadas), permitindo distinguir omissões de erros no Mapa de Acertos.
  - Unicidade garantida em banco por `(questao_id, estudante_id)`. Estudantes nunca são criados via avaliações.
- **Endpoints:**
  - `POST /api/v1/avaliacoes`, `GET /api/v1/avaliacoes`, `GET /api/v1/avaliacoes/{avaliacao_id}`, `PATCH /api/v1/avaliacoes/{avaliacao_id}`
  - `POST /api/v1/avaliacoes/{avaliacao_id}/questoes`, `GET /api/v1/avaliacoes/{avaliacao_id}/questoes`, `PATCH /api/v1/questoes/{questao_id}`
  - `GET /api/v1/avaliacoes/{avaliacao_id}/respostas`, `POST /api/v1/questoes/{questao_id}/respostas`

### 2. Participação, Atividades e Entregas Esperadas (Bloco C)
- **Modelos (`app/modules/participacao/models.py`):** `Atividade` e `EntregaAtividade` (`StatusEntregaAtividade`: `ENTREGUE`, `ATRASADO`, `PENDENTE`, `NAO_ENTREGUE`).
- **Geração Idempotente de Entregas Esperadas (`POST /api/v1/atividades/{atividade_id}/gerar-entregas-esperadas`):**
  - Identifica todos os estudantes ativos já vinculados à turma da atividade nos dados escolares (`BoletimPeriodo`) e cria os registros de entrega esperados sem duplicar entregas existentes e sem jamais criar estudantes novos.
  - Notas ausentes permanecem `None` (`NULL`), nunca sendo convertidas em `0`.
  - Calcula/valida automaticamente o status: `ENTREGUE` (`data_entrega <= data_limite`), `ATRASADO` (`data_entrega > data_limite`), `PENDENTE` (sem entrega antes do prazo) e `NAO_ENTREGUE` (sem entrega após o vencimento do prazo).
- **Endpoints:**
  - `POST /api/v1/atividades`, `GET /api/v1/atividades`, `GET /api/v1/atividades/{atividade_id}`, `PATCH /api/v1/atividades/{atividade_id}`
  - `POST /api/v1/atividades/{atividade_id}/gerar-entregas-esperadas`
  - `GET /api/v1/atividades/{atividade_id}/entregas`, `POST /api/v1/atividades/{atividade_id}/entregas`, `PATCH /api/v1/entregas/{entrega_id}`

### 3. Acompanhamento Pedagógico (`app/modules/acompanhamento/`)
- **Modelo (`AcompanhamentoPedagogico`):** suporta ações pedagógicas individuais (`estudante_id`) ou coletivas (`turma_id`), exigindo ao menos um deles (`ck_acompanhamento_estudante_ou_turma_obrigatorio`), com origem classificada em `ESTUDANTES`, `MAPA_ACERTOS` ou `PARTICIPACAO`.
- **Autoria e Trilha de Auditoria:** o autor (`usuario_id`) é extraído exclusivamente da sessão JWT autenticada. Atualizações via `PATCH /api/v1/acompanhamentos/{acompanhamento_id}` preservam o snapshot completo anterior em `historico_alteracoes` sem apagar descrições ou ações passadas.
- **Endpoints:** `POST /api/v1/acompanhamentos`, `GET /api/v1/acompanhamentos`, `GET /api/v1/acompanhamentos/{acompanhamento_id}`, `PATCH /api/v1/acompanhamentos/{acompanhamento_id}`.

### 4. Indicadores Educacionais (`app/modules/indicadores/`)
- **Serviços Especializados:**
  - `GET /api/v1/indicadores/gerais` (`IndicadoresGeraisService`): total de estudantes distintos (sem duplicar estudantes com múltiplos períodos/disciplinas), frequência média, média geral, distribuições por série/turma/turno e evolução longitudinal com comparação contra o período anterior.
  - `GET /api/v1/indicadores/avaliacoes` (`IndicadoresAvaliacoesService`): Mapa de Acertos completo por questão e tópico, taxa de acerto, distribuição de alternativas (`A`-`E` e `BRANCO`), classificação da faixa de desempenho observada da turma (`Fácil >= 75%`, `Adequada 50%-74.99%`, `Atenção 30%-49.99%`, `Difícil < 30%`) e média ponderada na escala 0-10.
  - `GET /api/v1/indicadores/participacao` (`IndicadoresParticipacaoService`): entregas esperadas, realizadas, no prazo, atrasadas, não entregues após o prazo, pendentes antes do prazo, taxas por atividade/turma, percentual individual por estudante e evolução temporal.

### 5. Extensão da Importação em Duas Etapas (`AVALIACOES` e `ATIVIDADES`)
- O endpoint `POST /api/v1/importacoes/validar` suporta e detecta automaticamente três tipos de lote (`TipoImportacao`): `DADOS_ESCOLARES`, `AVALIACOES` e `ATIVIDADES` (também selecionável via query param `tipo_importacao`).
- Nas importações de `AVALIACOES` e `ATIVIDADES`, estudantes inexistentes ou fora da turma são rejeitados na validação — nunca são criados estudantes novos fora da importação de `DADOS_ESCOLARES`.

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
