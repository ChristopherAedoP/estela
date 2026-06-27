import app.vram as vram


def test_unload_ollama_calls_endpoint(monkeypatch):
    called = {}

    def fake_post(url, json, timeout):
        called["url"] = url
        called["json"] = json

        class R:
            def raise_for_status(self):
                pass

        return R()

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, url, json, timeout):
            return fake_post(url, json, timeout)

    monkeypatch.setattr(vram.httpx, "Client", FakeClient)
    ok = vram.unload_ollama_model()
    assert ok is True
    assert called["json"]["keep_alive"] == 0
    assert "generate" in called["url"]


def test_unload_ollama_swallows_errors(monkeypatch):
    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, *a, **k):
            raise RuntimeError("ollama down")

    monkeypatch.setattr(vram.httpx, "Client", FakeClient)
    # No debe lanzar; devuelve False
    assert vram.unload_ollama_model() is False
