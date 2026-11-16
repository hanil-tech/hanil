Attribute VB_Name = "frmOutMan"
Attribute VB_Base = "0{8D8016A7-C749-4B43-ACEE-8F30F08CDAAF}{0F134163-E440-47B7-A4FB-4720772594A2}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

Private Sub cmdBack_Click()
    
    Me.Hide
    frmOutput.Show 1
    
End Sub

Private Sub cmdDSheet_Click()
    
    Call datasheet
    
End Sub

Private Sub cmdEnd_Click()
    
    Dim answer As Integer
        
        answer = MsgBox("정말로 끝내시겠습니까?", vbYesNo + vbQuestion, "종료확인")

    If answer = vbYes Then
        
        End
    
    End If
    
End Sub

Private Sub cmdFan_Click()
    
    If frmInput.optVbelt = True Then
        
        VBeltDraw
    
    Else
        
        DirectDraw
    
    End If
    

End Sub

Private Sub cmdImp_Click()
    
    Draw_Impeller
    
End Sub

Private Sub cmdNoise_Click()
    
    Me.Hide
    frmNoise.Show 1
    
End Sub

Private Sub cmdPer_Click()
    
    Performance
       
End Sub

Private Sub cmdResult_Click()
        
    Maker_Report

End Sub


