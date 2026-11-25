# Execução e Operação do Pipeline ML — Vértice

Todos os comandos abaixo partem do diretório `backend/` com o ambiente virtual ativado (`.venv`).

---

## 1. Instalação de Dependências

```bash
pip install -r requirements.txt
```

Para rodar testes e ferramentas de desenvolvimento:

```bash
pip install -r requirements-dev.txt
```

---

## 2. Configuração Mínima Necessária

Basta configurar a URL da API e o token técnico único emitido manualmente pelo Administrador na tela **Credenciais ML**:

```env
VERTICE_API_URL=http://127.0.0.1:8000
VERTICE_ML_SERVICE_TOKEN=vtx_ml_SEU_TOKEN
```

Escola e modelo não precisam ser repetidos no `.env`: o pipeline os identifica automaticamente a partir da própria credencial.

### Variáveis operacionais opcionais

| Variável | Padrão | Descrição |
|---|---|---|
| `VERTICE_API_URL` | `http://127.0.0.1:8000` | URL base da API do Vértice. |
| `VERTICE_ML_TURMA_ID` | `None` | Filtra opcionalmente uma turma específica. |
| `VERTICE_ML_DISCIPLINA_ID` | `None` | Filtra opcionalmente uma disciplina específica. |
| `VERTICE_ML_ANO_LETIVO` | `None` | Filtra opcionalmente um ano letivo (ex.: `2026`). |
| `VERTICE_ML_PERIODO_LETIVO` | `1º Bimestre` | Período do corte inicial (`1º Bimestre`, `1º Trimestre`, `1º Semestre`, `1º Período`, `T1`). |
| `VERTICE_ML_BATCH_SIZE` | `500` | Tamanho máximo de cada sublote enviado (`1..2000`). |
| `VERTICE_ML_EXPORT_PAGE_SIZE` | `200` | Tamanho da página na extração (`1..1000`). |
| `VERTICE_ML_HTTP_TIMEOUT` | `30.0` | Timeout HTTP em segundos. |
| `VERTICE_ML_SCHEDULER_ENABLED` | `false` | Ativa (`true`) ou desativa (`false`) o loop do agendador. |
| `VERTICE_ML_SCHEDULER_INTERVAL_SECONDS` | `3600` | Intervalo em segundos entre execuções do agendador. |
| `VERTICE_ML_LOCK_FILE` | `<tempdir>/vertice_ml_pipeline.lock` | Arquivo de lock contra execuções simultâneas. |

---

## 3. Comandos CLI Disponíveis

### Verificar configuração e metadados da credencial

Valida URL, presença do token, escola e modelo vinculados na API e disponibilidade local do artefato `.joblib` correspondente (sem exibir o segredo):

```bash
python -m app.integrations.prediction.pipeline.executor --check-config
```

### Verificar modelos disponíveis no catálogo

```bash
python -m app.integrations.prediction.pipeline.executor --check-model
```

### Executar inferência sem envio (`--dry-run`)

Consulta a API usando o token configurado, descobre escola e modelo automaticamente e roda a inferência sem persistir previsões:

```bash
python -m app.integrations.prediction.pipeline.executor --dry-run --json
```

### Executar fluxo completo e enviar previsões (`--send`)

```bash
python -m app.integrations.prediction.pipeline.executor --send --json
```

### Agendador periódico

```bash
python -m app.integrations.prediction.pipeline.agendador --once --json
python -m app.integrations.prediction.pipeline.agendador
```

---

## 4. Testes Automatizados

```bash
pytest tests/test_pipeline_ml.py -v
pytest tests/test_modelo_risco.py tests/test_fase7_predicao_e_ia.py tests/test_api_docs_parity.py -v
```
