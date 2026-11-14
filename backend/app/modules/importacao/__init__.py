"""
Módulo de Importação em Duas Etapas de Planilhas e Dados Escolares (LGPD).

Componentes implementados:
- router.py: histórico de lotes, download de modelos (CSV/XLSX), validar, prévia, confirmar e descartar
- schemas.py: contratos de prévia, relatório de validação e resumo/confirmação de lotes
- models.py: modelo ORM LoteImportacao, enums TipoImportacao e StatusLoteImportacao
- validator.py: parser CSV/XLSX, detecção anti-PII, checagem de escopo e geração de modelos oficiais
- service.py: fluxo atômico validar -> confirmar (rollback integral em falhas) para dados escolares, avaliações e atividades
- repository.py: consultas de histórico de lotes por escola ou usuário
"""
