' 원본: cMotor.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cMotor

    Public FrameNo As String '후렘임 번호
    Public CP As Object ' 삽입점
    Public Mirror As Boolean ' 거울 영상 여부
    Public C As Double
    Public B As Double
    Public H As Double
    Public DS As Double ' 축직경
    Public RotAng As Double
    Public AB As Double

    Dim pntCol As New VBCollection

    Dim a As Double
    Dim AA As Double
    Dim AC As Double
    Dim AD As Double
    Dim AE As Double
    Dim BB As Double

    Dim HA As Double
    Dim HC As Double
    Dim K As Double
    Dim LB As Double
    Dim R1 As Double
    Dim R2 As Double
    Dim R3 As Double
    Dim R4 As Double
    Dim R5 As Double
    Dim XO As Double
    Dim XP As Double

    Dim XN As Double
    Dim XL As Double
    Dim YA As Double
    Dim YB As Double
    Dim YD As Double
    Dim YE As Double
    Dim YF As Double
    Dim YG As Double
    Dim YH As Double
    Dim YK As Double

    Dim eAng As Double
    Dim WAng As Double

    Dim pntArray() As Double
    Dim MotorEnt As Object
    Dim MirMotorEnt As Object


    Public Sub DrawFront() ' 정면도
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
        Dim P24 As Object
        Dim P25 As Object
        Dim P26 As Object
        Dim P27 As Object
        Dim P28 As Object
        Dim P29 As Object
        Dim P30 As Object
        Dim P31 As Object
        Dim P32 As Object
        Dim P33 As Object
        Dim P34 As Object
        Dim P35 As Object
        Dim P36 As Object
        Dim tmpPnt As Object
        Dim tmpLine As Object
        Dim tmpCir As Object
        Dim StartPnt(2) As Double
        Dim EndPnt(2) As Double
        Dim StartLine As Object
        Dim EndLine As Object
        Dim StartAngle As Double
        Dim EndAngle As Double
        Dim IntersectPoint As Object
        Dim btmLine As Object
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
        Dim Line14 As Object
        Dim Line15 As Object
        Dim Line16 As Object
        Dim Line17 As Object
        Dim Line18 As Object
        Dim Line19 As Object
        Dim Line20 As Object
        Dim Line21 As Object
        Dim Line22 As Object
        Dim Line23 As Object
        Dim Line24 As Object
        Dim Arc1 As Object
        Dim Arc2 As Object
        Dim Cir1 As Object
        Dim IntPnt As Object
        Dim gPnt1 As Object
        Dim gPnt2 As Object
        Dim gPnt3 As Object
        Dim gPnt4 As Object
        Dim gPnt5 As Object
        Dim gPnt6 As Object
        Dim gPnt7 As Object
        Dim gPnt8 As Object
        Dim tgLine1 As Object
        Dim tgLine2 As Object
        Dim tgLine3 As Object
        Dim tgLine4 As Object
        Dim Pnt1(2) As Double
        Dim Pnt2(2) As Double
        Dim Pnt3(2) As Double
        Dim Pnt4(2) As Double
        Dim Pnt5(2) As Double
        Dim Pnt6(2) As Double
        Dim Pnt7(2) As Double
        Dim Pnt8(2) As Double
        Dim gLine1 As Object
        Dim gLine2 As Object
        Dim gLine3 As Object
        Dim gLine4 As Object
        Dim gLine5 As Object
        Dim gLine6 As Object
        Dim gLine7 As Object
        Dim gLine8 As Object
        Dim cPnt1 As Object
        Dim cPnt2 As Object
        Dim cPnt3 As Object
        Dim cPnt4 As Object
        Dim cLine1 As Object
        Dim cLine2 As Object
        Dim cLine3 As Object
        Dim cLine4 As Object
        Dim cPnt5 As Object
        Dim cPnt6 As Object
        Dim cPnt7 As Object
        Dim cPnt8 As Object

        ReadData ' Motor Data 읽기

        If Mirror = False Then
            eAng = 0
            WAng = 180
            Else
            eAng = 180
            WAng = 0
        End If












            P1 = PolarPoint(CP, Dtr(RotAng + 90), H)
            P2 = PolarPoint(CP, Dtr(RotAng + WAng), AB / 2)
            P3 = PolarPoint(P2, Dtr(RotAng + 90), HA)
            P4 = PolarPoint(P3, Dtr(RotAng + eAng), (AB - a - K) / 2)

            P5 = PolarPoint(P4, Dtr(RotAng + eAng), K)
            P6 = PolarPoint(P5, Dtr(RotAng + eAng), AA - ((AB - a - K) / 2 + K))

            P7 = PolarPoint(P6, Dtr(RotAng + 270), HA)
            P8 = PolarPoint(P5, Dtr(RotAng + 270), HA)

            P9 = PolarPoint(P4, Dtr(RotAng + 270), HA)
            P10 = PolarPoint(CP, Dtr(RotAng + eAng), AB / 2)
            P11 = PolarPoint(P10, Dtr(RotAng + 90), HA)
            P12 = PolarPoint(P11, Dtr(RotAng + RotAng + WAng), (AB - a - K) / 2)

            P13 = PolarPoint(P12, Dtr(RotAng + WAng), K)
            P14 = PolarPoint(P13, Dtr(RotAng + WAng), AA - ((AB - a - K) / 2 + K))
            P15 = PolarPoint(P14, Dtr(RotAng + 270), HA)
            P16 = PolarPoint(P13, Dtr(RotAng + 270), HA)

            P17 = PolarPoint(P12, Dtr(RotAng + 270), HA)
            P18 = PolarPoint(P1, Dtr(RotAng + eAng), AD)
            P19 = PolarPoint(P18, Dtr(RotAng + 270), 0.5 * XL)
            P20 = PolarPoint(P19, Dtr(RotAng + WAng), XO)

            P21 = PolarPoint(P20, Dtr(RotAng + 90), (XL - 0.8 * XN) / 2)
            P22 = PolarPoint(P21, Dtr(RotAng + 90), 0.8 * XN)
            P23 = PolarPoint(P22, Dtr(RotAng + 90), (XL - 0.8 * XN) / 2)
            P24 = PolarPoint(P23, Dtr(RotAng + eAng), XO - R1)

            P25 = PolarPoint(P24, Dtr(RotAng + 270), R1)
            P26 = PolarPoint(P25, Dtr(RotAng + eAng), R1)

            P27 = PolarPoint(P22, Dtr(RotAng + WAng), XP)
            P28 = PolarPoint(P27, Dtr(RotAng + 270), 0.8 * XN)



                ' P29를 구하기 위한 루틴
            If Mirror = False Then
                tmpPnt = PolarPoint(P3, Dtr(RotAng + 60), H)
                Else
                tmpPnt = PolarPoint(P3, Dtr(RotAng + 120), H)
            End If
                tmpLine = ThisDrawing.ModelSpace.AddLine(P3, tmpPnt)
                tmpCir = ThisDrawing.ModelSpace.AddCircle(P1, R5)
            P29 = tmpLine.IntersectWith(tmpCir, acExtendNone)
                tmpLine.Delete


            If FrameNo <> "80" And FrameNo <> "90L" And FrameNo <> "100L" Then
                ' P30을 구하기 위한 루틴
            If Mirror = False Then
                tmpPnt = PolarPoint(P7, Dtr(RotAng + 60), H)
                Else
                tmpPnt = PolarPoint(P7, Dtr(RotAng + 120), H)
            End If

                tmpLine = ThisDrawing.ModelSpace.AddLine(P7, tmpPnt)
            P30 = tmpLine.IntersectWith(tmpCir, acExtendNone)
                tmpLine.Delete

                ' P31을 구하기 위한 루틴
            If Mirror = False Then
                tmpPnt = PolarPoint(P15, Dtr(RotAng + 120), H)
                Else
                tmpPnt = PolarPoint(P15, Dtr(RotAng + 60), H)
            End If

                tmpLine = ThisDrawing.ModelSpace.AddLine(P15, tmpPnt)
            P31 = tmpLine.IntersectWith(tmpCir, acExtendNone)
                tmpLine.Delete
            End If

                ' P32를 구하기 위한 루틴
            If Mirror = False Then
                tmpPnt = PolarPoint(P11, Dtr(RotAng + 120), H)
                Else
                tmpPnt = PolarPoint(P11, Dtr(RotAng + 60), H)
            End If

                tmpLine = ThisDrawing.ModelSpace.AddLine(P11, tmpPnt)
            P32 = tmpLine.IntersectWith(tmpCir, acExtendNone)
                tmpLine.Delete
            P35 = PolarPoint(CP, Dtr(RotAng + 90), HA / 2)
            P36 = PolarPoint(P35, Dtr(RotAng + eAng), 10)

                ' P33, P34를 구하기 위한 루틴

                    btmLine = ThisDrawing.ModelSpace.AddXline(P35, P36)
                    IntersectPoint = btmLine.IntersectWith(tmpCir, acExtendNone)

                    StartPnt(0) = IntersectPoint(0)
                    StartPnt(1) = IntersectPoint(1)
                    StartPnt(2) = IntersectPoint(2)

                    EndPnt(0) = IntersectPoint(3)
                    EndPnt(1) = IntersectPoint(4)
                    EndPnt(2) = IntersectPoint(5)

            P33 = VbCopy(EndPnt)
            P34 = VbCopy(StartPnt)

                    StartLine = ThisDrawing.ModelSpace.AddLine(P1, P34)
                    EndLine = ThisDrawing.ModelSpace.AddLine(P1, P33)

                    StartAngle = VbCopy(StartLine.Angle)
                    EndAngle = VbCopy(EndLine.Angle)

            tmpCir.Delete
            btmLine.Delete
            StartLine.Delete
            EndLine.Delete

            ' 엔터티 생성








                Arc1 = ThisDrawing.ModelSpace.AddArc(P1, R5, StartAngle, EndAngle)
                    Arc1.Update

            If Mirror = False Then
                Arc2 = ThisDrawing.ModelSpace.AddArc(P25, R1, Dtr(RotAng + 0), Dtr(RotAng + 90))
                Else
                Arc2 = ThisDrawing.ModelSpace.AddArc(P25, R1, Dtr(RotAng + 90), Dtr(RotAng + 180))
            End If
                Arc2.Update

                Cir1 = ThisDrawing.ModelSpace.AddCircle(P1, 0.35 * AC)
                    Cir1.Update
                Line1 = ThisDrawing.ModelSpace.AddLine(P33, P34)
                    Line1.Update

                Line2 = ThisDrawing.ModelSpace.AddLine(P2, P7)
                    Line2.Update

                Line3 = ThisDrawing.ModelSpace.AddLine(P7, P6)
                    Line3.Update

                Line4 = ThisDrawing.ModelSpace.AddLine(P6, P3)
                    Line4.Update

                Line5 = ThisDrawing.ModelSpace.AddLine(P3, P2)
                    Line5.Update

                'Hidden Line
                Line6 = ThisDrawing.ModelSpace.AddLine(P9, P4)
                    Line6.color = VbCopy(acGreen)
                    Line6.Linetype = "Hidden"
                    Line6.Update

                Line7 = ThisDrawing.ModelSpace.AddLine(P8, P5)
                    Line7.color = VbCopy(acGreen)
                    Line7.Linetype = "Hidden"
                    Line7.Update

                Line8 = ThisDrawing.ModelSpace.AddLine(P3, P29)
                    Line8.Update

                If FrameNo <> "80" And FrameNo <> "90L" And FrameNo <> "100L" Then
                    Line9 = ThisDrawing.ModelSpace.AddLine(P7, P30)
                        Line9.Update
                End If

                Line10 = ThisDrawing.ModelSpace.AddLine(P15, P10)
                    Line10.Update

                Line11 = ThisDrawing.ModelSpace.AddLine(P10, P11)
                    Line11.Update

                Line12 = ThisDrawing.ModelSpace.AddLine(P11, P14)
                    Line12.Update

                Line13 = ThisDrawing.ModelSpace.AddLine(P14, P15)
                    Line13.Update

                'Hidden Line
                Line14 = ThisDrawing.ModelSpace.AddLine(P16, P13)
                    Line14.color = VbCopy(acGreen)
                    Line14.Linetype = "Hidden"
                    Line14.Update

                Line15 = ThisDrawing.ModelSpace.AddLine(P17, P12)
                    Line15.color = VbCopy(acGreen)
                    Line15.Linetype = "Hidden"
                    Line15.Update

                If FrameNo <> "80" And FrameNo <> "90L" And FrameNo <> "100L" Then
                    Line16 = ThisDrawing.ModelSpace.AddLine(P15, P31)
                        Line16.Update
                End If

                Line17 = ThisDrawing.ModelSpace.AddLine(P11, P32)
                    Line17.Update

                Line18 = ThisDrawing.ModelSpace.AddLine(P28, P21)
                    Line18.Update

                Line19 = ThisDrawing.ModelSpace.AddLine(P27, P22)
                    Line19.Update

                Line20 = ThisDrawing.ModelSpace.AddLine(P20, P23)
                    Line20.Update

                Line21 = ThisDrawing.ModelSpace.AddLine(P23, P24)
                    Line21.Update

                Line22 = ThisDrawing.ModelSpace.AddLine(P26, P19)
                    Line22.Update

                Line23 = ThisDrawing.ModelSpace.AddLine(P19, P20)
                    Line23.Update

                Line24 = ThisDrawing.ModelSpace.AddLine(P23, P19)
                    Line24.Update




                If FrameNo = "80" Then
                    IntPnt = Line3.IntersectWith(Line1, acExtendNone)
                        Line3.EndPoint = VbCopy(IntPnt)
                        Line3.Update
                    IntPnt = Arc1.IntersectWith(Line4, acExtendNone)
                        Line4.StartPoint = VbCopy(IntPnt)
                        Line4.Update
                    IntPnt = Arc1.IntersectWith(Line7, acExtendNone)

                        Line7.EndPoint = VbCopy(IntPnt) ' 에러발생
                        Line7.Update

                    IntPnt = Line13.IntersectWith(Line1, acExtendNone)
                        Line13.StartPoint = VbCopy(IntPnt)
                        Line13.Update

                    IntPnt = Arc1.IntersectWith(Line12, acExtendNone)
                        Line12.EndPoint = VbCopy(IntPnt)
                        Line12.Update

                    IntPnt = Arc1.IntersectWith(Line14, acExtendNone)
                        Line14.EndPoint = VbCopy(IntPnt)
                        Line14.Update
                End If

                If FrameNo = "90L" Or FrameNo = "100L" Then
                    IntPnt = Line3.IntersectWith(Line1, acExtendNone)
                        Line3.EndPoint = VbCopy(IntPnt)
                        Line3.Update

                    IntPnt = Arc1.IntersectWith(Line4, acExtendNone)
                        Line4.StartPoint = VbCopy(IntPnt)
                        Line4.Update
                    IntPnt = Line13.IntersectWith(Line1, acExtendNone)
                        Line13.StartPoint = VbCopy(IntPnt)
                        Line13.Update
                    IntPnt = Arc1.IntersectWith(Line12, acExtendNone)
                        Line12.EndPoint = VbCopy(IntPnt)
                        Line12.Update
                End If

                If FrameNo = "112M" Or FrameNo = "160M" Or FrameNo = "160L" Then
                    IntPnt = Arc1.IntersectWith(Line4, acExtendNone)
                    Line4.StartPoint = VbCopy(IntPnt)
                    Line4.Update
                    IntPnt = Arc1.IntersectWith(Line3, acExtendNone)
                    Line3.EndPoint = VbCopy(IntPnt)
                    Line3.Update

                    IntPnt = Arc1.IntersectWith(Line12, acExtendNone)
                    Line12.EndPoint = VbCopy(IntPnt)
                    Line12.Update
                    IntPnt = Arc1.IntersectWith(Line13, acExtendNone)
                    Line13.StartPoint = VbCopy(IntPnt)
                    Line13.Update
                End If

                ' 그릴그리기

                    gPnt1 = PolarPoint(P1, Dtr(RotAng + 90), R4 / 8)
                    gPnt2 = PolarPoint(gPnt1, Dtr(RotAng + eAng), 0.1)

                    gPnt3 = PolarPoint(P1, Dtr(RotAng + 90), R4 * 3 / 8)
                    gPnt4 = PolarPoint(gPnt3, Dtr(RotAng + eAng), 0.1)

                    gPnt5 = PolarPoint(P1, Dtr(RotAng + 90), R4 * 5 / 8)
                    gPnt6 = PolarPoint(gPnt5, Dtr(RotAng + eAng), 0.1)

                    gPnt7 = PolarPoint(P1, Dtr(RotAng + 90), R4 * 7 / 8)
                    gPnt8 = PolarPoint(gPnt7, Dtr(RotAng + eAng), 0.1)

                    tgLine1 = ThisDrawing.ModelSpace.AddLine(gPnt1, gPnt2)
                    tgLine2 = ThisDrawing.ModelSpace.AddLine(gPnt3, gPnt4)
                    tgLine3 = ThisDrawing.ModelSpace.AddLine(gPnt5, gPnt6)
                    tgLine4 = ThisDrawing.ModelSpace.AddLine(gPnt7, gPnt8)


                IntPnt = Cir1.IntersectWith(tgLine1, acExtendOtherEntity)
                    Pnt1(0) = IntPnt(0)
                    Pnt1(1) = IntPnt(1)
                    Pnt1(2) = IntPnt(2)
                    Pnt2(0) = IntPnt(3)
                    Pnt2(1) = IntPnt(4)
                    Pnt2(2) = IntPnt(5)

                IntPnt = Cir1.IntersectWith(tgLine2, acExtendOtherEntity)
                    Pnt3(0) = IntPnt(0)
                    Pnt3(1) = IntPnt(1)
                    Pnt3(2) = IntPnt(2)
                    Pnt4(0) = IntPnt(3)
                    Pnt4(1) = IntPnt(4)
                    Pnt4(2) = IntPnt(5)

                IntPnt = Cir1.IntersectWith(tgLine3, acExtendOtherEntity)
                    Pnt5(0) = IntPnt(0)
                    Pnt5(1) = IntPnt(1)
                    Pnt5(2) = IntPnt(2)
                    Pnt6(0) = IntPnt(3)
                    Pnt6(1) = IntPnt(4)
                    Pnt6(2) = IntPnt(5)

                IntPnt = Cir1.IntersectWith(tgLine4, acExtendOtherEntity)
                    Pnt7(0) = IntPnt(0)
                    Pnt7(1) = IntPnt(1)
                    Pnt7(2) = IntPnt(2)
                    Pnt8(0) = IntPnt(3)
                    Pnt8(1) = IntPnt(4)
                    Pnt8(2) = IntPnt(5)

                tgLine1.Delete
                tgLine2.Delete
                tgLine3.Delete
                tgLine4.Delete



                    gLine1 = ThisDrawing.ModelSpace.AddLine(Pnt1, Pnt2)
                    gLine2 = ThisDrawing.ModelSpace.AddLine(Pnt3, Pnt4)
                    gLine3 = ThisDrawing.ModelSpace.AddLine(Pnt5, Pnt6)
                    gLine4 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt8)
                        gLine1.color = VbCopy(acBlue)
                        gLine2.color = VbCopy(acBlue)
                        gLine3.color = VbCopy(acBlue)
                        gLine4.color = VbCopy(acBlue)

                gLine5 = gLine1.Mirror(P1, P18)
                gLine6 = gLine2.Mirror(P1, P18)
                gLine7 = gLine3.Mirror(P1, P18)
                gLine8 = gLine4.Mirror(P1, P18)

                gLine1.Update
                gLine2.Update
                gLine3.Update
                gLine4.Update
                gLine5.Update
                gLine6.Update
                gLine7.Update
                gLine8.Update


        ' 중심선 그리기

        ' 모터중심선
            cPnt1 = PolarPoint(P1, Dtr(RotAng + WAng), R5 + D3 / 20)
            cPnt2 = PolarPoint(P1, Dtr(RotAng + eAng), AD + D3 / 20)
            cPnt3 = PolarPoint(P1, Dtr(RotAng + 270), R5 + D3 / 10)
            cPnt4 = PolarPoint(P1, Dtr(RotAng + 90), R5 + D3 / 20)

            cLine1 = ThisDrawing.ModelSpace.AddLine(cPnt1, cPnt2)
            cLine2 = ThisDrawing.ModelSpace.AddLine(cPnt3, cPnt4)
                cLine1.color = VbCopy(acRed)
                cLine1.Linetype = "Center"
                cLine1.Update
                cLine2.color = VbCopy(acRed)
                cLine2.Linetype = "Center"
                cLine2.Update

            cPnt1 = PolarPoint(CP, Dtr(RotAng + WAng), a / 2)
            cPnt2 = PolarPoint(CP, Dtr(RotAng + eAng), a / 2)

            cPnt5 = PolarPoint(cPnt1, Dtr(RotAng + 270), HA)
            cPnt6 = PolarPoint(cPnt1, Dtr(RotAng + 90), 2 * HA)

            cPnt7 = PolarPoint(cPnt2, Dtr(RotAng + 270), HA)
            cPnt8 = PolarPoint(cPnt2, Dtr(RotAng + 90), 2 * HA)

            cLine3 = ThisDrawing.ModelSpace.AddLine(cPnt5, cPnt6)
            cLine4 = ThisDrawing.ModelSpace.AddLine(cPnt7, cPnt8)
                cLine3.color = VbCopy(acRed)
                cLine3.Linetype = "Center"
                cLine3.Update
                cLine4.color = VbCopy(acRed)
                cLine4.Linetype = "Center"
                cLine4.Update



    End Sub

    Public Sub DrawPlan() ' 평면도 작성
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
        Dim P24 As Object
        Dim P25 As Object
        Dim P26 As Object
        Dim P27 As Object
        Dim P28 As Object
        Dim P29 As Object
        Dim P30 As Object
        Dim P31 As Object
        Dim P32 As Object
        Dim P33 As Object
        Dim P34 As Object
        Dim P35 As Object
        Dim P36 As Object
        Dim P37 As Object
        Dim P38 As Object
        Dim P39 As Object
        Dim P40 As Object
        Dim cP1 As Object
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
        Dim Line14 As Object
        Dim Line15 As Object
        Dim Line16 As Object
        Dim Line17 As Object
        Dim Line18 As Object
        Dim Line19 As Object
        Dim Line20 As Object
        Dim Line21 As Object
        Dim Line22 As Object
        Dim Line23 As Object
        Dim Arc1 As Object
        Dim Arc2 As Object
        Dim Arc3 As Object
        Dim Arc4 As Object
        Dim Arc5 As Object
        Dim Arc6 As Object

        pntCol = New VBCollection

        ReadData

        If Mirror = False Then
            eAng = 0
            WAng = 180
            Else
            eAng = 180
            WAng = 0
        End If












            cP1 = PolarPoint(CP, Dtr(RotAng + 90), C + 0.5 * B)

            P1 = PolarPoint(cP1, Dtr(RotAng + WAng), 0.5 * YG)
            P2 = PolarPoint(P1, Dtr(RotAng + 270), YD)
            P3 = PolarPoint(P2, Dtr(RotAng + WAng), (YH - YG) / 2)
            P4 = PolarPoint(P3, Dtr(RotAng + 270), YD)

            P5 = PolarPoint(P4, Dtr(RotAng + WAng), (YK - YH) / 2)
            P6 = PolarPoint(P5, Dtr(RotAng + 270), YD)
            P7 = PolarPoint(cP1, Dtr(RotAng + eAng), 0.5 * YG)
            P8 = PolarPoint(P7, Dtr(RotAng + 270), YD)

            P9 = PolarPoint(P8, Dtr(RotAng + eAng), (YH - YG) / 2)
            P10 = PolarPoint(P9, Dtr(RotAng + 270), YD)
            P11 = PolarPoint(P10, Dtr(RotAng + eAng), (YK - YH) / 2)
            P12 = PolarPoint(P11, Dtr(RotAng + 270), YD)

            P13 = PolarPoint(P6, Dtr(RotAng + WAng), (AC - YK - 2 * R2) / 2)
            P14 = PolarPoint(P13, Dtr(RotAng + 270), R2)
            P15 = PolarPoint(P14, Dtr(RotAng + WAng), R2)
            P16 = PolarPoint(P15, Dtr(RotAng + 270), YB)

            P17 = PolarPoint(P16, Dtr(RotAng + 270), YA - R3)
            P18 = PolarPoint(P17, Dtr(RotAng + eAng), R3)
            P19 = PolarPoint(P18, Dtr(RotAng + 270), R3)
            P20 = PolarPoint(P19, Dtr(RotAng + eAng), 2 * R4)

            P21 = PolarPoint(P20, Dtr(RotAng + 90), R3)
            P22 = PolarPoint(P21, Dtr(RotAng + eAng), R3)
            P23 = PolarPoint(P22, Dtr(RotAng + 90), YA - R3)
            P24 = PolarPoint(P23, Dtr(RotAng + 90), LB - (C + B / 2) - YA - 0.4 * XN)

            P25 = PolarPoint(P24, Dtr(RotAng + 90), 0.8 * XN)
            P26 = PolarPoint(P25, Dtr(RotAng + 90), (C + B / 2) - R2 - 3 * YD - 0.4 * XN)
            P27 = PolarPoint(P26, Dtr(RotAng + WAng), R2)
            P28 = PolarPoint(P27, Dtr(RotAng + 90), R2)

            P29 = PolarPoint(P24, Dtr(RotAng + WAng), XP - (AD - XO - R5))
            P30 = PolarPoint(P29, Dtr(RotAng + 90), 0.8 * XN)
            P31 = PolarPoint(P30, Dtr(RotAng + eAng), XP)
            P32 = PolarPoint(P31, Dtr(RotAng + 90), 0.1 * XN)

            P33 = PolarPoint(P32, Dtr(RotAng + eAng), XO - R1)
            P34 = PolarPoint(P33, Dtr(RotAng + 270), R1)
            P35 = PolarPoint(P34, Dtr(RotAng + eAng), R1)
            P36 = PolarPoint(P35, Dtr(RotAng + 270), XN - 2 * R1)

            P37 = PolarPoint(P36, Dtr(RotAng + WAng), R1)
            P38 = PolarPoint(P37, Dtr(RotAng + 270), R1)
            P39 = PolarPoint(P38, Dtr(RotAng + WAng), XO - R1)
            P40 = PolarPoint(P39, Dtr(RotAng + 90), 0.1 * XN)

            pntCol.Add(P19)
            pntCol.Add(P20)
            pntCol.Add(P22)
            pntCol.Add(P24)

            pntCol.Add(P40)
            pntCol.Add(P39)
            pntCol.Add(P38)
            pntCol.Add(P36)

            pntCol.Add(P35)
            pntCol.Add(P33)
            pntCol.Add(P32)
            pntCol.Add(P31)

            pntCol.Add(P25)
            pntCol.Add(P26)
            pntCol.Add(P28)
            pntCol.Add(P12)

            pntCol.Add(P11)
            pntCol.Add(P10)
            pntCol.Add(P9)
            pntCol.Add(P8)

            pntCol.Add(P7)
            pntCol.Add(P1)
            pntCol.Add(P2)
            pntCol.Add(P3)

            pntCol.Add(P4)
            pntCol.Add(P5)
            pntCol.Add(P6)
            pntCol.Add(P13)

            pntCol.Add(P15)
            pntCol.Add(P17)

            MakePntArray

            MotorEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)



            With MotorEnt
                .Closed = True
                If Mirror = False Then
                    .SetBulge(1, Sqr(2) - 1)
                    .SetBulge(6, Sqr(2) - 1)
                    .SetBulge(8, Sqr(2) - 1)
                    .SetBulge(13, Sqr(2) - 1)
                    .SetBulge(27, Sqr(2) - 1)
                    .SetBulge(29, Sqr(2) - 1)
                    Else
                    .SetBulge(1, 1 - Sqr(2))
                    .SetBulge(6, 1 - Sqr(2))
                    .SetBulge(8, 1 - Sqr(2))
                    .SetBulge(13, 1 - Sqr(2))
                    .SetBulge(27, 1 - Sqr(2))
                    .SetBulge(29, 1 - Sqr(2))
                End If

                .Highlight(True)

            End With

            AutoTrim.Ent = MotorEnt
            AutoTrim.DoTrim
            MotorEnt.Delete









            Line1 = ThisDrawing.ModelSpace.AddLine(P2, P1)
                Line1.color = VbCopy(acCyan)
                Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P1, P7)
                Line2.color = VbCopy(acCyan)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P7, P8)
                Line3.color = VbCopy(acCyan)
                Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P4, P3)
                Line4.color = VbCopy(acCyan)
                Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P3, P9)
                Line5.color = VbCopy(acCyan)
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P9, P10)
                Line6.color = VbCopy(acCyan)
                Line6.Update
            Line7 = ThisDrawing.ModelSpace.AddLine(P6, P5)
                Line7.color = VbCopy(acCyan)
                Line7.Update
            Line8 = ThisDrawing.ModelSpace.AddLine(P5, P11)
                Line8.color = VbCopy(acCyan)
                Line8.Update

            Line9 = ThisDrawing.ModelSpace.AddLine(P11, P12)
                Line9.color = VbCopy(acCyan)
                Line9.Update
            Line10 = ThisDrawing.ModelSpace.AddLine(P13, P28)
                Line10.Update
            Line11 = ThisDrawing.ModelSpace.AddLine(P15, P26)
                Line11.Update
            Line12 = ThisDrawing.ModelSpace.AddLine(P15, P17)
                Line12.Update

            Line13 = ThisDrawing.ModelSpace.AddLine(P19, P20)
                Line13.Update
            Line14 = ThisDrawing.ModelSpace.AddLine(P22, P24)
                Line14.Update
            Line15 = ThisDrawing.ModelSpace.AddLine(P25, P26)
                Line15.Update
            Line16 = ThisDrawing.ModelSpace.AddLine(P16, P23)
                Line16.Update

            Line17 = ThisDrawing.ModelSpace.AddLine(P29, P30)
                Line17.Update
            Line18 = ThisDrawing.ModelSpace.AddLine(P29, P40)
                Line18.Update
            Line19 = ThisDrawing.ModelSpace.AddLine(P30, P31)
                Line19.Update
            Line20 = ThisDrawing.ModelSpace.AddLine(P39, P32)
                Line20.Update

            Line21 = ThisDrawing.ModelSpace.AddLine(P32, P33)
                Line21.Update
            Line22 = ThisDrawing.ModelSpace.AddLine(P35, P36)
                Line22.Update
            Line23 = ThisDrawing.ModelSpace.AddLine(P38, P39)
                Line23.Update

            If Mirror = False Then
                Arc1 = ThisDrawing.ModelSpace.AddArc(P14, R2, Dtr(RotAng + 90), Dtr(RotAng + 180))
                    Arc1.Update
                Arc2 = ThisDrawing.ModelSpace.AddArc(P27, R2, Dtr(RotAng + 0), Dtr(RotAng + 90))
                    Arc2.Update
                Arc3 = ThisDrawing.ModelSpace.AddArc(P18, R3, Dtr(RotAng + 180), Dtr(RotAng + 270))
                    Arc3.Update
                Arc4 = ThisDrawing.ModelSpace.AddArc(P21, R3, Dtr(RotAng + 270), Dtr(RotAng + 0))
                    Arc4.Update
                Arc5 = ThisDrawing.ModelSpace.AddArc(P34, R1, Dtr(RotAng + 0), Dtr(RotAng + 90))
                    Arc5.Update
                Arc6 = ThisDrawing.ModelSpace.AddArc(P37, R1, Dtr(RotAng + 270), Dtr(RotAng + 0))
                    Arc6.Update
                Else
                Arc1 = ThisDrawing.ModelSpace.AddArc(P14, R2, Dtr(RotAng + 0), Dtr(RotAng + 90))
                    Arc1.Update
                Arc2 = ThisDrawing.ModelSpace.AddArc(P27, R2, Dtr(RotAng + 90), Dtr(RotAng + 180))
                    Arc2.Update
                Arc3 = ThisDrawing.ModelSpace.AddArc(P18, R3, Dtr(RotAng + 270), Dtr(RotAng + 0))
                    Arc3.Update
                Arc4 = ThisDrawing.ModelSpace.AddArc(P21, R3, Dtr(RotAng + 180), Dtr(RotAng + 270))
                    Arc4.Update
                Arc5 = ThisDrawing.ModelSpace.AddArc(P34, R1, Dtr(RotAng + 90), Dtr(RotAng + 180))
                    Arc5.Update
                Arc6 = ThisDrawing.ModelSpace.AddArc(P37, R1, Dtr(RotAng + 180), Dtr(RotAng + 270))
                    Arc6.Update
            End If

            pCenP3 = PolarPoint(CP, Dtr(RotAng + 270), LB - (C + B / 2))



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
        Dim P21 As Object
        Dim P22 As Object
        Dim P23 As Object
        Dim P24 As Object
        Dim P25 As Object
        Dim P26 As Object
        Dim P27 As Object
        Dim P28 As Object
        Dim P29 As Object
        Dim P30 As Object
        Dim P31 As Object
        Dim P32 As Object
        Dim P33 As Object
        Dim P34 As Object
        Dim P35 As Object
        Dim P36 As Object
        Dim P37 As Object
        Dim P38 As Object
        Dim P39 As Object
        Dim P40 As Object
        Dim P41 As Object
        Dim P42 As Object
        Dim P43 As Object
        Dim P44 As Object
        Dim P45 As Object
        Dim P46 As Object
        Dim P47 As Object
        Dim P48 As Object
        Dim P49 As Object
        Dim P50 As Object
        Dim P51 As Object
        Dim P52 As Object
        Dim P53 As Object
        Dim P54 As Object
        Dim P55 As Object
        Dim cP1 As Object
        Dim cP2 As Object
        Dim cenP1 As Object
        Dim cenP2 As Object
        Dim cenP3 As Object
        Dim cenP4 As Object
        Dim R6 As Double
        Dim tmpPnt1 As Object
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
        Dim Line14 As Object
        Dim Line15 As Object
        Dim Line16 As Object
        Dim Line17 As Object
        Dim Line18 As Object
        Dim Line19 As Object
        Dim Line20 As Object
        Dim Line21 As Object
        Dim Line22 As Object
        Dim Line23 As Object
        Dim Line24 As Object
        Dim Line25 As Object
        Dim Line26 As Object
        Dim Line27 As Object
        Dim Line28 As Object
        Dim Line29 As Object
        Dim Line30 As Object
        Dim Line31 As Object
        Dim cenLine1 As Object
        Dim cenLine2 As Object
        Dim Arc1 As Object
        Dim Arc2 As Object
        Dim Arc3 As Object
        Dim Arc4 As Object
        Dim Arc5 As Object
        Dim Arc6 As Object
        Dim Arc7 As Object
        Dim Arc8 As Object

        pntCol = New VBCollection

        ReadData ' Motor Data 읽기


















        If Mirror = False Then
            eAng = 0
            WAng = 180

            Else
            eAng = 180
            WAng = 0

        End If


            cP1 = PolarPoint(CP, Dtr(RotAng + 90), H)
            cP2 = PolarPoint(cP1, Dtr(RotAng + eAng), B / 2 + C)

            P1 = PolarPoint(CP, Dtr(RotAng + WAng), (B - K) / 2)
            P2 = PolarPoint(P1, Dtr(RotAng + WAng), K)
            P3 = PolarPoint(P2, Dtr(RotAng + WAng), (BB - B - K) / 2)
            P4 = PolarPoint(P3, Dtr(RotAng + 90), HA / 2)

            P5 = PolarPoint(P4, Dtr(RotAng + 90), HA / 2)
            P6 = PolarPoint(P5, Dtr(RotAng + eAng), (BB - B - K) / 2)
            P7 = PolarPoint(P6, Dtr(RotAng + eAng), K)
            P8 = PolarPoint(P7, Dtr(RotAng + eAng), B - K)

            P9 = PolarPoint(P8, Dtr(RotAng + eAng), K)
            P10 = PolarPoint(P9, Dtr(RotAng + eAng), (BB - B - K) / 2)
            P11 = PolarPoint(P10, Dtr(RotAng + 270), HA / 2)
            P12 = PolarPoint(P11, Dtr(RotAng + 270), HA / 2)

            P13 = PolarPoint(P9, Dtr(RotAng + 270), HA)
            P14 = PolarPoint(P8, Dtr(RotAng + 270), HA)
            P15 = PolarPoint(P5, Dtr(RotAng + eAng), (BB - YF) / 2)
            P16 = PolarPoint(P15, Dtr(RotAng + 90), YE)

            P17 = PolarPoint(P16, Dtr(RotAng + eAng), YF)
            P18 = PolarPoint(P17, Dtr(RotAng + 270), YE)
            P19 = PolarPoint(P11, Dtr(RotAng + eAng), C - (BB - B) / 2 - R2 - 3 * YD)
            P20 = PolarPoint(P19, Dtr(RotAng + 90), R2)

            P21 = PolarPoint(P20, Dtr(RotAng + eAng), R2)

            P22 = PolarPoint(P21, Dtr(RotAng + 90), H - YK / 2 - HA / 2 - R2)
            P23 = PolarPoint(P22, Dtr(RotAng + eAng), YD)
            P24 = PolarPoint(P23, Dtr(RotAng + 90), (YK - YH) / 2)

            P25 = PolarPoint(P24, Dtr(RotAng + eAng), YD)
            P26 = PolarPoint(P25, Dtr(RotAng + 90), (YH - YG) / 2)
            P27 = PolarPoint(P26, Dtr(RotAng + eAng), YD)
            P28 = PolarPoint(P27, Dtr(RotAng + 90), YG)

            P29 = PolarPoint(P28, Dtr(RotAng + WAng), YD)
            P30 = PolarPoint(P29, Dtr(RotAng + 90), (YH - YG) / 2)
            P31 = PolarPoint(P30, Dtr(RotAng + WAng), YD)
            P32 = PolarPoint(P31, Dtr(RotAng + 90), (YK - YH) / 2)

            P33 = PolarPoint(P32, Dtr(RotAng + WAng), YD)
            P34 = PolarPoint(P33, Dtr(RotAng + 90), R5 - YK / 2 - R2)
            P35 = PolarPoint(P34, Dtr(RotAng + WAng), R2)
            P36 = PolarPoint(P35, Dtr(RotAng + 90), R2)

            P37 = PolarPoint(P36, Dtr(RotAng + WAng), YB)
            P38 = PolarPoint(P37, Dtr(RotAng + WAng), YA - R3)
            P39 = PolarPoint(P38, Dtr(RotAng + 270), R3)
            P40 = PolarPoint(P39, Dtr(RotAng + WAng), R3)
            P41 = PolarPoint(P40, Dtr(RotAng + 270), 2 * R4)
                R6 = H - R4 - HA / 2
            P42 = PolarPoint(P41, Dtr(RotAng + eAng), R6)
            P43 = PolarPoint(P42, Dtr(RotAng + 270), R6)
                    tmpPnt1 = PolarPoint(cP1, Dtr(RotAng + WAng), XN / 2)

            P44 = PolarPoint(tmpPnt1, Dtr(RotAng + 90), XL / 2 - R1)

            P45 = PolarPoint(P44, Dtr(RotAng + eAng), R1)
            P46 = PolarPoint(P45, Dtr(RotAng + 90), R1)
            P47 = PolarPoint(P46, Dtr(RotAng + eAng), XN - 2 * R1)
            P48 = PolarPoint(P47, Dtr(RotAng + 270), R1)

            P49 = PolarPoint(P48, Dtr(RotAng + eAng), R1)
            P50 = PolarPoint(P49, Dtr(RotAng + 270), XL - 2 * R1)
            P51 = PolarPoint(P50, Dtr(RotAng + WAng), R1)
            P52 = PolarPoint(P51, Dtr(RotAng + 270), R1)

            P53 = PolarPoint(P52, Dtr(RotAng + WAng), XN - 2 * R1)
            P54 = PolarPoint(P53, Dtr(RotAng + 90), R1)
            P55 = PolarPoint(P54, Dtr(RotAng + WAng), R1)

            cenP1 = PolarPoint(P6, Dtr(RotAng + eAng), K / 2)
            cenP1 = PolarPoint(cenP1, Dtr(RotAng + 90), K)
            cenP2 = PolarPoint(P2, Dtr(RotAng + eAng), K / 2)
            cenP2 = PolarPoint(cenP2, Dtr(RotAng + 270), K)
            cenP3 = PolarPoint(P8, Dtr(RotAng + eAng), K / 2)
            cenP3 = PolarPoint(cenP3, Dtr(RotAng + 90), K)
            cenP4 = PolarPoint(P14, Dtr(RotAng + eAng), K / 2)
            cenP4 = PolarPoint(cenP4, Dtr(RotAng + 270), K)


        If frmInput.optVbelt.Value = True Then ' 직결일 땐 Trim 안함

            pntCol.Add(P36)
            pntCol.Add(P38)
            pntCol.Add(P40)
            pntCol.Add(P41)
            pntCol.Add(P43)
            pntCol.Add(P4)
            pntCol.Add(P3)
            pntCol.Add(P12)
            pntCol.Add(P11)
            pntCol.Add(P19)
            pntCol.Add(P21)
            pntCol.Add(P22)
            pntCol.Add(P23)
            pntCol.Add(P24)
            pntCol.Add(P25)
            pntCol.Add(P26)
            pntCol.Add(P27)
            pntCol.Add(P28)
            pntCol.Add(P29)
            pntCol.Add(P30)
            pntCol.Add(P31)
            pntCol.Add(P32)
            pntCol.Add(P33)
            pntCol.Add(P34)

            MakePntArray

            MotorEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
            MotorEnt.Closed = True

            With MotorEnt
                .SetBulge(1, Sqr(2) - 1)
                .SetBulge(3, Sqr(2) - 1)
                .SetBulge(9, Sqr(2) - 1)
                .SetBulge(23, Sqr(2) - 1)
            End With

            MotorEnt.Update
            MotorEnt.Highlight(True)

            AutoTrim.Ent = MotorEnt
            AutoTrim.DoTrim
            MotorEnt.Delete

        End If ' 직결일 땐 Trim 안함













            Line1 = ThisDrawing.ModelSpace.AddLine(P3, P12)
            Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P12, P10)
            Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P5, P10)
            Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P3, P5)
            Line4.Update

            Line5 = ThisDrawing.ModelSpace.AddLine(P11, P19)
            Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P19, P36)
            Line6.Update
            Line7 = ThisDrawing.ModelSpace.AddLine(P21, P34)
            Line7.Update

            'Cyan 라인
            Line8 = ThisDrawing.ModelSpace.AddLine(P22, P23)
                Line8.color = VbCopy(acCyan)
                Line8.Update
            Line9 = ThisDrawing.ModelSpace.AddLine(P33, P32)
                Line9.color = VbCopy(acCyan)
                Line9.Update
            Line10 = ThisDrawing.ModelSpace.AddLine(P23, P32)
                Line10.color = VbCopy(acCyan)
                Line10.Update
            Line11 = ThisDrawing.ModelSpace.AddLine(P24, P25)
                Line11.color = VbCopy(acCyan)
                Line11.Update
            Line12 = ThisDrawing.ModelSpace.AddLine(P31, P30)
                Line12.color = VbCopy(acCyan)
                Line12.Update
            Line13 = ThisDrawing.ModelSpace.AddLine(P25, P30)
                Line13.color = VbCopy(acCyan)
                Line13.Update
            Line14 = ThisDrawing.ModelSpace.AddLine(P26, P27)
                Line14.color = VbCopy(acCyan)
                Line14.Update
            Line15 = ThisDrawing.ModelSpace.AddLine(P29, P28)
                Line15.color = VbCopy(acCyan)
                Line15.Update
            Line16 = ThisDrawing.ModelSpace.AddLine(P27, P28)
                Line16.color = VbCopy(acCyan)
                Line16.Update



            Line17 = ThisDrawing.ModelSpace.AddLine(P36, P38)
            Line17.Update
            Line18 = ThisDrawing.ModelSpace.AddLine(P40, P41)
            Line18.Update
            Line19 = ThisDrawing.ModelSpace.AddLine(P43, P4)
            Line19.Update
            Line20 = ThisDrawing.ModelSpace.AddLine(P5, P37)
            Line20.Update

            'Set Line21 = ThisDrawing.ModelSpace.AddLine(P15, P16)
            'Set Line22 = ThisDrawing.ModelSpace.AddLine(P18, P17)
            'Set Line23 = ThisDrawing.ModelSpace.AddLine(P16, P17)

        If Mirror = False Then
            Line24 = ThisDrawing.ModelSpace.AddLine(P55, P44)
            Line24.Update
            Line25 = ThisDrawing.ModelSpace.AddLine(P50, P49)
            Line25.Update
            Line26 = ThisDrawing.ModelSpace.AddLine(P46, P47)
            Line26.Update
            Line27 = ThisDrawing.ModelSpace.AddLine(P53, P52)
        End If

            ' Hidden Line
            Line28 = ThisDrawing.ModelSpace.AddLine(P2, P6)
                Line28.color = VbCopy(acGreen)
                Line28.Linetype = "Hidden"
                Line28.Update
            Line29 = ThisDrawing.ModelSpace.AddLine(P1, P7)
                Line29.color = VbCopy(acGreen)
                Line29.Linetype = "Hidden"
                Line29.Update
            Line30 = ThisDrawing.ModelSpace.AddLine(P14, P8)
                Line30.color = VbCopy(acGreen)
                Line30.Linetype = "Hidden"
                Line30.Update
            Line31 = ThisDrawing.ModelSpace.AddLine(P13, P9)
                Line31.color = VbCopy(acGreen)
                Line31.Linetype = "Hidden"
                Line31.Update

        If Mirror = False Then
            Arc1 = ThisDrawing.ModelSpace.AddArc(P35, R2, Dtr(RotAng + 0), Dtr(RotAng + 90))
            Else
            Arc1 = ThisDrawing.ModelSpace.AddArc(P35, R2, Dtr(RotAng + 90), Dtr(RotAng + 180))
        End If
            Line1.Update

        If Mirror = False Then
            Arc2 = ThisDrawing.ModelSpace.AddArc(P39, R3, Dtr(RotAng + 90), Dtr(RotAng + 180))
            Else
            Arc2 = ThisDrawing.ModelSpace.AddArc(P39, R3, Dtr(RotAng + 0), Dtr(RotAng + 90))
        End If
            Line2.Update

        If Mirror = False Then
            Arc3 = ThisDrawing.ModelSpace.AddArc(P42, R6, Dtr(RotAng + 180), Dtr(RotAng + 270))
            Else
            Arc3 = ThisDrawing.ModelSpace.AddArc(P42, R6, Dtr(RotAng + 270), Dtr(RotAng + 0))
        End If
            Line3.Update

        If Mirror = False Then
            Arc4 = ThisDrawing.ModelSpace.AddArc(P20, R2, Dtr(RotAng + 270), Dtr(RotAng + 0))
            Else
            Arc4 = ThisDrawing.ModelSpace.AddArc(P20, R2, Dtr(RotAng + 180), Dtr(RotAng + 270))
        End If
            Line4.Update

        If frmInput.optVbelt.Value = True Then
            Arc5 = ThisDrawing.ModelSpace.AddArc(P45, R1, Dtr(RotAng + 90), Dtr(RotAng + WAng))
            Line5.Update
            Arc6 = ThisDrawing.ModelSpace.AddArc(P54, R1, Dtr(RotAng + WAng), Dtr(RotAng + 270))
            Line6.Update
            Arc7 = ThisDrawing.ModelSpace.AddArc(P51, R1, Dtr(RotAng + 270), Dtr(RotAng + eAng))
            Line7.Update
            Arc8 = ThisDrawing.ModelSpace.AddArc(P48, R1, Dtr(RotAng + eAng), Dtr(RotAng + 90))
            Line8.Update

            If Right(Direction, 1) = "R" Then

                rCenP3 = PolarPoint(cP1, Dtr(RotAng + 180), LB - (C + B / 2))

            End If

        End If

        If frmInput.optDirect.Value Then
            rCenP2 = PolarPoint(cP1, Dtr(0), LB - (C + B / 2))
        End If

        cenLine1 = ThisDrawing.ModelSpace.AddLine(cenP1, cenP2)
            cenLine1.color = VbCopy(acRed)
            cenLine1.Linetype = "Center"
            cenLine1.Update
        cenLine2 = ThisDrawing.ModelSpace.AddLine(cenP3, cenP4)
            cenLine2.color = VbCopy(acRed)
            cenLine2.Linetype = "Center"
            cenLine2.Update



    End Sub

    Private Function Dtr(ByVal Degree As Double) As Double

        Dtr = 3.141592654 * Degree / 180

    End Function

    Public Sub ReadData()

        Select Case FrameNo
            Case "71"
                a = 112 : AA = 38 : AB = 148 : AC = 148 : AD = 145 : AE = 122 : B = 90 : BB = 114 : C = 45 : DS = 14
                H = 71 : HA = 4 : K = 7 : LB = 200 : XL = 104 : XN = 102
            Case "80"
                a = 125 : AA = 35 : AB = 150 : AC = 180 : AD = 135 : AE = 117 : B = 100 : BB = 125 : C = 50 : DS = 19
                H = 80 : HA = 8 : K = 10 : LB = 232 : XL = 104 : XN = 102
            Case "90L"
                a = 140 : AA = 38 : AB = 167 : AC = 199 : AD = 150 : AE = 128 : B = 125 : BB = 150 : C = 56 : DS = 24
                H = 90 : HA = 10 : K = 10 : LB = 282 : XL = 104 : XN = 102
            Case "100L"
                a = 160 : AA = 47 : AB = 196 : AC = 220 : AD = 180 : AE = 154 : B = 140 : BB = 174 : C = 63 : DS = 28
                H = 100 : HA = 12 : K = 12 : LB = 311 : XL = 104 : XN = 102
            Case "112M"
                a = 190 : AA = 41 : AB = 226 : AC = 244 : AD = 190 : AE = 165 : B = 140 : BB = 172 : C = 70 : DS = 28
                H = 112 : HA = 14 : K = 12 : LB = 313 : XL = 138 : XN = 124
            Case "132S"
                a = 216 : AA = 50 : AB = 264 : AC = 284 : AD = 213 : AE = 185 : B = 140 : BB = 178 : C = 89 : DS = 38
                H = 132 : HA = 16 : K = 12 : LB = 358 : XL = 138 : XN = 124
            Case "132M"
                a = 216 : AA = 50 : AB = 264 : AC = 284 : AD = 213 : AE = 185 : B = 178 : BB = 216 : C = 89 : DS = 38
                H = 132 : HA = 16 : K = 12 : LB = 396 : XL = 138 : XN = 124
            Case "160M"
                a = 254 : AA = 67 : AB = 314 : AC = 337 : AD = 261 : AE = 230 : B = 210 : BB = 260 : C = 108 : DS = 42
                H = 160 : HA = 19 : K = 15 : LB = 473 : XL = 165 : XN = 147
            Case "160L"
                a = 254 : AA = 67 : AB = 314 : AC = 337 : AD = 261 : AE = 230 : B = 254 : BB = 304 : C = 108 : DS = 42
                H = 160 : HA = 19 : K = 15 : LB = 517 : XL = 165 : XN = 147
            Case "180M"
                a = 279 : AA = 63 : AB = 338 : AC = 374 : AD = 288 : AE = 255 : B = 241 : BB = 300 : C = 121 : DS = 48
                H = 180 : HA = 20 : K = 15 : LB = 558 : XL = 165 : XN = 147
            Case "180L"
                a = 279 : AA = 63 : AB = 338 : AC = 374 : AD = 288 : AE = 255 : B = 279 : BB = 338 : C = 121 : DS = 55
                H = 180 : HA = 20 : K = 15 : LB = 596 : XL = 165 : XN = 147
            Case "200L"
                a = 318 : AA = 70 : AB = 382 : AC = 414 : AD = 317 : AE = 282 : B = 305 : BB = 370 : C = 133 : DS = 60
                H = 200 : HA = 22 : K = 19 : LB = 651 : XL = 187 : XN = 174
            Case "225S"
                a = 356 : AA = 79 : AB = 432 : AC = 465 : AD = 397 : AE = 334 : B = 286 : BB = 343 : C = 149 : DS = 60
                H = 225 : HA = 25 : K = 19 : LB = 677 : XL = 262 : XN = 202
            Case "225M"
                a = 356 : AA = 79 : AB = 432 : AC = 465 : AD = 397 : AE = 334 : B = 311 : BB = 368 : C = 149 : DS = 60
                H = 225 : HA = 25 : K = 19 : LB = 702 : XL = 262 : XN = 202
            Case "250S"
                a = 406 : AA = 86 : AB = 485 : AC = 529 : AD = 428 : AE = 362 : B = 311 : BB = 368 : C = 168 : DS = 75
                H = 250 : HA = 27 : K = 24 : LB = 736 : XL = 262 : XN = 202
            Case "250M"
                a = 406 : AA = 86 : AB = 485 : AC = 529 : AD = 428 : AE = 362 : B = 349 : BB = 406 : C = 168 : DS = 75
                H = 250 : HA = 27 : K = 24 : LB = 774 : XL = 262 : XN = 202
            Case "280S"
                a = 457 : AA = 89 : AB = 546 : AC = 602 : AD = 510 : AE = 430 : B = 368 : BB = 439 : C = 190 : DS = 85
                H = 280 : HA = 32 : K = 24 : LB = 874 : XL = 340 : XN = 308
            Case "280M"
                a = 457 : AA = 89 : AB = 546 : AC = 602 : AD = 510 : AE = 430 : B = 419 : BB = 490 : C = 190 : DS = 85
                H = 280 : HA = 32 : K = 24 : LB = 925 : XL = 340 : XN = 308
            Case "280L"
                a = 457 : AA = 89 : AB = 546 : AC = 602 : AD = 510 : AE = 430 : B = 508 : BB = 580 : C = 190 : DS = 95
                H = 280 : HA = 32 : K = 24 : LB = 1014 : XL = 304 : XN = 308
            Case "280LL"
                a = 457 : AA = 89 : AB = 546 : AC = 602 : AD = 510 : AE = 430 : B = 635 : BB = 708 : C = 190 : DS = 95
                H = 280 : HA = 32 : K = 24 : LB = 1141 : XL = 340 : XN = 308

        End Select

        R1 = 0.15 * XN
        R2 = C / 3
        R5 = AC / 2

        R3 = 0.3 * R5
        R4 = 0.7 * R5

        XO = 2 * (AD - AE)
        XP = (AD - XO) - Sqr(R5 ^ 2 - (0.4 * XN) ^ 2)
        YA = LB - (C + B + (BB - B) / 2)
        YD = C / 9
        YB = LB - (YA + R2 + 3 * YD)
        YE = VbCopy(AA)
        YF = 3 * AA

        YG = DS + 10
        YH = 0.8 * R5
        YK = 1.2 * R5
        YF = 0.5 * BB

    End Sub

    Sub MakePntArray()
        Dim i As Integer
        Dim pnt As Object

        ReDim pntArray(pntCol.Count * 3 - 1)

        For i = 1 To pntCol.Count

            pnt = pntCol.Item(i)

            pntArray(0 + (i - 1) * 3) = pnt(0)
            pntArray(1 + (i - 1) * 3) = pnt(1)
            pntArray(2 + (i - 1) * 3) = pnt(2)

        Next i

    End Sub


End Class
