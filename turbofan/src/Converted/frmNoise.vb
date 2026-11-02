' 원본: frmNoise.frm (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Partial Class frmNoise

    Public Sub New()
        InitializeComponent()
        EndInitialize()
    End Sub

    Dim TW As Object, FW As Object, FN As Object, FD As Object, DST As Object, K As Object, SAN As Object, BPF As Object, SPL As Object, SAEff As Double

    Private Sub cboKind_Change() Handles cboKind.VbChange

        If cboKind.text = "스프링" Then
            cboDisplacement.Clear
            cboDisplacement.AddItem("2.5")
            cboDisplacement.AddItem("5")
            cboDisplacement.ListIndex = 0

        Else
            cboDisplacement.Clear
            cboDisplacement.AddItem("0.5")
            cboDisplacement.ListIndex = 0

        End If

    End Sub

    Private Sub cmdBack_Click() Handles cmdBack.VbClick

        Me.Hide
        frmOutMan.Show(0)

    End Sub

    Private Sub cmdCatalogue_Click() Handles cmdCatalogue.VbClick

        ShellExecute(GetDesktopWindow(), "Open", SupportFolder() & "\Data\방진카타로그.pdf", "", "C:\", 1)

    End Sub

    Private Sub cmdEnd_Click() Handles cmdEnd.VbClick
        Dim answer As Integer


            answer = MsgBox("정말로 끝내시겠습니까?", vbYesNo + vbQuestion, "종료확인")

        If answer = vbYes Then

            QuitApplication()

        End If

    End Sub

    Private Sub cmdReport_Click() Handles cmdReport.VbClick

        Maker_Noize_Report

    End Sub

    Private Sub cboDisplacement_Change() Handles cboDisplacement.VbChange

        Cal_SA

    End Sub

    Private Sub txtFanWeight_Change() Handles txtFanWeight.VbChange

        TW = Val(txtMotorWeight.text) + Val(txtFanWeight.text)
        txtTotalWeight.text = Format(TW, "###")

        Cal_SA

    End Sub

    Private Sub txtNoSA_Change() Handles txtNoSA.VbChange

        Cal_SA

    End Sub

    Protected Overrides Sub UserForm_Activate()

        txtMotorWeight.text = VbCopy(motorwt)
        cboKind.Clear
        cboKind.AddItem("스프링")
        cboKind.AddItem("고무")
        cboDisplacement.Clear
        cboDisplacement.AddItem("2.5")
        cboDisplacement.AddItem("5")

        txtBladeNo.text = VbCopy(Z)
        txtFanRevolution.text = VbCopy(N)
        FW = 20.721 * D2no ^ 2 - 9.9471 * D2no + 43.605

        txtFanWeight.text = Format(FW, "##0")

        Cal_SA
        Cal_SPL

    End Sub
    Sub Cal_SA()

        On Error Resume Next

        TW = Val(txtMotorWeight.text) + Val(txtFanWeight.text)
        DST = Val(cboDisplacement.text)
        SAN = Val(txtNoSA.text)
        BPF = Z * N / 60
        K = TW / (DST * SAN)
        FN = 4.981 * (1 / DST) ^ 0.5
        FD = N / 60
        SAEff = Abs(1 - (1 / ((FD / FN) ^ 2 - 1)))
        txtTotalWeight.text = VbCopy(TW)
        txtSpringConstant.text = Format(K, "#.0")
        txtNaturalF.text = Format(FN, "#.0")
        txtForcedF.text = Format(FD, "#.0")
        txtSAEff.text = Format(SAEff * 100, "#.00")

    End Sub

    Sub Cal_SPL()
        Dim dBs As Object, SPL As Double


        txtBPF.text = Format(BPF, "#.0")

        Select Case BPF
            Case 0 To 63
                dBs = 35
            Case 63 To 125
                dBs = 35
            Case 125 To 500
                dBs = 34
            Case 500 To 1000
                dBs = 32
            Case 1000 To 2000
                dBs = 31
            Case 2000 To 4000
                dBs = 26
            Case 4000 To 8000
                dBs = 18
            Case Is > 8000
                dBs = 10
        End Select

        SPL = dBs + 10 * Log(q) / Log(10#) + 20 * Log(ps) / Log(10#) + 3 - 12.62

        txtCalculatedSPL.text = Format(SPL, "#.0")

    End Sub



End Class
