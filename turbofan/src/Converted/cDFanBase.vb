' 원본: cDFanBase.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cDFanBase

    Public CP As Object
    Public ChanSize As Integer
    Public MotorPoint As Object
    Public BossPoint As Object

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
        Dim P1 As Object
        Dim P2 As Object
        Dim P3 As Object
        Dim P4 As Object
        Dim P5 As Object
        Dim P6 As Object
        Dim P7 As Object
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim Line6 As Object

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


            P1 = PolarPoint(CP, Dtr(270), t2)
            P2 = PolarPoint(CP, Dtr(270), H - t2)
            P3 = PolarPoint(CP, Dtr(270), H)

        If Left(Direction, 1) = "R" Then
            P4 = PolarPoint(P3, Dtr(0), D3)
            Else
            P4 = PolarPoint(P3, Dtr(180), D3)
        End If

            P5 = PolarPoint(P4, Dtr(90), t2)
            P6 = PolarPoint(P4, Dtr(90), H - t2)
            P7 = PolarPoint(P4, Dtr(90), H)

            Line1 = ThisDrawing.ModelSpace.AddLine(CP, P3)
                Line1.color = VbCopy(acCyan)
                Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P3, P4)
                Line2.color = VbCopy(acCyan)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P4, P7)
                Line3.color = VbCopy(acCyan)
                Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P7, CP)
                Line4.color = VbCopy(acCyan)
                Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P1, P6)
                Line5.color = VbCopy(acCyan)
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P2, P5)
                Line6.color = VbCopy(acCyan)
                Line6.Update

        ' 치수점 할당
        If Left(Direction, 1) = "R" Then
            dimP1 = VbCopy(P3)
            dimP2 = VbCopy(P4)
            Else
            dimP1 = VbCopy(P4)
            dimP2 = VbCopy(P3)
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
        Dim mLeng As Double
        Dim mbW As Double
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




            P1 = PolarPoint(CP, Dtr(270), 15 + FanCasing.Wout + B)
            P2 = PolarPoint(P1, Dtr(180), (D3 - 2 * B) / 2)
            P3 = PolarPoint(P2, Dtr(180), B)
            P4 = PolarPoint(P2, Dtr(90), B)
            P5 = PolarPoint(P4, Dtr(0), D3 - 2 * B)
            P6 = PolarPoint(P5, Dtr(270), B)
            P7 = PolarPoint(P6, Dtr(0), B)
            mLeng = Int((2.5 * Motor.C + Motor.B) / 10) * 10 + 10
            P8 = PolarPoint(P7, Dtr(90), 2 * B + FanCasing.Wout + mLeng)
            P9 = PolarPoint(P8, Dtr(180), B)
            P10 = PolarPoint(P9, Dtr(270), B)
            P11 = PolarPoint(P9, Dtr(180), D3 - 2 * B)
            P12 = PolarPoint(P11, Dtr(180), B)
            P13 = PolarPoint(P11, Dtr(270), B)

        If D3 - 2 * B - Motor.AB > 200 Then
            mbW = Int(((D3 - 2 * B - Motor.AB) / 2 - 100) / 10) * 10
            P14 = PolarPoint(P4, Dtr(0), mbW)
            P15 = PolarPoint(P5, Dtr(180), mbW)
            P16 = PolarPoint(P13, Dtr(0), mbW)
            P17 = PolarPoint(P10, Dtr(180), mbW)
        End If




            Line1 = ThisDrawing.ModelSpace.AddLine(P12, P8)
                Line1.Update

        ThisDrawing.Application.ZoomExtents
        ThisDrawing.Application.ZoomScaled(0.8, acZoomScaledRelative)

            Line2 = ThisDrawing.ModelSpace.AddLine(P12, P3)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P3, P7)
                Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P7, P8)
                Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P2, P11)
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P6, P9)
                Line6.Update
            Line7 = ThisDrawing.ModelSpace.AddLine(P4, P5)
                Line7.Update
            Line8 = ThisDrawing.ModelSpace.AddLine(P13, P10)
                Line8.Update
        If D3 - 2 * B - Motor.AB > 200 Then
            Line9 = ThisDrawing.ModelSpace.AddLine(P14, P16)
                Line9.Update
            Line10 = ThisDrawing.ModelSpace.AddLine(P15, P17)
                Line10.Update
        End If


    End Sub

    Public Sub DrawRight()
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
        Dim mLeng As Object
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
            P2 = PolarPoint(P1, Dtr(270), Motor.H)
            P3 = PolarPoint(P2, Dtr(270), RecFlange.t)
            mLeng = Int((2.5 * Motor.C + Motor.B) / 10) * 10 + 10
            P4 = PolarPoint(P2, Dtr(0), mLeng)
            P5 = PolarPoint(P4, Dtr(270), RecFlange.t)
            P6 = PolarPoint(P4, Dtr(270), FanCasing.cHeight - Motor.H)

            P7 = PolarPoint(P2, Dtr(270), FanCasing.cHeight - Motor.H)

            P8 = PolarPoint(P7, Dtr(180), FanCasing.Wout)
            P9 = PolarPoint(P8, Dtr(270), t2)
            P10 = PolarPoint(P8, Dtr(270), H - t2)
            P11 = PolarPoint(P8, Dtr(270), H)
            P12 = PolarPoint(P6, Dtr(270), H)
            P13 = PolarPoint(P12, Dtr(90), t2)
            P14 = PolarPoint(P6, Dtr(270), t2)

        If Direction = "RL" Then
            bPntCol = New VBCollection

            bPntCol.Add(P4)
            bPntCol.Add(P2)
            bPntCol.Add(P7)

            With Channel
                .CP = VbCopy(P8)
                .Mirror = True
                .PointCal

                .CP = VbCopy(P6)
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


            Line1 = ThisDrawing.ModelSpace.AddLine(P4, P6)
                Line1.Update

        ThisDrawing.Application.ZoomExtents
        ThisDrawing.Application.ZoomScaled(0.85, acZoomScaledRelative)
        ThisDrawing.Regen(acActiveViewport)

            Line2 = ThisDrawing.ModelSpace.AddLine(P4, P2)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P3, P5)
                Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P8, P6)
                Line4.color = VbCopy(acCyan)
                Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P11, P12)
                Line5.color = VbCopy(acCyan)
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P9, P14)
                Line6.color = VbCopy(acCyan)
                Line6.Update
            Line7 = ThisDrawing.ModelSpace.AddLine(P10, P13)
                Line7.color = VbCopy(acCyan)
                Line7.Update

        With Channel
            .CP = VbCopy(P8)
            .Mirror = True
            .PointCal
            .Draw

            .CP = VbCopy(P6)
            .Mirror = False
            .PointCal
            .Draw
        End With

        MotorPoint = PolarPoint(P2, Dtr(0), 15 + Motor.C + Motor.B / 2)
        BossPoint = PolarPoint(P1, Dtr(0), 15)

    End Sub



End Class
