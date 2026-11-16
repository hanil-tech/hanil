Attribute VB_Name = "cTrimLines"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit
Public TrimEntity As AcadPolyline

Public Sub trim()
    
    Dim IntPnt As Variant
    Dim Ent2 As AcadEntity
    
        For Each Ent2 In ThisDrawing.ModelSpace
            
            IntPnt = TrimEntity.IntersectWith(Ent2, acExtendNone)
            
            If UBound(IntPnt) = 2 And Ent2.ObjectName = "AcDbLine" Then
                
                Dim Line1 As AcadLine
                    Set Line1 = Ent2
                    
                Dim XLine1 As AcadXline
                Dim XLine2 As AcadXline
                Dim XPnt1 As Variant
                Dim XPnt2 As Variant
                
                XPnt1 = ThisDrawing.Utility.PolarPoint(Line1.EndPoint, Dtr(0), 10)
                XPnt2 = ThisDrawing.Utility.PolarPoint(Line1.EndPoint, Dtr(90), 10)
                
                Set XLine1 = ThisDrawing.ModelSpace.AddXline(Line1.EndPoint, XPnt1)
                Set XLine2 = ThisDrawing.ModelSpace.AddXline(Line1.EndPoint, XPnt2)
                        
                Dim intPnt1 As Variant
                Dim intPnt2 As Variant
                    intPnt1 = TrimEntity.IntersectWith(XLine1, acExtendNone)
                    intPnt2 = TrimEntity.IntersectWith(XLine2, acExtendNone)
                    XLine1.Delete
                    XLine2.Delete
                    
                    If UBound(intPnt1) = 5 And UBound(intPnt2) = 5 Then
                        Line1.EndPoint = IntPnt
                        Else
                        Line1.StartPoint = IntPnt
                    End If
            End If
            
            If UBound(IntPnt) = 5 And Ent2.ObjectName = "AcDbLine" Then
                
                Set Line1 = Ent2
                
                Dim FirstPnt(0 To 2) As Double
                Dim SecondPnt(0 To 2) As Double
                    FirstPnt(0) = IntPnt(0)
                    FirstPnt(1) = IntPnt(1)
                    FirstPnt(2) = IntPnt(2)
                    SecondPnt(0) = IntPnt(3)
                    SecondPnt(1) = IntPnt(4)
                    SecondPnt(2) = IntPnt(5)
                Dim NewLine1 As AcadLine
                Dim NewLine2 As AcadLine
                Dim tmpLine1 As AcadLine
                Dim tmpLine2 As AcadLine
                
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Line1.StartPoint, FirstPnt)
                Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(Line1.StartPoint, SecondPnt)
                
                If tmpLine1.Length < tmpLine2.Length Then
                    Set NewLine1 = ThisDrawing.ModelSpace.AddLine(Line1.StartPoint, FirstPnt)
                    Else
                    Set NewLine1 = ThisDrawing.ModelSpace.AddLine(Line1.StartPoint, SecondPnt)
                End If
                tmpLine1.Delete
                tmpLine2.Delete
            
                
                Set tmpLine1 = ThisDrawing.ModelSpace.AddLine(Line1.EndPoint, FirstPnt)
                Set tmpLine2 = ThisDrawing.ModelSpace.AddLine(Line1.EndPoint, SecondPnt)
                
                If tmpLine1.Length < tmpLine2.Length Then
                    Set NewLine1 = ThisDrawing.ModelSpace.AddLine(Line1.EndPoint, FirstPnt)
                    Else
                    Set NewLine1 = ThisDrawing.ModelSpace.AddLine(Line1.EndPoint, SecondPnt)
                End If
                tmpLine1.Delete
                tmpLine2.Delete
                Line1.Delete
            
            End If
            
        Next
        
End Sub

Private Function Dtr(Angle As Double) As Double

    Dtr = Angle * (Atn(1) * 4) / 180#
    
End Function


