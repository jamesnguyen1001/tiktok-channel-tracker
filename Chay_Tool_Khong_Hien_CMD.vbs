Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
CurrentDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = CurrentDir

If Not FSO.FileExists(CurrentDir & "\data\.playwright_ready") Then
    WshShell.Run "cmd.exe /c Chay_Tool.bat", 1, False
Else
    ExitCode = WshShell.Run("pythonw app.py", 0, False)
End If
