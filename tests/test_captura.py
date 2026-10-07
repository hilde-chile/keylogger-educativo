#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests del formateo de teclas (captura.py) — sin teclado físico."""

from captura import Teclado, EventoTecla, etiqueta_combinacion, _letra_desde_control


def test_caracter_imprimible(char):
    t = Teclado()
    ev = t.presionar(char("a"))
    assert ev == EventoTecla(key="a", texto="a", token_txt="a", especial=False, combo=False)


def test_espacio_cuenta_como_imprimible(especial):
    t = Teclado()
    ev = t.presionar(especial("space"))
    assert ev.texto == " "
    assert ev.especial is False  # el espacio es un carácter imprimible funcional


def test_enter_y_tab_aportan_texto(especial):
    t = Teclado()
    enter = t.presionar(especial("enter"))
    tab = t.presionar(especial("tab"))
    assert enter.texto == "\n" and enter.especial is True
    assert tab.texto == "\t" and tab.especial is True


def test_tecla_especial_sin_texto(especial):
    t = Teclado()
    ev = t.presionar(especial("esc"))
    assert ev.key == "esc"
    assert ev.texto == ""            # no aporta a la reconstrucción
    assert ev.token_txt == "[esc]"   # sí aparece en el .txt legible
    assert ev.especial is True


def test_backspace_se_marca_como_especial(especial):
    t = Teclado()
    ev = t.presionar(especial("backspace"))
    assert ev.key == "backspace"
    assert ev.especial is True
    assert ev.texto == ""


def test_modificador_se_registra_una_sola_vez(especial):
    """Shift pulsado y mantenido (autorrepetición) no debe duplicar eventos."""
    t = Teclado()
    primero = t.presionar(especial("shift"))
    segundo = t.presionar(especial("shift"))   # autorrepetición
    assert primero is not None and primero.especial is True and primero.texto == ""
    assert segundo is None
    assert "shift" in t.modificadores
    t.soltar(especial("shift"))
    assert "shift" not in t.modificadores


def test_shift_no_crea_combinacion(char, especial):
    """Shift solo capitaliza; pynput ya entrega la mayúscula, no es un atajo."""
    t = Teclado()
    t.presionar(especial("shift"))
    ev = t.presionar(char("A"))   # pynput ya la entrega en mayúscula
    assert ev.key == "A"
    assert ev.combo is False


def test_combinacion_ctrl_c_desde_caracter_de_control(char, especial):
    """En Windows Ctrl+C llega como '\\x03'; debe leerse como 'Ctrl+C'."""
    t = Teclado()
    t.presionar(especial("ctrl"))
    ev = t.presionar(char("\x03"))
    assert ev.combo is True
    assert ev.key == "Ctrl+C"
    assert ev.token_txt == "[Ctrl+C]"
    assert ev.texto == ""   # una combinación no aporta texto a la reconstrucción


def test_combinacion_ctrl_shift_s_orden_canonico(char, especial):
    t = Teclado()
    t.presionar(especial("ctrl"))
    t.presionar(especial("shift"))
    ev = t.presionar(char("s"))
    assert ev.combo is True
    assert ev.key == "Ctrl+Shift+S"


def test_combinacion_alt_tab_con_tecla_especial(especial):
    t = Teclado()
    t.presionar(especial("alt"))
    ev = t.presionar(especial("tab"))
    assert ev.combo is True
    assert ev.key == "Alt+Tab"


def test_altgr_produce_simbolo_no_combinacion(char, especial):
    """AltGr = Ctrl+Alt en Windows; '@' con AltGr NO es un atajo, es un símbolo."""
    t = Teclado()
    t.presionar(especial("alt_gr"))
    ev = t.presionar(char("@"))
    assert ev.combo is False
    assert ev.key == "@"
    assert ev.texto == "@"


def test_tecla_muerta_compone_acento(char, muerta):
    """´ (tecla muerta) + a  ->  á (issue #118 de pynput)."""
    t = Teclado()
    pendiente = t.presionar(muerta("´"))   # acento agudo
    assert pendiente is None                     # aún no hay carácter
    ev = t.presionar(char("a"))
    assert ev.key == "á"                    # 'á'
    assert ev.texto == "á"


def test_letra_desde_control():
    assert _letra_desde_control("\x03") == "C"   # Ctrl+C
    assert _letra_desde_control("\x16") == "V"   # Ctrl+V
    assert _letra_desde_control("z") == "Z"
