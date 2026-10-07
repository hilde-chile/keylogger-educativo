#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests del análisis del registro para el panel (dashboard.py)."""

import json

import dashboard


def _escribir_jsonl(ruta, eventos):
    with open(ruta, "w", encoding="utf-8") as f:
        for e in eventos:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _usar_jsonl(monkeypatch, ruta, eventos):
    _escribir_jsonl(ruta, eventos)
    monkeypatch.setattr(dashboard, "ARCHIVO_JSONL", str(ruta))
    return dashboard.analizar_registro()


def test_reconstruccion_con_backspace(monkeypatch, tmp_path):
    eventos = [
        {"ts": "2026-09-28 10:00:00", "type": "session_start", "meta": {}},
        {"ts": "2026-09-28 10:00:01", "type": "window", "window": "Bloc"},
        {"ts": "2026-09-28 10:00:02", "type": "key", "window": "Bloc", "key": "h", "special": False, "combo": False, "text": "h"},
        {"ts": "2026-09-28 10:00:02", "type": "key", "window": "Bloc", "key": "o", "special": False, "combo": False, "text": "o"},
        {"ts": "2026-09-28 10:00:02", "type": "key", "window": "Bloc", "key": "l", "special": False, "combo": False, "text": "l"},
        {"ts": "2026-09-28 10:00:03", "type": "key", "window": "Bloc", "key": "a", "special": False, "combo": False, "text": "a"},
        {"ts": "2026-09-28 10:00:04", "type": "key", "window": "Bloc", "key": "backspace", "special": True, "combo": False, "text": ""},
        {"ts": "2026-09-28 10:00:05", "type": "key", "window": "Bloc", "key": "!", "special": False, "combo": False, "text": "!"},
        {"ts": "2026-09-28 10:01:30", "type": "session_stop", "reason": "ESC"},
    ]
    data = _usar_jsonl(monkeypatch, tmp_path / "r.jsonl", eventos)

    assert data["has_data"] is True
    assert data["source"] == "jsonl"
    # h o l a  <backspace>  !  ->  "hol!"
    assert data["segments"][0]["text"] == "hol!"
    assert data["stats"]["total_chars"] == 5    # h,o,l,a,!
    assert data["stats"]["total_specials"] == 1  # backspace
    assert data["stats"]["sessions_count"] == 1


def test_duracion_de_sesion(monkeypatch, tmp_path):
    eventos = [
        {"ts": "2026-09-28 10:00:00", "type": "session_start", "meta": {}},
        {"ts": "2026-09-28 10:00:10", "type": "key", "window": "X", "key": "a", "special": False, "combo": False, "text": "a"},
        {"ts": "2026-09-28 10:01:30", "type": "session_stop", "reason": "ESC"},
    ]
    data = _usar_jsonl(monkeypatch, tmp_path / "r.jsonl", eventos)
    assert data["sessions"][0]["duration"] == "1 min 30 s"
    assert data["sessions"][0]["start"] == "2026-09-28 10:00:00"
    assert data["sessions"][0]["stop"] == "2026-09-28 10:01:30"


def test_agrega_ventanas_y_especiales(monkeypatch, tmp_path):
    eventos = [
        {"ts": "2026-09-28 10:00:00", "type": "session_start", "meta": {}},
        {"ts": "2026-09-28 10:00:01", "type": "key", "window": "Chrome", "key": "a", "special": False, "combo": False, "text": "a"},
        {"ts": "2026-09-28 10:00:02", "type": "key", "window": "Chrome", "key": "Ctrl+C", "special": False, "combo": True, "text": ""},
        {"ts": "2026-09-28 10:00:03", "type": "key", "window": "Word", "key": "b", "special": False, "combo": False, "text": "b"},
        {"ts": "2026-09-28 10:00:04", "type": "key", "window": "Word", "key": "enter", "special": True, "combo": False, "text": "\n"},
    ]
    data = _usar_jsonl(monkeypatch, tmp_path / "r.jsonl", eventos)

    ventanas = {w["window"]: w for w in data["windows"]}
    assert set(ventanas) == {"Chrome", "Word"}
    assert ventanas["Chrome"]["events"] == 2
    assert data["stats"]["windows_count"] == 2

    especiales = {k["key"]: k["count"] for k in data["special_keys"]}
    assert especiales.get("Ctrl+C") == 1   # las combinaciones se cuentan aparte
    assert especiales.get("enter") == 1


def test_lineas_corruptas_se_ignoran(monkeypatch, tmp_path):
    ruta = tmp_path / "r.jsonl"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts": "2026-09-28 10:00:00", "type": "session_start", "meta": {}}) + "\n")
        f.write('{"ts": "2026-09-28 10:00:01", "type": "key"  <-- LINEA ROTA\n')
        f.write(json.dumps({"ts": "2026-09-28 10:00:02", "type": "key", "window": "X", "key": "z", "special": False, "combo": False, "text": "z"}) + "\n")
    monkeypatch.setattr(dashboard, "ARCHIVO_JSONL", str(ruta))
    data = dashboard.analizar_registro()
    assert data["has_data"] is True
    assert data["stats"]["total_chars"] == 1   # solo la 'z' válida


def test_duracion_humana():
    assert dashboard._duracion_humana("2026-09-28 10:00:00", "2026-09-28 10:00:45") == "45 s"
    assert dashboard._duracion_humana("2026-09-28 10:00:00", "2026-09-28 11:02:03") == "1 h 2 min 3 s"
    assert dashboard._duracion_humana("2026-09-28 10:00:00", "2026-09-28 09:00:00") is None
