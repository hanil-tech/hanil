Attribute VB_Name = "ResizeFrm"
Option Explicit

Public Sub ResizeForm(FrmName As Form, XRatio As Integer, YRatio As Integer, Optional Param As Integer)

    On Error Resume Next
    If XRatio < 1 Or YRatio < 1 Then
        MsgBox "XRatio와 Yratio의 값은 1보다 커야 합니다."
        Exit Sub
    End If
    
    If Param <> 0 Then GoTo ResizeControl
    
    FrmName.Height = FrmName.Height * YRatio / 100
    FrmName.Width = FrmName.Width * XRatio / 100
    FrmName.FontSize = FrmName.FontSize * XRatio / 100
    
ResizeControl:
    Dim Ctl As Control
    For Each Ctl In FrmName.Controls
        Ctl.Left = Ctl.Left * XRatio / 100
        Ctl.Top = Ctl.Top * YRatio / 100
        Ctl.Height = Ctl.Height * YRatio / 100
        Ctl.Width = Ctl.Width * XRatio / 100
        Ctl.Font.Size = Ctl.Font.Size * XRatio / 100
    Next

End Sub
                                      

