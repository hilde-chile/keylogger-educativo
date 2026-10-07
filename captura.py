#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
captura.py — Lógica de FORMATEO de teclas del keylogger educativo.
================================================================================
Este módulo NO toca el disco ni el teclado físico: solo transforma los eventos
que entrega ``pynput`` en estructuras de datos claras y verificables. Por eso es
100 % testeable con objetos simulados (ver ``tests/``), sin pulsar teclas reales.

Responsabilidad única: dado un evento de tecla (y el estado de los modificadores
que este módulo lleva internamente), decidir si es…

    * un CARÁCTER imprimible      (``a``, ``ñ``, ``5``, un espacio)
    * una tecla ESPECIAL          (``enter``, ``backspace``, ``esc``, ``F4``…)
    * una COMBINACIÓN con valor    (``Ctrl+C``, ``Alt+Tab``, ``Alt+F4``…)

…y producir un :class:`EventoTecla` con toda la información que necesitan tanto
el registro legible (``.txt``) como el estructurado (``.jsonl``).

Decisiones de diseño (el porqué, no solo el qué):
  - Los modificadores sueltos (Shift/Ctrl/Alt/Cmd) se registran, pero con
    ``texto=""`` para que NO ensucien la reconstrucción del texto: el efecto de
    Shift ya viene aplicado por pynput en ``key.char`` (mayúscula/símbolo).
  - AltGr (tecla ``alt_gr``) se trata como productor de SÍMBOLOS, no como parte
    de una combinación, porque en Windows AltGr = Ctrl_izq + Alt_der y de lo
    contrario "@" o "€" se confundirían con un atajo Ctrl+algo.
  - Las teclas muertas (acentos: ´ ` ¨ ^) se componen con la vocal siguiente
    usando la API de pynput ``KeyCode.join`` (histórico issue #118). Si la
    composición falla, se degrada con elegancia sin romper la captura.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, asdict
from typing import Any, Optional

# ``pynput`` es la dependencia que engancha el teclado. Se importa aquí porque
# necesitamos sus tipos (Key / KeyCode) para clasificar, pero TODA la lógica de
# formateo funciona igual con objetos simulados que imiten esos atributos.
from pynput import keyboard


# --------------------------------------------------------------------------- #
# Tablas de referencia
# --------------------------------------------------------------------------- #

#: Nombres de tecla (pynput ``Key.name``) que son modificadores y su forma
#: canónica. AltGr y Alt derecho se unifican como ``alt_gr`` para distinguirlos
#: del Alt izquierdo, que sí forma atajos (Alt+Tab).
_MODIFICADORES: dict[str, str] = {
    "ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "alt": "alt", "alt_l": "alt",
    "alt_r": "alt_gr", "alt_gr": "alt_gr",
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
    "cmd": "cmd", "cmd_l": "cmd", "cmd_r": "cmd",
}

#: Teclas especiales que SÍ aportan texto a la reconstrucción.
_TEXTO_ESPECIAL: dict[str, str] = {
    "space": " ",
    "enter": "\n",
    "tab": "\t",
}

#: Nombre "bonito" para mostrar una tecla dentro de una combinación
#: (p. ej. ``Alt+Tab``, ``Alt+F4``, ``Ctrl+Supr``).
_NOMBRE_BONITO: dict[str, str] = {
    "tab": "Tab", "enter": "Enter", "esc": "Esc", "space": "Espacio",
    "backspace": "Retroceso", "delete": "Supr", "insert": "Ins",
    "home": "Inicio", "end": "Fin", "page_up": "RePág", "page_down": "AvPág",
    "up": "↑", "down": "↓", "left": "←", "right": "→",
    "print_screen": "ImprPant", "pause": "Pausa", "menu": "Menú",
}

#: Orden canónico en que se muestran los modificadores de una combinación.
_ORDEN_MODIFICADORES = ("ctrl", "alt", "shift", "cmd")
_ETIQUETA_MODIFICADOR = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "cmd": "Cmd"}


# --------------------------------------------------------------------------- #
# Estructura de salida
# --------------------------------------------------------------------------- #
@dataclass
class EventoTecla:
    """Representa una pulsación ya interpretada, lista para registrar.

    Atributos:
        key:      Nombre canónico legible ('a', 'enter', 'Ctrl+C').
        texto:    Aporte a la RECONSTRUCCIÓN del texto ('a', '\\n', '\\t' o '').
                  Vacío para modificadores, esc, flechas… (no escriben texto).
        token_txt: Lo que se vuelca en el registro LEGIBLE (.txt). Puede ser el
                  propio carácter, '\\n', '[esc]', '[Ctrl+C]' o '' (se omite).
        especial: True si es una tecla especial (no un carácter imprimible).
        combo:    True si es una combinación Ctrl/Alt/Cmd + tecla.
    """

    key: str
    texto: str
    token_txt: str
    especial: bool
    combo: bool

    def como_dict(self) -> dict[str, Any]:
        """Devuelve los campos relevantes para el JSONL (sin ``token_txt``)."""
        d = asdict(self)
        d.pop("token_txt", None)
        return d


# --------------------------------------------------------------------------- #
# Utilidades de bajo nivel (funciones puras, fáciles de testear)
# --------------------------------------------------------------------------- #
def nombre_modificador(tecla: Any) -> Optional[str]:
    """Si ``tecla`` es un modificador, devuelve su forma canónica; si no, None."""
    nombre = getattr(tecla, "name", None)
    if nombre is None:
        return None
    return _MODIFICADORES.get(nombre)


def _es_tecla_muerta(tecla: Any) -> bool:
    """True si la tecla es "muerta" (acento pendiente de componerse)."""
    return getattr(tecla, "combining", None) not in (None, "")


def _letra_desde_control(char: str) -> str:
    """Convierte un carácter de control (Ctrl+letra) en su letra visible.

    En Windows, Ctrl+C llega como '\\x03'. Sumar 64 al código lo devuelve a
    'C' (0x03 + 0x40 = 0x43). Útil para mostrar "Ctrl+C" en vez de basura.
    """
    if len(char) == 1 and ord(char) < 32:
        return chr(ord(char) + 64)
    return char.upper()


def _nombre_bonito(tecla: Any) -> str:
    """Nombre presentable de una tecla especial dentro de una combinación."""
    nombre = getattr(tecla, "name", None)
    if nombre:
        return _NOMBRE_BONITO.get(nombre, nombre.replace("_", " ").title())
    char = getattr(tecla, "char", None)
    if char:
        return _letra_desde_control(char)
    return "?"


def etiqueta_combinacion(modificadores: set[str], tecla: Any) -> str:
    """Construye la etiqueta legible de una combinación, p. ej. 'Ctrl+Shift+S'.

    Solo participan los modificadores de atajo (Ctrl/Alt/Shift/Cmd), en orden
    canónico. AltGr nunca llega aquí porque no forma combinaciones.
    """
    partes = [
        _ETIQUETA_MODIFICADOR[m]
        for m in _ORDEN_MODIFICADORES
        if m in modificadores
    ]
    char = getattr(tecla, "char", None)
    if char:
        partes.append(_letra_desde_control(char))
    else:
        partes.append(_nombre_bonito(tecla))
    return "+".join(partes)


# --------------------------------------------------------------------------- #
# Máquina de estado del teclado
# --------------------------------------------------------------------------- #
class Teclado:
    """Interpreta la secuencia de eventos de teclado manteniendo el estado.

    Lleva la cuenta de qué modificadores están pulsados y si hay una tecla
    muerta (acento) pendiente. No escribe nada: solo produce :class:`EventoTecla`.
    """

    def __init__(self) -> None:
        #: Modificadores actualmente pulsados (formas canónicas).
        self._modificadores: set[str] = set()
        #: Tecla muerta (acento) pendiente de componerse con la siguiente vocal.
        self._muerta: Any = None

    # -- API pública ------------------------------------------------------- #
    @property
    def modificadores(self) -> set[str]:
        """Copia de los modificadores activos (para inspección/tests)."""
        return set(self._modificadores)

    def presionar(self, tecla: Any) -> Optional[EventoTecla]:
        """Procesa una pulsación y devuelve un :class:`EventoTecla` o ``None``.

        Devuelve ``None`` cuando el evento no debe registrarse como pulsación
        propia (p. ej. autorrepetición de un modificador ya pulsado, o la
        primera mitad de una tecla muerta que aún no se ha compuesto).
        """
        # 1) ¿Es un modificador? Actualiza estado y regístralo una sola vez.
        canon = nombre_modificador(tecla)
        if canon is not None:
            if canon in self._modificadores:
                return None  # autorrepetición: no duplicar el evento
            self._modificadores.add(canon)
            nombre = getattr(tecla, "name", canon)
            # Los modificadores se registran (para estadística) pero sin texto,
            # así no contaminan la reconstrucción.
            return EventoTecla(
                key=nombre, texto="", token_txt="", especial=True, combo=False
            )

        # 2) ¿Hay una combinación de atajo activa (Ctrl/Alt/Cmd, no AltGr)?
        if self._hay_combinacion():
            self._muerta = None  # un atajo cancela cualquier acento pendiente
            etiqueta = etiqueta_combinacion(self._modificadores, tecla)
            return EventoTecla(
                key=etiqueta, texto="", token_txt=f"[{etiqueta}]",
                especial=False, combo=True,
            )

        # 3) Tecla muerta (acento): guárdala para componerla con la siguiente.
        if _es_tecla_muerta(tecla):
            self._muerta = tecla
            return None

        # 4) Tecla con carácter imprimible (incluye símbolos de AltGr).
        char = getattr(tecla, "char", None)
        if char is not None:
            char = self._componer_si_pendiente(char, tecla)
            return EventoTecla(
                key=char, texto=char, token_txt=char, especial=False, combo=False
            )

        # 5) Tecla especial con nombre (space/enter/tab aportan texto).
        return self._formatear_especial(tecla)

    def soltar(self, tecla: Any) -> None:
        """Actualiza el estado al soltar una tecla (quita modificadores)."""
        canon = nombre_modificador(tecla)
        if canon is not None:
            self._modificadores.discard(canon)

    # -- Interno ----------------------------------------------------------- #
    def _hay_combinacion(self) -> bool:
        """True si hay un modificador de atajo activo (Ctrl/Alt/Cmd, no AltGr).

        Si AltGr está pulsado, se asume composición de símbolo, no atajo, aunque
        Windows haya reportado además un Ctrl "fantasma".
        """
        if "alt_gr" in self._modificadores:
            return False
        return bool(self._modificadores & {"ctrl", "alt", "cmd"})

    def _componer_si_pendiente(self, char: str, tecla: Any) -> str:
        """Compone una tecla muerta pendiente (´ + a = á) si la hay."""
        if self._muerta is None:
            return char
        muerta, self._muerta = self._muerta, None
        # Vía preferente: la API de pynput sabe combinar acento + vocal.
        try:
            combinado = muerta.join(tecla)
            if getattr(combinado, "char", None):
                return combinado.char
        except Exception:
            pass
        # Degradación elegante: normalización Unicode con el diacrítico.
        try:
            diacritico = getattr(muerta, "combining", "") or ""
            compuesto = unicodedata.normalize("NFC", char + diacritico)
            if compuesto:
                return compuesto
        except Exception:
            pass
        return char

    def _formatear_especial(self, tecla: Any) -> Optional[EventoTecla]:
        """Formatea una tecla especial (enter, tab, esc, flechas, F1…)."""
        # Si había un acento pendiente y llega una especial, se pierde el acento
        # de forma controlada (no se compone con enter/space, etc.).
        self._muerta = None
        nombre = getattr(tecla, "name", None)
        if nombre is None:
            return None  # evento no interpretable: se ignora sin romper nada
        if nombre in _TEXTO_ESPECIAL:
            texto = _TEXTO_ESPECIAL[nombre]
            # space/enter/tab: imprimibles funcionales -> no "especiales" en stats.
            es_imprimible = nombre == "space"
            return EventoTecla(
                key=nombre, texto=texto, token_txt=texto,
                especial=not es_imprimible, combo=False,
            )
        return EventoTecla(
            key=nombre, texto="", token_txt=f"[{nombre}]",
            especial=True, combo=False,
        )
