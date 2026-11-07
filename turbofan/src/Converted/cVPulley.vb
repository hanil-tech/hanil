' 원본: cVPulley.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cVPulley

    Public CP As Object
    Public BeltType As String
    Public Size As Double
    Public PCS As Integer
    Public RotAng As Double
    Public IsFanPulley As Boolean
    Public IsPlan As Boolean

    Dim Ang As Double
    Dim W As Double
    Dim H As Double
    Dim E As Double
    Dim F As Double
    Dim a As Double
    Dim B As Double
    Dim C As Double
    Dim d As Double

    Dim USP As Object
    Dim LSP As Object

    Dim VPSize As Double
    Dim EntCol As New VBCollection
    Dim Ent As Object
    Dim regionObj As Object
    Dim tmpPnt As Object


    Public Sub DrawPulley()
        Dim i As Integer
        Dim aLine As Object
        Dim SelPnt As Object
        Dim Lines() As Object
        Dim regionEnt As Object
        Dim ExplodedObj As Object

        EntCol = New VBCollection ' EntCol을 비움


        ReadData

        LeftSide

        For i = 1 To PCS
            VNotch
            If i < PCS Then Gab
        Next i

        RightSide


        ' Pulley를 Region으로 만듬
        ReDim Lines(EntCol.Count - 1)

        For i = 1 To EntCol.Count
            Lines(i - 1) = EntCol.Item(i)
        Next i

        ' Create the region
        regionObj = ThisDrawing.ModelSpace.AddRegion(Lines)
        regionObj(0).color = VbCopy(acCyan)

        regionEnt = regionObj(0)

        ' Pulley를 지움
        For Each Ent In EntCol
            Ent.Delete
        Next


        AutoTrim.Ent = regionEnt
        AutoTrim.DoTrim

            ExplodedObj = regionObj(0).Explode
            regionObj(0).Delete

    End Sub

    Private Sub LeftSide()
        Dim P1 As Object
        Dim P2 As Object
        Dim P3 As Object
        Dim P4 As Object
        Dim BeltCoverGap As Double
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object


            P1 = PolarPoint(CP, Dtr(RotAng + 270), VPSize / 2)
            P2 = PolarPoint(CP, Dtr(RotAng + 90), VPSize / 2)
            P3 = PolarPoint(P2, Dtr(RotAng + 0), a)
            P4 = PolarPoint(P1, Dtr(RotAng + 0), a)

        Select Case D2no
            Case 0 To 3
                BeltCoverGap = 25
            Case 3 To 5
                BeltCoverGap = 50
            Case 5 To 8
                BeltCoverGap = 75
            Case Is > 8
                BeltCoverGap = 100
        End Select
        If IsPlan = True Then '평면도라면
            If IsFanPulley = True Then
                If Right(Direction, 1) = "L" Then
                    tmpPnt = PolarPoint(P1, Dtr(RotAng + 270), BeltCoverGap) '벨트커버 작도용
                    BeltCoverPntCol.Add(tmpPnt, "4")
                Else
                    tmpPnt = PolarPoint(P2, Dtr(RotAng + 90), BeltCoverGap) '벨트커버 작도용
                    BeltCoverPntCol.Add(tmpPnt, "1")
                End If
            Else
                If Right(Direction, 1) = "L" Then
                    tmpPnt = PolarPoint(P2, Dtr(RotAng + 90), BeltCoverGap) '벨트커버 작도용
                    BeltCoverPntCol.Add(tmpPnt, "1")
                Else
                    tmpPnt = PolarPoint(P1, Dtr(RotAng + 270), BeltCoverGap) '벨트커버 작도용
                    BeltCoverPntCol.Add(tmpPnt, "4")
                End If
            End If
        Else '우측면도라면
            If IsFanPulley = True Then
                tmpPnt = PolarPoint(P2, Dtr(RotAng + 90), BeltCoverGap) '벨트커버 작도용
                BeltCoverPntCol.Add(tmpPnt, "1")
            Else
                tmpPnt = PolarPoint(P1, Dtr(RotAng + 270), BeltCoverGap) '벨트커버 작도용
                BeltCoverPntCol.Add(tmpPnt, "4")
            End If
        End If

            Line1 = ThisDrawing.ModelSpace.AddLine(P4, P1)
                Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P1, P2)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P2, P3)
                Line3.Update

        ' 생성된 Entity를 EntCol에 저장
        EntCol.Add(Line1)
        EntCol.Add(Line2)
        EntCol.Add(Line3)

        ' 다음 작도의 시작점을 지정
        USP = VbCopy(P3)
        LSP = VbCopy(P4)

    End Sub

    Private Sub RightSide()
        Dim P1 As Object
        Dim P2 As Object
        Dim BeltCoverGap As Double
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object
        Select Case D2no
            Case 0 To 3
                BeltCoverGap = 25
            Case 3 To 5
                BeltCoverGap = 50
            Case 5 To 8
                BeltCoverGap = 75
            Case Is > 8
                BeltCoverGap = 100
        End Select

            P1 = PolarPoint(USP, Dtr(RotAng + 0), a)
            P2 = PolarPoint(LSP, Dtr(RotAng + 0), a)

        If IsPlan = True Then '평면도라면
            If IsFanPulley = True Then
                If Right(Direction, 1) = "L" Then
                    tmpPnt = PolarPoint(P2, Dtr(RotAng + 0), BeltCoverGap) '벨트커버 작도용
                    tmpPnt = PolarPoint(tmpPnt, Dtr(RotAng + 270), BeltCoverGap)
                    BeltCoverPntCol.Add(tmpPnt, "3")
                Else
                    tmpPnt = PolarPoint(P1, Dtr(RotAng + 0), BeltCoverGap) '벨트커버 작도용
                    tmpPnt = PolarPoint(tmpPnt, Dtr(RotAng + 90), BeltCoverGap)
                    BeltCoverPntCol.Add(tmpPnt, "2")
                End If
            Else
                If Right(Direction, 1) = "L" Then
                    tmpPnt = PolarPoint(P1, Dtr(RotAng + 0), BeltCoverGap) '벨트커버 작도용
                    tmpPnt = PolarPoint(tmpPnt, Dtr(RotAng + 90), BeltCoverGap)
                    BeltCoverPntCol.Add(tmpPnt, "2")
                Else
                    tmpPnt = PolarPoint(P2, Dtr(RotAng + 0), BeltCoverGap) '벨트커버 작도용
                    tmpPnt = PolarPoint(tmpPnt, Dtr(RotAng + 270), BeltCoverGap)
                    BeltCoverPntCol.Add(tmpPnt, "3")
                End If
            End If
        Else '우측면도라면
            If IsFanPulley = True Then
                tmpPnt = PolarPoint(P1, Dtr(RotAng + 0), BeltCoverGap) '벨트커버 작도용
                tmpPnt = PolarPoint(tmpPnt, Dtr(RotAng + 90), BeltCoverGap)
                BeltCoverPntCol.Add(tmpPnt, "2")
            Else
                tmpPnt = PolarPoint(P2, Dtr(RotAng + 0), BeltCoverGap) '벨트커버 작도용
                tmpPnt = PolarPoint(tmpPnt, Dtr(RotAng + 270), BeltCoverGap)
                BeltCoverPntCol.Add(tmpPnt, "3")
            End If
        End If

            Line1 = ThisDrawing.ModelSpace.AddLine(USP, P1)
                Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P1, P2)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P2, LSP)
                Line3.Update

        ' 생성된 Entity를 EntCol에 저장
        EntCol.Add(Line1)
        EntCol.Add(Line2)
        EntCol.Add(Line3)

        If CallFromPCP2 Then
            pCenP2 = PolarPoint(P1, Dtr(RotAng + 270), VPSize / 2)
            CallFromPCP2 = False
        End If
        If CallFromPCP4 Then
            pCenP4 = PolarPoint(P1, Dtr(RotAng + 270), VPSize / 2)
            CallFromPCP4 = False
        End If
        If CallFromRCP2 Then
            rCenP2 = PolarPoint(P1, Dtr(RotAng + 270), VPSize / 2)
            CallFromRCP2 = False
        End If
        If CallFromRCP4 Then
            rCenP4 = PolarPoint(P1, Dtr(RotAng + 270), VPSize / 2)
            CallFromRCP4 = False
        End If


    End Sub

    Private Sub VNotch()
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
        Dim Line1 As Object
        Dim Line2 As Object
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim Line6 As Object

            P1 = PolarPoint(USP, Dtr(RotAng + 270), H)
            P2 = PolarPoint(P1, Dtr(RotAng + 0), B)
            P3 = PolarPoint(P2, Dtr(RotAng + 0), C)
            P4 = PolarPoint(P3, Dtr(RotAng + 0), B)
            P5 = PolarPoint(P4, Dtr(RotAng + 90), H)

            P6 = PolarPoint(LSP, Dtr(RotAng + 90), H)
            P7 = PolarPoint(P6, Dtr(RotAng + 0), B)
            P8 = PolarPoint(P7, Dtr(RotAng + 0), C)
            P9 = PolarPoint(P8, Dtr(RotAng + 0), B)
            P10 = PolarPoint(P9, Dtr(RotAng + 270), H)


            Line1 = ThisDrawing.ModelSpace.AddLine(USP, P2)
                Line1.Update
            Line2 = ThisDrawing.ModelSpace.AddLine(P2, P3)
                Line2.Update
            Line3 = ThisDrawing.ModelSpace.AddLine(P3, P5)
                Line3.Update
            Line4 = ThisDrawing.ModelSpace.AddLine(LSP, P7)
                Line4.Update
            Line5 = ThisDrawing.ModelSpace.AddLine(P7, P8)
                Line5.Update
            Line6 = ThisDrawing.ModelSpace.AddLine(P8, P10)
                Line6.Update

        ' 생성된 Entity를 EntCol에 저장
        EntCol.Add(Line1)
        EntCol.Add(Line2)
        EntCol.Add(Line3)
        EntCol.Add(Line4)
        EntCol.Add(Line5)
        EntCol.Add(Line6)

        '다음 작도의 시작점을 지정
        USP = VbCopy(P5)
        LSP = VbCopy(P10)

    End Sub

    Private Sub Gab()
        Dim P1 As Object
        Dim P2 As Object
        Dim Line1 As Object
        Dim Line2 As Object
            P1 = PolarPoint(USP, Dtr(RotAng + 0), d)
            P2 = PolarPoint(LSP, Dtr(RotAng + 0), d)

            Line1 = ThisDrawing.ModelSpace.AddLine(USP, P1)
            Line2 = ThisDrawing.ModelSpace.AddLine(LSP, P2)

        ' 생성된 Entity를 EntCol에 저장
        EntCol.Add(Line1)
        EntCol.Add(Line2)

        ' 다음 작도를 위해 시작점 지정
        USP = VbCopy(P1)
        LSP = VbCopy(P2)

    End Sub

    Private Sub ReadData()

        VPSize = 25.4 * Size

        Select Case BeltType

            Case "A"
                Select Case VPSize
                    Case Is <= 100
                        Ang = 34
                        W = 11.95
                    Case 100 To 125
                        Ang = 36
                        W = 12.12
                    Case Is > 125
                        Ang = 38
                        W = 12.3
                End Select
                H = 12.5 : E = 15 : F = 10

            Case "B"
                Select Case VPSize
                    Case Is <= 160
                        Ang = 34
                        W = 15.86
                    Case 160 To 200
                        Ang = 36
                        W = 16.07
                    Case Is > 200
                        Ang = 38
                        W = 16.29
                End Select
                H = 15 : E = 19 : F = 12.5

            Case "C"
                Select Case VPSize
                    Case Is <= 250
                        Ang = 34
                        W = 21.18
                    Case 250 To 315
                        Ang = 36
                        W = 21.45
                    Case Is > 315
                        Ang = 38
                        W = 21.72
                End Select
                H = 19 : E = 25.5 : F = 17

            Case "D"
                Select Case VPSize
                    Case Is <= 450
                        Ang = 36
                        W = 30.77
                    Case Is > 450
                        Ang = 38
                        W = 31.14
                End Select
                H = 25 : E = 37 : F = 24

            Case "3V"
                Select Case VPSize
                    Case Is <= 90
                        Ang = 36
                        W = 9.23
                    Case 95 To 150
                        Ang = 38
                        W = 9.24
                    Case 150 To 305
                        Ang = 40
                        W = 9.26
                    Case Is > 305
                        Ang = 42
                        W = 9.28
                End Select
                H = 9 : E = 10.3 : F = 8.7

            Case "5V"
                Select Case VPSize
                    Case Is <= 255
                        Ang = 38
                        W = 15.54
                    Case 255 To 405
                        Ang = 40
                        W = 15.56
                    Case Is > 405
                        Ang = 42
                        W = 15.58
                End Select
                H = 15 : E = 17.5 : F = 12.7
        End Select

        B = H * Tan(Dtr(Ang) / 2)
        C = W - 2 * B
        d = E - 2 * (C / 2 + B)
        a = F - (B + C / 2)

    End Sub

    Private Function Dtr(ByVal Degree As Double) As Double

        Dtr = Atn(1) * 4 * Degree / 180#

    End Function


End Class
