Attribute VB_Name = "FanDraw"
Option Explicit

' 클래스의 인스턴스 생성
Public Cirflange As New cCirFlange
Public FanCasing As New cFanCasing
Public RecFlange As New cRecFlange
Public SN3 As New cSN3
Public Motor As New cMotor
Public VPulley As New cVPulley
Public FanBase As New cFanBase
Public AutoTrim As New cAutoTrim
Public SlideBase As New cSlideBase
Public Shaft As New cShaft
Public Channel As New cChannel

Public BeltCoverPntCol As New Collection '벨트커버작도용 포인트 컬렉션

Dim CP(0 To 2) As Double
Public MDist As Double
Public MWidth As Double
Public TrimEnt1 As AcadLine
Public TrimEnt2 As AcadLine
Public BBaseW As Double
Public D3 As Double

Public bPntCol As New Collection '우측면도에서 자를 Polyline용 포인트 Collection

Public CallFromPCP2 As Boolean
Public CallFromPCP4 As Boolean
Public CallFromPCP7 As Boolean
Public CallFromRCP2 As Boolean
Public CallFromRCP4 As Boolean
Public CallFromRCP7 As Boolean

Public pCenP1 As Variant
Public pCenP2 As Variant
Public pCenP3 As Variant
Public pCenP4 As Variant
Public pCenP5 As Variant
Public pCenP6 As Variant
Public pCenP7 As Variant
Public pCenP8 As Variant

Public rCenP1 As Variant
Public rCenP2 As Variant
Public rCenP3 As Variant
Public rCenP4 As Variant
Public rCenP5 As Variant
Public rCenP6 As Variant
Public rCenP7 As Variant
Public rCenP8 As Variant

Public DFanBase As New cDFanBase ' 직결형 FanBase

' 치수기입용 Point 선언
Public dimP1 As Variant
Public dimP2 As Variant
Public dimP3 As Variant
Public dimP4 As Variant
Public dimP5 As Variant
Public dimP6 As Variant
Public dimP7 As Variant
Public dimP8 As Variant
Public dimP9 As Variant
Public dimP10 As Variant
Public dimP11 As Variant
Public dimP12 As Variant
Public dimP13 As Variant
Public dimP14 As Variant
Public dimP15 As Variant
Public dimP16 As Variant
Public dimP17 As Variant
Public dimP18 As Variant
Public dimP19 As Variant
Public dimP20 As Variant
Public dimP21 As Variant
Public dimP22 As Variant
Public dimP23 As Variant
Public dimP24 As Variant
Public dimP25 As Variant
Public dimP26 As Variant
Public dimP27 As Variant
Public dimP28 As Variant
Public dimP29 As Variant
Public dimP30 As Variant
    
    Dim dmsL1 As AcadDimRotated
    Dim dmsL2 As AcadDimRotated
    Dim dmsL3 As AcadDimRotated
    Dim dmsL4 As AcadDimRotated
    Dim dmsL5 As AcadDimRotated
    Dim dmsL6 As AcadDimRotated
    Dim dmsL7 As AcadDimRotated
    Dim dmsL8 As AcadDimRotated
    Dim dmsL9 As AcadDimRotated
    Dim dmsL10 As AcadDimRotated
    Dim dmsL11 As AcadDimRotated
    Dim dmsL12 As AcadDimRotated
    Dim dmsL13 As AcadDimRotated
    Dim dmsL14 As AcadDimRotated
    Dim dmsL15 As AcadDimRotated

Public LeftChannel As Boolean
Public RightChannel As Boolean

Public FrontRecFlange As Boolean
Public PlanRecFlange As Boolean
Public RightRecFlange As Boolean
Public FrontCirFlange As Boolean
Public PlanCirFlange As Boolean
Public RightCirFlange As Boolean

Dim Sc As Double
Dim Height As Double

Public Sub VBeltDraw()
    '에러무시
    On Error Resume Next
    
    Load_LT
    
    Dim fGab As Double
    fGab = D2 * 6 * ns ^ 0.9 / 20
    If fGab < 30 Then fGab = 30
    If fGab > 100 Then fGab = 100
    D3 = Int((D2 * 1000 + 2 * fGab) / 10) * 10 + 10
    
    Call SetACAD("FanDrawing", D3 / 65)
    
'===========================================================================================
'   정면도 작성
'===========================================================================================
    
    FrontRecFlange = True
    PlanRecFlange = False
    RightRecFlange = False
    FrontCirFlange = True
    PlanCirFlange = False
    RightCirFlange = False
    
    ' 작도 중심점을 (0, 0, 0) 점으로 지정
    
        CP(0) = 0
        CP(1) = 0
        CP(2) = 0
    
    ' 정면도에 흡입구 플랜지 그리기
    With Cirflange
        .CP = CP
        .ID = DiaInlet
        .Matl = material
        .DrawPlan
    End With
    
    LoadData
    
    ' 화면조정
    ThisDrawing.Application.ZoomExtents
    ThisDrawing.Regen acActiveViewport
    ThisDrawing.Application.ZoomScaled 0.3, acZoomScaledRelative
    
    
    ' 정면도에 Fan Casing 그리기
    With FanCasing
        .Direction = Left$(Direction, 2)
        .CenterPoint = CP
        .D1 = D1 * 1000
        .D2 = D2
        .D3 = D3
        .InletDia = DiaInlet
        .Lout = Lout
        .Wout = Wout
        .DrawFront
    End With
        
    ' 정면도에 토출구 플랜지 그리기
    
    With RecFlange
        .B = Cirflange.B
        .BD = Cirflange.BoltHoleDia
        .idLength = Lout
        .idWidth = Wout
        .t = Cirflange.Thickness
        
        Select Case Left(Direction, 2)
            Case "RH", "LH"
                .RotAng = 0
            Case "RR", "LR"
                .RotAng = -90
            Case "RL", "LL"
                .RotAng = 90
        End Select
        
        .CP = FanCasing.ConPnt1
        .DrawFront
    End With
    
    ' FanCasing 정면도 작성
    Dim ChanSize As Integer
        Select Case Val(motoroutput)
            Case 0 To 5.5
                ChanSize = 75
            Case 5.5 To 18.5
                ChanSize = 100
            Case 18.5 To 37
                ChanSize = 125
            Case 37 To 75
                ChanSize = 150
            Case Is > 75
                ChanSize = 200
        End Select
    
    With FanBase
        .ChanSize = ChanSize
        .DrawFront
    End With
    
    With Motor
        If Right$(Direction, 1) = "L" Then
            .Mirror = True
            Else
            .Mirror = False
        End If
        .FrameNo = frmOutput.txtMFrame
        .CP = FanBase.ConPnt1
        .DrawFront
    End With
    
    ' 정면도에 중심선 그리기
    Dim cLine1 As AcadLine
    Dim cLine2 As AcadLine
    Dim cLine3 As AcadLine
    With FanCasing
        Set cLine1 = ThisDrawing.ModelSpace.AddLine(.cPnt1, .cPnt2)
            cLine1.color = acRed
            cLine1.Linetype = "Center"
            cLine1.Update
        Set cLine2 = ThisDrawing.ModelSpace.AddLine(.cPnt3, .cPnt4)
            cLine2.color = acRed
            cLine2.Linetype = "Center"
            cLine2.Update
        Set cLine3 = ThisDrawing.ModelSpace.AddLine(.cPnt5, .cPnt6)
            cLine3.color = acRed
            cLine3.Linetype = "Center"
            cLine3.Update
    End With
    
    ' 정면도에 치수 기입
    '----------------------------------------------------------------------------------------
    'dimP1, dimP3는 cFanBase에서 공통으로 얻어냄
    ' dmsL1,L2,L3 삽입하기
    
    If Left$(Direction, 2) = "RH" Or Left$(Direction, 2) = "LH" Then
        dimP2 = FanCasing.cPnt3
        dimP10 = FanCasing.cPnt4
        
        ElseIf Left$(Direction, 2) = "RL" Or Left$(Direction, 2) = "LR" Then
            dimP2 = FanCasing.cPnt1
            dimP10 = FanCasing.cPnt2
        ElseIf Left$(Direction, 2) = "RR" Or Left$(Direction, 2) = "LL" Then
            dimP2 = FanCasing.cPnt2
            dimP10 = FanCasing.cPnt1
    End If
    
    dimP4 = ThisDrawing.Utility.PolarPoint(dimP3, Dtr(270), 0.15 * D3)
    dimP5 = ThisDrawing.Utility.PolarPoint(dimP4, Dtr(270), 0.1 * D3)
        Set dmsL1 = ThisDrawing.ModelSpace.AddDimRotated(dimP1, dimP2, dimP4, Dtr(0))
        Set dmsL2 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP3, dimP4, Dtr(0))
        Set dmsL3 = ThisDrawing.ModelSpace.AddDimRotated(dimP1, dimP3, dimP5, Dtr(0))
    
    ' dmsL4 삽입하기
    If Mid$(Direction, 2, 1) = "H" Then
        ' dimP6,7은 cRecFlang에서 얻어냄
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP7, Dtr(90), 0.1 * D3)
        dimP9 = ThisDrawing.Utility.PolarPoint(FanCasing.cPnt6, Dtr(90), 0.15 * D3)
        dimP11 = ThisDrawing.Utility.PolarPoint(dimP9, Dtr(90), 0.05 * D3)
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP6, dimP7, dimP8, Dtr(0))
    End If
    
    If Mid$(Direction, 2, 1) = "L" Then
        ' dimP6,7,9는 cRecFlang에서 얻어냄
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP7, Dtr(180), 0.1 * D3)
        dimP11 = ThisDrawing.Utility.PolarPoint(dimP10, Dtr(90), 0.1 * D3)
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP6, dimP7, dimP8, Dtr(90))
    End If
    
    If Mid$(Direction, 2, 1) = "R" Then
        ' dimP6,7,9는 cRecFlang에서 얻어냄
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP7, Dtr(0), 0.15 * D3)
        dimP11 = ThisDrawing.Utility.PolarPoint(dimP10, Dtr(90), 0.1 * D3)
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP6, dimP7, dimP8, Dtr(90))
    End If
    
    ' dmsL5 삽입하기
    Set dmsL5 = ThisDrawing.ModelSpace.AddDimRotated(dimP9, dimP10, dimP11, Dtr(0))
    
    ThisDrawing.SendCommand "dim up all  e "
    
'===========================================================================================
'   평면도 작성
'===========================================================================================
    
    FrontRecFlange = False
    PlanRecFlange = True
    RightRecFlange = False
    FrontCirFlange = False
    PlanCirFlange = True
    RightCirFlange = False
    
    ' 베이스 평면도 작도
    With FanBase
        .CP = ThisDrawing.Utility.PolarPoint(FanCasing.CenterPoint, Dtr(90), D3 * 2#)
        .DrawPlan
    End With
    
    ' Slide Base 그리기
    SlideBase.CP = FanBase.ConPnt6
    SlideBase.DrawPlan
    
    ' 모터 평면도 작성
    Motor.CP = FanBase.ConPnt2
    
    If Right$(Direction, 1) = "L" Then
        Motor.Mirror = True
        Else
        Motor.Mirror = False
    End If
    Motor.DrawPlan
    
    
    ' 베어링 플로머 평면도 작성
    SN3.ReadData
    SN3.CP = ThisDrawing.Utility.PolarPoint(FanBase.CP, Dtr(90), (SN3.a + Wout) / 2 + 40)
    SN3.DrawPlan ' 임펠러측
    
    SN3.CP = ThisDrawing.Utility.PolarPoint(FanBase.CP, Dtr(90), MWidth + Wout / 2 - SN3.a / 2)
    SN3.DrawPlan ' 풀리측
    
    ' V-풀리 평면도 작성
    
    With VPulley
        CallFromPCP2 = True
        .IsPlan = True
        .IsFanPulley = True
        .CP = ThisDrawing.Utility.PolarPoint(SN3.CP, Dtr(90), SN3.a / 2 + 20)
        .BeltType = RTrim(Left$(VbeltType, 2))
        .PCS = PCS
        .Size = fanPulley
        .RotAng = 90
        .DrawPulley
        .IsFanPulley = False
        CallFromPCP4 = True
        .Size = motorPulley
        .CP = FanBase.ConPnt1
        .DrawPulley
    End With
    
    'Belt Cover 그리기
    Dim bCoverLine1 As AcadLine
    Dim bCoverLine2 As AcadLine
    Dim bCoverLine3 As AcadLine
    
    Set bCoverLine1 = ThisDrawing.ModelSpace.AddLine(BeltCoverPntCol.Item("1"), BeltCoverPntCol.Item("2"))
        bCoverLine1.Linetype = "Phantom"
        bCoverLine1.color = acMagenta
        bCoverLine1.Update
    Set bCoverLine2 = ThisDrawing.ModelSpace.AddLine(BeltCoverPntCol.Item("2"), BeltCoverPntCol.Item("3"))
        bCoverLine2.Linetype = "Phantom"
        bCoverLine2.color = acMagenta
        bCoverLine2.Update
    Set bCoverLine3 = ThisDrawing.ModelSpace.AddLine(BeltCoverPntCol.Item("3"), BeltCoverPntCol.Item("4"))
        bCoverLine3.Linetype = "Phantom"
        bCoverLine3.color = acMagenta
        bCoverLine3.Update
        
    Set BeltCoverPntCol = Nothing
    
    
    ' 축 평면도 작성
    With Shaft
        .CP = ThisDrawing.Utility.PolarPoint(FanBase.CP, Dtr(90), Wout / 2)
        .RotAng = 0
        .Draw
    End With
    
    ' 케이싱 평면도 작도
    FanCasing.CenterPoint = FanBase.CP
    FanCasing.DrawPlan
    
    '흡입구 플랜지 평면도 작도
    With Cirflange
        .CP = FanCasing.ConPnt2
        .RotAng = 180
        .Matl = material
        .DrawFront
    End With
    
    ' Grand 작도
    Dim GrandPnt1 As Variant
    Dim GrandPnt2 As Variant
    Dim GrandPnt3 As Variant
    Dim GrandPnt4 As Variant
    Dim GrandLine1 As AcadLine
    Dim GrandLine2 As AcadLine
    Dim GrandLine3 As AcadLine
        GrandPnt1 = ThisDrawing.Utility.PolarPoint(FanCasing.ConPnt3, Dtr(0), SN3.H * 0.8)
        GrandPnt2 = ThisDrawing.Utility.PolarPoint(GrandPnt1, Dtr(90), 15)
        GrandPnt3 = ThisDrawing.Utility.PolarPoint(GrandPnt2, Dtr(180), SN3.H * 1.6)
        GrandPnt4 = ThisDrawing.Utility.PolarPoint(GrandPnt3, Dtr(270), 15)
        Set GrandLine1 = ThisDrawing.ModelSpace.AddLine(GrandPnt1, GrandPnt2)
            GrandLine1.color = acCyan
            GrandLine1.Update
        Set GrandLine2 = ThisDrawing.ModelSpace.AddLine(GrandPnt2, GrandPnt3)
            GrandLine2.color = acCyan
            GrandLine2.Update
        Set GrandLine3 = ThisDrawing.ModelSpace.AddLine(GrandPnt3, GrandPnt4)
            GrandLine3.color = acCyan
            GrandLine3.Update
    
    
    '토출구 플랜지 삽입
    With RecFlange
        
        CallFromPCP7 = True
        .CP = FanCasing.ConPnt1
        
        Select Case Mid$(Direction, 2, 1)
            Case "H"
                .RotAng = 0
                .DrawPlan
            Case "L"
                .RotAng = 90
                .DrawRight
            Case "R"
                .RotAng = -90
                .DrawRight
        End Select
    
    End With
        
        
    ' 중심선 작도
    Dim pCenLine1 As AcadLine
    Dim pCenLine2 As AcadLine
    Dim pCenLine3 As AcadLine
    Dim pCenLine4 As AcadLine
        pCenP1 = ThisDrawing.Utility.PolarPoint(pCenP1, Dtr(270), D3 / 20)
        pCenP2 = ThisDrawing.Utility.PolarPoint(pCenP2, Dtr(90), D3 / 20)
        Set pCenLine1 = ThisDrawing.ModelSpace.AddLine(pCenP1, pCenP2)
        pCenLine1.color = acRed
        pCenLine1.Linetype = "Center"
        pCenLine1.Update
        
        pCenP3 = ThisDrawing.Utility.PolarPoint(pCenP3, Dtr(270), D3 / 20)
        pCenP4 = ThisDrawing.Utility.PolarPoint(pCenP4, Dtr(90), D3 / 20)
        Set pCenLine2 = ThisDrawing.ModelSpace.AddLine(pCenP3, pCenP4)
        pCenLine2.color = acRed
        pCenLine2.Linetype = "Center"
        pCenLine2.Update
        
        
        If Left$(Direction, 2) = "RH" Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(pCenP5, Dtr(180), D3 / 10)
            pCenP6 = ThisDrawing.Utility.PolarPoint(pCenP6, Dtr(0), D3 / 20)
            
            ElseIf Left$(Direction, 2) = "LH" Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(pCenP5, Dtr(0), D3 / 10)
            pCenP6 = ThisDrawing.Utility.PolarPoint(pCenP6, Dtr(180), D3 / 20)
            
            ElseIf Left$(Direction, 2) = "RR" Or Left$(Direction, 2) = "RL" Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(pCenP5, Dtr(180), D3 / 20)
            pCenP6 = ThisDrawing.Utility.PolarPoint(pCenP6, Dtr(0), D3 / 20)
            
            ElseIf Left$(Direction, 2) = "LL" Or Left$(Direction, 2) = "LR" Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(pCenP5, Dtr(0), D3 / 20)
            pCenP6 = ThisDrawing.Utility.PolarPoint(pCenP6, Dtr(180), D3 / 20)
            
        End If
        
        
        Set pCenLine3 = ThisDrawing.ModelSpace.AddLine(pCenP5, pCenP6)
        pCenLine3.color = acRed
        pCenLine3.Linetype = "Center"
        pCenLine3.Update
    If Mid$(Direction, 2, 1) = "H" Then
        pCenP7 = ThisDrawing.Utility.PolarPoint(pCenP7, Dtr(90), D3 / 20)
        pCenP8 = ThisDrawing.Utility.PolarPoint(pCenP8, Dtr(270), D3 / 20)
        Set pCenLine4 = ThisDrawing.ModelSpace.AddLine(pCenP7, pCenP8)
        pCenLine4.color = acRed
        pCenLine4.Linetype = "Center"
        pCenLine4.Update
    End If
    
    ThisDrawing.Application.ZoomExtents
    ThisDrawing.Application.ZoomScaled 0.8, acZoomScaledRelative
    ThisDrawing.Regen acActiveViewport
    
    ' 치수기입
    ' dmsL6 삽입
    ' dimP12,13은 cCirFlange에서 얻음
    dimP14 = ThisDrawing.Utility.PolarPoint(dimP13, Dtr(270), 0.15 * D3)
    Set dmsL6 = ThisDrawing.ModelSpace.AddDimRotated(dimP12, dimP13, dimP14, Dtr(0))
        dmsL6.TextOverride = "%%c<>"
        
    ' dmsL7 삽입
    ' dimP15,16은 cRecFlange에서 얻음
    Select Case Left$(Direction, 2)
        Case "LH", "LR", "RR"
            If Mid$(Direction, 2, 1) = "H" Then
                dimP17 = ThisDrawing.Utility.PolarPoint(dimP15, Dtr(0), 0.2 * D3)
                Else
                dimP17 = ThisDrawing.Utility.PolarPoint(dimP15, Dtr(0), 0.15 * D3)
            End If
            
        Case "RH", "RL", "LL"
                dimP17 = ThisDrawing.Utility.PolarPoint(dimP15, Dtr(180), 0.15 * D3)
    End Select
    
    Set dmsL7 = ThisDrawing.ModelSpace.AddDimRotated(dimP15, dimP16, dimP17, Dtr(90))
    
    ThisDrawing.SendCommand "dim up all  e "
    
'===========================================================================================
'   우측면도 작성
'===========================================================================================
    
    FrontRecFlange = False
    PlanRecFlange = False
    RightRecFlange = True
    FrontCirFlange = False
    PlanCirFlange = False
    RightCirFlange = True
    LeftChannel = True
    RightChannel = True
    
    If Right$(Direction, 1) = "R" Then
        FanCasing.CenterPoint = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), D3 * 2.8)
        Else
        FanCasing.CenterPoint = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), D3 * 2.2)
    End If
    
    FanCasing.PointCal_Right
    
    If Left$(Direction, 2) = "RL" Or Left$(Direction, 2) = "LL" Then
        With RecFlange
            CallFromRCP7 = True
            .CP = FanCasing.ConPnt1
            .RotAng = -90
            .DrawPlan
            ThisDrawing.Application.ZoomExtents
            ThisDrawing.Application.ZoomScaled 0.8, acZoomScaledRelative
            ThisDrawing.Regen acActiveViewport
            
        End With
    End If
    
    
    ' 케이싱 미리 잘라내기
    If Left$(Direction, 2) = "RL" Or Left$(Direction, 2) = "LL" Then
        FanCasing.BeforTrimRight
    End If
    
    ' Base 우측면도
    With FanBase
        .CP = FanCasing.CenterPoint
        .DrawRight
    End With
    
    ' 송풍기 케이싱 우측면도 작도
    FanCasing.DrawRight
    
    ' 흡입구 플랜지 우측면도 삽입
    With Cirflange
        .CP = FanCasing.ConPnt2
        .RotAng = 90
        .Matl = material
        .DrawFront
    End With
    
    '토출구 플랜지 우측면도 삽입
    If Left$(Direction, 2) <> "RL" And Left$(Direction, 2) <> "LL" Then
        With RecFlange
            CallFromRCP7 = True
            .CP = FanCasing.ConPnt1
            Select Case Mid$(Direction, 2, 1)
                Case "H"
                    .RotAng = 0
                    .DrawRight
                Case "L"
                    .RotAng = 90
                    .DrawPlan
                Case "R"
                    .RotAng = -90
                    .DrawPlan
            End Select
        End With
    End If
    
    
    ' SN 플로머 우측면도
    With SN3
        .CP = FanBase.ConPnt1
        .DrawRight
        .CP = FanBase.ConPnt2
        .DrawRight
    End With
    
    ' V-풀리 우측면도 작성
    With VPulley
        .IsPlan = False
        .BeltType = RTrim(Left$(VbeltType, 2))
        .RotAng = 0
        .PCS = PCS
            
        If Right$(Direction, 1) = "R" Then
            CallFromRCP2 = True
            .CP = FanBase.ConPnt3
            .Size = fanPulley
            .IsFanPulley = True
            .DrawPulley
            CallFromRCP4 = True
            .Size = motorPulley
            .CP = FanBase.ConPnt4
            .IsFanPulley = False
            .DrawPulley
            
        Else
            
            CallFromRCP4 = True
            .Size = motorPulley
            .CP = FanBase.ConPnt4
            .IsFanPulley = False
            .DrawPulley
            CallFromRCP2 = True
            .Size = fanPulley
            .CP = FanBase.ConPnt3
            .IsFanPulley = True
            .DrawPulley
        End If
    
    End With
    
    'Belt Cover 그리기
    Set bCoverLine1 = ThisDrawing.ModelSpace.AddLine(BeltCoverPntCol.Item("1"), BeltCoverPntCol.Item("2"))
        bCoverLine1.Linetype = "Phantom"
        bCoverLine1.color = acMagenta
        bCoverLine1.Update
    Set bCoverLine2 = ThisDrawing.ModelSpace.AddLine(BeltCoverPntCol.Item("2"), BeltCoverPntCol.Item("3"))
        bCoverLine2.Linetype = "Phantom"
        bCoverLine2.color = acMagenta
        bCoverLine2.Update
    Set bCoverLine3 = ThisDrawing.ModelSpace.AddLine(BeltCoverPntCol.Item("3"), BeltCoverPntCol.Item("4"))
        bCoverLine3.Linetype = "Phantom"
        bCoverLine3.color = acMagenta
        bCoverLine3.Update
        
    Set BeltCoverPntCol = Nothing
    
    ' 축 평면도 작성
    With Shaft
        .CP = ThisDrawing.Utility.PolarPoint(FanCasing.CenterPoint, Dtr(0), Wout / 2)
        .RotAng = -90
        .Draw
    End With
    
        GrandPnt1 = ThisDrawing.Utility.PolarPoint(FanCasing.ConPnt3, Dtr(270), SN3.H * 0.8)
        GrandPnt2 = ThisDrawing.Utility.PolarPoint(GrandPnt1, Dtr(0), 15)
        GrandPnt3 = ThisDrawing.Utility.PolarPoint(GrandPnt2, Dtr(90), SN3.H * 1.6)
        GrandPnt4 = ThisDrawing.Utility.PolarPoint(GrandPnt3, Dtr(180), 15)
        Set GrandLine1 = ThisDrawing.ModelSpace.AddLine(GrandPnt1, GrandPnt2)
            GrandLine1.color = acCyan
            GrandLine1.Update
        Set GrandLine2 = ThisDrawing.ModelSpace.AddLine(GrandPnt2, GrandPnt3)
            GrandLine2.color = acCyan
            GrandLine2.Update
        Set GrandLine3 = ThisDrawing.ModelSpace.AddLine(GrandPnt3, GrandPnt4)
            GrandLine3.color = acCyan
            GrandLine3.Update
    
    ' 모터위치가 우측일 때 모터 그리기
    If Right$(Direction, 1) = "R" Then
        With Motor
            .CP = FanBase.ConPnt5
            .DrawRight
        End With
    End If
    
    ' 우측면도에 중심선 그리기
    Dim rCenLine1 As AcadLine
    Dim rCenLine2 As AcadLine
    Dim rCenLine3 As AcadLine
    Dim rCenLine4 As AcadLine
    
        rCenP1 = ThisDrawing.Utility.PolarPoint(rCenP1, Dtr(180), D3 / 20)
        rCenP2 = ThisDrawing.Utility.PolarPoint(rCenP2, Dtr(0), D3 / 20)
        Set rCenLine1 = ThisDrawing.ModelSpace.AddLine(rCenP1, rCenP2)
        rCenLine1.color = acRed
        rCenLine1.Linetype = "Center"
        rCenLine1.Update
        
        rCenP3 = ThisDrawing.Utility.PolarPoint(rCenP3, Dtr(180), D3 / 20)
        rCenP4 = ThisDrawing.Utility.PolarPoint(rCenP4, Dtr(0), D3 / 20)
        Set rCenLine2 = ThisDrawing.ModelSpace.AddLine(rCenP3, rCenP4)
        rCenLine2.color = acRed
        rCenLine2.Linetype = "Center"
        rCenLine2.Update
    
        If Left$(Direction, 2) = "RR" Or Left$(Direction, 2) = "LL" Then
            rCenP5 = ThisDrawing.Utility.PolarPoint(rCenP5, Dtr(90), D3 / 10)
            Else
            rCenP5 = ThisDrawing.Utility.PolarPoint(rCenP5, Dtr(90), D3 / 20)
        End If
        
        rCenP6 = ThisDrawing.Utility.PolarPoint(rCenP6, Dtr(270), D3 / 10)
        
        Set rCenLine3 = ThisDrawing.ModelSpace.AddLine(rCenP5, rCenP6)
        rCenLine3.color = acRed
        rCenLine3.Linetype = "Center"
        rCenLine3.Update
    
    If Mid$(Direction, 2, 1) <> "H" Then
        rCenP7 = ThisDrawing.Utility.PolarPoint(rCenP7, Dtr(0), D3 / 20)
        rCenP8 = ThisDrawing.Utility.PolarPoint(rCenP8, Dtr(180), D3 / 20)
        Set rCenLine4 = ThisDrawing.ModelSpace.AddLine(rCenP7, rCenP8)
        rCenLine4.color = acRed
        rCenLine4.Linetype = "Center"
        rCenLine4.Update
    End If
    
    ' 치수기입
    dimP25 = rCenP5
    dimP27 = rCenP1
    dimP22 = ThisDrawing.Utility.PolarPoint(dimP21, Dtr(270), 0.15 * D3)
    dimP23 = ThisDrawing.Utility.PolarPoint(dimP22, Dtr(270), 0.1 * D3)
    dimP26 = ThisDrawing.Utility.PolarPoint(dimP25, Dtr(90), 0.1 * D3)
    
    If Mid$(Direction, 2, 1) = "H" Then
        dimP29 = ThisDrawing.Utility.PolarPoint(dimP28, Dtr(180), 0.2 * D3)
        Else
        dimP28 = rCenP8
        dimP29 = ThisDrawing.Utility.PolarPoint(dimP28, Dtr(180), 0.15 * D3)
    End If
    dimP30 = ThisDrawing.Utility.PolarPoint(dimP29, Dtr(180), 0.1 * D3)
    
    Set dmsL8 = ThisDrawing.ModelSpace.AddDimRotated(dimP19, dimP18, dimP22, Dtr(0))
    Set dmsL9 = ThisDrawing.ModelSpace.AddDimRotated(dimP19, dimP20, dimP22, Dtr(0))
    Set dmsL10 = ThisDrawing.ModelSpace.AddDimRotated(dimP20, dimP21, dimP22, Dtr(0))
    Set dmsL11 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP21, dimP23, Dtr(0))
    
    Set dmsL12 = ThisDrawing.ModelSpace.AddDimRotated(dimP24, dimP25, dimP26, Dtr(0))
    
    If Left$(Direction, 2) = "RL" Or Left$(Direction, 2) = "LR" Then
        Set dmsL13 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP28, dimP29, Dtr(90))
        Set dmsL14 = ThisDrawing.ModelSpace.AddDimRotated(dimP27, dimP28, dimP29, Dtr(90))
        Set dmsL15 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP27, dimP30, Dtr(90))
        
        Else
        Set dmsL13 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP27, dimP29, Dtr(90))
        Set dmsL14 = ThisDrawing.ModelSpace.AddDimRotated(dimP27, dimP28, dimP29, Dtr(90))
        Set dmsL15 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP28, dimP30, Dtr(90))
    End If
    
    ThisDrawing.SendCommand "dim up all  e "
    
    
    ' 도면박스 삽입하기
    Sc = D3 / 49
    
    Dim BlockCenP As Variant
    Dim Fanbox As AcadBlockReference
        
    If Right$(Direction, 1) = "L" Then
        BlockCenP = ThisDrawing.Utility.PolarPoint(CP, Dtr(180), 0.5 * D3)
        Else
        BlockCenP = CP
    End If
    
    Set Fanbox = ThisDrawing.ModelSpace.InsertBlock(BlockCenP, ThisDrawing.Application.Path & "\ALISP\Turbo Fan Design\Acad\dFanBox.dwg", _
                         Sc, Sc, 1#, 0)
    ThisDrawing.SendCommand "Explode (entlast)  "
    ThisDrawing.Application.ZoomExtents
    
    ' 도면에 Text 기입하기
    Dim tText As String
    Height = 2 * Sc
    
    PutText Str(q), 250.1879, 94.6714 '풍량
    PutText Str(ps), 250.1879, 88.6714 ' 풍압
    PutText Format(Str(N), "0"), 250.1879, 82.6714 ' 송풍기 회전수
    PutText Str(temp), 250.1879, 76.6714 ' 온도
    PutText Str(motorPulley), 250.1879, 70.6714 ' 모터풀리
    PutText Str(fanPulley), 250.1879, 64.6714 ' Fan풀리
        tText = VbeltType + "-" + Str(PCS) + " pcs"
    PutText tText, 250.1879, 58.6714 ' 벨트타입/가닥수
    
    Dim oldTstyle As AcadTextStyle
    Dim newTstyle As AcadTextStyle
        Set oldTstyle = ThisDrawing.ActiveTextStyle
        Set newTstyle = ThisDrawing.TextStyles.Add("한글")
        newTstyle.fontFile = "C:\Windows\Fonts\malgunsl.ttf"
        newTstyle.SetFont "맑은 고딕 Semilight", False, False, 129, 50
        
    ThisDrawing.ActiveTextStyle = newTstyle
    PutText frmOutput.txtMMaker, 310.303, 94.6714   ' 모터 메이커
    ThisDrawing.ActiveTextStyle = oldTstyle
    PutText frmOutput.txtMType, 310.303, 88.6714   ' 모터 타입
    PutText Str(motorcapa), 310.303, 82.6714  ' 모터 출력
    PutText Str(motorrpm), 310.303, 76.6714  '풍량
        tText = Str(motorpoles) + "P/" + frmOutput.txtMFrequency
    PutText tText, 310.303, 70.6714 ' 극수/주파수
    PutText "3%%c", 310.303, 64.6714  ' 상수
        tText = Str(motorvoltage) + "V/" + Format(Str(motorloadamp), "0.0") + "A"
    PutText tText, 310.303, 58.6714 ' 전압/전류
    
    ThisDrawing.ActiveTextStyle = newTstyle
    Height = 3.2 * Sc
    PutText frmOutput.txtCustomer, 300.9441, -54.9238 ' 고객명
    
    ThisDrawing.ActiveTextStyle = oldTstyle
    Height = 2 * Sc
    PutText Format(Date, "YYYY. M. D."), 244.5854, -68.3686 ' 설계일자
    
    ThisDrawing.Regen acActiveViewport
    ThisDrawing.Utility.Prompt ""
    ThisDrawing.Application.Update
    ThisDrawing.Utility.Prompt "Auto Drawing Completed!!!"
    VariablesSetting
    ThisDrawing.Application.Update

End Sub

Public Sub DirectDraw() ' 직결형 도면 작성
    
    Load_LT
    
    FrontRecFlange = True
    PlanRecFlange = True
    RightRecFlange = True
    FrontCirFlange = True
    PlanCirFlange = True
    RightCirFlange = True
        
    Dim fGab As Double
    fGab = D2 * 6 * ns ^ 0.9 / 20
    If fGab < 30 Then fGab = 30
    If fGab > 100 Then fGab = 100
    D3 = Int((D2 * 1000 + 2 * fGab) / 10) * 10 + 10
    
    Call SetACAD("FanDrawing", D3 / 65)
    
    ThisDrawing.Application.Update
    
'===========================================================================================
'   정면도 작성
'===========================================================================================
        
    ' 작도 중심점을 (0, 0, 0) 점으로 지정
    
        CP(0) = 0
        CP(1) = 0
        CP(2) = 0
    
    ' 정면도에 흡입구 플랜지 그리기
    With Cirflange
        .CP = CP
        .ID = DiaInlet
        .Matl = material
        .DrawPlan
    End With
    
    
    ' 화면조정
    ThisDrawing.Application.ZoomExtents
    ThisDrawing.Regen acActiveViewport
    ThisDrawing.Application.ZoomScaled 0.3, acZoomScaledRelative
    
    
    ' 정면도에 Fan Casing 그리기
    With FanCasing
        .Direction = Left$(Direction, 2)
        .CenterPoint = CP
        .D1 = D1 * 1000
        .D2 = D2
        .D3 = D3
        .InletDia = DiaInlet
        .Lout = Lout
        .Wout = Wout
        .DrawFront
    End With
    
    ' 정면도에 토출구 플랜지 그리기
    
    With RecFlange
        .B = Cirflange.B
        .BD = Cirflange.BoltHoleDia
        .idLength = Lout
        .idWidth = Wout
        .t = Cirflange.Thickness
        
        Select Case Left$(Direction, 2)
            Case "RH", "LH"
                .RotAng = 0
            Case "RR", "LR"
                .RotAng = -90
            Case "RL", "LL"
                .RotAng = 90
        End Select
        
        .CP = FanCasing.ConPnt1
        .DrawFront
    End With
    
    Dim ChanSize As Integer
        Select Case Val(motoroutput)
            Case 0 To 5.5
                ChanSize = 75
            Case 5.5 To 18.5
                ChanSize = 100
            Case 18.5 To 37
                ChanSize = 125
            Case 37 To 75
                ChanSize = 150
            Case Is > 75
                ChanSize = 200
        End Select
    
    With DFanBase
        .ChanSize = ChanSize
        .CP = FanCasing.ConPnt2
        .DrawFront
    End With
    
    ' 정면도에 중심선 그리기
    Dim cLine1 As AcadLine
    Dim cLine2 As AcadLine
    Dim cLine3 As AcadLine
    
    With FanCasing
        Set cLine1 = ThisDrawing.ModelSpace.AddLine(.cPnt1, .cPnt2)
            cLine1.color = acRed
            cLine1.Linetype = "Center"
            cLine1.Update
        Set cLine2 = ThisDrawing.ModelSpace.AddLine(.cPnt3, .cPnt4)
            cLine2.color = acRed
            cLine2.Linetype = "Center"
            cLine2.Update
        Set cLine3 = ThisDrawing.ModelSpace.AddLine(.cPnt5, .cPnt6)
            cLine3.color = acRed
            cLine3.Linetype = "Center"
            cLine3.Update
    End With
    
    
    ' 치수기입
    If Direction = "RH" Then
        dimP6 = FanCasing.cPnt6
        dimP5 = FanCasing.cPnt4
        dimP3 = FanCasing.cPnt2
        
        dimP7 = ThisDrawing.Utility.PolarPoint(dimP1, Dtr(270), 0.2 * D3)
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP3, Dtr(0), 0.15 * D3)
        dimP9 = ThisDrawing.Utility.PolarPoint(dimP8, Dtr(0), 0.1 * D3)
        dimP10 = ThisDrawing.Utility.PolarPoint(dimP6, Dtr(90), 0.1 * D3)
        
        Set dmsL1 = ThisDrawing.ModelSpace.AddDimRotated(dimP1, dimP2, dimP7, Dtr(0))
        Set dmsL2 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP3, dimP8, Dtr(90))
        Set dmsL3 = ThisDrawing.ModelSpace.AddDimRotated(dimP3, dimP4, dimP8, Dtr(90))
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP4, dimP9, Dtr(90))
        Set dmsL5 = ThisDrawing.ModelSpace.AddDimRotated(dimP6, dimP5, dimP10, Dtr(0))
    End If
    
    If Direction = "RL" Then
        dimP3 = FanCasing.cPnt3
        dimP4 = FanCasing.cPnt2
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP1, Dtr(270), 0.15 * D3)
        dimP9 = ThisDrawing.Utility.PolarPoint(dimP3, Dtr(0), 0.1 * D3)
        dimP10 = ThisDrawing.Utility.PolarPoint(dimP4, Dtr(90), 0.1 * D3)
        dimP11 = ThisDrawing.Utility.PolarPoint(dimP5, Dtr(180), 0.1 * D3)
        Set dmsL1 = ThisDrawing.ModelSpace.AddDimRotated(dimP1, dimP2, dimP8, Dtr(0))
        Set dmsL2 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP3, dimP9, Dtr(90))
        Set dmsL3 = ThisDrawing.ModelSpace.AddDimRotated(dimP5, dimP4, dimP10, Dtr(0))
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP7, dimP6, dimP11, Dtr(90))
    End If
    
    If Direction = "RR" Then
        dimP3 = FanCasing.cPnt4
        dimP4 = FanCasing.cPnt6
        dimP6 = FanCasing.cPnt1
        dimP7 = ThisDrawing.Utility.PolarPoint(dimP1, Dtr(270), 0.15 * D3)
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP2, Dtr(0), 0.25 * D3)
        dimP9 = ThisDrawing.Utility.PolarPoint(dimP8, Dtr(0), 0.1 * D3)
        dimP10 = ThisDrawing.Utility.PolarPoint(dimP5, Dtr(90), 0.1 * D3)
        Set dmsL1 = ThisDrawing.ModelSpace.AddDimRotated(dimP1, dimP2, dimP7, Dtr(0))
        Set dmsL2 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP3, dimP8, Dtr(90))
        Set dmsL3 = ThisDrawing.ModelSpace.AddDimRotated(dimP3, dimP4, dimP8, Dtr(90))
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP4, dimP9, Dtr(90))
        Set dmsL5 = ThisDrawing.ModelSpace.AddDimRotated(dimP6, dimP5, dimP10, Dtr(0))
    End If
    
    If Direction = "LH" Then
        dimP3 = FanCasing.cPnt1
        dimP5 = FanCasing.cPnt6
        dimP6 = FanCasing.cPnt4
        dimP7 = ThisDrawing.Utility.PolarPoint(dimP1, Dtr(270), 0.2 * D3)
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP3, Dtr(0), 0.2 * D3)
        dimP9 = ThisDrawing.Utility.PolarPoint(dimP8, Dtr(0), 0.1 * D3)
        dimP10 = ThisDrawing.Utility.PolarPoint(dimP5, Dtr(90), 0.1 * D3)
        Set dmsL1 = ThisDrawing.ModelSpace.AddDimRotated(dimP1, dimP2, dimP7, Dtr(0))
        Set dmsL2 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP3, dimP8, Dtr(90))
        Set dmsL3 = ThisDrawing.ModelSpace.AddDimRotated(dimP3, dimP4, dimP8, Dtr(90))
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP4, dimP9, Dtr(90))
        Set dmsL5 = ThisDrawing.ModelSpace.AddDimRotated(dimP6, dimP5, dimP10, Dtr(0))
    End If
    
    If Direction = "LL" Then
        dimP3 = FanCasing.cPnt3
        dimP4 = FanCasing.cPnt1
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP1, Dtr(270), 0.15 * D3)
        dimP9 = ThisDrawing.Utility.PolarPoint(dimP3, Dtr(0), 0.1 * D3)
        dimP10 = ThisDrawing.Utility.PolarPoint(dimP4, Dtr(90), 0.1 * D3)
        dimP11 = ThisDrawing.Utility.PolarPoint(dimP5, Dtr(180), 0.1 * D3)
        
        Set dmsL1 = ThisDrawing.ModelSpace.AddDimRotated(dimP1, dimP2, dimP8, Dtr(0))
        Set dmsL2 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP3, dimP9, Dtr(90))
        Set dmsL3 = ThisDrawing.ModelSpace.AddDimRotated(dimP5, dimP4, dimP10, Dtr(0))
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP7, dimP6, dimP11, Dtr(90))
    End If
    
    If Direction = "LR" Then
        dimP3 = FanCasing.cPnt4
        dimP6 = FanCasing.cPnt2
        dimP8 = ThisDrawing.Utility.PolarPoint(dimP1, Dtr(270), 0.15 * D3)
        dimP9 = ThisDrawing.Utility.PolarPoint(dimP4, Dtr(0), 0.15 * D3)
        dimP10 = ThisDrawing.Utility.PolarPoint(dimP9, Dtr(0), 0.1 * D3)
        dimP11 = ThisDrawing.Utility.PolarPoint(dimP6, Dtr(90), 0.1 * D3)
        Set dmsL1 = ThisDrawing.ModelSpace.AddDimRotated(dimP1, dimP2, dimP8, Dtr(0))
        Set dmsL2 = ThisDrawing.ModelSpace.AddDimRotated(dimP2, dimP3, dimP10, Dtr(90))
        Set dmsL3 = ThisDrawing.ModelSpace.AddDimRotated(dimP4, dimP5, dimP9, Dtr(90))
        Set dmsL4 = ThisDrawing.ModelSpace.AddDimRotated(dimP6, dimP7, dimP11, Dtr(0))
    End If
    
    ThisDrawing.SendCommand "dim up all  e "
    
'===========================================================================================
'   평면도 작성
'===========================================================================================
    
    ' 모터 데이터 읽기
    With Motor
        .Mirror = False
        .FrameNo = frmOutput.txtMFrame
        .ReadData
    End With
    
    '  FanBase 평면
    With DFanBase
        .CP = ThisDrawing.Utility.PolarPoint(CP, Dtr(90), D3 * 2)
        .DrawPlan
    End With
    
    ' 모터평면
    With Motor
        .Mirror = False
        .CP = ThisDrawing.Utility.PolarPoint(DFanBase.CP, Dtr(90), Motor.C + Motor.B / 2)
        .RotAng = 180
        .DrawPlan
        
    End With
    
    ' FanCasing 평면
    FanCasing.CenterPoint = ThisDrawing.Utility.PolarPoint(DFanBase.CP, Dtr(270), FanCasing.Wout / 2 + 15)
    FanCasing.DrawPlan
    
    '흡입구 플랜지 평면도 작도
    With Cirflange
        .CP = FanCasing.ConPnt2
        .RotAng = 180
        .Matl = material
        .DrawFront
    End With
    
    '토출구 플랜지 평면 삽입
    With RecFlange
        CallFromPCP7 = True
        .CP = FanCasing.ConPnt1
        Select Case Mid$(Direction, 2, 1)
            Case "H"
                .RotAng = 0
                .DrawPlan
            Case "L"
                .RotAng = 90
                .DrawRight
            Case "R"
                .RotAng = -90
                .DrawRight
        End Select
    
    End With
    
    Dim bP1 As Variant
    Dim bP2 As Variant
    Dim bP3 As Variant
    Dim bP4 As Variant
        bP1 = ThisDrawing.Utility.PolarPoint(DFanBase.CP, Dtr(180), DS / 2 + 15)
        bP2 = ThisDrawing.Utility.PolarPoint(bP1, Dtr(270), 15)
        bP3 = ThisDrawing.Utility.PolarPoint(bP2, Dtr(0), DS + 30)
        bP4 = ThisDrawing.Utility.PolarPoint(bP3, Dtr(90), 15)
    Dim bossLine1 As AcadLine
    Dim bossLine2 As AcadLine
    Dim bossLine3 As AcadLine
        Set bossLine1 = ThisDrawing.ModelSpace.AddLine(bP2, bP1)
            bossLine1.Update
        Set bossLine2 = ThisDrawing.ModelSpace.AddLine(bP1, bP4)
            bossLine2.Update
        Set bossLine3 = ThisDrawing.ModelSpace.AddLine(bP4, bP3)
            bossLine3.Update
            
    ' 중심선 그리기
    Dim pCenLine1 As AcadLine
    Dim pCenLine2 As AcadLine
    Dim pCenLine3 As AcadLine
        pCenP1 = ThisDrawing.Utility.PolarPoint(pCenP1, Dtr(270), D3 / 20)
        pCenP3 = ThisDrawing.Utility.PolarPoint(pCenP3, Dtr(90), D3 / 20)
        Set pCenLine1 = ThisDrawing.ModelSpace.AddLine(pCenP1, pCenP3)
        pCenLine1.color = acRed
        pCenLine1.Linetype = "Center"
        pCenLine1.Update
        
        If Left$(Direction, 2) = "RH" Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(pCenP5, Dtr(180), D3 / 10)
            pCenP6 = ThisDrawing.Utility.PolarPoint(pCenP6, Dtr(0), D3 / 20)
            
            ElseIf Left$(Direction, 2) = "LH" Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(pCenP5, Dtr(0), D3 / 10)
            pCenP6 = ThisDrawing.Utility.PolarPoint(pCenP6, Dtr(180), D3 / 20)
            
            ElseIf Left$(Direction, 2) = "RR" Or Left$(Direction, 2) = "RL" Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(pCenP5, Dtr(180), D3 / 20)
            pCenP6 = ThisDrawing.Utility.PolarPoint(pCenP6, Dtr(0), D3 / 20)
            
            ElseIf Left$(Direction, 2) = "LL" Or Left$(Direction, 2) = "LR" Then
            pCenP5 = ThisDrawing.Utility.PolarPoint(pCenP5, Dtr(0), D3 / 20)
            pCenP6 = ThisDrawing.Utility.PolarPoint(pCenP6, Dtr(180), D3 / 20)
            
        End If
        
        
        Set pCenLine2 = ThisDrawing.ModelSpace.AddLine(pCenP5, pCenP6)
        pCenLine2.color = acRed
        pCenLine2.Linetype = "Center"
        pCenLine2.Update
        
    If Mid$(Direction, 2, 1) = "H" Then
        pCenP7 = ThisDrawing.Utility.PolarPoint(pCenP7, Dtr(90), D3 / 20)
        pCenP8 = ThisDrawing.Utility.PolarPoint(pCenP8, Dtr(270), D3 / 20)
        Set pCenLine3 = ThisDrawing.ModelSpace.AddLine(pCenP7, pCenP8)
        pCenLine3.color = acRed
        pCenLine3.Linetype = "Center"
        pCenLine3.Update
    End If
    
    ' 치수기입
    If Direction = "RH" Then
        dimP14 = ThisDrawing.Utility.PolarPoint(dimP11, Dtr(180), 0.2 * D3)
        dimP15 = ThisDrawing.Utility.PolarPoint(dimP12, Dtr(270), 0.25 * D3)
        Set dmsL6 = ThisDrawing.ModelSpace.AddDimRotated(dimP11, dimP12, dimP14, Dtr(90))
        Set dmsL7 = ThisDrawing.ModelSpace.AddDimRotated(dimP12, dimP13, dimP15, Dtr(0))
    End If
    
    If Direction = "RL" Then
        dimP16 = ThisDrawing.Utility.PolarPoint(dimP13, Dtr(180), 0.1 * D3)
        dimP17 = ThisDrawing.Utility.PolarPoint(dimP15, Dtr(270), 0.15 * D3)
        Set dmsL5 = ThisDrawing.ModelSpace.AddDimRotated(dimP12, dimP13, dimP16, Dtr(90))
        Set dmsL6 = ThisDrawing.ModelSpace.AddDimRotated(dimP14, dimP15, dimP17, Dtr(0))
            dmsL6.TextOverride = "%%c<>"
    End If
    
    If Direction = "RR" Then
        dimP12 = pCenP6
        dimP13 = ThisDrawing.Utility.PolarPoint(dimP12, Dtr(0), 0.15 * D3)
        Set dmsL6 = ThisDrawing.ModelSpace.AddDimRotated(dimP11, dimP12, dimP13, Dtr(90))
    End If
    
    If Direction = "LH" Then
        dimP14 = ThisDrawing.Utility.PolarPoint(dimP11, Dtr(270), 0.25 * D3)
        dimP15 = ThisDrawing.Utility.PolarPoint(dimP12, Dtr(0), 0.25 * D3)
        Set dmsL6 = ThisDrawing.ModelSpace.AddDimRotated(dimP11, dimP12, dimP14, Dtr(0))
        Set dmsL7 = ThisDrawing.ModelSpace.AddDimRotated(dimP12, dimP13, dimP15, Dtr(90))
    End If
    
    If Direction = "LL" Then
        dimP14 = ThisDrawing.Utility.PolarPoint(dimP12, Dtr(180), 0.1 * D3)
        dimP17 = ThisDrawing.Utility.PolarPoint(dimP16, Dtr(270), 0.15 * D3)
        Set dmsL5 = ThisDrawing.ModelSpace.AddDimRotated(dimP12, dimP13, dimP14, Dtr(90))
        Set dmsL6 = ThisDrawing.ModelSpace.AddDimRotated(dimP15, dimP16, dimP17, Dtr(0))
    End If
    
    If Direction = "LR" Then
        dimP14 = ThisDrawing.Utility.PolarPoint(dimP12, Dtr(270), 0.15 * D3)
        dimP17 = ThisDrawing.Utility.PolarPoint(dimP15, Dtr(0), 0.15 * D3)
        Set dmsL5 = ThisDrawing.ModelSpace.AddDimRotated(dimP12, dimP13, dimP14, Dtr(0))
            dmsL5.TextOverride = "%%c<>"
        Set dmsL6 = ThisDrawing.ModelSpace.AddDimRotated(dimP15, dimP16, dimP17, Dtr(90))
    End If
        
    ThisDrawing.SendCommand "dim up all  e "
    
'===========================================================================================
'   우측면도 작성
'===========================================================================================
    LeftChannel = True
    RightChannel = True
    
    FanCasing.CenterPoint = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), D3 * 2#)
    FanCasing.PointCal_Right
    
    If Direction = "RL" Or Direction = "LL" Then
        With RecFlange
            CallFromRCP7 = True
            .CP = FanCasing.ConPnt1
            .RotAng = -90
            .DrawPlan
            ThisDrawing.Application.ZoomExtents
            ThisDrawing.Application.ZoomScaled 0.8, acZoomScaledRelative
            ThisDrawing.Regen acActiveViewport
            
        End With
    End If
    
    
    ' 케이싱 미리 잘라내기
    If Direction = "RL" Or Direction = "LL" Then
        FanCasing.BeforTrimRight
    End If
    
    ' Base 우측면도
    With DFanBase
        .CP = FanCasing.CenterPoint
        .DrawRight
    End With
    
    ' 송풍기 케이싱 우측면도 작도
    FanCasing.DrawRight
    
    
    ' 흡입구 플랜지 우측면도 삽입
    With Cirflange
        .CP = FanCasing.ConPnt2
        .RotAng = 90
        .Matl = material
        .DrawFront
    End With
    
    
    '토출구 플랜지 우측면도 삽입
    If Direction <> "RL" And Direction <> "LL" Then
        With RecFlange
            CallFromRCP7 = True
            .CP = FanCasing.ConPnt1
            Select Case Mid$(Direction, 2, 1)
                Case "H"
                    .RotAng = 0
                    .DrawRight
                Case "L"
                    .RotAng = 90
                    .DrawPlan
                Case "R"
                    .RotAng = -90
                    .DrawPlan
            End Select
        End With
    End If
    
    ' 모터 우측면도
    With Motor
        .CP = DFanBase.MotorPoint
        .RotAng = 0
        .Mirror = True
        .DrawRight
    End With
    
        ' Boss 돌출부 그리기
        bP1 = ThisDrawing.Utility.PolarPoint(DFanBase.BossPoint, Dtr(90), DS / 2 + 15)
        bP2 = ThisDrawing.Utility.PolarPoint(bP1, Dtr(180), 15)
        bP3 = ThisDrawing.Utility.PolarPoint(bP2, Dtr(270), DS + 30)
        bP4 = ThisDrawing.Utility.PolarPoint(bP3, Dtr(0), 15)
        Set bossLine1 = ThisDrawing.ModelSpace.AddLine(bP2, bP1)
            bossLine1.Update
        Set bossLine2 = ThisDrawing.ModelSpace.AddLine(bP1, bP4)
            bossLine2.Update
        Set bossLine3 = ThisDrawing.ModelSpace.AddLine(bP4, bP3)
            bossLine3.Update

    
    ' 우측면도에 중심선 그리기
    Dim rCenLine1 As AcadLine
    Dim rCenLine2 As AcadLine
    Dim rCenLine3 As AcadLine
    
        rCenP1 = ThisDrawing.Utility.PolarPoint(rCenP1, Dtr(180), D3 / 20)
        rCenP2 = ThisDrawing.Utility.PolarPoint(rCenP2, Dtr(0), D3 / 20)
        Set rCenLine1 = ThisDrawing.ModelSpace.AddLine(rCenP1, rCenP2)
        rCenLine1.color = acRed
        rCenLine1.Linetype = "Center"
        rCenLine1.Update
        
        If Left$(Direction, 2) = "RR" Or Left$(Direction, 2) = "LL" Then
            rCenP5 = ThisDrawing.Utility.PolarPoint(rCenP5, Dtr(90), D3 / 10)
            Else
            rCenP5 = ThisDrawing.Utility.PolarPoint(rCenP5, Dtr(90), D3 / 20)
        End If
        
        rCenP6 = ThisDrawing.Utility.PolarPoint(rCenP6, Dtr(270), D3 / 10)
        
        Set rCenLine2 = ThisDrawing.ModelSpace.AddLine(rCenP5, rCenP6)
        rCenLine2.color = acRed
        rCenLine2.Linetype = "Center"
        rCenLine2.Update
    
    If Mid$(Direction, 2, 1) <> "H" Then
        rCenP7 = ThisDrawing.Utility.PolarPoint(rCenP7, Dtr(0), D3 / 20)
        rCenP8 = ThisDrawing.Utility.PolarPoint(rCenP8, Dtr(180), D3 / 20)
        Set rCenLine3 = ThisDrawing.ModelSpace.AddLine(rCenP7, rCenP8)
        rCenLine3.color = acRed
        rCenLine3.Linetype = "Center"
        rCenLine3.Update
    End If
    
    
    ' 치수기입
    If Direction = "RH" Then
        dimP20 = rCenP5
        dimP24 = ThisDrawing.Utility.PolarPoint(dimP19, Dtr(270), 0.15 * D3)
        dimP25 = ThisDrawing.Utility.PolarPoint(dimP24, Dtr(270), 0.1 * D3)
        dimP26 = ThisDrawing.Utility.PolarPoint(dimP20, Dtr(90), 0.1 * D3)
        dimP27 = ThisDrawing.Utility.PolarPoint(dimP22, Dtr(180), 0.1 * D3)
    
        Set dmsL8 = ThisDrawing.ModelSpace.AddDimRotated(dimP17, dimP16, dimP24, Dtr(0))
        Set dmsL9 = ThisDrawing.ModelSpace.AddDimRotated(dimP17, dimP18, dimP24, Dtr(0))
        Set dmsL10 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP19, dimP24, Dtr(0))
        Set dmsL11 = ThisDrawing.ModelSpace.AddDimRotated(dimP16, dimP19, dimP25, Dtr(0))
        Set dmsL12 = ThisDrawing.ModelSpace.AddDimRotated(dimP21, dimP20, dimP26, Dtr(0))
        Set dmsL13 = ThisDrawing.ModelSpace.AddDimRotated(dimP23, dimP22, dimP27, Dtr(90))
            dmsL13.TextOverride = "%%c<>"
    End If
    
    If Direction = "LH" Then
        dimP20 = rCenP5
        dimP24 = ThisDrawing.Utility.PolarPoint(dimP19, Dtr(270), 0.2 * D3)
        dimP25 = ThisDrawing.Utility.PolarPoint(dimP24, Dtr(270), 0.1 * D3)
        dimP26 = ThisDrawing.Utility.PolarPoint(dimP20, Dtr(90), 0.1 * D3)
        dimP27 = ThisDrawing.Utility.PolarPoint(dimP22, Dtr(180), 0.15 * D3)
    
        Set dmsL8 = ThisDrawing.ModelSpace.AddDimRotated(dimP17, dimP16, dimP24, Dtr(0))
        Set dmsL9 = ThisDrawing.ModelSpace.AddDimRotated(dimP17, dimP18, dimP24, Dtr(0))
        Set dmsL10 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP19, dimP24, Dtr(0))
        Set dmsL11 = ThisDrawing.ModelSpace.AddDimRotated(dimP16, dimP19, dimP25, Dtr(0))
        Set dmsL12 = ThisDrawing.ModelSpace.AddDimRotated(dimP21, dimP20, dimP26, Dtr(0))
        Set dmsL13 = ThisDrawing.ModelSpace.AddDimRotated(dimP23, dimP22, dimP27, Dtr(90))
            dmsL13.TextOverride = "%%c<>"
    End If
    
    If Direction = "RL" Then
        dimP18 = rCenP5
        dimP20 = rCenP8
        dimP25 = ThisDrawing.Utility.PolarPoint(dimP18, Dtr(90), 0.1 * D3)
        dimP26 = ThisDrawing.Utility.PolarPoint(dimP20, Dtr(180), 0.1 * D3)
        dimP27 = ThisDrawing.Utility.PolarPoint(dimP24, Dtr(270), 0.15 * D3)
        dimP28 = ThisDrawing.Utility.PolarPoint(dimP27, Dtr(270), 0.1 * D3)
    
        Set dmsL7 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP19, dimP25, Dtr(0))
        Set dmsL8 = ThisDrawing.ModelSpace.AddDimRotated(dimP21, dimP20, dimP26, Dtr(90))
        
        Set dmsL9 = ThisDrawing.ModelSpace.AddDimRotated(dimP22, dimP21, dimP27, Dtr(0))
        Set dmsL10 = ThisDrawing.ModelSpace.AddDimRotated(dimP22, dimP23, dimP27, Dtr(0))
        Set dmsL11 = ThisDrawing.ModelSpace.AddDimRotated(dimP23, dimP24, dimP27, Dtr(0))
        Set dmsL12 = ThisDrawing.ModelSpace.AddDimRotated(dimP21, dimP24, dimP28, Dtr(0))
    End If
    
    If Direction = "RR" Then
        dimP21 = ThisDrawing.Utility.PolarPoint(dimP15, Dtr(90), 0.2 * D3)
        dimP22 = ThisDrawing.Utility.PolarPoint(dimP16, Dtr(180), 0.2 * D3)
        dimP23 = ThisDrawing.Utility.PolarPoint(dimP20, Dtr(270), 0.15 * D3)
        dimP24 = ThisDrawing.Utility.PolarPoint(dimP23, Dtr(270), 0.1 * D3)
        dimP27 = ThisDrawing.Utility.PolarPoint(dimP26, Dtr(180), 0.1 * D3)
    
        Set dmsL7 = ThisDrawing.ModelSpace.AddDimRotated(dimP14, dimP15, dimP21, Dtr(0))
        Set dmsL8 = ThisDrawing.ModelSpace.AddDimRotated(dimP16, dimP14, dimP22, Dtr(90))
        Set dmsL9 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP17, dimP23, Dtr(0))
        Set dmsL10 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP19, dimP23, Dtr(0))
        Set dmsL11 = ThisDrawing.ModelSpace.AddDimRotated(dimP19, dimP20, dimP23, Dtr(0))
        Set dmsL12 = ThisDrawing.ModelSpace.AddDimRotated(dimP17, dimP20, dimP24, Dtr(0))
        Set dmsL13 = ThisDrawing.ModelSpace.AddDimRotated(dimP26, dimP25, dimP27, Dtr(90))
        
    End If
    
    If Direction = "LL" Then
        dimP22 = rCenP5
        dimP24 = rCenP8
        
        dimP25 = ThisDrawing.Utility.PolarPoint(dimP21, Dtr(270), 0.15 * D3)
        dimP26 = ThisDrawing.Utility.PolarPoint(dimP25, Dtr(270), 0.1 * D3)
        dimP27 = ThisDrawing.Utility.PolarPoint(dimP22, Dtr(90), 0.1 * D3)
        dimP28 = ThisDrawing.Utility.PolarPoint(dimP24, Dtr(180), 0.15 * D3)
    
        Set dmsL7 = ThisDrawing.ModelSpace.AddDimRotated(dimP19, dimP18, dimP25, Dtr(0))
        Set dmsL8 = ThisDrawing.ModelSpace.AddDimRotated(dimP19, dimP20, dimP25, Dtr(0))
        Set dmsL9 = ThisDrawing.ModelSpace.AddDimRotated(dimP20, dimP21, dimP25, Dtr(0))
        Set dmsL10 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP21, dimP26, Dtr(0))
        Set dmsL11 = ThisDrawing.ModelSpace.AddDimRotated(dimP23, dimP22, dimP27, Dtr(0))
        Set dmsL12 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP24, dimP28, Dtr(90))
        
    End If
    
    If Direction = "LR" Then
        dimP22 = rCenP5
        dimP24 = rCenP8
        dimP25 = ThisDrawing.Utility.PolarPoint(dimP21, Dtr(270), 0.15 * D3)
        dimP26 = ThisDrawing.Utility.PolarPoint(dimP25, Dtr(270), 0.1 * D3)
        dimP27 = ThisDrawing.Utility.PolarPoint(dimP22, Dtr(90), 0.1 * D3)
        dimP28 = ThisDrawing.Utility.PolarPoint(dimP24, Dtr(180), 0.1 * D3)
    
        Set dmsL7 = ThisDrawing.ModelSpace.AddDimRotated(dimP19, dimP18, dimP25, Dtr(0))
        Set dmsL8 = ThisDrawing.ModelSpace.AddDimRotated(dimP19, dimP20, dimP25, Dtr(0))
        Set dmsL9 = ThisDrawing.ModelSpace.AddDimRotated(dimP20, dimP21, dimP25, Dtr(0))
        Set dmsL10 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP21, dimP26, Dtr(0))
        Set dmsL11 = ThisDrawing.ModelSpace.AddDimRotated(dimP23, dimP22, dimP27, Dtr(0))
        Set dmsL12 = ThisDrawing.ModelSpace.AddDimRotated(dimP18, dimP24, dimP28, Dtr(90))
        
    End If
    
    ThisDrawing.SendCommand "dim up all  e "
    
    
    ' 도면박스 삽입하기
    Dim Fanbox As AcadBlockReference
    Set Fanbox = ThisDrawing.ModelSpace.InsertBlock(CP, ThisDrawing.Application.Path & "\ALISP\Turbo Fan Design\Acad\dFanBox.dwg", _
                         D3 / 58, D3 / 58, 1#, 0)
    ThisDrawing.SendCommand "Explode (entlast)  "
    ThisDrawing.Application.ZoomExtents
    
    ' 도면에 Text 기입하기
    Dim tText As String
    Sc = D3 / 58
    Height = 2 * Sc
    
    PutText Str(q), 250.1879, 94.6714 '풍량
    PutText Str(ps), 250.1879, 88.6714 ' 풍압
    PutText Format(Str(N), "0"), 250.1879, 82.6714 ' 송풍기 회전수
    PutText Str(temp), 250.1879, 76.6714 ' 온도
    PutText "-", 250.1879, 70.6714 ' 모터풀리
    PutText "-", 250.1879, 64.6714 ' Fan풀리
    PutText "-", 250.1879, 58.6714 ' 벨트타입/가닥수
    
    Dim oldTstyle As AcadTextStyle
    Dim newTstyle As AcadTextStyle
        Set oldTstyle = ThisDrawing.ActiveTextStyle
        Set newTstyle = ThisDrawing.TextStyles.Add("한글")
        newTstyle.fontFile = "C:\Windows\Fonts\malgunsl.ttf"
        newTstyle.SetFont "맑은 고딕 Semilight", False, False, 129, 50
    
    ThisDrawing.ActiveTextStyle = newTstyle
    PutText frmOutput.txtMMaker, 310.303, 94.6714   ' 모터 메이커
    ThisDrawing.ActiveTextStyle = oldTstyle
    PutText frmOutput.txtMType, 310.303, 88.6714   ' 모터 타입
    PutText Str(motorcapa), 310.303, 82.6714  ' 모터 출력
    PutText Str(motorrpm), 310.303, 76.6714  ' 모터 회전수
        tText = Str(motorpoles) + "P/" + frmOutput.txtMFrequency
    PutText tText, 310.303, 70.6714 ' 극수/주파수
    PutText "3%%c", 310.303, 64.6714  ' 상수
        tText = Str(motorvoltage) + "V/" + Format(Str(motorloadamp), "0.0") + "A"
    PutText tText, 310.303, 58.6714 ' 전압/전류
    
    ThisDrawing.ActiveTextStyle = newTstyle
    Height = 3.2 * Sc
    PutText frmOutput.txtCustomer, 300.9441, -54.9238 ' 고객명
    
    ThisDrawing.ActiveTextStyle = oldTstyle
    Height = 2 * Sc
    PutText Format(Date, "YYYY. M. D."), 244.5854, -68.3686 ' 설계일자
    
    ThisDrawing.Regen acActiveViewport
    ThisDrawing.Utility.Prompt ""
    ThisDrawing.Application.Update
    ThisDrawing.Utility.Prompt "Auto Drawing Completed!!!"
    VariablesSetting
    ThisDrawing.Application.Update
    
End Sub ' 직결형 도면 작성

Private Sub LoadData()
    
    'Data 결정하기
        Select Case frmOutput.txtMFrame
            Case "71"
                MDist = 300
                MWidth = Int((200 + Cirflange.B) / 10) * 10 + 10
            Case "80"
                MDist = 300
                MWidth = Int((232 + Cirflange.B) / 10) * 10 + 10
            Case "90L"
                MDist = 300
                MWidth = Int((282 + Cirflange.B) / 10) * 10 + 10
            Case "100L"
                MDist = 400
                MWidth = Int((311 + Cirflange.B) / 10) * 10 + 10
            Case "112M"
                MDist = 400
                MWidth = Int((313 + Cirflange.B) / 10) * 10 + 10
            Case "132S"
                MDist = 450
                MWidth = Int((358 + Cirflange.B) / 10) * 10 + 10
            Case "132M"
                MDist = 450
                MWidth = Int((396 + Cirflange.B) / 10) * 10 + 10
            Case "160M"
                MDist = 550
                MWidth = Int((473 + Cirflange.B) / 10) * 10 + 10
            Case "160L"
                MDist = 550
                MWidth = Int((517 + Cirflange.B) / 10) * 10 + 10
            Case "180M"
                MDist = 600
                MWidth = Int((558 + Cirflange.B) / 10) * 10 + 10
            Case "180L"
                MDist = 596
                MWidth = Int((610 + Cirflange.B) / 10) * 10 + 10
            Case "200L"
                MDist = 650
                MWidth = Int((651 + Cirflange.B) / 10) * 10 + 10
            Case "225S"
                MDist = 850
                MWidth = Int((677 + Cirflange.B) / 10) * 10 + 10
            Case "225M"
                MDist = 850
                MWidth = Int((702 + Cirflange.B) / 10) * 10 + 10
            Case "250S"
                MDist = 900
                MWidth = Int((736 + Cirflange.B) / 10) * 10 + 10
            Case "250M"
                MDist = 900
                MWidth = Int((774 + Cirflange.B) / 10) * 10 + 10
            Case "280S"
                MDist = 1100
                MWidth = Int((874 + Cirflange.B) / 10) * 10 + 10
            Case "280M"
                MDist = 1100
                MWidth = Int((925 + Cirflange.B) / 10) * 10 + 10
            Case "280L"
                MDist = 1100
                MWidth = Int((1014 + Cirflange.B) / 10) * 10 + 10
            Case "280LL"
                MDist = 300
                MWidth = Int((1141 + Cirflange.B) / 10) * 10 + 10
        End Select
        
        ' 해당 베어링 치수 할당
    Dim SN3Name As String
        SN3Name = Mid$(frmOutput.txtBearingImp.text, 2, 3)
        SN3Name = "SN" + SN3Name
        SN3.Name = SN3Name
            
    Select Case SN3Name
        Case "SN305"
            BBaseW = 280
        Case "SN306"
            BBaseW = 280
        Case "SN307"
            BBaseW = 300
        Case "SN308"
            BBaseW = 300
        Case "SN309"
            BBaseW = 350
        Case "SN310"
            BBaseW = 350
        Case "SN311"
            BBaseW = 370
        Case "SN312"
            BBaseW = 370
        Case "SN313"
            BBaseW = 410
        Case "SN314"
            BBaseW = 410
        Case "SN315"
            BBaseW = 440
        Case "SN316"
            BBaseW = 440
        Case "SN317"
            BBaseW = 480
        Case "SN318"
            BBaseW = 500
        Case "SN319"
            BBaseW = 520
        Case "SN320"
            BBaseW = 520
        Case "SN322"
            BBaseW = 560
        Case "SN324"
            BBaseW = 640
        Case "SN326"
            BBaseW = 660
        Case "SN328"
            BBaseW = 730
        Case "SN330"
            BBaseW = 780
        Case "SN332"
            BBaseW = 810
    End Select
 
    

End Sub

Private Sub PutText(text As String, X As Double, Y As Double)
    
    Dim textObj As AcadText
    Dim insertionPoint(0 To 2) As Double
    Dim alignmentPoint(0 To 2) As Double
    Dim xCood As Double
    Dim yCood As Double
        xCood = X * Sc
        yCood = Y * Sc
        If frmInput.optVbelt Then
            If Right$(Direction, 1) = "L" Then
                xCood = xCood - 0.5 * D3
            End If
        End If
    
        insertionPoint(0) = xCood
        insertionPoint(1) = yCood
        insertionPoint(2) = 0
        If text = "" Then text = "-"
        Set textObj = ThisDrawing.ModelSpace.AddText(text, insertionPoint, Height)
        textObj.Alignment = acAlignmentMiddle
        alignmentPoint(0) = xCood
        alignmentPoint(1) = yCood
        alignmentPoint(2) = 0
        textObj.Alignment = acAlignmentMiddle
        textObj.TextAlignmentPoint = alignmentPoint
        textObj.color = acYellow
        textObj.Update
    
End Sub

