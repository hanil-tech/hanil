Attribute VB_Name = "ImpellerDraw"
Option Explicit
Dim Sc As Double
Dim Height As Double

Public Sub Draw_Impeller()
    
    Load_LT
    
    If diaratio > 0.575 Then
        Dim smyy As Double
        Dim beta0 As Double
            beta0 = Atn(vi / (u2 / 2))
            smyy = (D1 ^ 2 - (D2 / 2) ^ 2) / (4 * (D1 * Cos(beta1) - (D2 / 2) * Cos(beta0)))
    End If
    
   '----------------------------------------------------------------------------------------
    Sc = D2 / 0.1525
    Call SetACAD("FanDrawing", Sc)
    
    ThisDrawing.SendCommand "ucsicon off "
    
    ' Fan Impeller 자동 작도
    Dim CP(0 To 2) As Double
    CP(0) = 0: CP(1) = 0: CP(2) = 0
    
    '도면틀 삽입
    Dim iFanBox As AcadBlockReference
    Set iFanBox = ThisDrawing.ModelSpace.InsertBlock(CP, ThisDrawing.Application.Path & "\ALISP\Turbo Fan Design\Acad\iFanBox.dwg", Sc, Sc, 1#, 0)
    ThisDrawing.SendCommand "Explode (entlast)  "
    ThisDrawing.Application.ZoomExtents
    
    '------------------------------ 평면도작성 시작 --------------------------------
    Dim P1 As Variant
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180), 1000 * D2 / 2)
    Dim P2 As Variant
        P2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180), 1000 * D1 / 2)
    Dim P3 As Variant
        P3 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180), 1000 * D2 / 4)
    Dim P4 As Variant
        P4 = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), 1000 * D2 / 4)
    Dim P5 As Variant
        P5 = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), 1000 * D1 / 2)
    Dim P6 As Variant
        P6 = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), 1000 * D2 / 2)
    Dim P7 As Variant
        P7 = ThisDrawing.Utility.PolarPoint(CP, Dtr(90), 1000 * D2 / 2)
    Dim P8 As Variant
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(315), 1000 * myy)
    
    Dim Line1 As AcadLine
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P1, P6)
        Line1.color = acRed
        Line1.Linetype = "Center"
        Line1.Update
        
    ThisDrawing.Regen acActiveViewport
    
    Dim Line2 As AcadLine
        Set Line2 = ThisDrawing.ModelSpace.AddLine(CP, P7)
        Line2.color = acRed
        Line2.Linetype = "Center"
        Line2.Update
    
    Dim Arc1 As AcadArc
        
    Dim Arc2 As AcadArc
        Set Arc2 = ThisDrawing.ModelSpace.AddArc(CP, 1000 * D1 / 2, Dtr(0), Dtr(180))
        Arc2.Update
    Dim Arc3 As AcadArc
        Set Arc3 = ThisDrawing.ModelSpace.AddArc(CP, 1000 * D2 / 2, Dtr(0), Dtr(180))
        Arc3.Update
    
    Dim tempCircle As AcadCircle
        Set tempCircle = ThisDrawing.ModelSpace.AddCircle(P8, myy * 1000)
    
    Dim IntPnt As Variant
        IntPnt = Arc2.IntersectWith(tempCircle, acExtendNone)
        
    Dim P9(0 To 2) As Double
        P9(0) = IntPnt(0)
        P9(1) = IntPnt(1)
        P9(2) = IntPnt(2)
    
    Dim Line3 As AcadLine
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P8, P7)
        Line3.color = acRed
        Line3.Update
    Dim Line4 As AcadLine
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P8, P9)
        Line4.color = acRed
        Line4.Update
    Dim Line5 As AcadLine
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P8, CP)
        Line5.color = acRed
        Line5.Update
    Dim StartAngle As Double
        StartAngle = Line3.Angle
    Dim EndAngle As Double
        EndAngle = Line4.Angle
    
    Dim Arc4 As AcadArc
        Set Arc4 = ThisDrawing.ModelSpace.AddArc(P8, 1000 * myy, StartAngle, EndAngle)
        Arc4.Update
    tempCircle.Delete
    
    If diaratio > 0.575 Then '직경비가 0.575보다 클 때 보조날개작도
        Set Arc1 = ThisDrawing.ModelSpace.AddArc(CP, 1000 * D2 / 4, Dtr(0), Dtr(180))
        Arc1.color = acBlue
        Arc1.Linetype = "Phantom"
        
        Dim P10 As Variant
            
            P10 = ThisDrawing.Utility.PolarPoint(P9, Line4.Angle + (Atn(1) * 4), 1000 * smyy)
            
        Set tempCircle = ThisDrawing.ModelSpace.AddCircle(P10, smyy * 1000)
            IntPnt = Arc1.IntersectWith(tempCircle, acExtendNone)
        Dim P11(0 To 2) As Double
            P11(0) = IntPnt(0)
            P11(1) = IntPnt(1)
            P11(2) = IntPnt(2)
        Dim Line6 As AcadLine
            Set Line6 = ThisDrawing.ModelSpace.AddLine(P10, P11)
            Line6.color = acRed
            StartAngle = Line4.Angle
            EndAngle = Line6.Angle
            Line6.Update
        Dim Arc5 As AcadArc
            Set Arc5 = ThisDrawing.ModelSpace.AddArc(P10, smyy * 1000, StartAngle, EndAngle)
            Arc5.Update
        tempCircle.Delete
        
    End If
    
    '------------------------------ 평면도작성 끝 ---------------------------------
    
    
    '------------------------------ 정면도작성 시작 -------------------------------
    
    Dim P12 As Variant
        P12 = ThisDrawing.Utility.PolarPoint(CP, Dtr(270), D2 * 0.65 * 1000)
    Dim P13 As Variant
        P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(180), D2 / 2 * 1000)
    Dim P14 As Variant
        P14 = ThisDrawing.Utility.PolarPoint(P12, Dtr(0), D2 / 2 * 1000)
    
    Dim mpT As Double
    Dim clH As Double
    mpT = D2 * 10
    clH = D2 ^ 0.5 * 30
    
    Dim P15 As Variant
        P15 = ThisDrawing.Utility.PolarPoint(P13, Dtr(90), mpT)
    
    Dim P16 As Variant
    Dim P17 As Variant
    Dim P18 As Variant
    If diaratio > 0.5 Then
            P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(0), D2 * 1000 / 4)
            P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(0), D2 * 1000 / 2)
            P18 = ThisDrawing.Utility.PolarPoint(P17, Dtr(0), D2 * 1000 / 4)
        Else
            P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(0), (D2 - D1) / 2 * 1000)
            P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(0), D1 * 1000)
            P18 = ThisDrawing.Utility.PolarPoint(P17, Dtr(0), (D2 - D1) / 2 * 1000)
    
    End If
        
    Dim P19 As Variant
        P19 = ThisDrawing.Utility.PolarPoint(P15, Dtr(90), b2 * 1000)
    Dim P24 As Variant
        P24 = ThisDrawing.Utility.PolarPoint(P12, Dtr(90), (b1 * 1000) + clH)
    Dim P23 As Variant
        P23 = ThisDrawing.Utility.PolarPoint(P24, Dtr(180), D1 / 2 * 1000)
    Dim P20 As Variant
        P20 = ThisDrawing.Utility.PolarPoint(P23, Dtr(270), clH)
    Dim P21 As Variant
        P21 = ThisDrawing.Utility.PolarPoint(P20, Dtr(0), D1 * 1000)
    Dim P25 As Variant
        P25 = ThisDrawing.Utility.PolarPoint(P24, Dtr(0), D1 / 2 * 1000)
    Dim P22 As Variant
        P22 = ThisDrawing.Utility.PolarPoint(P18, Dtr(90), b2 * 1000)
    
    Dim Line7 As AcadLine
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P13, P14)
        Line7.Update
        
    Dim Line8 As AcadLine
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P15, P18)
        Line8.Update
        
    Dim Line9 As AcadLine
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P13, P15)
        Line9.Update
        
    Dim Line10 As AcadLine
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P14, P18)
        Line10.Update
        
    Dim Line11 As AcadLine
        Set Line11 = ThisDrawing.ModelSpace.AddLine(P15, P19)
        Line11.Update
        
    Dim Line12 As AcadLine
        Set Line12 = ThisDrawing.ModelSpace.AddLine(P19, P20)
        Line12.Update
        
    Dim Line13 As AcadLine
        Set Line13 = ThisDrawing.ModelSpace.AddLine(P20, P16)
        Line13.Update
        
    Dim Line14 As AcadLine
        Set Line14 = ThisDrawing.ModelSpace.AddLine(P17, P21)
        Line14.Update
        
    Dim Line15 As AcadLine
        Set Line15 = ThisDrawing.ModelSpace.AddLine(P21, P22)
        Line15.Update
        
    Dim Line16 As AcadLine
        Set Line16 = ThisDrawing.ModelSpace.AddLine(P18, P22)
        Line16.Update
    
    Dim Line17 As AcadLine
        Set Line17 = ThisDrawing.ModelSpace.AddLine(P20, P21)
        Line17.color = acCyan
        Line17.Update
        
    Dim Line18 As AcadLine
        Set Line18 = ThisDrawing.ModelSpace.AddLine(P20, P23)
        Line18.Update
        
    Dim Line19 As AcadLine
        Set Line19 = ThisDrawing.ModelSpace.AddLine(P21, P25)
        Line19.Update
        
    Dim Line20 As AcadLine
        Set Line20 = ThisDrawing.ModelSpace.AddLine(P23, P25)
        Line20.Update
        
    Dim Line21 As AcadLine
        Set Line21 = ThisDrawing.ModelSpace.AddLine(P12, P24)
        Line21.color = acRed
        Line21.Linetype = "Center"
        Line21.Update
    
    '-----------------------------------------------------------------------------------------
    ' 치수기입
    '-----------------------------------------------------------------------------------------
    Dim dimGap As Double
    dimGap = D2 * 60
    
    Dim Dim1 As AcadDimAligned
    Dim txtPos As Variant
    Dim tempAng As Double
    
    tempAng = Line3.Angle - (Atn(1) * 4) / 2
    txtPos = ThisDrawing.Utility.PolarPoint(P8, tempAng, dimGap)
    Set Dim1 = ThisDrawing.ModelSpace.AddDimAligned(P7, P8, txtPos)
    Dim1.TextOverride = "R<>"
    
    Dim Dim2 As AcadDimAligned
    tempAng = Line5.Angle + (Atn(1) * 4) / 2
    txtPos = ThisDrawing.Utility.PolarPoint(P8, tempAng, dimGap)
    Set Dim2 = ThisDrawing.ModelSpace.AddDimAligned(CP, P8, txtPos)
    Dim2.TextOverride = "R<>"
    
    If diaratio > 0.575 Then
        Dim Dim3 As AcadDimAligned
        tempAng = Line6.Angle + (Atn(1) * 4) / 2
        txtPos = ThisDrawing.Utility.PolarPoint(P10, tempAng, dimGap)
        Set Dim3 = ThisDrawing.ModelSpace.AddDimAligned(P11, P10, txtPos)
        Dim3.TextOverride = "R<>"
    End If
    
    Dim Dim4 As AcadDimRotated
    Dim dimGap1 As Double
    If diaratio > 0.5 Then
        dimGap1 = dimGap * 2
        Else
        dimGap1 = dimGap
    End If
    txtPos = ThisDrawing.Utility.PolarPoint(P12, Dtr(270), dimGap1)
    Set Dim4 = ThisDrawing.ModelSpace.AddDimRotated(P13, P14, txtPos, 0)
    Dim4.TextOverride = "%%c<>"
    
    Dim Dim5 As AcadDimRotated
    txtPos = ThisDrawing.Utility.PolarPoint(P24, Dtr(90), dimGap)
    Set Dim5 = ThisDrawing.ModelSpace.AddDimRotated(P23, P25, txtPos, 0)
    Dim5.TextOverride = "%%c<>"
    
    Dim Dim6 As AcadDimAligned
    tempAng = Line16.Angle - (Atn(1) * 4) / 2
    txtPos = ThisDrawing.Utility.PolarPoint(P18, tempAng, dimGap)
    Set Dim6 = ThisDrawing.ModelSpace.AddDimAligned(P18, P22, txtPos)
    
    Dim Dim7 As AcadDimRotated
    txtPos = ThisDrawing.Utility.PolarPoint(P17, Dtr(180), dimGap)
    Set Dim7 = ThisDrawing.ModelSpace.AddDimRotated(P17, P21, txtPos, (Atn(1) * 4) / 2)
    
    If diaratio > 0.5 Then
        Dim Dim8 As AcadDimRotated
        txtPos = ThisDrawing.Utility.PolarPoint(P12, Dtr(270), dimGap)
        Set Dim8 = ThisDrawing.ModelSpace.AddDimRotated(P16, P17, txtPos, 0)
        Dim8.TextOverride = "%%c<>"
    End If
    
    ThisDrawing.SendCommand "dim up all  e "
    
    '---------------------------------------------------------------------------------------
    ' 도면에 Text 기입하기
    '---------------------------------------------------------------------------------------
    
    ThisDrawing.ActiveTextStyle = ThisDrawing.TextStyles("Standard")
        
    Dim tText As String
    Height = 2 * Sc
    
    PutText Str(q), 195, 26 '풍량
    PutText Str(ps), 195, 20 ' 풍압
    PutText Format(Str(N), "0"), 195, 14 ' 송풍기 회전수
    PutText Str(temp), 195, 8 ' 온도
    If frmInput.optVbelt Then
        PutText Str(motorPulley), 195, 2 ' 모터풀리
        PutText Str(fanPulley), 195, -4 ' Fan풀리
            tText = VbeltType + "-" + Str(PCS) + " pcs"
        PutText tText, 195, -10 ' 벨트타입/가닥수
        
        Else
        PutText "-", 195, 2 ' 모터풀리
        PutText "-", 195, -4 ' Fan풀리
        PutText "-", 195, -10 ' 벨트타입/가닥수
    End If
    
    Dim oldTstyle As AcadTextStyle
    Dim newTstyle As AcadTextStyle
        Set oldTstyle = ThisDrawing.ActiveTextStyle
        Set newTstyle = ThisDrawing.TextStyles.Add("한글")
        newTstyle.fontFile = "C:\Windows\Fonts\malgunsl.ttf"
        newTstyle.SetFont "맑은 고딕 Semilight", False, False, 129, 50
    
    ThisDrawing.ActiveTextStyle = newTstyle
    PutText frmOutput.txtMMaker, 255, 26   ' 모터 메이커
    ThisDrawing.ActiveTextStyle = oldTstyle
    PutText frmOutput.txtMType, 255, 20   ' 모터 타입
    PutText Str(motorcapa), 255, 14  ' 모터 출력
    PutText Str(motorrpm), 255, 8  ' 모터 회전수
        tText = Str(motorpoles) + "P/" + frmOutput.txtMFrequency
    PutText tText, 255, 2 ' 극수/주파수
    PutText "3%%c", 255, -4  ' 상수
        tText = Str(motorvoltage) + "V/" + Format(Str(motorloadamp), "0.0") + "A"
    PutText tText, 255, -10 ' 전압/전류
    
    ' 회전차 번호
    tText = "#" + Format(D2 / 0.1524, "0.0#")
    PutText tText, 245, -38
    
    ' Tip Speed
    tText = Format(Str(D2 * (Atn(1) * 4) * N / 60), "0.0")
    PutText tText, 245, -44
    
    ' 주판응력
    PutText Format(mStress, "####"), 245, -50
    
    ' 날개응력
    PutText Format(bladeStress, "####"), 245, -56
    
    ' 날개수삽입
    PutText frmInput.txtBladeNo, 245, -62
    
    ' 날개두께삽입
    PutText frmInput.txtBladeThickness, 245, -68
    
    ' 재질삽입
    PutText frmOutput.txtImpMatl, 245, -74
    
    ThisDrawing.ActiveTextStyle = newTstyle
    Height = 3.2 * Sc
    PutText frmOutput.txtCustomer, 246.0961, -124.2559 ' 고객명
    
    ThisDrawing.ActiveTextStyle = oldTstyle
    Height = 2 * Sc
    PutText Format(Date, "YYYY. M. D."), 189.7375, -137.04   ' 설계일자
    
    ' 작도 완료 후 전체보기
    ThisDrawing.Regen acActiveViewport
    ThisDrawing.Utility.Prompt ""
    ThisDrawing.Application.Update
    ThisDrawing.Utility.Prompt "Auto Drawing Completed!!!"
    VariablesSetting
    ThisDrawing.Application.Update
    
End Sub

Private Sub PutText(text As String, X As Double, Y As Double)
    
    Dim textObj As AcadText
    Dim insertionPoint(0 To 2) As Double
    Dim alignmentPoint(0 To 2) As Double
    Dim xCood As Double
    Dim yCood As Double
        xCood = X * Sc
        yCood = Y * Sc
        
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

