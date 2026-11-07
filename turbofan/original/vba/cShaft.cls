Attribute VB_Name = "cShaft"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit
Public RotAng As Double
Public CP As Variant


Public Sub Draw()
    
    
    Dim P1 As Variant
    Dim P2 As Variant
    Dim P3 As Variant
    Dim P4 As Variant
    
    Dim P5 As Variant
    Dim P6 As Variant
    Dim P7 As Variant
    Dim P8 As Variant
    
    Dim P9 As Variant
    Dim P10 As Variant
    Dim P11 As Variant
    Dim P12 As Variant
    
    Dim P13 As Variant
    Dim P14 As Variant
    
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 180), SN3.Dia2 / 2)
        P1 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 90), 15)
        
        P2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 0), SN3.Dia2 / 2)
        P2 = ThisDrawing.Utility.PolarPoint(P2, Dtr(RotAng + 90), 15)
        
        
        P3 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 90), 25)
        P4 = ThisDrawing.Utility.PolarPoint(P2, Dtr(RotAng + 90), 25)
     
        P5 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), 40 + SN3.a)
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(RotAng + 180), SN3.Dia1 / 2)
        P7 = ThisDrawing.Utility.PolarPoint(P5, Dtr(RotAng + 0), SN3.Dia1 / 2)
        P8 = ThisDrawing.Utility.PolarPoint(P6, Dtr(RotAng + 90), MWidth - 2 * SN3.a - 40)
     
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(RotAng + 0), SN3.Dia1)
        P10 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), MWidth)
        P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(RotAng + 180), SN3.Dia2 / 2)
        P12 = ThisDrawing.Utility.PolarPoint(P10, Dtr(RotAng + 0), SN3.Dia2 / 2)
     
        P13 = ThisDrawing.Utility.PolarPoint(P11, Dtr(RotAng + 90), 20)
        P14 = ThisDrawing.Utility.PolarPoint(P12, Dtr(RotAng + 90), 20)
     
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    Dim Line5 As AcadLine
    Dim Line6 As AcadLine
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P1, P3)
        Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P2, P4)
        Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P6, P8)
        Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P7, P9)
        Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P11, P13)
        Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P12, P14)
        Line6.Update
        
    
End Sub
