Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
CurrentDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = CurrentDir

Function FindPythonW()
    Dim LocalAppData, PyRoot, SubFolder, Candidate
    LocalAppData = WshShell.ExpandEnvironmentStrings("%LocalAppData%")
    PyRoot = LocalAppData & "\Programs\Python"
    FindPythonW = ""

    If FSO.FolderExists(PyRoot) Then
        For Each SubFolder In FSO.GetFolder(PyRoot).SubFolders
            Candidate = SubFolder.Path & "\pythonw.exe"
            If FSO.FileExists(Candidate) Then
                FindPythonW = Candidate
            End If
        Next
    End If
End Function

Dim PyWPath
PyWPath = FindPythonW()

On Error Resume Next
Err.Clear

' Luu y: pythonw.exe la ung dung GUI (khong co CMD), phai truyen 1 (SW_SHOWNORMAL) de PyQt6 hien cua so Giao dien!
If PyWPath <> "" Then
    WshShell.Run """" & PyWPath & """ """ & CurrentDir & "\app.py""", 1, False
Else
    WshShell.Run "pythonw.exe """ & CurrentDir & "\app.py""", 1, False
    If Err.Number <> 0 Then
        Err.Clear
        WshShell.Run "pyw.exe -3 """ & CurrentDir & "\app.py""", 1, False
        If Err.Number <> 0 Then
            Err.Clear
            WshShell.Run "cmd.exe /c """ & CurrentDir & "\Cai_Dat_Thu_Vien.bat""", 1, False
        End If
    End If
End If
