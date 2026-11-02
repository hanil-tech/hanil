Attribute VB_Name = "cDFanBase"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

Public CP As Variant
Public ChanSize As Integer
Public MotorPoint As Variant
Public BossPoint As Variant

Public B As Double
Public H As Double
Public Y1 As Double
Public Y2 As Double

Dim b1 As Double
Dim b2 As Double
Dim t1 As Double
Dim t2 As Double
Dim R1 As Double
Dim R2 As Double
Dim pntArray() As Double

Public Sub DrawFront() ' 정면도 작성
    
    Select Case ChanSize
        Case 75
            H = 75: B = 40: b1 = 15: b2 = 25: t1 = 5: t2 = 7: R1 = 8: R2 = 4: Y1 = 17: Y2 = 23
        Case 100
            H = 100: B = 50: b1 = 20: b2 = 30: t1 = 5: t2 = 7.5: R1 = 8: R2 = 4: Y1 = 22: Y2 = 28
        Case 125
            H = 125: B = 65: b1 = 27: b2 = 38: t1 = 6: t2 = 8: R1 = 8: R2 = 4: Y1 = 29: Y2 = 36
        Case 150
            H = 150: B = 75: b1 = 32: b2 = 43: t1 = 6.5: t2 = 10: R1 = 10: R2 = 5: Y1 = 34: Y2 = 41
        Case 200
            H = 200: B = 90: b1 = 38: b2 = 52: t1 = 8: t2 = 13.5: R1 = 14: R2 = 7: Y1 = 40: Y2 = 50
    End Select
    
    Dim P1 As Variant
    Dim P2 As Variant
    Dim P3 As Variant
    Dim P4 As Variant
    Dim P5 As Variant
    Dim P6 As Variant
    Dim P7 As Variant

        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(270), t2)
        P2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(270), H - t2)
        P3 = ThisDrawing.Utility.PolarPoint(CP, Dtr(270), H)
    
    If Left$(Direction, 1) = "R" Then
        P4 = ThisDrawing.Utility.PolarPoint(P3, Dtr(0), D3)
        Else
        P4 = ThisDrawing.Utility.PolarPoint(P3, Dtr(180), D3)
    End If
    
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(90), t2)
        P6 = ThisDrawing.Utility.PolarPoint(P4, Dtr(90), H - t2)
        P7 = ThisDrawing.Utility.PolarPoint(P4, Dtr(90), H)
        
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    Dim Line5 As AcadLine
    Dim Line6 As AcadLine
        Set Line1 = ThisDrawing.ModelSpace.AddLine(CP, P3)
            Line1.color = acCyan
            Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P3, P4)
            Line2.color = acCyan
            Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P4, P7)
            Line3.color = acCyan
            Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P7, CP)
            Line4.color = acCyan
            Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P1, P6)
            Line5.color = acCyan
            Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P2, P5)
            Line6.color = acCyan
            Line6.Update
    
    ' 치수점 할당
    If Left$(Direction, 1) = "R" Then
        dimP1 = P3
        dimP2 = P4
        Else
        dimP1 = P4
        dimP2 = P3
    End If
    
End Sub

Public Sub DrawPlan() '평면도

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
    Dim P17 As Variant
    
    
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(270), 15 + FanCasing.Wout + B)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(180), (D3 - 2 * B) / 2)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(180), B)
        P4 = ThisDrawing.Utility.PolarPoint(P2, Dtr(90), B)
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(0), D3 - 2 * B)
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(270), B)
        P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(0), B)
    Dim mLeng As Double
        mLeng = Int((2.5 * Motor.C + Motor.B) / 10) * 10 + 10
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(90), 2 * B + FanCasing.Wout + mLeng)
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(180), B)
        P10 = ThisDrawing.Utility.PolarPoint(P9, Dtr(270), B)
        P11 = ThisDrawing.Utility.PolarPoint(P9, Dtr(180), D3 - 2 * B)
        P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(180), B)
        P13 = ThisDrawing.Utility.PolarPoint(P11, Dtr(270), B)
        
    If D3 - 2 * B - Motor.AB > 200 Then
        Dim mbW As Double
        mbW = Int(((D3 - 2 * B - Motor.AB) / 2 - 100) / 10) * 10
        P14 = ThisDrawing.Utility.PolarPoint(P4, Dtr(0), mbW)
        P15 = ThisDrawing.Utility.PolarPoint(P5, Dtr(180), mbW)
        P16 = ThisDrawing.Utility.PolarPoint(P13, Dtr(0), mbW)
        P17 = ThisDrawing.Utility.PolarPoint(P10, Dtr(180), mbW)
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
    
    
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P12, P8)
            Line1.Update
    
    ThisDrawing.Application.ZoomExtents
    ThisDrawing.Application.ZoomScaled 0.8, acZoomScaledRelative
        
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P12, P3)
            Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P3, P7)
            Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P7, P8)
            Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P2, P11)
            Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P6, P9)
            Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P4, P5)
            Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P13, P10)
            Line8.Update
    If D3 - 2 * B - Motor.AB > 200 Then
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P14, P16)
            Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P15, P17)
            Line10.Update
    End If
    

End Sub

Public Sub DrawRight()

' Channel 인스턴스에 치수 할당
    With Channel
        .H = H
        .B = B
        .t1 = t1
        .t2 = t2
        .R1 = R1
        .R2 = R2
    End With
        
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
    
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), Wout / 2)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), Motor.H)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(270), RecFlange.t)
        Dim mLeng
        mLeng = Int((2.5 * Motor.C + Motor.B) / 10) * 10 + 10
        P4 = ThisDrawing.Utility.PolarPoint(P2, Dtr(0), mLeng)
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(270), RecFlange.t)
        P6 = ThisDrawing.Utility.PolarPoint(P4, Dtr(270), FanCasing.cHeight - Motor.H)
        
        P7 = ThisDrawing.Utility.PolarPoint(P2, Dtr(270), FanCasing.cHeight - Motor.H)
        
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(180), FanCasing.Wout)
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(270), t2)
        P10 = ThisDrawing.Utility.PolarPoint(P8, Dtr(270), H - t2)
        P11 = ThisDrawing.Utility.PolarPoint(P8, Dtr(270), H)
        P12 = ThisDrawing.Utility.PolarPoint(P6, Dtr(270), H)
        P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(90), t2)
        P14 = ThisDrawing.Utility.PolarPoint(P6, Dtr(270), t2)
        
    If Direction = "RL" Then
        Set bPntCol = Nothing
        
        bPntCol.Add P4
        bPntCol.Add P2
        bPntCol.Add P7
        
        With Channel
            .CP = P8
            .Mirror = True
            .PointCal
            
            .CP = P6
            .Mirror = False
            .PointCal
        End With
        
        Dim i As Integer
        ReDim pntArray(bPntCol.Count * 3 - 1)
        
        Dim pnt As Variant
    
        For i = 1 To bPntCol.Count
            
            pnt = bPntCol.Item(i)
            pntArray(0 + (i - 1) * 3) = pnt(0)
            pntArray(1 + (i - 1) * 3) = pnt(1)
            pntArray(2 + (i - 1) * 3) = pnt(2)
            
        Next i
        
        Dim bBaseEnt As AcadPolyline
        
        Set bBaseEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        
        With bBaseEnt
            .Closed = True
            '.SetBulge 1, Sqr(2) - 1
            .Highlight True
        End With
        
        Set AutoTrim.Ent = bBaseEnt
        AutoTrim.DoTrim
        bBaseEnt.Delete
    
    End If
        
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    Dim Line5 As AcadLine
    Dim Line6 As AcadLine
    Dim Line7 As AcadLine
        
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P4, P6)
            Line1.Update
    
    ThisDrawing.Application.ZoomExtents
    ThisDrawing.Application.ZoomScaled 0.85, acZoomScaledRelative
    ThisDrawing.Regen acActiveViewport
    
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P4, P2)
            Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P3, P5)
            Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P8, P6)
            Line4.color = acCyan
            Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P11, P12)
            Line5.color = acCyan
            Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P9, P14)
            Line6.color = acCyan
            Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P10, P13)
            Line7.color = acCyan
            Line7.Update
        
    With Channel
        .CP = P8
        .Mirror = True
        .PointCal
        .Draw
        
        .CP = P6
        .Mirror = False
        .PointCal
        .Draw
    End With
    
    MotorPoint = ThisDrawing.Utility.PolarPoint(P2, Dtr(0), 15 + Motor.C + Motor.B / 2)
    BossPoint = ThisDrawing.Utility.PolarPoint(P1, Dtr(0), 15)

End Sub


