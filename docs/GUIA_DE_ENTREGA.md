# Guía de entrega — Trabajo Parcial (Keylogger)

Esta guía cubre los 4 entregables: **Word, GitHub, Video (YouTube) y PPT**, más la preparación de la exposición.

---

## ✅ Checklist de entregables

- [ ] **Word** con: definición, cómo funciona, qué se necesitó, vector de ataque, conclusiones y recomendaciones → `docs/Trabajo_Parcial_Keylogger.docx`
- [ ] **Repositorio de GitHub** con el código (adjuntar el enlace en el Word)
- [ ] **Video en YouTube (privado)** con la demostración — **todos participan**
- [ ] **PPT** resumen → `docs/Keylogger_Presentacion.pptx`
- [ ] Solo **1 integrante** envía el trabajo

> Antes de entregar: reemplaza todos los `[corchetes]` (nombres, universidad, docente, enlaces) en el Word y el PPT.

---

## 1. Subir el código a GitHub

En una terminal, dentro de la carpeta `keylogger-educativo`:

```bash
git init
git add .
git commit -m "Keylogger educativo - Trabajo Parcial de Hacking Etico"
git branch -M main
# Crea primero el repo vacío en github.com (por ejemplo: keylogger-educativo)
git remote add origin https://github.com/USUARIO/keylogger-educativo.git
git push -u origin main
```

> El archivo `.gitignore` evita que se suba `registro_teclas.txt` (que podría tener datos sensibles) y el `__pycache__`.
> Puedes dejar el repo **público** (es material educativo con aviso legal) o **privado** y darle acceso al docente.

Luego pega el enlace del repo en el Word (sección 7) y en la última diapositiva del PPT.

---

## 2. Guion del video de YouTube (demostración)

Sube el video como **NO listado** o **privado** y comparte el acceso con el docente. Duración sugerida: **3–5 min**. Que **cada integrante hable** en la parte indicada.

| Parte | Quién | Qué decir / mostrar |
|-------|-------|---------------------|
| **Intro (30 s)** | Integrante 1 | Saludo, nombre del curso, integrantes y tema: "keylogger educativo". Aclarar que es un ejercicio académico en equipo propio. |
| **Definición (30 s)** | Integrante 2 | Explicar qué es un keylogger y para qué sirve (con apoyo del PPT). |
| **Código (60 s)** | Integrante 3 | Mostrar `keylogger.py` en VS Code: el `Listener` de pynput, `al_presionar`, el guardado local y la tecla ESC. |
| **Demostración (90 s)** | Integrante 1 | Ejecutar `python keylogger.py`, aceptar el consentimiento, escribir en el bloc de notas y en el navegador, presionar ESC y **abrir `registro_teclas.txt`** para mostrar lo capturado (con ventana activa y hora). |
| **Defensa y cierre (45 s)** | Todos | Mencionar 2–3 recomendaciones de defensa y despedirse. |

**Antes de grabar:** `pip install -r requirements.txt`. Graba la pantalla con la grabadora de Windows (Win+G) o con OBS.

---

## 3. Preparación de la exposición — posibles preguntas del docente

El representante debe responder 3 preguntas. Estas son las más probables:

**P1. ¿Qué diferencia hay entre un keylogger de software y uno de hardware?**
> El de software es un programa que se engancha a los eventos del teclado del sistema operativo; se puede detectar con un antivirus y eliminar. El de hardware es un dispositivo físico entre el teclado y el equipo (o dentro del teclado); no lo detecta el antivirus y solo se descubre por inspección física.

**P2. ¿Cómo se distribuye/instala un keylogger real en la víctima?**
> Principalmente por ingeniería social: phishing con adjuntos maliciosos, software pirata troyanizado o dispositivos USB (BadUSB). Requiere que la víctima ejecute el archivo; por eso la concientización es clave.

**P3. ¿Cómo se defiende un usuario de un keylogger?**
> Antivirus/EDR actualizado, no ejecutar archivos desconocidos, **autenticación multifactor (MFA)** —para que la contraseña robada no baste—, gestores de contraseñas/teclados virtuales y monitoreo de procesos.

**P4. ¿Por qué su keylogger pide consentimiento y guarda todo localmente?**
> Porque es un proyecto educativo y ético: no se implementaron técnicas de sigilo, propagación ni envío de datos por la red. Solo demuestra el concepto en un entorno controlado y autorizado.

**P5. ¿Qué librería usaron y por qué?**
> `pynput`, porque permite capturar eventos globales del teclado de forma sencilla y multiplataforma, ideal para un ejercicio didáctico.

**P6. ¿Es legal hacer esto? / ¿Qué dice la ley?**
> Usarlo en tu propio equipo o en un laboratorio autorizado es legal y es práctica común en formación de seguridad. Espiar a terceros sin consentimiento es delito (en Perú, Ley N.° 30096 de Delitos Informáticos).

> **Consejo:** la exposición es formal. Vístanse formal, hablen con seguridad, no lean la diapositiva palabra por palabra y usen las notas del PPT (ya incluidas en cada slide).
