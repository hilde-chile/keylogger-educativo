#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la escritura de registros (registro.py) — .txt y .jsonl."""

import json

from captura import EventoTecla
from registro import Registrador


def _leer_jsonl(ruta):
    eventos = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                eventos.append(json.loads(linea))
    return eventos


def test_escribe_ambos_formatos(tmp_path):
    ruta_txt = tmp_path / "r.txt"
    ruta_jsonl = tmp_path / "r.jsonl"
    with Registrador(str(ruta_txt), str(ruta_jsonl)) as reg:
        reg.iniciar_sesion({"usuario": "ana", "equipo": "PC-LAB",
                            "sistema": "Windows 11", "consentimiento": "aceptado"})
        reg.registrar_ventana("Bloc de notas")
        reg.registrar_tecla(EventoTecla("h", "h", "h", False, False), "Bloc de notas")
        reg.registrar_tecla(EventoTecla("i", "i", "i", False, False), "Bloc de notas")
        reg.registrar_tecla(EventoTecla("enter", "\n", "\n", True, False), "Bloc de notas")
        reg.detener_sesion("tecla ESC")

    # El .txt legible contiene la cabecera y el texto tecleado.
    texto = ruta_txt.read_text(encoding="utf-8")
    assert "Nueva sesión de captura iniciada" in texto
    assert "EDUCATIVO" in texto
    assert "hi" in texto
    assert "Captura detenida (tecla ESC)" in texto

    # El .jsonl estructurado: una línea JSON por evento, con el esquema esperado.
    eventos = _leer_jsonl(ruta_jsonl)
    tipos = [e["type"] for e in eventos]
    assert tipos == ["session_start", "window", "key", "key", "key", "session_stop"]

    tecla_h = eventos[2]
    assert tecla_h["type"] == "key"
    assert tecla_h["key"] == "h"
    assert tecla_h["text"] == "h"
    assert tecla_h["window"] == "Bloc de notas"
    assert tecla_h["special"] is False
    assert tecla_h["combo"] is False
    assert set(tecla_h) >= {"ts", "type", "window", "key", "special", "combo", "text"}

    assert eventos[0]["meta"]["usuario"] == "ana"
    assert eventos[-1]["reason"] == "tecla ESC"


def test_combinacion_y_nota_en_jsonl(tmp_path):
    ruta_txt = tmp_path / "r.txt"
    ruta_jsonl = tmp_path / "r.jsonl"
    with Registrador(str(ruta_txt), str(ruta_jsonl)) as reg:
        reg.registrar_tecla(EventoTecla("Ctrl+C", "", "[Ctrl+C]", False, True), "App")
        reg.registrar_nota("Captura OMITIDA: ventana sensible activa")

    eventos = _leer_jsonl(ruta_jsonl)
    assert eventos[0]["combo"] is True
    assert eventos[0]["key"] == "Ctrl+C"
    assert eventos[1]["type"] == "note"
    # El token de combinación aparece en el .txt legible.
    assert "[Ctrl+C]" in ruta_txt.read_text(encoding="utf-8")


def test_cierre_es_idempotente(tmp_path):
    reg = Registrador(str(tmp_path / "r.txt"), str(tmp_path / "r.jsonl"))
    reg.cerrar()
    reg.cerrar()  # no debe lanzar
