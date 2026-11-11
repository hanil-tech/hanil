Attribute VB_Name = "cFanCasing"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

Public CenterPoint As Variant ' 도면 중심점
Public Direction As String ' 송풍기 회전 및 토출방향 (RH,LH,RR,LL,RL,LR)
Public D3 As Double ' 원심시초원 직경
Public Lout As Double ' 토출구 길이
Public Wout As Double ' 토출구 폭
Public D2 As Double
Public D1 As Double
Public InletDia As Double
Public cHeight As Double

' 중심선을 위한점

' 정면도용
Public cPnt1 As Variant ' 중심 좌측
Public cPnt2 As Variant ' 중심 우측
Public cPnt3 As Variant ' 중심 하부
Public cPnt4 As Variant ' 중심 상부
Public cPnt5 As Variant ' 토출 하부
Public cPnt6 As Variant ' 토출 상부

' FanBase 정면도 작도시 사용
Public TrimEnt1 As AcadLine
Public TrimEnt2 As AcadLine


' 다음 작도를 위한 기준점
Public ConPnt1 As Variant
Public ConPnt2 As Variant
Public ConPnt3 As Variant
Public ConPnt4 As Variant

Dim Mirror As Boolean ' 거울 영상 여부
Dim RotAng As Double ' 회전각도 Degree(+90 또는 -90도)
' 거리
Dim Dist1 As Double ' 중심에서 0도 점과과의 거리
Dim Dist2 As Double ' 중심에서 90도 점과과의 거리
Dim Dist3 As Double ' 중심에서 180도 점과과의 거리
Dim Dist4 As Double ' 중심에서 270도 점과과의 거리
Dim Dist5 As Double ' 바닥에서 케이싱 하단까지의 거리
Dim Dist6 As Double ' 토출 플랜지까지의 거리
Dim Dist7 As Double ' 중심에서 높이 = Dist5 + Dist2

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
    
    Dim fcA As Double
    Dim fcB As Double
    Dim fcC As Double
    Dim fcD As Double

Dim pntArray() As Double
Dim pntCol As New Collection


Public Sub DrawFront() ' 정면도 작성
    
    Select Case Direction
        Case "RH"
            RotAng = 0
            Mirror = False
        Case "RL"
            RotAng = 90
            Mirror = False
        Case "RR"
            RotAng = -90
            Mirror = False
            
        Case "LH"
            RotAng = 0
            Mirror = True
        Case "LL"
            RotAng = 90
            Mirror = True
        Case "LR"
            RotAng = -90
            Mirror = True
    End Select
    
    
    Dim R1 As Double
    Dim R2 As Double
    Dim R3 As Double
    Dim R4 As Double
    Dim R5 As Double
    Dim R6 As Double
    Dim R7 As Double
    Dim R8 As Double
    Dim tAng As Double
    Dim tH As Double
    
        tH = Sqr((D3 / 2) ^ 2 - ((D3 - Lout) / 2) ^ 2)
        tAng = Dtr(270) + Atn(((D3 - Lout) / 2) / tH)
        
        
        Dist1 = D3 / 2 + Lout / 2
        Dist2 = Dist1 - Lout / 2 * Dtr(90) / tAng
        Dist3 = Dist1 - Lout / 2 * Dtr(180) / tAng
        Dist4 = Dist1 - Lout / 2 * Dtr(270) / tAng
        
        Select Case D2 ' 회전차 직경에 따라 Dist5를 결정
            Case 0 To 0.318 ' 0~2.5호
                Dist5 = 10
            Case 0.318 To 0.5334 ' 2.5~3.5호
                Dist5 = 20
            Case 0.5334 To 0.762 ' 3.5~5호
                Dist5 = 30
            Case 0.762 To 0.9906 '5~6.5호
                Dist5 = 40
            Case Is > 0.9906
                Dist5 = 50
        End Select
        
        Select Case Direction ' 방향에 따라 높이 달라짐
            Case "RH", "LH"
                Dist7 = Int((Dist2 + Dist5) / 10) * 10 + 10
            Case "RR", "LL"
                Dist7 = Int((Dist3 + Dist5) / 10) * 10 + 10
            Case "RL", "LR"
                Dist7 = Int((Dist1 + Dist5) / 10) * 10 + 10
        End Select
            
        Dist5 = Dist7 - Dist2
        Dist6 = Int((0.6 * D3) / 10) * 10
        
        R1 = Dist1 - (Lout / 2) * (1 / 8)
        R2 = Dist1 - (Lout / 2) * (2 / 8)
        R3 = Dist1 - (Lout / 2) * (3 / 8)
        R4 = Dist1 - (Lout / 2) * (4 / 8)
        R5 = Dist1 - (Lout / 2) * (5 / 8)
        R6 = Dist1 - (Lout / 2) * (6 / 8)
        R7 = Dist1 - (Lout / 2) * (7 / 8)
        R8 = Dist1 - (Lout / 2) * (8 / 8)
        
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
    Dim tmpPnt As Variant
    
    
        If Mirror = False Then
            P1 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng), Dist1)
            Else
            P1 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng), Dist1)
        End If
        
        If Mirror = False Then
            P2 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng) + tAng * (1 / 8), R1)
            Else
            P2 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng) - tAng * (1 / 8), R1)
        End If
        
        If Mirror = False Then
            P3 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng) + tAng * (2 / 8), R2)
            Else
            P3 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng) - tAng * (2 / 8), R2)
        End If
        
        If Mirror = False Then
            P4 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng) + tAng * (3 / 8), R3)
            Else
            P4 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng) - tAng * (3 / 8), R3)
        End If
        
        If Mirror = False Then
            P5 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng) + tAng * (4 / 8), R4)
            Else
            P5 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng) - tAng * (4 / 8), R4)
        End If
        
        If Mirror = False Then
            P6 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng) + tAng * (5 / 8), R5)
            Else
            P6 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng) - tAng * (5 / 8), R5)
        End If
        
        If Mirror = False Then
            P7 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng) + tAng * (6 / 8), R6)
            Else
            P7 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng) - tAng * (6 / 8), R6)
        End If
        
        If Mirror = False Then
            P8 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng) + tAng * (7 / 8), R7)
            Else
            P8 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng) - tAng * (7 / 8), R7)
        End If
        
        If Mirror = False Then
            P9 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng) + tAng * (8 / 8), R8)
            Else
            P9 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng) - tAng * (8 / 8), R8)
        End If
        
        P10 = ThisDrawing.Utility.PolarPoint(P1, Dtr(90 + RotAng), Dist6)

        If Mirror = False Then
            P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(0 + RotAng), Lout / 2)
            Else
            P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(180 + RotAng), Lout / 2)
        End If

        If Mirror = False Then
            P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(0 + RotAng), Lout / 2)
            Else
            P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(180 + RotAng), Lout / 2)
        End If

        P13 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(270), Dist7)
        
        If Mirror = False Then
            P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(180), D3 / 2)
            Else
            P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(0), D3 / 2)
        End If
        
        If Mirror = False Then
            P15 = ThisDrawing.Utility.PolarPoint(P13, Dtr(0), D3 / 2)
            Else
            P15 = ThisDrawing.Utility.PolarPoint(P13, Dtr(180), D3 / 2)
        End If
        
    Dim Cir1 As AcadCircle
    Dim Cir2 As AcadCircle
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    Dim Line5 As AcadLine
    
    Dim Arc1 As AcadArc
    Dim Arc2 As AcadArc
    Dim Arc3 As AcadArc
    Dim Arc4 As AcadArc
    Dim Arc5 As AcadArc
    Dim Arc6 As AcadArc
    Dim Arc7 As AcadArc
    Dim Arc8 As AcadArc
        
        Set Cir1 = ThisDrawing.ModelSpace.AddCircle(CenterPoint, D3 / 2)
            Cir1.color = 5
            Cir1.Update
        
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P1, P10)
        Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P10, P12)
        Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P12, P9)
        Line3.Update
        
    Dim tmpCir1 As AcadCircle
    Dim tmpCir2 As AcadCircle
    Dim cP1(0 To 2) As Double
    Dim cP2(0 To 2) As Double
    Dim IntP As Variant
    Dim ArcCenP1(0 To 2) As Double
    Dim ArcCenP2(0 To 2) As Double
    Dim ArcCenP3(0 To 2) As Double
    Dim ArcCenP4(0 To 2) As Double
    Dim ArcCenP5(0 To 2) As Double
    Dim ArcCenP6(0 To 2) As Double
    Dim ArcCenP7(0 To 2) As Double
    Dim ArcCenP8(0 To 2) As Double
    Dim tmpLine1 As AcadLine
    Dim tmpLine2 As AcadLine
    Dim sAng As Double
    Dim eAng As Double
    
        ' Arc1 그리기
        Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P1, R1)
        Set tmpCir2 = ThisDrawing.ModelSpace.AddCircle(P2, R1)
        IntP = tmpCir1.IntersectWith(tmpCir2, acExtendNone)
        cP1(0) = IntP(0)
        cP1(1) = IntP(1)
        cP1(2) = IntP(2)
        cP2(0) = IntP(3)
        cP2(1) = IntP(4)
        cP2(2) = IntP(5)
        
        If WhetherIn(cP1, Cir1) Then
            ArcCenP1(0) = cP1(0)
            ArcCenP1(1) = cP1(1)
            ArcCenP1(2) = cP1(2)
            Else
            ArcCenP1(0) = cP2(0)
            ArcCenP1(1) = cP2(1)
            ArcCenP1(2) = cP2(2)
        End If
        
        Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(ArcCenP1, P1)
        Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(ArcCenP1, P2)
        
        If Mirror = False Then
            sAng = tmpLine1.Angle
            eAng = tmpLine2.Angle
            Else
            sAng = tmpLine2.Angle
            eAng = tmpLine1.Angle
        End If
        
        Set Arc1 = ThisDrawing.ModelSpace.AddArc(ArcCenP1, R1, sAng, eAng)
        
        tmpCir1.Delete
        tmpCir2.Delete
        tmpLine1.Delete
        tmpLine2.Delete
        Arc1.Update
        
        ' Arc2 그리기
        Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P2, R2)
        Set tmpCir2 = ThisDrawing.ModelSpace.AddCircle(P3, R2)
        IntP = tmpCir1.IntersectWith(tmpCir2, acExtendNone)
        cP1(0) = IntP(0)
        cP1(1) = IntP(1)
        cP1(2) = IntP(2)
        cP2(0) = IntP(3)
        cP2(1) = IntP(4)
        cP2(2) = IntP(5)
        
        If WhetherIn(cP1, Cir1) Then
            ArcCenP2(0) = cP1(0)
            ArcCenP2(1) = cP1(1)
            ArcCenP2(2) = cP1(2)
            Else
            ArcCenP2(0) = cP2(0)
            ArcCenP2(1) = cP2(1)
            ArcCenP2(2) = cP2(2)
        End If
        
        Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(ArcCenP2, P2)
        Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(ArcCenP2, P3)
        
        If Mirror = False Then
            sAng = tmpLine1.Angle
            eAng = tmpLine2.Angle
            Else
            sAng = tmpLine2.Angle
            eAng = tmpLine1.Angle
        End If
        
        Set Arc2 = ThisDrawing.ModelSpace.AddArc(ArcCenP2, R2, sAng, eAng)
        
        tmpCir1.Delete
        tmpCir2.Delete
        tmpLine1.Delete
        tmpLine2.Delete
        Arc2.Update
        
        ' Arc3 그리기
        Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P3, R3)
        Set tmpCir2 = ThisDrawing.ModelSpace.AddCircle(P4, R3)
        IntP = tmpCir1.IntersectWith(tmpCir2, acExtendNone)
        cP1(0) = IntP(0)
        cP1(1) = IntP(1)
        cP1(2) = IntP(2)
        cP2(0) = IntP(3)
        cP2(1) = IntP(4)
        cP2(2) = IntP(5)
        
        If WhetherIn(cP1, Cir1) Then
            ArcCenP3(0) = cP1(0)
            ArcCenP3(1) = cP1(1)
            ArcCenP3(2) = cP1(2)
            Else
            ArcCenP3(0) = cP2(0)
            ArcCenP3(1) = cP2(1)
            ArcCenP3(2) = cP2(2)
        End If
        
        Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(ArcCenP3, P3)
        Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(ArcCenP3, P4)
        
        If Mirror = False Then
            sAng = tmpLine1.Angle
            eAng = tmpLine2.Angle
            Else
            sAng = tmpLine2.Angle
            eAng = tmpLine1.Angle
        End If
        
        Set Arc3 = ThisDrawing.ModelSpace.AddArc(ArcCenP3, R3, sAng, eAng)
        
        tmpCir1.Delete
        tmpCir2.Delete
        tmpLine1.Delete
        tmpLine2.Delete
        Arc3.Update
        
        ' Arc4 그리기
        Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P4, R4)
        Set tmpCir2 = ThisDrawing.ModelSpace.AddCircle(P5, R4)
        IntP = tmpCir1.IntersectWith(tmpCir2, acExtendNone)
        cP1(0) = IntP(0)
        cP1(1) = IntP(1)
        cP1(2) = IntP(2)
        cP2(0) = IntP(3)
        cP2(1) = IntP(4)
        cP2(2) = IntP(5)
        
        If WhetherIn(cP1, Cir1) Then
            ArcCenP4(0) = cP1(0)
            ArcCenP4(1) = cP1(1)
            ArcCenP4(2) = cP1(2)
            Else
            ArcCenP4(0) = cP2(0)
            ArcCenP4(1) = cP2(1)
            ArcCenP4(2) = cP2(2)
        End If
        
        Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(ArcCenP4, P4)
        Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(ArcCenP4, P5)
        
        If Mirror = False Then
            sAng = tmpLine1.Angle
            eAng = tmpLine2.Angle
            Else
            sAng = tmpLine2.Angle
            eAng = tmpLine1.Angle
        End If
        
        Set Arc4 = ThisDrawing.ModelSpace.AddArc(ArcCenP4, R4, sAng, eAng)
        
        tmpCir1.Delete
        tmpCir2.Delete
        tmpLine1.Delete
        tmpLine2.Delete
        Arc4.Update
        
        ' Arc5 그리기
        Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P5, R5)
        Set tmpCir2 = ThisDrawing.ModelSpace.AddCircle(P6, R5)
        IntP = tmpCir1.IntersectWith(tmpCir2, acExtendNone)
        cP1(0) = IntP(0)
        cP1(1) = IntP(1)
        cP1(2) = IntP(2)
        cP2(0) = IntP(3)
        cP2(1) = IntP(4)
        cP2(2) = IntP(5)
        
        If WhetherIn(cP1, Cir1) Then
            ArcCenP5(0) = cP1(0)
            ArcCenP5(1) = cP1(1)
            ArcCenP5(2) = cP1(2)
            Else
            ArcCenP5(0) = cP2(0)
            ArcCenP5(1) = cP2(1)
            ArcCenP5(2) = cP2(2)
        End If
        
        Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(ArcCenP5, P5)
        Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(ArcCenP5, P6)
        
        If Mirror = False Then
            sAng = tmpLine1.Angle
            eAng = tmpLine2.Angle
            Else
            sAng = tmpLine2.Angle
            eAng = tmpLine1.Angle
        End If
        
        Set Arc5 = ThisDrawing.ModelSpace.AddArc(ArcCenP5, R5, sAng, eAng)
        
        tmpCir1.Delete
        tmpCir2.Delete
        tmpLine1.Delete
        tmpLine2.Delete
        Arc5.Update
        
        ' Arc6 그리기
        Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P6, R6)
        Set tmpCir2 = ThisDrawing.ModelSpace.AddCircle(P7, R6)
        IntP = tmpCir1.IntersectWith(tmpCir2, acExtendNone)
        cP1(0) = IntP(0)
        cP1(1) = IntP(1)
        cP1(2) = IntP(2)
        cP2(0) = IntP(3)
        cP2(1) = IntP(4)
        cP2(2) = IntP(5)
        
        If WhetherIn(cP1, Cir1) Then
            ArcCenP6(0) = cP1(0)
            ArcCenP6(1) = cP1(1)
            ArcCenP6(2) = cP1(2)
            Else
            ArcCenP6(0) = cP2(0)
            ArcCenP6(1) = cP2(1)
            ArcCenP6(2) = cP2(2)
        End If
        
        Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(ArcCenP6, P6)
        Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(ArcCenP6, P7)
        
        If Mirror = False Then
            sAng = tmpLine1.Angle
            eAng = tmpLine2.Angle
            Else
            sAng = tmpLine2.Angle
            eAng = tmpLine1.Angle
        End If
        
        Set Arc6 = ThisDrawing.ModelSpace.AddArc(ArcCenP6, R6, sAng, eAng)
        
        tmpCir1.Delete
        tmpCir2.Delete
        tmpLine1.Delete
        tmpLine2.Delete
        Arc6.Update
        
        ' Arc7 그리기
        Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P7, R7)
        Set tmpCir2 = ThisDrawing.ModelSpace.AddCircle(P8, R7)
        IntP = tmpCir1.IntersectWith(tmpCir2, acExtendNone)
        cP1(0) = IntP(0)
        cP1(1) = IntP(1)
        cP1(2) = IntP(2)
        cP2(0) = IntP(3)
        cP2(1) = IntP(4)
        cP2(2) = IntP(5)
        
        If WhetherIn(cP1, Cir1) Then
            ArcCenP7(0) = cP1(0)
            ArcCenP7(1) = cP1(1)
            ArcCenP7(2) = cP1(2)
            Else
            ArcCenP7(0) = cP2(0)
            ArcCenP7(1) = cP2(1)
            ArcCenP7(2) = cP2(2)
        End If
        
        Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(ArcCenP7, P7)
        Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(ArcCenP7, P8)
        
        If Mirror = False Then
            sAng = tmpLine1.Angle
            eAng = tmpLine2.Angle
            Else
            sAng = tmpLine2.Angle
            eAng = tmpLine1.Angle
        End If
        
        Set Arc7 = ThisDrawing.ModelSpace.AddArc(ArcCenP7, R7, sAng, eAng)
        
        tmpCir1.Delete
        tmpCir2.Delete
        tmpLine1.Delete
        tmpLine2.Delete
        Arc7.Update
        
        ' Arc8 그리기
        Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P8, R8)
        Set tmpCir2 = ThisDrawing.ModelSpace.AddCircle(P9, R8)
        IntP = tmpCir1.IntersectWith(tmpCir2, acExtendNone)
        cP1(0) = IntP(0)
        cP1(1) = IntP(1)
        cP1(2) = IntP(2)
        cP2(0) = IntP(3)
        cP2(1) = IntP(4)
        cP2(2) = IntP(5)
        
        If WhetherIn(cP1, Cir1) Then
            ArcCenP8(0) = cP1(0)
            ArcCenP8(1) = cP1(1)
            ArcCenP8(2) = cP1(2)
            Else
            ArcCenP8(0) = cP2(0)
            ArcCenP8(1) = cP2(1)
            ArcCenP8(2) = cP2(2)
        End If
        
        Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(ArcCenP8, P8)
        Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(ArcCenP8, P9)
        
        If Mirror = False Then
            sAng = tmpLine1.Angle
            eAng = tmpLine2.Angle
            Else
            sAng = tmpLine2.Angle
            eAng = tmpLine1.Angle
        End If
        
        Set Arc8 = ThisDrawing.ModelSpace.AddArc(ArcCenP8, R8, sAng, eAng)
        
        tmpCir1.Delete
        tmpCir2.Delete
        tmpLine1.Delete
        tmpLine2.Delete
        Arc8.Update
        
        
        ' P14, P15와 접하는 Arc성분의 발견과 접점 찿아내기
        ' 참고 : 본 루틴은 현재 지정된 각도 90 또는 -90도 에서만 작동함. 따라서 추후에 임의 각도에 대해서도
        ' 처리할 수 있는 루틴의 개발이 요구되는 바임. 2000. 8. 24.
        Dim eA As Double
        Dim eB As Double
        Dim eC As Double
            
        Select Case Direction
            
            Case "RH", "LH"
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc1.Center, P14)
                eC = tmpLine1.Length
                eA = R1
                eB = Sqr(eC ^ 2 - eA ^ 2)
                Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P14, eB)
                P16 = Arc1.IntersectWith(tmpCir1, acExtendNone) ' P16을 얻어냄
                tmpLine1.Delete
                tmpCir1.Delete
                
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc5.Center, P15)
                eC = tmpLine1.Length
                eA = R5
                eB = Sqr(eC ^ 2 - eA ^ 2)
                Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P15, eB)
                P17 = Arc5.IntersectWith(tmpCir1, acExtendNone) ' P17을 얻어냄
                tmpLine1.Delete
                tmpCir1.Delete
                
                Dim newAng1 As Double
                Dim newAng2 As Double
                Dim newArc1 As AcadArc
                Dim newArc2 As AcadArc
                
                    Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc1.Center, P16)
                    newAng1 = tmpLine1.Angle
                    If Mirror = False Then
                        Set newArc1 = ThisDrawing.ModelSpace.AddArc(Arc1.Center, R1, newAng1, Arc1.EndAngle)
                        Arc1.EndAngle = newAng1
                        Else
                        Set newArc1 = ThisDrawing.ModelSpace.AddArc(Arc1.Center, R1, Arc1.StartAngle, newAng1)
                        Arc1.StartAngle = newAng1
                    End If
                        newArc1.color = 3
                        newArc1.Linetype = "Hidden"
                    tmpLine1.Delete
                    Arc1.Update
                    newArc1.Update
                    
                    Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc5.Center, P17)
                    newAng2 = tmpLine1.Angle
                    If Mirror = False Then
                        Set newArc2 = ThisDrawing.ModelSpace.AddArc(Arc5.Center, R5, Arc5.StartAngle, newAng2)
                        Arc5.StartAngle = newAng2
                        Else
                        Set newArc2 = ThisDrawing.ModelSpace.AddArc(Arc5.Center, R5, newAng2, Arc5.EndAngle)
                        Arc5.EndAngle = newAng2
                    End If
                    newArc2.color = 3
                    newArc2.Linetype = "Hidden"
                    tmpLine1.Delete
                    Arc2.color = 3
                    Arc2.Linetype = "Hidden"
                    Arc2.Update
                    Arc3.color = 3
                    Arc3.Linetype = "Hidden"
                    Arc3.Update
                    Arc4.color = 3
                    Arc4.Linetype = "Hidden"
                    Arc4.Update
                    
                    Arc5.Update
                    newArc2.Update
                    
            Case "RR", "LL"
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc3.Center, P14)
                eC = tmpLine1.Length
                eA = R3
                eB = Sqr(eC ^ 2 - eA ^ 2)
                Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P14, eB)
                P16 = Arc3.IntersectWith(tmpCir1, acExtendNone) ' P16을 얻어냄
                
                tmpLine1.Delete
                tmpCir1.Delete
                
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc8.Center, P15)
                eC = tmpLine1.Length
                eA = R8
                eB = Sqr(eC ^ 2 - eA ^ 2)
                Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P15, eB)
                P17 = Arc8.IntersectWith(tmpCir1, acExtendNone) ' P17을 얻어냄
                
                If UBound(P17) = -1 Then ' 접점이 없다면 다음 Arc를 검사
                    tmpLine1.Delete
                    tmpCir1.Delete
                    Dim errFlag As Boolean
                    errFlag = True
                    
                    Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc7.Center, P15)
                    eC = tmpLine1.Length
                    eA = R7
                    eB = Sqr(eC ^ 2 - eA ^ 2)
                    Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P15, eB)
                    P17 = Arc7.IntersectWith(tmpCir1, acExtendNone) ' P17을 얻어냄
                    Else
                End If
                tmpLine1.Delete
                tmpCir1.Delete
                
            
            '접하는 Arc를 2개로 분리
                ' Arc3에 대한 작업
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc3.Center, P16)
                newAng1 = tmpLine1.Angle
                If Mirror = False Then
                    Set newArc1 = ThisDrawing.ModelSpace.AddArc(Arc3.Center, R3, newAng1, Arc3.EndAngle)
                    Arc3.EndAngle = newAng1
                    Else
                    Set newArc1 = ThisDrawing.ModelSpace.AddArc(Arc3.Center, R3, Arc3.StartAngle, newAng1)
                    Arc3.StartAngle = newAng1
                End If
                    newArc1.color = 3
                    newArc1.Linetype = "Hidden"
                    tmpLine1.Delete
                    newArc1.Update
                
                If errFlag Then
                    ' Arc7에 대한 작업
                    Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc7.Center, P17)
                    newAng2 = tmpLine1.Angle
                    If Mirror = False Then
                        Set newArc2 = ThisDrawing.ModelSpace.AddArc(Arc7.Center, R7, Arc7.StartAngle, newAng2)
                        Arc7.StartAngle = newAng2
                        Else
                        Set newArc2 = ThisDrawing.ModelSpace.AddArc(Arc7.Center, R7, newAng2, Arc7.EndAngle)
                        Arc7.EndAngle = newAng2
                    End If
                        newArc2.color = 3
                        newArc2.Linetype = "Hidden"
                        newArc2.Update
                        Arc4.color = 3
                        Arc4.Linetype = "Hidden"
                        Arc4.Update
                        Arc5.color = 3
                        Arc5.Linetype = "Hidden"
                        Arc5.Update
                        Arc6.color = 3
                        Arc6.Linetype = "Hidden"
                        Arc6.Update
                        tmpLine1.Delete
                    
                    Else
                    ' Arc8에 대한 작업
                    Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc8.Center, P17)
                    newAng2 = tmpLine1.Angle
                    If Mirror = False Then
                        Set newArc2 = ThisDrawing.ModelSpace.AddArc(Arc8.Center, R8, Arc8.StartAngle, newAng2)
                        Arc8.StartAngle = newAng2
                        Else
                        Set newArc2 = ThisDrawing.ModelSpace.AddArc(Arc8.Center, R8, newAng2, Arc8.EndAngle)
                        Arc8.EndAngle = newAng2
                    End If
                        newArc2.color = 3
                        newArc2.Linetype = "Hidden"
                        newArc2.Update
                        Arc4.color = 3
                        Arc4.Linetype = "Hidden"
                        Arc4.Update
                        Arc5.color = 3
                        Arc5.Linetype = "Hidden"
                        Arc5.Update
                        Arc6.color = 3
                        Arc6.Linetype = "Hidden"
                        Arc6.Update
                        Arc7.color = 3
                        Arc7.Linetype = "Hidden"
                        Arc7.Update
                        tmpLine1.Delete
                End If
                    
            Case "RL", "LR"
                tmpPnt = ThisDrawing.Utility.PolarPoint(P14, Dtr(90), 0.1)
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(P14, tmpPnt)
                P16 = tmpLine1.IntersectWith(Line1, acExtendThisEntity) ' P16을 얻어냄
                tmpLine1.Delete
                
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc2.Center, P15)
                eC = tmpLine1.Length
                eA = R2
                eB = Sqr(eC ^ 2 - eA ^ 2)
                Set tmpCir1 = ThisDrawing.ModelSpace.AddCircle(P15, eB)
                P17 = Arc2.IntersectWith(tmpCir1, acExtendNone) ' P17을 얻어냄
                If UBound(P17) = -1 Then P17 = Arc2.EndPoint
                tmpLine1.Delete
                tmpCir1.Delete
                
                Dim newLine As AcadLine
                    Set newLine = ThisDrawing.ModelSpace.AddLine(P16, P1)
                    Line1.StartPoint = P16
                    Line1.Update
                        newLine.color = 3
                        newLine.Linetype = "Hidden"
                        newLine.Update
                    
                    Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Arc2.Center, P17)
                    newAng2 = tmpLine1.Angle
                    If Mirror = False Then
                        Set newArc2 = ThisDrawing.ModelSpace.AddArc(Arc2.Center, R2, Arc2.StartAngle, newAng2)
                        Arc2.StartAngle = newAng2
                        Else
                        Set newArc2 = ThisDrawing.ModelSpace.AddArc(Arc2.Center, R2, newAng2, Arc2.EndAngle)
                        Arc2.EndAngle = newAng2
                    End If
                    newArc2.color = 3
                    newArc2.Linetype = "Hidden"
                    Arc2.Update
                    Arc1.color = 3
                    Arc1.Linetype = "Hidden"
                    Arc1.Update
                    tmpLine1.Delete
        
        End Select
        
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P14, P16)
        Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P15, P17)
        Line5.Update
        
        If D1 < InletDia Then
            Set Cir2 = ThisDrawing.ModelSpace.AddCircle(CenterPoint, D1 / 2)
            Cir2.color = 4
            Cir2.Update
        End If
        
        
        ' 외부에 돌려줄 자료
        Set TrimEnt1 = Line4
        Set TrimEnt2 = Line5
        
        ConPnt1 = P11
        ConPnt2 = P14
        ConPnt3 = P15
        
        If Mirror = False Then
            cPnt1 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng), Dist1 * 1.1)
            Else
            cPnt1 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng), Dist1 * 1.1)
        End If
        If Mirror = False Then
            cPnt2 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0 + RotAng), Dist3 * 1.1)
            Else
            cPnt2 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180 + RotAng), Dist3 * 1.1)
        End If
        cPnt3 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(270 + RotAng), Dist2 * 1.1)
        cPnt4 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(90 + RotAng), Dist4 * 1.1)
        
        cPnt5 = ThisDrawing.Utility.PolarPoint(P11, Dtr(270 + RotAng), 0.5 * Lout)
        cPnt6 = ThisDrawing.Utility.PolarPoint(P11, Dtr(90 + RotAng), 0.1 * Lout)
        
        cHeight = Dist7
        
End Sub

Public Sub DrawPlan() ' 평면도 작성
    
    Set pntCol = Nothing
    
        Select Case D2 ' 회전차 직경에 따라 Dist5를 결정
            Case 0 To 0.3048 ' 0~2.0호
                fcC = 50
                fcD = 2.3
            Case 0.3048 To 0.381 ' 2.0~2.5호
                fcC = 50
                fcD = 3.2
            Case 0.381 To 0.4572 ' 2.5~3.0호
                fcC = 50
                fcD = 3.2
            Case 0.4572 To 0.5334 '3.0~3.5호
                fcC = 60
                fcD = 3.2
            Case 0.5334 To 0.6096 '3.5~4.0호
                fcC = 70
                fcD = 4
            Case 0.6096 To 0.6858 '4.0~4.5호
                fcC = 70
                fcD = 4.5
            Case 0.6858 To 0.762 '4.5~5.0호
                fcC = 80
                fcD = 4.5
            Case 0.762 To 0.8382 '5.0~5.5호
                fcC = 80
                fcD = 6
            Case 0.8382 To 0.9906 '5.5~6.5호
                fcC = 90
                fcD = 6
            Case 0.9906 To 1.143 '6.5~7.5호
                fcC = 100
                fcD = 6
            Case 1.143 To 1.2954 '7.5~8.5호
                fcC = 110
                fcD = 9
            Case Is > 1.2954  '9.5 이상
                fcC = 130
                fcD = 9
        End Select
    
        Select Case Direction
            Case "RH", "LH"
                fcA = Dist1
                fcB = Dist3
            Case "RR", "LL"
                fcA = Dist2
                fcB = Dist6
            Case "RL", "LR"
                fcA = Dist6
                fcB = Dist2
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
    Dim P15 As Variant
    Dim P16 As Variant
    Dim P17 As Variant
    Dim P18 As Variant
    Dim P19 As Variant
    Dim P20 As Variant
    
        P1 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(270), Wout / 2)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), fcC)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(180), InletDia / 2)
        P4 = ThisDrawing.Utility.PolarPoint(P2, Dtr(0), InletDia / 2)
        P5 = ThisDrawing.Utility.PolarPoint(P1, Dtr(180), D3 / 2)
        
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(270), fcD)
        P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(0), D3)
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(90), fcD)
        
        P9 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180), D1 / 2)
        P10 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0), D1 / 2)
        
        Dim tmpLine1 As AcadLine
        Dim tmpLine2 As AcadLine
            Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(P6, P7)
            Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(P3, P9)
        P11 = tmpLine1.IntersectWith(tmpLine2, acExtendNone)
            tmpLine1.Delete
            tmpLine2.Delete
            Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(P6, P7)
            Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(P4, P10)
        P12 = tmpLine1.IntersectWith(tmpLine2, acExtendNone)
            tmpLine1.Delete
            tmpLine2.Delete
        
        If Mirror = False Then
            P13 = ThisDrawing.Utility.PolarPoint(P1, Dtr(0), fcB)
            Else
            P13 = ThisDrawing.Utility.PolarPoint(P1, Dtr(180), fcB)
        End If
        
        P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(90), Wout)
        
        If Mirror = False Then
            P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(180), fcB)
            Else
            P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(0), fcB)
        End If
        
        If Mirror = False Then
            P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(180), fcA)
            Else
            P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(0), fcA)
        End If
        
        P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(270), Wout)
        
        Select Case Direction
            Case "RH"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180), D3 / 2)
            Case "LH"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0), D3 / 2)
            Case "RR"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0), fcB)
            Case "LL"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180), fcB)
            Case "RL"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180), fcA)
                P19 = ThisDrawing.Utility.PolarPoint(P15, Dtr(180), Dist4)
                P20 = ThisDrawing.Utility.PolarPoint(P19, Dtr(270), Wout)
            Case "LR"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0), fcA)
                P19 = ThisDrawing.Utility.PolarPoint(P15, Dtr(0), Dist4)
                P20 = ThisDrawing.Utility.PolarPoint(P19, Dtr(270), Wout)
        End Select
        
        pntCol.Add P16
        pntCol.Add P17
        pntCol.Add P13
        pntCol.Add P14
        
        MakePntArray
        
        Dim pfEnt As AcadPolyline
        Set pfEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        With pfEnt
            .Closed = True
            .Update
            .Highlight True
        End With
        
        Set AutoTrim.Ent = pfEnt
        AutoTrim.DoTrim
        pfEnt.Delete
        
        Set pntCol = Nothing
        pntCol.Add P5
        pntCol.Add P6
        pntCol.Add P11
        pntCol.Add P3
        pntCol.Add P4
        pntCol.Add P12
        pntCol.Add P7
        pntCol.Add P8
        
        MakePntArray
        
        Set pfEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        With pfEnt
            .Closed = True
            .Update
            .Highlight True
        End With
        
        Set AutoTrim.Ent = pfEnt
        AutoTrim.DoTrim
        pfEnt.Delete
        
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
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P17, P13)
        Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P13, P14)
        Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P14, P16)
        Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P16, P17)
        Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P5, P6)
        Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P6, P7)
        Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P7, P8)
            Line5.color = 4
            Line6.color = 4
            Line7.color = 4
            Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P11, P3)
        Line8.Update
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P3, P4)
        Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P4, P12)
        Line10.Update
        
        If Direction = "RL" Or Direction = "LR" Then
            Set Line11 = ThisDrawing.ModelSpace.AddLine(P20, P19)
            Line11.Update
        End If
        
        ' 외부에 돌려줄 자료
        ConPnt1 = P18
        ConPnt2 = P2
        ConPnt3 = P15
        
        pCenP1 = P2
        If Mirror = False Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180), fcA)
            pCenP6 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0), fcB)
            Else
            pCenP5 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(0), fcA)
            pCenP6 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180), fcB)
        End If
        
End Sub

Public Sub DrawRight() ' 우측면도 작성
    
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
    
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P17, P13)
        Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P13, P14)
        Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P14, P16)
        Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P16, P17)
        Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P5, P6)
        Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P6, P7)
        Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P7, P8)
        Line7.Update
            Line5.color = 4
            Line5.Update
            Line6.color = 4
            Line6.Update
            Line7.color = 4
            Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P11, P3)
        Line8.Update
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P3, P4)
        Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P4, P12)
        Line10.Update
        
        If Direction = "RH" Then
            Set Line11 = ThisDrawing.ModelSpace.AddLine(P20, P19)
            Line11.Update
        End If
        
        Set Line12 = ThisDrawing.ModelSpace.AddLine(P13, P21)
        Line12.Update
        Set Line13 = ThisDrawing.ModelSpace.AddLine(P14, P22)
        Line13.Update
        
        
        
        
End Sub

Public Sub PointCal_Right() ' 우측면도를 위한 점의 계산
    
        Select Case D2 ' 회전차 직경에 따라 Dist5를 결정
            Case 0 To 0.3048 ' 0~2.0호
                fcC = 50
                fcD = 2.3
            Case 0.3048 To 0.381 ' 2.0~2.5호
                fcC = 50
                fcD = 3.2
            Case 0.381 To 0.4572 ' 2.5~3.0호
                fcC = 50
                fcD = 3.2
            Case 0.4572 To 0.5334 '3.0~3.5호
                fcC = 60
                fcD = 3.2
            Case 0.5334 To 0.6096 '3.5~4.0호
                fcC = 70
                fcD = 4
            Case 0.6096 To 0.6858 '4.0~4.5호
                fcC = 70
                fcD = 4.5
            Case 0.6858 To 0.762 '4.5~5.0호
                fcC = 80
                fcD = 4.5
            Case 0.762 To 0.8382 '5.0~5.5호
                fcC = 80
                fcD = 6
            Case 0.8382 To 0.9906 '5.5~6.5호
                fcC = 90
                fcD = 6
            Case 0.9906 To 1.143 '6.5~7.5호
                fcC = 100
                fcD = 6
            Case 1.143 To 1.2954 '7.5~8.5호
                fcC = 110
                fcD = 9
            Case Is > 1.2954  '9.5 이상
                fcC = 130
                fcD = 9
        End Select
    
        Select Case Direction
            Case "RH", "LH"
                fcA = Dist6
                fcB = Dist2
            Case "RR", "LL"
                fcA = Dist1
                fcB = Dist3
            Case "RL", "LR"
                fcA = Dist3
                fcB = Dist1
        End Select
    
        P1 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(180), Wout / 2)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(180), fcC)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(90), InletDia / 2)
        P4 = ThisDrawing.Utility.PolarPoint(P2, Dtr(270), InletDia / 2)
        P5 = ThisDrawing.Utility.PolarPoint(P1, Dtr(90), D3 / 2)
        
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(180), fcD)
        P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(270), D3)
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(0), fcD)
        
        P9 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(90), D1 / 2)
        P10 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(270), D1 / 2)
        
        Dim tmpLine1 As AcadLine
        Dim tmpLine2 As AcadLine
            Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(P6, P7)
            Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(P3, P9)
        P11 = tmpLine1.IntersectWith(tmpLine2, acExtendNone)
            tmpLine1.Delete
            tmpLine2.Delete
            Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(P6, P7)
            Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(P4, P10)
        P12 = tmpLine1.IntersectWith(tmpLine2, acExtendNone)
            tmpLine1.Delete
            tmpLine2.Delete
        
        P13 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), fcB)
        P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(0), Wout)
        
        P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(90), fcB)
        P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(90), fcA)
        P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(180), Wout)
        
        Select Case Direction
            Case "RH"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(90), fcA)
                P19 = ThisDrawing.Utility.PolarPoint(P15, Dtr(90), Dist4)
                P20 = ThisDrawing.Utility.PolarPoint(P19, Dtr(180), Wout)
            Case "LH"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(90), fcA)
            Case "RR", "LL"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(90), D3 / 2)
            Case "RL", "LR"
                P18 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(270), D3 / 2)
        End Select
        
        P21 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), Dist7)
        P22 = ThisDrawing.Utility.PolarPoint(P15, Dtr(270), Dist7)
        
        ' 외부에 돌려줄 자료
    
        ConPnt1 = P18
        ConPnt2 = P2
        ConPnt3 = P15
        ConPnt4 = P13
        
        rCenP1 = P2
        rCenP5 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(90), fcA)
        rCenP6 = ThisDrawing.Utility.PolarPoint(CenterPoint, Dtr(270), fcB)
        
End Sub
Public Sub BeforTrimRight()

    Set pntCol = Nothing
    
        pntCol.Add P16
        pntCol.Add P17
        pntCol.Add P13
        pntCol.Add P14
        
        MakePntArray
        
        Dim pfEnt As AcadPolyline
        Set pfEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        With pfEnt
            .Closed = True
            .Update
            .Highlight True
        End With
        
        Set AutoTrim.Ent = pfEnt
        AutoTrim.DoTrim
        pfEnt.Delete
        
        Set pntCol = Nothing
        pntCol.Add P5
        pntCol.Add P6
        pntCol.Add P11
        pntCol.Add P3
        pntCol.Add P4
        pntCol.Add P12
        pntCol.Add P7
        pntCol.Add P8
        
        MakePntArray
        
        Set pfEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        With pfEnt
            .Closed = True
            .Update
            .Highlight True
        End With
        
        Set AutoTrim.Ent = pfEnt
        AutoTrim.DoTrim
        pfEnt.Delete

End Sub

Private Function Dtr(Degree As Double) As Double
    
    Dtr = (Atn(1) * 4) * Degree / 180#
    
End Function

Private Function WhetherIn(pnt As Variant, Ent As AcadEntity) As Boolean
    Dim dLine As AcadLine
    Dim IntP As Variant
    
        WhetherIn = False
    
    Dim UPnt As Variant
        UPnt = ThisDrawing.Utility.PolarPoint(pnt, Dtr(90), 0.1)
    Set dLine = ThisDrawing.ModelSpace.AddLine(pnt, UPnt)
    
    IntP = dLine.IntersectWith(Ent, acExtendThisEntity)
        dLine.Delete
    
    Dim PntNo As Integer
        PntNo = (UBound(IntP) - 2) / 3
    
    ' 얻어진 교점을 Y좌표의 순서대로 정열함
    Dim i As Integer
    Dim j As Integer
    Dim tmpPnt(0 To 2) As Double
    
    For i = 0 To PntNo - 1
        For j = i + 1 To PntNo
            If IntP(3 * i + 1) > IntP(3 * j + 1) Then
                tmpPnt(0) = IntP(3 * i)
                tmpPnt(1) = IntP(3 * i + 1)
                tmpPnt(2) = IntP(3 * i + 2)
                
                IntP(3 * i) = IntP(3 * j)
                IntP(3 * i + 1) = IntP(3 * j + 1)
                IntP(3 * i + 2) = IntP(3 * j + 2)
                
                IntP(3 * j) = tmpPnt(0)
                IntP(3 * j + 1) = tmpPnt(1)
                IntP(3 * j + 2) = tmpPnt(2)
            End If
        Next j
    Next i
    
    For i = 0 To PntNo Step 2
        If pnt(1) > IntP(3 * i + 1) And pnt(1) < IntP(3 * i + 4) Then
            WhetherIn = True
        End If
    Next i
    
End Function


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

