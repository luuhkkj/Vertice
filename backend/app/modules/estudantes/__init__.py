"""
Módulo de Gestão de Estudantes Anonimizados e Histórico Escolar.

Componentes implementados:
- router.py: endpoints de listagem paginada (`X-Total-Count`) e detalhamento individual
- schemas.py: contratos anonimizados de Estudante, BoletimPeriodo e NotaDisciplina (sem PII)
- models.py: modelos ORM Estudante, BoletimPeriodo, NotaDisciplina e SituacaoFinalPeriodo
- service.py: filtros e isolamento por escola, turma, disciplina e período letivo
- repository.py: consultas otimizadas por vínculo escolar/turma e histórico longitudinal
"""
