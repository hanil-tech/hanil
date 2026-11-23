' 원본: ImpellerDraw.bas (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Module ImpellerDraw
    Dim Sc As Double
    Dim Height As Double

    Public Sub Draw_Impeller()
        Dim smyy As Double
        Dim beta0 As Double
        Dim CP(2) As Double
        Dim iFanBox As Object
        Dim P1 As Object
        Dim P2 As Object
        Dim P3 As Object
        Dim P4 As Object
        Dim P5 As Object
        Dim P6 As Object
        Dim P7 As Object
        Dim P8 As Object
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Arc1 As Object
        Dim Arc2 As Object
        Dim Arc3 As Object
        Dim tempCircle As Object
        Dim IntPnt As Object
        Dim P9(2) As Double
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim StartAngle As Double
        Dim EndAngle As Double
        Dim Arc4 As Object
        Dim P10 As Object
        Dim P11(2) As Double
        Dim Line6 As Object
        Dim Arc5 As Object
        Dim P12 As Object
        Dim P13 As Object
        Dim P14 As Object
        Dim mpT As Double
        Dim clH As Double
        Dim P15 As Object
        Dim P16 As Object
        Dim P17 As Object
        Dim P18 As Object
        Dim P19 As Object
        Dim P24 As Object
        Dim P23 As Object
        Dim P20 As Object
        Dim P21 As Object
        Dim P25 As Object
        Dim P22 As Object
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
        Dim dimGap As Double
        Dim Dim1 As Object
        Dim txtPos As Object
        Dim tempAng As Double
        Dim Dim2 As Object
        Dim Dim3 As Object
        Dim Dim4 As Object
        Dim dimGap1 As Double
        Dim Dim5 As Object
        Dim Dim6 As Object
        Dim Dim7 As Object
        Dim Dim8 As Object
        Dim tText As String
        Dim oldTstyle As Object
        Dim newTstyle As Object

        Load_LT

        If diaratio > 0.575 Then
                beta0 = Atn(vi / (u2 / 2))
                smyy = (D1 ^ 2 - (D2 / 2) ^ 2) / (4 * (D1 * Cos(beta1) - (D2 / 2) * Cos(beta0)))
        End If

       '----------------------------------------------------------------------------------------
        Sc = D2 / 0.1525
        Call SetACAD("FanDrawing", Sc)

        ThisDrawing.SendCommand("ucsicon off ")

        ' Fan Impeller 자동 작도
        CP(0) = 0 : CP(1) = 0 : CP(2) = 0

        '도면틀 삽입
        iFanBox = ThisDrawing.ModelSpace.InsertBlock(CP, SupportFolder() & "\Acad\iFanBox.dwg", Sc, Sc, 1#, 0)
        ThisDrawing.SendCommand("Explode (entlast)  ")
        ThisDrawing.Application.ZoomExtents

        '------------------------------ 평면도작성 시작 --------------------------------
            P1 = PolarPoint(CP, Dtr(180), 1000 * D2 / 2)
            P2 = PolarPoint(CP, Dtr(180), 1000 * D1 / 2)
            P3 = PolarPoint(CP, Dtr(180), 1000 * D2 / 4)
            P4 = PolarPoint(CP, Dtr(0), 1000 * D2 / 4)
            P5 = PolarPoint(CP, Dtr(0), 1000 * D1 / 2)
            P6 = PolarPoint(CP, Dtr(0), 1000 * D2 / 2)
            P7 = PolarPoint(CP, Dtr(90), 1000 * D2 / 2)
            P8 = PolarPoint(P7, Dtr(315), 1000 * myy)

            Line1 = ThisDrawing.ModelSpace.AddLine(P1, P6)
            Line1.color = VbCopy(acRed)
            Line1.Linetype = "Center"
            Line1.Update

        ThisDrawing.Regen(acActiveViewport)

            Line2 = ThisDrawing.ModelSpace.AddLine(CP, P7)
            Line2.color = VbCopy(acRed)
            Line2.Linetype = "Center"
            Line2.Update


            Arc2 = ThisDrawing.ModelSpace.AddArc(CP, 1000 * D1 / 2, Dtr(0), Dtr(180))
            Arc2.Update
            Arc3 = ThisDrawing.ModelSpace.AddArc(CP, 1000 * D2 / 2, Dtr(0), Dtr(180))
            Arc3.Update

            tempCircle = ThisDrawing.ModelSpace.AddCircle(P8, myy * 1000)

            IntPnt = Arc2.IntersectWith(tempCircle, acExtendNone)

            P9(0) = IntPnt(0)
            P9(1) = IntPnt(1)
            P9(2) = IntPnt(2)

            Line3 = ThisDrawing.ModelSpace.AddLine(P8, P7)
            Line3.color = VbCopy(acRed)
            Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P8, P9)
            Line4.color = VbCopy(acRed)
            Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P8, CP)
            Line5.color = VbCopy(acRed)
            Line5.Update
            StartAngle = VbCopy(Line3.Angle)
            EndAngle = VbCopy(Line4.Angle)

            Arc4 = ThisDrawing.ModelSpace.AddArc(P8, 1000 * myy, StartAngle, EndAngle)
            Arc4.Update
        tempCircle.Delete

        If diaratio > 0.575 Then '직경비가 0.575보다 클 때 보조날개작도
            Arc1 = ThisDrawing.ModelSpace.AddArc(CP, 1000 * D2 / 4, Dtr(0), Dtr(180))
            Arc1.color = VbCopy(acBlue)
            Arc1.Linetype = "Phantom"


                P10 = PolarPoint(P9, Line4.Angle + (Atn(1) * 4), 1000 * smyy)

            tempCircle = ThisDrawing.ModelSpace.AddCircle(P10, smyy * 1000)
                IntPnt = Arc1.IntersectWith(tempCircle, acExtendNone)
                P11(0) = IntPnt(0)
                P11(1) = IntPnt(1)
                P11(2) = IntPnt(2)
                Line6 = ThisDrawing.ModelSpace.AddLine(P10, P11)
                Line6.color = VbCopy(acRed)
                StartAngle = VbCopy(Line4.Angle)
                EndAngle = VbCopy(Line6.Angle)
                Line6.Update
                Arc5 = ThisDrawing.ModelSpace.AddArc(P10, smyy * 1000, StartAngle, EndAngle)
                Arc5.Update
            tempCircle.Delete

        End If

        '------------------------------ 평면도작성 끝 ---------------------------------


        '------------------------------ 정면도작성 시작 -------------------------------

            P12 = PolarPoint(CP, Dtr(270), D2 * 0.65 * 1000)
            P13 = PolarPoint(P12, Dtr(180), D2 / 2 * 1000)
            P14 = PolarPoint(P12, Dtr(0), D2 / 2 * 1000)

        mpT = D2 * 10
        clH = D2 ^ 0.5 * 30

            P15 = PolarPoint(P13, Dtr(90), mpT)

        If diaratio > 0.5 Then
                P16 = PolarPoint(P15, Dtr(0), D2 * 1000 / 4)
                P17 = PolarPoint(P16, Dtr(0), D2 * 1000 / 2)
                P18 = PolarPoint(P17, Dtr(0), D2 * 1000 / 4)
            Else
                P16 = PolarPoint(P15, Dtr(0), (D2 - D1) / 2 * 1000)
                P17 = PolarPoint(P16, Dtr(0), D1 * 1000)
                P18 = PolarPoint(P17, Dtr(0), (D2 - D1) / 2 * 1000)

        End If

            P19 = PolarPoint(P15, Dtr(90), b2 * 1000)
            P24 = PolarPoint(P12, Dtr(90), (b1 * 1000) + clH)
            P23 = PolarPoint(P24, Dtr(180), D1 / 2 * 1000)
            P20 = PolarPoint(P23, Dtr(270), clH)
            P21 = PolarPoint(P20, Dtr(0), D1 * 1000)
            P25 = PolarPoint(P24, Dtr(0), D1 / 2 * 1000)
            P22 = PolarPoint(P18, Dtr(90), b2 * 1000)

            Line7 = ThisDrawing.ModelSpace.AddLine(P13, P14)
            Line7.Update

            Line8 = ThisDrawing.ModelSpace.AddLine(P15, P18)
            Line8.Update

            Line9 = ThisDrawing.ModelSpace.AddLine(P13, P15)
            Line9.Update

            Line10 = ThisDrawing.ModelSpace.AddLine(P14, P18)
            Line10.Update

            Line11 = ThisDrawing.ModelSpace.AddLine(P15, P19)
            Line11.Update

            Line12 = ThisDrawing.ModelSpace.AddLine(P19, P20)
            Line12.Update

            Line13 = ThisDrawing.ModelSpace.AddLine(P20, P16)
            Line13.Update

            Line14 = ThisDrawing.ModelSpace.AddLine(P17, P21)
            Line14.Update

            Line15 = ThisDrawing.ModelSpace.AddLine(P21, P22)
            Line15.Update

            Line16 = ThisDrawing.ModelSpace.AddLine(P18, P22)
            Line16.Update

            Line17 = ThisDrawing.ModelSpace.AddLine(P20, P21)
            Line17.color = VbCopy(acCyan)
            Line17.Update

            Line18 = ThisDrawing.ModelSpace.AddLine(P20, P23)
            Line18.Update

            Line19 = ThisDrawing.ModelSpace.AddLine(P21, P25)
            Line19.Update

            Line20 = ThisDrawing.ModelSpace.AddLine(P23, P25)
            Line20.Update

            Line21 = ThisDrawing.ModelSpace.AddLine(P12, P24)
            Line21.color = VbCopy(acRed)
            Line21.Linetype = "Center"
            Line21.Update

        '-----------------------------------------------------------------------------------------
        ' 치수기입
        '-----------------------------------------------------------------------------------------
        dimGap = D2 * 60


        tempAng = Line3.Angle - (Atn(1) * 4) / 2
        txtPos = PolarPoint(P8, tempAng, dimGap)
        Dim1 = ThisDrawing.ModelSpace.AddDimAligned(P7, P8, txtPos)
        Dim1.TextOverride = "R<>"

        tempAng = Line5.Angle + (Atn(1) * 4) / 2
        txtPos = PolarPoint(P8, tempAng, dimGap)
        Dim2 = ThisDrawing.ModelSpace.AddDimAligned(CP, P8, txtPos)
        Dim2.TextOverride = "R<>"

        If diaratio > 0.575 Then
            tempAng = Line6.Angle + (Atn(1) * 4) / 2
            txtPos = PolarPoint(P10, tempAng, dimGap)
            Dim3 = ThisDrawing.ModelSpace.AddDimAligned(P11, P10, txtPos)
            Dim3.TextOverride = "R<>"
        End If

        If diaratio > 0.5 Then
            dimGap1 = dimGap * 2
            Else
            dimGap1 = VbCopy(dimGap)
        End If
        txtPos = PolarPoint(P12, Dtr(270), dimGap1)
        Dim4 = ThisDrawing.ModelSpace.AddDimRotated(P13, P14, txtPos, 0)
        Dim4.TextOverride = "%%c<>"

        txtPos = PolarPoint(P24, Dtr(90), dimGap)
        Dim5 = ThisDrawing.ModelSpace.AddDimRotated(P23, P25, txtPos, 0)
        Dim5.TextOverride = "%%c<>"

        tempAng = Line16.Angle - (Atn(1) * 4) / 2
        txtPos = PolarPoint(P18, tempAng, dimGap)
        Dim6 = ThisDrawing.ModelSpace.AddDimAligned(P18, P22, txtPos)

        txtPos = PolarPoint(P17, Dtr(180), dimGap)
        Dim7 = ThisDrawing.ModelSpace.AddDimRotated(P17, P21, txtPos, (Atn(1) * 4) / 2)

        If diaratio > 0.5 Then
            txtPos = PolarPoint(P12, Dtr(270), dimGap)
            Dim8 = ThisDrawing.ModelSpace.AddDimRotated(P16, P17, txtPos, 0)
            Dim8.TextOverride = "%%c<>"
        End If

        ThisDrawing.SendCommand("dim up all  e ")

        '---------------------------------------------------------------------------------------
        ' 도면에 Text 기입하기
        '---------------------------------------------------------------------------------------

        ThisDrawing.ActiveTextStyle = ThisDrawing.TextStyles("Standard")

        Height = 2 * Sc

        PutText(Str(q), 195, 26) '풍량
        PutText(Str(ps), 195, 20) ' 풍압
        PutText(Format(Str(N), "0"), 195, 14) ' 송풍기 회전수
        PutText(Str(temp), 195, 8) ' 온도
        If frmInput.optVbelt.Value Then
            PutText(Str(motorPulley), 195, 2) ' 모터풀리
            PutText(Str(fanPulley), 195, -4) ' Fan풀리
                tText = VbeltType + "-" + Str(PCS) + " pcs"
            PutText(tText, 195, -10) ' 벨트타입/가닥수

            Else
            PutText("-", 195, 2) ' 모터풀리
            PutText("-", 195, -4) ' Fan풀리
            PutText("-", 195, -10) ' 벨트타입/가닥수
        End If

            oldTstyle = ThisDrawing.ActiveTextStyle
            newTstyle = ThisDrawing.TextStyles.Add("한글")
            newTstyle.fontFile = "C:\Windows\Fonts\malgunsl.ttf"
            newTstyle.SetFont("맑은 고딕 Semilight", False, False, 129, 50)

        ThisDrawing.ActiveTextStyle = VbCopy(newTstyle)
        PutText((frmOutput.txtMMaker.Text), 255, 26) ' 모터 메이커
        ThisDrawing.ActiveTextStyle = VbCopy(oldTstyle)
        PutText((frmOutput.txtMType.Text), 255, 20) ' 모터 타입
        PutText(Str(motorcapa), 255, 14) ' 모터 출력
        PutText(Str(motorrpm), 255, 8) ' 모터 회전수
            tText = Str(motorpoles) + "P/" + frmOutput.txtMFrequency.Text
        PutText(tText, 255, 2) ' 극수/주파수
        PutText("3%%c", 255, -4) ' 상수
            tText = Str(motorvoltage) + "V/" + Format(Str(motorloadamp), "0.0") + "A"
        PutText(tText, 255, -10) ' 전압/전류

        ' 회전차 번호
        tText = "#" + Format(D2 / 0.1524, "0.0#")
        PutText(tText, 245, -38)

        ' Tip Speed
        tText = Format(Str(D2 * (Atn(1) * 4) * N / 60), "0.0")
        PutText(tText, 245, -44)

        ' 주판응력
        PutText(Format(mStress, "####"), 245, -50)

        ' 날개응력
        PutText(Format(bladeStress, "####"), 245, -56)

        ' 날개수삽입
        PutText((frmInput.txtBladeNo.Text), 245, -62)

        ' 날개두께삽입
        PutText((frmInput.txtBladeThickness.Text), 245, -68)

        ' 재질삽입
        PutText((frmOutput.txtImpMatl.Text), 245, -74)

        ThisDrawing.ActiveTextStyle = VbCopy(newTstyle)
        Height = 3.2 * Sc
        PutText((frmOutput.txtCustomer.Text), 246.0961, -124.2559) ' 고객명

        ThisDrawing.ActiveTextStyle = VbCopy(oldTstyle)
        Height = 2 * Sc
        PutText(Format(DateTime.Today, "YYYY. M. D."), 189.7375, -137.04) ' 설계일자

        ' 작도 완료 후 전체보기
        ThisDrawing.Regen(acActiveViewport)
        ThisDrawing.Utility.Prompt("")
        ThisDrawing.Application.Update
        ThisDrawing.Utility.Prompt("Auto Drawing Completed!!!")
        VariablesSetting
        ThisDrawing.Application.Update

    End Sub

    Private Sub PutText(ByRef text As String, ByVal X As Double, ByVal Y As Double)
        Dim textObj As Object
        Dim insertionPoint(2) As Double
        Dim alignmentPoint(2) As Double
        Dim xCood As Double
        Dim yCood As Double

            xCood = X * Sc
            yCood = Y * Sc

            insertionPoint(0) = VbCopy(xCood)
            insertionPoint(1) = VbCopy(yCood)
            insertionPoint(2) = 0
            If text = "" Then text = "-"

            textObj = ThisDrawing.ModelSpace.AddText(text, insertionPoint, Height)

            textObj.Alignment = VbCopy(acAlignmentMiddle)
            alignmentPoint(0) = VbCopy(xCood)
            alignmentPoint(1) = VbCopy(yCood)
            alignmentPoint(2) = 0
            textObj.Alignment = VbCopy(acAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.color = VbCopy(acYellow)
            textObj.Update

    End Sub


End Module
