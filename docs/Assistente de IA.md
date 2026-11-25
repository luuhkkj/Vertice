Assistente de IA do Vértice

1. O que mudou no projeto

1.1. Assistente de IA

Foi implementada a integração com o Ollama local, permitindo a utilização de modelos de inteligência artificial sem depender de provedores externos.

As principais alterações incluem:

Integração com contexto autorizado e auditado.

Geração de respostas e envio de anexos.

Melhorias na interface e no tratamento de timeouts e erros.

Atualizações nos arquivos assistente_ia.py, api_client.py e assistente_ia.css.

Ampliação dos contratos e das rotas do backend.

Criação dos módulos documents.py e ollama.py, responsáveis pela extração de documentos e pela integração local com o modelo de IA.

1.2. Predição de risco

Foi desenvolvida uma estrutura de treinamento e comparação de modelos para predição de risco, contemplando:

Treinamento de um modelo baseline.

Treinamento de Regressão Logística.

Treinamento de Random Forest.

Comparação de métricas de desempenho.

Implementação de uma função de inferência.

Prevenção de vazamento temporal (data leakage).

A implementação está concentrada nos arquivos treinar_modelo_risco.py e modelo_risco.py.

Importante: Conforme documentado em RELATORIO_MODELO_RISCO.md, os rótulos utilizados são derivados de uma base pública e não representam uma validação de risco real dos estudantes do Vértice.

1.3. Configuração e documentação

Foram realizadas atualizações na infraestrutura e na documentação do projeto, incluindo:

Atualização do docker-compose.yml.

Atualização das dependências.

Revisão dos contratos da API.

Atualização dos arquivos README.

Revisão dos documentos de arquitetura, instalação e manutenção.

1.4. Testes

Foram adicionados novos testes para garantir o funcionamento das funcionalidades implementadas, incluindo:

Testes de anexos.

Testes de integração com o Ollama.

Testes do modelo de predição de risco.

Atualizações nos testes de integração existentes.

2. Como habilitar o Assistente de IA local

Esta seção apresenta os procedimentos necessários para configurar e executar o Assistente de IA utilizando o Ollama localmente por meio do Docker.

2.1. Pré-requisitos

Antes de iniciar a configuração, verifique se o ambiente atende aos seguintes requisitos:

Docker Desktop instalado e em execução, com Docker Compose disponível.

Conexão com a internet para baixar as imagens Docker e o modelo durante a primeira instalação.

Espaço em disco suficiente para armazenar o modelo qwen2.5:3b (aproximadamente 1,9 GB no ambiente verificado).

Memória RAM suficiente para carregar o modelo.

Observações sobre desempenho:

O modelo funciona utilizando CPU, porém as respostas podem ser mais lentas. No ambiente testado, o Ollama utilizou aproximadamente 4,2 GB de memória durante a inferência.

Não é necessário instalar o Ollama nativamente nem configurar uma chave de API ao utilizar o perfil Docker apresentado neste documento.

2.2. Configurar o arquivo .env da raiz

Caso o arquivo .env ainda não exista, copie o arquivo .env.example para .env, na raiz do projeto.

Também é necessário preencher as configurações obrigatórias do banco de dados e definir a SECRET_KEY, conforme as instruções disponíveis no próprio template.

Em seguida, altere e mantenha as seguintes configurações para a execução via Docker Compose:

# Provedor de IA
ASSISTENTE_LLM_PROVEDOR=ollama

# Configurações do Ollama no Docker Compose
ASSISTENTE_OLLAMA_BASE_URL=http://ollama:11434
ASSISTENTE_OLLAMA_MODELO=qwen2.5:3b


Atenção: Não envie o arquivo .env real para o GitHub, pois ele pode conter informações sensíveis. Apenas o arquivo .env.example, sem segredos ou credenciais, deve ser versionado.

2.3. Iniciar os serviços

Com as configurações concluídas, abra o terminal na raiz do projeto e execute o seguinte comando:

docker compose --profile assistente-local up -d --build


Esse comando inicia os serviços necessários, incluindo o Ollama, por meio do perfil assistente-local.

O parâmetro --build recompila os serviços da aplicação utilizando o código local atualizado.

2.4. Baixar o modelo de IA

Após iniciar os serviços, execute o comando abaixo para baixar o modelo utilizado pelo assistente:

docker compose --profile assistente-local exec ollama ollama pull qwen2.5:3b


O modelo será armazenado no volume Docker do Ollama, portanto não será necessário baixá-lo novamente a cada inicialização.

2.5. Verificar a instalação

Após concluir o download, é importante verificar se os serviços estão funcionando corretamente.

Verificar o estado dos containers:

docker compose --profile assistente-local ps


Verificar se o modelo foi instalado:

docker compose --profile assistente-local exec ollama ollama list


Se os serviços estiverem funcionando corretamente:

API (Health Check): http://localhost:8000/health

Interface do sistema Vértice: http://localhost:8501

3. Observações importantes

O Ollama e o modelo de inteligência artificial são executados localmente por meio do Docker. Portanto, não é necessária uma conta ou chave de API de um provedor externo.

A primeira resposta do assistente pode demorar um pouco mais devido ao carregamento inicial do modelo na memória.

Em ambientes que utilizam CPU, perguntas mais objetivas tendem a apresentar respostas mais rápidas.

O assistente permite o envio de anexos nos formatos PDF, DOCX, TXT, CSV e XLSX, respeitando os limites definidos pela aplicação.

Arquivos PDF digitalizados, que não possuem texto selecionável, não são processados por OCR.

Privacidade: Não envie documentos que contenham nomes, números de matrícula ou outros dados pessoais identificáveis.

Revisão humana: As respostas geradas pelo modelo devem ser revisadas por um profissional, pois não representam decisões pedagógicas automáticas.

3.1. Solução de problemas

Caso o assistente apresente erros de configuração ou timeout, recomenda-se verificar:

Se a variável ASSISTENTE_LLM_PROVEDOR está definida corretamente como ollama.

Se os containers estão em execução.

Se o modelo foi baixado e está disponível.

Se os logs dos serviços apresentam algum erro.

Para consultar os logs dos serviços backend e ollama, execute:

docker compose --profile assistente-local logs --tail 100 backend ollama


Após identificar e corrigir possíveis problemas, tente acessar novamente a interface do sistema.