#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  PANEL DE CONTROL (GUI)  -  Keylogger Educativo (Curso de Hacking Ético)
================================================================================
  ¿QUÉ ES?
  --------
  Una interfaz gráfica sencilla (Tkinter, incluido en Python) para MANEJAR con
  botones la herramienta educativa, en vez de escribir comandos. NO captura nada
  por sí misma: únicamente LANZA los scripts existentes:
     - keylogger.py  (la captura, en su propia ventana de consola, con su aviso)
     - dashboard.py  (el panel web local)

  TRANSPARENCIA (por diseño, esto NO es malware):
  - La ventana es siempre VISIBLE y muestra un indicador claro de "GRABANDO".
  - Exige marcar el consentimiento antes de iniciar la captura.
  - El keylogger arranca en su propia consola visible (donde confirmas el aviso).
  - No se oculta, no persiste al reinicio, no se disfraza y no usa la red externa.
  - Úsalo SOLO en tu propio equipo o laboratorio autorizado, con consentimiento.
    Registrar a terceros sin permiso es ilegal (en Perú, Ley N.° 30096).

  USO:
      python launcher.py
================================================================================
"""

import os
import sys
import shutil
import webbrowser
import subprocess
import tkinter as tk
from tkinter import messagebox

# --------------------------------------------------------------------------- #
# Rutas e intérprete
# --------------------------------------------------------------------------- #
_FROZEN = getattr(sys, "frozen", False)  # True si corre empaquetado como .exe
if _FROZEN:
    _CARPETA = os.path.dirname(os.path.abspath(sys.executable))
    _PYTHON = shutil.which("python") or shutil.which("py") or "python"
else:
    _CARPETA = os.path.dirname(os.path.abspath(__file__))
    _PYTHON = sys.executable

KEYLOGGER = os.path.join(_CARPETA, "keylogger.py")
DASHBOARD = os.path.join(_CARPETA, "dashboard.py")
LOG_TXT = os.path.join(_CARPETA, "registro_teclas.txt")
LOG_JSONL = os.path.join(_CARPETA, "registro_teclas.jsonl")

# Bandera para abrir el keylogger en su PROPIA consola visible (solo Windows),
# donde se muestra el aviso y se confirma el consentimiento.
_NUEVA_CONSOLA = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
# Bandera para ejecutar el PANEL WEB sin ventana de consola (solo Windows).
_SIN_VENTANA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _ip_lan() -> str:
    """IP de este equipo en la red local (para abrir el panel desde el celular).
    No transmite datos: solo consulta qué interfaz usaría el sistema."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# --------------------------------------------------------------------------- #
# Aplicación
# --------------------------------------------------------------------------- #
class Panel(tk.Tk):
    # Paleta (tema oscuro sobrio)
    BG = "#0B1020"
    SURFACE = "#151d3b"
    BORDE = "#26305c"
    TEXTO = "#e7ecff"
    TEXTO2 = "#9aa6d4"
    ACENTO = "#5b8cff"
    VERDE = "#35d0a5"
    ROJO = "#ff6b81"
    AMARILLO = "#f2c14e"

    def __init__(self):
        super().__init__()
        self.proc_keylogger = None
        self.proc_dashboard = None

        self.title("Keylogger Educativo — Panel de Control")
        self.configure(bg=self.BG)
        self.geometry("560x560")
        self.minsize(520, 540)
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        self._construir_ui()
        self._refrescar_estado()
        self.after(1000, self._vigilar_procesos)

    # ---------------------------------------------------------------- UI ---- #
    def _construir_ui(self):
        cont = tk.Frame(self, bg=self.BG)
        cont.pack(fill="both", expand=True, padx=22, pady=18)

        # Encabezado
        tk.Label(cont, text="⌨  Keylogger Educativo", bg=self.BG, fg=self.TEXTO,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(cont, text="Panel de control · Curso de Hacking Ético",
                 bg=self.BG, fg=self.TEXTO2, font=("Segoe UI", 10)).pack(anchor="w")

        # Banner ético
        banner = tk.Frame(cont, bg="#2a2410", highlightbackground=self.AMARILLO,
                          highlightthickness=1)
        banner.pack(fill="x", pady=(14, 12))
        tk.Label(banner, justify="left", wraplength=480, bg="#2a2410", fg="#ffe6ab",
                 font=("Segoe UI", 9),
                 text=("⚠  Uso educativo y local. Ejecuta esto SOLO en tu propio equipo o "
                       "laboratorio autorizado, con consentimiento. Registrar a terceros sin "
                       "permiso es ilegal (Perú, Ley N.° 30096). No envía datos por la red.")
                 ).pack(padx=12, pady=10, anchor="w")

        # Indicador de estado
        estado_fila = tk.Frame(cont, bg=self.SURFACE, highlightbackground=self.BORDE,
                               highlightthickness=1)
        estado_fila.pack(fill="x", pady=(0, 14))
        self.lbl_estado = tk.Label(estado_fila, text="○  Detenido", bg=self.SURFACE,
                                   fg=self.TEXTO2, font=("Consolas", 14, "bold"))
        self.lbl_estado.pack(side="left", padx=14, pady=12)
        self.lbl_panel = tk.Label(estado_fila, text="Panel: cerrado", bg=self.SURFACE,
                                  fg=self.TEXTO2, font=("Segoe UI", 9))
        self.lbl_panel.pack(side="right", padx=14)

        # Consentimiento
        self.var_consent = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(
            cont, variable=self.var_consent, command=self._refrescar_estado,
            bg=self.BG, fg=self.TEXTO, selectcolor=self.SURFACE,
            activebackground=self.BG, activeforeground=self.TEXTO,
            font=("Segoe UI", 9), wraplength=470, justify="left",
            text=("Confirmo que usaré esta herramienta de forma ética y autorizada, "
                  "en mi propio equipo o laboratorio."))
        chk.pack(anchor="w", pady=(0, 12))

        # Botones de captura
        self.btn_iniciar = self._boton(cont, "▶  Iniciar captura", self._iniciar, self.VERDE)
        self.btn_iniciar.pack(fill="x", pady=4)
        self.btn_detener = self._boton(cont, "⏹  Detener captura", self._detener, self.ROJO)
        self.btn_detener.pack(fill="x", pady=4)

        sep = tk.Frame(cont, bg=self.BORDE, height=1)
        sep.pack(fill="x", pady=12)

        # Botones del panel web
        self._boton(cont, "📊  Abrir panel web (solo este equipo)",
                    self._panel_local, self.ACENTO).pack(fill="x", pady=4)
        self._boton(cont, "🌐  Abrir panel web en la red (ver desde el celular)",
                    self._panel_lan, self.ACENTO).pack(fill="x", pady=4)

        sep2 = tk.Frame(cont, bg=self.BORDE, height=1)
        sep2.pack(fill="x", pady=12)

        self._boton(cont, "🗑  Borrar registros locales", self._borrar_logs,
                    self.SURFACE, fg=self.TEXTO).pack(fill="x", pady=4)

        # Info / ayuda
        self.lbl_info = tk.Label(cont, text="", bg=self.BG, fg=self.TEXTO2,
                                 font=("Consolas", 9), justify="left", wraplength=480)
        self.lbl_info.pack(anchor="w", pady=(12, 0))

    def _boton(self, parent, texto, comando, color, fg="#0b1020"):
        return tk.Button(parent, text=texto, command=comando, bg=color, fg=fg,
                         activebackground=color, activeforeground=fg, relief="flat",
                         font=("Segoe UI", 11, "bold"), cursor="hand2", pady=9, bd=0)

    # ------------------------------------------------------------ acciones -- #
    def _capturando(self) -> bool:
        return self.proc_keylogger is not None and self.proc_keylogger.poll() is None

    def _panel_activo(self) -> bool:
        return self.proc_dashboard is not None and self.proc_dashboard.poll() is None

    def _verificar_scripts(self) -> bool:
        faltan = [p for p in (KEYLOGGER, DASHBOARD) if not os.path.exists(p)]
        if faltan:
            messagebox.showerror(
                "Faltan archivos",
                "No encuentro estos archivos junto al panel:\n\n" +
                "\n".join(faltan) +
                "\n\nColoca launcher.py en la misma carpeta que keylogger.py y dashboard.py.")
            return False
        return True

    def _iniciar(self):
        if not self.var_consent.get():
            messagebox.showwarning("Consentimiento requerido",
                                   "Marca la casilla de consentimiento antes de iniciar.")
            return
        if self._capturando():
            return
        if not self._verificar_scripts():
            return
        try:
            self.proc_keylogger = subprocess.Popen(
                [_PYTHON, KEYLOGGER], cwd=_CARPETA, creationflags=_NUEVA_CONSOLA)
        except Exception as e:
            messagebox.showerror("Error al iniciar", str(e))
            return
        self.lbl_info.config(
            text=("Se abrió la consola del keylogger: confirma el aviso escribiendo 'si'.\n"
                  f"Registro: {LOG_TXT}"))
        self._refrescar_estado()

    def _detener(self):
        if self._capturando():
            try:
                self.proc_keylogger.terminate()
            except Exception:
                pass
        self.proc_keylogger = None
        self.lbl_info.config(text="Captura detenida.")
        self._refrescar_estado()

    def _panel_local(self):
        if not self._verificar_scripts():
            return
        if self._panel_activo():
            self.lbl_info.config(text="El panel ya está en ejecución.")
            return
        try:
            self.proc_dashboard = subprocess.Popen(
                [_PYTHON, DASHBOARD], cwd=_CARPETA, creationflags=_SIN_VENTANA)
            self.lbl_info.config(text="Panel local: se abrirá en tu navegador (127.0.0.1:8000).")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        self._refrescar_estado()

    def _panel_lan(self):
        if not self._verificar_scripts():
            return
        aviso = ("Vas a exponer el panel en tu RED LOCAL para verlo desde el celular.\n\n"
                 "El panel muestra datos sensibles (lo tecleado). Cualquiera en la misma "
                 "Wi-Fi que abra la URL podría verlo.\n\n"
                 "Úsalo SOLO en tu red de confianza y ciérralo al terminar. ¿Continuar?")
        if not messagebox.askyesno("Modo red local", aviso):
            return
        if self._panel_activo():
            try:
                self.proc_dashboard.terminate()
            except Exception:
                pass
        try:
            self.proc_dashboard = subprocess.Popen(
                [_PYTHON, DASHBOARD, "--lan"], cwd=_CARPETA, creationflags=_SIN_VENTANA)
            ip = _ip_lan()
            self.lbl_info.config(
                text=(f"Panel en red local activo.\nEn este equipo:  http://127.0.0.1:8000\n"
                      f"Desde el celular (misma Wi-Fi):  http://{ip}:8000"))
            # Abre el panel en el navegador de esta PC (en modo LAN el servidor no lo hace solo).
            try:
                webbrowser.open("http://127.0.0.1:8000")
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", str(e))
        self._refrescar_estado()

    def _borrar_logs(self):
        existentes = [p for p in (LOG_TXT, LOG_JSONL) if os.path.exists(p)]
        if not existentes:
            messagebox.showinfo("Sin registros", "No hay registros que borrar.")
            return
        if self._capturando():
            messagebox.showwarning("Captura activa",
                                   "Detén la captura antes de borrar los registros.")
            return
        if not messagebox.askyesno("Borrar registros",
                                   "¿Seguro que quieres borrar los registros locales?\n"
                                   "Esta acción no se puede deshacer."):
            return
        errores = []
        for p in existentes:
            try:
                os.remove(p)
            except Exception as e:
                errores.append(f"{p}: {e}")
        if errores:
            messagebox.showerror("Error al borrar", "\n".join(errores))
        else:
            self.lbl_info.config(text="Registros borrados.")

    # -------------------------------------------------------------- estado -- #
    def _refrescar_estado(self):
        if self._capturando():
            self.lbl_estado.config(text="●  GRABANDO", fg=self.ROJO)
            self.btn_iniciar.config(state="disabled")
            self.btn_detener.config(state="normal")
        else:
            self.lbl_estado.config(text="○  Detenido", fg=self.TEXTO2)
            estado_btn = "normal" if self.var_consent.get() else "disabled"
            self.btn_iniciar.config(state=estado_btn)
            self.btn_detener.config(state="disabled")
        self.lbl_panel.config(text="Panel: activo" if self._panel_activo() else "Panel: cerrado")

    def _vigilar_procesos(self):
        # Detecta si el keylogger terminó por su cuenta (ESC en su consola).
        self._refrescar_estado()
        self.after(1000, self._vigilar_procesos)

    def _al_cerrar(self):
        if self._capturando() or self._panel_activo():
            if not messagebox.askyesno(
                    "Cerrar",
                    "Hay procesos en ejecución (captura o panel). ¿Cerrar y detenerlos?"):
                return
        for proc in (self.proc_keylogger, self.proc_dashboard):
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        self.destroy()


if __name__ == "__main__":
    Panel().mainloop()
