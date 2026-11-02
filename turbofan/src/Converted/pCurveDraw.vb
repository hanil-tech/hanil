' 원본: pCurveDraw.bas (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Module pCurveDraw

    Public Sub Performance() ' Acad에서 성능곡선작성 루틴
        Dim volume(16) As Double
        Dim vol As Double
        Dim i As Integer
        Dim dpthin(16) As Double
        Dim epsilon(16) As Double
        Dim dpth(16) As Double
        Dim dp_entry(16) As Double
        Dim dp_retardation(16) As Double
        Dim dp_friction(16) As Double
        Dim dp_shock(16) As Double
        Dim dp(16) As Double
        Dim c1m(16) As Double
        Dim c2m(16) As Double
        Dim w1(16) As Double
        Dim w2(16) As Double
        Dim nux(16) As Double
        Dim blength As Double
        Dim bm As Double
        Dim betam As Double
        Dim oldTstyle As Object
        Dim newTstyle As Object
        Dim ratio As Object
        Dim insp(2) As Double
        Dim blockname As String
        Dim PerGraph As Object
        Dim myPnt As Object
        Dim pnt(50) As Double
        Dim startTan(2) As Double
        Dim endTan(2) As Double
        Dim plineObj As Object
        Dim tempLine As Object
        Dim Sp(2) As Double
        Dim Ep(2) As Double
        Dim RotAng As Double
        Dim TextString As String
        Dim insertPoint As Object
        Dim Height As Double
        Dim textObj As Object
        Dim UnitScale As Double
        Dim LPnt(8) As Double
        Dim powerLine As Object
        Dim tempLine1 As Object
        Dim tempLine2 As Object
        Dim tempPnt1(2) As Double
        Dim tempPnt2(2) As Double
        Dim tempPnt3(2) As Double
        Dim tempPnt4(2) As Double
        Dim powerIntPnt1 As Object
        Dim powerIntPnt2 As Object
        Dim spower60 As Double
        Dim spower140 As Double
        Dim MP(2) As Double
        Dim Eff(11) As Double
        Dim EffLine As Object
        Dim capatext As Object
        Dim capaPos(2) As Object
        Dim scapstring As String
        Dim insertionPoint(2) As Double
        Dim alignmentPoint(2) As Double
        Dim K As Integer
        Dim L As Integer
        Dim M As Integer
        Dim NN As Integer
        Dim ipx As Double
        Dim ipy As Double

        Call SetACAD("Performance", 1)

        vol = q / 60





        oldTstyle = ThisDrawing.ActiveTextStyle
        newTstyle = ThisDrawing.TextStyles.Add("한글")
        newTstyle.fontFile = "C:\Windows\Fonts\malgunsl.ttf"
        newTstyle.SetFont("맑은 고딕 Semilight", False, False, 129, 50)

        ThisDrawing.ActiveTextStyle = VbCopy(newTstyle)

        betam = (beta1 + Dtr(45)) / 2
        blength = (D2 - D1) / (2 * Sin(betam))
        bm = (b1 + D2) / 2

        For i = 0 To 16

            volume(i) = vol * i / 10
            dpthin(i) = gamma * u2 ^ 2 / 9.8 - volume(i) * gamma / (2 * 9.8) * u2 / ((Atn(1) * 4) * D2 * b2 * Tan(Dtr(45)))

            epsilon(i) = 1 - u2 * (Atn(1) * 4) * Sin(Dtr(45)) / (Z * (u2 - volume(i) / ((Atn(1) * 4) * D2 * b2 * Tan(Dtr(45)))))

            dpth(i) = dpthin(i) * epsilon(i)

            c2m(i) = volume(i) / ((Atn(1) * 4) * D2 * b2)
            c1m(i) = volume(i) / ((Atn(1) * 4) * D1 * b1)

            w1(i) = Sqr(u1 ^ 2 + c1m(i) ^ 2)
            w2(i) = c2m(i) / Sin(Dtr(45))
            nux(i) = w2(i) / w1(i)

            dp_entry(i) = 0.25 * gamma / (2 * 9.8) * c1m(i) ^ 2

            dp_retardation(i) = 0.2 * gamma * u2 ^ 2 / (2 * 9.8) * (D1 / D2) ^ 2 * ((1 - nux(i) ^ 2) / (Cos(beta1)) ^ 2)

            dp_friction(i) = 0.009 * gamma * u2 ^ 2 / (2 * 9.8) * 2 * (D1 / D2) ^ 2 * ((1 + nux(i)) / 2) ^ 2 * (Z * blength * bm / (D1 * b1) + (Atn(1) * 4) * D2 ^ 2 / (4 * D1 * b1) * (1 - (D1 / D2) ^ 2)) / ((Atn(1) * 4) * Sin(beta1) * (Cos(beta1)) ^ 2)

            dp_shock(i) = 0.9 * gamma * u2 ^ 2 / (2 * 9.8) * (D1 / D2) ^ 2 * (volume(i) / vol - 1) ^ 2

            dp(i) = dpth(i) - dp_entry(i) - dp_retardation(i) - dp_friction(i) - dp_shock(i)

        Next i


            ratio = pt / dp(10)

        For i = 0 To 16

            dp(i) = dp(i) * ratio

        Next i

        ' Pertable block 삽입(그래프블록삽입)
            blockname = SupportRoot() & "\ALISP\Turbo Fan Design\Acad\pertable.dwg"
            insp(0) = 0 : insp(1) = 0 : insp(2) = 0

        PerGraph = ThisDrawing.ModelSpace.InsertBlock(insp, blockname, 1#, 1#, 1#, 0)
        ThisDrawing.SendCommand("explode (entlast)  ")
        ThisDrawing.Application.ZoomExtents
        ThisDrawing.Regen(acActiveViewport)

        ' 압력선도 작성

            '시작점과 끝점의 접선각 설정
            startTan(0) = 0
            startTan(1) = 0
            startTan(2) = 0

            endTan(0) = 0
            endTan(1) = 0
            endTan(2) = 0

        For i = 0 To 16
            pnt(i * 3) = volume(i) * 60 * 90 / q
            pnt(i * 3 + 1) = dp(i) * 90 / pt + 9
            pnt(i * 3 + 2) = 0
        Next i

        plineObj = ThisDrawing.ModelSpace.AddSpline(pnt, startTan, endTan)
        plineObj.color = VbCopy(acMagenta)
        plineObj.Update

        'Static Pressure 글씨쓰기
                Sp(0) = pnt(42) : Sp(1) = pnt(43) : Sp(2) = pnt(44)
                Ep(0) = pnt(45) : Ep(1) = pnt(46) : Ep(2) = pnt(47)

            tempLine = ThisDrawing.ModelSpace.AddLine(Sp, Ep)

            RotAng = VbCopy(tempLine.Angle)

            TextString = "Static Pressure"

            insertPoint = PolarPoint(Sp, RotAng + (Atn(1) * 4) / 2, 5#)
            Height = 3.2
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertPoint, Height)
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(insertPoint)
            textObj.Rotate(insertPoint, RotAng)
            tempLine.Delete
            textObj.Update

    '축동력 곡선 계산

        '축동력곡선 Scale 메기기

        Select Case spower

            Case Is < 0.2
                UnitScale = 0.04
            Case 0.2 To 0.5
                UnitScale = 0.1
            Case 0.5 To 1
                UnitScale = 0.2

            Case 1 To 1.5
                UnitScale = 0.3
            Case 1.5 To 2
                UnitScale = 0.4
            Case 2 To 2.5
                UnitScale = 0.5
            Case 2.5 To 3.5
                UnitScale = 0.7
            Case 3.5 To 5
                UnitScale = 1
            Case 5 To 7
                UnitScale = 1.2
            Case 7 To 10
                UnitScale = 2

            Case 10 To 15
                UnitScale = 3
            Case 15 To 20
                UnitScale = 4
            Case 20 To 25
                UnitScale = 5
            Case 25 To 35
                UnitScale = 7
            Case 35 To 50
                UnitScale = 10
            Case 50 To 70
                UnitScale = 14
            Case 70 To 100
                UnitScale = 20
            Case Else
                UnitScale = 25
        End Select


        '축동력 선도용 Point계산하여 축동력 선도 작도
        LPnt(0) = 0
        LPnt(1) = spower * 0.55 * 9 / UnitScale
        LPnt(2) = 0

        LPnt(3) = volume(10) * 60 * 90 / q
        LPnt(4) = spower * 9 / UnitScale
        LPnt(5) = 0

        LPnt(6) = volume(16) * 60 * 90 / q
        LPnt(7) = spower * 1.08 * 9 / UnitScale
        LPnt(8) = 0

        powerLine = ThisDrawing.ModelSpace.AddSpline(LPnt, startTan, endTan)
        powerLine.color = VbCopy(acMagenta)
        powerLine.Update

        '풍량의 60% 및 140% 지점에서의 축동력 값 읽어오기

            '임의의 라인생성

            tempPnt1(0) = volume(6) * 60 * 90 / q
            tempPnt1(1) = 0
            tempPnt1(2) = 0
            tempPnt2(0) = volume(6) * 60 * 90 / q
            tempPnt2(1) = 100
            tempPnt2(2) = 0

            tempPnt3(0) = volume(14) * 60 * 90 / q
            tempPnt3(1) = 0
            tempPnt3(2) = 0
            tempPnt4(0) = volume(14) * 60 * 90 / q
            tempPnt4(1) = 100
            tempPnt4(2) = 0

            tempLine1 = ThisDrawing.ModelSpace.AddLine(tempPnt1, tempPnt2)
            tempLine2 = ThisDrawing.ModelSpace.AddLine(tempPnt3, tempPnt4)

            powerIntPnt1 = powerLine.IntersectWith(tempLine1, acExtendNone) '교점구하기

            powerIntPnt2 = powerLine.IntersectWith(tempLine2, acExtendNone) '교점구하기

            tempLine1.Delete '임시선 지우기
            tempLine2.Delete '임시선지우기


            spower60 = powerIntPnt1(1) * UnitScale / 9
            spower140 = powerIntPnt2(1) * UnitScale / 9

            'Shaft Power 글씨쓰기
                Sp(0) = LPnt(3) : Sp(1) = LPnt(4) : Sp(2) = LPnt(5)
                Ep(0) = LPnt(6) : Ep(1) = LPnt(7) : Ep(2) = LPnt(8)

                MP(0) = (Sp(0) + Ep(0)) / 2
                MP(1) = (Sp(1) + Ep(1)) / 2
                MP(2) = 0

            tempLine = ThisDrawing.ModelSpace.AddLine(Sp, Ep)

            RotAng = VbCopy(tempLine.Angle)

            TextString = "Shaft Power"

            insertPoint = PolarPoint(MP, RotAng + (Atn(1) * 4) / 2, 5#)
            Height = 3.2
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertPoint, Height)
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(insertPoint)
            textObj.Rotate(insertPoint, RotAng)
            tempLine.Delete
            textObj.Update


            '효율곡선 작도


            Eff(0) = 0
            Eff(1) = 0
            Eff(2) = 0

            Eff(3) = volume(6) * 60 * 90 / q
            Eff(4) = dp(6) * volume(6) * 60 / (6120 * spower60) * 90
            Eff(5) = 0

            Eff(6) = 90
            Eff(7) = FanEff * 90
            Eff(8) = 0

            Eff(9) = volume(16) * 60 * 90 / q
            Eff(10) = dp(16) * volume(16) * 60 / (6120 * spower * 1.08) * 90
            Eff(11) = 0

            EffLine = ThisDrawing.ModelSpace.AddSpline(Eff, startTan, endTan)
            EffLine.color = VbCopy(acMagenta)
            EffLine.Update

            'Fan Efficiency 글씨쓰기
            Sp(0) = 0 : Sp(1) = 0 : Sp(2) = 0
            Ep(0) = Eff(3) : Ep(1) = Eff(4) : Ep(2) = Eff(5)
            tempLine = ThisDrawing.ModelSpace.AddLine(Sp, Ep)
            RotAng = VbCopy(tempLine.Angle)
            TextString = "Fan Efficiency"
            insertPoint = PolarPoint(Ep, RotAng + (Atn(1) * 4) / 2, 5#)
            Height = 3.2

            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertPoint, Height)
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(insertPoint)
            textObj.Rotate(insertPoint, RotAng)
            tempLine.Delete
            textObj.Update

        ' 도면내에 글자쓰기


        ThisDrawing.SetVariable("osmode", 0)

        For K = 0 To 8
            TextString = Str(K * q / 5) '풍량값 눈금
            insertionPoint(0) = K * 18 : insertionPoint(1) = -3 : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            textObj.Alignment = VbCopy(acAlignmentMiddle)
            alignmentPoint(0) = K * 18 : alignmentPoint(1) = -3 : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update
        Next K

        For L = 2 To 13
            TextString = Str((L - 1) * ps / 10) '풍압값 눈금
            insertionPoint(0) = -28 : insertionPoint(1) = L * 9 : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            textObj.Alignment = VbCopy(acAlignmentMiddle)
            alignmentPoint(0) = -28 : alignmentPoint(1) = L * 9 : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update
        Next L

        '효율값 스캐일(눈금값)
        For M = 1 To 8
            TextString = Str(M * 10)
            insertionPoint(0) = -16 : insertionPoint(1) = M * 9 : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            textObj.Alignment = VbCopy(acAlignmentMiddle)
            alignmentPoint(0) = -16 : alignmentPoint(1) = M * 9 : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update
        Next M

        '동력값 스캐일(눈금값)
        For NN = 1 To 5
            TextString = Str(NN * UnitScale)
            insertionPoint(0) = -4 : insertionPoint(1) = NN * 9 : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            textObj.Alignment = VbCopy(acAlignmentMiddle)
            alignmentPoint(0) = -4 : alignmentPoint(1) = NN * 9 : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update
        Next NN


        '삽입점 선언


        ' 날짜 삽입
        TextString = Format(DateTime.Today, "YYYY년 M월 D일")
            ipx = 203 : ipy = 156
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 풍량 삽입
        TextString = VbCopy(q)
            ipx = 201 : ipy = 128
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 풍압 삽입
        TextString = VbCopy(ps)
            ipx = 201 : ipy = 118
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 회전수 삽입
        TextString = Format(N, "####")
            ipx = 201 : ipy = 108
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 모터출력 삽입
        TextString = VbCopy(motoroutput)
            ipx = 201 : ipy = 98
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 모터주파수 삽입
        TextString = "60"
            ipx = 201 : ipy = 88
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 모터극수 삽입
        TextString = "4"
            ipx = 201 : ipy = 78
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 온도 삽입
        TextString = VbCopy(temp)
            ipx = 185 : ipy = 48
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 밀도 삽입
        TextString = Format(gamma, "0.000")
            ipx = 208 : ipy = 48
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 2.5
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 주문자명 삽입
        If frmOutput.txtCustomer.text <> "" Then

        TextString = frmOutput.txtCustomer.text
            ipx = 3# : ipy = 142.5
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 3#
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update
        End If

        ' 송풍기 규격 및 형식 삽입
        TextString = "#" & D2no & "  Turbo Fan"
            ipx = 70 : ipy = 142.5
            insertionPoint(0) = VbCopy(ipx) : insertionPoint(1) = VbCopy(ipy) : insertionPoint(2) = 0
            Height = 3.2
            textObj = ThisDrawing.ModelSpace.AddText(TextString, insertionPoint, Height)
            alignmentPoint(0) = VbCopy(ipx) : alignmentPoint(1) = VbCopy(ipy) : alignmentPoint(2) = 0
            textObj.HorizontalAlignment = VbCopy(acHorizontalAlignmentMiddle)
            textObj.TextAlignmentPoint = VbCopy(alignmentPoint)
            textObj.Update

        ' 작도 완료 후 전체보기
        ThisDrawing.Regen(acActiveViewport)
        ThisDrawing.Utility.Prompt("")
        ThisDrawing.Application.Update
        ThisDrawing.Utility.Prompt("Auto Drawing Completed!!!")
        ThisDrawing.Application.Update

    End Sub


End Module
