Attribute VB_Name = "cCirFlange"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

' Property 선언
Public CP As Variant
Public ID As Double
Public B As Integer 'Flange 폭
Public Thickness As Integer ' Flange 두께
Public Pitch As Double ' Bolt Hole Pitch
Public BoltNo As Integer ' Bolt Hole 수
Public BoltHoleDia As Integer ' Bolt Hole 직경
Public OutDia As Double
Public RotAng As Double
Public Matl As String '송풍기 재질

Dim pcd As Double
Dim pntCol As New Collection
Dim pntArray() As Double

Public Sub DrawPlan() ' 평면도 작도
    
    DataCalculation ' Data 계산 루틴 작동
    
    Dim Pnt1 As Variant ' Bolt Hole 중심점
    Dim ArrayedCir As Variant ' Array될 Bolt Hole원 객체저장
    
        Pnt1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(90), (ID + B) / 2)
    
    Dim Cir1 As AcadCircle ' ID원 객체
    Dim Cir2 As AcadCircle ' PCD원 객체
    Dim Cir3 As AcadCircle ' OD원 객체
    Dim Cir4 As AcadCircle ' Bolt Hole원 객체
    
    Set Cir1 = ThisDrawing.ModelSpace.AddCircle(CP, ID / 2)
    Set Cir2 = ThisDrawing.ModelSpace.AddCircle(CP, (ID + B) / 2)
        Cir2.color = acRed
        Cir2.Linetype = "Center"
    
    Set Cir3 = ThisDrawing.ModelSpace.AddCircle(CP, ID / 2 + B)
    Set Cir4 = ThisDrawing.ModelSpace.AddCircle(Pnt1, BoltHoleDia / 2)
        Cir4.color = acCyan
        Cir4.Rotate CP, Dtr(180 / BoltNo)
        ArrayedCir = Cir4.ArrayPolar(BoltNo, Dtr(360 - (360 / BoltNo)), CP)
    
    

End Sub

Public Sub DrawFront() ' 정면도 작성
    
    DataCalculation ' Data 계산 루틴 작동
    
    Set pntCol = Nothing
    
    Dim Pnt1 As Variant
    Dim Pnt2 As Variant
    Dim Pnt3 As Variant
    Dim Pnt4 As Variant
    Dim Pnt5 As Variant
    
    Dim Pnt6 As Variant
    Dim Pnt7 As Variant
    Dim Pnt8 As Variant
    Dim Pnt9 As Variant
    Dim Pnt10 As Variant
    
    Dim Pnt11 As Variant
    Dim Pnt12 As Variant
    Dim Pnt13 As Variant
    Dim Pnt14 As Variant
    Dim Pnt15 As Variant
    
    Dim Pnt16 As Variant
    Dim Pnt17 As Variant
    Dim Pnt18 As Variant
    Dim Pnt19 As Variant
    Dim Pnt20 As Variant
    
    Dim Pnt21 As Variant
    Dim Pnt22 As Variant
    Dim Pnt23 As Variant
    Dim Pnt24 As Variant
    Dim Pnt25 As Variant
    
        Pnt1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), ID / 2)
        Pnt2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), (pcd - BoltHoleDia) / 2)
        Pnt3 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), pcd / 2)
        Pnt4 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 90), Thickness)
        Pnt5 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 180), BoltHoleDia / 2)
        
        Pnt6 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), OutDia / 2)
        Pnt7 = ThisDrawing.Utility.PolarPoint(Pnt6, Dtr(RotAng + 270), Thickness)
        Pnt8 = ThisDrawing.Utility.PolarPoint(Pnt5, Dtr(RotAng + 270), Thickness)
        Pnt9 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 270), Thickness)
        Pnt10 = ThisDrawing.Utility.PolarPoint(Pnt9, Dtr(RotAng + 270), Thickness)
        
        Pnt11 = ThisDrawing.Utility.PolarPoint(Pnt2, Dtr(RotAng + 270), Thickness)
        Pnt12 = ThisDrawing.Utility.PolarPoint(Pnt1, Dtr(RotAng + 270), Thickness)
        Pnt13 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 270), Thickness)
        Pnt14 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), ID / 2)
        Pnt15 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), (pcd - BoltHoleDia) / 2)
        
        Pnt16 = ThisDrawing.Utility.PolarPoint(Pnt15, Dtr(RotAng + 0), BoltHoleDia / 2)
        Pnt17 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 270), Thickness)
        Pnt18 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 0), BoltHoleDia / 2)
        Pnt19 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), OutDia / 2)
        Pnt20 = ThisDrawing.Utility.PolarPoint(Pnt19, Dtr(RotAng + 90), Thickness)
        
        Pnt21 = ThisDrawing.Utility.PolarPoint(Pnt18, Dtr(RotAng + 90), Thickness)
        Pnt22 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 90), Thickness)
        Pnt23 = ThisDrawing.Utility.PolarPoint(Pnt22, Dtr(RotAng + 90), Thickness)
        Pnt24 = ThisDrawing.Utility.PolarPoint(Pnt15, Dtr(RotAng + 90), Thickness)
        Pnt25 = ThisDrawing.Utility.PolarPoint(Pnt14, Dtr(RotAng + 90), Thickness)
        
        pntCol.Add Pnt6
        pntCol.Add Pnt20
        pntCol.Add Pnt19
        pntCol.Add Pnt7
        
        MakePntArray
        
        Dim cirFlangeEnt As AcadPolyline
        Set cirFlangeEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        With cirFlangeEnt
            .Closed = True
            .Highlight True
            .Update
        End With
        
        Set AutoTrim.Ent = cirFlangeEnt
        AutoTrim.DoTrim
        cirFlangeEnt.Delete
        
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    
    Dim Line5 As AcadLine
    Dim Line6 As AcadLine
    Dim Line7 As AcadLine
    Dim Line8 As AcadLine
    
    Dim Line9 As AcadLine
    Dim Line10 As AcadLine
    Dim Line11 As AcadLine
    Dim Line12 As AcadLine
    
        Set Line1 = ThisDrawing.ModelSpace.AddLine(Pnt6, Pnt20)
        Set Line2 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt6)
        Set Line3 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt19)
        Set Line4 = ThisDrawing.ModelSpace.AddLine(Pnt19, Pnt20)
            Line1.color = acCyan
            Line2.color = acCyan
            Line3.color = acCyan
            Line4.color = acCyan
        
        Set Line5 = ThisDrawing.ModelSpace.AddLine(Pnt8, Pnt5)
            Line5.color = acGreen
            Line5.Linetype = "Hidden"
        Set Line6 = ThisDrawing.ModelSpace.AddLine(Pnt10, Pnt4)
            Line6.color = acRed
            Line6.Linetype = "Center"
        Set Line7 = ThisDrawing.ModelSpace.AddLine(Pnt11, Pnt2)
            Line7.color = acGreen
            Line7.Linetype = "Hidden"
        Set Line8 = ThisDrawing.ModelSpace.AddLine(Pnt12, Pnt1)
            Line8.color = acGreen
            Line8.Linetype = "Hidden"
        
        Set Line9 = ThisDrawing.ModelSpace.AddLine(Pnt14, Pnt25)
            Line9.color = acGreen
            Line9.Linetype = "Hidden"
        Set Line10 = ThisDrawing.ModelSpace.AddLine(Pnt15, Pnt24)
            Line10.color = acGreen
            Line10.Linetype = "Hidden"
        Set Line11 = ThisDrawing.ModelSpace.AddLine(Pnt17, Pnt23)
            Line11.color = acRed
            Line11.Linetype = "Center"
        Set Line12 = ThisDrawing.ModelSpace.AddLine(Pnt18, Pnt21)
            Line12.color = acGreen
            Line12.Linetype = "Hidden"
            
    ' 치수점 할당
    If frmInput.optDirect = True Then
        If Direction = "RH" Then
            dimP21 = Pnt20
            dimP22 = Pnt25
            dimP23 = Pnt1
        End If
    
        If Direction = "RL" Then
            If PlanCirFlange Then
                dimP14 = Pnt25
                dimP15 = Pnt1
                PlanCirFlange = False
            
                ElseIf RightCirFlange Then
                    dimP19 = Pnt20
                    RightCirFlange = False
            End If
        End If
    
        If Direction = "RR" Then
            If PlanCirFlange Then
                dimP11 = Pnt6
                PlanCirFlange = False
            
                ElseIf RightCirFlange Then
                    dimP25 = Pnt25
                    dimP26 = Pnt1
                    RightCirFlange = False
            End If
        End If
    
        If Direction = "LH" Then
            dimP21 = Pnt20
            dimP22 = Pnt25
            dimP23 = Pnt1
        End If
    
        If Direction = "LL" Then
            If PlanCirFlange Then
                dimP15 = Pnt25
                dimP16 = Pnt1
                PlanCirFlange = False
            
                ElseIf RightCirFlange Then
                dimP23 = Pnt20
                RightCirFlange = False
            End If
        End If
    
        If Direction = "LR" Then
            If PlanCirFlange Then
                dimP12 = Pnt25
                dimP13 = Pnt1
                PlanCirFlange = False
            
                ElseIf RightCirFlange Then
                dimP23 = Pnt20
            End If
        End If
    
    Else ' V-Belt 전동시
        If PlanCirFlange Then
            dimP12 = Pnt25
            dimP13 = Pnt1
            PlanCirFlange = False
            
            ElseIf RightCirFlange Then
                dimP24 = Pnt20
                RightCirFlange = False
        End If
    
    End If
    
End Sub

Private Sub DataCalculation()
    
    ' 평철 규격 선정
    
        If Matl = "SS400" Or Matl = "STS304" Or Matl = "STS316" Or Matl = "STS316L" Or Matl = "Ti-Alloy" Then
            
            Select Case ID
            
                Case 0 To 250
                    B = 32: Thickness = 6
                Case 250 To 450
                    B = 38: Thickness = 6
                Case 450 To 600
                    B = 50: Thickness = 9
                Case 600 To 950
                    B = 65: Thickness = 9
                Case Is > 950
                    B = 75: Thickness = 12
                    
            End Select
        
        ElseIf Matl = "F.R.P" Then
        
            Select Case ID
            
                Case 0 To 250
                    B = 50: Thickness = 12
                Case 250 To 450
                    B = 50: Thickness = 14
                Case 450 To 600
                    B = 65: Thickness = 15
                Case 600 To 950
                    B = 65: Thickness = 15
                Case Is > 950
                    B = 65: Thickness = 15
            
            End Select
        
        ElseIf Matl = "P.V.C" Then
            
            Select Case ID
                
                Case 0 To 250
                    B = 50: Thickness = 10
                Case 250 To 450
                    B = 50: Thickness = 10
                Case 450 To 600
                    B = 50: Thickness = 12
                Case 600 To 950
                    B = 65: Thickness = 15
                Case Is > 950
                    B = 65: Thickness = 15
            
            End Select
        
        End If
        
    ' pcd 계산
    
    pcd = ID + B
    
    ' OutDia 계산
    
    OutDia = ID + 2 * B
    
    
    ' Bolt Hole 직경 선정
    
    Select Case ID
        Case 0 To 300
            BoltHoleDia = 12
        Case 300 To 700
            BoltHoleDia = 15
        Case Is > 700
            BoltHoleDia = 19
    End Select
    
    ' Bolt Hole Pitch 계산
    
    Pitch = 120 * ((B * Thickness ^ 3) / 36450) ^ (1 / 3)
    
    ' Bolt 수 계산
    
    BoltNo = Int(((ID + B) * (Atn(1) * 4) / Pitch + 1) / 2) * 2
    
End Sub

Sub MakePntArray()
        
    ReDim pntArray(pntCol.Count * 3 - 1)
    Dim i As Integer
    Dim pnt As Variant
    
    For i = 1 To pntCol.Count
        
        pnt = pntCol.Item(i)
            
        pntArray(0 + (i - 1) * 3) = pnt(0)
        pntArray(1 + (i - 1) * 3) = pnt(1)
        pntArray(2 + (i - 1) * 3) = pnt(2)
            
    Next i
        
End Sub



