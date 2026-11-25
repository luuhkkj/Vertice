# Troubleshooting — Pipeline Automatizado de Machine Learning (Vértice)

Guia rápido de diagnóstico e correção para incidentes de credencial única, modelo, validação, envio e exibição no painel.

---

## 1. Token ausente

- **Sintoma**: `ErroConfiguracaoPipeline` / `ErroExtracaoConfiguracao` / `ErroEnvioAutenticacao`: *"Credencial técnica `VERTICE_ML_SERVICE_TOKEN` ausente"*.
- **Solução**:
  1. No painel **Administrador → Credenciais ML**, selecione a escola e o modelo e clique em **Emitir token técnico**.
  2. Exporte `VERTICE_ML_SERVICE_TOKEN=vtx_ml_...` no ambiente do pipeline e confirme com `python -m app.integrations.prediction.pipeline.executor --check-config`.

---

## 2. Token inválido (`HTTP 401`)

- **Sintoma**: `ErroExtracaoAutenticacao` ou `ErroEnvioAutenticacao` (`HTTP 401 Unauthorized`).
- **Causa**: Token truncado, com aspas/espaços extras ou emitido em outro banco de dados.
- **Solução**: Confira `VERTICE_ML_SERVICE_TOKEN`; se o valor original não estiver mais disponível, revogue a credencial antiga na UI e emita uma nova.

---

## 3. Credencial sem permissão de leitura, revogada, expirada ou fora do escopo (`HTTP 403`)

- **Sintoma**: `ErroExtracaoAutorizacao` ou `ErroEnvioAutorizacao` (`HTTP 403 Forbidden`).
- **Causas reais**:
  1. **Credencial legada sem permissão de leitura**: credenciais antigas ou globais (`permite_leitura_inferencia=False`) continuam autorizando apenas o envio e são bloqueadas na exportação (`GET /api/v1/previsoes/exportacao-inferencia`). Emita uma nova credencial selecionando uma escola específica e um modelo na tela **Credenciais ML**.
  2. **Credencial revogada ou expirada**: reemitir manualmente na UI.
  3. **Token JWT comum de usuário**: usuários humanos recebem `403` tanto na extração quanto na ingestão do pipeline.
  4. **Modelo ou escola divergente no envio**: o backend valida que `escola_id` do estudante e `modelo_nome` correspondem à credencial autenticada.

---

## 4. Modelo ou artefato indisponível

- **Sintoma**: `etapa_falha: "carregamento_modelo"` (*"Artefato ... não encontrado"* ou *"não possui implementação disponível"*).
- **Causa**: O modelo vinculado à credencial não possui arquivo `.joblib` compatível em `backend/artifacts/`, ou as versões de `scikit-learn`/`joblib` diferem de `backend/requirements.txt`. O pipeline **nunca substitui silenciosamente** por outro modelo nem treina automaticamente em produção.
- **Solução**:
  1. Instale `pip install -r backend/requirements.txt`.
  2. Para gerar o artefato padrão localmente em `backend/`, execute:
     ```bash
     python -m app.integrations.prediction.treinar_modelo_risco
     ```
  3. Valide com `python -m app.integrations.prediction.pipeline.executor --check-model`.

---

## 5. Versão de modelo divergente (`HTTP 422`)

- **Sintoma**: `ErroEnvioValidacao` informando *"Versão de modelo divergente da versão registrada"*.
- **Causa**: O artefato carregado possui `versao_modelo` diferente da versão registrada no catálogo central para o modelo autorizado. Reinstale as dependências e garanta que o artefato `.joblib` corresponde à versão esperada (`--check-model`).

---

## 6. Variáveis obrigatórias ausentes ou Data Leakage (`transformador.py`)

- **Sintoma**: `rejeitados_transformacao > 0` (`nota_t1_ausente` / `contexto_minimo_ausente`) ou `ErroTransformacaoLeakage`.
- **Causa**: Estudantes sem nota lançada no 1º período não recebem previsão artificial (sem imputação inventada). Períodos posteriores (`2º Bimestre`, `Final`) e campos pós-corte (`situacao_final`, `nota_t2`, `g2`, `nota_t3`, `g3`, `media_geral`, `faltas`, `frequencia_percentual`, PII) são bloqueados imediatamente.

---

## 7. Conflitos de idempotência (`HTTP 409`), timeout ou lote rejeitado (`HTTP 422`)

- **Timeout / Rede (`ErroExtracaoComunicacao` / `ErroEnvioComunicacao`)**: confirme `VERTICE_API_URL` (`GET /health`) e ajuste `VERTICE_ML_HTTP_TIMEOUT` / `VERTICE_ML_BATCH_SIZE`.
- **Conflito `409 Conflict`**: tentativa de reenviar exatamente o mesmo lote/assinatura append-only; confirme em `GET /api/v1/previsoes` antes de disparar nova execução.

---

## 8. Nenhuma previsão exibida ou filtros divergentes no painel Visão Geral

- Confirme que rodou com `--send` (não apenas `--dry-run`) e que `persistidos > 0`.
- Verifique se o filtro de **Turma**, **Disciplina**, **Ano letivo** ou **Período letivo** na **Visão geral** corresponde ao recorte processado (ex.: `1º Bimestre`); recortes sem previsões exibem normalmente a mensagem orientativa padrão.
