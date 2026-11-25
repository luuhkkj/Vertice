"""
Pacote modular do pipeline automatizado de Machine Learning do Vértice.
Usa carregamento sob demanda (`__getattr__`) para evitar avisos `runpy` ao executar
submódulos via `python -m app.integrations.prediction.pipeline.<modulo>`.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.integrations.prediction.pipeline.agendador import (
        AgendadorPipelineML,
        BloqueioExecucaoSimultanea,
        ErroExecucaoSimultanea,
        RegistroCicloAgendador,
    )
    from app.integrations.prediction.pipeline.cliente_api import (
        LIMITE_ITENS_LOTE_API,
        ClienteAPIPrevisoes,
        ErroEnvioAutenticacao,
        ErroEnvioAutorizacao,
        ErroEnvioComunicacao,
        ErroEnvioConflitoIdempotencia,
        ErroEnvioPipeline,
        ErroEnvioValidacao,
        PrevisaoItemEnvio,
        PrevisaoLoteEnvio,
        ResultadoEnvioAPI,
    )
    from app.integrations.prediction.pipeline.config import (
        ErroConfiguracaoPipeline,
        PipelineMLConfig,
        mascarar_segredo,
        normalizar_api_v1_url,
        sanitizar_texto_segredos,
    )
    from app.integrations.prediction.pipeline.executor import (
        ErroArtefatoModelo,
        ErroInferenciaModelo,
        ExecutorPipelineML,
        InfoArtefatoModelo,
        RelatorioExecucaoPipeline,
        inspecionar_artefato_modelo,
    )
    from app.integrations.prediction.pipeline.extrator import (
        ErroExtracaoAutenticacao,
        ErroExtracaoAutorizacao,
        ErroExtracaoComunicacao,
        ErroExtracaoConfiguracao,
        ErroExtracaoPipeline,
        ErroExtracaoValidacao,
        ExtratorDadosInferencia,
        ResultadoExtracao,
    )
    from app.integrations.prediction.pipeline.transformador import (
        CAMPOS_POS_CORTE_BLOQUEADOS_PIPELINE,
        ErroTransformacaoLeakage,
        MotivoRejeicaoRegistro,
        RegistroInferenciaTransformado,
        ResultadoTransformacao,
        TransformadorDadosInferencia,
    )

_MAPA_EXPORTS: dict[str, tuple[str, str]] = {
    "AgendadorPipelineML": ("agendador", "AgendadorPipelineML"),
    "BloqueioExecucaoSimultanea": ("agendador", "BloqueioExecucaoSimultanea"),
    "ErroExecucaoSimultanea": ("agendador", "ErroExecucaoSimultanea"),
    "RegistroCicloAgendador": ("agendador", "RegistroCicloAgendador"),
    "LIMITE_ITENS_LOTE_API": ("cliente_api", "LIMITE_ITENS_LOTE_API"),
    "ClienteAPIPrevisoes": ("cliente_api", "ClienteAPIPrevisoes"),
    "ErroEnvioAutenticacao": ("cliente_api", "ErroEnvioAutenticacao"),
    "ErroEnvioAutorizacao": ("cliente_api", "ErroEnvioAutorizacao"),
    "ErroEnvioComunicacao": ("cliente_api", "ErroEnvioComunicacao"),
    "ErroEnvioConflitoIdempotencia": ("cliente_api", "ErroEnvioConflitoIdempotencia"),
    "ErroEnvioPipeline": ("cliente_api", "ErroEnvioPipeline"),
    "ErroEnvioValidacao": ("cliente_api", "ErroEnvioValidacao"),
    "PrevisaoItemEnvio": ("cliente_api", "PrevisaoItemEnvio"),
    "PrevisaoLoteEnvio": ("cliente_api", "PrevisaoLoteEnvio"),
    "ResultadoEnvioAPI": ("cliente_api", "ResultadoEnvioAPI"),
    "ErroConfiguracaoPipeline": ("config", "ErroConfiguracaoPipeline"),
    "PipelineMLConfig": ("config", "PipelineMLConfig"),
    "mascarar_segredo": ("config", "mascarar_segredo"),
    "normalizar_api_v1_url": ("config", "normalizar_api_v1_url"),
    "sanitizar_texto_segredos": ("config", "sanitizar_texto_segredos"),
    "ErroArtefatoModelo": ("executor", "ErroArtefatoModelo"),
    "ErroInferenciaModelo": ("executor", "ErroInferenciaModelo"),
    "ExecutorPipelineML": ("executor", "ExecutorPipelineML"),
    "InfoArtefatoModelo": ("executor", "InfoArtefatoModelo"),
    "RelatorioExecucaoPipeline": ("executor", "RelatorioExecucaoPipeline"),
    "inspecionar_artefato_modelo": ("executor", "inspecionar_artefato_modelo"),
    "ErroExtracaoAutenticacao": ("extrator", "ErroExtracaoAutenticacao"),
    "ErroExtracaoAutorizacao": ("extrator", "ErroExtracaoAutorizacao"),
    "ErroExtracaoComunicacao": ("extrator", "ErroExtracaoComunicacao"),
    "ErroExtracaoConfiguracao": ("extrator", "ErroExtracaoConfiguracao"),
    "ErroExtracaoPipeline": ("extrator", "ErroExtracaoPipeline"),
    "ErroExtracaoValidacao": ("extrator", "ErroExtracaoValidacao"),
    "ExtratorDadosInferencia": ("extrator", "ExtratorDadosInferencia"),
    "ResultadoExtracao": ("extrator", "ResultadoExtracao"),
    "CAMPOS_POS_CORTE_BLOQUEADOS_PIPELINE": ("transformador", "CAMPOS_POS_CORTE_BLOQUEADOS_PIPELINE"),
    "ErroTransformacaoLeakage": ("transformador", "ErroTransformacaoLeakage"),
    "MotivoRejeicaoRegistro": ("transformador", "MotivoRejeicaoRegistro"),
    "RegistroInferenciaTransformado": ("transformador", "RegistroInferenciaTransformado"),
    "ResultadoTransformacao": ("transformador", "ResultadoTransformacao"),
    "TransformadorDadosInferencia": ("transformador", "TransformadorDadosInferencia"),
}


def __getattr__(name: str) -> Any:
    if name in _MAPA_EXPORTS:
        import importlib

        submodulo_nome, attr_nome = _MAPA_EXPORTS[name]
        mod = importlib.import_module(
            f"app.integrations.prediction.pipeline.{submodulo_nome}"
        )
        return getattr(mod, attr_nome)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgendadorPipelineML",
    "BloqueioExecucaoSimultanea",
    "CAMPOS_POS_CORTE_BLOQUEADOS_PIPELINE",
    "ClienteAPIPrevisoes",
    "ErroArtefatoModelo",
    "ErroConfiguracaoPipeline",
    "ErroEnvioAutenticacao",
    "ErroEnvioAutorizacao",
    "ErroEnvioComunicacao",
    "ErroEnvioConflitoIdempotencia",
    "ErroEnvioPipeline",
    "ErroEnvioValidacao",
    "ErroExecucaoSimultanea",
    "ErroExtracaoAutenticacao",
    "ErroExtracaoAutorizacao",
    "ErroExtracaoComunicacao",
    "ErroExtracaoConfiguracao",
    "ErroExtracaoPipeline",
    "ErroExtracaoValidacao",
    "ErroInferenciaModelo",
    "ErroTransformacaoLeakage",
    "ExecutorPipelineML",
    "ExtratorDadosInferencia",
    "InfoArtefatoModelo",
    "LIMITE_ITENS_LOTE_API",
    "MotivoRejeicaoRegistro",
    "PipelineMLConfig",
    "PrevisaoItemEnvio",
    "PrevisaoLoteEnvio",
    "RegistroCicloAgendador",
    "RegistroInferenciaTransformado",
    "RelatorioExecucaoPipeline",
    "ResultadoEnvioAPI",
    "ResultadoExtracao",
    "ResultadoTransformacao",
    "TransformadorDadosInferencia",
    "inspecionar_artefato_modelo",
    "mascarar_segredo",
    "normalizar_api_v1_url",
    "sanitizar_texto_segredos",
]
