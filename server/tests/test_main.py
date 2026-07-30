import io
import pytest
from fastapi.testclient import TestClient
import app.main as main


@pytest.fixture(autouse=True)
def _no_vram_ops(monkeypatch):
    # Neutraliza efectos de infraestructura VRAM en los tests unitarios
    monkeypatch.setattr(main, "unload_ollama_model", lambda: True)
    monkeypatch.setattr(main, "free_torch_cache", lambda: None)
    # Evita importar torch para decidir si hay que liberar VRAM: los tests no
    # deben depender de que la maquina tenga GPU.
    monkeypatch.setattr(main, "whisper_uses_cuda", lambda: True)
    # Por defecto sin diarización (Fase 1/2); los tests que la prueban lo sobreescriben
    monkeypatch.setattr(main, "diarize", lambda p, **kw: [])


def test_health_ok():
    client = TestClient(main.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_transcribe_returns_markdown(monkeypatch):
    from app.models import Segment

    def fake_transcribe(path):
        return ([Segment(0.0, 1.0, "hola")], 1.0)

    monkeypatch.setattr(main, "transcribe", fake_transcribe)
    monkeypatch.setattr(
        main, "archive_audio", lambda src, title, date: "/mnt/actas/audio/x.wav"
    )
    monkeypatch.setattr(main, "summarize", lambda t: (None, False))

    client = TestClient(main.app)
    files = {"audio": ("test.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    data = {"title": "Prueba"}
    r = client.post("/transcribe", files=files, data=data)
    assert r.status_code == 200
    body = r.json()
    assert "markdown" in body
    assert "hola" in body["markdown"]
    assert body["filename"].startswith("Acta ")


def test_transcribe_includes_summary(monkeypatch):
    from app.models import Segment

    monkeypatch.setattr(main, "transcribe", lambda p: ([Segment(0.0, 1.0, "hola")], 1.0))
    monkeypatch.setattr(main, "archive_audio", lambda s, t, d: "/x.wav")
    monkeypatch.setattr(main, "summarize", lambda t: ("## Resumen\nok", True))

    client = TestClient(main.app)
    files = {"audio": ("t.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    r = client.post("/transcribe", files=files, data={"title": "X"})
    assert "## Resumen" in r.json()["markdown"]


def test_transcribe_pending_summary(monkeypatch):
    from app.models import Segment

    monkeypatch.setattr(main, "transcribe", lambda p: ([Segment(0.0, 1.0, "hola")], 1.0))
    monkeypatch.setattr(main, "archive_audio", lambda s, t, d: "/x.wav")
    monkeypatch.setattr(main, "summarize", lambda t: (None, False))

    client = TestClient(main.app)
    files = {"audio": ("t.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    r = client.post("/transcribe", files=files, data={"title": "X"})
    assert "resumen: pendiente" in r.json()["markdown"]


def test_empty_transcription_skips_summary(monkeypatch):
    # Si Whisper no detecta habla, NO se debe llamar a summarize (evita alucinaciones)
    from app.models import Segment

    called = {"summarize": False}

    def _summarize_spy(t):
        called["summarize"] = True
        return ("## Resumen\ninventado", True)

    monkeypatch.setattr(main, "transcribe", lambda p: ([], 10.0))
    monkeypatch.setattr(main, "archive_audio", lambda s, t, d: "/x.wav")
    monkeypatch.setattr(main, "summarize", _summarize_spy)

    client = TestClient(main.app)
    files = {"audio": ("t.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    r = client.post("/transcribe", files=files, data={"title": "X"})
    md = r.json()["markdown"]
    assert called["summarize"] is False
    assert "transcripcion: vacia" in md
    assert "## Resumen" not in md


def test_no_descarga_ollama_si_whisper_va_en_cpu(monkeypatch):
    # En CPU no hay competencia por VRAM: descargar el LLM solo forzaria una
    # recarga completa al resumir.
    from app.models import Segment

    llamado = {"unload": False}

    def _unload_spy():
        llamado["unload"] = True
        return True

    monkeypatch.setattr(main, "unload_ollama_model", _unload_spy)
    monkeypatch.setattr(main, "whisper_uses_cuda", lambda: False)
    monkeypatch.setattr(main, "transcribe", lambda p: ([Segment(0.0, 1.0, "hola")], 1.0))
    monkeypatch.setattr(main, "archive_audio", lambda s, t, d: "/x.wav")
    monkeypatch.setattr(main, "summarize", lambda t: (None, False))

    client = TestClient(main.app)
    files = {"audio": ("t.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    r = client.post("/transcribe", files=files, data={"title": "X"})
    assert r.status_code == 200
    assert llamado["unload"] is False


def test_descarga_ollama_si_whisper_va_en_gpu(monkeypatch):
    from app.models import Segment

    llamado = {"unload": False}

    def _unload_spy():
        llamado["unload"] = True
        return True

    monkeypatch.setattr(main, "unload_ollama_model", _unload_spy)
    monkeypatch.setattr(main, "whisper_uses_cuda", lambda: True)
    monkeypatch.setattr(main, "transcribe", lambda p: ([Segment(0.0, 1.0, "hola")], 1.0))
    monkeypatch.setattr(main, "archive_audio", lambda s, t, d: "/x.wav")
    monkeypatch.setattr(main, "summarize", lambda t: (None, False))

    client = TestClient(main.app)
    files = {"audio": ("t.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    client.post("/transcribe", files=files, data={"title": "X"})
    assert llamado["unload"] is True


def test_titulo_hostil_no_escapa_del_directorio_temporal(monkeypatch, tmp_path):
    # El titulo llega del usuario y se usa como nombre de archivo temporal.
    from app.models import Segment

    monkeypatch.setattr(main.config, "tmp_dir", str(tmp_path))
    monkeypatch.setattr(main, "transcribe", lambda p: ([Segment(0.0, 1.0, "hola")], 1.0))
    monkeypatch.setattr(main, "archive_audio", lambda s, t, d: "/x.wav")
    monkeypatch.setattr(main, "summarize", lambda t: (None, False))

    client = TestClient(main.app)
    files = {"audio": ("t.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    r = client.post("/transcribe", files=files, data={"title": "../../pwned"})

    assert r.status_code == 200
    # Nada escrito fuera de tmp_path
    assert not (tmp_path.parent / "pwned.src").exists()
    # Y el nombre devuelto tampoco puede sacar al cliente de su carpeta de actas
    filename = r.json()["filename"]
    assert "/" not in filename
    assert "\\" not in filename
    assert ".." not in filename


def test_filename_devuelto_es_valido_en_windows(monkeypatch):
    # El cliente escribe la nota con este nombre; ':' la haria fallar en Windows.
    from app.models import Segment

    monkeypatch.setattr(main, "transcribe", lambda p: ([Segment(0.0, 1.0, "hola")], 1.0))
    monkeypatch.setattr(main, "archive_audio", lambda s, t, d: "/x.wav")
    monkeypatch.setattr(main, "summarize", lambda t: (None, False))

    client = TestClient(main.app)
    files = {"audio": ("t.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    r = client.post("/transcribe", files=files, data={"title": "Daily: 10:30"})

    filename = r.json()["filename"]
    assert filename.endswith(".md")
    for ch in '<>:"/\\|?*':
        assert ch not in filename


def test_health_deep_reporta_checks(monkeypatch):
    monkeypatch.setattr(main, "pipeline_status", lambda: (True, {"torch": True}))
    monkeypatch.setattr(main, "ollama_status", lambda: (False, {"reachable": False}))

    client = TestClient(main.app)
    r = client.get("/health", params={"deep": 1})
    body = r.json()

    assert r.status_code == 200
    assert body["status"] == "degraded"
    assert body["checks"]["pipeline"]["torch"] is True
    assert body["checks"]["ollama"]["reachable"] is False


def test_health_barato_no_ejercita_el_pipeline(monkeypatch):
    # El cliente lo usa para elegir servidor: debe ser barato y no importar nada.
    def _boom():
        raise AssertionError("/health sin deep no debe comprobar el pipeline")

    monkeypatch.setattr(main, "pipeline_status", _boom)
    monkeypatch.setattr(main, "ollama_status", _boom)

    client = TestClient(main.app)
    assert client.get("/health").json() == {"status": "ok"}


def test_transcribe_with_diarization(monkeypatch):
    from app.models import Segment, SpeakerTurn

    monkeypatch.setattr(
        main,
        "transcribe",
        lambda p: ([Segment(0.0, 1.0, "hola"), Segment(2.5, 3.0, "chau")], 3.0),
    )
    monkeypatch.setattr(main, "archive_audio", lambda s, t, d: "/x.wav")
    monkeypatch.setattr(main, "summarize", lambda t: ("## Resumen\nok", True))
    monkeypatch.setattr(
        main,
        "diarize",
        lambda p, **kw: [
            SpeakerTurn(0.0, 2.0, "Hablante 1"),
            SpeakerTurn(2.0, 4.0, "Hablante 2"),
        ],
    )

    client = TestClient(main.app)
    files = {"audio": ("t.wav", io.BytesIO(b"RIFF" + b"0" * 2000), "audio/wav")}
    r = client.post("/transcribe", files=files, data={"title": "X"})
    md = r.json()["markdown"]
    assert "[Hablante 1]" in md
    assert "[Hablante 2]" in md
    assert "hablantes: 2" in md
