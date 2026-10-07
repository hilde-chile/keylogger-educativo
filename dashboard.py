#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  PANEL WEB LOCAL  -  Keylogger Educativo (Curso de Hacking Ético)
================================================================================
  ¿QUÉ HACE?
  ----------
  Levanta un pequeño servidor web LOCAL (solo en 127.0.0.1) que LEE el archivo
  `registro_teclas.txt` generado por keylogger.py y lo muestra de forma
  organizada y profesional en el navegador.

  IMPORTANTE (privacidad):
  - Este panel NO captura nada: únicamente LEE y MUESTRA lo ya registrado.
  - Escucha SOLO en 127.0.0.1 (localhost). No es accesible desde la red.
  - No usa Flask, ni CDNs, ni fuentes externas: todo es local y autocontenido.
    Nada sale ni entra de tu equipo.

  USO:
      python dashboard.py            # abre http://127.0.0.1:8000
      python dashboard.py 8080       # usa otro puerto

  Detén el servidor con Ctrl+C.
================================================================================
"""

import os
import re
import sys
import json
import html
import datetime
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# --------------------------------------------------------------------------- #
# Rutas
# --------------------------------------------------------------------------- #
_CARPETA = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(_CARPETA, "web")
ARCHIVO_LOG = os.path.join(_CARPETA, "registro_teclas.txt")      # legible (fallback)
ARCHIVO_JSONL = os.path.join(_CARPETA, "registro_teclas.jsonl")  # estructurado (preferido)

HOST = "127.0.0.1"          # Por defecto SOLO localhost. Con --lan escucha en la red local.
PUERTO_POR_DEFECTO = 8000


# --------------------------------------------------------------------------- #
# Parser del registro legible (registro_teclas.txt)
# --------------------------------------------------------------------------- #
#
# El keylogger escribe marcadores en líneas propias:
#   [YYYY-MM-DD HH:MM:SS] === Nueva sesión de captura iniciada ===
#   [YYYY-MM-DD HH:MM:SS] --- Ventana activa: <título> ---
#   [YYYY-MM-DD HH:MM:SS] === Captura detenida por el usuario (ESC) ===
# Entre marcador y marcador va el texto tecleado en crudo; las teclas
# especiales aparecen como [nombre] (p. ej. [backspace], [esc], [shift]).
# --------------------------------------------------------------------------- #

_MARCADOR = re.compile(
    r"^\[(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] "
    r"(?:=== (?P<inicio>Nueva sesión de captura iniciada) ==="
    r"|=== (?P<fin>Captura detenida por el usuario \(ESC\)) ==="
    r"|--- Ventana activa: (?P<ventana>.*?) ---)\s*$",
    re.MULTILINE,
)

_SEPARADOR = re.compile(r"^=+\s*$", re.MULTILINE)   # líneas de "===..." decorativas
_TOKEN = re.compile(r"\[[^\]\n]*\]|[\s\S]")          # un [especial] o un carácter


def _reconstruir(texto_crudo: str):
    """Convierte texto crudo (con tokens [especial]) en:
       - texto reconstruido (aplicando backspace y descartando modificadores),
       - nº de caracteres imprimibles,
       - nº de teclas especiales,
       - conteo por nombre de tecla especial.
    """
    resultado = []
    n_chars = 0
    n_especiales = 0
    conteo_especiales = {}

    # Modificadores/teclas que no aportan texto visible al reconstruir.
    ignorar = {
        "shift", "shift_r", "shift_l", "ctrl", "ctrl_l", "ctrl_r",
        "alt", "alt_l", "alt_r", "alt_gr", "cmd", "cmd_l", "cmd_r",
        "caps_lock", "num_lock", "esc",
    }

    for token in _TOKEN.findall(texto_crudo):
        if len(token) > 1 and token.startswith("[") and token.endswith("]"):
            nombre = token[1:-1]
            n_especiales += 1
            conteo_especiales[nombre] = conteo_especiales.get(nombre, 0) + 1
            if nombre == "backspace" and resultado:
                resultado.pop()
            elif nombre not in ignorar and nombre not in ("backspace",):
                resultado.append(" ")  # otras especiales -> espacio de contexto
        else:
            # carácter literal (incluye espacio, salto de línea, tab)
            if token not in ("\r",):
                resultado.append(token)
            if not token.isspace():
                n_chars += 1
            elif token in (" ", "\n", "\t"):
                n_chars += 1  # contamos espacios/enter/tab como pulsaciones útiles

    return "".join(resultado), n_chars, n_especiales, conteo_especiales


def _duracion_humana(inicio: str, fin: str):
    """Diferencia legible entre dos marcas de tiempo 'YYYY-MM-DD HH:MM:SS'."""
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        d = datetime.datetime.strptime(fin, fmt) - datetime.datetime.strptime(inicio, fmt)
    except Exception:
        return None
    seg = int(d.total_seconds())
    if seg < 0:
        return None
    h, resto = divmod(seg, 3600)
    m, s = divmod(resto, 60)
    partes = []
    if h:
        partes.append(f"{h} h")
    if m:
        partes.append(f"{m} min")
    partes.append(f"{s} s")
    return " ".join(partes)


def _analizar_txt():
    """Lee y analiza registro_teclas.txt -> estructura lista para el panel.

    Se conserva como PLAN B (compatibilidad): si aún no hay .jsonl estructurado
    pero sí un .txt de una versión anterior, el panel sigue funcionando.
    """
    if not os.path.exists(ARCHIVO_LOG):
        return {"has_data": False, "generated_at": _ahora(), "message": "Aún no existe registro_teclas.txt. Ejecuta primero keylogger.py."}

    with open(ARCHIVO_LOG, "r", encoding="utf-8", errors="replace") as f:
        contenido = f.read()

    marcadores = list(_MARCADOR.finditer(contenido))
    if not marcadores:
        return {"has_data": False, "generated_at": _ahora(), "message": "El registro existe pero no contiene sesiones reconocibles."}

    sesiones = []
    segmentos = []
    ventanas_agg = {}
    especiales_agg = {}
    total_chars = 0
    total_especiales = 0
    primer_ts = None
    ultimo_ts = None

    sesion_actual = None
    ventana_actual = "(sin ventana)"

    def cerrar_sesion(fin_ts=None):
        if sesion_actual is not None:
            sesion_actual["stop"] = fin_ts
            if fin_ts:
                sesion_actual["duration"] = _duracion_humana(sesion_actual["start"], fin_ts)
            sesiones.append(sesion_actual)

    for i, m in enumerate(marcadores):
        ts = m.group("ts")
        primer_ts = primer_ts or ts
        ultimo_ts = ts

        # Texto tecleado entre este marcador y el siguiente.
        ini = m.end()
        fin_pos = marcadores[i + 1].start() if i + 1 < len(marcadores) else len(contenido)
        crudo = contenido[ini:fin_pos]
        crudo = _SEPARADOR.sub("", crudo).strip("\n")

        if m.group("inicio"):
            cerrar_sesion()
            sesion_actual = {
                "index": len(sesiones) + 1,
                "start": ts, "stop": None, "duration": None,
                "events": 0, "chars": 0, "specials": 0, "windows": set(),
            }
            ventana_actual = "(sin ventana)"
        elif m.group("fin"):
            cerrar_sesion(ts)
            sesion_actual = None
            continue
        elif m.group("ventana") is not None:
            ventana_actual = m.group("ventana") or "(sin título)"

        if sesion_actual is None:
            # Datos sueltos sin sesión abierta: creamos una implícita.
            sesion_actual = {
                "index": len(sesiones) + 1,
                "start": ts, "stop": None, "duration": None,
                "events": 0, "chars": 0, "specials": 0, "windows": set(),
            }

        if not crudo.strip():
            continue

        texto, n_chars, n_esp, conteo = _reconstruir(crudo)
        if n_chars == 0 and n_esp == 0:
            continue

        total_chars += n_chars
        total_especiales += n_esp
        sesion_actual["chars"] += n_chars
        sesion_actual["specials"] += n_esp
        sesion_actual["events"] += n_chars + n_esp
        sesion_actual["windows"].add(ventana_actual)

        agg = ventanas_agg.setdefault(ventana_actual, {"window": ventana_actual, "chars": 0, "specials": 0, "events": 0})
        agg["chars"] += n_chars
        agg["specials"] += n_esp
        agg["events"] += n_chars + n_esp

        for k, v in conteo.items():
            especiales_agg[k] = especiales_agg.get(k, 0) + v

        segmentos.append({
            "session": sesion_actual["index"],
            "ts": ts,
            "window": ventana_actual,
            "text": texto,
            "chars": n_chars,
            "specials": n_esp,
        })

    cerrar_sesion(ultimo_ts if sesion_actual and sesion_actual.get("stop") is None else None)

    # Normalizar sesiones (set -> lista/conteo).
    for s in sesiones:
        s["windows_count"] = len(s["windows"])
        s["windows"] = sorted(w for w in s["windows"] if w != "(sin ventana)")

    ventanas = sorted(ventanas_agg.values(), key=lambda x: x["events"], reverse=True)
    especiales = sorted(
        ({"key": k, "count": v} for k, v in especiales_agg.items()),
        key=lambda x: x["count"], reverse=True,
    )

    return {
        "has_data": True,
        "generated_at": _ahora(),
        "stats": {
            "total_events": total_chars + total_especiales,
            "total_chars": total_chars,
            "total_specials": total_especiales,
            "windows_count": len(ventanas),
            "sessions_count": len(sesiones),
            "first_ts": primer_ts,
            "last_ts": ultimo_ts,
            "duration": _duracion_humana(primer_ts, ultimo_ts) if primer_ts and ultimo_ts else None,
        },
        "sessions": sesiones,
        "windows": ventanas,
        "special_keys": especiales,
        "segments": segmentos,
    }


def _analizar_jsonl():
    """Lee y analiza registro_teclas.jsonl (formato preferido) -> estructura panel.

    Cada línea es un evento JSON escrito por registro.py. Al ser datos ya
    estructurados, la reconstrucción es directa y fiable: se usa el campo
    ``text`` de cada tecla y se aplica retroceso (backspace). Las líneas
    corruptas (p. ej. por un cierre abrupto) se ignoran sin romper el análisis.
    """
    eventos = []
    with open(ARCHIVO_JSONL, "r", encoding="utf-8", errors="replace") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                eventos.append(json.loads(linea))
            except json.JSONDecodeError:
                continue  # robustez ante una última línea incompleta

    if not eventos:
        return {"has_data": False, "generated_at": _ahora(),
                "message": "El registro estructurado existe pero está vacío."}

    sesiones = []
    segmentos = []
    ventanas_agg = {}
    especiales_agg = {}
    total_chars = 0
    total_especiales = 0
    primer_ts = None
    ultimo_ts = None

    sesion_actual = None
    ventana_actual = "(sin ventana)"
    seg_actual = None

    def nueva_sesion(ts):
        return {"index": len(sesiones) + 1, "start": ts, "stop": None,
                "duration": None, "events": 0, "chars": 0, "specials": 0,
                "windows": set()}

    def cerrar_sesion(fin_ts=None):
        nonlocal sesion_actual
        if sesion_actual is not None:
            if fin_ts:
                sesion_actual["stop"] = fin_ts
                sesion_actual["duration"] = _duracion_humana(sesion_actual["start"], fin_ts)
            sesiones.append(sesion_actual)
            sesion_actual = None

    def flush_seg():
        nonlocal seg_actual
        if seg_actual is not None:
            if seg_actual["chars"] or seg_actual["specials"]:
                segmentos.append({
                    "session": seg_actual["session"],
                    "ts": seg_actual["ts"],
                    "window": seg_actual["window"],
                    "text": "".join(seg_actual["_buf"]),
                    "chars": seg_actual["chars"],
                    "specials": seg_actual["specials"],
                })
            seg_actual = None

    for ev in eventos:
        ts = ev.get("ts")
        if ts:
            primer_ts = primer_ts or ts
            ultimo_ts = ts
        tipo = ev.get("type")

        if tipo == "session_start":
            flush_seg()
            cerrar_sesion()
            sesion_actual = nueva_sesion(ts)
            ventana_actual = "(sin ventana)"
            continue
        if tipo == "session_stop":
            flush_seg()
            cerrar_sesion(ts)
            continue
        if tipo == "window":
            w = ev.get("window") or "(sin título)"
            if w != ventana_actual:
                flush_seg()
                ventana_actual = w
            continue
        if tipo in ("session_pause", "session_resume", "note"):
            flush_seg()  # una interrupción corta el segmento actual
            continue
        if tipo != "key":
            continue

        # --- Evento de tecla ---
        if sesion_actual is None:
            sesion_actual = nueva_sesion(ts)   # datos sin sesión abierta: implícita
        w = ev.get("window") or ventana_actual
        if w != ventana_actual:
            flush_seg()
            ventana_actual = w
        if seg_actual is None:
            seg_actual = {"session": sesion_actual["index"], "ts": ts,
                          "window": ventana_actual, "_buf": [],
                          "chars": 0, "specials": 0}

        especial = bool(ev.get("special"))
        combo = bool(ev.get("combo"))
        key = ev.get("key", "")
        texto = ev.get("text", "")
        es_char = not especial and not combo

        # Reconstrucción del texto (aplica retroceso).
        if key == "backspace":
            if seg_actual["_buf"]:
                seg_actual["_buf"].pop()
        elif texto:
            seg_actual["_buf"].append(texto)

        # Conteos.
        if es_char:
            total_chars += 1
            seg_actual["chars"] += 1
            sesion_actual["chars"] += 1
        else:
            total_especiales += 1
            seg_actual["specials"] += 1
            sesion_actual["specials"] += 1
            especiales_agg[key or "(?)"] = especiales_agg.get(key or "(?)", 0) + 1

        sesion_actual["events"] += 1
        sesion_actual["windows"].add(ventana_actual)

        agg = ventanas_agg.setdefault(
            ventana_actual,
            {"window": ventana_actual, "chars": 0, "specials": 0, "events": 0},
        )
        agg["chars" if es_char else "specials"] += 1
        agg["events"] += 1

    flush_seg()
    cerrar_sesion(ultimo_ts if (sesion_actual and sesion_actual.get("stop") is None) else None)

    for s in sesiones:
        s["windows_count"] = len(s["windows"])
        s["windows"] = sorted(w for w in s["windows"] if w != "(sin ventana)")

    ventanas = sorted(ventanas_agg.values(), key=lambda x: x["events"], reverse=True)
    especiales = sorted(
        ({"key": k, "count": v} for k, v in especiales_agg.items()),
        key=lambda x: x["count"], reverse=True,
    )

    return {
        "has_data": True,
        "generated_at": _ahora(),
        "source": "jsonl",
        "stats": {
            "total_events": total_chars + total_especiales,
            "total_chars": total_chars,
            "total_specials": total_especiales,
            "windows_count": len(ventanas),
            "sessions_count": len(sesiones),
            "first_ts": primer_ts,
            "last_ts": ultimo_ts,
            "duration": _duracion_humana(primer_ts, ultimo_ts) if primer_ts and ultimo_ts else None,
        },
        "sessions": sesiones,
        "windows": ventanas,
        "special_keys": especiales,
        "segments": segmentos,
    }


def analizar_registro():
    """Devuelve los datos para el panel, prefiriendo el .jsonl estructurado.

    Orden de preferencia:
      1. registro_teclas.jsonl  (estructurado, escrito por registro.py)
      2. registro_teclas.txt    (legible, compatibilidad con versiones previas)
    """
    if os.path.exists(ARCHIVO_JSONL) and os.path.getsize(ARCHIVO_JSONL) > 0:
        try:
            return _analizar_jsonl()
        except Exception as e:  # nunca dejar caer el servidor por un dato raro
            return {"has_data": False, "generated_at": _ahora(),
                    "message": f"No se pudo analizar el .jsonl: {e}"}
    return _analizar_txt()


def _ahora():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------- #
# Servidor HTTP
# --------------------------------------------------------------------------- #
class Handler(SimpleHTTPRequestHandler):
    """Sirve la carpeta web/ y expone la API local /api/data."""

    def do_GET(self):
        if self.path.split("?")[0] == "/api/data":
            self._enviar_json(analizar_registro())
            return
        return super().do_GET()

    def _enviar_json(self, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, formato, *args):
        # Log discreto en consola.
        sys.stderr.write("  [web] %s\n" % (formato % args))


def _elegir_puerto(preferido):
    """Devuelve el primer puerto libre a partir del preferido."""
    import socket
    for puerto in range(preferido, preferido + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", puerto)) != 0:  # no hay nadie escuchando
                return puerto
    return preferido


def _ip_lan():
    """IP de este equipo en la red local (para abrir el panel desde el celular).

    NO transmite datos: en un socket UDP, connect() solo hace que el sistema
    elija qué interfaz de red usaría; no se envía ningún paquete a 8.8.8.8.
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    if not os.path.isdir(WEB_DIR):
        print(f"[!] No se encontró la carpeta web/ en: {WEB_DIR}")
        sys.exit(1)

    # --- Argumentos: puerto (número) y modo red local (--lan / --red) ---
    modo_lan = any(a in ("--lan", "--red") for a in sys.argv[1:])
    preferido = PUERTO_POR_DEFECTO
    for a in sys.argv[1:]:
        if a.isdigit():
            preferido = int(a)

    # Host de escucha: por defecto solo este equipo; con --lan, toda la red local.
    bind_host = "0.0.0.0" if modo_lan else "127.0.0.1"
    puerto = _elegir_puerto(preferido)

    handler = partial(Handler, directory=WEB_DIR)
    servidor = ThreadingHTTPServer((bind_host, puerto), handler)

    print("=" * 64)
    print("  PANEL WEB LOCAL - Keylogger Educativo")
    print("=" * 64)
    print(f"  En este equipo:    http://127.0.0.1:{puerto}")
    if modo_lan:
        ip = _ip_lan()
        print(f"  Desde el celular:  http://{ip}:{puerto}   (conéctate a la MISMA Wi-Fi)")
        print("  " + "-" * 60)
        print("  [!] MODO RED LOCAL ACTIVADO")
        print("      El panel muestra datos SENSIBLES (todo lo que se tecleó).")
        print("      Cualquiera en esta misma Wi-Fi que abra la URL podría verlo.")
        print("      Úsalo SOLO en tu red de confianza (o tu propio hotspot),")
        print("      durante la demo, y ciérralo con Ctrl+C al terminar.")
        print("      En Wi-Fi público (universidad, café) NO lo actives.")
    else:
        print("  Solo localhost (127.0.0.1). Nada sale por la red.")
        print("  ¿Verlo desde el celular en tu Wi-Fi?  ->  python dashboard.py --lan")
    _fuente = ARCHIVO_JSONL if (os.path.exists(ARCHIVO_JSONL) and os.path.getsize(ARCHIVO_JSONL) > 0) else ARCHIVO_LOG
    print(f"  Leyendo:           {_fuente}")
    print("  Detén el servidor con Ctrl+C.")
    print("=" * 64)

    # Solo abrimos el navegador local automáticamente (no en modo LAN).
    if not modo_lan:
        try:
            webbrowser.open(f"http://127.0.0.1:{puerto}")
        except Exception:
            pass

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Servidor detenido.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
