Attribute VB_Name = "cFanBase"
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
Public ConPnt1 As Variant ' Motor 자리
Public ConPnt2 As Variant
Public ConPnt3 As Variant
Public ConPnt4 As Variant
Public ConPnt5 As Variant
Public ConPnt6 As Variant

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
Dim RDML As String '회전과 모터위치
Dim pntArray() As Double


Public Sub DrawFront() ' 정면도 작성
    
    RDML = Left$(Direction, 1) + Right$(Direction, 1)
        
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
    Dim P8 As Variant
    Dim P9 As Variant
    Dim P10 As Variant
    Dim P11 As Variant
    Dim P12 As Variant
    Dim P13 As Variant
    Dim P14 As Variant
    
    If RDML = "RL" Or RDML = "LR" Then
        P1 = FanCasing.ConPnt3
        Else
        P1 = FanCasing.ConPnt2
    End If
        
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), t2)
        P3 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), H - t2)
        P4 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), H)
    
    If RDML = "RL" Or RDML = "LL" Then
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(180), MDist + D3)
        Else
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(0), MDist + D3)
    End If
    
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(90), t2)
        P7 = ThisDrawing.Utility.PolarPoint(P5, Dtr(90), H - t2)
        P8 = ThisDrawing.Utility.PolarPoint(P5, Dtr(90), H)
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(90), t2)
        P10 = ThisDrawing.Utility.PolarPoint(P8, Dtr(90), H - t2)
        P11 = ThisDrawing.Utility.PolarPoint(P8, Dtr(90), H)
        
    Dim tmpLine1 As AcadLine
    Dim tmpLine2 As AcadLine
    Dim tmpLine3 As AcadLine
    Dim tmpPnt1 As Variant
    Dim tmpPnt2 As Variant
    Dim tmpPnt3 As Variant
    
    If RDML = "RL" Or RDML = "LL" Then
        tmpPnt1 = ThisDrawing.Utility.PolarPoint(P11, Dtr(0), 0.1)
        tmpPnt2 = ThisDrawing.Utility.PolarPoint(P10, Dtr(0), 0.1)
        tmpPnt3 = ThisDrawing.Utility.PolarPoint(P9, Dtr(0), 0.1)
        Else
        tmpPnt1 = ThisDrawing.Utility.PolarPoint(P11, Dtr(180), 0.1)
        tmpPnt2 = ThisDrawing.Utility.PolarPoint(P10, Dtr(180), 0.1)
        tmpPnt3 = ThisDrawing.Utility.PolarPoint(P9, Dtr(180), 0.1)
    End If
    
    Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(P11, tmpPnt1)
    Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(P10, tmpPnt2)
    Set tmpLine3 = ThisDrawing.ModelSpace.AddLine(P9, tmpPnt3)
    
    If RDML = "RL" Or RDML = "LR" Then
        P12 = tmpLine1.IntersectWith(FanCasing.TrimEnt1, acExtendThisEntity)
        P13 = tmpLine2.IntersectWith(FanCasing.TrimEnt1, acExtendThisEntity)
        P14 = tmpLine3.IntersectWith(FanCasing.TrimEnt1, acExtendThisEntity)
        Else
        P12 = tmpLine1.IntersectWith(FanCasing.TrimEnt2, acExtendThisEntity)
        P13 = tmpLine2.IntersectWith(FanCasing.TrimEnt2, acExtendThisEntity)
        P14 = tmpLine3.IntersectWith(FanCasing.TrimEnt2, acExtendThisEntity)
    End If
    tmpLine1.Delete
    tmpLine2.Delete
    tmpLine3.Delete
    
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
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P1, P4)
            Line1.color = acCyan
            Line1.Update
            
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P4, P5)
            Line2.color = acCyan
            Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P5, P8)
            Line3.color = acCyan
            Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P8, P11)
            Line4.color = acCyan
            Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P11, P12)
            Line5.color = acCyan
            Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P10, P13)
            Line6.color = acCyan
            Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P9, P14)
            Line7.color = acCyan
            Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P8, P1)
            Line8.color = acCyan
            Line8.Update
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P7, P2)
            Line9.color = acCyan
            Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P6, P3)
            Line10.color = acCyan
            Line10.Update
        
    If RDML = "RL" Or RDML = "LL" Then
        ConPnt1 = ThisDrawing.Utility.PolarPoint(P11, Dtr(0), 0.4 * MDist)
    Else
        ConPnt1 = ThisDrawing.Utility.PolarPoint(P11, Dtr(180), 0.4 * MDist)
    End If
    
    ' 치수점 할당
    
    If Right$(Direction, 1) = "L" Then
        
        dimP1 = P5
        dimP3 = P4
        
        Else
        
        dimP1 = P4
        dimP3 = P5
        
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
    Dim P18 As Variant
    Dim P19 As Variant
    Dim P20 As Variant
    
    Dim P21 As Variant
    Dim P22 As Variant
    Dim P23 As Variant
    
    
    Dim eAng As Double
    Dim WAng As Double
    
    If Right$(Direction, 1) = "L" Then
        eAng = 0
        WAng = 180
        Else
        eAng = 180
        WAng = 0
    End If
    
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(270), FanCasing.Wout / 2)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(eAng), BBaseW / 2)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(WAng), BBaseW)
        
        P6 = ThisDrawing.Utility.PolarPoint(P1, Dtr(eAng), D3 / 2)
        P7 = ThisDrawing.Utility.PolarPoint(P1, Dtr(WAng), D3 / 2)
        
        P4 = ThisDrawing.Utility.PolarPoint(P6, Dtr(WAng), B)
        P5 = ThisDrawing.Utility.PolarPoint(P7, Dtr(eAng), B)
        
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(90), FanCasing.Wout + MWidth)
        P9 = ThisDrawing.Utility.PolarPoint(P5, Dtr(90), FanCasing.Wout + MWidth)
        P10 = ThisDrawing.Utility.PolarPoint(P3, Dtr(90), FanCasing.Wout + MWidth)
        P11 = ThisDrawing.Utility.PolarPoint(P2, Dtr(90), FanCasing.Wout + MWidth)
        P12 = ThisDrawing.Utility.PolarPoint(P4, Dtr(90), FanCasing.Wout + MWidth)
        P13 = ThisDrawing.Utility.PolarPoint(P6, Dtr(90), FanCasing.Wout + MWidth)
        
        P14 = ThisDrawing.Utility.PolarPoint(P6, Dtr(270), B)
        P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(WAng), MDist + D3)
        P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(90), B)
        P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(eAng), B)
        P18 = ThisDrawing.Utility.PolarPoint(P16, Dtr(90), FanCasing.Wout + MWidth)
        P19 = ThisDrawing.Utility.PolarPoint(P18, Dtr(90), B)
        P20 = ThisDrawing.Utility.PolarPoint(P18, Dtr(eAng), B)
        P21 = ThisDrawing.Utility.PolarPoint(P14, Dtr(90), FanCasing.Wout + MWidth + 2 * B)
        
        
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
    Dim Line13 As AcadLine
    
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P21, P19)
            Line3.Update
    ThisDrawing.Application.ZoomExtents
    ThisDrawing.Application.ZoomScaled 0.8, acZoomScaledRelative
    ThisDrawing.Regen acActiveViewport
    
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P15, P14)
            Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P14, P21)
            Line2.Update
        
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P19, P15)
            Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P18, P13)
            Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P16, P6)
            Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P18, P13)
            Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P17, P20)
            Line8.Update
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P7, P8)
            Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P5, P9)
            Line10.Update
        Set Line11 = ThisDrawing.ModelSpace.AddLine(P3, P10)
            Line11.Update
        Set Line12 = ThisDrawing.ModelSpace.AddLine(P2, P11)
            Line12.Update
        Set Line13 = ThisDrawing.ModelSpace.AddLine(P4, P12)
            Line13.Update
    
    ' 삽입점 계산
    Dim tmpPnt1 As Variant
        tmpPnt1 = ThisDrawing.Utility.PolarPoint(P18, Dtr(eAng), 0.4 * MDist)
        
    ConPnt1 = ThisDrawing.Utility.PolarPoint(tmpPnt1, Dtr(90), 20)  ' Fan Pulley 삽입점
    ConPnt2 = ThisDrawing.Utility.PolarPoint(ConPnt1, Dtr(270), Motor.C + Motor.B / 2)  '모터 삽입점
    
    ' 모터 슬라이드 베이스 작도 중심점
    ConPnt6 = P19
        
End Sub

Public Sub DrawRight() ' 우측면도 작성
    
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
    Dim P15 As Variant
    Dim P16 As Variant
    Dim P17 As Variant
    Dim P18 As Variant
    Dim P19 As Variant
    Dim P20 As Variant
    
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), Wout / 2)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(0), 40 + SN3.a / 2)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(270), SN3.H)
        P4 = ThisDrawing.Utility.PolarPoint(P1, Dtr(0), 20 + MWidth)
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(180), 20 + SN3.a / 2)
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(270), SN3.H)
        P7 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), SN3.H)
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(270), RecFlange.t)
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(0), MWidth)
        P10 = ThisDrawing.Utility.PolarPoint(P7, Dtr(0), MWidth)
        
        P12 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), FanCasing.cHeight)
        P11 = ThisDrawing.Utility.PolarPoint(P12, Dtr(0), MWidth)
        P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(180), Wout)
        P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(270), t2)
        P15 = ThisDrawing.Utility.PolarPoint(P13, Dtr(270), H - t2)
        P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(270), t2)
        P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(0), Wout + MWidth)
        P18 = ThisDrawing.Utility.PolarPoint(P15, Dtr(0), Wout + MWidth)
        P19 = ThisDrawing.Utility.PolarPoint(P14, Dtr(0), Wout + MWidth)
        P20 = ThisDrawing.Utility.PolarPoint(P4, Dtr(270), FanCasing.cHeight - H - Motor.H)
        
    If Left$(Direction, 2) = "RL" Then
        Set bPntCol = Nothing
        
        bPntCol.Add P10
        bPntCol.Add P7
        bPntCol.Add P12
        
        With Channel
            .CP = P13
            .Mirror = True
            .PointCal
            
            .CP = P11
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
        
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P7, P10)
            Line1.Update
    
    ThisDrawing.Application.ZoomExtents
    ThisDrawing.Application.ZoomScaled 0.85, acZoomScaledRelative
    ThisDrawing.Regen acActiveViewport
    
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P8, P9)
            Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P10, P11)
            Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P13, P11)
            Line4.color = acCyan
            Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P14, P19)
            Line5.color = acCyan
            Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P15, P18)
            Line6.color = acCyan
            Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P16, P17)
            Line7.color = acCyan
            Line7.Update
        
    With Channel
        .CP = P13
        .Mirror = True
        .PointCal
        .Draw
        .CP = P11
        .Mirror = False
        .PointCal
        .Draw
    End With
    
    ' 모터의 위치가 좌측일 때
    If Right$(Direction, 1) = "L" Then
        Dim P21 As Variant
        Dim P22 As Variant
        Dim P23 As Variant
        Dim P24 As Variant
            P21 = ThisDrawing.Utility.PolarPoint(P20, Dtr(90), Motor.DS / 2)
            P22 = ThisDrawing.Utility.PolarPoint(P21, Dtr(180), 20)
            P23 = ThisDrawing.Utility.PolarPoint(P22, Dtr(270), Motor.DS)
            P24 = ThisDrawing.Utility.PolarPoint(P23, Dtr(0), 20)
        Dim Line8 As AcadLine
        Dim Line9 As AcadLine
            Set Line8 = ThisDrawing.ModelSpace.AddLine(P22, P21)
            Set Line9 = ThisDrawing.ModelSpace.AddLine(P23, P24)
                Line8.color = acCyan
                Line9.color = acCyan
    End If
    
    '모터의 위치가 우측일 때 슬라이드 베이스 그리기
    If Right$(Direction, 1) = "R" Then
        Dim P25 As Variant
        Dim P26 As Variant
        Dim P27 As Variant
        Dim P28 As Variant
        Dim P29 As Variant
        Dim P30 As Variant
        Dim P31 As Variant
        Dim mtmpPnt As Variant
            mtmpPnt = ThisDrawing.Utility.PolarPoint(P20, Dtr(180), Motor.C + Y2)
            P25 = ThisDrawing.Utility.PolarPoint(mtmpPnt, Dtr(270), Motor.H)
            P26 = ThisDrawing.Utility.PolarPoint(P25, Dtr(180), Motor.B - 2 * Y2)
            P27 = ThisDrawing.Utility.PolarPoint(P26, Dtr(270), t2)
            P28 = ThisDrawing.Utility.PolarPoint(P26, Dtr(270), H - t2)
            P29 = ThisDrawing.Utility.PolarPoint(P25, Dtr(270), H - t2)
            P30 = ThisDrawing.Utility.PolarPoint(P25, Dtr(270), t2)
            P31 = ThisDrawing.Utility.PolarPoint(P25, Dtr(180), (Motor.B - 2 * Y2) / 2)
        Dim Line10 As AcadLine
        Dim Line11 As AcadLine
        Dim Line12 As AcadLine
            Set Line10 = ThisDrawing.ModelSpace.AddLine(P26, P25)
            Set Line11 = ThisDrawing.ModelSpace.AddLine(P27, P30)
            Set Line12 = ThisDrawing.ModelSpace.AddLine(P28, P29)
                Line10.color = acCyan
                Line11.color = acCyan
                Line12.color = acCyan
        With Channel
            .CP = P25
            .Mirror = False
            .PointCal
            .Draw
            .CP = P26
            .Mirror = True
            .PointCal
            .Draw
        End With
        
    End If
    
    
    ' 접속점 할당
    ConPnt1 = P3
    ConPnt2 = P6
    ConPnt3 = P4
    ConPnt4 = P20
    ConPnt5 = P31
    
    If Right$(Direction, 1) = "L" Then
        rCenP3 = P20
    End If

End Sub
