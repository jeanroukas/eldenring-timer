@echo off
echo Launching Elden Ring Timer (Debug Mode)...
echo Time: %TIME% > launch_log.txt
python main.py >> launch_log.txt 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo CRASHED with code %ERRORLEVEL% >> launch_log.txt
)
