' 원본: cShaft.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cShaft
    Public RotAng As Double
    Public CP As Object


    Public Sub Draw()
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
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim Line6 As Object






            P1 = PolarPoint(CP, Dtr(RotAng + 180), SN3.Dia2 / 2)
            P1 = PolarPoint(P1, Dtr(RotAng + 90), 15)

            P2 = PolarPoint(CP, Dtr(RotAng + 0), SN3.Dia2 / 2)
            P2 = PolarPoint(P2, Dtr(RotAng + 90), 15)


            P3 = PolarPoint(P1, Dtr(RotAng + 90), 25)
            P4 = PolarPoint(P2, Dtr(RotAng + 90), 25)

            P5 = PolarPoint(CP, Dtr(RotAng + 90), 40 + SN3.a)
            P6 = PolarPoint(P5, Dtr(RotAng + 180), SN3.Dia1 / 2)
            P7 = PolarPoint(P5, Dtr(RotAng + 0), SN3.Dia1 / 2)
            P8 = PolarPoint(P6, Dtr(RotAng + 90), MWidth - 2 * SN3.a - 40)

            P9 = PolarPoint(P8, Dtr(RotAng + 0), SN3.Dia1)
            P10 = PolarPoint(CP, Dtr(RotAng + 90), MWidth)
            P11 = PolarPoint(P10, Dtr(RotAng + 180), SN3.Dia2 / 2)
            P12 = PolarPoint(P10, Dtr(RotAng + 0), SN3.Dia2 / 2)

            P13 = PolarPoint(P11, Dtr(RotAng + 90), 20)
            P14 = PolarPoint(P12, Dtr(RotAng + 90), 20)

            Line1 = ThisDrawing.ModelSpace.AddLine(P1, P3)
            Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P2, P4)
            Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P6, P8)
            Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P7, P9)
            Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P11, P13)
            Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P12, P14)
            Line6.Update


    End Sub

End Class
