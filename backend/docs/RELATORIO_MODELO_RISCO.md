# Relatório de avaliação do modelo de risco acadêmico

## Decisões e escopo

- **Previsão:** desfecho acadêmico desfavorável combinado (`Reprovado` ou `Evadido`) ao fim do ano.
- **Momento da previsão:** após o primeiro período letivo.
- **Variáveis de entrada:** idade, histórico de reprovações anterior e nota do primeiro período (`G1 / 2`).
- **Referência usada:** notebook `notebooks/dados_estudantes.ipynb`, que combina os arquivos públicos UCI de Matemática e Português.
- **Limitação fundamental:** o notebook não contém rótulo histórico observado de evasão. Ele cria `situacao_final` por regra a partir de frequência anual, nota do terceiro período e média final. Portanto, as métricas abaixo avaliam a capacidade de reproduzir esse **rótulo proxy**, não a capacidade validada de prever resultados reais dos estudantes do Vértice.

## Dados e corte temporal

- Registros: **1044** (Matemática: 395; Português: 649).
- `situacao_final` reproduzida do notebook: {"Aprovado": 722, "Reprovado": 266, "Evadido": 56}.
- Rótulo de risco combinado: {"aprovado": 722, "reprovado_ou_evadido": 322}.
- Features no modelo: `idade, historico_reprovacao, nota_t1`. `G2`, `G3`, `media_geral`, ausências/frequência anual e `situacao_final` não entram como preditores.
- Divisão agrupada: treino 626, validação 209, teste 209 registros. Os grupos são fingerprints de atributos estáveis porque o dataset não fornece um identificador real de aluno; isso reduz, mas não prova que elimina, contaminação entre disciplinas.
- Semente: 42 (partição de teste) e 43 (validação); imputação por mediana e transformações fazem parte dos pipelines.

## Modelos, parâmetros e validação

| Modelo | Parâmetros |
|---|---|
| Baseline | `DummyClassifier(strategy='most_frequent')` |
| Regressão logística | `C=1.0`, `class_weight='balanced'`, `solver='liblinear'`, `max_iter=2000`, `random_state=42`; mediana + padronização |
| Random Forest | `n_estimators=300`, `max_depth=6`, `min_samples_leaf=4`, `class_weight='balanced_subsample'`, `random_state=42`; mediana |

O modelo foi escolhido na validação pelo F1 macro. Se a regressão logística ficar até 0,020 abaixo do melhor F1 macro, ela é escolhida por ser mais interpretável. A calibração sigmoid é ajustada na validação; o teste fica separado. A seleção resultou em **regressao_logistica**.

### Validação (seleção do modelo)

| Modelo | Acurácia | Precisão macro | Revocação macro | F1 macro | Precisão risco | Revocação risco | F1 risco | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline (classe majoritária) | 0.689 | 0.344 | 0.500 | 0.408 | 0.000 | 0.000 | 0.000 | 0.311 |
| Regressão Logística | 0.933 | 0.925 | 0.918 | 0.921 | 0.905 | 0.877 | 0.891 | 0.057 |
| Random Forest | 0.933 | 0.925 | 0.918 | 0.921 | 0.905 | 0.877 | 0.891 | 0.061 |

### Teste agrupado (avaliação final)

| Modelo | Acurácia | Precisão macro | Revocação macro | F1 macro | Precisão risco | Revocação risco | F1 risco | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline (classe majoritária) | 0.694 | 0.347 | 0.500 | 0.410 | 0.000 | 0.000 | 0.000 | 0.306 |
| Regressão Logística | 0.914 | 0.918 | 0.877 | 0.894 | 0.926 | 0.781 | 0.847 | 0.068 |
| Random Forest | 0.909 | 0.905 | 0.878 | 0.890 | 0.895 | 0.797 | 0.843 | 0.065 |

No teste do modelo escolhido, matriz de confusão (linhas: real aprovado/risco; colunas: previsto aprovado/risco) é `[[141, 4], [14, 50]]`. Foram observados **4 falsos positivos** (acompanhamento sugerido para rótulo proxy aprovado) e **14 falsos negativos** (rótulo proxy desfavorável não identificado).

### Desempenho por classe

| Classe real | Precisão | Revocação | F1-score | Suporte |
|---|---:|---:|---:|---:|
| aprovado | 0.910 | 0.972 | 0.940 | 145 |
| reprovado_ou_evadido_proxy | 0.926 | 0.781 | 0.847 | 64 |

### Interpretação

Os coeficientes abaixo são da Regressão Logística, medidos por desvio-padrão após `StandardScaler`; indicam associação com o rótulo proxy, não causalidade. A escolha desse modelo mantém uma regra linear auditável e teve F1 macro de validação empatado com a Random Forest.

| Variável | Coeficiente logístico padronizado | Direção associativa |
|---|---:|---|
| idade | -0.137 | menor score do rótulo proxy |
| historico_reprovacao | 0.578 | maior score do rótulo proxy |
| nota_t1 | -4.571 | menor score do rótulo proxy |

### Probabilidade e faixas de acompanhamento

Brier score no teste: **0.068** (menor é melhor; 0 é perfeito). A calibração foi medida apenas contra o rótulo proxy derivado do notebook, não contra desfechos reais do Vértice.

| Faixa | Pontuação | Status sugerido | Estudantes no teste | Taxa observada do rótulo proxy |
|---|---|---|---:|---:|
| BAIXO | [0.000, 0.333) | Estável | 150 | 0.087 |
| MODERADO | [0.333, 0.667) | Atenção | 16 | 0.562 |
| ALTO | [0.667, 1.000] | Prioritário | 43 | 0.977 |

Os limites são divisões iniciais de um score calibrado em três partes iguais: baixo `< 0,333`, moderado `0,333–<0,667` e alto `>=0,667`. São critérios de triagem a validar com educadores e dados reais; não são decisões automáticas.

| Faixa | Status sugerido |
|---|---|
| Baixo | Estável |
| Moderado | Atenção |
| Alto | Prioritário |
| Sem previsão válida | Dados insuficientes |

## Limitações e uso responsável

1. A situação final do notebook é construída por regra e não distingue evasão observada de nota final zero/frequência anual baixa.
2. O identificador `ALU_...` do notebook é gerado pelo índice da linha, não é uma chave real. Grupos por fingerprint não substituem o identificador longitudinal correto.
3. O dataset público é pequeno e não representa necessariamente escolas, períodos ou critérios de aprovação do Vértice.
4. As features disponíveis no corte são limitadas; resultados não demonstram causalidade.
5. Ausência da nota do primeiro período ou de ambas as variáveis de contexto retorna **Sem previsão válida / Dados insuficientes**; não se imputa quando não existe o mínimo de informação.
6. A função e o artefato são uma prova de conceito. Antes de uso operacional, treine e avalie com desfechos históricos reais do Vértice, chave de estudante longitudinal e validação temporal externa.

Gerado em 2026-11-19T20:05:25.722436+00:00 com Python 3.14.5, scikit-learn 1.9.1 e pandas 3.1.1.
