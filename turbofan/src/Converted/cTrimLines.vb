' 원본: cTrimLines.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cTrimLines
    Public TrimEntity As Object

    Public Sub trim()
        Dim IntPnt As Object
        Dim Ent2 As Object
        Dim Line1 As Object
        Dim XLine1 As Object
        Dim XLine2 As Object
        Dim XPnt1 As Object
        Dim XPnt2 As Object
        Dim intPnt1 As Object
        Dim intPnt2 As Object
        Dim FirstPnt(2) As Double
        Dim SecondPnt(2) As Double
        Dim NewLine1 As Object
        Dim NewLine2 As Object
        Dim tmpLine1 As Object
        Dim tmpLine2 As Object


            For Each Ent2 In ThisDrawing.ModelSpace

                IntPnt = TrimEntity.IntersectWith(Ent2, acExtendNone)

                If UBound(IntPnt) = 2 And Ent2.ObjectName = "AcDbLine" Then

                        Line1 = Ent2


                    XPnt1 = PolarPoint(Line1.EndPoint, Dtr(0), 10)
                    XPnt2 = PolarPoint(Line1.EndPoint, Dtr(90), 10)

                    XLine1 = ThisDrawing.ModelSpace.AddXline(Line1.EndPoint, XPnt1)
                    XLine2 = ThisDrawing.ModelSpace.AddXline(Line1.EndPoint, XPnt2)

                        intPnt1 = TrimEntity.IntersectWith(XLine1, acExtendNone)
                        intPnt2 = TrimEntity.IntersectWith(XLine2, acExtendNone)
                        XLine1.Delete
                        XLine2.Delete

                        If UBound(intPnt1) = 5 And UBound(intPnt2) = 5 Then
                            Line1.EndPoint = VbCopy(IntPnt)
                            Else
                            Line1.StartPoint = VbCopy(IntPnt)
                        End If
                End If

                If UBound(IntPnt) = 5 And Ent2.ObjectName = "AcDbLine" Then

                    Line1 = Ent2

                        FirstPnt(0) = IntPnt(0)
                        FirstPnt(1) = IntPnt(1)
                        FirstPnt(2) = IntPnt(2)
                        SecondPnt(0) = IntPnt(3)
                        SecondPnt(1) = IntPnt(4)
                        SecondPnt(2) = IntPnt(5)

                    tmpLine1 = ThisDrawing.ModelSpace.AddLine(Line1.StartPoint, FirstPnt)
                    tmpLine2 = ThisDrawing.ModelSpace.AddLine(Line1.StartPoint, SecondPnt)

                    If tmpLine1.Length < tmpLine2.Length Then
                        NewLine1 = ThisDrawing.ModelSpace.AddLine(Line1.StartPoint, FirstPnt)
                        Else
                        NewLine1 = ThisDrawing.ModelSpace.AddLine(Line1.StartPoint, SecondPnt)
                    End If
                    tmpLine1.Delete
                    tmpLine2.Delete


                    tmpLine1 = ThisDrawing.ModelSpace.AddLine(Line1.EndPoint, FirstPnt)
                    tmpLine2 = ThisDrawing.ModelSpace.AddLine(Line1.EndPoint, SecondPnt)

                    If tmpLine1.Length < tmpLine2.Length Then
                        NewLine1 = ThisDrawing.ModelSpace.AddLine(Line1.EndPoint, FirstPnt)
                        Else
                        NewLine1 = ThisDrawing.ModelSpace.AddLine(Line1.EndPoint, SecondPnt)
                    End If
                    tmpLine1.Delete
                    tmpLine2.Delete
                    Line1.Delete

                End If

            Next

    End Sub

    Private Function Dtr(ByVal Angle As Double) As Double

        Dtr = Angle * (Atn(1) * 4) / 180#

    End Function



End Class
