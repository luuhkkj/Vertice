# Referência Completa de Endpoints — API Vértice (`v1`)

Documentação técnica dos endpoints expostos pelo backend FastAPI do **Vértice** (`app.main:app`), alinhada ao contrato OpenAPI gerado pela aplicação (`75` operações HTTP).

---

## 1. Convenções Gerais, Autenticação e RBAC

### 1.1 Prefixo e Documentação Interativa
- **Base API (`API_V1_STR`)**: `/api/v1`
- **Swagger UI** (disponível apenas quando `DEBUG=True`): `/docs`
- **ReDoc** (disponível apenas quando `DEBUG=True`): `/redoc`
- **Esquema OpenAPI** (disponível apenas quando `DEBUG=True`): `/openapi.json`

### 1.2 Autenticação
1. **Usuários Humanos (JWT Bearer)**
   - Obtido em `POST /api/v1/auth/login`.
   - Enviado no header `Authorization: Bearer <access_token>`.
   - Papéis canônicos (`PapelUsuario`): exclusivamente `administrador`, `gestor` e `professor`.
2. **Serviços Externos de Machine Learning (`X-Service-Token`)**
   - Utilizado exclusivamente para ingestão de previsões (`POST /api/v1/previsoes` e `POST /api/v1/previsoes/lote`).
   - Enviado no header `X-Service-Token: <chave_secreta>` (ou `Authorization: Bearer <chave_secreta>`).
   - O backend rejeita explicitamente tokens JWT de usuários comuns nessas rotas (`HTTP 403`) e armazena apenas prefixo + hash SHA-256 da credencial técnica.

### 1.3 Dependências de Permissão (`backend/app/core/dependencies.py`)
| Regra / Dependência | Papéis Aceitos | Observação de Escopo |
|---|---|---|
| Pública (sem autenticação) | Todos | Apenas `/`, `/health`, `/api/v1/health`, `/api/v1/auth/login` |
| `get_current_user` | Usuário ativo autenticado | Valida token JWT e status `ativo=True` |
| `require_qualquer_papel` | `administrador`, `gestor`, `professor` | Regras de escopo aplicadas nos serviços |
| `require_admin` | `administrador` | Gestão de usuários e emissão/revogação de credenciais ML |
| `require_gestor_ou_admin` | `administrador`, `gestor` | Administração estrutural de rede/escola |
| `require_importacao_datasets` | `gestor`, `professor` | Escopo escolar/turma/disciplina estrito (`administrador` recebe `403`) |
| `require_acesso_pedagogico` | `gestor`, `professor` | Indicadores, avaliações, atividades, acompanhamentos e previsões (`administrador` recebe `403`) |
| `get_credencial_integracao_predicao` | Pipeline ML (`X-Service-Token`) | Escopo opcional por `escola_id` e lista `modelos_permitidos` |

### 1.4 Códigos HTTP Comuns e LGPD
- `200 OK` / `201 Created` / `204 No Content`: operação bem-sucedida.
- `401 Unauthorized`: token ausente, inválido, expirado ou usuário inativo.
- `403 Forbidden`: papel não autorizado ou tentativa de acesso a escola/turma/disciplina fora do vínculo.
- `404 Not Found`: recurso inexistente.
- `409 Conflict`: violação de unicidade (ex.: `codigo_anonimo`, código de avaliação/atividade, idempotência de previsão, vínculo duplicado em `professor_turmas`).
- `422 Unprocessable Content`: falha de validação de payload, colunas PII proibidas em planilhas ou variáveis rejeitadas pela política anti-data-leakage.
- `501 Not Implemented`: rota reservada (`POST /api/v1/auth/refresh`).
- `503 Service Unavailable`: LLM externo não configurado em `POST /api/v1/assistente/consultar` (ou falha de conexão com banco no health check quando degradado).
- **Anonimização (LGPD)**: estudantes são identificados exclusivamente por `id` (UUID) e `codigo_anonimo`. Planilhas com colunas nominais/PII (`nome`, `cpf`, `rg`, `email`, `telefone`, `endereco`, `data_nascimento`, etc.) são bloqueadas na validação.

---

## 2. Infraestrutura e Saúde (`Root` & `Health`)

| Método | Rota | Auth | Descrição | Resposta `200` |
|---|---|---|---|---|
| `GET` | `/` | Pública | Informações básicas de status do serviço | Objeto JSON (`service`, `status`, `version`, etc.) |
| `GET` | `/health` | Pública | Health check com verificação ativa de banco (`SELECT 1` via `get_db`) | Objeto JSON de saúde |
| `GET` | `/api/v1/health` | Pública | Health check versionado da API v1 | Objeto JSON de saúde |

---

## 3. Autenticação (`/api/v1/auth`)

| Método | Rota | Auth | Payload (`JSON`) | Resposta Principal | Observações |
|---|---|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Pública | `LoginRequest`: `email`, `senha` (obrigatórios) | `200 TokenResponse`: `access_token`, `token_type`, `expires_in`, `usuario` | `401` em credenciais inválidas ou usuário inativo; `422` em payload inválido |
| `GET` | `/api/v1/auth/me` | `get_current_user` | — | `200 UsuarioResponse` | Retorna dados do usuário autenticado |
| `POST` | `/api/v1/auth/logout` | `get_current_user` | — | `200 LogoutResponse`: `message`, `detail` | Logout stateless (cliente descarta JWT) |
| `POST` | `/api/v1/auth/refresh` | — | — | `501 Not Implemented` | Reservado para rotação futura |

---

## 4. Usuários (`/api/v1/usuarios`)

| Método | Rota | RBAC | Parâmetros Query / Path | Payload (`JSON`) | Resposta |
|---|---|---|---|---|---|
| `POST` | `/api/v1/usuarios` | `require_admin` | — | `UsuarioCreate`: `nome`*, `email`*, `senha`*, `papel`, `escola_id`, `ativo` | `201 UsuarioResponse` |
| `GET` | `/api/v1/usuarios` | `require_gestor_ou_admin` | `skip=0`, `limit=100` (1..200), `papel?`, `apenas_ativos=false` | — | `200 list[UsuarioResponse]` |
| `GET` | `/api/v1/usuarios/{usuario_id}` | `require_gestor_ou_admin` | Path: `usuario_id` (UUID) | — | `200 UsuarioResponse` |
| `PATCH` | `/api/v1/usuarios/{usuario_id}` | `require_admin` | Path: `usuario_id` (UUID) | `UsuarioUpdate`: `nome?`, `email?`, `senha?`, `papel?`, `escola_id?`, `ativo?` | `200 UsuarioResponse` |

> **Escopo do `gestor`**: ao consultar `GET /api/v1/usuarios` ou `GET /api/v1/usuarios/{usuario_id}`, o gestor visualiza apenas usuários vinculados à sua própria `escola_id` (ou recebe `403` ao consultar usuário de outra escola ou se não possuir escola vinculada).

---

## 5. Estrutura Escolar: Escolas, Turmas, Disciplinas e Atribuições

### 5.1 Escolas (`/api/v1/escolas`)

| Método | Rota | RBAC | Parâmetros | Payload (`JSON`) | Resposta |
|---|---|---|---|---|---|
| `POST` | `/api/v1/escolas` | `require_gestor_ou_admin` | — | `EscolaCreate`: `nome`*, `codigo`*, `ativo` | `201 EscolaResponse` |
| `GET` | `/api/v1/escolas` | `require_qualquer_papel` | `skip=0`, `limit=100` | — | `200 list[EscolaResponse]` |
| `GET` | `/api/v1/escolas/{escola_id}` | `require_qualquer_papel` | Path: `escola_id` (UUID) | — | `200 EscolaResponse` |
| `PATCH` | `/api/v1/escolas/{escola_id}` | `require_gestor_ou_admin` | Path: `escola_id` (UUID) | `EscolaUpdate`: `nome?`, `codigo?`, `ativo?` | `200 EscolaResponse` |

> **Isolamento**: `administrador` lista/consulta todas; `gestor` acessa somente sua `escola_id` (`403` para outras unidades); `professor` acessa sua `escola_id` (se definida) e as escolas das turmas em que possui vínculo em `professor_turmas`.

### 5.2 Turmas (`/api/v1/turmas`)

| Método | Rota | RBAC | Parâmetros | Payload (`JSON`) | Resposta |
|---|---|---|---|---|---|
| `POST` | `/api/v1/turmas` | `require_gestor_ou_admin` | — | `TurmaCreate`: `nome`*, `serie`*, `turno`*, `ano_letivo`*, `escola_id`*, `ativo` | `201 TurmaResponse` |
| `GET` | `/api/v1/turmas` | `require_qualquer_papel` | `skip=0`, `limit=100` | — | `200 list[TurmaResponse]` |
| `GET` | `/api/v1/turmas/{turma_id}` | `require_qualquer_papel` | Path: `turma_id` (UUID) | — | `200 TurmaResponse` |
| `PATCH` | `/api/v1/turmas/{turma_id}` | `require_gestor_ou_admin` | Path: `turma_id` (UUID) | `TurmaUpdate`: `nome?`, `serie?`, `turno?`, `ano_letivo?`, `ativo?` | `200 TurmaResponse` |

### 5.3 Disciplinas (`/api/v1/disciplinas`)

| Método | Rota | RBAC | Parâmetros | Payload (`JSON`) | Resposta |
|---|---|---|---|---|---|
| `POST` | `/api/v1/disciplinas` | `require_gestor_ou_admin` | — | `DisciplinaCreate`: `nome`*, `codigo`*, `ativo` | `201 DisciplinaResponse` |
| `GET` | `/api/v1/disciplinas` | `require_qualquer_papel` | `skip=0`, `limit=100` | — | `200 list[DisciplinaResponse]` |
| `GET` | `/api/v1/disciplinas/{disciplina_id}` | `require_qualquer_papel` | Path: `disciplina_id` (UUID) | — | `200 DisciplinaResponse` |
| `PATCH` | `/api/v1/disciplinas/{disciplina_id}` | `require_gestor_ou_admin` | Path: `disciplina_id` (UUID) | `DisciplinaUpdate`: `nome?`, `codigo?`, `ativo?` | `200 DisciplinaResponse` |

### 5.4 Atribuições Professor–Turma–Disciplina (`/api/v1/atribuicoes`)

| Método | Rota | RBAC | Parâmetros | Payload (`JSON`) | Resposta |
|---|---|---|---|---|---|
| `POST` | `/api/v1/atribuicoes` | `require_gestor_ou_admin` | — | `AtribuicaoCreate`: `professor_id`*, `turma_id`*, `disciplina_id?` | `201 AtribuicaoResponse` |
| `GET` | `/api/v1/atribuicoes` | `require_qualquer_papel` | `skip=0`, `limit=100` | — | `200 list[AtribuicaoResponse]` |
| `DELETE` | `/api/v1/atribuicoes/{atribuicao_id}` | `require_gestor_ou_admin` | Path: `atribuicao_id` (UUID) | — | `204 No Content` |

> **Regras críticas**: `disciplina_id=None` representa professor polivalente/unidocente na turma e possui índice único parcial em PostgreSQL (`disciplina_id IS NULL`) impedindo duplicidade (`409`). Caso o professor possua `usuario.escola_id` preenchido e distinto de `turma.escola_id`, o vínculo é bloqueado com `403`.

---

## 6. Estudantes Anonimizados (`/api/v1/estudantes`)

| Método | Rota | RBAC | Parâmetros | Resposta |
|---|---|---|---|---|
| `GET` | `/api/v1/estudantes` | `require_importacao_datasets` (`gestor`, `professor`) | Query: `turma_id?`, `disciplina_id?`, `ano_letivo?`, `periodo_letivo?`, `skip=0`, `limit=100` | `200 list[EstudanteResponse]` + Header `X-Total-Count` |
| `GET` | `/api/v1/estudantes/{estudante_id}` | `require_importacao_datasets` (`gestor`, `professor`) | Path: `estudante_id` (UUID) | `200 EstudanteHistoricoDetalhadoResponse` (`+ boletins`) |

> **Campos de `EstudanteResponse`**: `id`, `codigo_anonimo`, `escola_id`, `historico_reprovacoes`, `ativo`, `criado_em`, `atualizado_em`. Nenhum dado nominal existe no schema. `X-Total-Count` informa o total de estudantes distintos no escopo para paginação server-side no frontend.

---

## 7. Importação Automatizada em Duas Etapas (`/api/v1/importacoes`)

Todas as rotas exigem `require_importacao_datasets` (`gestor` ou `professor`).

### 7.1 Fluxo Obrigatório em Duas Etapas
1. **Etapa 1 (`POST /api/v1/importacoes/validar`)**: envia arquivo CSV ou XLSX (`multipart/form-data`, campo `arquivo`), executa validação estrutural, anti-PII, vínculos de turma/disciplina/escola, unicidade e gera prévia + `RelatorioValidacaoSchema` + `pode_confirmar`. **Nada é persistido nas tabelas pedagógicas nesta etapa.**
2. **Etapa 2 (`POST /api/v1/importacoes/{lote_id}/confirmar`)**: persiste todo o lote em transação atômica única; qualquer falha de integridade executa `rollback` total. Alternativamente, `descartar` cancela o lote validado sem persistir dados.

### 7.2 Endpoints de Importação

| Método | Rota | Parâmetros | Corpo / Resposta |
|---|---|---|---|
| `GET` | `/api/v1/importacoes` | Query: `skip=0`, `limit=50` | `200 list[LoteImportacaoResumoResponse]` (histórico no escopo) |
| `GET` | `/api/v1/importacoes/modelos/dados-escolares` | Query: `formato=csv` (`csv` \| `xlsx`) | `200` Arquivo modelo para download (`14` colunas) |
| `GET` | `/api/v1/importacoes/modelos/avaliacoes` | Query: `formato=csv` (`csv` \| `xlsx`) | `200` Arquivo modelo para download (`16` colunas) |
| `GET` | `/api/v1/importacoes/modelos/atividades` | Query: `formato=csv` (`csv` \| `xlsx`) | `200` Arquivo modelo para download (`12` colunas) |
| `POST` | `/api/v1/importacoes/validar` | Query: `tipo_importacao?` (`DADOS_ESCOLARES` \| `AVALIACOES` \| `ATIVIDADES`) | Form `arquivo` (`UploadFile`) -> `201 LoteImportacaoPreviaResponse` |
| `GET` | `/api/v1/importacoes/{lote_id}` | Path: `lote_id` (UUID) | `200 LoteImportacaoResumoResponse` |
| `GET` | `/api/v1/importacoes/{lote_id}/previa` | Path: `lote_id` (UUID) | `200 LoteImportacaoPreviaResponse` |
| `POST` | `/api/v1/importacoes/{lote_id}/confirmar` | Path: `lote_id` (UUID) | `200 ConfirmacaoImportacaoResponse` |
| `POST` | `/api/v1/importacoes/{lote_id}/descartar` | Path: `lote_id` (UUID) | `200 LoteImportacaoResumoResponse` |

### 7.3 Colunas Oficiais das Planilhas Modelo
- **Dados Escolares**: `codigo_anonimo`, `turma`, `disciplina`, `ano_letivo`, `periodo_letivo`, `frequencia_percentual`, `faltas`, `media_geral`, `nota`, `nota_prova`, `nota_trabalho`, `historico_reprovacoes`, `participacao_recuperacao`, `situacao_final`.
- **Avaliações**: `id_avaliacao`, `titulo_avaliacao`, `disciplina`, `turma`, `periodo_letivo`, `data_avaliacao`, `id_questao`, `tipo_questao`, `valor_questao`, `alternativa_correta`, `codigo_anonimo`, `alternativa_marcada`, `em_branco`, `nota_obtida`, `faixa_dificuldade`, `topico`.
- **Atividades**: `id_atividade`, `titulo_atividade`, `disciplina`, `turma`, `periodo_letivo`, `ano_letivo`, `data_limite`, `nota_maxima`, `codigo_anonimo`, `status_entrega`, `data_entrega`, `nota`.

---

## 8. Avaliações, Questões e Mapa de Acertos (`/api/v1/avaliacoes` e `/api/v1/questoes`)

Todas as rotas exigem `require_acesso_pedagogico` (`gestor` ou `professor`) com validação de vínculo turma/disciplina/escola.

| Método | Rota | Parâmetros | Payload (`JSON`) | Resposta |
|---|---|---|---|---|
| `POST` | `/api/v1/avaliacoes` | — | `AvaliacaoCreate`: `codigo?`, `titulo`*, `turma_id`*, `disciplina_id`*, `periodo_letivo`*, `data_avaliacao`*, `status` | `201 AvaliacaoResponse` |
| `GET` | `/api/v1/avaliacoes` | `turma_id?`, `disciplina_id?`, `periodo_letivo?`, `skip=0`, `limit=100` | — | `200 list[AvaliacaoResponse]` |
| `GET` | `/api/v1/avaliacoes/{avaliacao_id}` | Path: `avaliacao_id` | — | `200 AvaliacaoDetalhadaResponse` (`+ questoes`) |
| `PATCH` | `/api/v1/avaliacoes/{avaliacao_id}` | Path: `avaliacao_id` | `AvaliacaoUpdate`: `titulo?`, `periodo_letivo?`, `data_avaliacao?`, `status?`, `ativo?` | `200 AvaliacaoResponse` |
| `POST` | `/api/v1/avaliacoes/{avaliacao_id}/questoes` | Path: `avaliacao_id` | `QuestaoAvaliacaoCreate`: `codigo_questao`*, `tipo_questao`*, `alternativa_correta?`, `valor_questao`*, `faixa_dificuldade`, `topico?` | `201 QuestaoAvaliacaoResponse` |
| `GET` | `/api/v1/avaliacoes/{avaliacao_id}/questoes` | Path: `avaliacao_id` | — | `200 list[QuestaoAvaliacaoResponse]` |
| `GET` | `/api/v1/avaliacoes/{avaliacao_id}/respostas` | Path: `avaliacao_id`; Query: `questao_id?`, `estudante_id?` | — | `200 list[RespostaAvaliacaoResponse]` |
| `PATCH` | `/api/v1/questoes/{questao_id}` | Path: `questao_id` | `QuestaoAvaliacaoUpdate`: `codigo_questao?`, `tipo_questao?`, `alternativa_correta?`, `valor_questao?`, `faixa_dificuldade?`, `topico?` | `200 QuestaoAvaliacaoResponse` |
| `POST` | `/api/v1/questoes/{questao_id}/respostas` | Path: `questao_id`; Query: `permitir_atualizacao=false` | `RespostaAvaliacaoCreate`: `estudante_id?`, `codigo_anonimo?`, `alternativa_marcada?`, `em_branco?`, `nota_obtida?`, `acertou?` | `201 RespostaAvaliacaoResponse` |

---

## 9. Participação e Entregas de Atividades (`/api/v1/atividades` e `/api/v1/entregas`)

Todas as rotas exigem `require_acesso_pedagogico` (`gestor` ou `professor`). A regra central controla quem **deveria entregar** além de quem entregou.

| Método | Rota | Parâmetros | Payload (`JSON`) | Resposta |
|---|---|---|---|---|
| `POST` | `/api/v1/atividades` | — | `AtividadeCreate`: `codigo?`, `titulo`*, `turma_id`*, `disciplina_id`*, `periodo_letivo`*, `data_limite`*, `nota_maxima`, `status`, `gerar_entregas_esperadas` | `201 AtividadeResponse` |
| `GET` | `/api/v1/atividades` | `turma_id?`, `disciplina_id?`, `periodo_letivo?`, `skip=0`, `limit=100` | — | `200 list[AtividadeResponse]` |
| `GET` | `/api/v1/atividades/{atividade_id}` | Path: `atividade_id` | — | `200 AtividadeResponse` |
| `PATCH` | `/api/v1/atividades/{atividade_id}` | Path: `atividade_id` | `AtividadeUpdate`: `titulo?`, `periodo_letivo?`, `data_limite?`, `nota_maxima?`, `status?`, `ativo?` | `200 AtividadeResponse` |
| `POST` | `/api/v1/atividades/{atividade_id}/gerar-entregas-esperadas` | Path: `atividade_id`; Query: `data_referencia?` | — | `200 GeracaoEntregasEsperadasResponse` |
| `GET` | `/api/v1/atividades/{atividade_id}/entregas` | Path: `atividade_id`; Query: `estudante_id?` | — | `200 list[EntregaAtividadeResponse]` |
| `POST` | `/api/v1/atividades/{atividade_id}/entregas` | Path: `atividade_id` | `EntregaAtividadeUpsert`: `estudante_id?`, `codigo_anonimo?`, `data_entrega?`, `nota?`, `status_entrega?` | `201 EntregaAtividadeResponse` |
| `PATCH` | `/api/v1/entregas/{entrega_id}` | Path: `entrega_id` | `EntregaAtividadeUpdate`: `data_entrega?`, `nota?`, `status_entrega?` | `200 EntregaAtividadeResponse` |

---

## 10. Acompanhamento Pedagógico (`/api/v1/acompanhamentos`)

Todas as rotas exigem `require_acesso_pedagogico` (`gestor` ou `professor`). Edições preservam histórico estruturado em `historico_alteracoes`.

| Método | Rota | Parâmetros | Payload (`JSON`) | Resposta |
|---|---|---|---|---|
| `POST` | `/api/v1/acompanhamentos` | — | `AcompanhamentoCreate`: `estudante_id?`, `codigo_anonimo?`, `turma_id?`, `disciplina_id?`, `origem`*, `tipo_acao`*, `descricao`* | `201 AcompanhamentoResponse` |
| `GET` | `/api/v1/acompanhamentos` | `turma_id?`, `estudante_id?`, `origem?`, `skip=0`, `limit=100` | — | `200 list[AcompanhamentoResponse]` |
| `GET` | `/api/v1/acompanhamentos/{acompanhamento_id}` | Path: `acompanhamento_id` | — | `200 AcompanhamentoResponse` |
| `PATCH` | `/api/v1/acompanhamentos/{acompanhamento_id}` | Path: `acompanhamento_id` | `AcompanhamentoUpdate`: `origem?`, `tipo_acao?`, `descricao?`, `ativo?` | `200 AcompanhamentoResponse` |

---

## 11. Indicadores Analíticos (`/api/v1/indicadores`)

Todas as rotas exigem `require_acesso_pedagogico` (`gestor` ou `professor`).

| Método | Rota | Parâmetros Query | Resposta `200` (campos principais) |
|---|---|---|---|
| `GET` | `/api/v1/indicadores/gerais` | `escola_id?`, `turma_id?`, `disciplina_id?`, `ano_letivo?`, `periodo_letivo?`, `modelo_nome?`, `modelo_versao?` | `IndicadoresGeraisResponse`: `total_estudantes_distintos`, `total_registros_boletim`, `frequencia_media`, `media_geral`, `distribuicao_por_serie`, `distribuicao_por_turma`, `distribuicao_por_turno`, `evolucao_por_periodo`, `comparacao_periodo_anterior`, `possui_previsoes_risco`, `distribuicao_faixas_risco`, `modelo_nome_vigente`, `modelo_versao_vigente`, `ultima_previsao_em`, `nota_metodologica_risco` |
| `GET` | `/api/v1/indicadores/avaliacoes` | `escola_id?`, `turma_id?`, `disciplina_id?`, `ano_letivo?`, `periodo_letivo?`, `avaliacao_id?` | `IndicadoresAvaliacoesResponse`: totais de avaliações/questões/respostas/acertos/erros/brancos, `taxa_acerto_geral_percentual`, `media_avaliacao_ponderada`, `soma_pesos_avaliacao`, `media_pontos_obtidos`, extremos por questão, `questoes` (com distribuição A–E/BRANCO), `distribuicao_acertos_estudantes`, `distribuicao_por_topico`, `desempenho_por_turma_disciplina` |
| `GET` | `/api/v1/indicadores/participacao` | `escola_id?`, `turma_id?`, `disciplina_id?`, `ano_letivo?`, `periodo_letivo?`, `atividade_id?`, `estudante_id?`, `data_referencia?` | `IndicadoresParticipacaoResponse`: `total_atividades`, `total_entregas_esperadas`, `entregas_realizadas`, `entregas_no_prazo`, `entregas_atrasadas`, `nao_entregas_apos_prazo`, `atividades_pendentes_antes_prazo`, `taxa_entrega_geral_percentual`, `media_notas_disponiveis`, `taxa_por_atividade`, `taxa_por_turma`, `percentual_por_estudante`, `evolucao_participacao` |

---

## 12. Integração Preditiva e Anti-Data Leakage (`/api/v1/previsoes`)

Documentação arquitetural complementar em [FASE7_INTEGRACAO_PREDITIVA_E_IA.md](FASE7_INTEGRACAO_PREDITIVA_E_IA.md).

### 12.1 Governança de Credenciais de Serviço ML (Somente `administrador`)

| Método | Rota | RBAC | Parâmetros / Corpo | Resposta |
|---|---|---|---|---|
| `POST` | `/api/v1/previsoes/credenciais` | `require_admin` | `CredencialIntegracaoCreate`: `nome`*, `escola_id?`, `modelos_permitidos?`, `expira_em?` | `201 CredencialIntegracaoCriadaResponse` (`chave_secreta` exibida apenas na criação) |
| `GET` | `/api/v1/previsoes/credenciais` | `require_admin` | Query: `escola_id?`, `apenas_ativas?` | `200 list[CredencialIntegracaoResponse]` |
| `PATCH` | `/api/v1/previsoes/credenciais/{credencial_id}/revogar` | `require_admin` | Path: `credencial_id` | `200 CredencialIntegracaoResponse` |

### 12.2 Contratos Anti-Leakage e Ingestão de Previsões

| Método | Rota | Auth / RBAC | Parâmetros / Corpo | Resposta |
|---|---|---|---|---|
| `GET` | `/api/v1/previsoes/contrato-variaveis` | `get_current_user` | — | `200 CatalogoVariaveisResponse` (`variaveis_elegiveis`, `campos_proibidos_base`, `alvo_supervisionado_reservado`, `metadados_tecnicos_permitidos`) |
| `POST` | `/api/v1/previsoes/validar-variaveis` | `get_current_user` | `ValidarVariaveisRequest`: `variaveis`*, `campos_proibidos_extras?`, `catalogo_extensao?` | `200 ResultadoValidacaoLeakage` |
| `POST` | `/api/v1/previsoes` | `X-Service-Token` / `Authorization` (serviço ML) | `PrevisaoRecebimentoItem`: `ano_letivo`*, `periodo_letivo`*, `pontuacao_risco`* (`0..1`), `faixa_risco`* (`BAIXO|MODERADO|ALTO|CRITICO`), `modelo_nome`*, `modelo_versao`*, `gerado_em`*, `estudante_id?`/`codigo_anonimo?`, `escola_id?`, `turma_id?`, `tipo_previsao`, `variaveis_utilizadas?`, `metadados_tecnicos?` | `201 PrevisaoResponse` (`409` em assinatura duplicada; `422` em leakage/variável não catalogada) |
| `POST` | `/api/v1/previsoes/lote` | `X-Service-Token` / `Authorization` (serviço ML) | `PrevisaoRecebimentoLoteRequest`: `lote_externo_id?`, `itens`* | `201 PrevisaoLoteResponse` (transação atômica) |

### 12.3 Consulta Pedagógica de Previsões (`require_acesso_pedagogico`: `gestor`, `professor`)

| Método | Rota | Parâmetros Query / Path | Resposta `200` |
|---|---|---|---|
| `GET` | `/api/v1/previsoes` | `escola_id?`, `turma_id?`, `disciplina_id?`, `ano_letivo?`, `periodo_letivo?`, `tipo_previsao?`, `faixa_risco?`, `modelo_nome?`, `modelo_versao?`, `skip=0`, `limit=100` | `list[PrevisaoResponse]` |
| `GET` | `/api/v1/previsoes/resumo` | `escola_id?`, `turma_id?`, `disciplina_id?`, `ano_letivo?`, `periodo_letivo?`, `tipo_previsao?`, `modelo_nome?`, `modelo_versao?` | `ResumoPrevisoesRiscoResponse` (aplica política de versão única por modelo) |
| `GET` | `/api/v1/previsoes/estudantes/{estudante_id}` | Path: `estudante_id`; Query: `tipo_previsao?`, `modelo_nome?`, `modelo_versao?` | `HistoricoPrevisoesEstudanteResponse` (histórico append-only) |

---

## 13. Assistente IA — Contexto Estruturado e Auditoria (`/api/v1/assistente`)

| Método | Rota | Auth / RBAC | Corpo / Parâmetros | Resposta |
|---|---|---|---|---|
| `GET` | `/api/v1/assistente/status` | `get_current_user` | — | `200 StatusAssistenteResponse`: estado do provedor (`provedor_llm_configurado`, `modo_operacao`, `niveis_contexto_suportados`, `auditoria_ativa`) |
| `POST` | `/api/v1/assistente/contexto` | `get_current_user` (somente `gestor` e `professor`; `administrador` é negado com `403` e auditado) | `SolicitacaoContextoAssistente`: `tipo_contexto`* (`ESCOLA`\|`TURMA`\|`INDIVIDUAL`), `escola_id?`, `turma_id?`, `disciplina_id?`, `estudante_id?`, `ano_letivo?`, `periodo_letivo?`, `modelo_nome?`, `modelo_versao?`, `incluir_acompanhamentos`, `conversation_id?` | `200 ContextoAssistenteEstruturado` (dados reais e diretrizes anti-alucinação; gera `request_id` único no backend) |
| `POST` | `/api/v1/assistente/consultar` | `get_current_user` (mesma validação estrita de escopo de `/contexto`) | `ConsultaAssistentePromptRequest`: campos de `SolicitacaoContextoAssistente` + `pergunta_usuario`* | `200 RespostaAssistenteLLM` quando LLM plugado; **`503 Service Unavailable`** enquanto `ProvedorLLMNaoConfigurado` estiver ativo |
| `GET` | `/api/v1/assistente/auditoria` | `get_current_user` (`administrador`: rede; `gestor`: própria escola; `professor`: apenas próprias consultas) | Query: `escola_id?`, `resultado_autorizacao?`, `request_id?`, `conversation_id?`, `skip=0`, `limit=100` | `200 list[AuditoriaConsultaIAResponse]` |

---

## 14. Catálogo Oficial de Enums da API

- **`PapelUsuario`**: `administrador`, `gestor`, `professor`
- **`TipoImportacao`**: `DADOS_ESCOLARES`, `AVALIACOES`, `ATIVIDADES`
- **`StatusLoteImportacao`**: `recebido`, `validando`, `validado`, `com_erros`, `confirmado`, `falhou`, `descartado`
- **`SituacaoFinalPeriodo`**: `Aprovado`, `Reprovado`, `Evadido`
- **`StatusAvaliacao`**: `RASCUNHO`, `PUBLICADA`, `ENCERRADA`, `ARQUIVADA`
- **`TipoQuestao`**: `FECHADA`, `ABERTA`
- **`FaixaDificuldadeQuestao`**: `Fácil`, `Adequada`, `Atenção`, `Difícil`
- **`StatusAtividade`**: `ABERTA`, `ENCERRADA`, `ARQUIVADA`
- **`StatusEntregaAtividade`**: `ENTREGUE`, `ATRASADO`, `PENDENTE`, `NAO_ENTREGUE`
- **`OrigemAcompanhamento`**: `ESTUDANTES`, `MAPA_ACERTOS`, `PARTICIPACAO`
- **`TipoPrevisao`**: `EVASAO`, `REPROVACAO`, `RISCO_ACADEMICO`
- **`FaixaRisco`**: `BAIXO`, `MODERADO`, `ALTO`, `CRITICO`
- **`TipoContextoAssistente`**: `ESCOLA`, `TURMA`, `INDIVIDUAL`
- **`ResultadoAutorizacaoIA`**: `AUTORIZADO`, `NEGADO`, `ERRO_EXECUCAO`
