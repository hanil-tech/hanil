' 원본: frmOutMan.frm (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Partial Class frmOutMan

    Public Sub New()
        InitializeComponent()
        EndInitialize()
    End Sub


    Private Sub cmdBack_Click() Handles cmdBack.VbClick

        Me.Hide
        frmOutput.Show(1)

    End Sub

    Private Sub cmdDSheet_Click() Handles cmdDSheet.VbClick

        Call datasheet

    End Sub

    Private Sub cmdEnd_Click() Handles cmdEnd.VbClick
        Dim answer As Integer


            answer = MsgBox("정말로 끝내시겠습니까?", vbYesNo + vbQuestion, "종료확인")

        If answer = vbYes Then

            End

        End If

    End Sub

    Private Sub cmdFan_Click() Handles cmdFan.VbClick

        If frmInput.optVbelt.Value = True Then

            VBeltDraw

        Else

            DirectDraw

        End If


    End Sub

    Private Sub cmdImp_Click() Handles cmdImp.VbClick

        Draw_Impeller

    End Sub

    Private Sub cmdNoise_Click() Handles cmdNoise.VbClick

        Me.Hide
        frmNoise.Show(1)

    End Sub

    Private Sub cmdPer_Click() Handles cmdPer.VbClick

        Performance

    End Sub

    Private Sub cmdResult_Click() Handles cmdResult.VbClick

        Maker_Report

    End Sub



End Class
