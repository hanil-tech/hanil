' 출력관리 창에 원본에 없던 [도면 DWG로 저장] 단추를 더한다.
' (원본 폼 배치는 src/Forms 에서 그대로 만들고, 여기서 단추 하나와 그만큼의 높이를 더한다)
Imports System.Drawing
Imports System.IO
Imports System.Windows.Forms

Partial Class frmOutMan

    Private WithEvents cmdSaveDwg As MCommandButton

    Protected Overrides Sub AddExtras()
        Dim gap = cmdImp.Top - cmdFan.Bottom
        Dim dy = cmdNoise.Height + gap
        ClientSize = New Size(ClientSize.Width, ClientSize.Height + dy)
        cmdBack.Top += dy
        cmdEnd.Top += dy
        cmdSaveDwg = New MCommandButton With {
            .Name = "cmdSaveDwg",
            .Text = "도면 DWG 로 저장",
            .Location = New Point(cmdNoise.Left, cmdNoise.Bottom + gap),
            .Size = cmdNoise.Size,
            .Font = cmdNoise.Font,
            .UseVisualStyleBackColor = True,
            .TabIndex = cmdNoise.TabIndex + 1
        }
        Controls.Add(cmdSaveDwg)
    End Sub

    Private Sub cmdSaveDwg_Click() Handles cmdSaveDwg.VbClick
        SaveDrawingAsDwg()
    End Sub

End Class

Public Module DwgSave

    ''' <summary>
    ''' 지금 CAD 에 열려 있는 도면(방금 그린 도면)을 DWG 파일로 저장한다. CAD 의 "다른 이름으로 저장" 을 쓴다.
    ''' </summary>
    Public Sub SaveDrawingAsDwg()
        If Not EnsureCad() Then Return
        Dim doc = ThisDrawing
        Dim name = "TurboFan"
        Try
            Dim cust = frmOutput.txtCustomer.Text.Trim()
            If cust <> "" Then name = cust
        Catch
        End Try
        For Each c In Path.GetInvalidFileNameChars()
            name = name.Replace(c, "_"c)
        Next
        Using dlg As New SaveFileDialog()
            dlg.Title = "도면을 DWG 파일로 저장"
            dlg.Filter = "DWG 도면 (*.dwg)|*.dwg"
            dlg.DefaultExt = "dwg"
            dlg.AddExtension = True
            dlg.OverwritePrompt = True
            dlg.InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)
            dlg.FileName = name & "_" & DateTime.Now.ToString("yyyyMMdd_HHmm") & ".dwg"
            If dlg.ShowDialog() <> DialogResult.OK Then Return
            Try
                Using New WaitCursor()
                    doc.SaveAs(dlg.FileName)
                End Using
                MsgBox("저장했습니다." & vbCrLf & dlg.FileName, MsgBoxStyle.Information, "DWG 저장")
            Catch ex As Exception
                MsgBox(CadName & " 에서 저장하지 못했습니다." & vbCrLf & ex.Message, MsgBoxStyle.Exclamation, "DWG 저장")
            End Try
        End Using
    End Sub

End Module
