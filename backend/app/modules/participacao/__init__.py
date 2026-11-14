"""
Módulo de Participação, Atividades e Entregas Escolares.

Componentes implementados:
- router.py: cadastro de atividades, geração de entregas esperadas e registro/edição de entregas
- schemas.py: contratos de Atividade, EntregaAtividade e consolidação de pendências/não entregas
- models.py: modelos ORM Atividade, EntregaAtividade, StatusAtividade e StatusEntregaAtividade
- service.py: regras de cálculo de entrega no prazo, atraso, pendência e não entrega após prazo
- repository.py: consultas de atividades e entregas por turma, disciplina, estudante e período
"""
