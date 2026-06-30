Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
' Safely get the absolute path of the directory containing this script
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

WshShell.Run "cmd /c npm --prefix """ & scriptDir & "\desktop\electron"" run dev", 0, False
