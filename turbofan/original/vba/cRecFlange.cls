Attribute VB_Name = "cRecFlange"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

' 프로퍼티 선언
Public CP As Variant
Public B As Double
Public t As Double
Public idLength As Double
Public idWidth As Double
Public BD As Double ' Bolt hole Diameter
Public RotAng As Double

Dim pntCol As New Collection
Dim pntArray() As Double

' 클래스내 전역변수 선언
Dim Pitch As Double ' Bolt Hole Pitch


Public Sub DrawFront() ' 정면도 작성
    
    Set pntCol = Nothing
    
    ' pcd 계산
    Dim pcd As Double
        pcd = idLength + B
    ' od 계산
    Dim OD As Double
        OD = idLength + 2 * B
    
    ' Point Calculation
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
    
        Pnt1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), idLength / 2)
        Pnt2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), (pcd - BD) / 2)
        Pnt3 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), pcd / 2)
        Pnt4 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 90), t)
        Pnt5 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 180), BD / 2)
        
        Pnt6 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), OD / 2)
        Pnt7 = ThisDrawing.Utility.PolarPoint(Pnt6, Dtr(RotAng + 270), t)
        Pnt8 = ThisDrawing.Utility.PolarPoint(Pnt5, Dtr(RotAng + 270), t)
        Pnt9 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 270), t)
        Pnt10 = ThisDrawing.Utility.PolarPoint(Pnt9, Dtr(RotAng + 270), t)
        
        Pnt11 = ThisDrawing.Utility.PolarPoint(Pnt2, Dtr(RotAng + 270), t)
        Pnt12 = ThisDrawing.Utility.PolarPoint(Pnt1, Dtr(RotAng + 270), t)
        Pnt13 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 270), t)
        Pnt14 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), idLength / 2)
        Pnt15 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), (pcd - BD) / 2)
        
        Pnt16 = ThisDrawing.Utility.PolarPoint(Pnt15, Dtr(RotAng + 0), BD / 2)
        Pnt17 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 270), t)
        Pnt18 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 0), BD / 2)
        Pnt19 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), OD / 2)
        Pnt20 = ThisDrawing.Utility.PolarPoint(Pnt19, Dtr(RotAng + 90), t)
        
        Pnt21 = ThisDrawing.Utility.PolarPoint(Pnt18, Dtr(RotAng + 90), t)
        Pnt22 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 90), t)
        Pnt23 = ThisDrawing.Utility.PolarPoint(Pnt22, Dtr(RotAng + 90), t)
        Pnt24 = ThisDrawing.Utility.PolarPoint(Pnt15, Dtr(RotAng + 90), t)
        Pnt25 = ThisDrawing.Utility.PolarPoint(Pnt14, Dtr(RotAng + 90), t)
        
        pntCol.Add Pnt6
        pntCol.Add Pnt7
        pntCol.Add Pnt19
        pntCol.Add Pnt20
        
        MakePntArray
        
        Dim rFlangeEnt As AcadPolyline
        Set rFlangeEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        With rFlangeEnt
            .Closed = True
            .Highlight True
            .Update
        End With
        
        Set AutoTrim.Ent = rFlangeEnt
        AutoTrim.DoTrim
        rFlangeEnt.Delete
        
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
            
            Line1.Update
            Line2.Update
            Line3.Update
            Line4.Update
            
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
            
            Line5.Update
            Line6.Update
            Line7.Update
            Line8.Update
            Line9.Update
            Line10.Update
            Line11.Update
            Line12.Update
        
    ' 치수 Point 할당
    If frmInput.optDirect Then ' 직결구동일 경우
            If Direction = "RH" Then
                dimP4 = Pnt20
            End If
        
            If Direction = "RL" Then
                If FrontRecFlange Then
                    dimP5 = Pnt20
                    dimP6 = Pnt25
                    dimP7 = Pnt1
                    FrontRecFlange = False
                
                    ElseIf PlanRecFlange Then
                        dimP12 = Pnt1
                        dimP13 = Pnt25
                        PlanRecFlange = False
                End If
            End If
        
            If Direction = "RR" Then
                dimP5 = Pnt6
            End If
        
            If Direction = "LH" Then
                dimP4 = Pnt20
            End If
                
            If Direction = "LL" Then
                If FrontRecFlange Then
                    dimP5 = Pnt20
                    dimP6 = Pnt25
                    dimP7 = Pnt1
                    FrontRecFlange = False
                
                    ElseIf PlanRecFlange Then
                    dimP12 = Pnt25
                    dimP13 = Pnt1
                    PlanRecFlange = False
                End If
            End If
                
            If Direction = "LR" Then
                If FrontRecFlange Then
                    dimP4 = Pnt25
                    dimP5 = Pnt1
                    dimP7 = Pnt6
                    FrontRecFlange = False
                
                    ElseIf PlanRecFlange Then
                    dimP15 = Pnt25
                    dimP16 = Pnt1
                    PlanRecFlange = False
                End If
            End If
        
        Else ' V-Belt 구동일 경우
            If FrontRecFlange Then
                dimP6 = Pnt1
                dimP7 = Pnt25
                dimP9 = Pnt20
                FrontRecFlange = False
                
                ElseIf PlanRecFlange Then
                    dimP15 = Pnt1
                    dimP16 = Pnt25
                    PlanRecFlange = False
                    
                ElseIf RightRecFlange Then
                    dimP28 = Pnt6
                    RightRecFlange = False
                    
            End If
            
    End If
        
End Sub

Public Sub DrawPlan() ' 평면도 작성

    Set pntCol = Nothing
    
    Dim L As Double
    Dim W As Double
    Dim CL As Double
    Dim CW As Double
    Dim OL As Double
    Dim OW As Double
        L = idLength
        W = idWidth
        CL = L + B
        CW = W + B
        OL = L + 2 * B
        OW = W + 2 * B
            
    Dim P1 As Variant
    Dim P2 As Variant
    Dim P3 As Variant
    Dim P4 As Variant
    Dim P5 As Variant
    
    Dim P6 As Variant
    Dim P7 As Variant
    Dim P8 As Variant
    Dim P9 As Variant
    Dim P10 As Variant
    
    Dim P11 As Variant
    Dim P12 As Variant
    Dim P13 As Variant
    Dim P14 As Variant
    Dim P15 As Variant
    
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), W / 2)
        P2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), CW / 2)
        P3 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), OW / 2)
        P4 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 180), L / 2)
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(RotAng + 270), W)
        
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(RotAng + 0), L)
        P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(RotAng + 90), W)
        P8 = ThisDrawing.Utility.PolarPoint(P2, Dtr(RotAng + 180), CL / 2)
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(RotAng + 270), CW)
        P10 = ThisDrawing.Utility.PolarPoint(P9, Dtr(RotAng + 0), CL)
        
        P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(RotAng + 90), CW)
        P12 = ThisDrawing.Utility.PolarPoint(P3, Dtr(RotAng + 180), OL / 2)
        P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(RotAng + 270), OW)
        P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(RotAng + 0), OL)
        P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(RotAng + 90), OW)
        
        If Left$(Direction, 2) <> "RL" And Left$(Direction, 2) <> "LL" Then
        
            pntCol.Add P12
            pntCol.Add P13
            pntCol.Add P14
            pntCol.Add P15
        
            MakePntArray
        
            Dim rFlangeEnt As AcadPolyline
            Set rFlangeEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
            With rFlangeEnt
                .Closed = True
                .Highlight True
                .Update
            End With
        
            Set AutoTrim.Ent = rFlangeEnt
            AutoTrim.DoTrim
            rFlangeEnt.Delete
        
        End If
    
        
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
    
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P4, P7)
        Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P5, P4)
        Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P5, P6)
        Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P6, P7)
        Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P8, P11)
            Line5.color = acRed
            Line5.Linetype = "Center"
            Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P8, P9)
            Line6.color = acRed
            Line6.Linetype = "Center"
            Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P9, P10)
            Line7.color = acRed
            Line7.Linetype = "Center"
            Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P10, P11)
            Line8.color = acRed
            Line8.Linetype = "Center"
            Line8.Update
        
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P12, P15)
        Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P13, P12)
        Line10.Update
        Set Line11 = ThisDrawing.ModelSpace.AddLine(P13, P14)
        Line11.Update
        Set Line12 = ThisDrawing.ModelSpace.AddLine(P14, P15)
        Line12.Update
    
    ' Bolt Hole 그리기
    Dim Cir1 As AcadCircle
    Dim Cir2 As AcadCircle
    Dim Cir3 As AcadCircle
    Dim Cir4 As AcadCircle
        Set Cir1 = ThisDrawing.ModelSpace.AddCircle(P8, BD / 2)
        Cir1.color = acCyan
        Cir1.Update
        Set Cir2 = ThisDrawing.ModelSpace.AddCircle(P9, BD / 2)
        Cir2.color = acCyan
        Cir2.Update
        Set Cir3 = ThisDrawing.ModelSpace.AddCircle(P10, BD / 2)
        Cir3.color = acCyan
        Cir3.Update
        Set Cir4 = ThisDrawing.ModelSpace.AddCircle(P11, BD / 2)
        Cir4.color = acCyan
        Cir4.Update
            
    
    ' Bolt Hole Pitch 계산
    Dim Pitch As Double
        Pitch = 140 * ((B * t ^ 3) / 36450) ^ (1 / 3) '원래 120
        
        
    ' Bolt Hole 수 계산
    Dim LBN As Integer
    Dim WBN As Integer
        LBN = Int(CL / Pitch) + 1
        WBN = Int(CW / Pitch) + 1
    Dim vSpace As Double
    Dim hSpace As Double
        vSpace = CW / WBN
        hSpace = CL / LBN
    
    If RotAng = 0 Then
        Cir1.ArrayRectangular 1, LBN, 1, 0, hSpace, 1
        Cir2.ArrayRectangular 1, LBN, 1, 0, hSpace, 1
        Cir2.ArrayRectangular WBN, 1, 1, vSpace, 0, 1
        Cir3.ArrayRectangular WBN, 1, 1, vSpace, 0, 1
        
        ElseIf RotAng = -90 Then
            Cir2.ArrayRectangular 1, LBN, 1, 0, hSpace, 1
            Cir3.ArrayRectangular 1, LBN, 1, 0, hSpace, 1
            Cir3.ArrayRectangular WBN, 1, 1, vSpace, 0, 1
            Cir4.ArrayRectangular WBN, 1, 1, vSpace, 0, 1
    End If
    
    If CallFromPCP7 Then
        pCenP7 = P3
        pCenP8 = ThisDrawing.Utility.PolarPoint(P3, Dtr(RotAng + 270), idWidth + 2 * B)
        CallFromPCP7 = False
    End If
    
    If CallFromRCP7 Then
        rCenP7 = P3
        rCenP8 = ThisDrawing.Utility.PolarPoint(P3, Dtr(RotAng + 270), idWidth + 2 * B)
        CallFromRCP7 = False
    End If
    
    ' 치수점 할당
    If frmInput.optDirect Then ' 직결형일 때
        
        If Direction = "RH" Then
            dimP11 = P4
            dimP12 = P5
            dimP13 = P6
        End If
    
        If Direction = "RR" Then
            dimP14 = P5
            dimP15 = P4
            dimP16 = P6
        End If
    
        If Direction = "LH" Then
            dimP11 = P5
            dimP12 = P6
            dimP13 = P7
        End If
    
        Else ' V=Belt 전동시
            If Left$(Direction, 1) = "R" Then
                dimP15 = P5
                dimP16 = P4
                
                Else
                dimP15 = P6
                dimP16 = P7
            End If
    
    End If
        
End Sub

Public Sub DrawRight() ' 우측면도 작성
    
    Set pntCol = Nothing
    
    ' pcd 계산
    Dim pcd As Double
        pcd = idWidth + B
    ' od 계산
    Dim OD As Double
        OD = idWidth + 2 * B
    
    ' Point Calculation
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
    
        Pnt1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), idWidth / 2)
        Pnt2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), (pcd - BD) / 2)
        Pnt3 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), pcd / 2)
        Pnt4 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 90), t)
        Pnt5 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 180), BD / 2)
        
        Pnt6 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), OD / 2)
        Pnt7 = ThisDrawing.Utility.PolarPoint(Pnt6, Dtr(RotAng + 270), t)
        Pnt8 = ThisDrawing.Utility.PolarPoint(Pnt5, Dtr(RotAng + 270), t)
        Pnt9 = ThisDrawing.Utility.PolarPoint(Pnt3, Dtr(RotAng + 270), t)
        Pnt10 = ThisDrawing.Utility.PolarPoint(Pnt9, Dtr(RotAng + 270), t)
        
        Pnt11 = ThisDrawing.Utility.PolarPoint(Pnt2, Dtr(RotAng + 270), t)
        Pnt12 = ThisDrawing.Utility.PolarPoint(Pnt1, Dtr(RotAng + 270), t)
        Pnt13 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 270), t)
        Pnt14 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), idWidth / 2)
        Pnt15 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), (pcd - BD) / 2)
        
        Pnt16 = ThisDrawing.Utility.PolarPoint(Pnt15, Dtr(RotAng + 0), BD / 2)
        Pnt17 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 270), t)
        Pnt18 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 0), BD / 2)
        Pnt19 = ThisDrawing.Utility.PolarPoint(Pnt13, Dtr(RotAng + 0), OD / 2)
        Pnt20 = ThisDrawing.Utility.PolarPoint(Pnt19, Dtr(RotAng + 90), t)
        
        Pnt21 = ThisDrawing.Utility.PolarPoint(Pnt18, Dtr(RotAng + 90), t)
        Pnt22 = ThisDrawing.Utility.PolarPoint(Pnt16, Dtr(RotAng + 90), t)
        Pnt23 = ThisDrawing.Utility.PolarPoint(Pnt22, Dtr(RotAng + 90), t)
        Pnt24 = ThisDrawing.Utility.PolarPoint(Pnt15, Dtr(RotAng + 90), t)
        Pnt25 = ThisDrawing.Utility.PolarPoint(Pnt14, Dtr(RotAng + 90), t)
        
        pntCol.Add Pnt6
        pntCol.Add Pnt7
        pntCol.Add Pnt19
        pntCol.Add Pnt20
        
        MakePntArray
        
        Dim rFlangeEnt As AcadPolyline
        Set rFlangeEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        With rFlangeEnt
            .Closed = True
            .Highlight True
            .Update
        End With
        
        Set AutoTrim.Ent = rFlangeEnt
        AutoTrim.DoTrim
        rFlangeEnt.Delete
        
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
            
            Line1.Update
            Line2.Update
            Line3.Update
            Line4.Update
            
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
            
            Line5.Update
            Line6.Update
            Line7.Update
            Line8.Update
            Line9.Update
            Line10.Update
            Line11.Update
            Line12.Update
        
    ' 치수 Point 할당
    If frmInput.optDirect Then ' 직결구동일 경우
            If Direction = "RH" Then
                dimP4 = Pnt20
            End If
        
            If Direction = "RL" Then
                If FrontRecFlange Then
                    dimP5 = Pnt20
                    dimP6 = Pnt25
                    dimP7 = Pnt1
                    FrontRecFlange = False
                
                    ElseIf PlanRecFlange Then
                        dimP12 = Pnt1
                        dimP13 = Pnt25
                        PlanRecFlange = False
                End If
            End If
        
            If Direction = "RR" Then
                dimP5 = Pnt6
            End If
        
            If Direction = "LH" Then
                dimP4 = Pnt20
            End If
                
            If Direction = "LL" Then
                If FrontRecFlange Then
                    dimP5 = Pnt20
                    dimP6 = Pnt25
                    dimP7 = Pnt1
                    FrontRecFlange = False
                
                    ElseIf PlanRecFlange Then
                    dimP12 = Pnt25
                    dimP13 = Pnt1
                    PlanRecFlange = False
                End If
            End If
                
            If Direction = "LR" Then
                If FrontRecFlange Then
                    dimP4 = Pnt25
                    dimP5 = Pnt1
                    dimP7 = Pnt6
                    FrontRecFlange = False
                
                    ElseIf PlanRecFlange Then
                    dimP15 = Pnt25
                    dimP16 = Pnt1
                    PlanRecFlange = False
                End If
            End If
        
        Else ' V-Belt 구동일 경우
            If FrontRecFlange Then
                dimP6 = Pnt1
                dimP7 = Pnt25
                dimP9 = Pnt20
                FrontRecFlange = False
                
                ElseIf PlanRecFlange Then
                    dimP15 = Pnt1
                    dimP16 = Pnt25
                    PlanRecFlange = False
                    
                ElseIf RightRecFlange Then
                    dimP28 = Pnt6
                    RightRecFlange = False
                    
            End If
            
    End If
        
End Sub

Private Sub DataCalculation()
    
    ' Bolt Hole Pitch 계산
    Pitch = 120 * ((B * t ^ 3) / 36450) ^ (1 / 3)
    
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

