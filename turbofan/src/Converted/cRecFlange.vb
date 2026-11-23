' 원본: cRecFlange.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cRecFlange

    ' 프로퍼티 선언
    Public CP As Object
    Public B As Double
    Public t As Double
    Public idLength As Double
    Public idWidth As Double
    Public BD As Double ' Bolt hole Diameter
    Public RotAng As Double

    Dim pntCol As New VBCollection
    Dim pntArray() As Double

    ' 클래스내 전역변수 선언
    Dim Pitch As Double ' Bolt Hole Pitch


    Public Sub DrawFront() ' 정면도 작성
        Dim pcd As Double
        Dim OD As Double
        Dim Pnt1 As Object
        Dim Pnt2 As Object
        Dim Pnt3 As Object
        Dim Pnt4 As Object
        Dim Pnt5 As Object
        Dim Pnt6 As Object
        Dim Pnt7 As Object
        Dim Pnt8 As Object
        Dim Pnt9 As Object
        Dim Pnt10 As Object
        Dim Pnt11 As Object
        Dim Pnt12 As Object
        Dim Pnt13 As Object
        Dim Pnt14 As Object
        Dim Pnt15 As Object
        Dim Pnt16 As Object
        Dim Pnt17 As Object
        Dim Pnt18 As Object
        Dim Pnt19 As Object
        Dim Pnt20 As Object
        Dim Pnt21 As Object
        Dim Pnt22 As Object
        Dim Pnt23 As Object
        Dim Pnt24 As Object
        Dim Pnt25 As Object
        Dim rFlangeEnt As Object
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

        pntCol = New VBCollection

        ' pcd 계산
            pcd = idLength + B
        ' od 계산
            OD = idLength + 2 * B

        ' Point Calculation





            Pnt1 = PolarPoint(CP, Dtr(RotAng + 180), idLength / 2)
            Pnt2 = PolarPoint(CP, Dtr(RotAng + 180), (pcd - BD) / 2)
            Pnt3 = PolarPoint(CP, Dtr(RotAng + 180), pcd / 2)
            Pnt4 = PolarPoint(Pnt3, Dtr(RotAng + 90), t)
            Pnt5 = PolarPoint(Pnt3, Dtr(RotAng + 180), BD / 2)

            Pnt6 = PolarPoint(CP, Dtr(RotAng + 180), OD / 2)
            Pnt7 = PolarPoint(Pnt6, Dtr(RotAng + 270), t)
            Pnt8 = PolarPoint(Pnt5, Dtr(RotAng + 270), t)
            Pnt9 = PolarPoint(Pnt3, Dtr(RotAng + 270), t)
            Pnt10 = PolarPoint(Pnt9, Dtr(RotAng + 270), t)

            Pnt11 = PolarPoint(Pnt2, Dtr(RotAng + 270), t)
            Pnt12 = PolarPoint(Pnt1, Dtr(RotAng + 270), t)
            Pnt13 = PolarPoint(CP, Dtr(RotAng + 270), t)
            Pnt14 = PolarPoint(Pnt13, Dtr(RotAng + 0), idLength / 2)
            Pnt15 = PolarPoint(Pnt13, Dtr(RotAng + 0), (pcd - BD) / 2)

            Pnt16 = PolarPoint(Pnt15, Dtr(RotAng + 0), BD / 2)
            Pnt17 = PolarPoint(Pnt16, Dtr(RotAng + 270), t)
            Pnt18 = PolarPoint(Pnt16, Dtr(RotAng + 0), BD / 2)
            Pnt19 = PolarPoint(Pnt13, Dtr(RotAng + 0), OD / 2)
            Pnt20 = PolarPoint(Pnt19, Dtr(RotAng + 90), t)

            Pnt21 = PolarPoint(Pnt18, Dtr(RotAng + 90), t)
            Pnt22 = PolarPoint(Pnt16, Dtr(RotAng + 90), t)
            Pnt23 = PolarPoint(Pnt22, Dtr(RotAng + 90), t)
            Pnt24 = PolarPoint(Pnt15, Dtr(RotAng + 90), t)
            Pnt25 = PolarPoint(Pnt14, Dtr(RotAng + 90), t)

            pntCol.Add(Pnt6)
            pntCol.Add(Pnt7)
            pntCol.Add(Pnt19)
            pntCol.Add(Pnt20)

            MakePntArray

            rFlangeEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
            With rFlangeEnt
                .Closed = True
                .Highlight(True)
                .Update
            End With

            AutoTrim.Ent = rFlangeEnt
            AutoTrim.DoTrim
            rFlangeEnt.Delete




            Line1 = ThisDrawing.ModelSpace.AddLine(Pnt6, Pnt20)
            Line2 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt6)
            Line3 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt19)
            Line4 = ThisDrawing.ModelSpace.AddLine(Pnt19, Pnt20)
                Line1.color = VbCopy(acCyan)
                Line2.color = VbCopy(acCyan)
                Line3.color = VbCopy(acCyan)
                Line4.color = VbCopy(acCyan)

                Line1.Update
                Line2.Update
                Line3.Update
                Line4.Update

            Line5 = ThisDrawing.ModelSpace.AddLine(Pnt8, Pnt5)
                Line5.color = VbCopy(acGreen)
                Line5.Linetype = "Hidden"
            Line6 = ThisDrawing.ModelSpace.AddLine(Pnt10, Pnt4)
                Line6.color = VbCopy(acRed)
                Line6.Linetype = "Center"
            Line7 = ThisDrawing.ModelSpace.AddLine(Pnt11, Pnt2)
                Line7.color = VbCopy(acGreen)
                Line7.Linetype = "Hidden"
            Line8 = ThisDrawing.ModelSpace.AddLine(Pnt12, Pnt1)
                Line8.color = VbCopy(acGreen)
                Line8.Linetype = "Hidden"

            Line9 = ThisDrawing.ModelSpace.AddLine(Pnt14, Pnt25)
                Line9.color = VbCopy(acGreen)
                Line9.Linetype = "Hidden"
            Line10 = ThisDrawing.ModelSpace.AddLine(Pnt15, Pnt24)
                Line10.color = VbCopy(acGreen)
                Line10.Linetype = "Hidden"
            Line11 = ThisDrawing.ModelSpace.AddLine(Pnt17, Pnt23)
                Line11.color = VbCopy(acRed)
                Line11.Linetype = "Center"
            Line12 = ThisDrawing.ModelSpace.AddLine(Pnt18, Pnt21)
                Line12.color = VbCopy(acGreen)
                Line12.Linetype = "Hidden"

                Line5.Update
                Line6.Update
                Line7.Update
                Line8.Update
                Line9.Update
                Line10.Update
                Line11.Update
                Line12.Update

        ' 치수 Point 할당
        If frmInput.optDirect.Value Then ' 직결구동일 경우
                If Direction = "RH" Then
                    dimP4 = VbCopy(Pnt20)
                End If

                If Direction = "RL" Then
                    If FrontRecFlange Then
                        dimP5 = VbCopy(Pnt20)
                        dimP6 = VbCopy(Pnt25)
                        dimP7 = VbCopy(Pnt1)
                        FrontRecFlange = False

                        ElseIf PlanRecFlange Then
                            dimP12 = VbCopy(Pnt1)
                            dimP13 = VbCopy(Pnt25)
                            PlanRecFlange = False
                    End If
                End If

                If Direction = "RR" Then
                    dimP5 = VbCopy(Pnt6)
                End If

                If Direction = "LH" Then
                    dimP4 = VbCopy(Pnt20)
                End If

                If Direction = "LL" Then
                    If FrontRecFlange Then
                        dimP5 = VbCopy(Pnt20)
                        dimP6 = VbCopy(Pnt25)
                        dimP7 = VbCopy(Pnt1)
                        FrontRecFlange = False

                        ElseIf PlanRecFlange Then
                        dimP12 = VbCopy(Pnt25)
                        dimP13 = VbCopy(Pnt1)
                        PlanRecFlange = False
                    End If
                End If

                If Direction = "LR" Then
                    If FrontRecFlange Then
                        dimP4 = VbCopy(Pnt25)
                        dimP5 = VbCopy(Pnt1)
                        dimP7 = VbCopy(Pnt6)
                        FrontRecFlange = False

                        ElseIf PlanRecFlange Then
                        dimP15 = VbCopy(Pnt25)
                        dimP16 = VbCopy(Pnt1)
                        PlanRecFlange = False
                    End If
                End If

            Else ' V-Belt 구동일 경우
                If FrontRecFlange Then
                    dimP6 = VbCopy(Pnt1)
                    dimP7 = VbCopy(Pnt25)
                    dimP9 = VbCopy(Pnt20)
                    FrontRecFlange = False

                    ElseIf PlanRecFlange Then
                        dimP15 = VbCopy(Pnt1)
                        dimP16 = VbCopy(Pnt25)
                        PlanRecFlange = False

                    ElseIf RightRecFlange Then
                        dimP28 = VbCopy(Pnt6)
                        RightRecFlange = False

                End If

        End If

    End Sub

    Public Sub DrawPlan() ' 평면도 작성
        Dim L As Double
        Dim W As Double
        Dim CL As Double
        Dim CW As Double
        Dim OL As Double
        Dim OW As Double
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
        Dim rFlangeEnt As Object
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
        Dim Cir1 As Object
        Dim Cir2 As Object
        Dim Cir3 As Object
        Dim Cir4 As Object
        Dim Pitch As Double
        Dim LBN As Integer
        Dim WBN As Integer
        Dim vSpace As Double
        Dim hSpace As Double

        pntCol = New VBCollection

            L = VbCopy(idLength)
            W = VbCopy(idWidth)
            CL = L + B
            CW = W + B
            OL = L + 2 * B
            OW = W + 2 * B




            P1 = PolarPoint(CP, Dtr(RotAng + 90), W / 2)
            P2 = PolarPoint(CP, Dtr(RotAng + 90), CW / 2)
            P3 = PolarPoint(CP, Dtr(RotAng + 90), OW / 2)
            P4 = PolarPoint(P1, Dtr(RotAng + 180), L / 2)
            P5 = PolarPoint(P4, Dtr(RotAng + 270), W)

            P6 = PolarPoint(P5, Dtr(RotAng + 0), L)
            P7 = PolarPoint(P6, Dtr(RotAng + 90), W)
            P8 = PolarPoint(P2, Dtr(RotAng + 180), CL / 2)
            P9 = PolarPoint(P8, Dtr(RotAng + 270), CW)
            P10 = PolarPoint(P9, Dtr(RotAng + 0), CL)

            P11 = PolarPoint(P10, Dtr(RotAng + 90), CW)
            P12 = PolarPoint(P3, Dtr(RotAng + 180), OL / 2)
            P13 = PolarPoint(P12, Dtr(RotAng + 270), OW)
            P14 = PolarPoint(P13, Dtr(RotAng + 0), OL)
            P15 = PolarPoint(P14, Dtr(RotAng + 90), OW)

            If Left(Direction, 2) <> "RL" And Left(Direction, 2) <> "LL" Then

                pntCol.Add(P12)
                pntCol.Add(P13)
                pntCol.Add(P14)
                pntCol.Add(P15)

                MakePntArray

                rFlangeEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
                With rFlangeEnt
                    .Closed = True
                    .Highlight(True)
                    .Update
                End With

                AutoTrim.Ent = rFlangeEnt
                AutoTrim.DoTrim
                rFlangeEnt.Delete

            End If





            Line1 = ThisDrawing.ModelSpace.AddLine(P4, P7)
            Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P5, P4)
            Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P5, P6)
            Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(P6, P7)
            Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P8, P11)
                Line5.color = VbCopy(acRed)
                Line5.Linetype = "Center"
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P8, P9)
                Line6.color = VbCopy(acRed)
                Line6.Linetype = "Center"
                Line6.Update
            Line7 = ThisDrawing.ModelSpace.AddLine(P9, P10)
                Line7.color = VbCopy(acRed)
                Line7.Linetype = "Center"
                Line7.Update
            Line8 = ThisDrawing.ModelSpace.AddLine(P10, P11)
                Line8.color = VbCopy(acRed)
                Line8.Linetype = "Center"
                Line8.Update

            Line9 = ThisDrawing.ModelSpace.AddLine(P12, P15)
            Line9.Update
            Line10 = ThisDrawing.ModelSpace.AddLine(P13, P12)
            Line10.Update
            Line11 = ThisDrawing.ModelSpace.AddLine(P13, P14)
            Line11.Update
            Line12 = ThisDrawing.ModelSpace.AddLine(P14, P15)
            Line12.Update

        ' Bolt Hole 그리기
            Cir1 = ThisDrawing.ModelSpace.AddCircle(P8, BD / 2)
            Cir1.color = VbCopy(acCyan)
            Cir1.Update
            Cir2 = ThisDrawing.ModelSpace.AddCircle(P9, BD / 2)
            Cir2.color = VbCopy(acCyan)
            Cir2.Update
            Cir3 = ThisDrawing.ModelSpace.AddCircle(P10, BD / 2)
            Cir3.color = VbCopy(acCyan)
            Cir3.Update
            Cir4 = ThisDrawing.ModelSpace.AddCircle(P11, BD / 2)
            Cir4.color = VbCopy(acCyan)
            Cir4.Update


        ' Bolt Hole Pitch 계산
            Pitch = 140 * ((B * t ^ 3) / 36450) ^ (1 / 3) '원래 120


        ' Bolt Hole 수 계산
            LBN = Int(CL / Pitch) + 1
            WBN = Int(CW / Pitch) + 1
            vSpace = CW / WBN
            hSpace = CL / LBN

        If RotAng = 0 Then
            Cir1.ArrayRectangular(1, LBN, 1, 0, hSpace, 1)
            Cir2.ArrayRectangular(1, LBN, 1, 0, hSpace, 1)
            Cir2.ArrayRectangular(WBN, 1, 1, vSpace, 0, 1)
            Cir3.ArrayRectangular(WBN, 1, 1, vSpace, 0, 1)

            ElseIf RotAng = -90 Then
                Cir2.ArrayRectangular(1, LBN, 1, 0, hSpace, 1)
                Cir3.ArrayRectangular(1, LBN, 1, 0, hSpace, 1)
                Cir3.ArrayRectangular(WBN, 1, 1, vSpace, 0, 1)
                Cir4.ArrayRectangular(WBN, 1, 1, vSpace, 0, 1)
        End If

        If CallFromPCP7 Then
            pCenP7 = VbCopy(P3)
            pCenP8 = PolarPoint(P3, Dtr(RotAng + 270), idWidth + 2 * B)
            CallFromPCP7 = False
        End If

        If CallFromRCP7 Then
            rCenP7 = VbCopy(P3)
            rCenP8 = PolarPoint(P3, Dtr(RotAng + 270), idWidth + 2 * B)
            CallFromRCP7 = False
        End If

        ' 치수점 할당
        If frmInput.optDirect.Value Then ' 직결형일 때

            If Direction = "RH" Then
                dimP11 = VbCopy(P4)
                dimP12 = VbCopy(P5)
                dimP13 = VbCopy(P6)
            End If

            If Direction = "RR" Then
                dimP14 = VbCopy(P5)
                dimP15 = VbCopy(P4)
                dimP16 = VbCopy(P6)
            End If

            If Direction = "LH" Then
                dimP11 = VbCopy(P5)
                dimP12 = VbCopy(P6)
                dimP13 = VbCopy(P7)
            End If

            Else ' V=Belt 전동시
                If Left(Direction, 1) = "R" Then
                    dimP15 = VbCopy(P5)
                    dimP16 = VbCopy(P4)

                    Else
                    dimP15 = VbCopy(P6)
                    dimP16 = VbCopy(P7)
                End If

        End If

    End Sub

    Public Sub DrawRight() ' 우측면도 작성
        Dim pcd As Double
        Dim OD As Double
        Dim Pnt1 As Object
        Dim Pnt2 As Object
        Dim Pnt3 As Object
        Dim Pnt4 As Object
        Dim Pnt5 As Object
        Dim Pnt6 As Object
        Dim Pnt7 As Object
        Dim Pnt8 As Object
        Dim Pnt9 As Object
        Dim Pnt10 As Object
        Dim Pnt11 As Object
        Dim Pnt12 As Object
        Dim Pnt13 As Object
        Dim Pnt14 As Object
        Dim Pnt15 As Object
        Dim Pnt16 As Object
        Dim Pnt17 As Object
        Dim Pnt18 As Object
        Dim Pnt19 As Object
        Dim Pnt20 As Object
        Dim Pnt21 As Object
        Dim Pnt22 As Object
        Dim Pnt23 As Object
        Dim Pnt24 As Object
        Dim Pnt25 As Object
        Dim rFlangeEnt As Object
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

        pntCol = New VBCollection

        ' pcd 계산
            pcd = idWidth + B
        ' od 계산
            OD = idWidth + 2 * B

        ' Point Calculation





            Pnt1 = PolarPoint(CP, Dtr(RotAng + 180), idWidth / 2)
            Pnt2 = PolarPoint(CP, Dtr(RotAng + 180), (pcd - BD) / 2)
            Pnt3 = PolarPoint(CP, Dtr(RotAng + 180), pcd / 2)
            Pnt4 = PolarPoint(Pnt3, Dtr(RotAng + 90), t)
            Pnt5 = PolarPoint(Pnt3, Dtr(RotAng + 180), BD / 2)

            Pnt6 = PolarPoint(CP, Dtr(RotAng + 180), OD / 2)
            Pnt7 = PolarPoint(Pnt6, Dtr(RotAng + 270), t)
            Pnt8 = PolarPoint(Pnt5, Dtr(RotAng + 270), t)
            Pnt9 = PolarPoint(Pnt3, Dtr(RotAng + 270), t)
            Pnt10 = PolarPoint(Pnt9, Dtr(RotAng + 270), t)

            Pnt11 = PolarPoint(Pnt2, Dtr(RotAng + 270), t)
            Pnt12 = PolarPoint(Pnt1, Dtr(RotAng + 270), t)
            Pnt13 = PolarPoint(CP, Dtr(RotAng + 270), t)
            Pnt14 = PolarPoint(Pnt13, Dtr(RotAng + 0), idWidth / 2)
            Pnt15 = PolarPoint(Pnt13, Dtr(RotAng + 0), (pcd - BD) / 2)

            Pnt16 = PolarPoint(Pnt15, Dtr(RotAng + 0), BD / 2)
            Pnt17 = PolarPoint(Pnt16, Dtr(RotAng + 270), t)
            Pnt18 = PolarPoint(Pnt16, Dtr(RotAng + 0), BD / 2)
            Pnt19 = PolarPoint(Pnt13, Dtr(RotAng + 0), OD / 2)
            Pnt20 = PolarPoint(Pnt19, Dtr(RotAng + 90), t)

            Pnt21 = PolarPoint(Pnt18, Dtr(RotAng + 90), t)
            Pnt22 = PolarPoint(Pnt16, Dtr(RotAng + 90), t)
            Pnt23 = PolarPoint(Pnt22, Dtr(RotAng + 90), t)
            Pnt24 = PolarPoint(Pnt15, Dtr(RotAng + 90), t)
            Pnt25 = PolarPoint(Pnt14, Dtr(RotAng + 90), t)

            pntCol.Add(Pnt6)
            pntCol.Add(Pnt7)
            pntCol.Add(Pnt19)
            pntCol.Add(Pnt20)

            MakePntArray

            rFlangeEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
            With rFlangeEnt
                .Closed = True
                .Highlight(True)
                .Update
            End With

            AutoTrim.Ent = rFlangeEnt
            AutoTrim.DoTrim
            rFlangeEnt.Delete




            Line1 = ThisDrawing.ModelSpace.AddLine(Pnt6, Pnt20)
            Line2 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt6)
            Line3 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt19)
            Line4 = ThisDrawing.ModelSpace.AddLine(Pnt19, Pnt20)
                Line1.color = VbCopy(acCyan)
                Line2.color = VbCopy(acCyan)
                Line3.color = VbCopy(acCyan)
                Line4.color = VbCopy(acCyan)

                Line1.Update
                Line2.Update
                Line3.Update
                Line4.Update

            Line5 = ThisDrawing.ModelSpace.AddLine(Pnt8, Pnt5)
                Line5.color = VbCopy(acGreen)
                Line5.Linetype = "Hidden"
            Line6 = ThisDrawing.ModelSpace.AddLine(Pnt10, Pnt4)
                Line6.color = VbCopy(acRed)
                Line6.Linetype = "Center"
            Line7 = ThisDrawing.ModelSpace.AddLine(Pnt11, Pnt2)
                Line7.color = VbCopy(acGreen)
                Line7.Linetype = "Hidden"
            Line8 = ThisDrawing.ModelSpace.AddLine(Pnt12, Pnt1)
                Line8.color = VbCopy(acGreen)
                Line8.Linetype = "Hidden"

            Line9 = ThisDrawing.ModelSpace.AddLine(Pnt14, Pnt25)
                Line9.color = VbCopy(acGreen)
                Line9.Linetype = "Hidden"
            Line10 = ThisDrawing.ModelSpace.AddLine(Pnt15, Pnt24)
                Line10.color = VbCopy(acGreen)
                Line10.Linetype = "Hidden"
            Line11 = ThisDrawing.ModelSpace.AddLine(Pnt17, Pnt23)
                Line11.color = VbCopy(acRed)
                Line11.Linetype = "Center"
            Line12 = ThisDrawing.ModelSpace.AddLine(Pnt18, Pnt21)
                Line12.color = VbCopy(acGreen)
                Line12.Linetype = "Hidden"

                Line5.Update
                Line6.Update
                Line7.Update
                Line8.Update
                Line9.Update
                Line10.Update
                Line11.Update
                Line12.Update

        ' 치수 Point 할당
        If frmInput.optDirect.Value Then ' 직결구동일 경우
                If Direction = "RH" Then
                    dimP4 = VbCopy(Pnt20)
                End If

                If Direction = "RL" Then
                    If FrontRecFlange Then
                        dimP5 = VbCopy(Pnt20)
                        dimP6 = VbCopy(Pnt25)
                        dimP7 = VbCopy(Pnt1)
                        FrontRecFlange = False

                        ElseIf PlanRecFlange Then
                            dimP12 = VbCopy(Pnt1)
                            dimP13 = VbCopy(Pnt25)
                            PlanRecFlange = False
                    End If
                End If

                If Direction = "RR" Then
                    dimP5 = VbCopy(Pnt6)
                End If

                If Direction = "LH" Then
                    dimP4 = VbCopy(Pnt20)
                End If

                If Direction = "LL" Then
                    If FrontRecFlange Then
                        dimP5 = VbCopy(Pnt20)
                        dimP6 = VbCopy(Pnt25)
                        dimP7 = VbCopy(Pnt1)
                        FrontRecFlange = False

                        ElseIf PlanRecFlange Then
                        dimP12 = VbCopy(Pnt25)
                        dimP13 = VbCopy(Pnt1)
                        PlanRecFlange = False
                    End If
                End If

                If Direction = "LR" Then
                    If FrontRecFlange Then
                        dimP4 = VbCopy(Pnt25)
                        dimP5 = VbCopy(Pnt1)
                        dimP7 = VbCopy(Pnt6)
                        FrontRecFlange = False

                        ElseIf PlanRecFlange Then
                        dimP15 = VbCopy(Pnt25)
                        dimP16 = VbCopy(Pnt1)
                        PlanRecFlange = False
                    End If
                End If

            Else ' V-Belt 구동일 경우
                If FrontRecFlange Then
                    dimP6 = VbCopy(Pnt1)
                    dimP7 = VbCopy(Pnt25)
                    dimP9 = VbCopy(Pnt20)
                    FrontRecFlange = False

                    ElseIf PlanRecFlange Then
                        dimP15 = VbCopy(Pnt1)
                        dimP16 = VbCopy(Pnt25)
                        PlanRecFlange = False

                    ElseIf RightRecFlange Then
                        dimP28 = VbCopy(Pnt6)
                        RightRecFlange = False

                End If

        End If

    End Sub

    Private Sub DataCalculation()

        ' Bolt Hole Pitch 계산
        Pitch = 120 * ((B * t ^ 3) / 36450) ^ (1 / 3)

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
