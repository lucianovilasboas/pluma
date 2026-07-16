from __future__ import annotations

from unittest.mock import patch

from apps.avaliacoes import tasks


def test_disparar_noop_sob_pytest(monkeypatch):
    """Com PYTEST_CURRENT_TEST setado, disparar deve ser no-op (nem fila nem inline)."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "sim")
    monkeypatch.setenv("AVALIACAO_USE_Q2", "true")
    with patch.object(tasks, "agendar_avaliacao_llm") as m_fila, \
         patch.object(tasks, "executar_avaliacao_imediata") as m_inline:
        tasks.disparar_avaliacao_llm("rid", "pid", "um")
    m_fila.assert_not_called()
    m_inline.assert_not_called()


def test_disparar_usa_fila_quando_q2_true(monkeypatch):
    """AVALIACAO_USE_Q2=true → roteia para a fila (agendar), nunca inline."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("AVALIACAO_USE_Q2", "true")
    with patch.object(tasks, "agendar_avaliacao_llm") as m_fila, \
         patch.object(tasks, "executar_avaliacao_imediata") as m_inline:
        tasks.disparar_avaliacao_llm("rid", "pid", "tres", ["c1"])
    m_fila.assert_called_once_with("rid", "pid", "tres", ["c1"])
    m_inline.assert_not_called()


def test_disparar_usa_inline_quando_q2_false(monkeypatch):
    """AVALIACAO_USE_Q2=false → roteia inline (imediata), nunca fila."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("AVALIACAO_USE_Q2", "false")
    with patch.object(tasks, "agendar_avaliacao_llm") as m_fila, \
         patch.object(tasks, "executar_avaliacao_imediata") as m_inline:
        tasks.disparar_avaliacao_llm("rid", None, "um")
    m_inline.assert_called_once_with("rid", None, "um", None)
    m_fila.assert_not_called()


def test_disparar_default_e_inline_quando_env_ausente(monkeypatch):
    """Sem a env var, o default é inline (comportamento de dev)."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("AVALIACAO_USE_Q2", raising=False)
    with patch.object(tasks, "agendar_avaliacao_llm") as m_fila, \
         patch.object(tasks, "executar_avaliacao_imediata") as m_inline:
        tasks.disparar_avaliacao_llm("rid")
    m_inline.assert_called_once()
    m_fila.assert_not_called()


def test_variantes_truthy_da_flag_roteiam_para_fila(monkeypatch):
    """1/true/yes (case-insensitive) todos ativam a fila."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    for valor in ["true", "TRUE", "True", "1", "yes", "YES"]:
        monkeypatch.setenv("AVALIACAO_USE_Q2", valor)
        with patch.object(tasks, "agendar_avaliacao_llm") as m_fila, \
             patch.object(tasks, "executar_avaliacao_imediata") as m_inline:
            tasks.disparar_avaliacao_llm("rid", "pid")
        assert m_fila.call_count == 1, f"valor {valor!r} deveria usar fila"
        assert m_inline.call_count == 0, f"valor {valor!r} não deveria usar inline"


def test_variantes_falsy_da_flag_roteiam_inline(monkeypatch):
    """Valores não reconhecidos como truthy caem em inline."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    for valor in ["false", "0", "no", "", "off", "nao"]:
        monkeypatch.setenv("AVALIACAO_USE_Q2", valor)
        with patch.object(tasks, "agendar_avaliacao_llm") as m_fila, \
             patch.object(tasks, "executar_avaliacao_imediata") as m_inline:
            tasks.disparar_avaliacao_llm("rid", "pid")
        assert m_inline.call_count == 1, f"valor {valor!r} deveria usar inline"
        assert m_fila.call_count == 0, f"valor {valor!r} não deveria usar fila"


def test_agendar_envia_async_task_com_path_e_args_corretos():
    """agendar_avaliacao_llm deve enfileirar o job com o caminho e args exatos."""
    with patch.object(tasks, "async_task") as m_async:
        tasks.agendar_avaliacao_llm("rid", "pid", "tres", ["c1", "c2"])
    m_async.assert_called_once_with(
        "apps.avaliacoes.tasks._executar_avaliacao_job",
        "rid", "pid", "tres", ["c1", "c2"],
    )


def test_imediata_sob_pytest_roda_job_sincrono(monkeypatch):
    """Sob PYTEST_CURRENT_TEST, imediata executa o job sincronamente (sem thread)."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "sim")
    with patch.object(tasks, "_executar_avaliacao_job") as m_job, \
         patch.object(tasks.threading, "Thread") as m_thread:
        tasks.executar_avaliacao_imediata("rid", "pid", "um", None)
    m_job.assert_called_once_with("rid", "pid", "um", None)
    m_thread.assert_not_called()


def test_imediata_fora_do_pytest_usa_thread(monkeypatch):
    """Fora do pytest, imediata dispara uma thread daemon."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with patch.object(tasks, "_executar_avaliacao_job"), \
         patch.object(tasks.threading, "Thread") as m_thread:
        tasks.executar_avaliacao_imediata("rid", "pid", "um", None)
    m_thread.assert_called_once()
    _, kwargs = m_thread.call_args
    assert kwargs.get("daemon") is True
    m_thread.return_value.start.assert_called_once()
