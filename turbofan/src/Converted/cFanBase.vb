' 원본: cFanBase.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cFanBase

    Public CP As Object
    Public ChanSize As Integer
    Public ConPnt1 As Object ' Motor 자리
    Public ConPnt2 As Object
    Public ConPnt3 As Object
    Public ConPnt4 As Object
    Public ConPnt5 As Object
    Public ConPnt6 As Object

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
        Dim P1 As Object
        Dim P2 As Object
        Dim P3 As Object
        Dim P4 As Object
        Dim P5 As Object
        Dim P6 As Object
        Dim P7 As Object
        Dim P8 As Object
        Dim P9 As Object
        Dim P10 As Object
        Dim P11 As Object
        Dim P12 As Object
        Dim P13 As Object
        Dim P14 As Object
        Dim tmpLine1 As Object
        Dim tmpLine2 As Object
        Dim tmpLine3 As Object
        Dim tmpPnt1 As Object
        Dim tmpPnt2 As Object
        Dim tmpPnt3 As Object
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim Line6 As Object
        Dim Line7 As Object
        Dim Line8 As Object
        Dim Line9 As Object
        Dim Line10 As Object

        RDML = Left(Direction, 1) + Right(Direction, 1)

        Select Case ChanSize
            Case 75
                H = 75 : B = 40 : b1 = 15 : b2 = 25 : t1 = 5 : t2 = 7 : R1 = 8 : R2 = 4 : Y1 = 17 : Y2 = 23
            Case 100
                H = 100 : B = 50 : b1 = 20 : b2 = 30 : t1 = 5 : t2 = 7.5 : R1 = 8 : R2 = 4 : Y1 = 22 : Y2 = 28
            Case 125
                H = 125 : B = 65 : b1 = 27 : b2 = 38 : t1 = 6 : t2 = 8 : R1 = 8 : R2 = 4 : Y1 = 29 : Y2 = 36
            Case 150
                H = 150 : B = 75 : b1 = 32 : b2 = 43 : t1 = 6.5 : t2 = 10 : R1 = 10 : R2 = 5 : Y1 = 34 : Y2 = 41
            Case 200
                H = 200 : B = 90 : b1 = 38 : b2 = 52 : t1 = 8 : t2 = 13.5 : R1 = 14 : R2 = 7 : Y1 = 40 : Y2 = 50
        End Select


        If RDML = "RL" Or RDML = "LR" Then
            P1 = VbCopy(FanCasing.ConPnt3)
            Else
            P1 = VbCopy(FanCasing.ConPnt2)
        End If

            P2 = PolarPoint(P1, Dtr(270), t2)
            P3 = PolarPoint(P1, Dtr(270), H - t2)
            P4 = PolarPoint(P1, Dtr(270), H)

        If RDML = "RL" Or RDML = "LL" Then
            P5 = PolarPoint(P4, Dtr(180), MDist + D3)
            Else
            P5 = PolarPoint(P4, Dtr(0), MDist + D3)
        End If

            P6 = PolarPoint(P5, Dtr(90), t2)
            P7 = PolarPoint(P5, Dtr(90), H - t2)
            P8 = PolarPoint(P5, Dtr(90), H)
            P9 = PolarPoint(P8, Dtr(90), t2)
            P10 = PolarPoint(P8, Dtr(90), H - t2)
            P11 = PolarPoint(P8, Dtr(90), H)


        If RDML = "RL" Or RDML = "LL" Then
            tmpPnt1 = PolarPoint(P11, Dtr(0), 0.1)
            tmpPnt2 = PolarPoint(P10, Dtr(0), 0.1)
            tmpPnt3 = PolarPoint(P9, Dtr(0), 0.1)
            Else
            tmpPnt1 = PolarPoint(P11, Dtr(180), 0.1)
            tmpPnt2 = PolarPoint(P10, Dtr(180), 0.1)
            tmpPnt3 = PolarPoint(P9, Dtr(180), 0.1)
        End If

        tmpLine1 = ThisDrawing.ModelSpace.AddLine(P11, tmpPnt1)
        tmpLine2 = ThisDrawing.ModelSpace.AddLine(P10, tmpPnt2)
        tmpLine3 = ThisDrawing.ModelSpace.AddLine(P9, tmpPnt3)

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

            Line1 = ThisDrawing.ModelSpace.AddLine(P1, P4)
                Line1.color = VbCopy(acCyan)
                Line1.Update

            Line2 = ThisDrawing.ModelSpace.AddLine(P4, P5)
                Line2.color = VbCopy(acCyan)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P5, P8)
                Line3.color = VbCopy(acCyan)
                Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P8, P11)
                Line4.color = VbCopy(acCyan)
                Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P11, P12)
                Line5.color = VbCopy(acCyan)
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P10, P13)
                Line6.color = VbCopy(acCyan)
                Line6.Update
            Line7 = ThisDrawing.ModelSpace.AddLine(P9, P14)
                Line7.color = VbCopy(acCyan)
                Line7.Update
            Line8 = ThisDrawing.ModelSpace.AddLine(P8, P1)
                Line8.color = VbCopy(acCyan)
                Line8.Update
            Line9 = ThisDrawing.ModelSpace.AddLine(P7, P2)
                Line9.color = VbCopy(acCyan)
                Line9.Update
            Line10 = ThisDrawing.ModelSpace.AddLine(P6, P3)
                Line10.color = VbCopy(acCyan)
                Line10.Update

        If RDML = "RL" Or RDML = "LL" Then
            ConPnt1 = PolarPoint(P11, Dtr(0), 0.4 * MDist)
        Else
            ConPnt1 = PolarPoint(P11, Dtr(180), 0.4 * MDist)
        End If

        ' 치수점 할당

        If Right(Direction, 1) = "L" Then

            dimP1 = VbCopy(P5)
            dimP3 = VbCopy(P4)

            Else

            dimP1 = VbCopy(P4)
            dimP3 = VbCopy(P5)

        End If

    End Sub

    Public Sub DrawPlan() '평면도
        Dim P1 As Object
        Dim P2 As Object
        Dim P3 As Object
        Dim P4 As Object
        Dim P5 As Object
        Dim P6 As Object
        Dim P7 As Object
        Dim P8 As Object
        Dim P9 As Object
        Dim P10 As Object
        Dim P11 As Object
        Dim P12 As Object
        Dim P13 As Object
        Dim P14 As Object
        Dim P15 As Object
        Dim P16 As Object
        Dim P17 As Object
        Dim P18 As Object
        Dim P19 As Object
        Dim P20 As Object
        Dim P21 As Object
        Dim P22 As Object
        Dim P23 As Object
        Dim eAng As Double
        Dim WAng As Double
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim Line6 As Object
        Dim Line7 As Object
        Dim Line8 As Object
        Dim Line9 As Object
        Dim Line10 As Object
        Dim Line11 As Object
        Dim Line12 As Object
        Dim Line13 As Object
        Dim tmpPnt1 As Object









        If Right(Direction, 1) = "L" Then
            eAng = 0
            WAng = 180
            Else
            eAng = 180
            WAng = 0
        End If

            P1 = PolarPoint(CP, Dtr(270), FanCasing.Wout / 2)
            P2 = PolarPoint(P1, Dtr(eAng), BBaseW / 2)
            P3 = PolarPoint(P2, Dtr(WAng), BBaseW)

            P6 = PolarPoint(P1, Dtr(eAng), D3 / 2)
            P7 = PolarPoint(P1, Dtr(WAng), D3 / 2)

            P4 = PolarPoint(P6, Dtr(WAng), B)
            P5 = PolarPoint(P7, Dtr(eAng), B)

            P8 = PolarPoint(P7, Dtr(90), FanCasing.Wout + MWidth)
            P9 = PolarPoint(P5, Dtr(90), FanCasing.Wout + MWidth)
            P10 = PolarPoint(P3, Dtr(90), FanCasing.Wout + MWidth)
            P11 = PolarPoint(P2, Dtr(90), FanCasing.Wout + MWidth)
            P12 = PolarPoint(P4, Dtr(90), FanCasing.Wout + MWidth)
            P13 = PolarPoint(P6, Dtr(90), FanCasing.Wout + MWidth)

            P14 = PolarPoint(P6, Dtr(270), B)
            P15 = PolarPoint(P14, Dtr(WAng), MDist + D3)
            P16 = PolarPoint(P15, Dtr(90), B)
            P17 = PolarPoint(P16, Dtr(eAng), B)
            P18 = PolarPoint(P16, Dtr(90), FanCasing.Wout + MWidth)
            P19 = PolarPoint(P18, Dtr(90), B)
            P20 = PolarPoint(P18, Dtr(eAng), B)
            P21 = PolarPoint(P14, Dtr(90), FanCasing.Wout + MWidth + 2 * B)





            Line3 = ThisDrawing.ModelSpace.AddLine(P21, P19)
                Line3.Update
        ThisDrawing.Application.ZoomExtents
        ThisDrawing.Application.ZoomScaled(0.8, acZoomScaledRelative)
        ThisDrawing.Regen(acActiveViewport)

            Line1 = ThisDrawing.ModelSpace.AddLine(P15, P14)
                Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P14, P21)
                Line2.Update

            Line4 = ThisDrawing.ModelSpace.AddLine(P19, P15)
                Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P18, P13)
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P16, P6)
                Line6.Update
            Line7 = ThisDrawing.ModelSpace.AddLine(P18, P13)
                Line7.Update
            Line8 = ThisDrawing.ModelSpace.AddLine(P17, P20)
                Line8.Update
            Line9 = ThisDrawing.ModelSpace.AddLine(P7, P8)
                Line9.Update
            Line10 = ThisDrawing.ModelSpace.AddLine(P5, P9)
                Line10.Update
            Line11 = ThisDrawing.ModelSpace.AddLine(P3, P10)
                Line11.Update
            Line12 = ThisDrawing.ModelSpace.AddLine(P2, P11)
                Line12.Update
            Line13 = ThisDrawing.ModelSpace.AddLine(P4, P12)
                Line13.Update

        ' 삽입점 계산
            tmpPnt1 = PolarPoint(P18, Dtr(eAng), 0.4 * MDist)

        ConPnt1 = PolarPoint(tmpPnt1, Dtr(90), 20) ' Fan Pulley 삽입점
        ConPnt2 = PolarPoint(ConPnt1, Dtr(270), Motor.C + Motor.B / 2) '모터 삽입점

        ' 모터 슬라이드 베이스 작도 중심점
        ConPnt6 = VbCopy(P19)

    End Sub

    Public Sub DrawRight() ' 우측면도 작성
        Dim P1 As Object
        Dim P2 As Object
        Dim P3 As Object
        Dim P4 As Object
        Dim P5 As Object
        Dim P6 As Object
        Dim P7 As Object
        Dim P8 As Object
        Dim P9 As Object
        Dim P10 As Object
        Dim P11 As Object
        Dim P12 As Object
        Dim P13 As Object
        Dim P14 As Object
        Dim P15 As Object
        Dim P16 As Object
        Dim P17 As Object
        Dim P18 As Object
        Dim P19 As Object
        Dim P20 As Object
        Dim i As Integer
        Dim pnt As Object
        Dim bBaseEnt As Object
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim Line6 As Object
        Dim Line7 As Object
        Dim P21 As Object
        Dim P22 As Object
        Dim P23 As Object
        Dim P24 As Object
        Dim Line8 As Object
        Dim Line9 As Object
        Dim P25 As Object
        Dim P26 As Object
        Dim P27 As Object
        Dim P28 As Object
        Dim P29 As Object
        Dim P30 As Object
        Dim P31 As Object
        Dim mtmpPnt As Object
        Dim Line10 As Object
        Dim Line11 As Object
        Dim Line12 As Object

        ' Channel 인스턴스에 치수 할당
        With Channel
            .H = VbCopy(H)
            .B = VbCopy(B)
            .t1 = VbCopy(t1)
            .t2 = VbCopy(t2)
            .R1 = VbCopy(R1)
            .R2 = VbCopy(R2)
        End With



            P1 = PolarPoint(CP, Dtr(0), Wout / 2)
            P2 = PolarPoint(P1, Dtr(0), 40 + SN3.a / 2)
            P3 = PolarPoint(P2, Dtr(270), SN3.H)
            P4 = PolarPoint(P1, Dtr(0), 20 + MWidth)
            P5 = PolarPoint(P4, Dtr(180), 20 + SN3.a / 2)
            P6 = PolarPoint(P5, Dtr(270), SN3.H)
            P7 = PolarPoint(P1, Dtr(270), SN3.H)
            P8 = PolarPoint(P7, Dtr(270), RecFlange.t)
            P9 = PolarPoint(P8, Dtr(0), MWidth)
            P10 = PolarPoint(P7, Dtr(0), MWidth)

            P12 = PolarPoint(P1, Dtr(270), FanCasing.cHeight)
            P11 = PolarPoint(P12, Dtr(0), MWidth)
            P13 = PolarPoint(P12, Dtr(180), Wout)
            P14 = PolarPoint(P13, Dtr(270), t2)
            P15 = PolarPoint(P13, Dtr(270), H - t2)
            P16 = PolarPoint(P15, Dtr(270), t2)
            P17 = PolarPoint(P16, Dtr(0), Wout + MWidth)
            P18 = PolarPoint(P15, Dtr(0), Wout + MWidth)
            P19 = PolarPoint(P14, Dtr(0), Wout + MWidth)
            P20 = PolarPoint(P4, Dtr(270), FanCasing.cHeight - H - Motor.H)

        If Left(Direction, 2) = "RL" Then
            bPntCol = New VBCollection

            bPntCol.Add(P10)
            bPntCol.Add(P7)
            bPntCol.Add(P12)

            With Channel
                .CP = VbCopy(P13)
                .Mirror = True
                .PointCal

                .CP = VbCopy(P11)
                .Mirror = False
                .PointCal
            End With

            ReDim pntArray(bPntCol.Count * 3 - 1)


            For i = 1 To bPntCol.Count

                pnt = bPntCol.Item(i)
                pntArray(0 + (i - 1) * 3) = pnt(0)
                pntArray(1 + (i - 1) * 3) = pnt(1)
                pntArray(2 + (i - 1) * 3) = pnt(2)

            Next i


            bBaseEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)

            With bBaseEnt
                .Closed = True
                '.SetBulge 1, Sqr(2) - 1
                .Highlight(True)
            End With

            AutoTrim.Ent = bBaseEnt
            AutoTrim.DoTrim
            bBaseEnt.Delete

        End If


            Line1 = ThisDrawing.ModelSpace.AddLine(P7, P10)
                Line1.Update

        ThisDrawing.Application.ZoomExtents
        ThisDrawing.Application.ZoomScaled(0.85, acZoomScaledRelative)
        ThisDrawing.Regen(acActiveViewport)

            Line2 = ThisDrawing.ModelSpace.AddLine(P8, P9)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P10, P11)
                Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P13, P11)
                Line4.color = VbCopy(acCyan)
                Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P14, P19)
                Line5.color = VbCopy(acCyan)
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P15, P18)
                Line6.color = VbCopy(acCyan)
                Line6.Update
            Line7 = ThisDrawing.ModelSpace.AddLine(P16, P17)
                Line7.color = VbCopy(acCyan)
                Line7.Update

        With Channel
            .CP = VbCopy(P13)
            .Mirror = True
            .PointCal
            .Draw
            .CP = VbCopy(P11)
            .Mirror = False
            .PointCal
            .Draw
        End With

        ' 모터의 위치가 좌측일 때
        If Right(Direction, 1) = "L" Then
                P21 = PolarPoint(P20, Dtr(90), Motor.DS / 2)
                P22 = PolarPoint(P21, Dtr(180), 20)
                P23 = PolarPoint(P22, Dtr(270), Motor.DS)
                P24 = PolarPoint(P23, Dtr(0), 20)
                Line8 = ThisDrawing.ModelSpace.AddLine(P22, P21)
                Line9 = ThisDrawing.ModelSpace.AddLine(P23, P24)
                    Line8.color = VbCopy(acCyan)
                    Line9.color = VbCopy(acCyan)
        End If

        '모터의 위치가 우측일 때 슬라이드 베이스 그리기
        If Right(Direction, 1) = "R" Then
                mtmpPnt = PolarPoint(P20, Dtr(180), Motor.C + Y2)
                P25 = PolarPoint(mtmpPnt, Dtr(270), Motor.H)
                P26 = PolarPoint(P25, Dtr(180), Motor.B - 2 * Y2)
                P27 = PolarPoint(P26, Dtr(270), t2)
                P28 = PolarPoint(P26, Dtr(270), H - t2)
                P29 = PolarPoint(P25, Dtr(270), H - t2)
                P30 = PolarPoint(P25, Dtr(270), t2)
                P31 = PolarPoint(P25, Dtr(180), (Motor.B - 2 * Y2) / 2)
                Line10 = ThisDrawing.ModelSpace.AddLine(P26, P25)
                Line11 = ThisDrawing.ModelSpace.AddLine(P27, P30)
                Line12 = ThisDrawing.ModelSpace.AddLine(P28, P29)
                    Line10.color = VbCopy(acCyan)
                    Line11.color = VbCopy(acCyan)
                    Line12.color = VbCopy(acCyan)
            With Channel
                .CP = VbCopy(P25)
                .Mirror = False
                .PointCal
                .Draw
                .CP = VbCopy(P26)
                .Mirror = True
                .PointCal
                .Draw
            End With

        End If


        ' 접속점 할당
        ConPnt1 = VbCopy(P3)
        ConPnt2 = VbCopy(P6)
        ConPnt3 = VbCopy(P4)
        ConPnt4 = VbCopy(P20)
        ConPnt5 = VbCopy(P31)

        If Right(Direction, 1) = "L" Then
            rCenP3 = VbCopy(P20)
        End If

    End Sub

End Class
