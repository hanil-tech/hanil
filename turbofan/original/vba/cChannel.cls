Attribute VB_Name = "cChannel"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

Public H As Double
Public B As Double
Public t1 As Double
Public t2 As Double
Public R1 As Double
Public R2 As Double
Public Mirror As Boolean
Public CP As Variant

Dim X1 As Double
Dim X2 As Double
Dim X3 As Double
Dim X4 As Double
Dim X5 As Double
Dim X6 As Double
Dim X7 As Double

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
Dim P16 As Variant
    
Public Sub Draw()
    
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    Dim Line5 As AcadLine
    Dim Line6 As AcadLine
    Dim Line7 As AcadLine
    Dim Line8 As AcadLine
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P1, P2)
            Line1.color = acCyan
            Line1.Update
            
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P2, P3)
            Line2.color = acCyan
            Line2.Update
            
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P3, P4)
            Line3.color = acCyan
            Line3.Update
            
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P6, P7)
            Line4.color = acCyan
            Line4.Update
            
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P9, P10)
            Line5.color = acCyan
            Line5.Update
            
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P12, P13)
            Line6.color = acCyan
            Line6.Update
            
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P15, P16)
            Line7.color = acCyan
            Line7.Update
            
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P16, P1)
            Line8.color = acCyan
            Line8.Update
        
    Dim Arc1 As AcadArc
    Dim Arc2 As AcadArc
    Dim Arc3 As AcadArc
    Dim Arc4 As AcadArc
    
        If Mirror = False Then
            Set Arc1 = ThisDrawing.ModelSpace.AddArc(P5, R2, Dtr(0), Dtr(85))
            Else
            Set Arc1 = ThisDrawing.ModelSpace.AddArc(P5, R2, Dtr(95), Dtr(180))
        End If
        Arc1.color = acCyan
        Arc1.Update
        
        If Mirror = False Then
            Set Arc2 = ThisDrawing.ModelSpace.AddArc(P8, R1, Dtr(180), Dtr(265))
            Else
            Set Arc2 = ThisDrawing.ModelSpace.AddArc(P8, R1, Dtr(275), Dtr(0))
        End If
        Arc2.color = acCyan
        Arc2.Update
        
        If Mirror = False Then
            Set Arc3 = ThisDrawing.ModelSpace.AddArc(P11, R1, Dtr(95), Dtr(180))
            Else
            Set Arc3 = ThisDrawing.ModelSpace.AddArc(P11, R1, Dtr(0), Dtr(85))
        End If
        Arc3.color = acCyan
        Arc3.Update
        
        If Mirror = False Then
            Set Arc4 = ThisDrawing.ModelSpace.AddArc(P14, R2, Dtr(275), Dtr(0))
            Else
            Set Arc4 = ThisDrawing.ModelSpace.AddArc(P14, R2, Dtr(180), Dtr(265))
        End If
        Arc4.color = acCyan
        Arc4.Update
    
    ' 치수점 할당
    If frmInput.optDirect Then ' 직결일 때
    
        If Direction = "RH" Then
            If LeftChannel Then
                dimP16 = P3
                dimP17 = P2
                LeftChannel = False
            
                ElseIf RightChannel Then
                dimP18 = P2
                dimP19 = P3
                RightChannel = False
            End If
        End If
    
        If Direction = "RL" Then
            If LeftChannel Then
                dimP21 = P3
                dimP22 = P2
                LeftChannel = False
            
                ElseIf RightChannel Then
                dimP23 = P2
                dimP24 = P3
                RightChannel = False
            End If
        End If
        
        If Direction = "RR" Then
            If LeftChannel Then
                dimP17 = P3
                dimP18 = P2
                LeftChannel = False
            
                ElseIf RightChannel Then
                dimP19 = P2
                dimP20 = P3
                RightChannel = False
            End If
        End If
    
        If Direction = "LH" Then
            If LeftChannel Then
                dimP16 = P3
                dimP17 = P2
                LeftChannel = False
            
                ElseIf RightChannel Then
                dimP18 = P2
                dimP19 = P3
                RightChannel = False
            End If
        End If
    
        If Direction = "LL" Then
            If LeftChannel Then
                dimP18 = P3
                dimP19 = P2
                LeftChannel = False
            
                ElseIf RightChannel Then
                dimP20 = P2
                dimP21 = P3
                RightChannel = False
            End If
        End If
    
        If Direction = "LR" Then
            If LeftChannel Then
                dimP18 = P3
                dimP19 = P2
                LeftChannel = False
            
                ElseIf RightChannel Then
                dimP20 = P2
                dimP21 = P3
                RightChannel = False
            End If
        End If
            
        Else ' V-Belt 전동시
            If LeftChannel Then
                dimP18 = P3
                dimP19 = P2
                LeftChannel = False
            
                ElseIf RightChannel Then
                dimP20 = P2
                dimP21 = P3
                RightChannel = False
            End If
    End If
    
End Sub

Public Sub PointCal()
        
        X1 = R1 * Tan(Dtr(42.5))
        X2 = R2 * Tan(Dtr(42.5))
        X6 = (B - t1) / 2 * Tan(Dtr(5))
        X3 = t2 - X6 - X2
        X4 = (B - t1) / Cos(Dtr(5)) - X1 - X2
        X5 = (X1 + X4 + X2) * Tan(Dtr(5))
        X7 = H - 2 * (X3 + X2 + X5 + X1)
        
        P1 = CP
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), H)
        If Mirror = False Then
            P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(0), B)
            Else
            P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(180), B)
        End If
        
        P4 = ThisDrawing.Utility.PolarPoint(P3, Dtr(90), X3)
        
        If Mirror = False Then
            P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(180), R2)
            Else
            P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(0), R2)
        End If
        
        If Mirror = False Then
            P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(85), R2)
            Else
            P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(95), R2)
        End If
        
        If Mirror = False Then
            P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(175), X4)
            Else
            P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(5), X4)
        End If
        
        If Mirror = False Then
            P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(85), R1)
            Else
            P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(95), R1)
        End If
        
        If Mirror = False Then
            P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(180), R1)
            Else
            P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(0), R1)
        End If
        
        P10 = ThisDrawing.Utility.PolarPoint(P9, Dtr(90), X7)
        
        If Mirror = False Then
            P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(0), R1)
            Else
            P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(180), R1)
        End If
        If Mirror = False Then
            P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(95), R1)
            Else
            P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(85), R1)
        End If
        
        If Mirror = False Then
            P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(5), X4)
            Else
            P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(175), X4)
        End If
        
        If Mirror = False Then
            P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(95), R2)
            Else
            P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(85), R2)
        End If
        
        If Mirror = False Then
            P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(0), R2)
            Else
            P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(180), R2)
        End If
        
        P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(90), X3)
        
        If Mirror = False Then
            bPntCol.Add P3
            bPntCol.Add P4
            bPntCol.Add P6
            bPntCol.Add P7
            bPntCol.Add P9
            bPntCol.Add P10
            bPntCol.Add P12
            bPntCol.Add P13
            bPntCol.Add P15
            bPntCol.Add P16
            bPntCol.Add P1
            
            Else
            bPntCol.Add P16
            bPntCol.Add P15
            bPntCol.Add P13
            bPntCol.Add P12
            bPntCol.Add P10
            bPntCol.Add P9
            bPntCol.Add P7
            bPntCol.Add P6
            bPntCol.Add P4
            bPntCol.Add P3
        End If

End Sub
