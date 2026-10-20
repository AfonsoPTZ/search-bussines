"""Configuração dos testes. TODOS os perfis usados nos testes são DADOS DE TESTE FICTÍCIOS (prefixo 'teste_')."""

import pytest

from prospeccao import config


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTADOS_DIR", tmp_path / "resultados")
    monkeypatch.setattr(config, "DADOS_USUARIO_DIR", tmp_path / "dados")
    monkeypatch.setattr(config, "SESSAO_ARQ", tmp_path / "dados" / "sessao.bin")
    monkeypatch.delenv("PROSPECCAO_SESSIONID", raising=False)
    monkeypatch.delenv("PROSPECCAO_TRIAGEM", raising=False)
    monkeypatch.setenv("PROSPECCAO_TRIAGEM", str(tmp_path / "sem_triagem.json"))  # testes nunca leem o triagem.json real
    return tmp_path
