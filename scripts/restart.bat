@echo off
ping 127.0.0.1 -n 2 > nul
cd /d "%~dp0.."
start "" pythonw main.py
exit
