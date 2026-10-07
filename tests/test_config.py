#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests de la configuración (config.py)."""

import json

import pytest

from config import Config, cargar_config, config_desde_args


def test_defaults_validos():
    cfg = Config()
    cfg.validar()  # no debe lanzar
    assert cfg.tecla_salir == "esc"
    assert cfg.tecla_pausa == "f9"
    assert cfg.registrar_ventanas is True


def test_salir_y_pausa_no_pueden_coincidir():
    cfg = Config(tecla_salir="esc", tecla_pausa="esc")
    with pytest.raises(ValueError):
        cfg.validar()


def test_duracion_negativa_invalida():
    cfg = Config(duracion_maxima_min=-1)
    with pytest.raises(ValueError):
        cfg.validar()


def test_cargar_config_desde_json(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps({
        "tecla_salir": "f12",
        "duracion_maxima_min": 10,
        "clave_desconocida": "se ignora",  # robustez
    }), encoding="utf-8")
    cfg = cargar_config(str(ruta))
    assert cfg.tecla_salir == "f12"
    assert cfg.duracion_maxima_min == 10
    assert not hasattr(cfg, "clave_desconocida")


def test_json_invalido_lanza(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_config(str(ruta))


def test_cli_sobrescribe_config(tmp_path):
    inexistente = str(tmp_path / "no-existe.json")   # fuerza defaults
    cfg, args = config_desde_args(
        ["--config", inexistente, "--tecla-salir", "f10",
         "--duracion", "5", "--sin-ventanas"]
    )
    assert cfg.tecla_salir == "f10"
    assert cfg.duracion_maxima_min == 5.0
    assert cfg.registrar_ventanas is False
    assert args.crear_config is False


def test_rutas_absolutas():
    cfg = Config(archivo_txt="salida.txt")
    assert cfg.ruta_txt.endswith("salida.txt")
    import os
    assert os.path.isabs(cfg.ruta_txt)
