# Fase 7 — Integração com Modelo Preditivo e Assistente IA

Este documento descreve a arquitetura implementada na **Fase 7** do projeto Vértice. Esta fase estabelece toda a fundação de contratos, persistência, segurança, prevenção de *data leakage*, auditoria e preparação de contexto no backend e frontend, **sem executar treinamento/inferência de ML nem chamadas externas a APIs de LLM**.

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
                     ProvedorLLMBase (ProvedorLLMNaoConfigurado -> 503)
```

---

## 2. Módulo Preditivo (`backend/app/integrations/prediction/`)

### 2.1 Credenciais Técnicas de Serviço (`CredencialIntegracaoPredicao`)
- Tokens JWT comuns de `professor`, `gestor` ou `administrador` **não autorizam** o envio de previsões (`HTTP 403 Forbidden`).
- Apenas administradores emitem (`POST /api/v1/previsoes/credenciais`), listam (`GET /api/v1/previsoes/credenciais`) e revogam (`PATCH /api/v1/previsoes/credenciais/{id}/revogar`) credenciais técnicas dedicadas.
- O segredo bruto (`vtx_ml_*`) é exibido **uma única vez** na criação; apenas prefixo e hash SHA-256 são gravados no banco.
- A credencial pode restringir `escola_id`, `modelos_permitidos` e `expira_em`.

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
- **Variáveis elegíveis (`CATALOGO_VARIAVEIS_PREDITIVAS`):** `frequencia_percentual`, `faltas`, `media_geral`, `notas_baixas`, `historico_reprovacoes`, `participacao_recuperacao`, `atrasos`, `idade`, `taxa_acerto_avaliacoes`, `taxa_entrega_atividades`, `entregas_atrasadas`, `entregas_nao_entregues`, `ano_letivo`, `periodo_letivo`, `turno`, `serie`.
- **Variável-alvo supervisionada reservada (`CONTRATO_ALVO_SUPERVISIONADO_SITUACAO_FINAL`):** `situacao_final` é mantida exclusivamente como referência documental de desfecho (`disponibilidade_temporal = pos_desfecho`, `elegivel_predicao = False`, `uso_exclusivo_alvo_supervisionado = True`) para futura etapa de treinamento supervisionado, sendo bloqueada como entrada preditiva.
- **Variáveis bloqueadas (`CAMPOS_PROIBIDOS_PREDICAO` -> `HTTP 422`):**
  - `situacao_final` e variantes pós-desfecho (`evadiu`, `reprovou`, `aprovado`, `desfecho`, `target`, `label`, `data_evasao`, `status_final`, `conclusao_periodo`, etc.).
  - Atributos de identificação pessoal direta (LGPD): `nome`, `nome_completo`, `cpf`, `rg`, `email`, `telefone`, `endereco`, `aluno_nome`, etc.
- Extensões de regras são suportadas via `campos_proibidos_extras` e `catalogo_extensao` (aceitas apenas mediante contrato completo com `elegivel_predicao=True`, disponibilidade anterior à data de corte e ausência de PII).

### 2.4 Contrato Fechado de Metadados Técnicos (`metadados_tecnicos`)
- `metadados_tecnicos` aceita exclusivamente chaves do catálogo operacional fechado (`CATALOGO_METADADOS_TECNICOS_PERMITIDOS`): `pipeline_execucao_id`, `framework_ml`, `origem_pipeline`, `data_corte_extracao`, `janela_corte_dias`, `limiar_decisao`, `calibracao_aplicada`, `tempo_inferencia_ms`, `hash_artefato_modelo` e `politica_limiares` (`baixo_max`, `moderado_max`, `alto_max`, `critico_min` em `[0.0, 1.0]`).
- É proibido enviar campos desconhecidos, PII, variáveis de entrada/pós-desfecho, texto livre pedagógico ou segredos/tokens (`Bearer`, JWTs, `api_key`, `vtx_ml_*`), sendo tudo validado recursivamente com rejeição `HTTP 422`.
- Todas as respostas da API passam por `sanitizar_metadados_tecnicos_resposta`, removendo chaves não contratuais caso existam registros legados no banco.

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

### 4.3 Abstração para Provedor LLM
- `ProvedorLLMBase` define o contrato estável para futura conexão de modelos externos (Gemini/OpenAI/local).
- Na Fase 7, `ProvedorLLMNaoConfigurado` responde de forma transparente (`GET /api/v1/assistente/status` com `provedor_llm_configurado=false` e `POST /api/v1/assistente/consultar` retornando `HTTP 503`) sem simular respostas generativas.

---

## 5. Limitações Conhecidas e Próximos Passos (Pós-Fase 7)

1. Treinamento e *serving* do pipeline de ML ainda serão conectados em fase posterior utilizando o contrato `/api/v1/previsoes(/lote)` com credenciais `vtx_ml_*`.
2. Conexão de provedor LLM externo será realizada implementando `ProvedorLLMBase` e registrando variáveis de ambiente próprias (sem segredos no repositório).
3. Políticas dinâmicas de limiares por faixa (`politica_classificacao_versao`) e explicabilidade detalhada (*SHAP / feature contributions*) podem trafegar via `metadados_tecnicos` seguindo a política anti-leakage.
