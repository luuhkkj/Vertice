"""
Módulo de Acompanhamento Pedagógico e Planos de Ação.

Componentes implementados:
- router.py: registro, consulta e atualização de acompanhamentos com escopo por papel/vínculo
- schemas.py: contratos de criação, alteração e resposta com histórico estruturado
- models.py: modelo ORM AcompanhamentoPedagogico e enum OrigemAcompanhamento
- service.py: validação de vínculo turma/disciplina/escola e trilha `historico_alteracoes`
- repository.py: consultas filtradas por escola, turma, estudante e origem
"""
