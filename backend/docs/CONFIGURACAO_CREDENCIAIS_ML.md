# Configuração e Emissão Manual de Credenciais ML — Vértice

Este guia explica passo a passo como o **Administrador** emite manualmente uma única credencial técnica (`X-Service-Token`) na interface do Vértice e como configurá-la no ambiente do pipeline de Machine Learning.

> **Regra de segurança obrigatória:** a emissão e a revogação de credenciais ML são operações **exclusivamente manuais**, realizadas pelo Administrador. O pipeline nunca gera nem renova tokens automaticamente. Quando emitida com escola específica e modelo autorizado, a mesma credencial autoriza a extração controlada e o envio de previsões para essa escola e esse modelo.

---

## 1. Como acessar a tela de Credenciais ML

1. Acesse o frontend Streamlit do Vértice (`http://localhost:8501`).
2. Faça login com uma conta de perfil **`administrador`**.
3. No menu lateral esquerdo, selecione **Credenciais ML** (`/credenciais-ml`, em [administracao_tecnica.py](file:///c:/Users/Jessica/Documents/Projetos/Vértice/Vertice/Frontend%20vertice/pages/administracao_tecnica.py)).

---

## 2. Como selecionar a escola

No card **Emitir nova credencial ML**, no campo **Escola**, selecione a unidade escolar específica que será atendida pelo pipeline.

- A escola selecionada vincula o token exclusivamente aos estudantes e turmas dessa unidade.
- Por menor privilégio, selecione sempre a escola específica do pipeline (a opção global fica restrita a cenários legados de somente envio, sem permissão de extração).

---

## 3. Como selecionar o modelo de Machine Learning

No campo **Modelo de Machine Learning**, selecione diretamente na lista suspensa o modelo disponibilizado pelo backend (descoberto automaticamente em `GET /api/v1/previsoes/modelos-disponiveis`, como **Risco Acadêmico — Regressão Logística (1º Período)** / `regressao_logistica`).

Não é necessário digitar nomes técnicos ou vírgulas manualmente.

---

## 4. Como emitir a credencial

1. Preencha **Identificação do serviço** (ex.: `Pipeline Escola Norte`).
2. Confirme a **Escola** e o **Modelo de Machine Learning** selecionados.
3. Clique em **Emitir token técnico**.

---

## 5. Como copiar e armazenar o token

Logo após a emissão, a tela exibe o segredo gerado (`vtx_ml_...`) com o aviso:

> *"Copie o token de serviço ML abaixo agora. Por segurança, ele não será exibido novamente."*

- Copie o valor imediatamente para um cofre de segredos ou variável de ambiente local.
- O backend grava apenas o prefixo e o hash SHA-256 do token; após recarregar a página, o segredo completo não pode ser recuperado.
- Nunca cole tokens reais em arquivos versionados no Git.

---

## 6. Como configurar o token no ambiente do pipeline

No ambiente onde o pipeline será executado (`.env` local ou variáveis de sessão), informe apenas:

```env
VERTICE_API_URL=http://127.0.0.1:8000
VERTICE_ML_SERVICE_TOKEN=vtx_ml_SEU_TOKEN
```

No Windows PowerShell (sessão atual):

```powershell
$env:VERTICE_API_URL = "http://127.0.0.1:8000"
$env:VERTICE_ML_SERVICE_TOKEN = "vtx_ml_SEU_TOKEN"
```

Não é necessário configurar uma segunda chave de exportação nem repetir `school_id` ou `modelo_nome` no `.env`: o pipeline descobre ambos automaticamente a partir da própria credencial autenticada na API.

---

## 7. Como testar a integração

A partir do diretório `backend/`:

1. Verifique URL, credencial e disponibilidade local do modelo associado ao token (sem expor o segredo):
   ```bash
   python -m app.integrations.prediction.pipeline.executor --check-config
   ```
2. Execute extração, transformação e inferência sem persistir previsões:
   ```bash
   python -m app.integrations.prediction.pipeline.executor --dry-run --json
   ```
3. Execute o fluxo completo enviando e persistindo as previsões na API:
   ```bash
   python -m app.integrations.prediction.pipeline.executor --send --json
   ```

Se precisar interromper o acesso desse pipeline, clique em **Revogar credencial selecionada** na mesma tela **Credenciais ML** — a revogação bloqueia imediatamente tanto a extração quanto o envio.
