' CAD 고르기 창.
'  - 켜진 CAD 가 없을 때: 설치된 CAD 중 하나를 골라 실행하거나, 직접 켠 뒤 [다시 찾기].
'  - 켜진 CAD 가 여러 개일 때: 어디에 그릴지 고르기.
Imports System.Drawing
Imports System.Windows.Forms

Public Class CadPicker

    Public Enum PickAction
        Launch
        Retry
        Cancel
    End Enum

    Public Structure LaunchChoice
        Public Action As PickAction
        Public Product As AcadHost.CadProduct
        Public ProgId As String
    End Structure

    ''' <summary>켜진 CAD 가 없을 때.</summary>
    Public Shared Function ChooseToLaunch(installed As List(Of KeyValuePair(Of AcadHost.CadProduct, String)), preferred As String) As LaunchChoice
        Using f As New Form()
            f.Text = "CAD 연결"
            f.FormBorderStyle = FormBorderStyle.FixedDialog
            f.StartPosition = FormStartPosition.CenterScreen
            f.MaximizeBox = False : f.MinimizeBox = False : f.ShowInTaskbar = False
            f.Font = New Font("맑은 고딕", 9.0F)
            f.AutoScaleMode = AutoScaleMode.Dpi
            f.ClientSize = New Size(420, 270)
            f.TopMost = True

            Dim lbl As New Label With {.Location = New Point(14, 12), .Size = New Size(392, 64), .Text =
                "실행 중인 CAD 를 찾지 못했습니다." & vbCrLf &
                "아래에서 실행할 CAD 를 고르거나, CAD 를 직접 켠 뒤 [다시 찾기] 를 누르세요." & vbCrLf &
                "(AutoCAD, ZWCAD, GstarCAD, BricsCAD, progeCAD/IntelliCAD)"}
            Dim list As New ListBox With {.Location = New Point(14, 80), .Size = New Size(392, 120), .IntegralHeight = False}
            For Each kv In installed
                list.Items.Add(kv.Key)
            Next
            If list.Items.Count = 0 Then
                list.Items.Add("(이 PC 에 등록된 지원 CAD 가 없습니다)")
                list.Enabled = False
            Else
                Dim idx = installed.FindIndex(Function(kv) kv.Key.Name = preferred)
                list.SelectedIndex = Math.Max(0, idx)
            End If
            Dim btnLaunch As New Button With {.Text = "실행", .Location = New Point(130, 220), .Size = New Size(86, 32), .Enabled = installed.Count > 0}
            Dim btnRetry As New Button With {.Text = "다시 찾기", .Location = New Point(222, 220), .Size = New Size(90, 32)}
            Dim btnCancel As New Button With {.Text = "취소", .Location = New Point(318, 220), .Size = New Size(86, 32), .DialogResult = DialogResult.Cancel}
            Dim result As New LaunchChoice With {.Action = PickAction.Cancel}
            AddHandler btnLaunch.Click, Sub()
                                            Dim i = list.SelectedIndex
                                            If i < 0 OrElse i >= installed.Count Then Return
                                            result = New LaunchChoice With {.Action = PickAction.Launch, .Product = installed(i).Key, .ProgId = installed(i).Value}
                                            f.DialogResult = DialogResult.OK
                                        End Sub
            AddHandler list.DoubleClick, Sub() btnLaunch.PerformClick()
            AddHandler btnRetry.Click, Sub()
                                           result = New LaunchChoice With {.Action = PickAction.Retry}
                                           f.DialogResult = DialogResult.Retry
                                       End Sub
            f.Controls.AddRange({lbl, list, btnLaunch, btnRetry, btnCancel})
            f.AcceptButton = If(installed.Count > 0, btnLaunch, btnRetry)
            f.CancelButton = btnCancel
            f.ShowDialog()
            Return result
        End Using
    End Function

    ''' <summary>켜진 CAD 가 여러 개일 때 어디에 그릴지.</summary>
    Public Shared Function ChooseRunning(running As List(Of AcadHost.CadProduct)) As AcadHost.CadProduct
        Using f As New Form()
            f.Text = "어느 CAD 에 그릴까요?"
            f.FormBorderStyle = FormBorderStyle.FixedDialog
            f.StartPosition = FormStartPosition.CenterScreen
            f.MaximizeBox = False : f.MinimizeBox = False : f.ShowInTaskbar = False
            f.Font = New Font("맑은 고딕", 9.0F)
            f.AutoScaleMode = AutoScaleMode.Dpi
            f.ClientSize = New Size(320, 210)
            f.TopMost = True
            Dim lbl As New Label With {.Location = New Point(14, 12), .Size = New Size(292, 22), .Text = "CAD 가 여러 개 켜져 있습니다. 그릴 곳을 고르세요."}
            Dim list As New ListBox With {.Location = New Point(14, 40), .Size = New Size(292, 110), .IntegralHeight = False}
            For Each p In running
                list.Items.Add(p)
            Next
            list.SelectedIndex = 0
            Dim ok As New Button With {.Text = "확인", .Location = New Point(126, 162), .Size = New Size(86, 32), .DialogResult = DialogResult.OK}
            Dim cancel As New Button With {.Text = "취소", .Location = New Point(220, 162), .Size = New Size(86, 32), .DialogResult = DialogResult.Cancel}
            AddHandler list.DoubleClick, Sub() f.DialogResult = DialogResult.OK
            f.Controls.AddRange({lbl, list, ok, cancel})
            f.AcceptButton = ok : f.CancelButton = cancel
            If f.ShowDialog() <> DialogResult.OK Then Return Nothing
            Return TryCast(list.SelectedItem, AcadHost.CadProduct)
        End Using
    End Function

End Class
