' 원본: cChannel.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cChannel

    Public H As Double
    Public B As Double
    Public t1 As Double
    Public t2 As Double
    Public R1 As Double
    Public R2 As Double
    Public Mirror As Boolean
    Public CP As Object

    Dim X1 As Double
    Dim X2 As Double
    Dim X3 As Double
    Dim X4 As Double
    Dim X5 As Double
    Dim X6 As Double
    Dim X7 As Double

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

    Public Sub Draw()
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim Line6 As Object
        Dim Line7 As Object
        Dim Line8 As Object
        Dim Arc1 As Object
        Dim Arc2 As Object
        Dim Arc3 As Object
        Dim Arc4 As Object

            Line1 = ThisDrawing.ModelSpace.AddLine(P1, P2)
                Line1.color = VbCopy(acCyan)
                Line1.Update

            Line2 = ThisDrawing.ModelSpace.AddLine(P2, P3)
                Line2.color = VbCopy(acCyan)
                Line2.Update

            Line3 = ThisDrawing.ModelSpace.AddLine(P3, P4)
                Line3.color = VbCopy(acCyan)
                Line3.Update

            Line4 = ThisDrawing.ModelSpace.AddLine(P6, P7)
                Line4.color = VbCopy(acCyan)
                Line4.Update

            Line5 = ThisDrawing.ModelSpace.AddLine(P9, P10)
                Line5.color = VbCopy(acCyan)
                Line5.Update

            Line6 = ThisDrawing.ModelSpace.AddLine(P12, P13)
                Line6.color = VbCopy(acCyan)
                Line6.Update

            Line7 = ThisDrawing.ModelSpace.AddLine(P15, P16)
                Line7.color = VbCopy(acCyan)
                Line7.Update

            Line8 = ThisDrawing.ModelSpace.AddLine(P16, P1)
                Line8.color = VbCopy(acCyan)
                Line8.Update


            If Mirror = False Then
                Arc1 = ThisDrawing.ModelSpace.AddArc(P5, R2, Dtr(0), Dtr(85))
                Else
                Arc1 = ThisDrawing.ModelSpace.AddArc(P5, R2, Dtr(95), Dtr(180))
            End If
            Arc1.color = VbCopy(acCyan)
            Arc1.Update

            If Mirror = False Then
                Arc2 = ThisDrawing.ModelSpace.AddArc(P8, R1, Dtr(180), Dtr(265))
                Else
                Arc2 = ThisDrawing.ModelSpace.AddArc(P8, R1, Dtr(275), Dtr(0))
            End If
            Arc2.color = VbCopy(acCyan)
            Arc2.Update

            If Mirror = False Then
                Arc3 = ThisDrawing.ModelSpace.AddArc(P11, R1, Dtr(95), Dtr(180))
                Else
                Arc3 = ThisDrawing.ModelSpace.AddArc(P11, R1, Dtr(0), Dtr(85))
            End If
            Arc3.color = VbCopy(acCyan)
            Arc3.Update

            If Mirror = False Then
                Arc4 = ThisDrawing.ModelSpace.AddArc(P14, R2, Dtr(275), Dtr(0))
                Else
                Arc4 = ThisDrawing.ModelSpace.AddArc(P14, R2, Dtr(180), Dtr(265))
            End If
            Arc4.color = VbCopy(acCyan)
            Arc4.Update

        ' 치수점 할당
        If frmInput.optDirect.Value Then ' 직결일 때

            If Direction = "RH" Then
                If LeftChannel Then
                    dimP16 = VbCopy(P3)
                    dimP17 = VbCopy(P2)
                    LeftChannel = False

                    ElseIf RightChannel Then
                    dimP18 = VbCopy(P2)
                    dimP19 = VbCopy(P3)
                    RightChannel = False
                End If
            End If

            If Direction = "RL" Then
                If LeftChannel Then
                    dimP21 = VbCopy(P3)
                    dimP22 = VbCopy(P2)
                    LeftChannel = False

                    ElseIf RightChannel Then
                    dimP23 = VbCopy(P2)
                    dimP24 = VbCopy(P3)
                    RightChannel = False
                End If
            End If

            If Direction = "RR" Then
                If LeftChannel Then
                    dimP17 = VbCopy(P3)
                    dimP18 = VbCopy(P2)
                    LeftChannel = False

                    ElseIf RightChannel Then
                    dimP19 = VbCopy(P2)
                    dimP20 = VbCopy(P3)
                    RightChannel = False
                End If
            End If

            If Direction = "LH" Then
                If LeftChannel Then
                    dimP16 = VbCopy(P3)
                    dimP17 = VbCopy(P2)
                    LeftChannel = False

                    ElseIf RightChannel Then
                    dimP18 = VbCopy(P2)
                    dimP19 = VbCopy(P3)
                    RightChannel = False
                End If
            End If

            If Direction = "LL" Then
                If LeftChannel Then
                    dimP18 = VbCopy(P3)
                    dimP19 = VbCopy(P2)
                    LeftChannel = False

                    ElseIf RightChannel Then
                    dimP20 = VbCopy(P2)
                    dimP21 = VbCopy(P3)
                    RightChannel = False
                End If
            End If

            If Direction = "LR" Then
                If LeftChannel Then
                    dimP18 = VbCopy(P3)
                    dimP19 = VbCopy(P2)
                    LeftChannel = False

                    ElseIf RightChannel Then
                    dimP20 = VbCopy(P2)
                    dimP21 = VbCopy(P3)
                    RightChannel = False
                End If
            End If

            Else ' V-Belt 전동시
                If LeftChannel Then
                    dimP18 = VbCopy(P3)
                    dimP19 = VbCopy(P2)
                    LeftChannel = False

                    ElseIf RightChannel Then
                    dimP20 = VbCopy(P2)
                    dimP21 = VbCopy(P3)
                    RightChannel = False
                End If
        End If

    End Sub

    Public Sub PointCal()

            X1 = R1 * Tan(Dtr(42.5))
            X2 = R2 * Tan(Dtr(42.5))
            X6 = (B - t1) / 2 * Tan(Dtr(5))
            X3 = t2 - X6 - X2
            X4 = (B - t1) / Cos(Dtr(5)) - X1 - X2
            X5 = (X1 + X4 + X2) * Tan(Dtr(5))
            X7 = H - 2 * (X3 + X2 + X5 + X1)

            P1 = VbCopy(CP)
            P2 = PolarPoint(P1, Dtr(270), H)
            If Mirror = False Then
                P3 = PolarPoint(P2, Dtr(0), B)
                Else
                P3 = PolarPoint(P2, Dtr(180), B)
            End If

            P4 = PolarPoint(P3, Dtr(90), X3)

            If Mirror = False Then
                P5 = PolarPoint(P4, Dtr(180), R2)
                Else
                P5 = PolarPoint(P4, Dtr(0), R2)
            End If

            If Mirror = False Then
                P6 = PolarPoint(P5, Dtr(85), R2)
                Else
                P6 = PolarPoint(P5, Dtr(95), R2)
            End If

            If Mirror = False Then
                P7 = PolarPoint(P6, Dtr(175), X4)
                Else
                P7 = PolarPoint(P6, Dtr(5), X4)
            End If

            If Mirror = False Then
                P8 = PolarPoint(P7, Dtr(85), R1)
                Else
                P8 = PolarPoint(P7, Dtr(95), R1)
            End If

            If Mirror = False Then
                P9 = PolarPoint(P8, Dtr(180), R1)
                Else
                P9 = PolarPoint(P8, Dtr(0), R1)
            End If

            P10 = PolarPoint(P9, Dtr(90), X7)

            If Mirror = False Then
                P11 = PolarPoint(P10, Dtr(0), R1)
                Else
                P11 = PolarPoint(P10, Dtr(180), R1)
            End If
            If Mirror = False Then
                P12 = PolarPoint(P11, Dtr(95), R1)
                Else
                P12 = PolarPoint(P11, Dtr(85), R1)
            End If

            If Mirror = False Then
                P13 = PolarPoint(P12, Dtr(5), X4)
                Else
                P13 = PolarPoint(P12, Dtr(175), X4)
            End If

            If Mirror = False Then
                P14 = PolarPoint(P13, Dtr(95), R2)
                Else
                P14 = PolarPoint(P13, Dtr(85), R2)
            End If

            If Mirror = False Then
                P15 = PolarPoint(P14, Dtr(0), R2)
                Else
                P15 = PolarPoint(P14, Dtr(180), R2)
            End If

            P16 = PolarPoint(P15, Dtr(90), X3)

            If Mirror = False Then
                bPntCol.Add(P3)
                bPntCol.Add(P4)
                bPntCol.Add(P6)
                bPntCol.Add(P7)
                bPntCol.Add(P9)
                bPntCol.Add(P10)
                bPntCol.Add(P12)
                bPntCol.Add(P13)
                bPntCol.Add(P15)
                bPntCol.Add(P16)
                bPntCol.Add(P1)

                Else
                bPntCol.Add(P16)
                bPntCol.Add(P15)
                bPntCol.Add(P13)
                bPntCol.Add(P12)
                bPntCol.Add(P10)
                bPntCol.Add(P9)
                bPntCol.Add(P7)
                bPntCol.Add(P6)
                bPntCol.Add(P4)
                bPntCol.Add(P3)
            End If

    End Sub

End Class
