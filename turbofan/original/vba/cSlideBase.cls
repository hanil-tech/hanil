Attribute VB_Name = "cSlideBase"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

Public CP As Variant
Dim SBPntCol As New Collection
Dim SBEnt As AcadPolyline
Dim pntArray() As Double

Public Sub DrawPlan()
    
    Set SBPntCol = Nothing
    
    Dim L As Double
    Dim Seta As Double
    Dim dDist As Double
        Seta = Atn(((D3 - 2 * FanBase.B - BBaseW) / 2) / (FanCasing.cHeight - SN3.H))
        dDist = FanBase.H * Tan(Seta)
        L = MDist + FanBase.B + dDist
    Dim SBAng As Double
    Dim P1 As Variant
    Dim P2 As Variant
    Dim P3 As Variant
    Dim P4 As Variant
    Dim P5 As Variant
    Dim P6 As Variant
    Dim P7 As Variant
    Dim P8 As Variant
        
        If Right$(Direction, 1) = "L" Then
            SBAng = 0
            Else
            SBAng = 180
        End If
        
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(270), Motor.C - 20 - FanBase.Y1 + FanBase.B)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270), FanBase.B)
        
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(270), Motor.B - 2 * FanBase.Y2)
        P4 = ThisDrawing.Utility.PolarPoint(P3, Dtr(270), FanBase.B)
        
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(SBAng), L)
        P6 = ThisDrawing.Utility.PolarPoint(P3, Dtr(SBAng), L)
        P7 = ThisDrawing.Utility.PolarPoint(P2, Dtr(SBAng), L)
        P8 = ThisDrawing.Utility.PolarPoint(P1, Dtr(SBAng), L)
        
        SBPntCol.Add P1
        SBPntCol.Add P2
        SBPntCol.Add P7
        SBPntCol.Add P8
        
        MakePntArray
        Set SBEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        SBEnt.Closed = True
        SBEnt.Highlight True
        ThisDrawing.Application.Update
        
        Set AutoTrim.Ent = SBEnt
        AutoTrim.DoTrim
        SBEnt.Delete
        
        Set SBPntCol = Nothing
        SBPntCol.Add P3
        SBPntCol.Add P4
        SBPntCol.Add P5
        SBPntCol.Add P6
        MakePntArray
        Set SBEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        SBEnt.Closed = True
        SBEnt.Highlight True
        ThisDrawing.Application.Update
        
        Set AutoTrim.Ent = SBEnt
        AutoTrim.DoTrim
        
        SBEnt.Delete
        
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    Dim Line5 As AcadLine
    Dim Line6 As AcadLine
    Dim Line7 As AcadLine
    Dim Line8 As AcadLine
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P1, P8)
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P8, P7)
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P7, P2)
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P2, P1)
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P3, P6)
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P6, P5)
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P5, P4)
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P4, P3)
    
End Sub

Sub MakePntArray()
        
    ReDim pntArray(SBPntCol.Count * 3 - 1)
    Dim i As Integer
    Dim pnt As Variant
    
    For i = 1 To SBPntCol.Count
        
        pnt = SBPntCol.Item(i)
            
        pntArray(0 + (i - 1) * 3) = pnt(0)
        pntArray(1 + (i - 1) * 3) = pnt(1)
        pntArray(2 + (i - 1) * 3) = pnt(2)
            
    Next i
        
End Sub
