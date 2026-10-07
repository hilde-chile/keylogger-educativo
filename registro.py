#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
registro.py — Escritura ROBUSTA del registro (legible .txt + estructurado .jsonl).
================================================================================
El keylogger produce DOS salidas complementarias, ambas 100 % locales:

  * ``registro_teclas.txt``  — legible por humanos, para leer "de un vistazo".
  * ``registro_teclas.jsonl`` — una línea JSON por evento, que consume el panel
    web (``dashboard.py``). Estructurado = fácil de analizar y graficar.

Prioridades de este módulo:
  - No perder datos: se abre en modo *append* y se hace *flush* tras cada evento
    (y ``os.fsync`` periódico), de modo que un cierre abrupto pierda como mucho
    la última pulsación.
  - No romper la captura: cualquier error de E/S se reporta pero no propaga.
  - Codificación UTF-8 explícita y rutas absolutas (nada de rutas frágiles).
"""

from __future__ import annotations

import datetime
import getpass
import json
import logging
import os
import platform
from typing import Any

from captura import EventoTecla

_log = logging.getLogger("keylogger.registro")


def marca_de_tiempo() -> str:
    """Fecha y hora local con formato 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Registrador:
    """Gestiona la escritura de ambos registros con cierre ordenado.

    Uso típico::

        with Registrador(ruta_txt, ruta_jsonl) as reg:
            reg.iniciar_sesion(meta)
            reg.registrar_ventana("Bloc de notas")
            reg.registrar_tecla(evento, "Bloc de notas")
            reg.detener_sesion("ESC")
    """

    def __init__(self, ruta_txt: str, ruta_jsonl: str) -> None:
        self.ruta_txt = ruta_txt
        self.ruta_jsonl = ruta_jsonl
        self._txt = None
        self._jsonl = None
        self._eventos_desde_sync = 0
        self._abrir()

    # -- Ciclo de vida ----------------------------------------------------- #
    def _abrir(self) -> None:
        """Abre ambos ficheros en modo append con UTF-8."""
        try:
            self._txt = open(self.ruta_txt, "a", encoding="utf-8")
            self._jsonl = open(self.ruta_jsonl, "a", encoding="utf-8")
        except OSError as e:
            _log.error("No se pudieron abrir los registros: %s", e)
            raise

    def cerrar(self) -> None:
        """Cierra los ficheros de forma segura (idempotente)."""
        for f in (self._txt, self._jsonl):
            if f is not None:
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except (OSError, ValueError):
                    pass
                try:
                    f.close()
                except OSError:
                    pass
        self._txt = None
        self._jsonl = None

    def __enter__(self) -> "Registrador":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.cerrar()

    # -- Escritura de bajo nivel ------------------------------------------- #
    def _escribir_txt(self, texto: str) -> None:
        if not texto or self._txt is None:
            return
        try:
            self._txt.write(texto)
            self._txt.flush()
        except (OSError, ValueError) as e:
            _log.error("Error al escribir el .txt: %s", e)

    def _escribir_jsonl(self, obj: dict[str, Any]) -> None:
        if self._jsonl is None:
            return
        try:
            self._jsonl.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self._jsonl.flush()
            self._eventos_desde_sync += 1
            # fsync periódico: equilibrio entre no perder datos y no saturar E/S.
            if self._eventos_desde_sync >= 20:
                os.fsync(self._jsonl.fileno())
                self._eventos_desde_sync = 0
        except (OSError, ValueError) as e:
            _log.error("Error al escribir el .jsonl: %s", e)

    def _evento_jsonl(self, tipo: str, **campos: Any) -> dict[str, Any]:
        base = {"ts": marca_de_tiempo(), "type": tipo}
        base.update(campos)
        return base

    # -- Eventos de alto nivel --------------------------------------------- #
    def iniciar_sesion(self, meta: dict[str, Any]) -> None:
        """Escribe la cabecera de una nueva sesión (con datos de consentimiento).

        La cabecera deja constancia EXPLÍCITA del uso educativo, quién y en qué
        equipo se ejecuta y que el consentimiento fue aceptado. Transparencia
        total: lo contrario de un malware.
        """
        ts = marca_de_tiempo()
        cabecera = (
            f"\n{'=' * 64}\n"
            f"[{ts}] === Nueva sesión de captura iniciada ===\n"
            f"  Uso:            EDUCATIVO (curso de Hacking Ético)\n"
            f"  Usuario:        {meta.get('usuario', '?')}\n"
            f"  Equipo:         {meta.get('equipo', '?')}\n"
            f"  Sistema:        {meta.get('sistema', '?')}\n"
            f"  Consentimiento: {meta.get('consentimiento', 'aceptado')}\n"
            f"  Nota:           registro LOCAL, sin red. Puede contener datos\n"
            f"                  sensibles: no lo compartas.\n"
            f"{'=' * 64}\n"
        )
        self._escribir_txt(cabecera)
        self._escribir_jsonl(self._evento_jsonl("session_start", meta=meta))

    def registrar_ventana(self, titulo: str) -> None:
        """Anota un cambio de ventana activa (contexto del registro)."""
        self._escribir_txt(f"\n\n[{marca_de_tiempo()}] --- Ventana activa: {titulo} ---\n")
        self._escribir_jsonl(self._evento_jsonl("window", window=titulo))

    def registrar_tecla(self, evento: EventoTecla, ventana: str) -> None:
        """Registra una pulsación en ambos formatos."""
        self._escribir_txt(evento.token_txt)
        self._escribir_jsonl(self._evento_jsonl(
            "key",
            window=ventana,
            key=evento.key,
            special=evento.especial,
            combo=evento.combo,
            text=evento.texto,
        ))

    def registrar_nota(self, texto: str) -> None:
        """Registra una nota de contexto (p. ej. omisión por ventana sensible)."""
        self._escribir_txt(f"\n\n[{marca_de_tiempo()}] --- {texto} ---\n")
        self._escribir_jsonl(self._evento_jsonl("note", text=texto))

    def registrar_pausa(self, en_pausa: bool) -> None:
        """Marca una pausa o reanudación de la captura."""
        estado = "pausada" if en_pausa else "reanudada"
        self._escribir_txt(f"\n\n[{marca_de_tiempo()}] --- Captura {estado} ---\n")
        tipo = "session_pause" if en_pausa else "session_resume"
        self._escribir_jsonl(self._evento_jsonl(tipo))

    def detener_sesion(self, motivo: str) -> None:
        """Escribe el marcador de fin de sesión (nada silencioso)."""
        ts = marca_de_tiempo()
        self._escribir_txt(
            f"\n\n[{ts}] === Captura detenida ({motivo}) ===\n"
        )
        self._escribir_jsonl(self._evento_jsonl("session_stop", reason=motivo))
