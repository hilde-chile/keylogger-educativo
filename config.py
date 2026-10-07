#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.py — Configuración del keylogger educativo (SOLO opciones benignas).
================================================================================
Reúne las opciones de ejecución desde dos fuentes, con esta prioridad:

    valores por defecto  <  config.json  <  argumentos de línea de comandos

IMPORTANTE (ética): aquí NO existe —ni existirá— ninguna opción de sigilo,
persistencia o red. Todas las opciones aumentan control, transparencia o
privacidad. Cualquier "mejora" que fuera en dirección contraria queda fuera.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any

_CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CONFIG = os.path.join(_CARPETA, "config.json")

#: Ventanas cuyo nombre, si aparece, hace que la captura se PAUSE sola
#: (minimización de datos: no registrar mientras usas un gestor de contraseñas).
_EXCLUIDAS_POR_DEFECTO = [
    "keepass", "bitwarden", "1password", "lastpass", "dashlane",
    "nordpass", "proton pass", "gestor de contraseñas", "password manager",
]


def _ruta_absoluta(ruta: str) -> str:
    """Resuelve una ruta relativa respecto a la carpeta del proyecto."""
    if os.path.isabs(ruta):
        return ruta
    return os.path.join(_CARPETA, ruta)


@dataclass
class Config:
    """Opciones de ejecución del keylogger. Todas benignas y validadas."""

    #: Registro legible para humanos.
    archivo_txt: str = "registro_teclas.txt"
    #: Registro estructurado (una línea JSON por evento) que consume el panel.
    archivo_jsonl: str = "registro_teclas.jsonl"
    #: Tecla que detiene la captura (nombre de pynput: esc, f12, etc.).
    tecla_salir: str = "esc"
    #: Tecla que pausa/reanuda la captura sin cerrar el programa.
    tecla_pausa: str = "f9"
    #: Registrar (o no) el título de la ventana activa.
    registrar_ventanas: bool = True
    #: Auto-detención por tiempo: minutos máximos de captura (0 = sin límite).
    duracion_maxima_min: float = 0.0
    #: Recordatorio periódico "GRABANDO" cada N minutos (0 = desactivado).
    intervalo_recordatorio_min: float = 2.0
    #: Subcadenas (en minúsculas) que, si aparecen en el título activo, pausan
    #: la captura como buena práctica de minimización de datos.
    ventanas_excluidas: list[str] = field(
        default_factory=lambda: list(_EXCLUIDAS_POR_DEFECTO)
    )

    # -- Rutas resueltas (propiedades) ------------------------------------- #
    @property
    def ruta_txt(self) -> str:
        return _ruta_absoluta(self.archivo_txt)

    @property
    def ruta_jsonl(self) -> str:
        return _ruta_absoluta(self.archivo_jsonl)

    # -- Validación -------------------------------------------------------- #
    def validar(self) -> None:
        """Comprueba que los valores sean coherentes. Lanza ValueError si no."""
        if not self.archivo_txt or not self.archivo_jsonl:
            raise ValueError("Las rutas de salida no pueden estar vacías.")
        if not isinstance(self.tecla_salir, str) or not self.tecla_salir:
            raise ValueError("tecla_salir debe ser un nombre de tecla válido.")
        if not isinstance(self.tecla_pausa, str) or not self.tecla_pausa:
            raise ValueError("tecla_pausa debe ser un nombre de tecla válido.")
        if self.tecla_salir == self.tecla_pausa:
            raise ValueError("tecla_salir y tecla_pausa no pueden ser la misma.")
        if self.duracion_maxima_min < 0:
            raise ValueError("duracion_maxima_min no puede ser negativa.")
        if self.intervalo_recordatorio_min < 0:
            raise ValueError("intervalo_recordatorio_min no puede ser negativo.")
        if not isinstance(self.ventanas_excluidas, list):
            raise ValueError("ventanas_excluidas debe ser una lista de textos.")

    def como_dict(self) -> dict[str, Any]:
        """Representación serializable (para escribir un config.json de ejemplo)."""
        return asdict(self)


# --------------------------------------------------------------------------- #
# Carga desde config.json
# --------------------------------------------------------------------------- #
def cargar_config(ruta: str | None = None) -> Config:
    """Carga la configuración desde ``config.json`` si existe; si no, defaults.

    Ignora claves desconocidas (robustez ante ficheros antiguos) y valida el
    resultado antes de devolverlo.
    """
    ruta = ruta or ARCHIVO_CONFIG
    cfg = Config()
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"No se pudo leer {ruta}: {e}") from e
        campos_validos = set(Config().como_dict().keys())
        for clave, valor in datos.items():
            if clave in campos_validos:
                setattr(cfg, clave, valor)
    cfg.validar()
    return cfg


def escribir_config_ejemplo(ruta: str | None = None) -> str:
    """Escribe un ``config.json`` de ejemplo con los valores por defecto."""
    ruta = ruta or ARCHIVO_CONFIG
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(Config().como_dict(), f, ensure_ascii=False, indent=2)
    return ruta


# --------------------------------------------------------------------------- #
# Fusión con argumentos de línea de comandos
# --------------------------------------------------------------------------- #
def _crear_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="keylogger.py",
        description=(
            "Keylogger EDUCATIVO (curso de Hacking Ético). Transparente, local "
            "y con consentimiento. No oculta nada ni envía datos por la red."
        ),
        epilog="Solo para uso ético en tu propio equipo o laboratorio autorizado.",
    )
    p.add_argument("--config", metavar="RUTA",
                   help="Ruta a un config.json alternativo.")
    p.add_argument("--txt", dest="archivo_txt", metavar="RUTA",
                   help="Ruta del registro legible (.txt).")
    p.add_argument("--jsonl", dest="archivo_jsonl", metavar="RUTA",
                   help="Ruta del registro estructurado (.jsonl).")
    p.add_argument("--tecla-salir", dest="tecla_salir", metavar="TECLA",
                   help="Tecla para detener la captura (por defecto: esc).")
    p.add_argument("--tecla-pausa", dest="tecla_pausa", metavar="TECLA",
                   help="Tecla para pausar/reanudar (por defecto: f9).")
    p.add_argument("--sin-ventanas", dest="registrar_ventanas",
                   action="store_false", default=None,
                   help="No registrar los títulos de ventana.")
    p.add_argument("--duracion", dest="duracion_maxima_min", type=float,
                   metavar="MIN",
                   help="Detener automáticamente tras MIN minutos (0 = sin límite).")
    p.add_argument("--recordatorio", dest="intervalo_recordatorio_min",
                   type=float, metavar="MIN",
                   help="Recordatorio 'GRABANDO' cada MIN minutos (0 = off).")
    p.add_argument("--crear-config", action="store_true",
                   help="Escribe un config.json de ejemplo y sale.")
    p.add_argument("--borrar-registros", action="store_true",
                   help="Borra de forma segura los registros locales y sale.")
    return p


def config_desde_args(argv: list[str] | None = None) -> tuple[Config, argparse.Namespace]:
    """Combina config.json + argumentos CLI y devuelve (Config, args crudos).

    Los ``args`` crudos se devuelven aparte porque incluyen acciones que no son
    configuración (``--crear-config``, ``--borrar-registros``).
    """
    args = _crear_parser().parse_args(argv)
    cfg = cargar_config(args.config)

    # Aplica solo los argumentos que el usuario haya especificado (no None).
    for campo in (
        "archivo_txt", "archivo_jsonl", "tecla_salir", "tecla_pausa",
        "duracion_maxima_min", "intervalo_recordatorio_min",
    ):
        valor = getattr(args, campo, None)
        if valor is not None:
            setattr(cfg, campo, valor)
    if args.registrar_ventanas is False:
        cfg.registrar_ventanas = False

    cfg.validar()
    return cfg, args
