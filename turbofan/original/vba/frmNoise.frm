Attribute VB_Name = "frmNoise"
Attribute VB_Base = "0{7F14075C-D4B4-4EF2-A7DB-12DB1535BC9A}{C166A304-4918-45BE-8CA5-6D3D0154BE38}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit
Dim TW, FW, FN, FD, DST, K, SAN, BPF, SPL, SAEff  As Double

Private Sub cboKind_Change()
    
    If cboKind.text = "스프링" Then
        cboDisplacement.Clear
        cboDisplacement.AddItem "2.5"
        cboDisplacement.AddItem "5"
        cboDisplacement.ListIndex = 0
        
    Else
        cboDisplacement.Clear
        cboDisplacement.AddItem "0.5"
        cboDisplacement.ListIndex = 0
        
    End If
    
End Sub

Private Sub cmdBack_Click()
    
    Me.Hide
    frmOutMan.Show 0
    
End Sub

Private Sub cmdCatalogue_Click()
        
    ShellExecute GetDesktopWindow(), "Open", ThisDrawing.Application.Path & "\ALISP\Turbo Fan Design\Data\방진카타로그.pdf", "", "C:\", 1
    
End Sub

Private Sub cmdEnd_Click()
        
    Dim answer As Integer
        
        answer = MsgBox("정말로 끝내시겠습니까?", vbYesNo + vbQuestion, "종료확인")

    If answer = vbYes Then
        
        End
    
    End If

End Sub

Private Sub cmdReport_Click()
    
    Maker_Noize_Report
    
End Sub

Private Sub cboDisplacement_Change()
    
    Cal_SA
    
End Sub

Private Sub txtFanWeight_Change()
    
    TW = Val(txtMotorWeight.text) + Val(txtFanWeight.text)
    txtTotalWeight.text = Format(TW, "###")
    
    Cal_SA
    
End Sub

Private Sub txtNoSA_Change()
    
    Cal_SA
    
End Sub

Private Sub UserForm_Activate()
        
    txtMotorWeight.text = motorwt
    cboKind.Clear
    cboKind.AddItem "스프링"
    cboKind.AddItem "고무"
    cboDisplacement.Clear
    cboDisplacement.AddItem "2.5"
    cboDisplacement.AddItem "5"
    
    txtBladeNo.text = Z
    txtFanRevolution.text = N
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
    txtTotalWeight.text = TW
    txtSpringConstant.text = Format(K, "#.0")
    txtNaturalF.text = Format(FN, "#.0")
    txtForcedF.text = Format(FD, "#.0")
    txtSAEff.text = Format(SAEff * 100, "#.00")
    
End Sub

Sub Cal_SPL()
    
    Dim dBs, SPL As Double
    
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


