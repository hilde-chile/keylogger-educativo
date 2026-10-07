# Keylogger Educativo — Curso de Hacking Ético

> ⚠️ **Aviso legal y ético:** Este proyecto es **exclusivamente educativo**. Fue creado
> para comprender el funcionamiento interno de un keylogger y, sobre todo, **cómo
> defenderse** de esta amenaza. Úsalo **únicamente en tu propio equipo o en un
> laboratorio autorizado**. Registrar las pulsaciones de otra persona sin su
> consentimiento es **ilegal** (en Perú, **Ley N.° 30096** de Delitos Informáticos,
> modificada por la Ley N.° 30171).

## 📋 Descripción

Un **keylogger** (registrador de teclas) captura y almacena las pulsaciones del teclado.
Este proyecto implementa una versión **didáctica y transparente**, diseñada a propósito en
la **dirección opuesta a un malware**:

- Muestra un **aviso de consentimiento** y exige confirmación explícita al iniciar.
- Enseña un **indicador visible y persistente** de que está grabando (y un recordatorio
  periódico), nunca captura en silencio.
- Guarda todo de forma **100 % local** en dos archivos (`.txt` y `.jsonl`); **no abre
  sockets ni envía nada por la red**.
- **No se oculta, no persiste, no se disfraza.** Se detiene con una tecla.
- Incluye **salvaguardas de privacidad**: pausa/reanudación, auto-detención por tiempo,
  exclusión de ventanas sensibles (gestores de contraseñas) y borrado seguro de registros.

## ✨ Novedades de esta versión

- **Precisión de captura:** mayúsculas (Shift), símbolos de **AltGr** (`@`, `€`…), teclas
  muertas/acentos (`á`, `ñ`, `ü`) y combinaciones legibles (`[Ctrl+C]`, `[Alt+Tab]`).
- **Salida estructurada** `registro_teclas.jsonl` (una línea JSON por evento) además del
  `.txt` legible. El panel web consume el `.jsonl`.
- **Arquitectura modular** con *type hints*, *docstrings* y `logging`.
- **Configuración benigna** por `config.json` y argumentos de línea de comandos.
- **Pruebas con `pytest`** que no requieren teclado físico.

## 🗂️ Estructura del proyecto

```
keylogger-educativo/
├── keylogger.py     # Orquestador: consentimiento, ciclo de vida, pausa, señales
├── captura.py       # Formateo de teclas: carácter / especial / combinación (testeable)
├── registro.py      # Escritura robusta del .txt (legible) y .jsonl (estructurado)
├── ventana.py       # Título de la ventana activa (ctypes en Windows, PyWinCtl opcional)
├── config.py        # Opciones benignas (config.json + CLI) con validación
├── dashboard.py     # Servidor web LOCAL que LEE los registros y expone /api/data
├── web/             # Front-end del panel (HTML/CSS/JS puro, sin CDNs)
├── config.json      # Configuración de ejemplo (valores por defecto)
├── tests/           # Pruebas con pytest (lógica pura, sin hardware)
└── requirements.txt
```

## 🧩 Requisitos

| Requisito | Detalle |
|-----------|---------|
| Lenguaje  | Python 3.9+ |
| Obligatoria | [`pynput`](https://pypi.org/project/pynput/) (captura de eventos de teclado) |
| Opcional  | [`pywinctl`](https://pypi.org/project/PyWinCtl/) → título de ventana multiplataforma |
| Opcional  | [`pytest`](https://pypi.org/project/pytest/) → ejecutar las pruebas |
| Sistema   | Windows / Linux / macOS (en Windows el título de ventana funciona sin instalar nada) |

## 🚀 Instalación y uso

```bash
# 1. (Opcional) Entorno virtual
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate      # Linux/macOS

# 2. Dependencias
pip install -r requirements.txt

# 3. Ejecutar
python keylogger.py
```

Confirma el aviso de consentimiento, escribe con normalidad y **detén con `ESC`**
(pausa/reanuda con `F9`). El resultado queda en `registro_teclas.txt` y
`registro_teclas.jsonl`.

### Opciones de línea de comandos

```bash
python keylogger.py --help
python keylogger.py --duracion 5            # auto-detención a los 5 minutos
python keylogger.py --tecla-salir f12       # cambia la tecla de salida
python keylogger.py --sin-ventanas          # no registrar títulos de ventana
python keylogger.py --recordatorio 1        # recordatorio "GRABANDO" cada 1 min
python keylogger.py --crear-config          # escribe un config.json de ejemplo
python keylogger.py --borrar-registros      # borra de forma segura los registros
```

### Configuración (`config.json`)

Prioridad: **valores por defecto  <  `config.json`  <  argumentos CLI**.

| Clave | Descripción | Por defecto |
|-------|-------------|-------------|
| `archivo_txt` / `archivo_jsonl` | Rutas de salida | `registro_teclas.txt` / `.jsonl` |
| `tecla_salir` | Tecla que detiene la captura | `esc` |
| `tecla_pausa` | Tecla que pausa/reanuda | `f9` |
| `registrar_ventanas` | Registrar el título de la ventana activa | `true` |
| `duracion_maxima_min` | Auto-detención en minutos (`0` = sin límite) | `0` |
| `intervalo_recordatorio_min` | Recordatorio "GRABANDO" cada N min (`0` = off) | `2` |
| `ventanas_excluidas` | Subcadenas que **pausan** la captura (p. ej. gestores de contraseñas) | lista de gestores comunes |

> **Por qué estas opciones y no otras:** todas aumentan el control, la transparencia o la
> privacidad. **No existe** —ni existirá— ninguna opción de sigilo, persistencia o red;
> eso queda fuera del alcance del proyecto (se explica solo de forma conceptual, ver
> *Vector de ataque*).

## 🧾 Formato del registro estructurado (`.jsonl`)

Un objeto JSON por línea. Es lo que consume el panel web (fácil de analizar y graficar):

```jsonc
{"ts": "2026-09-28 14:24:34", "type": "session_start", "meta": {"usuario": "...", "equipo": "...", "sistema": "...", "consentimiento": "..."}}
{"ts": "2026-09-28 14:24:35", "type": "window", "window": "Bloc de notas"}
{"ts": "2026-09-28 14:24:36", "type": "key", "window": "Bloc de notas", "key": "h", "special": false, "combo": false, "text": "h"}
{"ts": "2026-09-28 14:24:37", "type": "key", "window": "Bloc de notas", "key": "Ctrl+C", "special": false, "combo": true, "text": ""}
{"ts": "2026-09-28 14:24:38", "type": "key", "window": "Bloc de notas", "key": "backspace", "special": true, "combo": false, "text": ""}
{"ts": "2026-09-28 14:29:13", "type": "session_stop", "reason": "tecla ESC"}
```

| Campo | Significado |
|-------|-------------|
| `ts` | Marca de tiempo local `YYYY-MM-DD HH:MM:SS` |
| `type` | `session_start` · `window` · `key` · `note` · `session_pause` · `session_resume` · `session_stop` |
| `window` | Título de la ventana activa en ese momento |
| `key` | Nombre canónico: `a`, `enter`, `Ctrl+C`… |
| `special` | `true` si es una tecla especial (Enter, Backspace, Esc…) |
| `combo` | `true` si es una combinación (Ctrl/Alt/Cmd + tecla) |
| `text` | Aporte a la reconstrucción del texto (`"a"`, `"\n"`, o `""`) |

El `.txt` legible se mantiene en paralelo para leer "de un vistazo". Ambos se escriben con
*flush* tras cada evento, de modo que un cierre abrupto pierda, como mucho, la última tecla.

## 📊 Panel web local (dashboard)

```bash
python dashboard.py            # abre http://127.0.0.1:8000
# python dashboard.py 8080     # otro puerto si el 8000 está ocupado
```

El panel **prefiere** `registro_teclas.jsonl` y, si no existe, recurre al `.txt`
(compatibilidad). Muestra:

- **Tarjetas** con totales: pulsaciones, caracteres, especiales, ventanas, sesiones y duración.
- **Gráficos SVG** de actividad por ventana, composición y teclas especiales más usadas.
- **Línea de tiempo** de cada sesión, con duración y ventanas.
- **Registro por ventana** con el texto reconstruido (aplica retroceso `⌫`), buscador,
  vista de tabla ordenable y exportación a CSV.

> 🔒 **Privacidad y alcance:** el panel **no captura nada**, solo lee y muestra. Por defecto
> escucha **solo en `127.0.0.1` (localhost)** y **no usa CDNs ni fuentes externas**. Detén
> el servidor con `Ctrl+C`. *(El modo opcional `--lan` sirve el panel en tu red local para
> verlo desde el móvil; úsalo solo en una red de confianza, ya que muestra datos sensibles.)*

## ✅ Pruebas

```bash
pip install pytest
pytest -q
```

Cubren la lógica que **no** depende del teclado físico (se simulan los eventos): formateo de
teclas (mayúsculas, AltGr, acentos, combinaciones), serialización JSONL, reconstrucción de
texto con retroceso, carga/validación de la configuración y cálculo de duraciones.

## ⚙️ ¿Cómo funciona? (flujo técnico)

```
   teclado físico
        │  (el sistema operativo entrega eventos de tecla)
        ▼
   pynput.keyboard.Listener   ← corre en un hilo aparte
        │
        ├─ on_press(tecla) ─────────────┐
        └─ on_release(tecla)            │  (actualiza el estado de modificadores)
                                        ▼
                          captura.Teclado.presionar()
                                        │  clasifica:
                                        │   • carácter imprimible  → "a", "ñ", "@"
                                        │   • tecla especial        → [enter], [esc]
                                        │   • combinación           → [Ctrl+C], [Alt+Tab]
                                        │   • tecla muerta + vocal   → compone "á"
                                        ▼
                                 EventoTecla
                                        │
                                        ▼
                             registro.Registrador
                          ┌─────────────┴──────────────┐
                          ▼                            ▼
              registro_teclas.txt           registro_teclas.jsonl
                (legible)                      (estructurado)
                                                     │
                                                     ▼
                              dashboard.py  →  /api/data  →  panel web (LOCAL)
```

**Decisiones de diseño (el porqué, no solo el qué):**
- Los **modificadores sueltos** (Shift/Ctrl…) se registran para estadística, pero con
  `text=""`, para no ensuciar la reconstrucción del texto.
- **AltGr** se trata como productor de símbolos (no como atajo), porque en Windows
  AltGr = Ctrl_izq + Alt_der; de lo contrario `@` o `€` se confundirían con `Ctrl+algo`.
- Las **teclas muertas** (acentos) se componen con la API `KeyCode.join` de pynput
  (histórico *issue #118*), degradando con elegancia si la composición falla.
- Los *callbacks* van envueltos en `try/except`: un fallo puntual **no** tumba el listener.

## 🎯 Vector de ataque (contexto de la exposición — solo teoría)

En un escenario real (malicioso), un keylogger suele distribuirse y sostenerse mediante:

- **Phishing / adjuntos** (un ejecutable disfrazado de documento, instalador o "crack").
- **Ingeniería social** y dispositivos USB (*BadUSB*, *Rubber Ducky*).
- **Persistencia** (arranque, tareas programadas, servicios) y **ocultación** de procesos.
- **Exfiltración** de datos por red (HTTP, correo, DNS, Telegram…).

> Este proyecto **no** implementa —ni implementará— técnicas de sigilo, persistencia,
> propagación, evasión ni exfiltración. Esas técnicas se describen **solo de forma
> conceptual** en la exposición, para entender la amenaza y defenderse; **no** viven en el
> código.

## 🛡️ Recomendaciones de defensa

- Antivirus/EDR actualizado y con análisis de comportamiento.
- No abrir adjuntos ni ejecutar software de origen desconocido.
- **Autenticación multifactor (MFA):** aunque roben la contraseña, no basta.
- Teclados virtuales / gestores de contraseñas para datos críticos.
- Monitoreo de procesos y de conexiones de red inusuales.
- Principio de mínimo privilegio y actualizaciones del sistema.

## 🔐 Nota sobre los registros

Los archivos `registro_teclas.txt` y `.jsonl` **pueden contener datos sensibles**
(lo que se tecleó). Están en `.gitignore` para no subirlos por accidente. Bórralos con
`python keylogger.py --borrar-registros` cuando termines la demo.

> El borrado sobrescribe el contenido y elimina el archivo. En discos **SSD** la
> sobrescritura no garantiza el borrado físico (por el *wear leveling* de las celdas);
> para una demo educativa es suficiente, pero conviene conocer la limitación.

## 👥 Integrantes

- <Nombre 1>
- <Nombre 2>
- <Nombre 3>

## 📄 Licencia

Uso educativo. Los autores no se responsabilizan por el mal uso de este software.
