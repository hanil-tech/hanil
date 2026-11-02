' 시험 빌드용 대역: 메시지 창은 띄우지 않고 기록만 한다.
Public Module TestShims
    Public ReadOnly Messages As New List(Of String)
    Public Function MsgBox(Prompt As Object, Optional Buttons As MsgBoxStyle = MsgBoxStyle.OkOnly, Optional Title As Object = Nothing) As MsgBoxResult
        Messages.Add("[MsgBox " & CStr(Title) & "] " & CStr(Prompt).Replace(vbCrLf, " / "))
        Console.WriteLine("    MsgBox: " & CStr(Prompt).Replace(vbCrLf, " / "))
        If (Buttons And MsgBoxStyle.YesNo) = MsgBoxStyle.YesNo Then Return MsgBoxResult.No
        Return MsgBoxResult.Ok
    End Function
End Module

Public Module Program
    Public Sub QuitApplication()
        Throw New Exception("QuitApplication 호출됨")
    End Sub
End Module
