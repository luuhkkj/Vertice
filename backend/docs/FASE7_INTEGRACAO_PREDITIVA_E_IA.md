# Fase 7 — Integração com Modelo Preditivo e Assistente IA

Este documento descreve a arquitetura implementada na **Fase 7** do projeto Vértice. Esta fase estabelece contratos, persistência, segurança, prevenção de *data leakage*, auditoria e preparação de contexto. O assistente generativo usa Ollama local e não envia dados pedagógicos a provedores externos.

---

## 1. Arquitetura Geral da Camada

```text
Pipeline ML Externo ──(X-Service-Token: vtx_ml_...)──▶ /api/v1/previsoes (/lote)
                                                               │
                                               [Anti-Leakage + Validação + Append-Only]
                                                               │
                                                               ▼
                                                    PostgreSQL: previsoes_risco
                                                               │
Gestor / Professor (JWT) ──▶ /api/v1/indicadores/gerais ◀──────┤
                         ──▶ /api/v1/previsoes/*        ◀──────┤
                         ──▶ /api/v1/assistente/contexto ◀─────┴──▶ Serviços Reais Vértice
                                      │
                                      ▼
                        PostgreSQL: auditoria_consultas_ia
                                      │
                                      ▼
                     ProvedorLLMBase -> Ollama local (/api/chat)
```

---

## 2. Módulo Preditivo (`backend/app/integrations/prediction/`)

### 2.1 Credenciais Técnicas de Serviço (`CredencialIntegracaoPredicao`)
- Tokens JWT comuns de `professor`, `gestor` ou `administrador` **não autorizam** a extração nem o envio de previsões pelo pipeline (`HTTP 403 Forbidden`).
- Apenas administradores consultam modelos elegíveis (`GET /api/v1/previsoes/modelos-disponiveis`), emitem (`POST /api/v1/previsoes/credenciais`), listam (`GET /api/v1/previsoes/credenciais`) e revogam (`PATCH /api/v1/previsoes/credenciais/{id}/revogar`) credenciais técnicas dedicadas.
- O segredo bruto (`vtx_ml_*`) é exibido **uma única vez** na criação; apenas prefixo e hash SHA-256 são gravados no banco.
- Quando emitida com escola específica e modelo autorizado (`permite_leitura_inferencia=True`), a mesma credencial autoriza a exportação controlada do 1º período (`GET /api/v1/previsoes/exportacao-inferencia`) e o envio de previsões (`POST /api/v1/previsoes/lote`) exclusivamente para essa escola e esse modelo; credenciais legadas (`permite_leitura_inferencia=False`) permanecem restritas ao envio.

### 2.2 Persistência Append-Only e Idempotência (`PrevisaoRisco`)
- Cada previsão persistida armazena: `estudante_id`, `escola_id`, `turma_id` (opcional), `ano_letivo`, `periodo_letivo`, `tipo_previsao` (`EVASAO`, `REPROVACAO`, `RISCO_ACADEMICO`), `pontuacao_risco` (`0.0 <= x <= 1.0`), `faixa_risco` (`BAIXO`, `MODERADO`, `ALTO`, `CRITICO`), `politica_classificacao_versao`, `modelo_nome`, `modelo_versao`, `gerado_em`, `recebido_em`, `lote_externo_id`, `assinatura_idempotencia` e `metadados_tecnicos`.
- Novas execuções nunca sobrescrevem registros passados.
- Reenvios idênticos são bloqueados com `HTTP 409 Conflict` via índice único em `assinatura_idempotencia`.
- `POST /api/v1/previsoes/lote` processa o lote de forma **atômica**: qualquer falha de validação, leakage, escopo ou duplicidade aborta todo o lote antes do commit.

### 2.3 Contrato Estrito de Variáveis e Prevenção de Data Leakage (`leakage.py`)
- Definido formalmente em `backend/app/integrations/prediction/leakage.py` e exposto em:
  - `GET /api/v1/previsoes/contrato-variaveis`
  - `POST /api/v1/previsoes/validar-variaveis`
- **Política padrão de negação para desconhecidas (`exige_contrato_para_desconhecidas = True`):** qualquer variável não catalogada e sem contrato completo em `VariavelPreditivaContrato` (`nome`, `origem`, `tipo`, `descricao`, `disponibilidade_temporal`, `sensibilidade`, `elegivel_predicao`) é **rejeitada automaticamente** (`HTTP 422` na ingestão / `variaveis_desconhecidas_rejeitadas` na validação prévia).
- **Normalização Unicode e inspeção recursiva:** todas as chaves e caminhos aninhados passam por normalização Unicode (`NFKD`, remoção de acentos, caixa, espaços, hífens e prefixos) antes da conferência contra proibições e catálogo.
- **Variáveis elegíveis (`CATALOGO_VARIAVEIS_PREDITIVAS`):** `frequencia_percentual`, `faltas`, `media_geral`, `nota_t1`, `notas_baixas`, `historico_reprovacoes`, `participacao_recuperacao`, `atrasos`, `idade`, `taxa_entrega_atividades`, `entregas_atrasadas`, `nao_entregas_apos_prazo`, `taxa_acerto_avaliacoes`, `respostas_em_branco`. Uma variável só é válida se seu valor estiver disponível até o corte escolhido; indicadores anuais não podem substituir valores parciais.
- **Variável-alvo supervisionada reservada (`CONTRATO_ALVO_SUPERVISIONADO_SITUACAO_FINAL`):** `situacao_final` é mantida exclusivamente como referência documental de desfecho (`disponibilidade_temporal = pos_desfecho`, `elegivel_predicao = False`, `uso_exclusivo_alvo_supervisionado = True`) para futura etapa de treinamento supervisionado, sendo bloqueada como entrada preditiva.
- **Variáveis bloqueadas (`CAMPOS_PROIBIDOS_PREDICAO` -> `HTTP 422`):**
  - `situacao_final` e variantes pós-desfecho (`evadiu`, `reprovou`, `aprovado`, `desfecho`, `target`, `label`, `data_evasao`, `status_final`, `conclusao_periodo`, etc.).
  - Para o corte fixo após o primeiro período, `nota_t2`/`G2` e `nota_t3`/`G3` são posteriores e bloqueadas.
  - Atributos de identificação pessoal direta (LGPD): `nome`, `nome_completo`, `cpf`, `rg`, `email`, `telefone`, `endereco`, `aluno_nome`, etc.
- Extensões de regras são suportadas via `campos_proibidos_extras` e `catalogo_extensao` (aceitas apenas mediante contrato completo com `elegivel_predicao=True`, disponibilidade anterior à data de corte e ausência de PII).

### 2.4 Contrato Fechado de Metadados Técnicos (`metadados_tecnicos`)
- `metadados_tecnicos` aceita exclusivamente chaves do catálogo operacional fechado (`CATALOGO_METADADOS_TECNICOS_PERMITIDOS`): `pipeline_execucao_id`, `framework_ml`, `origem_pipeline`, `data_corte_extracao`, `janela_corte_dias`, `limiar_decisao`, `calibracao_aplicada`, `tempo_inferencia_ms`, `hash_artefato_modelo` e `politica_limiares` (`baixo_max`, `moderado_max`, `alto_max`, `critico_min` em `[0.0, 1.0]`).
- É proibido enviar campos desconhecidos, PII, variáveis de entrada/pós-desfecho, texto livre pedagógico ou segredos/tokens (`Bearer`, JWTs, `api_key`, `vtx_ml_*`), sendo tudo validado recursivamente com rejeição `HTTP 422`.
- Todas as respostas da API passam por `sanitizar_metadados_tecnicos_resposta`, removendo chaves não contratuais caso existam registros legados no banco.

### 2.5 Treinamento local e função `prever_risco`
- O protótipo local compara `DummyClassifier` (baseline), Regressão Logística e Random Forest, com imputação dentro de `Pipeline`, divisões estratificadas por grupos, métricas por classe, matriz de confusão, falsos positivos/negativos e Brier score.
- Para reproduzir, a partir de `backend/`: `python -m app.integrations.prediction.treinar_modelo_risco`. O comando baixa os CSVs públicos UCI em memória, salva `artifacts/modelo_risco_academico_v1.joblib` e gera `docs/RELATORIO_MODELO_RISCO.md`.
- A função `from app.integrations.prediction import prever_risco` recebe uma lista de dicionários ou `DataFrame` com `id_estudante` (ou `id_aluno`), `idade`, `historico_reprovacao` e `nota_t1`. Também aceita os aliases `age`, `failures` e `G1` bruto (0–20).
- Para usar o DataFrame completo do notebook, selecione explicitamente apenas as colunas anteriores ao corte: `previsoes = prever_risco(df[["id_aluno", "idade", "historico_reprovacao", "nota_t1"]])`. A função rejeita colunas pós-corte e o alvo caso sejam incluídos.
- A função retorna `id_estudante`, `pontuacao_risco`, `faixa_risco`, `status_acompanhamento`, `versao_modelo` e `data_processamento`. A pontuação é calibrada apenas para o rótulo proxy usado neste experimento.
- `situacao_final`, `G2`/`nota_t2`, `G3`/`nota_t3`, média anual, faltas e frequência anual são rejeitados como entradas por serem alvo ou dados posteriores ao corte. Sem nota do primeiro período e pelo menos uma das variáveis de contexto, retorna `SEM_PREVISAO_VALIDA` / `Dados insuficientes`.
- Faixas iniciais: score `< 0,333` → Baixo/Estável; `0,333–<0,667` → Moderado/Atenção; `>=0,667` → Alto/Prioritário. A divisão em terços é uma proposta de triagem, não limiar de decisão validado. A função não persiste previsões nem as envia automaticamente à API.

### 2.6 Validade dos dados e uso operacional
- O notebook concatena Matemática e Português, atribui IDs sequenciais e cria `situacao_final` a partir de frequência anual, nota do terceiro período e média final; não há histórico confirmado de evasão. O classificador aprende a reproduzir esse rótulo derivado, não um desfecho real independente.
- O particionamento agrupa fingerprints de atributos estáveis para reduzir a sobreposição de estudantes entre matérias. Como o dataset não fornece um identificador longitudinal confiável, esse agrupamento não garante ausência total de registros relacionados entre as partições.
- O artefato e o relatório são **prova de conceito**. Não devem gerar alertas operacionais nem decisões sobre estudantes do Vértice. Uso real depende de rótulos históricos observados, chave longitudinal, avaliação temporal externa e validação por educadores.

---

## 3. Política de Versão Única e Integração com `IndicadoresGeraisService`

- `IndicadoresGeraisService.calcular_indicadores_gerais` consulta `PredictionService.obter_resumo_previsoes` dentro do mesmo escopo autorizado (escola/turma/disciplina/ano/período).
- Quando **não há previsões** para o recorte: `possui_previsoes_risco = False`, `distribuicao_faixas_risco = []`.
- Quando **há previsões**:
  - Se `modelo_versao` (e opcionalmente `modelo_nome`) for informado, filtra exclusivamente aquela versão.
  - Caso contrário, seleciona automaticamente a versão mais recente ativa no escopo (`modelo_nome_vigente`, `modelo_versao_vigente`).
  - Contabiliza **uma única vez cada estudante** pela sua última previsão (`gerado_em` mais recente) dentro dessa versão, garantindo que contagens/percentuais nunca somem versões distintas nem dupliquem o mesmo estudante.

---

## 4. Camada de Preparação do Assistente IA (`backend/app/integrations/assistant/`)

### 4.1 Níveis de Contexto Suportados
Via `POST /api/v1/assistente/contexto`:
1. `ESCOLA`: indicadores gerais, avaliações, participação, resumo de risco e acompanhamentos recentes autorizados.
2. `TURMA` (exige `turma_id`): indicadores e distribuições filtrados para a turma autorizada.
3. `INDIVIDUAL` (exige `estudante_id`): histórico escolar anonimizado (`codigo_anonimo`), indicadores de participação individuais, histórico append-only de previsões e acompanhamentos.

Todos os cálculos reutilizam exclusivamente os serviços existentes do Vértice, mantendo separação explícita entre **dados observados** e **estimativas preditivas**.

### 4.2 Segurança, RBAC e Auditoria (`AuditoriaConsultaIA`)
- **Administrador:** bloqueado com `HTTP 403` em consultas/contextos pedagógicos; pode auditar metadados em `/assistente/auditoria`.
- **Gestor:** acesso restrito à própria escola (`escola_id`).
- **Professor:** acesso restrito às turmas e disciplinas em que possui vínculo real em `ProfessorTurma`.
- **Trilha persistente e rastreabilidade (`AuditoriaConsultaIA`):**
  - Cada execução gera um `request_id` único no **backend** (sem possibilidade de sobrescrita pelo cliente) e aceita opcionalmente `conversation_id` para agrupar turnos relacionados, retornando ambos em `MetadadosContextoAssistente` e em `GET /api/v1/assistente/auditoria` (com filtros por `request_id` e `conversation_id`).
  - Todas as tentativas são gravadas com `resultado_autorizacao` (`AUTORIZADO`, `NEGADO` ou `ERRO_EXECUCAO`), `motivo_decisao`, IDs estruturais, `filtros_utilizados`, `resumo_fontes_consultadas` e `criado_em`, sem armazenar PII, tokens ou texto livre de conversa.
  - Em falhas inesperadas durante a montagem do contexto, a transação principal sofre *rollback* e uma nova sessão isolada registra `ERRO_EXECUCAO` antes de retornar `HTTP 500`, evitando falso registro de `AUTORIZADO`.

### 4.3 Provedor LLM local
- `ProvedorLLMBase` define o contrato de integração; `ProvedorLLMOllama` usa `POST /api/chat` em um host local confiável.
- A configuração é feita por `ASSISTENTE_LLM_PROVEDOR=ollama`, `ASSISTENTE_OLLAMA_BASE_URL`, `ASSISTENTE_OLLAMA_MODELO` e `ASSISTENTE_OLLAMA_TIMEOUT_SEGUNDOS`. Sem provedor/modelo, o status informa que o assistente está desabilitado e a consulta retorna `HTTP 503`.
- A configuração padrão sugerida é o modelo gratuito `qwen2.5:3b`. Baixe-o uma vez com `ollama pull qwen2.5:3b` (execução nativa) ou `docker compose exec ollama ollama pull qwen2.5:3b` (Docker).
- No Compose, defina `ASSISTENTE_LLM_PROVEDOR=ollama` no `.env` antes de iniciar os serviços, use `ASSISTENTE_OLLAMA_BASE_URL=http://ollama:11434` e execute `docker compose --profile assistente-local up -d --build` para incluir as alterações mais recentes da aplicação.
- Cada consulta remonta o contexto autorizado no backend. UUIDs internos são removidos do prompt; para contexto individual o modelo recebe o código anonimizado, indicadores e registros autorizados. O histórico recente fica apenas na sessão do frontend e não é persistido como conversa.
- O prompt exige respostas baseadas nos dados disponíveis, explicitação de lacunas, separação entre observações e previsões e revisão humana. As respostas incluem fontes consultadas e aviso de que previsões não são certezas.
- O endpoint `POST /api/v1/assistente/consultar-arquivos` aceita até cinco anexos PDF, DOCX, TXT, CSV ou XLSX (5 MB por arquivo e 10 MB no total). O backend extrai texto em memória, limita o conteúdo enviado ao modelo e não persiste os anexos nem seu texto na auditoria. Documentos digitalizados sem camada de texto não têm OCR; não anexe dados pessoais identificáveis.

---

## 5. Pipeline Automatizado e Limitações Conhecidas (Pós-Fase 7)

1. O fluxo automatizado desacoplado reside em `backend/app/integrations/prediction/pipeline/` (`config.py`, `extrator.py`, `transformador.py`, `executor.py`, `cliente_api.py` e `agendador.py`), utilizando uma única credencial `X-Service-Token` (`VERTICE_ML_SERVICE_TOKEN`) que identifica automaticamente escola e modelo em `GET /api/v1/previsoes/exportacao-inferencia` e envia previsões `RISCO_ACADEMICO` para `POST /api/v1/previsoes/lote`.
2. A emissão de credenciais `vtx_ml_*` permanece **estritamente manual** pelo perfil `administrador`, e o protótipo `poc-risco-academico-uci-v1` segue sem validação científica para estudantes reais do Vértice. Consulte [PIPELINE_ML.md](PIPELINE_ML.md), [CONFIGURACAO_CREDENCIAIS_ML.md](CONFIGURACAO_CREDENCIAIS_ML.md), [EXECUCAO_PIPELINE_ML.md](EXECUCAO_PIPELINE_ML.md), [VALIDACAO_MODELO_ML.md](VALIDACAO_MODELO_ML.md) e [TROUBLESHOOTING_ML.md](TROUBLESHOOTING_ML.md).
3. O Ollama e o modelo devem estar instalados/baixados e acessíveis pelo backend; a primeira inferência pode demorar enquanto o modelo é carregado.
4. Políticas dinâmicas de limiares por faixa (`politica_classificacao_versao`) e explicabilidade detalhada (*SHAP / feature contributions*) podem trafegar via `metadados_tecnicos` seguindo a política anti-leakage.
