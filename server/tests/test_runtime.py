import app.runtime as runtime
from app.config import config


def test_auto_resuelve_a_cuda_si_hay_gpu(monkeypatch):
    monkeypatch.setattr(config, "whisper_device", "auto")
    monkeypatch.setattr(config, "whisper_compute", "auto")
    monkeypatch.setattr(runtime, "cuda_available", lambda: True)
    assert runtime.resolve_device_compute() == ("cuda", "float16")


def test_auto_resuelve_a_cpu_sin_gpu(monkeypatch):
    # En CPU el compute debe caer a int8: float16 no esta soportado y CTranslate2
    # degradaria de forma silenciosa.
    monkeypatch.setattr(config, "whisper_device", "auto")
    monkeypatch.setattr(config, "whisper_compute", "auto")
    monkeypatch.setattr(runtime, "cuda_available", lambda: False)
    assert runtime.resolve_device_compute() == ("cpu", "int8")


def test_valor_explicito_manda_sobre_la_deteccion(monkeypatch):
    monkeypatch.setattr(config, "whisper_device", "cpu")
    monkeypatch.setattr(config, "whisper_compute", "float32")
    monkeypatch.setattr(runtime, "cuda_available", lambda: True)
    assert runtime.resolve_device_compute() == ("cpu", "float32")


def test_device_explicito_con_compute_auto(monkeypatch):
    monkeypatch.setattr(config, "whisper_device", "cuda")
    monkeypatch.setattr(config, "whisper_compute", "auto")
    monkeypatch.setattr(runtime, "cuda_available", lambda: False)
    assert runtime.resolve_device_compute() == ("cuda", "float16")


def test_whisper_uses_cuda(monkeypatch):
    monkeypatch.setattr(config, "whisper_device", "auto")
    monkeypatch.setattr(config, "whisper_compute", "auto")

    monkeypatch.setattr(runtime, "cuda_available", lambda: False)
    assert runtime.whisper_uses_cuda() is False

    monkeypatch.setattr(runtime, "cuda_available", lambda: True)
    assert runtime.whisper_uses_cuda() is True


def test_ollama_status_no_alcanzable(monkeypatch):
    monkeypatch.setattr(config, "ollama_url", "http://127.0.0.1:1")
    ready, detail = runtime.ollama_status()
    assert ready is False
    assert detail["reachable"] is False
    assert "error" in detail


def test_ollama_status_sin_el_modelo(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"models": [{"name": "otro-modelo:1b"}]}

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            return _Resp()

    import httpx

    monkeypatch.setattr(httpx, "Client", _Client)
    monkeypatch.setattr(config, "ollama_model", "gemma4:12b-it-qat")

    ready, detail = runtime.ollama_status()
    assert ready is False
    assert detail["reachable"] is True
    assert detail["model_present"] is False
