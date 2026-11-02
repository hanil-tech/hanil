' 원본: cFlange.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cFlange


    Public ID As Double
    Public pcd As Double
    Public OD As Double
    Public t As Double
    Public BHD As Double
    Public BN As Integer
    Public CP As Object
    Public RotAng As Double

    Public Sub PlanDraw()
        Dim P1 As Object
        Dim Cir1 As Object ' ID 작도
        Dim Cir2 As Object ' PCD 작도
        Dim Cir3 As Object ' OD 작도
        Dim Cir4 As Object ' BoltHole 작도
        Dim ArrayedCir As Object

        ' 작도 중심점 입력 받음

        P1 = PolarPoint(CP, Dtr(90 + 180 / BN), pcd / 2)

        ' Entity 생성
        Cir1 = ThisDrawing.ModelSpace.AddCircle(CP, ID / 2)

        Cir2 = ThisDrawing.ModelSpace.AddCircle(CP, pcd / 2)
        Cir2.color = VbCopy(acRed)
        Cir2.Linetype = "CENTER"

        Cir3 = ThisDrawing.ModelSpace.AddCircle(CP, OD / 2)

        Cir4 = ThisDrawing.ModelSpace.AddCircle(P1, BHD / 2)
        Cir4.color = VbCopy(acCyan)

        ArrayedCir = Cir4.ArrayPolar(BN, Dtr(360 * (BN - 1) / BN), CP)


    End Sub

    Public Sub FrontDraw()
        Dim myLinetype As Object
        Dim Found As Boolean
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

        ' Line Type Loading

        Found = False
        For Each myLinetype In ThisDrawing.Linetypes
            If myLinetype.Name = "CENTER" Then
                Found = True
            End If
        Next
        If Not (Found) Then
            ThisDrawing.Linetypes.Load("CENTER", "acad.lin")
        End If

        Found = False
        For Each myLinetype In ThisDrawing.Linetypes
            If myLinetype.Name = "HIDDEN" Then
                Found = True
            End If
        Next
        If Not (Found) Then
            ThisDrawing.Linetypes.Load("HIDDEN", "acad.lin")
        End If
        '-----------------------------------------------------------------

        ' Point Calculation

        P1 = PolarPoint(CP, Dtr(180 + RotAng), ID / 2)
        P2 = PolarPoint(CP, Dtr(180 + RotAng), (pcd - BHD) / 2)
        P3 = PolarPoint(P2, Dtr(180 + RotAng), BHD / 2)
        P4 = PolarPoint(P3, Dtr(90 + RotAng), t)
        P5 = PolarPoint(P3, Dtr(180 + RotAng), BHD / 2)


        P6 = PolarPoint(CP, Dtr(180 + RotAng), OD / 2)
        P7 = PolarPoint(P6, Dtr(270 + RotAng), t)
        P8 = PolarPoint(P5, Dtr(270 + RotAng), t)
        P9 = PolarPoint(P3, Dtr(270 + RotAng), t)
        P10 = PolarPoint(P9, Dtr(270 + RotAng), t)

        P11 = PolarPoint(P2, Dtr(270 + RotAng), t)
        P12 = PolarPoint(P1, Dtr(270 + RotAng), t)
        P13 = PolarPoint(P12, Dtr(0 + RotAng), ID)
        P14 = PolarPoint(P11, Dtr(0 + RotAng), pcd - BHD)
        P15 = PolarPoint(P14, Dtr(0 + RotAng), BHD / 2)

        P16 = PolarPoint(P15, Dtr(270 + RotAng), t)
        P17 = PolarPoint(P15, Dtr(0 + RotAng), BHD / 2)
        P18 = PolarPoint(P7, Dtr(0 + RotAng), OD)
        P19 = PolarPoint(P18, Dtr(90 + RotAng), t)
        P20 = PolarPoint(P17, Dtr(90 + RotAng), t)

        P21 = PolarPoint(P15, Dtr(90 + RotAng), t)
        P22 = PolarPoint(P21, Dtr(90 + RotAng), t)
        P23 = PolarPoint(P14, Dtr(90 + RotAng), t)
        P24 = PolarPoint(P13, Dtr(90 + RotAng), t)

        ' Entity 생성

        ' Continuous Line
        Line1 = ThisDrawing.ModelSpace.AddLine(P6, P19)
        Line1.color = VbCopy(acCyan)

        Line2 = ThisDrawing.ModelSpace.AddLine(P6, P7)
        Line2.color = VbCopy(acCyan)

        Line3 = ThisDrawing.ModelSpace.AddLine(P7, P18)
        Line3.color = VbCopy(acCyan)

        Line4 = ThisDrawing.ModelSpace.AddLine(P18, P19)
        Line4.color = VbCopy(acCyan)

        ' Hidden Line 생성
        Line5 = ThisDrawing.ModelSpace.AddLine(P8, P5)
        Line5.color = VbCopy(acGreen)
        Line5.Linetype = "HIDDEN"

        Line6 = ThisDrawing.ModelSpace.AddLine(P11, P2)
        Line6.color = VbCopy(acGreen)
        Line6.Linetype = "HIDDEN"

        Line7 = ThisDrawing.ModelSpace.AddLine(P12, P1)
        Line7.color = VbCopy(acGreen)
        Line7.Linetype = "HIDDEN"

        Line8 = ThisDrawing.ModelSpace.AddLine(P13, P24)
        Line8.color = VbCopy(acGreen)
        Line8.Linetype = "HIDDEN"

        Line9 = ThisDrawing.ModelSpace.AddLine(P14, P23)
        Line9.color = VbCopy(acGreen)
        Line9.Linetype = "HIDDEN"

        Line10 = ThisDrawing.ModelSpace.AddLine(P17, P20)
        Line10.color = VbCopy(acGreen)
        Line10.Linetype = "HIDDEN"

        ' Center Line 생성
        Line11 = ThisDrawing.ModelSpace.AddLine(P10, P4)
        Line11.color = VbCopy(acRed)
        Line11.Linetype = "CENTER"

        Line12 = ThisDrawing.ModelSpace.AddLine(P16, P22)
        Line12.color = VbCopy(acRed)
        Line12.Linetype = "CENTER"


    End Sub

    Private Function Dtr(ByVal Degree As Double) As Object

        Dtr = (Atn(1) * 4) * Degree / 180#

    End Function

End Class
