# Validação, Limitações Científicas e Anti-Data Leakage do Modelo ML — Vértice

## 1. Distinção Obrigatória: Integração Técnica vs. Validação Preditiva

O pipeline implementado entrega **infraestrutura operacional completa e segura** (extração controlada, validação de schema, inferência local, envio autenticado por `X-Service-Token`, persistência append-only e exibição no painel **Visão geral**).

Entretanto, **funcionamento técnico da integração não equivale a validação científica do modelo**. O modelo atualmente embarcado (`backend/artifacts/modelo_risco_academico_v1.joblib`, versão `poc-risco-academico-uci-v1`) é uma **prova de conceito (PoC)** e **não** deve ser usado isoladamente como fundamento para decisões pedagógicas automáticas sobre estudantes reais do Vértice.

---

## 2. Origem do Modelo e Rótulo Proxy

Conforme documentado em [treinar_modelo_risco.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/app/integrations/prediction/treinar_modelo_risco.py) e [RELATORIO_MODELO_RISCO.md](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/backend/docs/RELATORIO_MODELO_RISCO.md):

- **Base de origem**: conjunto público *UCI Student Performance* (`student-mat.csv` e `student-por.csv`).
- **Algoritmo selecionado**: `regressao_logistica` com imputação por mediana (`SimpleImputer`), padronização (`StandardScaler`), `class_weight="balanced"` e calibração sigmoide (`CalibratedClassifierCV`).
- **Rótulo proxy utilizado no treino**: a base pública original não contém histórico real de evasão escolar no contexto brasileiro. A PoC derivou um rótulo sintético `desfecho_desfavoravel_proxy` combinando regras sobre `absences`, `G3` e média final `(G1+G2+G3)/3`.
- **Implicação prática**: a probabilidade estimada reflete apenas a propensão ao rótulo proxy na base UCI e **não foi calibrada nem validada sobre dados longitudinais reais de evasão/reprovação das escolas do Vértice**.

---

## 3. Variáveis Utilizadas e Processo de Inferência

O corte temporal fixo adotado pelo modelo ocorre ao término do **1º período letivo** (`1º Bimestre` / `1º Trimestre` / `1º Semestre` / `1º Período`).

Variáveis de entrada aceitas no corte inicial:

| Variável no Contrato (`leakage.py`) | Campo no Modelo Local | Intervalo / Tipo Válido | Regra de Suficiência |
|---|---|---|---|
| `idade` | `idade` (alias `age`) | Inteiro em `[10, 100]` ou `None` | Opcional se `historico_reprovacoes` estiver presente |
| `historico_reprovacoes` | `historico_reprovacao` (aliases `historico_reprovacoes`, `failures`) | Inteiro em `[0, 50]` ou `None` | Opcional se `idade` estiver presente |
| `nota_t1` | `nota_t1` (alias `G1` em `[0, 20]` convertido por `/2`) | Decimal finito em `[0.0, 10.0]` | **Obrigatória** |

Classificação inicial nas faixas de acompanhamento (limiares em terços apenas para triagem exploratória):

- `pontuacao_risco < 0.333333` → **`BAIXO`** (`Estável`)
- `0.333333 <= pontuacao_risco < 0.666667` → **`MODERADO`** (`Atenção`)
- `pontuacao_risco >= 0.666667` → **`ALTO`** (`Prioritário`)

Tipo persistido na API: **`RISCO_ACADEMICO`** (nunca rotulado automaticamente como `EVASAO`).

Registros sem `nota_t1` ou sem nenhuma variável contextual (`idade` e `historico_reprovacoes` simultaneamente nulas) são **rejeitados na transformação** (ou classificados localmente como `SEM_PREVISAO_VALIDA` / `Dados insuficientes`), sem preenchimento artificial com zeros ou médias externas.

---

## 4. Prevenção de Data Leakage em Três Camadas

A proteção contra vazamento de dados futuros (*Data Leakage*) e exposição de PII atua em três pontos independentes:

1. **Na extração (`GET /api/v1/previsoes/exportacao-inferencia`)**:
   - Autenticada exclusivamente por `X-Service-Token` autorizado (`permite_leitura_inferencia=True`), restrita à escola vinculada à credencial.
   - Rejeita (`HTTP 422`) consultas para períodos pós-corte (`2º Bimestre`, `3º Bimestre`, `Final`, `Anual`, etc.).
   - Consulta somente os boletins do 1º corte e retorna estritamente `estudante_id`, `escola_id`, `turma_id`, `ano_letivo`, `periodo_letivo`, `idade`, `historico_reprovacoes` e `nota_t1` (além dos metadados da credencial/modelo).
2. **Na transformação (`transformador.py`) e inferência (`modelo_risco.py`)**:
   - Reutiliza `CAMPOS_PROIBIDOS_PREDICAO` de `leakage.py` e bloqueia explicitamente variáveis pós-corte ou fora do corte inicial do modelo:
     - `situacao_final`, `target`, `classe_real`
     - `nota_t2`, `g2`, `nota_t3`, `g3`
     - `media_geral`, `ausencias`, `absences`, `faltas`, `frequencia_percentual`
     - Atributos PII (`nome`, `nome_completo`, `cpf`, `rg`, `email`, `telefone`, `endereco`, etc.)
   - Qualquer campo desconhecido ou não catalogado também é recusado imediatamente.
3. **Na ingestão da API (`POST /api/v1/previsoes/lote`)**:
   - `PredictionService` executa novamente `validar_variaveis_contra_leakage()` e `validar_metadados_tecnicos()` antes de abrir escrita no banco.

---

## 5. Requisitos para Validação Científica Futura

Antes de promover qualquer modelo futuro de risco acadêmico ou evasão para apoio pedagógico contínuo no Vértice, será necessário:

1. Coletar coortes históricas longitudinais reais anonimizadas do próprio Vértice, com desfecho observado verdadeiro (`situacao_final`).
2. Realizar validação temporal (*out-of-time*), avaliando métricas de calibração (Brier score), área sob a curva PR/ROC, falsos negativos e equidade entre escolas/turmas/turnos.
3. Revisar os limiares (`baixo_max`, `moderado_max`, `alto_max`) em conjunto com gestores educacionais, registrando nova `modelo_versao` e nova `politica_classificacao_versao`.
