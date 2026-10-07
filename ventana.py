#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ventana.py — Título de la ventana ACTIVA (multiplataforma, con degradación).
================================================================================
Sirve para dar CONTEXTO educativo al registro ("¿en qué app se tecleó esto?").
No captura contenido de pantalla ni datos de otras apps: solo el TÍTULO de la
ventana en primer plano, que el propio sistema ya expone.

Estrategia por orden de preferencia:
  1. Windows: ``ctypes`` + user32 (sin dependencias externas; ya viene con Python).
  2. Cualquier SO: ``PyWinCtl`` SI está instalado (import opcional, nunca obligatorio).
  3. Si nada funciona: se devuelve "N/D" con elegancia (nunca lanza excepción).
"""

from __future__ import annotations

import os

_EN_WINDOWS = os.name == "nt"

# --- Vía 1: ctypes en Windows (sin dependencias) --------------------------- #
_user32 = None
if _EN_WINDOWS:
    try:
        import ctypes

        _user32 = ctypes.windll.user32
    except Exception:
        _user32 = None

# --- Vía 2: PyWinCtl opcional (multiplataforma) ---------------------------- #
try:
    import pywinctl as _pywinctl  # type: ignore
except Exception:
    _pywinctl = None


def _titulo_windows() -> str | None:
    """Título de la ventana activa vía user32 (solo Windows)."""
    if _user32 is None:
        return None
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        longitud = _user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(longitud + 1)
        _user32.GetWindowTextW(hwnd, buffer, longitud + 1)
        return buffer.value or "(sin título)"
    except Exception:
        return None


def _titulo_pywinctl() -> str | None:
    """Título de la ventana activa vía PyWinCtl (Windows/Linux/macOS)."""
    if _pywinctl is None:
        return None
    try:
        ventana = _pywinctl.getActiveWindow()
        if ventana is None:
            return None
        titulo = getattr(ventana, "title", None)
        return titulo or "(sin título)"
    except Exception:
        return None


def titulo_ventana_activa() -> str:
    """Devuelve el título de la ventana en primer plano, o 'N/D' si no se puede.

    Prueba las vías disponibles en orden y nunca propaga excepciones: si ninguna
    funciona (p. ej. Linux sin PyWinCtl), devuelve un valor neutro.
    """
    for via in (_titulo_windows, _titulo_pywinctl):
        titulo = via()
        if titulo:
            return titulo
    return "N/D (no disponible)"


def soporte_disponible() -> str:
    """Describe qué mecanismo de captura de ventana está activo (para el log)."""
    if _user32 is not None:
        return "ctypes/user32 (Windows)"
    if _pywinctl is not None:
        return "PyWinCtl (multiplataforma)"
    return "ninguno (títulos de ventana = N/D)"
