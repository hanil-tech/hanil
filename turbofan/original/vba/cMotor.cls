Attribute VB_Name = "cMotor"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

Public FrameNo As String '후렘임 번호
Public CP As Variant ' 삽입점
Public Mirror As Boolean ' 거울 영상 여부
Public C As Double
Public B As Double
Public H As Double
Public DS As Double ' 축직경
Public RotAng As Double
Public AB As Double

Dim pntCol As New Collection

Dim a As Double
Dim AA As Double
Dim AC As Double
Dim AD As Double
Dim AE As Double
Dim BB As Double

Dim HA As Double
Dim HC As Double
Dim K As Double
Dim LB As Double
Dim R1 As Double
Dim R2 As Double
Dim R3 As Double
Dim R4 As Double
Dim R5 As Double
Dim XO As Double
Dim XP As Double

Dim XN As Double
Dim XL As Double
Dim YA As Double
Dim YB As Double
Dim YD As Double
Dim YE As Double
Dim YF As Double
Dim YG As Double
Dim YH As Double
Dim YK As Double

Dim eAng As Double
Dim WAng As Double

Dim pntArray() As Double
Dim MotorEnt As AcadPolyline
Dim MirMotorEnt As AcadPolyline


Public Sub DrawFront() ' 정면도
    
    ReadData ' Motor Data 읽기
    
    If Mirror = False Then
        eAng = 0
        WAng = 180
        Else
        eAng = 180
        WAng = 0
    End If
    

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
    Dim P15 As Variant
    Dim P16 As Variant
    
    Dim P17 As Variant
    Dim P18 As Variant
    Dim P19 As Variant
    Dim P20 As Variant
    
    Dim P21 As Variant
    Dim P22 As Variant
    Dim P23 As Variant
    Dim P24 As Variant
    
    Dim P25 As Variant
    Dim P26 As Variant
    Dim P27 As Variant
    Dim P28 As Variant
    
    Dim P29 As Variant
    Dim P30 As Variant
    Dim P31 As Variant
    Dim P32 As Variant
    
    Dim P33 As Variant
    Dim P34 As Variant
    Dim P35 As Variant
    Dim P36 As Variant
    
        
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), H)
        P2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + WAng), AB / 2)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(RotAng + 90), HA)
        P4 = ThisDrawing.Utility.PolarPoint(P3, Dtr(RotAng + eAng), (AB - a - K) / 2)
        
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(RotAng + eAng), K)
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(RotAng + eAng), AA - ((AB - a - K) / 2 + K))
        
        P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(RotAng + 270), HA)
        P8 = ThisDrawing.Utility.PolarPoint(P5, Dtr(RotAng + 270), HA)
        
        P9 = ThisDrawing.Utility.PolarPoint(P4, Dtr(RotAng + 270), HA)
        P10 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + eAng), AB / 2)
        P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(RotAng + 90), HA)
        P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(RotAng + RotAng + WAng), (AB - a - K) / 2)
        
        P13 = ThisDrawing.Utility.PolarPoint(P12, Dtr(RotAng + WAng), K)
        P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(RotAng + WAng), AA - ((AB - a - K) / 2 + K))
        P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(RotAng + 270), HA)
        P16 = ThisDrawing.Utility.PolarPoint(P13, Dtr(RotAng + 270), HA)
        
        P17 = ThisDrawing.Utility.PolarPoint(P12, Dtr(RotAng + 270), HA)
        P18 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + eAng), AD)
        P19 = ThisDrawing.Utility.PolarPoint(P18, Dtr(RotAng + 270), 0.5 * XL)
        P20 = ThisDrawing.Utility.PolarPoint(P19, Dtr(RotAng + WAng), XO)
        
        P21 = ThisDrawing.Utility.PolarPoint(P20, Dtr(RotAng + 90), (XL - 0.8 * XN) / 2)
        P22 = ThisDrawing.Utility.PolarPoint(P21, Dtr(RotAng + 90), 0.8 * XN)
        P23 = ThisDrawing.Utility.PolarPoint(P22, Dtr(RotAng + 90), (XL - 0.8 * XN) / 2)
        P24 = ThisDrawing.Utility.PolarPoint(P23, Dtr(RotAng + eAng), XO - R1)
        
        P25 = ThisDrawing.Utility.PolarPoint(P24, Dtr(RotAng + 270), R1)
        P26 = ThisDrawing.Utility.PolarPoint(P25, Dtr(RotAng + eAng), R1)
            
        P27 = ThisDrawing.Utility.PolarPoint(P22, Dtr(RotAng + WAng), XP)
        P28 = ThisDrawing.Utility.PolarPoint(P27, Dtr(RotAng + 270), 0.8 * XN)
        
            Dim tmpPnt As Variant
            Dim tmpLine As AcadLine
            Dim tmpCir As AcadCircle
            
        
            ' P29를 구하기 위한 루틴
        If Mirror = False Then
            tmpPnt = ThisDrawing.Utility.PolarPoint(P3, Dtr(RotAng + 60), H)
            Else
            tmpPnt = ThisDrawing.Utility.PolarPoint(P3, Dtr(RotAng + 120), H)
        End If
            Set tmpLine = ThisDrawing.ModelSpace.AddLine(P3, tmpPnt)
            Set tmpCir = ThisDrawing.ModelSpace.AddCircle(P1, R5)
        P29 = tmpLine.IntersectWith(tmpCir, acExtendNone)
            tmpLine.Delete
        
        
        If FrameNo <> "80" And FrameNo <> "90L" And FrameNo <> "100L" Then
            ' P30을 구하기 위한 루틴
        If Mirror = False Then
            tmpPnt = ThisDrawing.Utility.PolarPoint(P7, Dtr(RotAng + 60), H)
            Else
            tmpPnt = ThisDrawing.Utility.PolarPoint(P7, Dtr(RotAng + 120), H)
        End If
        
            Set tmpLine = ThisDrawing.ModelSpace.AddLine(P7, tmpPnt)
        P30 = tmpLine.IntersectWith(tmpCir, acExtendNone)
            tmpLine.Delete
        
            ' P31을 구하기 위한 루틴
        If Mirror = False Then
            tmpPnt = ThisDrawing.Utility.PolarPoint(P15, Dtr(RotAng + 120), H)
            Else
            tmpPnt = ThisDrawing.Utility.PolarPoint(P15, Dtr(RotAng + 60), H)
        End If
        
            Set tmpLine = ThisDrawing.ModelSpace.AddLine(P15, tmpPnt)
        P31 = tmpLine.IntersectWith(tmpCir, acExtendNone)
            tmpLine.Delete
        End If
        
            ' P32를 구하기 위한 루틴
        If Mirror = False Then
            tmpPnt = ThisDrawing.Utility.PolarPoint(P11, Dtr(RotAng + 120), H)
            Else
            tmpPnt = ThisDrawing.Utility.PolarPoint(P11, Dtr(RotAng + 60), H)
        End If
        
            Set tmpLine = ThisDrawing.ModelSpace.AddLine(P11, tmpPnt)
        P32 = tmpLine.IntersectWith(tmpCir, acExtendNone)
            tmpLine.Delete
        P35 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), HA / 2)
        P36 = ThisDrawing.Utility.PolarPoint(P35, Dtr(RotAng + eAng), 10)
            
            ' P33, P34를 구하기 위한 루틴
            Dim StartPnt(0 To 2) As Double
            Dim EndPnt(0 To 2) As Double
            Dim StartLine As AcadLine
            Dim EndLine As AcadLine
            Dim StartAngle As Double
            Dim EndAngle As Double
            Dim IntersectPoint As Variant
            Dim btmLine As AcadXline
            
                Set btmLine = ThisDrawing.ModelSpace.AddXline(P35, P36)
                IntersectPoint = btmLine.IntersectWith(tmpCir, acExtendNone)
                
                StartPnt(0) = IntersectPoint(0)
                StartPnt(1) = IntersectPoint(1)
                StartPnt(2) = IntersectPoint(2)
                
                EndPnt(0) = IntersectPoint(3)
                EndPnt(1) = IntersectPoint(4)
                EndPnt(2) = IntersectPoint(5)
        
        P33 = EndPnt
        P34 = StartPnt
        
                Set StartLine = ThisDrawing.ModelSpace.AddLine(P1, P34)
                Set EndLine = ThisDrawing.ModelSpace.AddLine(P1, P33)
                
                StartAngle = StartLine.Angle
                EndAngle = EndLine.Angle
        
        tmpCir.Delete
        btmLine.Delete
        StartLine.Delete
        EndLine.Delete
        
        ' 엔터티 생성
        Dim Line1 As AcadLine
        Dim Line2 As AcadLine
        Dim Line3 As AcadLine
        Dim Line4 As AcadLine
        
        Dim Line5 As AcadLine
        Dim Line6 As AcadLine
        Dim Line7 As AcadLine
        Dim Line8 As AcadLine
        
        Dim Line9 As AcadLine
        Dim Line10 As AcadLine
        Dim Line11 As AcadLine
        Dim Line12 As AcadLine
        
        Dim Line13 As AcadLine
        Dim Line14 As AcadLine
        Dim Line15 As AcadLine
        Dim Line16 As AcadLine
        
        Dim Line17 As AcadLine
        Dim Line18 As AcadLine
        Dim Line19 As AcadLine
        Dim Line20 As AcadLine
        
        Dim Line21 As AcadLine
        Dim Line22 As AcadLine
        Dim Line23 As AcadLine
        Dim Line24 As AcadLine
        
        Dim Arc1 As AcadArc
        Dim Arc2 As AcadArc
        
        Dim Cir1 As AcadCircle
        
            Set Arc1 = ThisDrawing.ModelSpace.AddArc(P1, R5, StartAngle, EndAngle)
                Arc1.Update
                
        If Mirror = False Then
            Set Arc2 = ThisDrawing.ModelSpace.AddArc(P25, R1, Dtr(RotAng + 0), Dtr(RotAng + 90))
            Else
            Set Arc2 = ThisDrawing.ModelSpace.AddArc(P25, R1, Dtr(RotAng + 90), Dtr(RotAng + 180))
        End If
            Arc2.Update
        
            Set Cir1 = ThisDrawing.ModelSpace.AddCircle(P1, 0.35 * AC)
                Cir1.Update
            Set Line1 = ThisDrawing.ModelSpace.AddLine(P33, P34)
                Line1.Update
                
            Set Line2 = ThisDrawing.ModelSpace.AddLine(P2, P7)
                Line2.Update
                
            Set Line3 = ThisDrawing.ModelSpace.AddLine(P7, P6)
                Line3.Update
                
            Set Line4 = ThisDrawing.ModelSpace.AddLine(P6, P3)
                Line4.Update
                
            Set Line5 = ThisDrawing.ModelSpace.AddLine(P3, P2)
                Line5.Update
                
            'Hidden Line
            Set Line6 = ThisDrawing.ModelSpace.AddLine(P9, P4)
                Line6.color = acGreen
                Line6.Linetype = "Hidden"
                Line6.Update
                
            Set Line7 = ThisDrawing.ModelSpace.AddLine(P8, P5)
                Line7.color = acGreen
                Line7.Linetype = "Hidden"
                Line7.Update
                
            Set Line8 = ThisDrawing.ModelSpace.AddLine(P3, P29)
                Line8.Update
                
            If FrameNo <> "80" And FrameNo <> "90L" And FrameNo <> "100L" Then
                Set Line9 = ThisDrawing.ModelSpace.AddLine(P7, P30)
                    Line9.Update
            End If
            
            Set Line10 = ThisDrawing.ModelSpace.AddLine(P15, P10)
                Line10.Update
                
            Set Line11 = ThisDrawing.ModelSpace.AddLine(P10, P11)
                Line11.Update
                
            Set Line12 = ThisDrawing.ModelSpace.AddLine(P11, P14)
                Line12.Update
                
            Set Line13 = ThisDrawing.ModelSpace.AddLine(P14, P15)
                Line13.Update
                
            'Hidden Line
            Set Line14 = ThisDrawing.ModelSpace.AddLine(P16, P13)
                Line14.color = acGreen
                Line14.Linetype = "Hidden"
                Line14.Update
                
            Set Line15 = ThisDrawing.ModelSpace.AddLine(P17, P12)
                Line15.color = acGreen
                Line15.Linetype = "Hidden"
                Line15.Update
            
            If FrameNo <> "80" And FrameNo <> "90L" And FrameNo <> "100L" Then
                Set Line16 = ThisDrawing.ModelSpace.AddLine(P15, P31)
                    Line16.Update
            End If
            
            Set Line17 = ThisDrawing.ModelSpace.AddLine(P11, P32)
                Line17.Update
                
            Set Line18 = ThisDrawing.ModelSpace.AddLine(P28, P21)
                Line18.Update
                
            Set Line19 = ThisDrawing.ModelSpace.AddLine(P27, P22)
                Line19.Update
                
            Set Line20 = ThisDrawing.ModelSpace.AddLine(P20, P23)
                Line20.Update
            
            Set Line21 = ThisDrawing.ModelSpace.AddLine(P23, P24)
                Line21.Update
                
            Set Line22 = ThisDrawing.ModelSpace.AddLine(P26, P19)
                Line22.Update
                
            Set Line23 = ThisDrawing.ModelSpace.AddLine(P19, P20)
                Line23.Update
                
            Set Line24 = ThisDrawing.ModelSpace.AddLine(P23, P19)
                Line24.Update
                
            
            
            Dim IntPnt As Variant
            
            If FrameNo = "80" Then
                IntPnt = Line3.IntersectWith(Line1, acExtendNone)
                    Line3.EndPoint = IntPnt
                    Line3.Update
                IntPnt = Arc1.IntersectWith(Line4, acExtendNone)
                    Line4.StartPoint = IntPnt
                    Line4.Update
                IntPnt = Arc1.IntersectWith(Line7, acExtendNone)
                
                    Line7.EndPoint = IntPnt ' 에러발생
                    Line7.Update
                    
                IntPnt = Line13.IntersectWith(Line1, acExtendNone)
                    Line13.StartPoint = IntPnt
                    Line13.Update
                    
                IntPnt = Arc1.IntersectWith(Line12, acExtendNone)
                    Line12.EndPoint = IntPnt
                    Line12.Update
                    
                IntPnt = Arc1.IntersectWith(Line14, acExtendNone)
                    Line14.EndPoint = IntPnt
                    Line14.Update
            End If
            
            If FrameNo = "90L" Or FrameNo = "100L" Then
                IntPnt = Line3.IntersectWith(Line1, acExtendNone)
                    Line3.EndPoint = IntPnt
                    Line3.Update
                    
                IntPnt = Arc1.IntersectWith(Line4, acExtendNone)
                    Line4.StartPoint = IntPnt
                    Line4.Update
                IntPnt = Line13.IntersectWith(Line1, acExtendNone)
                    Line13.StartPoint = IntPnt
                    Line13.Update
                IntPnt = Arc1.IntersectWith(Line12, acExtendNone)
                    Line12.EndPoint = IntPnt
                    Line12.Update
            End If
            
            If FrameNo = "112M" Or FrameNo = "160M" Or FrameNo = "160L" Then
                IntPnt = Arc1.IntersectWith(Line4, acExtendNone)
                Line4.StartPoint = IntPnt
                Line4.Update
                IntPnt = Arc1.IntersectWith(Line3, acExtendNone)
                Line3.EndPoint = IntPnt
                Line3.Update
                
                IntPnt = Arc1.IntersectWith(Line12, acExtendNone)
                Line12.EndPoint = IntPnt
                Line12.Update
                IntPnt = Arc1.IntersectWith(Line13, acExtendNone)
                Line13.StartPoint = IntPnt
                Line13.Update
            End If
            
            ' 그릴그리기
            Dim gPnt1 As Variant
            Dim gPnt2 As Variant
            Dim gPnt3 As Variant
            Dim gPnt4 As Variant
            
            Dim gPnt5 As Variant
            Dim gPnt6 As Variant
            Dim gPnt7 As Variant
            Dim gPnt8 As Variant
                gPnt1 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 90), R4 / 8)
                gPnt2 = ThisDrawing.Utility.PolarPoint(gPnt1, Dtr(RotAng + eAng), 0.1)
                
                gPnt3 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 90), R4 * 3 / 8)
                gPnt4 = ThisDrawing.Utility.PolarPoint(gPnt3, Dtr(RotAng + eAng), 0.1)
                
                gPnt5 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 90), R4 * 5 / 8)
                gPnt6 = ThisDrawing.Utility.PolarPoint(gPnt5, Dtr(RotAng + eAng), 0.1)
                
                gPnt7 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 90), R4 * 7 / 8)
                gPnt8 = ThisDrawing.Utility.PolarPoint(gPnt7, Dtr(RotAng + eAng), 0.1)
                
            Dim tgLine1 As AcadLine
            Dim tgLine2 As AcadLine
            Dim tgLine3 As AcadLine
            Dim tgLine4 As AcadLine
                Set tgLine1 = ThisDrawing.ModelSpace.AddLine(gPnt1, gPnt2)
                Set tgLine2 = ThisDrawing.ModelSpace.AddLine(gPnt3, gPnt4)
                Set tgLine3 = ThisDrawing.ModelSpace.AddLine(gPnt5, gPnt6)
                Set tgLine4 = ThisDrawing.ModelSpace.AddLine(gPnt7, gPnt8)
            
            Dim Pnt1(0 To 2) As Double
            Dim Pnt2(0 To 2) As Double
            Dim Pnt3(0 To 2) As Double
            Dim Pnt4(0 To 2) As Double
            Dim Pnt5(0 To 2) As Double
            Dim Pnt6(0 To 2) As Double
            Dim Pnt7(0 To 2) As Double
            Dim Pnt8(0 To 2) As Double
                
            IntPnt = Cir1.IntersectWith(tgLine1, acExtendOtherEntity)
                Pnt1(0) = IntPnt(0)
                Pnt1(1) = IntPnt(1)
                Pnt1(2) = IntPnt(2)
                Pnt2(0) = IntPnt(3)
                Pnt2(1) = IntPnt(4)
                Pnt2(2) = IntPnt(5)
                
            IntPnt = Cir1.IntersectWith(tgLine2, acExtendOtherEntity)
                Pnt3(0) = IntPnt(0)
                Pnt3(1) = IntPnt(1)
                Pnt3(2) = IntPnt(2)
                Pnt4(0) = IntPnt(3)
                Pnt4(1) = IntPnt(4)
                Pnt4(2) = IntPnt(5)
                
            IntPnt = Cir1.IntersectWith(tgLine3, acExtendOtherEntity)
                Pnt5(0) = IntPnt(0)
                Pnt5(1) = IntPnt(1)
                Pnt5(2) = IntPnt(2)
                Pnt6(0) = IntPnt(3)
                Pnt6(1) = IntPnt(4)
                Pnt6(2) = IntPnt(5)
                
            IntPnt = Cir1.IntersectWith(tgLine4, acExtendOtherEntity)
                Pnt7(0) = IntPnt(0)
                Pnt7(1) = IntPnt(1)
                Pnt7(2) = IntPnt(2)
                Pnt8(0) = IntPnt(3)
                Pnt8(1) = IntPnt(4)
                Pnt8(2) = IntPnt(5)
                
            tgLine1.Delete
            tgLine2.Delete
            tgLine3.Delete
            tgLine4.Delete
            
            Dim gLine1 As AcadLine
            Dim gLine2 As AcadLine
            Dim gLine3 As AcadLine
            Dim gLine4 As AcadLine
            
            Dim gLine5 As AcadLine
            Dim gLine6 As AcadLine
            Dim gLine7 As AcadLine
            Dim gLine8 As AcadLine
            
                Set gLine1 = ThisDrawing.ModelSpace.AddLine(Pnt1, Pnt2)
                Set gLine2 = ThisDrawing.ModelSpace.AddLine(Pnt3, Pnt4)
                Set gLine3 = ThisDrawing.ModelSpace.AddLine(Pnt5, Pnt6)
                Set gLine4 = ThisDrawing.ModelSpace.AddLine(Pnt7, Pnt8)
                    gLine1.color = acBlue
                    gLine2.color = acBlue
                    gLine3.color = acBlue
                    gLine4.color = acBlue
            
            Set gLine5 = gLine1.Mirror(P1, P18)
            Set gLine6 = gLine2.Mirror(P1, P18)
            Set gLine7 = gLine3.Mirror(P1, P18)
            Set gLine8 = gLine4.Mirror(P1, P18)
            
            gLine1.Update
            gLine2.Update
            gLine3.Update
            gLine4.Update
            gLine5.Update
            gLine6.Update
            gLine7.Update
            gLine8.Update
            
            
    ' 중심선 그리기
    
    ' 모터중심선
    Dim cPnt1 As Variant
    Dim cPnt2 As Variant
    Dim cPnt3 As Variant
    Dim cPnt4 As Variant
        cPnt1 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + WAng), R5 + D3 / 20)
        cPnt2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + eAng), AD + D3 / 20)
        cPnt3 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 270), R5 + D3 / 10)
        cPnt4 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 90), R5 + D3 / 20)
        
    Dim cLine1 As AcadLine
    Dim cLine2 As AcadLine
    Dim cLine3 As AcadLine
    Dim cLine4 As AcadLine
        Set cLine1 = ThisDrawing.ModelSpace.AddLine(cPnt1, cPnt2)
        Set cLine2 = ThisDrawing.ModelSpace.AddLine(cPnt3, cPnt4)
            cLine1.color = acRed
            cLine1.Linetype = "Center"
            cLine1.Update
            cLine2.color = acRed
            cLine2.Linetype = "Center"
            cLine2.Update
        
    Dim cPnt5 As Variant
    Dim cPnt6 As Variant
    Dim cPnt7 As Variant
    Dim cPnt8 As Variant
        cPnt1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + WAng), a / 2)
        cPnt2 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + eAng), a / 2)
        
        cPnt5 = ThisDrawing.Utility.PolarPoint(cPnt1, Dtr(RotAng + 270), HA)
        cPnt6 = ThisDrawing.Utility.PolarPoint(cPnt1, Dtr(RotAng + 90), 2 * HA)
        
        cPnt7 = ThisDrawing.Utility.PolarPoint(cPnt2, Dtr(RotAng + 270), HA)
        cPnt8 = ThisDrawing.Utility.PolarPoint(cPnt2, Dtr(RotAng + 90), 2 * HA)
        
        Set cLine3 = ThisDrawing.ModelSpace.AddLine(cPnt5, cPnt6)
        Set cLine4 = ThisDrawing.ModelSpace.AddLine(cPnt7, cPnt8)
            cLine3.color = acRed
            cLine3.Linetype = "Center"
            cLine3.Update
            cLine4.color = acRed
            cLine4.Linetype = "Center"
            cLine4.Update
            
            
            
End Sub

Public Sub DrawPlan() ' 평면도 작성
    
    Set pntCol = Nothing
    
    ReadData
    
    If Mirror = False Then
        eAng = 0
        WAng = 180
        Else
        eAng = 180
        WAng = 0
    End If
    
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
    Dim P15 As Variant
    Dim P16 As Variant
    
    Dim P17 As Variant
    Dim P18 As Variant
    Dim P19 As Variant
    Dim P20 As Variant
    
    Dim P21 As Variant
    Dim P22 As Variant
    Dim P23 As Variant
    Dim P24 As Variant
    
    Dim P25 As Variant
    Dim P26 As Variant
    Dim P27 As Variant
    Dim P28 As Variant
    
    Dim P29 As Variant
    Dim P30 As Variant
    Dim P31 As Variant
    Dim P32 As Variant
    
    Dim P33 As Variant
    Dim P34 As Variant
    Dim P35 As Variant
    Dim P36 As Variant
    
    Dim P37 As Variant
    Dim P38 As Variant
    Dim P39 As Variant
    Dim P40 As Variant
    
    Dim cP1 As Variant
    
        cP1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), C + 0.5 * B)
        
        P1 = ThisDrawing.Utility.PolarPoint(cP1, Dtr(RotAng + WAng), 0.5 * YG)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + 270), YD)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(RotAng + WAng), (YH - YG) / 2)
        P4 = ThisDrawing.Utility.PolarPoint(P3, Dtr(RotAng + 270), YD)
        
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(RotAng + WAng), (YK - YH) / 2)
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(RotAng + 270), YD)
        P7 = ThisDrawing.Utility.PolarPoint(cP1, Dtr(RotAng + eAng), 0.5 * YG)
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(RotAng + 270), YD)
        
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(RotAng + eAng), (YH - YG) / 2)
        P10 = ThisDrawing.Utility.PolarPoint(P9, Dtr(RotAng + 270), YD)
        P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(RotAng + eAng), (YK - YH) / 2)
        P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(RotAng + 270), YD)
        
        P13 = ThisDrawing.Utility.PolarPoint(P6, Dtr(RotAng + WAng), (AC - YK - 2 * R2) / 2)
        P14 = ThisDrawing.Utility.PolarPoint(P13, Dtr(RotAng + 270), R2)
        P15 = ThisDrawing.Utility.PolarPoint(P14, Dtr(RotAng + WAng), R2)
        P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(RotAng + 270), YB)
        
        P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(RotAng + 270), YA - R3)
        P18 = ThisDrawing.Utility.PolarPoint(P17, Dtr(RotAng + eAng), R3)
        P19 = ThisDrawing.Utility.PolarPoint(P18, Dtr(RotAng + 270), R3)
        P20 = ThisDrawing.Utility.PolarPoint(P19, Dtr(RotAng + eAng), 2 * R4)
        
        P21 = ThisDrawing.Utility.PolarPoint(P20, Dtr(RotAng + 90), R3)
        P22 = ThisDrawing.Utility.PolarPoint(P21, Dtr(RotAng + eAng), R3)
        P23 = ThisDrawing.Utility.PolarPoint(P22, Dtr(RotAng + 90), YA - R3)
        P24 = ThisDrawing.Utility.PolarPoint(P23, Dtr(RotAng + 90), LB - (C + B / 2) - YA - 0.4 * XN)
        
        P25 = ThisDrawing.Utility.PolarPoint(P24, Dtr(RotAng + 90), 0.8 * XN)
        P26 = ThisDrawing.Utility.PolarPoint(P25, Dtr(RotAng + 90), (C + B / 2) - R2 - 3 * YD - 0.4 * XN)
        P27 = ThisDrawing.Utility.PolarPoint(P26, Dtr(RotAng + WAng), R2)
        P28 = ThisDrawing.Utility.PolarPoint(P27, Dtr(RotAng + 90), R2)
        
        P29 = ThisDrawing.Utility.PolarPoint(P24, Dtr(RotAng + WAng), XP - (AD - XO - R5))
        P30 = ThisDrawing.Utility.PolarPoint(P29, Dtr(RotAng + 90), 0.8 * XN)
        P31 = ThisDrawing.Utility.PolarPoint(P30, Dtr(RotAng + eAng), XP)
        P32 = ThisDrawing.Utility.PolarPoint(P31, Dtr(RotAng + 90), 0.1 * XN)
        
        P33 = ThisDrawing.Utility.PolarPoint(P32, Dtr(RotAng + eAng), XO - R1)
        P34 = ThisDrawing.Utility.PolarPoint(P33, Dtr(RotAng + 270), R1)
        P35 = ThisDrawing.Utility.PolarPoint(P34, Dtr(RotAng + eAng), R1)
        P36 = ThisDrawing.Utility.PolarPoint(P35, Dtr(RotAng + 270), XN - 2 * R1)
        
        P37 = ThisDrawing.Utility.PolarPoint(P36, Dtr(RotAng + WAng), R1)
        P38 = ThisDrawing.Utility.PolarPoint(P37, Dtr(RotAng + 270), R1)
        P39 = ThisDrawing.Utility.PolarPoint(P38, Dtr(RotAng + WAng), XO - R1)
        P40 = ThisDrawing.Utility.PolarPoint(P39, Dtr(RotAng + 90), 0.1 * XN)
        
        pntCol.Add P19
        pntCol.Add P20
        pntCol.Add P22
        pntCol.Add P24
        
        pntCol.Add P40
        pntCol.Add P39
        pntCol.Add P38
        pntCol.Add P36
        
        pntCol.Add P35
        pntCol.Add P33
        pntCol.Add P32
        pntCol.Add P31
        
        pntCol.Add P25
        pntCol.Add P26
        pntCol.Add P28
        pntCol.Add P12
        
        pntCol.Add P11
        pntCol.Add P10
        pntCol.Add P9
        pntCol.Add P8
        
        pntCol.Add P7
        pntCol.Add P1
        pntCol.Add P2
        pntCol.Add P3
        
        pntCol.Add P4
        pntCol.Add P5
        pntCol.Add P6
        pntCol.Add P13
        
        pntCol.Add P15
        pntCol.Add P17
        
        MakePntArray
        
        Set MotorEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        
        
        
        With MotorEnt
            .Closed = True
            If Mirror = False Then
                .SetBulge 1, Sqr(2) - 1
                .SetBulge 6, Sqr(2) - 1
                .SetBulge 8, Sqr(2) - 1
                .SetBulge 13, Sqr(2) - 1
                .SetBulge 27, Sqr(2) - 1
                .SetBulge 29, Sqr(2) - 1
                Else
                .SetBulge 1, 1 - Sqr(2)
                .SetBulge 6, 1 - Sqr(2)
                .SetBulge 8, 1 - Sqr(2)
                .SetBulge 13, 1 - Sqr(2)
                .SetBulge 27, 1 - Sqr(2)
                .SetBulge 29, 1 - Sqr(2)
            End If
            
            .Highlight True
            
        End With
        
        Set AutoTrim.Ent = MotorEnt
        AutoTrim.DoTrim
        MotorEnt.Delete
        
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    
    Dim Line5 As AcadLine
    Dim Line6 As AcadLine
    Dim Line7 As AcadLine
    Dim Line8 As AcadLine
    
    Dim Line9 As AcadLine
    Dim Line10 As AcadLine
    Dim Line11 As AcadLine
    Dim Line12 As AcadLine
    
    Dim Line13 As AcadLine
    Dim Line14 As AcadLine
    Dim Line15 As AcadLine
    Dim Line16 As AcadLine
    
    Dim Line17 As AcadLine
    Dim Line18 As AcadLine
    Dim Line19 As AcadLine
    Dim Line20 As AcadLine
    
    Dim Line21 As AcadLine
    Dim Line22 As AcadLine
    Dim Line23 As AcadLine
    
    Dim Arc1 As AcadArc
    Dim Arc2 As AcadArc
    Dim Arc3 As AcadArc
    Dim Arc4 As AcadArc
    
    Dim Arc5 As AcadArc
    Dim Arc6 As AcadArc
    
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P2, P1)
            Line1.color = acCyan
            Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P1, P7)
            Line2.color = acCyan
            Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P7, P8)
            Line3.color = acCyan
            Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P4, P3)
            Line4.color = acCyan
            Line4.Update
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P3, P9)
            Line5.color = acCyan
            Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P9, P10)
            Line6.color = acCyan
            Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P6, P5)
            Line7.color = acCyan
            Line7.Update
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P5, P11)
            Line8.color = acCyan
            Line8.Update
        
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P11, P12)
            Line9.color = acCyan
            Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P13, P28)
            Line10.Update
        Set Line11 = ThisDrawing.ModelSpace.AddLine(P15, P26)
            Line11.Update
        Set Line12 = ThisDrawing.ModelSpace.AddLine(P15, P17)
            Line12.Update
        
        Set Line13 = ThisDrawing.ModelSpace.AddLine(P19, P20)
            Line13.Update
        Set Line14 = ThisDrawing.ModelSpace.AddLine(P22, P24)
            Line14.Update
        Set Line15 = ThisDrawing.ModelSpace.AddLine(P25, P26)
            Line15.Update
        Set Line16 = ThisDrawing.ModelSpace.AddLine(P16, P23)
            Line16.Update
        
        Set Line17 = ThisDrawing.ModelSpace.AddLine(P29, P30)
            Line17.Update
        Set Line18 = ThisDrawing.ModelSpace.AddLine(P29, P40)
            Line18.Update
        Set Line19 = ThisDrawing.ModelSpace.AddLine(P30, P31)
            Line19.Update
        Set Line20 = ThisDrawing.ModelSpace.AddLine(P39, P32)
            Line20.Update
        
        Set Line21 = ThisDrawing.ModelSpace.AddLine(P32, P33)
            Line21.Update
        Set Line22 = ThisDrawing.ModelSpace.AddLine(P35, P36)
            Line22.Update
        Set Line23 = ThisDrawing.ModelSpace.AddLine(P38, P39)
            Line23.Update
            
        If Mirror = False Then
            Set Arc1 = ThisDrawing.ModelSpace.AddArc(P14, R2, Dtr(RotAng + 90), Dtr(RotAng + 180))
                Arc1.Update
            Set Arc2 = ThisDrawing.ModelSpace.AddArc(P27, R2, Dtr(RotAng + 0), Dtr(RotAng + 90))
                Arc2.Update
            Set Arc3 = ThisDrawing.ModelSpace.AddArc(P18, R3, Dtr(RotAng + 180), Dtr(RotAng + 270))
                Arc3.Update
            Set Arc4 = ThisDrawing.ModelSpace.AddArc(P21, R3, Dtr(RotAng + 270), Dtr(RotAng + 0))
                Arc4.Update
            Set Arc5 = ThisDrawing.ModelSpace.AddArc(P34, R1, Dtr(RotAng + 0), Dtr(RotAng + 90))
                Arc5.Update
            Set Arc6 = ThisDrawing.ModelSpace.AddArc(P37, R1, Dtr(RotAng + 270), Dtr(RotAng + 0))
                Arc6.Update
            Else
            Set Arc1 = ThisDrawing.ModelSpace.AddArc(P14, R2, Dtr(RotAng + 0), Dtr(RotAng + 90))
                Arc1.Update
            Set Arc2 = ThisDrawing.ModelSpace.AddArc(P27, R2, Dtr(RotAng + 90), Dtr(RotAng + 180))
                Arc2.Update
            Set Arc3 = ThisDrawing.ModelSpace.AddArc(P18, R3, Dtr(RotAng + 270), Dtr(RotAng + 0))
                Arc3.Update
            Set Arc4 = ThisDrawing.ModelSpace.AddArc(P21, R3, Dtr(RotAng + 180), Dtr(RotAng + 270))
                Arc4.Update
            Set Arc5 = ThisDrawing.ModelSpace.AddArc(P34, R1, Dtr(RotAng + 90), Dtr(RotAng + 180))
                Arc5.Update
            Set Arc6 = ThisDrawing.ModelSpace.AddArc(P37, R1, Dtr(RotAng + 180), Dtr(RotAng + 270))
                Arc6.Update
        End If
        
        pCenP3 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 270), LB - (C + B / 2))
        
        
        
End Sub
Public Sub DrawRight() ' 우측면도 작성

    Set pntCol = Nothing

    ReadData ' Motor Data 읽기
    
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
    Dim P15 As Variant
    Dim P16 As Variant
    
    Dim P17 As Variant
    Dim P18 As Variant
    Dim P19 As Variant
    Dim P20 As Variant
    
    Dim P21 As Variant
    Dim P22 As Variant
    Dim P23 As Variant
    Dim P24 As Variant
    
    Dim P25 As Variant
    Dim P26 As Variant
    Dim P27 As Variant
    Dim P28 As Variant
    
    Dim P29 As Variant
    Dim P30 As Variant
    Dim P31 As Variant
    Dim P32 As Variant
    
    Dim P33 As Variant
    Dim P34 As Variant
    Dim P35 As Variant
    Dim P36 As Variant
    
    Dim P37 As Variant
    Dim P38 As Variant
    Dim P39 As Variant
    Dim P40 As Variant
    
    Dim P41 As Variant
    Dim P42 As Variant
    Dim P43 As Variant
    Dim P44 As Variant
    
    Dim P45 As Variant
    Dim P46 As Variant
    Dim P47 As Variant
    Dim P48 As Variant
    
    Dim P49 As Variant
    Dim P50 As Variant
    Dim P51 As Variant
    Dim P52 As Variant
    
    Dim P53 As Variant
    Dim P54 As Variant
    Dim P55 As Variant
    
    Dim cP1 As Variant
    Dim cP2 As Variant
        
    Dim cenP1 As Variant
    Dim cenP2 As Variant
    Dim cenP3 As Variant
    Dim cenP4 As Variant
    
    
    If Mirror = False Then
        eAng = 0
        WAng = 180
        
        Else
        eAng = 180
        WAng = 0
    
    End If
    
    
        cP1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + 90), H)
        cP2 = ThisDrawing.Utility.PolarPoint(cP1, Dtr(RotAng + eAng), B / 2 + C)
        
        P1 = ThisDrawing.Utility.PolarPoint(CP, Dtr(RotAng + WAng), (B - K) / 2)
        P2 = ThisDrawing.Utility.PolarPoint(P1, Dtr(RotAng + WAng), K)
        P3 = ThisDrawing.Utility.PolarPoint(P2, Dtr(RotAng + WAng), (BB - B - K) / 2)
        P4 = ThisDrawing.Utility.PolarPoint(P3, Dtr(RotAng + 90), HA / 2)
        
        P5 = ThisDrawing.Utility.PolarPoint(P4, Dtr(RotAng + 90), HA / 2)
        P6 = ThisDrawing.Utility.PolarPoint(P5, Dtr(RotAng + eAng), (BB - B - K) / 2)
        P7 = ThisDrawing.Utility.PolarPoint(P6, Dtr(RotAng + eAng), K)
        P8 = ThisDrawing.Utility.PolarPoint(P7, Dtr(RotAng + eAng), B - K)
        
        P9 = ThisDrawing.Utility.PolarPoint(P8, Dtr(RotAng + eAng), K)
        P10 = ThisDrawing.Utility.PolarPoint(P9, Dtr(RotAng + eAng), (BB - B - K) / 2)
        P11 = ThisDrawing.Utility.PolarPoint(P10, Dtr(RotAng + 270), HA / 2)
        P12 = ThisDrawing.Utility.PolarPoint(P11, Dtr(RotAng + 270), HA / 2)
        
        P13 = ThisDrawing.Utility.PolarPoint(P9, Dtr(RotAng + 270), HA)
        P14 = ThisDrawing.Utility.PolarPoint(P8, Dtr(RotAng + 270), HA)
        P15 = ThisDrawing.Utility.PolarPoint(P5, Dtr(RotAng + eAng), (BB - YF) / 2)
        P16 = ThisDrawing.Utility.PolarPoint(P15, Dtr(RotAng + 90), YE)
        
        P17 = ThisDrawing.Utility.PolarPoint(P16, Dtr(RotAng + eAng), YF)
        P18 = ThisDrawing.Utility.PolarPoint(P17, Dtr(RotAng + 270), YE)
        P19 = ThisDrawing.Utility.PolarPoint(P11, Dtr(RotAng + eAng), C - (BB - B) / 2 - R2 - 3 * YD)
        P20 = ThisDrawing.Utility.PolarPoint(P19, Dtr(RotAng + 90), R2)
        
        P21 = ThisDrawing.Utility.PolarPoint(P20, Dtr(RotAng + eAng), R2)
        
        P22 = ThisDrawing.Utility.PolarPoint(P21, Dtr(RotAng + 90), H - YK / 2 - HA / 2 - R2)
        P23 = ThisDrawing.Utility.PolarPoint(P22, Dtr(RotAng + eAng), YD)
        P24 = ThisDrawing.Utility.PolarPoint(P23, Dtr(RotAng + 90), (YK - YH) / 2)
        
        P25 = ThisDrawing.Utility.PolarPoint(P24, Dtr(RotAng + eAng), YD)
        P26 = ThisDrawing.Utility.PolarPoint(P25, Dtr(RotAng + 90), (YH - YG) / 2)
        P27 = ThisDrawing.Utility.PolarPoint(P26, Dtr(RotAng + eAng), YD)
        P28 = ThisDrawing.Utility.PolarPoint(P27, Dtr(RotAng + 90), YG)
        
        P29 = ThisDrawing.Utility.PolarPoint(P28, Dtr(RotAng + WAng), YD)
        P30 = ThisDrawing.Utility.PolarPoint(P29, Dtr(RotAng + 90), (YH - YG) / 2)
        P31 = ThisDrawing.Utility.PolarPoint(P30, Dtr(RotAng + WAng), YD)
        P32 = ThisDrawing.Utility.PolarPoint(P31, Dtr(RotAng + 90), (YK - YH) / 2)
        
        P33 = ThisDrawing.Utility.PolarPoint(P32, Dtr(RotAng + WAng), YD)
        P34 = ThisDrawing.Utility.PolarPoint(P33, Dtr(RotAng + 90), R5 - YK / 2 - R2)
        P35 = ThisDrawing.Utility.PolarPoint(P34, Dtr(RotAng + WAng), R2)
        P36 = ThisDrawing.Utility.PolarPoint(P35, Dtr(RotAng + 90), R2)
        
        P37 = ThisDrawing.Utility.PolarPoint(P36, Dtr(RotAng + WAng), YB)
        P38 = ThisDrawing.Utility.PolarPoint(P37, Dtr(RotAng + WAng), YA - R3)
        P39 = ThisDrawing.Utility.PolarPoint(P38, Dtr(RotAng + 270), R3)
        P40 = ThisDrawing.Utility.PolarPoint(P39, Dtr(RotAng + WAng), R3)
        P41 = ThisDrawing.Utility.PolarPoint(P40, Dtr(RotAng + 270), 2 * R4)
        Dim R6 As Double
            R6 = H - R4 - HA / 2
        P42 = ThisDrawing.Utility.PolarPoint(P41, Dtr(RotAng + eAng), R6)
        P43 = ThisDrawing.Utility.PolarPoint(P42, Dtr(RotAng + 270), R6)
            Dim tmpPnt1 As Variant
                tmpPnt1 = ThisDrawing.Utility.PolarPoint(cP1, Dtr(RotAng + WAng), XN / 2)
                
        P44 = ThisDrawing.Utility.PolarPoint(tmpPnt1, Dtr(RotAng + 90), XL / 2 - R1)
        
        P45 = ThisDrawing.Utility.PolarPoint(P44, Dtr(RotAng + eAng), R1)
        P46 = ThisDrawing.Utility.PolarPoint(P45, Dtr(RotAng + 90), R1)
        P47 = ThisDrawing.Utility.PolarPoint(P46, Dtr(RotAng + eAng), XN - 2 * R1)
        P48 = ThisDrawing.Utility.PolarPoint(P47, Dtr(RotAng + 270), R1)
        
        P49 = ThisDrawing.Utility.PolarPoint(P48, Dtr(RotAng + eAng), R1)
        P50 = ThisDrawing.Utility.PolarPoint(P49, Dtr(RotAng + 270), XL - 2 * R1)
        P51 = ThisDrawing.Utility.PolarPoint(P50, Dtr(RotAng + WAng), R1)
        P52 = ThisDrawing.Utility.PolarPoint(P51, Dtr(RotAng + 270), R1)
        
        P53 = ThisDrawing.Utility.PolarPoint(P52, Dtr(RotAng + WAng), XN - 2 * R1)
        P54 = ThisDrawing.Utility.PolarPoint(P53, Dtr(RotAng + 90), R1)
        P55 = ThisDrawing.Utility.PolarPoint(P54, Dtr(RotAng + WAng), R1)
        
        cenP1 = ThisDrawing.Utility.PolarPoint(P6, Dtr(RotAng + eAng), K / 2)
        cenP1 = ThisDrawing.Utility.PolarPoint(cenP1, Dtr(RotAng + 90), K)
        cenP2 = ThisDrawing.Utility.PolarPoint(P2, Dtr(RotAng + eAng), K / 2)
        cenP2 = ThisDrawing.Utility.PolarPoint(cenP2, Dtr(RotAng + 270), K)
        cenP3 = ThisDrawing.Utility.PolarPoint(P8, Dtr(RotAng + eAng), K / 2)
        cenP3 = ThisDrawing.Utility.PolarPoint(cenP3, Dtr(RotAng + 90), K)
        cenP4 = ThisDrawing.Utility.PolarPoint(P14, Dtr(RotAng + eAng), K / 2)
        cenP4 = ThisDrawing.Utility.PolarPoint(cenP4, Dtr(RotAng + 270), K)
        
        
    If frmInput.optVbelt = True Then ' 직결일 땐 Trim 안함
        
        pntCol.Add P36
        pntCol.Add P38
        pntCol.Add P40
        pntCol.Add P41
        pntCol.Add P43
        pntCol.Add P4
        pntCol.Add P3
        pntCol.Add P12
        pntCol.Add P11
        pntCol.Add P19
        pntCol.Add P21
        pntCol.Add P22
        pntCol.Add P23
        pntCol.Add P24
        pntCol.Add P25
        pntCol.Add P26
        pntCol.Add P27
        pntCol.Add P28
        pntCol.Add P29
        pntCol.Add P30
        pntCol.Add P31
        pntCol.Add P32
        pntCol.Add P33
        pntCol.Add P34
        
        MakePntArray
        
        Set MotorEnt = ThisDrawing.ModelSpace.AddPolyline(pntArray)
        MotorEnt.Closed = True
        
        With MotorEnt
            .SetBulge 1, Sqr(2) - 1
            .SetBulge 3, Sqr(2) - 1
            .SetBulge 9, Sqr(2) - 1
            .SetBulge 23, Sqr(2) - 1
        End With
        
        MotorEnt.Update
        MotorEnt.Highlight True
        
        Set AutoTrim.Ent = MotorEnt
        AutoTrim.DoTrim
        MotorEnt.Delete
        
    End If ' 직결일 땐 Trim 안함
    
        
    Dim Line1 As AcadLine
    Dim Line2 As AcadLine
    Dim Line3 As AcadLine
    Dim Line4 As AcadLine
    
    Dim Line5 As AcadLine
    Dim Line6 As AcadLine
    Dim Line7 As AcadLine
    Dim Line8 As AcadLine
    
    Dim Line9 As AcadLine
    Dim Line10 As AcadLine
    Dim Line11 As AcadLine
    Dim Line12 As AcadLine
    
    Dim Line13 As AcadLine
    Dim Line14 As AcadLine
    Dim Line15 As AcadLine
    Dim Line16 As AcadLine
    
    Dim Line17 As AcadLine
    Dim Line18 As AcadLine
    Dim Line19 As AcadLine
    Dim Line20 As AcadLine
    
    Dim Line21 As AcadLine
    Dim Line22 As AcadLine
    Dim Line23 As AcadLine
    Dim Line24 As AcadLine
    
    Dim Line25 As AcadLine
    Dim Line26 As AcadLine
    Dim Line27 As AcadLine
    Dim Line28 As AcadLine
    
    Dim Line29 As AcadLine
    Dim Line30 As AcadLine
    Dim Line31 As AcadLine
    
    Dim cenLine1 As AcadLine
    Dim cenLine2 As AcadLine
    
    Dim Arc1 As AcadArc
    Dim Arc2 As AcadArc
    Dim Arc3 As AcadArc
    Dim Arc4 As AcadArc
    
    Dim Arc5 As AcadArc
    Dim Arc6 As AcadArc
    Dim Arc7 As AcadArc
    Dim Arc8 As AcadArc
    
        Set Line1 = ThisDrawing.ModelSpace.AddLine(P3, P12)
        Line1.Update
        Set Line2 = ThisDrawing.ModelSpace.AddLine(P12, P10)
        Line2.Update
        Set Line3 = ThisDrawing.ModelSpace.AddLine(P5, P10)
        Line3.Update
        Set Line4 = ThisDrawing.ModelSpace.AddLine(P3, P5)
        Line4.Update
        
        Set Line5 = ThisDrawing.ModelSpace.AddLine(P11, P19)
        Line5.Update
        Set Line6 = ThisDrawing.ModelSpace.AddLine(P19, P36)
        Line6.Update
        Set Line7 = ThisDrawing.ModelSpace.AddLine(P21, P34)
        Line7.Update
        
        'Cyan 라인
        Set Line8 = ThisDrawing.ModelSpace.AddLine(P22, P23)
            Line8.color = acCyan
            Line8.Update
        Set Line9 = ThisDrawing.ModelSpace.AddLine(P33, P32)
            Line9.color = acCyan
            Line9.Update
        Set Line10 = ThisDrawing.ModelSpace.AddLine(P23, P32)
            Line10.color = acCyan
            Line10.Update
        Set Line11 = ThisDrawing.ModelSpace.AddLine(P24, P25)
            Line11.color = acCyan
            Line11.Update
        Set Line12 = ThisDrawing.ModelSpace.AddLine(P31, P30)
            Line12.color = acCyan
            Line12.Update
        Set Line13 = ThisDrawing.ModelSpace.AddLine(P25, P30)
            Line13.color = acCyan
            Line13.Update
        Set Line14 = ThisDrawing.ModelSpace.AddLine(P26, P27)
            Line14.color = acCyan
            Line14.Update
        Set Line15 = ThisDrawing.ModelSpace.AddLine(P29, P28)
            Line15.color = acCyan
            Line15.Update
        Set Line16 = ThisDrawing.ModelSpace.AddLine(P27, P28)
            Line16.color = acCyan
            Line16.Update
        
        
        
        Set Line17 = ThisDrawing.ModelSpace.AddLine(P36, P38)
        Line17.Update
        Set Line18 = ThisDrawing.ModelSpace.AddLine(P40, P41)
        Line18.Update
        Set Line19 = ThisDrawing.ModelSpace.AddLine(P43, P4)
        Line19.Update
        Set Line20 = ThisDrawing.ModelSpace.AddLine(P5, P37)
        Line20.Update
        
        'Set Line21 = ThisDrawing.ModelSpace.AddLine(P15, P16)
        'Set Line22 = ThisDrawing.ModelSpace.AddLine(P18, P17)
        'Set Line23 = ThisDrawing.ModelSpace.AddLine(P16, P17)
        
    If Mirror = False Then
        Set Line24 = ThisDrawing.ModelSpace.AddLine(P55, P44)
        Line24.Update
        Set Line25 = ThisDrawing.ModelSpace.AddLine(P50, P49)
        Line25.Update
        Set Line26 = ThisDrawing.ModelSpace.AddLine(P46, P47)
        Line26.Update
        Set Line27 = ThisDrawing.ModelSpace.AddLine(P53, P52)
    End If
        
        ' Hidden Line
        Set Line28 = ThisDrawing.ModelSpace.AddLine(P2, P6)
            Line28.color = acGreen
            Line28.Linetype = "Hidden"
            Line28.Update
        Set Line29 = ThisDrawing.ModelSpace.AddLine(P1, P7)
            Line29.color = acGreen
            Line29.Linetype = "Hidden"
            Line29.Update
        Set Line30 = ThisDrawing.ModelSpace.AddLine(P14, P8)
            Line30.color = acGreen
            Line30.Linetype = "Hidden"
            Line30.Update
        Set Line31 = ThisDrawing.ModelSpace.AddLine(P13, P9)
            Line31.color = acGreen
            Line31.Linetype = "Hidden"
            Line31.Update
    
    If Mirror = False Then
        Set Arc1 = ThisDrawing.ModelSpace.AddArc(P35, R2, Dtr(RotAng + 0), Dtr(RotAng + 90))
        Else
        Set Arc1 = ThisDrawing.ModelSpace.AddArc(P35, R2, Dtr(RotAng + 90), Dtr(RotAng + 180))
    End If
        Line1.Update
    
    If Mirror = False Then
        Set Arc2 = ThisDrawing.ModelSpace.AddArc(P39, R3, Dtr(RotAng + 90), Dtr(RotAng + 180))
        Else
        Set Arc2 = ThisDrawing.ModelSpace.AddArc(P39, R3, Dtr(RotAng + 0), Dtr(RotAng + 90))
    End If
        Line2.Update
    
    If Mirror = False Then
        Set Arc3 = ThisDrawing.ModelSpace.AddArc(P42, R6, Dtr(RotAng + 180), Dtr(RotAng + 270))
        Else
        Set Arc3 = ThisDrawing.ModelSpace.AddArc(P42, R6, Dtr(RotAng + 270), Dtr(RotAng + 0))
    End If
        Line3.Update
    
    If Mirror = False Then
        Set Arc4 = ThisDrawing.ModelSpace.AddArc(P20, R2, Dtr(RotAng + 270), Dtr(RotAng + 0))
        Else
        Set Arc4 = ThisDrawing.ModelSpace.AddArc(P20, R2, Dtr(RotAng + 180), Dtr(RotAng + 270))
    End If
        Line4.Update
    
    If frmInput.optVbelt = True Then
        Set Arc5 = ThisDrawing.ModelSpace.AddArc(P45, R1, Dtr(RotAng + 90), Dtr(RotAng + WAng))
        Line5.Update
        Set Arc6 = ThisDrawing.ModelSpace.AddArc(P54, R1, Dtr(RotAng + WAng), Dtr(RotAng + 270))
        Line6.Update
        Set Arc7 = ThisDrawing.ModelSpace.AddArc(P51, R1, Dtr(RotAng + 270), Dtr(RotAng + eAng))
        Line7.Update
        Set Arc8 = ThisDrawing.ModelSpace.AddArc(P48, R1, Dtr(RotAng + eAng), Dtr(RotAng + 90))
        Line8.Update
    
        If Right$(Direction, 1) = "R" Then
        
            rCenP3 = ThisDrawing.Utility.PolarPoint(cP1, Dtr(RotAng + 180), LB - (C + B / 2))
        
        End If
    
    End If
    
    If frmInput.optDirect Then
        rCenP2 = ThisDrawing.Utility.PolarPoint(cP1, Dtr(0), LB - (C + B / 2))
    End If
    
    Set cenLine1 = ThisDrawing.ModelSpace.AddLine(cenP1, cenP2)
        cenLine1.color = acRed
        cenLine1.Linetype = "Center"
        cenLine1.Update
    Set cenLine2 = ThisDrawing.ModelSpace.AddLine(cenP3, cenP4)
        cenLine2.color = acRed
        cenLine2.Linetype = "Center"
        cenLine2.Update
        
        
        
End Sub

Private Function Dtr(Degree As Double) As Double
    
    Dtr = 3.141592654 * Degree / 180

End Function

Public Sub ReadData()
    
    Select Case FrameNo
        Case "71"
            a = 112: AA = 38: AB = 148: AC = 148: AD = 145: AE = 122: B = 90: BB = 114: C = 45: DS = 14
            H = 71: HA = 4: K = 7: LB = 200: XL = 104: XN = 102
        Case "80"
            a = 125: AA = 35: AB = 150: AC = 180: AD = 135: AE = 117: B = 100: BB = 125: C = 50: DS = 19
            H = 80: HA = 8: K = 10: LB = 232: XL = 104: XN = 102
        Case "90L"
            a = 140: AA = 38: AB = 167: AC = 199: AD = 150: AE = 128: B = 125: BB = 150: C = 56: DS = 24
            H = 90: HA = 10: K = 10: LB = 282: XL = 104: XN = 102
        Case "100L"
            a = 160: AA = 47: AB = 196: AC = 220: AD = 180: AE = 154: B = 140: BB = 174: C = 63: DS = 28
            H = 100: HA = 12: K = 12: LB = 311: XL = 104: XN = 102
        Case "112M"
            a = 190: AA = 41: AB = 226: AC = 244: AD = 190: AE = 165: B = 140: BB = 172: C = 70: DS = 28
            H = 112: HA = 14: K = 12: LB = 313: XL = 138: XN = 124
        Case "132S"
            a = 216: AA = 50: AB = 264: AC = 284: AD = 213: AE = 185: B = 140: BB = 178: C = 89: DS = 38
            H = 132: HA = 16: K = 12: LB = 358: XL = 138: XN = 124
        Case "132M"
            a = 216: AA = 50: AB = 264: AC = 284: AD = 213: AE = 185: B = 178: BB = 216: C = 89: DS = 38
            H = 132: HA = 16: K = 12: LB = 396: XL = 138: XN = 124
        Case "160M"
            a = 254: AA = 67: AB = 314: AC = 337: AD = 261: AE = 230: B = 210: BB = 260: C = 108: DS = 42
            H = 160: HA = 19: K = 15: LB = 473: XL = 165: XN = 147
        Case "160L"
            a = 254: AA = 67: AB = 314: AC = 337: AD = 261: AE = 230: B = 254: BB = 304: C = 108: DS = 42
            H = 160: HA = 19: K = 15: LB = 517: XL = 165: XN = 147
        Case "180M"
            a = 279: AA = 63: AB = 338: AC = 374: AD = 288: AE = 255: B = 241: BB = 300: C = 121: DS = 48
            H = 180: HA = 20: K = 15: LB = 558: XL = 165: XN = 147
        Case "180L"
            a = 279: AA = 63: AB = 338: AC = 374: AD = 288: AE = 255: B = 279: BB = 338: C = 121: DS = 55
            H = 180: HA = 20: K = 15: LB = 596: XL = 165: XN = 147
        Case "200L"
            a = 318: AA = 70: AB = 382: AC = 414: AD = 317: AE = 282: B = 305: BB = 370: C = 133: DS = 60
            H = 200: HA = 22: K = 19: LB = 651: XL = 187: XN = 174
        Case "225S"
            a = 356: AA = 79: AB = 432: AC = 465: AD = 397: AE = 334: B = 286: BB = 343: C = 149: DS = 60
            H = 225: HA = 25: K = 19: LB = 677: XL = 262: XN = 202
        Case "225M"
            a = 356: AA = 79: AB = 432: AC = 465: AD = 397: AE = 334: B = 311: BB = 368: C = 149: DS = 60
            H = 225: HA = 25: K = 19: LB = 702: XL = 262: XN = 202
        Case "250S"
            a = 406: AA = 86: AB = 485: AC = 529: AD = 428: AE = 362: B = 311: BB = 368: C = 168: DS = 75
            H = 250: HA = 27: K = 24: LB = 736: XL = 262: XN = 202
        Case "250M"
            a = 406: AA = 86: AB = 485: AC = 529: AD = 428: AE = 362: B = 349: BB = 406: C = 168: DS = 75
            H = 250: HA = 27: K = 24: LB = 774: XL = 262: XN = 202
        Case "280S"
            a = 457: AA = 89: AB = 546: AC = 602: AD = 510: AE = 430: B = 368: BB = 439: C = 190: DS = 85
            H = 280: HA = 32: K = 24: LB = 874: XL = 340: XN = 308
        Case "280M"
            a = 457: AA = 89: AB = 546: AC = 602: AD = 510: AE = 430: B = 419: BB = 490: C = 190: DS = 85
            H = 280: HA = 32: K = 24: LB = 925: XL = 340: XN = 308
        Case "280L"
            a = 457: AA = 89: AB = 546: AC = 602: AD = 510: AE = 430: B = 508: BB = 580: C = 190: DS = 95
            H = 280: HA = 32: K = 24: LB = 1014: XL = 304: XN = 308
        Case "280LL"
            a = 457: AA = 89: AB = 546: AC = 602: AD = 510: AE = 430: B = 635: BB = 708: C = 190: DS = 95
            H = 280: HA = 32: K = 24: LB = 1141: XL = 340: XN = 308
            
    End Select
    
    R1 = 0.15 * XN
    R2 = C / 3
    R5 = AC / 2
    
    R3 = 0.3 * R5
    R4 = 0.7 * R5
    
    XO = 2 * (AD - AE)
    XP = (AD - XO) - Sqr(R5 ^ 2 - (0.4 * XN) ^ 2)
    YA = LB - (C + B + (BB - B) / 2)
    YD = C / 9
    YB = LB - (YA + R2 + 3 * YD)
    YE = AA
    YF = 3 * AA
    
    YG = DS + 10
    YH = 0.8 * R5
    YK = 1.2 * R5
    YF = 0.5 * BB
    
End Sub

Sub MakePntArray()
        
    ReDim pntArray(pntCol.Count * 3 - 1)
    Dim i As Integer
    Dim pnt As Variant
    
    For i = 1 To pntCol.Count
        
        pnt = pntCol.Item(i)
            
        pntArray(0 + (i - 1) * 3) = pnt(0)
        pntArray(1 + (i - 1) * 3) = pnt(1)
        pntArray(2 + (i - 1) * 3) = pnt(2)
            
    Next i
        
End Sub

