' 원본: cCirFlange.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cCirFlange

    ' Property 선언
    Public CP As Object
    Public ID As Double
    Public B As Integer 'Flange 폭
    Public Thickness As Integer ' Flange 두께
    Public Pitch As Double ' Bolt Hole Pitch
    Public BoltNo As Integer ' Bolt Hole 수
    Public BoltHoleDia As Integer ' Bolt Hole 직경
    Public OutDia As Double
    Public RotAng As Double
    Public Matl As String '송풍기 재질

    Dim pcd As Double
    Dim pntCol As New VBCollection
    Dim pntArray() As Double

    Public Sub DrawPlan() ' 평면도 작도
        Dim Pnt1 As Object ' Bolt Hole 중심점
        Dim ArrayedCir As Object ' Array될 Bolt Hole원 객체저장
        Dim Cir1 As Object ' ID원 객체
        Dim Cir2 As Object ' PCD원 객체
        Dim Cir3 As Object ' OD원 객체
        Dim Cir4 As Object ' Bolt Hole원 객체

        DataCalculation ' Data 계산 루틴 작동


            Pnt1 = PolarPoint(CP, Dtr(90), (ID + B) / 2)


        Cir1 = ThisDrawing.ModelSpace.AddCircle(CP, ID / 2)
        Cir2 = ThisDrawing.ModelSpace.AddCircle(CP, (ID + B) / 2)
            Cir2.color = VbCopy(acRed)
            Cir2.Linetype = "Center"

        Cir3 = ThisDrawing.ModelSpace.AddCircle(CP, ID / 2 + B)
        Cir4 = ThisDrawing.ModelSpace.AddCircle(Pnt1, BoltHoleDia / 2)
            Cir4.color = VbCopy(acCyan)
            Cir4.Rotate(CP, Dtr(180 / BoltNo))
            ArrayedCir = Cir4.ArrayPolar(BoltNo, Dtr(360 - (360 / BoltNo)), CP)



    End Sub

    Public Sub DrawFront() ' 정면도 작성
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
        Dim cirFlangeEnt As Object
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

        DataCalculation ' Data 계산 루틴 작동

        pntCol = New VBCollection






            Pnt1 = PolarPoint(CP, Dtr(RotAng + 180), ID / 2)
            Pnt2 = PolarPoint(CP, Dtr(RotAng + 180), (pcd - BoltHoleDia) / 2)
            Pnt3 = PolarPoint(CP, Dtr(RotAng + 180), pcd / 2)
            Pnt4 = PolarPoint(Pnt3, Dtr(RotAng + 90), Thickness)
            Pnt5 = PolarPoint(Pnt3, Dtr(RotAng + 180), BoltHoleDia / 2)

            Pnt6 = PolarPoint(CP, Dtr(RotAng + 180), OutDia / 2)
            Pnt7 = PolarPoint(Pnt6, Dtr(RotAng + 270), Thickness)
            Pnt8 = PolarPoint(Pnt5, Dtr(RotAng + 270), Thickness)
            Pnt9 = PolarPoint(Pnt3, Dtr(RotAng + 270), Thickness)
            Pnt10 = PolarPoint(Pnt9, Dtr(RotAng + 270), Thickness)

            Pnt11 = PolarPoint(Pnt2, Dtr(RotAng + 270), Thickness)
            Pnt12 = PolarPoint(Pnt1, Dtr(RotAng + 270), Thickness)
            Pnt13 = PolarPoint(CP, Dtr(RotAng + 270), Thickness)
            Pnt14 = PolarPoint(Pnt13, Dtr(RotAng + 0), ID / 2)
            Pnt15 = PolarPoint(Pnt13, Dtr(RotAng + 0), (pcd - BoltHoleDia) / 2)

            Pnt16 = PolarPoint(Pnt15, Dtr(RotAng + 0), BoltHoleDia / 2)
            Pnt17 = PolarPoint(Pnt16, Dtr(RotAng + 270), Thickness)
            Pnt18 = PolarPoint(Pnt16, Dtr(RotAng + 0), BoltHoleDia / 2)
            Pnt19 = PolarPoint(Pnt13, Dtr(RotAng + 0), OutDia / 2)
            Pnt20 = PolarPoint(Pnt19, Dtr(RotAng + 90), Thickness)

            Pnt21 = PolarPoint(Pnt18, Dtr(RotAng + 90), Thickness)
            Pnt22 = PolarPoint(Pnt16, Dtr(RotAng + 90), Thickness)
            Pnt23 = PolarPoint(Pnt22, Dtr(RotAng + 90), Thickness)
            Pnt24 = PolarPoint(Pnt15, Dtr(RotAng + 90), Thickness)
            Pnt25 = PolarPoint(Pnt14, Dtr(RotAng + 90), Thickness)

            pntCol.Add(Pnt6)
            pntCol.Add(Pnt20)
            pntCol.Add(Pnt19)
            pntCol.Add(Pnt7)

            MakePntArray

            cirFlangeEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
            With cirFlangeEnt
                .Closed = True
                .Highlight(True)
                .Update
            End With

            AutoTrim.Ent = cirFlangeEnt
            AutoTrim.DoTrim
            cirFlangeEnt.Delete




            Line1 = ThisDrawing.ModelSpace.AddLine(Pnt6, Pnt20)
            Line2 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt6)
            Line3 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt19)
            Line4 = ThisDrawing.ModelSpace.AddLine(Pnt19, Pnt20)
                Line1.color = VbCopy(acCyan)
                Line2.color = VbCopy(acCyan)
                Line3.color = VbCopy(acCyan)
                Line4.color = VbCopy(acCyan)

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

        ' 치수점 할당
        If frmInput.optDirect.Value = True Then
            If Direction = "RH" Then
                dimP21 = VbCopy(Pnt20)
                dimP22 = VbCopy(Pnt25)
                dimP23 = VbCopy(Pnt1)
            End If

            If Direction = "RL" Then
                If PlanCirFlange Then
                    dimP14 = VbCopy(Pnt25)
                    dimP15 = VbCopy(Pnt1)
                    PlanCirFlange = False

                    ElseIf RightCirFlange Then
                        dimP19 = VbCopy(Pnt20)
                        RightCirFlange = False
                End If
            End If

            If Direction = "RR" Then
                If PlanCirFlange Then
                    dimP11 = VbCopy(Pnt6)
                    PlanCirFlange = False

                    ElseIf RightCirFlange Then
                        dimP25 = VbCopy(Pnt25)
                        dimP26 = VbCopy(Pnt1)
                        RightCirFlange = False
                End If
            End If

            If Direction = "LH" Then
                dimP21 = VbCopy(Pnt20)
                dimP22 = VbCopy(Pnt25)
                dimP23 = VbCopy(Pnt1)
            End If

            If Direction = "LL" Then
                If PlanCirFlange Then
                    dimP15 = VbCopy(Pnt25)
                    dimP16 = VbCopy(Pnt1)
                    PlanCirFlange = False

                    ElseIf RightCirFlange Then
                    dimP23 = VbCopy(Pnt20)
                    RightCirFlange = False
                End If
            End If

            If Direction = "LR" Then
                If PlanCirFlange Then
                    dimP12 = VbCopy(Pnt25)
                    dimP13 = VbCopy(Pnt1)
                    PlanCirFlange = False

                    ElseIf RightCirFlange Then
                    dimP23 = VbCopy(Pnt20)
                End If
            End If

        Else ' V-Belt 전동시
            If PlanCirFlange Then
                dimP12 = VbCopy(Pnt25)
                dimP13 = VbCopy(Pnt1)
                PlanCirFlange = False

                ElseIf RightCirFlange Then
                    dimP24 = VbCopy(Pnt20)
                    RightCirFlange = False
            End If

        End If

    End Sub

    Private Sub DataCalculation()

        ' 평철 규격 선정

            If Matl = "SS400" Or Matl = "STS304" Or Matl = "STS316" Or Matl = "STS316L" Or Matl = "Ti-Alloy" Then

                Select Case ID

                    Case 0 To 250
                        B = 32 : Thickness = 6
                    Case 250 To 450
                        B = 38 : Thickness = 6
                    Case 450 To 600
                        B = 50 : Thickness = 9
                    Case 600 To 950
                        B = 65 : Thickness = 9
                    Case Is > 950
                        B = 75 : Thickness = 12

                End Select

            ElseIf Matl = "F.R.P" Then

                Select Case ID

                    Case 0 To 250
                        B = 50 : Thickness = 12
                    Case 250 To 450
                        B = 50 : Thickness = 14
                    Case 450 To 600
                        B = 65 : Thickness = 15
                    Case 600 To 950
                        B = 65 : Thickness = 15
                    Case Is > 950
                        B = 65 : Thickness = 15

                End Select

            ElseIf Matl = "P.V.C" Then

                Select Case ID

                    Case 0 To 250
                        B = 50 : Thickness = 10
                    Case 250 To 450
                        B = 50 : Thickness = 10
                    Case 450 To 600
                        B = 50 : Thickness = 12
                    Case 600 To 950
                        B = 65 : Thickness = 15
                    Case Is > 950
                        B = 65 : Thickness = 15

                End Select

            End If

        ' pcd 계산

        pcd = ID + B

        ' OutDia 계산

        OutDia = ID + 2 * B


        ' Bolt Hole 직경 선정

        Select Case ID
            Case 0 To 300
                BoltHoleDia = 12
            Case 300 To 700
                BoltHoleDia = 15
            Case Is > 700
                BoltHoleDia = 19
        End Select

        ' Bolt Hole Pitch 계산

        Pitch = 120 * ((B * Thickness ^ 3) / 36450) ^ (1 / 3)

        ' Bolt 수 계산

        BoltNo = Int(((ID + B) * (Atn(1) * 4) / Pitch + 1) / 2) * 2

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
