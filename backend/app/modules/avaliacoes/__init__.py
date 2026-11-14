"""
Módulo de Avaliações, Questões e Respostas Individuais.

Componentes implementados:
- router.py: endpoints de cadastro e consulta de avaliações, questões e respostas
- schemas.py: contratos de avaliações, itens (questões) e respostas (incluindo alternativa marcada)
- models.py: modelos ORM Avaliacao, QuestaoAvaliacao e RespostaAvaliacao
- service.py: validação de gabarito, correção automática/aberta e controle de escopo pedagógico
- repository.py: consultas de avaliações, itens e respostas por turma/disciplina/estudante
"""
