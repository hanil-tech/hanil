' 원본: cSlideBase.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cSlideBase

    Public CP As Object
    Dim SBPntCol As New VBCollection
    Dim SBEnt As Object
    Dim pntArray() As Double

    Public Sub DrawPlan()
        Dim L As Double
        Dim Seta As Double
        Dim dDist As Double
        Dim SBAng As Double
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
        Dim Line3 As Object
        Dim Line4 As Object
        Dim Line5 As Object
        Dim Line6 As Object
        Dim Line7 As Object
        Dim Line8 As Object

        SBPntCol = New VBCollection

            Seta = Atn(((D3 - 2 * FanBase.B - BBaseW) / 2) / (FanCasing.cHeight - SN3.H))
            dDist = FanBase.H * Tan(Seta)
            L = MDist + FanBase.B + dDist

            If Right(Direction, 1) = "L" Then
                SBAng = 0
                Else
                SBAng = 180
            End If

            P1 = PolarPoint(CP, Dtr(270), Motor.C - 20 - FanBase.Y1 + FanBase.B)
            P2 = PolarPoint(P1, Dtr(270), FanBase.B)

            P3 = PolarPoint(P2, Dtr(270), Motor.B - 2 * FanBase.Y2)
            P4 = PolarPoint(P3, Dtr(270), FanBase.B)

            P5 = PolarPoint(P4, Dtr(SBAng), L)
            P6 = PolarPoint(P3, Dtr(SBAng), L)
            P7 = PolarPoint(P2, Dtr(SBAng), L)
            P8 = PolarPoint(P1, Dtr(SBAng), L)

            SBPntCol.Add(P1)
            SBPntCol.Add(P2)
            SBPntCol.Add(P7)
            SBPntCol.Add(P8)

            MakePntArray
            SBEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
            SBEnt.Closed = True
            SBEnt.Highlight(True)
            ThisDrawing.Application.Update

            AutoTrim.Ent = SBEnt
            AutoTrim.DoTrim
            SBEnt.Delete

            SBPntCol = New VBCollection
            SBPntCol.Add(P3)
            SBPntCol.Add(P4)
            SBPntCol.Add(P5)
            SBPntCol.Add(P6)
            MakePntArray
            SBEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
            SBEnt.Closed = True
            SBEnt.Highlight(True)
            ThisDrawing.Application.Update

            AutoTrim.Ent = SBEnt
            AutoTrim.DoTrim

            SBEnt.Delete

            Line1 = ThisDrawing.ModelSpace.AddLine(P1, P8)
            Line2 = ThisDrawing.ModelSpace.AddLine(P8, P7)
            Line3 = ThisDrawing.ModelSpace.AddLine(P7, P2)
            Line4 = ThisDrawing.ModelSpace.AddLine(P2, P1)
            Line5 = ThisDrawing.ModelSpace.AddLine(P3, P6)
            Line6 = ThisDrawing.ModelSpace.AddLine(P6, P5)
            Line7 = ThisDrawing.ModelSpace.AddLine(P5, P4)
            Line8 = ThisDrawing.ModelSpace.AddLine(P4, P3)

    End Sub

    Sub MakePntArray()
        Dim i As Integer
        Dim pnt As Object

        ReDim pntArray(SBPntCol.Count * 3 - 1)

        For i = 1 To SBPntCol.Count

            pnt = SBPntCol.Item(i)

            pntArray(0 + (i - 1) * 3) = pnt(0)
            pntArray(1 + (i - 1) * 3) = pnt(1)
            pntArray(2 + (i - 1) * 3) = pnt(2)

        Next i

    End Sub

End Class
