Attribute VB_Name = "cFlange"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit


Public ID As Double
Public pcd As Double
Public OD As Double
Public t As Double
Public BHD As Double
Public BN As Integer
Public CP As Variant
Public RotAng As Double

Public Sub PlanDraw()
    
    ' 작도 중심점 입력 받음
    
    Dim P1 As Variant
    P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(90 + 180 / BN), pcd / 2)
    
    ' Entity 생성
    Dim Cir1 As AcadCircle ' ID 작도
    Set Cir1 = ThisDrawing.ModelSpace.AddCircle(CP, ID / 2)
    
    Dim Cir2 As AcadCircle ' PCD 작도
    Set Cir2 = ThisDrawing.ModelSpace.AddCircle(CP, pcd / 2)
    Cir2.color = acRed
    Cir2.Linetype = "CENTER"
    
    Dim Cir3 As AcadCircle ' OD 작도
    Set Cir3 = ThisDrawing.ModelSpace.AddCircle(CP, OD / 2)
    
    Dim Cir4 As AcadCircle ' BoltHole 작도
    Set Cir4 = ThisDrawing.ModelSpace.AddCircle(P1, BHD / 2)
    Cir4.color = acCyan
    
    Dim ArrayedCir As Variant
    Set ArrayedCir = Cir4.ArrayPolar(BN, Dtr(360 * (BN - 1) / BN), CP)
    
    
End Sub

Public Sub FrontDraw()

    ' Line Type Loading
    Dim myLinetype As AcadLineType
    Dim Found As Boolean
    
    Found = False
    For Each myLinetype In ThisDrawing.Linetypes
        If myLinetype.Name = "CENTER" Then
            Found = True
        End If
    Next
    If Not (Found) Then
        ThisDrawing.Linetypes.Load "CENTER", "acad.lin"
    End If
    
    Found = False
    For Each myLinetype In ThisDrawing.Linetypes
        If myLinetype.Name = "HIDDEN" Then
            Found = True
        End If
    Next
    If Not (Found) Then
        ThisDrawing.Linetypes.Load "HIDDEN", "acad.lin"
    End If
    '-----------------------------------------------------------------
    
    ' Point Calculation
    
    Dim P1 As Variant
    P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180 + RotAng), ID / 2)
    Dim P2 As Variant
    P2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180 + RotAng), (pcd - BHD) / 2)
    Dim P3 As Variant
    P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(180 + RotAng), BHD / 2)
    Dim P4 As Variant
    P4 = ThisDrawing.Utility.PolarPoint(P3, Dtr(90 + RotAng), t)
    Dim P5 As Variant
    P5 = ThisDrawing.Utility.PolarPoint(P3, Dtr(180 + RotAng), BHD / 2)
    
    
    Dim P6 As Variant
    P6 = ThisDrawing.Utility.PolarPoint(CP, Dtr(180 + RotAng), OD / 2)
    Dim P7 As Variant
    P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(270 + RotAng), t)
    Dim P8 As Variant
    P8 = ThisDrawing.Utility.PolarPoint(P5, Dtr(270 + RotAng), t)
    Dim P9 As Variant
    P9 = ThisDrawing.Utility.PolarPoint(P3, Dtr(270 + RotAng), t)
    Dim P10 As Variant
    P10 = ThisDrawing.Utility.PolarPoint(P9, Dtr(270 + RotAng), t)
    
    Dim P11 As Variant
    P11 = ThisDrawing.Utility.PolarPoint(P2, Dtr(270 + RotAng), t)
    Dim P12 As Variant
    P12 = ThisDrawing.Utility.PolarPoint(P1, Dtr(270 + RotAng), t)
    Dim P13 As Variant
    P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(0 + RotAng), ID)
    Dim P14 As Variant
    P14 = ThisDrawing.Utility.PolarPoint(P11, Dtr(0 + RotAng), pcd - BHD)
    Dim P15 As Variant
    P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(0 + RotAng), BHD / 2)
    
    Dim P16 As Variant
    P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(270 + RotAng), t)
    Dim P17 As Variant
    P17 = ThisDrawing.Utility.PolarPoint(P15, Dtr(0 + RotAng), BHD / 2)
    Dim P18 As Variant
    P18 = ThisDrawing.Utility.PolarPoint(P7, Dtr(0 + RotAng), OD)
    Dim P19 As Variant
    P19 = ThisDrawing.Utility.PolarPoint(P18, Dtr(90 + RotAng), t)
    Dim P20 As Variant
    P20 = ThisDrawing.Utility.PolarPoint(P17, Dtr(90 + RotAng), t)
    
    Dim P21 As Variant
    P21 = ThisDrawing.Utility.PolarPoint(P15, Dtr(90 + RotAng), t)
    Dim P22 As Variant
    P22 = ThisDrawing.Utility.PolarPoint(P21, Dtr(90 + RotAng), t)
    Dim P23 As Variant
    P23 = ThisDrawing.Utility.PolarPoint(P14, Dtr(90 + RotAng), t)
    Dim P24 As Variant
    P24 = ThisDrawing.Utility.PolarPoint(P13, Dtr(90 + RotAng), t)
    
    ' Entity 생성
    
    ' Continuous Line
    Dim Line1 As AcadLine
    Set Line1 = ThisDrawing.ModelSpace.AddLine(P6, P19)
    Line1.color = acCyan
    
    Dim Line2 As AcadLine
    Set Line2 = ThisDrawing.ModelSpace.AddLine(P6, P7)
    Line2.color = acCyan
    
    Dim Line3 As AcadLine
    Set Line3 = ThisDrawing.ModelSpace.AddLine(P7, P18)
    Line3.color = acCyan
    
    Dim Line4 As AcadLine
    Set Line4 = ThisDrawing.ModelSpace.AddLine(P18, P19)
    Line4.color = acCyan
    
    ' Hidden Line 생성
    Dim Line5 As AcadLine
    Set Line5 = ThisDrawing.ModelSpace.AddLine(P8, P5)
    Line5.color = acGreen
    Line5.Linetype = "HIDDEN"
    
    Dim Line6 As AcadLine
    Set Line6 = ThisDrawing.ModelSpace.AddLine(P11, P2)
    Line6.color = acGreen
    Line6.Linetype = "HIDDEN"
    
    Dim Line7 As AcadLine
    Set Line7 = ThisDrawing.ModelSpace.AddLine(P12, P1)
    Line7.color = acGreen
    Line7.Linetype = "HIDDEN"
    
    Dim Line8 As AcadLine
    Set Line8 = ThisDrawing.ModelSpace.AddLine(P13, P24)
    Line8.color = acGreen
    Line8.Linetype = "HIDDEN"
    
    Dim Line9 As AcadLine
    Set Line9 = ThisDrawing.ModelSpace.AddLine(P14, P23)
    Line9.color = acGreen
    Line9.Linetype = "HIDDEN"
     
    Dim Line10 As AcadLine
    Set Line10 = ThisDrawing.ModelSpace.AddLine(P17, P20)
    Line10.color = acGreen
    Line10.Linetype = "HIDDEN"
    
    ' Center Line 생성
    Dim Line11 As AcadLine
    Set Line11 = ThisDrawing.ModelSpace.AddLine(P10, P4)
    Line11.color = acRed
    Line11.Linetype = "CENTER"
    
    Dim Line12 As AcadLine
    Set Line12 = ThisDrawing.ModelSpace.AddLine(P16, P22)
    Line12.color = acRed
    Line12.Linetype = "CENTER"
    

End Sub

Private Function Dtr(Degree As Double)

    Dtr = (Atn(1) * 4) * Degree / 180#
    
End Function
