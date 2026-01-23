WScript.Sleep 1000
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c start_background.bat", 0, False
Set WshShell = Nothing
