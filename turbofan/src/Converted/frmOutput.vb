' 원본: frmOutput.frm (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Partial Class frmOutput

    Public Sub New()
        InitializeComponent()
        EndInitialize()
    End Sub


    Private Sub cboVbeltType_Click() Handles cboVbeltType.VbClick

        VbeltType = cboVbeltType.text
        Select Case VbeltType
            Case "A Type"
                SmallestSize = 3
            Case "B Type"
                SmallestSize = 5
            Case "C Type"
                SmallestSize = 8
            Case "D Type"
                SmallestSize = 14
            Case "3V Type"
                SmallestSize = 5
            Case "5V Type"
                SmallestSize = 8
        End Select

        fromcobVBelt = True
        Vbelt_Type_Reselection 'V-Belt 형식을 재설정했을 경우 V-Belt재계산
        fromcobVBelt = False

        txtVbeltPcs.text = PCS & " pcs"
        Bearing_Lifetime

    End Sub

    Private Sub cmdBigSize_Click() Handles cmdBigSize.VbClick '풀리규격 증가버튼

        If frmInput.optVbelt.Value = True Then
            If motorPulley < fanPulley Then
                SmallestSize = motorPulley + 0.5
                Else
                SmallestSize = fanPulley + 0.5
            End If

            Vbelt_Type_Reselection 'V-Belt 형식을 재설정했을 경우 V-Belt재계산
            txtVbeltPcs.text = PCS & " pcs"
            Bearing_Lifetime
        End If

    End Sub

    Private Sub cmdEnd_Click() Handles cmdEnd.VbClick
        Dim answer As Integer


            answer = MsgBox("정말로 끝내시겠습니까?", vbYesNo + vbQuestion, "종료확인")

        If answer = vbYes Then

            End

        End If

    End Sub

    Private Sub cmdOut_Click() Handles cmdOut.VbClick

        Me.Hide
        frmOutMan.Show(0)

    End Sub

    Private Sub cmdRestart_Click() Handles cmdRestart.VbClick

        Me.Hide
        frmInput.Show(1)
        frmInput.txtCustomer.SetFocus

    End Sub

    Private Sub cmdSmallSize_Click() Handles cmdSmallSize.VbClick '풀리규격 감소버튼

        If frmInput.optVbelt.Value = True Then
            If motorPulley > fanPulley Then
                BiggestSize = motorPulley - 0.5
                Else
                BiggestSize = fanPulley - 0.5
            End If

            If BiggestSize < sFanPulley Or BiggestSize < sMotorPulley Then
                If motorPulley > fanPulley Then
                    BiggestSize = motorPulley + 0.5
                    Else
                    BiggestSize = fanPulley + 0.5
                End If

                Exit Sub
            End If

            Vbelt_Type_Reselection1 'V-Belt 형식을 재설정했을 경우 V-Belt재계산(감소)

            txtVbeltPcs.text = PCS & " pcs"
            Bearing_Lifetime
        End If

    End Sub

    Private Sub txtMInsulGrade_Enter() Handles txtMInsulGrade.VbEnter

        Text_Selected

    End Sub

    Private Sub txtMMaker_Enter() Handles txtMMaker.VbEnter

        Text_Selected

    End Sub

    Private Sub txtVbeltPcs_Enter() Handles txtVbeltPcs.VbEnter

        Text_Selected

    End Sub

    Private Sub cmdDn_1_Click() Handles cmdDn_1.VbClick

        If frmInput.optVbelt.Value = True Then
            PCS = PCS - 1
            If PCS < 1 Then PCS = 1
            txtVbeltPcs.text = PCS & " pcs"
        End If

    End Sub

    Private Sub cmdUp_1_Click() Handles cmdUp_1.VbClick

        If frmInput.optVbelt.Value = True Then
            PCS = PCS + 1
            txtVbeltPcs.text = PCS & " pcs"
        End If

    End Sub
    Private Sub cmdDn_2_Click() Handles cmdDn_2.VbClick

        If frmInput.optVbelt.Value = True Then
            If bearingno >= 22 Then
                bearingno = bearingno - 2
                Else
                bearingno = bearingno - 1
            End If

            If bearingno < 0 Then bearingno = 0
            Bearing_Lifetime

            txtBearingImp.text = "63" & Format(bearingno, "00")
            txtBearingPulley.text = "63" & Format(bearingno, "00")

            Select Case bearingno
                Case 0
                    DS = 10
                Case 1
                    DS = 12
                Case 2
                    DS = 15
                Case 3
                    DS = 17
                Case Is >= 4
                    DS = bearingno * 5
            End Select
            txtShaftDia.text = "φ" & DS
        End If

    End Sub

    Private Sub cmdUp_2_Click() Handles cmdUp_2.VbClick

        If frmInput.optVbelt.Value = True Then
            If bearingno >= 22 Then
                bearingno = bearingno + 2
                Else
                bearingno = bearingno + 1
            End If

            If bearingno > 28 Then bearingno = 28
            Bearing_Lifetime

            txtBearingImp.text = "63" & Format(bearingno, "00")
            txtBearingPulley.text = "63" & Format(bearingno, "00")

            Select Case bearingno
                Case 0
                    DS = 10
                Case 1
                    DS = 12
                Case 2
                    DS = 15
                Case 3
                    DS = 17
                Case Is >= 4
                    DS = bearingno * 5
            End Select
            txtShaftDia.text = "φ" & DS

        End If

    End Sub

    Protected Overrides Sub UserForm_Activate()

        cboShaftMatl.Clear
        cboShaftMatl.AddItem("SM45C")
        cboShaftMatl.AddItem("STS304")
        cboShaftMatl.AddItem("STS316")
        cboShaftMatl.text = "SM45C"

        cboVbeltType.Clear
        cboVbeltType.AddItem("A Type")
        cboVbeltType.AddItem("B Type")
        cboVbeltType.AddItem("C Type")
        cboVbeltType.AddItem("D Type")
        cboVbeltType.AddItem("3V Type")
        cboVbeltType.AddItem("5V Type")
        cboVbeltType.text = VbCopy(VbeltType)


    End Sub

End Class
