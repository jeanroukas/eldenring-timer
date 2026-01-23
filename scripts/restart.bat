@echo off
ping 127.0.0.1 -n 2 > nul
start "" "..\start_background.bat"
exit
