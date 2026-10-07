@echo off
rem ==========================================================================
rem  Keylogger Educativo - Menu de inicio (uso educativo y local)
rem  Doble clic para abrir este menu. Necesita Python + pynput instalados.
rem  Este archivo solo LANZA los scripts; no cambia su comportamiento.
rem ==========================================================================
chcp 65001 >nul
title Keylogger Educativo - Menu
cd /d "%~dp0"

:menu
cls
echo ============================================================
echo   KEYLOGGER EDUCATIVO - Menu  (uso educativo y local)
echo ============================================================
echo.
echo   1. Iniciar captura (keylogger)
echo   2. Abrir panel web (solo este equipo)
echo   3. Abrir panel web en la red (ver desde el celular)
echo   4. Abrir panel de control (interfaz grafica)
echo   5. Borrar registros locales
echo   6. Salir
echo.
echo ============================================================
set /p "op=Elige una opcion (1-6): "

if "%op%"=="1" ( python keylogger.py & echo. & pause & goto menu )
if "%op%"=="2" ( start "" python dashboard.py & goto menu )
if "%op%"=="3" ( start "" python dashboard.py --lan & goto menu )
if "%op%"=="4" ( start "" python launcher.py & goto menu )
if "%op%"=="5" ( goto borrar )
if "%op%"=="6" ( exit /b )
goto menu

:borrar
echo.
set /p "c=Seguro que quieres borrar los registros? (s/n): "
if /i "%c%"=="s" (
  if exist registro_teclas.txt   del registro_teclas.txt
  if exist registro_teclas.jsonl del registro_teclas.jsonl
  echo Registros borrados.
  pause
)
goto menu
