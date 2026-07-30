from app.naming import safe_note_name, slugify


def test_slugify_quita_caracteres_prohibidos_en_windows():
    assert slugify("Reunión 10:30 ¿avances?") == "reunion-1030-avances"


def test_slugify_impide_escapar_del_directorio():
    out = slugify("../../etc/passwd")
    assert "/" not in out and ".." not in out


def test_safe_note_name_conserva_legibilidad():
    # A diferencia de slugify, es el nombre que se ve en el vault.
    assert safe_note_name("Acta 2026-07-30 - Revisión técnica") == (
        "Acta 2026-07-30 - Revisión técnica"
    )


def test_safe_note_name_elimina_caracteres_ilegales_en_windows():
    out = safe_note_name('Acta - Daily: avances <urgente> "ya"')
    for ch in '<>:"/\\|?*':
        assert ch not in out


def test_safe_note_name_impide_escapar_del_directorio():
    # El cliente concatena este nombre a su carpeta de actas sin validarlo.
    out = safe_note_name("Acta - ../../pwned")
    assert "/" not in out
    assert "\\" not in out
    assert ".." not in out


def test_safe_note_name_no_termina_en_punto_ni_espacio():
    # Windows rechaza ambos finales.
    assert not safe_note_name("Acta final...").endswith(".")
    assert not safe_note_name("Acta final   ").endswith(" ")


def test_safe_note_name_nunca_queda_vacio():
    assert safe_note_name("///") == "Reunion"
    assert safe_note_name("") == "Reunion"
    assert safe_note_name("   ") == "Reunion"


def test_safe_note_name_quita_caracteres_de_control():
    assert "\x00" not in safe_note_name("Acta\x00rara")
    assert "\n" not in safe_note_name("Acta\nrara")
