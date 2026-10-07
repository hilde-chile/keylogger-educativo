#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuración común de los tests.

Estos tests NO pulsan teclas reales ni abren el teclado: simulan los objetos
que entregaría ``pynput`` (``Key`` y ``KeyCode``) para probar la LÓGICA pura
(formateo, serialización, reconstrucción, config, duraciones).
"""

import os
import sys

# Permite ``import captura`` / ``config`` / ``registro`` / ``dashboard`` desde
# la raíz del proyecto sin instalar nada.
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

import pytest
from pynput import keyboard


# --------------------------------------------------------------------------- #
# Fábricas de teclas simuladas (usan objetos REALES de pynput, sin hardware)
# --------------------------------------------------------------------------- #
@pytest.fixture
def char():
    """Devuelve un KeyCode a partir de un carácter ('a', '@', '\\x03'…)."""
    return keyboard.KeyCode.from_char


@pytest.fixture
def especial():
    """Devuelve una tecla especial de pynput por su nombre ('enter', 'tab'…)."""
    def _obtener(nombre):
        return getattr(keyboard.Key, nombre)
    return _obtener


@pytest.fixture
def muerta():
    """Devuelve una tecla muerta (acento) a partir de su carácter ('´', '¨'…)."""
    return keyboard.KeyCode.from_dead
