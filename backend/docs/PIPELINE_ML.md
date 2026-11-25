# Pipeline Automatizado de Machine Learning — Vértice

## 1. Objetivo do Pipeline

O pipeline automatizado de Machine Learning conecta os dados escolares do primeiro período armazenados no **Vértice** ao modelo local disponível no catálogo central (`catalogo_modelos.py` / `modelo_risco.py`) e envia as previsões versionadas à API com uma **única credencial técnica (`X-Service-Token`)**, permitindo que os indicadores e gráficos do painel **Visão geral** sejam atualizados de maneira simples, segura e desacoplada da interface gráfica.

---

## 2. Arquitetura Geral e Fluxo com Credencial Única

```text
Administrador (UI Credenciais ML)
     │  Seleciona escola + modelo disponível e emite token manualmente
     ▼
X-Service-Token (`vtx_ml_...`)  [permite_leitura_inferencia=True, escola_id, modelo_autorizado]
     │
     ├──(1)──▶ GET /api/v1/previsoes/exportacao-inferencia
     │            └─ retorna escola_id, modelo_nome/versao e atributos do 1º corte (sem PII)
     ▼
ExtratorDadosInferencia (`extrator.py`)
     │
     ▼
Catálogo Central (`catalogo_modelos.py`) + Transformador (`transformador.py`)
     │            └─ resolve artefato do modelo autorizado e bloqueia Data Leakage / PII
     ▼
Inferência Local (`modelo_risco.py` + `executor.py`)
     │
     ├──(--dry-run para aqui; --send segue)──▶ POST /api/v1/previsoes/lote (mesmo X-Service-Token)
     │                                             └─ valida escola, modelo, versão e idempotência
     ▼
PostgreSQL (`previsoes_risco`) ──▶ GET /api/v1/indicadores/gerais ──▶ Painel Visão Geral
```

---

## 3. Responsabilidade de Cada Módulo

- [catalogo_modelos.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/app/integrations/prediction/catalogo_modelos.py): registro central leve que descobre dinamicamente modelos com implementação e artefato `.joblib` compatíveis para exibição na tela administrativa e carregamento exato pelo pipeline.
- [pipeline/config.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/app/integrations/prediction/pipeline/config.py): lê `VERTICE_API_URL` (padrão `http://127.0.0.1:8000`) e `VERTICE_ML_SERVICE_TOKEN` (além de opcionais como agendamento e lote), sem depender de `SECRET_KEY` ou `DATABASE_URL` e mascarando segredos em logs.
- [pipeline/extrator.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/app/integrations/prediction/pipeline/extrator.py): consulta `GET /api/v1/previsoes/exportacao-inferencia` usando `X-Service-Token`, obtendo os registros paginados e descobrindo automaticamente `escola_id`, `modelo_nome`, `modelo_versao` e `tipo_previsao` da credencial.
- [pipeline/transformador.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/app/integrations/prediction/pipeline/transformador.py): valida tipos, intervalos, suficiência mínima e bloqueia Data Leakage / PII sem inventar valores ausentes.
- [pipeline/executor.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/app/integrations/prediction/pipeline/executor.py): resolve o artefato do modelo autorizado (interrompendo se ausente/incompatível sem substituir por outro modelo), chama `prever_risco()`, valida as saídas e orquestra `--check-config`, `--check-model`, `--dry-run` e `--send`.
- [pipeline/cliente_api.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/app/integrations/prediction/pipeline/cliente_api.py): envia sublotes atômicos (máximo 2000 itens) para `POST /api/v1/previsoes/lote` usando o mesmo `X-Service-Token`, sem retentativas cegas que gerem `409 Conflict`.
- [pipeline/agendador.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/app/integrations/prediction/pipeline/agendador.py): executa ciclos programados ou pontuais (`--once`) protegidos por `BloqueioExecucaoSimultanea`.

---

## 4. Segurança e Compatibilidade Retroativa

- **Escopo estrito de menor privilégio**: o token autorizado na nova interface só lê os atributos mínimos do 1º período (`estudante_id`, `escola_id`, `turma_id`, `ano_letivo`, `periodo_letivo`, `idade`, `historico_reprovacoes`, `nota_t1`) da própria escola vinculada e só grava previsões para aquela escola e aquele modelo.
- **Compatibilidade**: credenciais antigas gravadas com `permite_leitura_inferencia = false` mantêm exatamente suas permissões somente de envio (nunca têm leitura ampliada silenciosamente) e recebem `HTTP 403` ao consultar `GET /api/v1/previsoes/exportacao-inferencia`.
- **Revogação imediata**: revogar a credencial (`ativo = false`) bloqueia instantaneamente extração e envio com `HTTP 403`.
- **Painel Visão Geral**: continua consumindo exclusivamente `GET /api/v1/indicadores/gerais` e `GET /api/v1/previsoes`, preservando todos os filtros e a mensagem de ausência de previsões nos recortes sem dados.
