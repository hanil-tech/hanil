Attribute VB_Name = "GetOSVersion"
Option Explicit

Public Declare Function GetVersionEx Lib "kernel32" Alias "GetVersionExA" _
     (lpVersionInformation As OSVERSIONINFO) As Long

Type OSVERSIONINFO
   dwOSVersionInfoSize As Long
   dwMajorVersion As Long
   dwMinorVersion As Long
   dwBuildNumber As Long
   dwPlatformId As Long
   szCSDVersion As String * 128
End Type

Dim OSV As OSVERSIONINFO         ' 구조체 할당

Public Function GetOSVersion() As Integer

   Dim Result As Long
   OSV.dwOSVersionInfoSize = Len(OSV)
   Result = GetVersionEx(OSV)
   GetOSVersion = OSV.dwPlatformId
   
   Select Case GetOSVersion
      Case 1
         If OSV.dwMinorVersion = 10 Then GetOSVersion = 3
      Case 2
         If OSV.dwMinorVersion = 51 Then GetOSVersion = 4
   End Select

End Function




