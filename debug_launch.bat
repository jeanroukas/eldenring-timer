@echo off
echo Starting Elden Ring Timer (Diagnostic Mode)...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo CRASH DETECTED! Exit Code: %ERRORLEVEL%
    echo Check application.jsonl for crash details
    pause
) else (
    echo App closed normally.
)
