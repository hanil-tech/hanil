Attribute VB_Name = "cSN3"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit
Public Name As String
Public CP As Variant
Public a As Double
Public Dia1 As Double
Public Dia2 As Double
Public H As Double

Dim A1 As Double
Dim H1 As Double
Dim H2 As Double
Dim j As Double
Dim L As Double
Dim N1 As Double

Public Sub DrawRight() ' 우측면도 작성

    ReadData ' 데이터 읽어오기
    
    ' Point 선언
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
    Dim P24 As Variant
    
    Dim P25 As Variant
    Dim P26 As Variant
    Dim P27 As Variant
    Dim P28 As Variant
    
    Dim P29 As Variant
    Dim P30 As Variant
    
    Dim cenP1 As Variant
    Dim cenP2 As Variant
    
        ' Point Calculation
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180), N1 / 2)
        P2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180), A1 / 2)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(90), H1)
        P4 = ThisDrawing.Utility.PolarPoint(P1, Dtr(90), H1)
        
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(0), N1)
        P6 = ThisDrawing.Utility.PolarPoint(P3, Dtr(0), A1)
        P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(270), H1)
        P8 = ThisDrawing.Utility.PolarPoint(P5, Dtr(270), H1)
        
        P9 = ThisDrawing.Utility.PolarPoint(CP, Dtr(90), H2)
        P10 = ThisDrawing.Utility.PolarPoint(P9, Dtr(180), A1 / 2)
        P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(270), (a - A1) / 4)
        P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(180), (a - A1) / 4)
        
        P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(270), (H2 - H) - 1.5 * Dia1 / 2 - (a - A1) / 4)
        P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(180), (a - A1) / 4)
        P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(270), 1.5 * Dia1)
        P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(0), (a - A1) / 4)
        
        P19 = ThisDrawing.Utility.PolarPoint(P2, Dtr(90), H1 / 4)
        P18 = ThisDrawing.Utility.PolarPoint(P19, Dtr(90), (a - A1) / 4)
        P17 = ThisDrawing.Utility.PolarPoint(P18, Dtr(180), (a - A1) / 4)
        
        P20 = ThisDrawing.Utility.PolarPoint(P7, Dtr(90), H1 / 4)
        P21 = ThisDrawing.Utility.PolarPoint(P20, Dtr(90), (a - A1) / 4)
        P22 = ThisDrawing.Utility.PolarPoint(P21, Dtr(0), (a - A1) / 4)
        
        P23 = ThisDrawing.Utility.PolarPoint(P22, Dtr(90), H2 - H1 / 4 - (a - A1) / 4 _
            - (H2 - H) - (1.5 * Dia1 / 2))
        
        P24 = ThisDrawing.Utility.PolarPoint(P23, Dtr(0), (a - A1) / 4)
        
        P25 = ThisDrawing.Utility.PolarPoint(P24, Dtr(90), 1.5 * Dia1)
        P26 = ThisDrawing.Utility.PolarPoint(P25, Dtr(180), (a - A1) / 4)
        P27 = ThisDrawing.Utility.PolarPoint(P26, Dtr(90), (H2 - H) - 1.5 * Dia1 / 2 - (a - A1) / 4)
        P28 = ThisDrawing.Utility.PolarPoint(P27, Dtr(180), (a - A1) / 4)
        
        P29 = ThisDrawing.Utility.PolarPoint(P28, Dtr(90), (a - A1) / 4)
        
        cenP1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(270), H1)
        cenP2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(90), 3 * H1)
        
    ' Entity 선언
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
    Dim Line14 As AcadLine
    Dim Line15 As AcadLine
    Dim Line16 As AcadLine
    
    Dim Line17 As AcadLine
    Dim cenLine1 As AcadLine
    
    Dim Arc1 As AcadArc
    Dim Arc2 As AcadArc
    Dim Arc3 As AcadArc
    Dim Arc4 As AcadArc
        
        ' Entity 생성
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P2, P7)
        Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P2, P3)
        Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P3, P6)
        Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P7, P6)
        Line4.Update
        
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P1, P4)
        Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P8, P5)
            Line5.color = acGreen
            Line5.Linetype = "Hidden"
            Line6.color = acGreen
            Line6.Linetype = "Hidden"
            Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P17, P12)
        Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P16, P15)
            Line8.color = acCyan
            Line8.Update
            
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P15, P14)
            Line9.color = acCyan
            Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P14, P13)
            Line10.color = acCyan
            Line10.Update
        
        Set Line11 = ThisDrawing.ModelSpace.AddLine(P10, P29)
        Line11.Update
        Set Line12 = ThisDrawing.ModelSpace.AddLine(P22, P27)
        Line12.Update
        Set Line13 = ThisDrawing.ModelSpace.AddLine(P23, P24)
            Line13.color = acCyan
            Line13.Update
        Set Line14 = ThisDrawing.ModelSpace.AddLine(P24, P25)
            Line14.color = acCyan
            Line14.Update
        Set Line15 = ThisDrawing.ModelSpace.AddLine(P26, P25)
            Line15.color = acCyan
            Line15.Update
                    
        Set Arc1 = ThisDrawing.ModelSpace.AddArc(P11, (a - A1) / 4, Dtr(90), Dtr(180))
        Arc1.Update
        Set Arc2 = ThisDrawing.ModelSpace.AddArc(P18, (a - A1) / 4, Dtr(180), Dtr(270))
        Arc2.Update
        Set Arc3 = ThisDrawing.ModelSpace.AddArc(P21, (a - A1) / 4, Dtr(270), Dtr(0))
        Arc3.Update
        Set Arc4 = ThisDrawing.ModelSpace.AddArc(P28, (a - A1) / 4, Dtr(0), Dtr(90))
        Arc4.Update
        
        Set cenLine1 = ThisDrawing.ModelSpace.AddLine(cenP1, cenP2)
        cenLine1.color = acRed
        cenLine1.Linetype = "Center"
        
        
End Sub

Public Sub DrawPlan() ' 평면도 작성
    
    ReadData ' 데이터 읽어오기
    
    ' Point 선언
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
    Dim P24 As Variant
    
    Dim P25 As Variant
    Dim P26 As Variant
    Dim P27 As Variant
    Dim P28 As Variant
    
    Dim cenP1 As Variant
    Dim cenP2 As Variant
    Dim cenP3 As Variant
    Dim cenP4 As Variant
    Dim cenP5 As Variant
    Dim cenP6 As Variant
    Dim cenP7 As Variant
    Dim cenP8 As Variant
    
    
        ' Point Calculation
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180), j / 2)
        P2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), j / 2)
        P3 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180), L / 2)
        P4 = ThisDrawing.Utility.PolarPoint(CP, Dtr(0), L / 2)
        
        P5 = ThisDrawing.Utility.PolarPoint(P3, Dtr(90), A1 / 2)
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(0), (L - 2 * (H2 - H)) / 2)
        P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(0), (a - A1) / 4)
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(90), (a - A1) / 4)
        
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(0), (H2 - H) - 1.5 * Dia1 / 2 - (a - A1) / 4)
        P10 = ThisDrawing.Utility.PolarPoint(P9, Dtr(90), (a - A1) / 4)
        P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(0), 1.5 * Dia1)
        P12 = ThisDrawing.Utility.PolarPoint(P9, Dtr(0), 1.5 * Dia1)
        
        P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(0), (H2 - H) - 1.5 * Dia1 / 2 - (a - A1) / 4)
        P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(270), (a - A1) / 4)
        P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(0), (a - A1) / 4)
        P16 = ThisDrawing.Utility.PolarPoint(P5, Dtr(0), L)
        
        P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(270), A1)
        P18 = ThisDrawing.Utility.PolarPoint(P15, Dtr(270), A1)
        P19 = ThisDrawing.Utility.PolarPoint(P14, Dtr(270), A1)
        P20 = ThisDrawing.Utility.PolarPoint(P19, Dtr(270), (a - A1) / 4)
        
        P21 = ThisDrawing.Utility.PolarPoint(P20, Dtr(180), (H2 - H) - 1.5 * Dia1 / 2 - (a - A1) / 4)
        P22 = ThisDrawing.Utility.PolarPoint(P21, Dtr(270), (a - A1) / 4)
        P23 = ThisDrawing.Utility.PolarPoint(P22, Dtr(180), 1.5 * Dia1)
        P24 = ThisDrawing.Utility.PolarPoint(P21, Dtr(180), 1.5 * Dia1)
        
        P25 = ThisDrawing.Utility.PolarPoint(P24, Dtr(180), (H2 - H) - 1.5 * Dia1 / 2 - (a - A1) / 4)
        P26 = ThisDrawing.Utility.PolarPoint(P25, Dtr(90), (a - A1) / 4)
        P27 = ThisDrawing.Utility.PolarPoint(P6, Dtr(270), A1)
        P28 = ThisDrawing.Utility.PolarPoint(P5, Dtr(270), A1)
        
        cenP1 = ThisDrawing.Utility.PolarPoint(P1, Dtr(180), 1.5 * N1)
        cenP2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(0), 1.5 * N1)
        cenP3 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), 1.5 * N1)
        cenP4 = ThisDrawing.Utility.PolarPoint(P1, Dtr(90), 1.5 * N1)
        
        cenP5 = ThisDrawing.Utility.PolarPoint(P2, Dtr(180), 1.5 * N1)
        cenP6 = ThisDrawing.Utility.PolarPoint(P2, Dtr(0), 1.5 * N1)
        cenP7 = ThisDrawing.Utility.PolarPoint(P2, Dtr(270), 1.5 * N1)
        cenP8 = ThisDrawing.Utility.PolarPoint(P2, Dtr(90), 1.5 * N1)
        
        

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
    Dim Line14 As AcadLine
    Dim Line15 As AcadLine
    Dim Line16 As AcadLine
    
    Dim cenLine1 As AcadLine
    Dim cenLine2 As AcadLine
    Dim cenLine3 As AcadLine
    Dim cenLine4 As AcadLine
    
    
    Dim Arc1 As AcadArc
    Dim Arc2 As AcadArc
    Dim Arc3 As AcadArc
    Dim Arc4 As AcadArc
    
    Dim Cir1 As AcadCircle
    Dim Cir2 As AcadCircle
    
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P23, P22)
            Line1.color = acCyan
            Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P23, P24)
            Line2.color = acCyan
            Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P22, P21)
            Line3.color = acCyan
            Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P25, P20)
        Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P28, P27)
        Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P28, P5)
        Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P5, P6)
        Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P18, P17)
        Line8.Update
        
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P17, P16)
        Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P15, P16)
        Line10.Update
        Set Line11 = ThisDrawing.ModelSpace.AddLine(P8, P13)
        Line11.Update
        
        Set Line12 = ThisDrawing.ModelSpace.AddLine(P9, P10)
            Line12.color = acCyan
            Line12.Update
        Set Line13 = ThisDrawing.ModelSpace.AddLine(P10, P11)
            Line13.color = acCyan
            Line13.Update
        Set Line14 = ThisDrawing.ModelSpace.AddLine(P12, P11)
            Line14.color = acCyan
            Line14.Update
        
        Set Line15 = ThisDrawing.ModelSpace.AddLine(P27, P6)
        Line15.Update
        Set Line16 = ThisDrawing.ModelSpace.AddLine(P18, P15)
        Line16.Update
        
        Set Arc1 = ThisDrawing.ModelSpace.AddArc(P7, (a - A1) / 4, Dtr(90), Dtr(180))
        Arc1.Update
        Set Arc2 = ThisDrawing.ModelSpace.AddArc(P26, (a - A1) / 4, Dtr(180), Dtr(270))
        Arc2.Update
        Set Arc3 = ThisDrawing.ModelSpace.AddArc(P19, (a - A1) / 4, Dtr(270), Dtr(0))
        Arc3.Update
        Set Arc4 = ThisDrawing.ModelSpace.AddArc(P14, (a - A1) / 4, Dtr(0), Dtr(90))
        Arc4.Update
        
        Set Cir1 = ThisDrawing.ModelSpace.AddCircle(P1, N1 / 2)
            Cir1.color = acCyan
            Cir1.Update
        Set Cir2 = ThisDrawing.ModelSpace.AddCircle(P2, N1 / 2)
            Cir2.color = acCyan
            Cir2.Update
        
        Set cenLine1 = ThisDrawing.ModelSpace.AddLine(cenP1, cenP2)
        cenLine1.color = acRed
        cenLine1.Linetype = "Center"
        cenLine1.Update
        Set cenLine2 = ThisDrawing.ModelSpace.AddLine(cenP3, cenP4)
        cenLine2.color = acRed
        cenLine2.Linetype = "Center"
        cenLine2.Update
        Set cenLine3 = ThisDrawing.ModelSpace.AddLine(cenP5, cenP6)
        cenLine3.color = acRed
        cenLine3.Linetype = "Center"
        cenLine3.Update
        Set cenLine4 = ThisDrawing.ModelSpace.AddLine(cenP7, cenP8)
        cenLine4.color = acRed
        cenLine4.Linetype = "Center"
        cenLine4.Update
        
    
End Sub
    


Private Function Dtr(Degree As Double) As Double
    
    Dtr = Atn(1) * 4 * Degree / 180

End Function

Public Sub ReadData()

    ' SN3 Plomer에 대한 Data Read
    Select Case Name
        Case "SN305"
            Dia1 = 30: Dia2 = 20: a = 80: A1 = 52: H = 50: H1 = 22: H2 = 90: j = 150: L = 185: N1 = 15
        Case "SN306"
            Dia1 = 35: Dia2 = 25: a = 82: A1 = 52: H = 50: H1 = 22: H2 = 95: j = 150: L = 185: N1 = 15
        Case "SN307"
            Dia1 = 45: Dia2 = 30: a = 90: A1 = 60: H = 60: H1 = 25: H2 = 110: j = 170: L = 205: N1 = 15
        Case "SN308"
            Dia1 = 50: Dia2 = 35: a = 95: A1 = 60: H = 60: H1 = 25: H2 = 115: j = 170: L = 205: N1 = 15
        Case "SN309"
            Dia1 = 55: Dia2 = 40: a = 105: A1 = 70: H = 70: H1 = 28: H2 = 130: j = 210: L = 255: N1 = 18
        Case "SN310"
            Dia1 = 60: Dia2 = 45: a = 115: A1 = 70: H = 70: H1 = 30: H2 = 135: j = 210: L = 255: N1 = 18
        Case "SN311"
            Dia1 = 65: Dia2 = 50: a = 120: A1 = 80: H = 80: H1 = 30: H2 = 150: j = 230: L = 275: N1 = 18
        Case "SN312"
            Dia1 = 70: Dia2 = 55: a = 125: A1 = 80: H = 80: H1 = 30: H2 = 155: j = 230: L = 280: N1 = 18
        Case "SN313"
            Dia1 = 75: Dia2 = 60: a = 130: A1 = 90: H = 95: H1 = 32: H2 = 175: j = 260: L = 315: N1 = 22
        Case "SN314"
            Dia1 = 80: Dia2 = 65: a = 130: A1 = 90: H = 95: H1 = 32: H2 = 185: j = 260: L = 320: N1 = 22
        
        Case "SN315"
            Dia1 = 85: Dia2 = 70: a = 140: A1 = 100: H = 100: H1 = 35: H2 = 195: j = 290: L = 345: N1 = 22
        Case "SN316"
            Dia1 = 90: Dia2 = 75: a = 145: A1 = 100: H = 112: H1 = 35: H2 = 212: j = 290: L = 345: N1 = 22
        Case "SN317"
            Dia1 = 95: Dia2 = 80: a = 155: A1 = 110: H = 112: H1 = 40: H2 = 218: j = 320: L = 380: N1 = 26
        Case "SN318"
            Dia1 = 100: Dia2 = 85: a = 160: A1 = 110: H = 112: H1 = 33: H2 = 230: j = 320: L = 400: N1 = 26
        Case "SN319"
            Dia1 = 110: Dia2 = 90: a = 170: A1 = 120: H = 125: H1 = 36: H2 = 245: j = 350: L = 420: N1 = 26
        Case "SN320"
            Dia1 = 115: Dia2 = 95: a = 175: A1 = 120: H = 140: H1 = 38: H2 = 280: j = 350: L = 420: N1 = 26
        Case "SN322"
            Dia1 = 125: Dia2 = 105: a = 190: A1 = 130: H = 150: H1 = 40: H2 = 300: j = 390: L = 460: N1 = 28
        Case "SN324"
            Dia1 = 135: Dia2 = 115: a = 205: A1 = 160: H = 160: H1 = 50: H2 = 325: j = 450: L = 540: N1 = 33
        Case "SN326"
            Dia1 = 150: Dia2 = 125: a = 215: A1 = 160: H = 170: H1 = 50: H2 = 350: j = 470: L = 560: N1 = 33
        Case "SN328"
            Dia1 = 160: Dia2 = 135: a = 235: A1 = 170: H = 180: H1 = 55: H2 = 375: j = 520: L = 630: N1 = 35
        Case "SN330"
            Dia1 = 170: Dia2 = 145: a = 245: A1 = 180: H = 190: H1 = 55: H2 = 395: j = 560: L = 680: N1 = 35
        Case "SN332"
            Dia1 = 180: Dia2 = 150: a = 255: A1 = 190: H = 200: H1 = 60: H2 = 415: j = 580: L = 710: N1 = 42
        
    End Select


End Sub
