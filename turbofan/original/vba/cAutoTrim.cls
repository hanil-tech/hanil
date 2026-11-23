Attribute VB_Name = "cAutoTrim"
Attribute VB_Base = "0{FCFB3D2A-A0FA-1068-A738-08002B3371B5}"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Attribute VB_TemplateDerived = False
Attribute VB_Customizable = False
Option Explicit

Public Ent As AcadEntity ' 자를 PolyLine

Dim tEnt As AcadEntity ' 잘릴 대상
Dim tEntName As String ' 잘릴 대상의 종류명
Dim IntPnt As Variant ' 얻어지는 교점
Dim LineEnt As AcadLine ' Line을 할당
Dim ArcEnt As AcadArc ' Arc를 할당
Dim CircleEnt As AcadCircle ' Circle을 할당

Dim oUB As Integer
Dim bgUB As Integer
Dim smUB As Integer
Dim sOffset As Variant
Dim bOffset As Variant

Dim spSin As Boolean
Dim spBin As Boolean
Dim epSin As Boolean
Dim epBin As Boolean


Dim intP1(0 To 2) As Double
Dim intP2(0 To 2) As Double
Dim intP3(0 To 2) As Double
Dim intP4(0 To 2) As Double
Dim tmpPnt(0 To 2) As Variant

Dim tmpLine As AcadLine
Dim NewLine1 As AcadLine
Dim NewLine2 As AcadLine
Dim newLine3 As AcadLine
Dim Length1 As Double
Dim Length2 As Double
Dim Length3 As Double
Dim i As Integer
Dim j As Integer
Dim L(1 To 3) As Double
Dim tmp(0 To 2) As Double

Dim Ang1 As Double
Dim Ang2 As Double
Dim sAng As Double
Dim eAng As Double
Dim tmpAng As Double
Dim angLine1 As AcadLine
Dim angLine2 As AcadLine
Dim newArc1 As AcadArc
Dim newArc2 As AcadArc
Dim aCP(0 To 2) As Double
Dim Rad As Double
Dim cCp(0 To 2) As Double
Dim cpIn As Boolean
Dim mAng As Double
Dim midPnt As Variant

Dim sOfs As AcadEntity
Dim bOfs As AcadEntity

Public Sub DoTrim()
    
    ' Ent의 BoundBox 점을 얻어냄
    Dim MinPnt As Variant '좌하점
    Dim MaxPnt As Variant '우상점
        Ent.GetBoundingBox MinPnt, MaxPnt
    
    ' SelectionSet을 이용하여 Ent에 포함 또는 인접한 Entity를 Collection으로 만듬
    Dim Sel As AcadSelectionSet
        Set Sel = ThisDrawing.SelectionSets.Add("SSet") ' SelectionSet을 생성
        Sel.Select acSelectionSetCrossing, MinPnt, MaxPnt 'Crossing을 이용하여 Entity를 선택
    
    ' Selection을 Collection에 넘겨줌
    Dim Col As New Collection
        For Each tEnt In Sel
            Col.Add tEnt
        Next
    
    Sel.Delete ' 사용한 Selection을 소멸시킴
    
For Each tEnt In Col
    
        tEntName = tEnt.ObjectName
        
    '=============================================================================================
    ' 대상이 Line인 경우
    '=============================================================================================
    If tEntName = "AcDbLine" Then
        
        Set LineEnt = tEnt
        
        '검사
        IntPnt = LineEnt.IntersectWith(Ent, acExtendNone)
        oUB = UBound(IntPnt)
        isUB LineEnt, Ent
        spSin = WhetherIn(LineEnt.StartPoint, sOfs)
        spBin = WhetherIn(LineEnt.StartPoint, bOfs)
        epSin = WhetherIn(LineEnt.EndPoint, sOfs)
        epBin = WhetherIn(LineEnt.EndPoint, bOfs)
        
        
        '---------------
        ' 교점이 없을 경우
        '---------------
        If oUB = -1 Then
            '양끝점 모두 Ent내부에 있을 경우는 지움
            If smUB = -1 And bgUB = -1 And spSin = True And _
                spBin = True And epSin = True And epBin = True Then
                LineEnt.Delete
            End If
            
            If smUB = -1 And _
               bgUB = -1 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.Delete
                
            End If
            
        End If
        
        '----------------
        ' 교점이 1개 일 경우
        '----------------
        If oUB = 2 Then
            
            If smUB = 2 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = False And _
               epSin = True And _
               epBin = True _
               Then
                
                LineEnt.EndPoint = IntPnt
                LineEnt.Update
                
            End If
            
            If smUB = 2 And _
               bgUB = 2 And _
               spSin = True And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                LineEnt.StartPoint = IntPnt
                LineEnt.Update
                
            End If
            
            If smUB = 2 And _
               bgUB = -1 And _
               spSin = False And _
               spBin = True And _
               epSin = True And _
               epBin = True _
               Then
                
                LineEnt.Delete
                
            End If
            
            If smUB = 2 And _
               bgUB = -1 And _
               spSin = True And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.Delete
                
            End If
            
            If smUB = -1 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                LineEnt.StartPoint = IntPnt
                LineEnt.Update
                
            End If
            
            If smUB = -1 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.EndPoint = IntPnt
                LineEnt.Update
                
            End If
            
            If smUB = -1 And bgUB = -1 Then
                
                LineEnt.Delete
                
            End If
        
        End If
        
        '----------------
        ' 교점이 2개 일 경우
        '----------------
        If oUB = 5 Then
            
            ' 교점의 순서를 정함(시작점기준)
            intP1(0) = IntPnt(0)
            intP1(1) = IntPnt(1)
            intP1(2) = IntPnt(2)
            intP2(0) = IntPnt(3)
            intP2(1) = IntPnt(4)
            intP2(2) = IntPnt(5)
            
            If Distance(LineEnt.StartPoint, intP1) > Distance(LineEnt.StartPoint, intP2) Then
                tmp(0) = intP1(0)
                tmp(1) = intP1(1)
                tmp(2) = intP1(2)
                intP1(0) = intP2(0)
                intP1(1) = intP2(1)
                intP1(2) = intP2(2)
                intP2(0) = tmp(0)
                intP2(1) = tmp(1)
                intP2(2) = tmp(2)
            End If ' 교점의 순서가 시작점을 기준으로 정렬됨
            
            If smUB = -1 And bgUB = -1 Then
                LineEnt.Delete
            End If
            
            If smUB = -1 And _
               bgUB = 5 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = False _
               Then
               Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                NewLine1.color = LineEnt.color
                NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(LineEnt.EndPoint, intP2)
                NewLine2.color = LineEnt.color
                NewLine2.Linetype = LineEnt.Linetype
                LineEnt.Delete
                NewLine1.Update
                NewLine2.Update
            End If
            
            If smUB = 5 And _
               bgUB = 5 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = False _
               Then
               Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                NewLine1.color = LineEnt.color
                NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(LineEnt.EndPoint, intP2)
                NewLine2.color = LineEnt.color
                NewLine2.Linetype = LineEnt.Linetype
                LineEnt.Delete
                NewLine1.Update
                NewLine2.Update
                
            End If
            
            If smUB = 5 And _
               bgUB = 5 And _
               spSin = True And _
               spBin = True And _
               epSin = True And _
               epBin = True _
               Then
                LineEnt.StartPoint = intP1
                LineEnt.EndPoint = intP2
                LineEnt.Update
                
            End If
            
            If smUB = 5 And _
               bgUB = -1 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                LineEnt.Delete
                
            End If
            
            If smUB = 5 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = True _
               Then
                LineEnt.EndPoint = intP1
                LineEnt.Update
            End If
        
            If smUB = 5 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                LineEnt.StartPoint = intP2
                LineEnt.Update
            
            End If
            
            If smUB = -1 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.EndPoint = intP1
                LineEnt.Update
            
            End If
            
            If smUB = -1 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                LineEnt.StartPoint = intP2
                LineEnt.Update
            
            End If
            
            If smUB = 2 And _
               bgUB = -1 And _
               spSin = False And _
               spBin = True And _
               epSin = True And _
               epBin = True _
               Then
                
                LineEnt.Delete
            
            End If
            
            If smUB = 2 And _
               bgUB = -1 And _
               spSin = True And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.Delete
            
            End If
        
        End If ' 교점이 2개일 때
        
        '----------------
        ' 교점이 3개 일 경우
        '----------------
        If oUB = 8 Then
        
            ' 교점의 순서를 정함(시작점기준)
            For i = 0 To 8 Step 3
                For j = 3 + i To 8 Step 3
                    intP1(0) = IntPnt(i)
                    intP1(1) = IntPnt(i + 1)
                    intP1(2) = IntPnt(i + 2)
                    intP2(0) = IntPnt(j)
                    intP2(1) = IntPnt(j + 1)
                    intP2(2) = IntPnt(j + 2)
                    
                    If Distance(LineEnt.StartPoint, intP1) > Distance(LineEnt.StartPoint, intP2) Then
                        tmp(0) = IntPnt(j)
                        tmp(1) = IntPnt(j + 1)
                        tmp(2) = IntPnt(j + 2)
                        IntPnt(j) = IntPnt(i)
                        IntPnt(j + 1) = IntPnt(i + 1)
                        IntPnt(j + 2) = IntPnt(i + 2)
                        IntPnt(i) = tmp(0)
                        IntPnt(i + 1) = tmp(1)
                        IntPnt(i + 2) = tmp(2)
                    End If
                Next j
            Next i
                    
            intP1(0) = IntPnt(0)
            intP1(1) = IntPnt(1)
            intP1(2) = IntPnt(2)
            intP2(0) = IntPnt(3)
            intP2(1) = IntPnt(4)
            intP2(2) = IntPnt(5)
            intP3(0) = IntPnt(6)
            intP3(1) = IntPnt(7)
            intP3(2) = IntPnt(8)
                        
            If smUB = 8 And _
               bgUB = 8 And _
               spSin = False And _
               spBin = False And _
               epSin = True And _
               epBin = True _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                LineEnt.Delete
            End If
                    
            If smUB = 8 And _
               bgUB = 8 And _
               spSin = True And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(intP1, intP2)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP3, LineEnt.EndPoint)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                LineEnt.Delete
            End If
            
            If smUB = -1 And _
               bgUB = 8 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = True _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                LineEnt.Delete
            
            End If
            
            If smUB = -1 And _
               bgUB = 8 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(intP1, intP2)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP3, LineEnt.EndPoint)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                LineEnt.Delete
                
            End If
            
            If smUB = -1 And _
               bgUB = 8 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = False _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                LineEnt.Delete
            
            End If
        
            If smUB = 5 And _
               bgUB = 8 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = True _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                LineEnt.Delete
            
            End If
        
            If smUB = 5 And _
               bgUB = 8 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP2)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP3, LineEnt.EndPoint)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                LineEnt.Delete
            
            End If
            
            If smUB = 5 And _
               bgUB = 5 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = False _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP3, LineEnt.EndPoint)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                LineEnt.Delete
            
            End If
        
            If smUB = 5 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = False And _
               epSin = True And _
               epBin = True _
               Then
                
                LineEnt.EndPoint = intP1
                LineEnt.Update
            End If
        
            If smUB = 5 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                LineEnt.StartPoint = intP3
                LineEnt.Update
            End If
        
            If smUB = 5 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.EndPoint = intP1
                LineEnt.Update
            End If
        
            If smUB = 8 And _
               bgUB = 5 And _
               spSin = False And _
               spBin = True And _
               epSin = True And _
               epBin = True _
               Then
                
                LineEnt.StartPoint = intP2
                LineEnt.EndPoint = intP3
                LineEnt.Update
            End If
            
            If smUB = 8 And _
               bgUB = 5 And _
               spSin = True And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.StartPoint = intP1
                LineEnt.EndPoint = intP2
                LineEnt.Update
            End If
            
            If smUB = 5 And _
               bgUB = -1 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.Delete
                
            End If
        
        End If ' 교점이 3개일 때
        
        
        '----------------
        ' 교점이 4개 일 경우
        '----------------
        If oUB = 11 Then
        
            ' 교점의 순서를 정함(시작점기준)
            For i = 0 To 11 Step 3
                For j = 3 + i To 11 Step 3
                    intP1(0) = IntPnt(i)
                    intP1(1) = IntPnt(i + 1)
                    intP1(2) = IntPnt(i + 2)
                    intP2(0) = IntPnt(j)
                    intP2(1) = IntPnt(j + 1)
                    intP2(2) = IntPnt(j + 2)
                    
                    If Distance(LineEnt.StartPoint, intP1) > Distance(LineEnt.StartPoint, intP2) Then
                        tmp(0) = IntPnt(j)
                        tmp(1) = IntPnt(j + 1)
                        tmp(2) = IntPnt(j + 2)
                        IntPnt(j) = IntPnt(i)
                        IntPnt(j + 1) = IntPnt(i + 1)
                        IntPnt(j + 2) = IntPnt(i + 2)
                        IntPnt(i) = tmp(0)
                        IntPnt(i + 1) = tmp(1)
                        IntPnt(i + 2) = tmp(2)
                    End If
                Next j
            Next i
                    
            intP1(0) = IntPnt(0)
            intP1(1) = IntPnt(1)
            intP1(2) = IntPnt(2)
            intP2(0) = IntPnt(3)
            intP2(1) = IntPnt(4)
            intP2(2) = IntPnt(5)
            intP3(0) = IntPnt(6)
            intP3(1) = IntPnt(7)
            intP3(2) = IntPnt(8)
            intP4(0) = IntPnt(9)
            intP4(1) = IntPnt(10)
            intP4(2) = IntPnt(11)
            
            If smUB = -1 And _
               bgUB = 5 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.StartPoint = intP2
                LineEnt.EndPoint = intP3
                LineEnt.Update
            End If
            
            If smUB = 11 And _
               bgUB = 8 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.EndPoint = intP1
                LineEnt.Update
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                    NewLine1.Update
            End If
            
            If smUB = 11 And _
               bgUB = 8 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                LineEnt.StartPoint = intP4
                LineEnt.Update
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                    NewLine1.Update
            End If
            
            If smUB = 11 And _
               bgUB = 11 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = False _
               Then
                
                Set NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                    NewLine1.color = LineEnt.color
                    NewLine1.Linetype = LineEnt.Linetype
                Set NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                    NewLine2.color = LineEnt.color
                    NewLine2.Linetype = LineEnt.Linetype
                Set newLine3 = ThisDrawing.ModelSpace.AddLine(intP4, LineEnt.EndPoint)
                    newLine3.color = LineEnt.color
                    newLine3.Linetype = LineEnt.Linetype
                
                NewLine1.Update
                NewLine2.Update
                newLine3.Update
                LineEnt.Delete
                
            End If
            
            If smUB = 11 And _
               bgUB = 5 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                
                LineEnt.StartPoint = intP2
                LineEnt.EndPoint = intP3
                LineEnt.Update
            End If
    
    End If ' 교점이 4개일 때
            
        sOfs.Delete
        bOfs.Delete
        
    End If ' Line일 경우
        
    
    '=============================================================================================
    ' 대상이 Arc인 경우
    '=============================================================================================
    If tEntName = "AcDbArc" Then
        
        Set ArcEnt = tEnt
        
        '검사
        IntPnt = ArcEnt.IntersectWith(Ent, acExtendNone)
        oUB = UBound(IntPnt)
        
        isUB ArcEnt, Ent
        spSin = WhetherIn(ArcEnt.StartPoint, sOfs)
        spBin = WhetherIn(ArcEnt.StartPoint, bOfs)
        epSin = WhetherIn(ArcEnt.EndPoint, sOfs)
        epBin = WhetherIn(ArcEnt.EndPoint, bOfs)
        
        
        '---------------
        ' 교점이 없을 경우
        '---------------
        If oUB = -1 Then
            
            If smUB = -1 And _
               bgUB = -1 And _
               spSin = True And _
               spBin = True And _
               epSin = True And _
               epBin = True _
               Then
                
                ArcEnt.Delete
            
            End If
        End If
        
        '---------------
        ' 교점이 1개인 경우
        '---------------
        If oUB = 2 Then
            
            Set angLine1 = ThisDrawing.ModelSpace.AddLine(ArcEnt.Center, IntPnt)
            Ang1 = angLine1.Angle
            
            If smUB = 2 And _
               bgUB = 2 And _
               spSin = True And _
               spBin = True And _
               epSin = False And _
               epBin = False _
               Then
                
                ArcEnt.StartAngle = Ang1
                ArcEnt.Update
                
            End If
            
            If smUB = 2 And _
               bgUB = 2 And _
               spSin = False And _
               spBin = False And _
               epSin = True And _
               epBin = True _
               Then
                
                ArcEnt.EndAngle = Ang1
                ArcEnt.Update
                
            End If
            
            angLine1.Delete
        
        End If ' 교점이 1개이면
        
        '---------------
        ' 교점이 2개인 경우
        '---------------
        If oUB = 5 Then
                
            intP1(0) = IntPnt(0)
            intP1(1) = IntPnt(1)
            intP1(2) = IntPnt(2)
            intP2(0) = IntPnt(3)
            intP2(1) = IntPnt(4)
            intP2(2) = IntPnt(5)
                
            Set angLine1 = ThisDrawing.ModelSpace.AddLine(ArcEnt.Center, intP1)
            Set angLine2 = ThisDrawing.ModelSpace.AddLine(ArcEnt.Center, intP2)
            Ang1 = angLine1.Angle
            Ang2 = angLine2.Angle
            sAng = ArcEnt.StartAngle
            eAng = ArcEnt.EndAngle
            aCP(0) = ArcEnt.Center(0)
            aCP(1) = ArcEnt.Center(1)
            aCP(2) = ArcEnt.Center(2)
            Rad = ArcEnt.Radius
            
            If eAng < sAng Then eAng = eAng + 2 * (Atn(1) * 4)
            If Ang1 < sAng Then Ang1 = Ang1 + 2 * (Atn(1) * 4)
            If Ang2 < sAng Then Ang2 = Ang2 + 2 * (Atn(1) * 4)
            
            If Ang1 > Ang2 Then
                tmpAng = Ang1
                Ang1 = Ang2
                Ang2 = tmpAng
            End If
            
            If smUB = 5 And _
               bgUB = -1 And _
               spSin = False And _
               spBin = True And _
               epSin = False And _
               epBin = True _
               Then
                
                ArcEnt.Delete
                
            End If
            
            If smUB = 5 And _
               bgUB = 5 And _
               spSin = False And _
               spBin = False And _
               epSin = False And _
               epBin = False _
               Then
                Set newArc1 = ThisDrawing.ModelSpace.AddArc(aCP, Rad, sAng, Ang1)
                    newArc1.color = ArcEnt.color
                    newArc1.Linetype = ArcEnt.Linetype
                Set newArc2 = ThisDrawing.ModelSpace.AddArc(aCP, Rad, Ang2, eAng)
                    newArc2.color = ArcEnt.color
                    newArc2.Linetype = ArcEnt.Linetype
                
                newArc1.Update
                newArc2.Update
                ArcEnt.Delete
                
            End If
            
            angLine1.Delete
            angLine2.Delete
        
        End If ' 교점이 2개이면
    
        sOfs.Delete
        bOfs.Delete
    
    End If ' Arc일 경우
        
    '=============================================================================================
    ' 대상이 Circle인 경우
    '=============================================================================================
    If tEntName = "AcDbCircle" Then
    
        Set CircleEnt = tEnt
        
        '검사
        IntPnt = CircleEnt.IntersectWith(Ent, acExtendNone)
        oUB = UBound(IntPnt)
        cCp(0) = CircleEnt.Center(0)
        cCp(1) = CircleEnt.Center(1)
        cCp(2) = CircleEnt.Center(2)
        Rad = CircleEnt.Radius
        cpIn = WhetherIn(cCp, Ent)
        
        'MsgBox "oUB = " & oUB & vbCrLf & "cpIn = " & cpIn
        
        '---------------
        ' 교점이 없을 경우
        '---------------
        If oUB = -1 And cpIn = True Then
            CircleEnt.Delete
        End If
        
        '---------------
        ' 교점이 2개일 경우
        '---------------
        If oUB = 5 Then
            
            intP1(0) = IntPnt(0)
            intP1(1) = IntPnt(1)
            intP1(2) = IntPnt(2)
            intP2(0) = IntPnt(3)
            intP2(1) = IntPnt(4)
            intP2(2) = IntPnt(5)
            
            cCp(0) = CircleEnt.Center(0)
            cCp(1) = CircleEnt.Center(1)
            cCp(2) = CircleEnt.Center(2)
            Rad = CircleEnt.Radius
                
            Set angLine1 = ThisDrawing.ModelSpace.AddLine(cCp, intP1)
            Set angLine2 = ThisDrawing.ModelSpace.AddLine(cCp, intP2)
            Ang1 = angLine1.Angle
            Ang2 = angLine2.Angle
            If Ang1 > Ang2 Then
                tmpAng = Ang1
                Ang1 = Ang2
                Ang2 = tmpAng
            End If
            
            mAng = (Ang1 + Ang2) / 2
            midPnt = ThisDrawing.Utility.PolarPoint(cCp, mAng, Rad)
            
            If WhetherIn(midPnt, Ent) Then
                Set newArc1 = ThisDrawing.ModelSpace.AddArc(cCp, Rad, Ang2, Ang1)
                newArc1.color = CircleEnt.color
                newArc1.Linetype = CircleEnt.Linetype
                
                Else
                Set newArc1 = ThisDrawing.ModelSpace.AddArc(cCp, Rad, Ang1, Ang2)
                newArc1.color = CircleEnt.color
                newArc1.Linetype = CircleEnt.Linetype
            End If
                
            newArc1.Update
            angLine1.Delete
            angLine2.Delete
            CircleEnt.Delete
            
        End If ' 교점이 2개일 때
    
    
    End If ' Circle일 경우


Next


End Sub

Private Function WhetherIn(Point As Variant, Entity As AcadEntity) As Boolean
    Dim PickPnt As Variant
    Dim dLine As AcadLine
    Dim IntP As Variant
    
        WhetherIn = False
    
    Dim UPnt As Variant
        UPnt = ThisDrawing.Utility.PolarPoint(Point, Dtr(90), 0.1)
    Set dLine = ThisDrawing.ModelSpace.AddLine(Point, UPnt)
    
    IntP = dLine.IntersectWith(Entity, acExtendThisEntity)
        dLine.Delete
    
    Dim PntNo As Integer
        PntNo = (UBound(IntP) - 2) / 3
    
    ' 얻어진 교점을 Y좌표의 순서대로 정열함
    Dim i As Integer
    Dim j As Integer
    Dim tmpPnt(0 To 2) As Double
    
    For i = 0 To PntNo - 1
        For j = i + 1 To PntNo
            If IntP(3 * i + 1) > IntP(3 * j + 1) Then
                tmpPnt(0) = IntP(3 * i)
                tmpPnt(1) = IntP(3 * i + 1)
                tmpPnt(2) = IntP(3 * i + 2)
                
                IntP(3 * i) = IntP(3 * j)
                IntP(3 * i + 1) = IntP(3 * j + 1)
                IntP(3 * i + 2) = IntP(3 * j + 2)
                
                IntP(3 * j) = tmpPnt(0)
                IntP(3 * j + 1) = tmpPnt(1)
                IntP(3 * j + 2) = tmpPnt(2)
            End If
        Next j
    Next i
    
    For i = 0 To PntNo Step 2
        If Point(1) > IntP(3 * i + 1) And Point(1) < IntP(3 * i + 4) Then
            WhetherIn = True
        End If
    Next i
    
End Function


Private Sub isUB(trimedEnt As AcadEntity, Ent As AcadEntity)
    
    Dim itP1 As Variant
    Dim itP2 As Variant
        
        If Ent.ObjectName = "AcDbRegion" Then
            Dim regEnt As AcadRegion
            Dim SrEnt As AcadRegion
            Dim BrEnt As AcadRegion
            Dim bP(0 To 2) As Double
                Set regEnt = Ent
                bP(0) = regEnt.Centroid(0)
                bP(1) = regEnt.Centroid(1)
                bP(2) = 0
                
                Set sOfs = regEnt.Copy
                Set bOfs = regEnt.Copy
                
                sOfs.ScaleEntity bP, 0.999
                sOfs.Update
                bOfs.ScaleEntity bP, 1.001
                bOfs.Update
                
            Else
            sOffset = Ent.Offset(0.01)
            bOffset = Ent.Offset(-0.01)
        
            Set sOfs = sOffset(0)
            Set bOfs = bOffset(0)
        
            If sOffset(0).Area > bOffset(0).Area Then
                sOffset(0).Delete
                bOffset(0).Delete
                sOffset = Ent.Offset(-0.01)
                bOffset = Ent.Offset(0.01)
            End If
        
            Set sOfs = sOffset(0)
            Set bOfs = bOffset(0)
        
        End If
        
        itP1 = trimedEnt.IntersectWith(sOfs, acExtendNone)
        itP2 = trimedEnt.IntersectWith(bOfs, acExtendNone)
    
        
    smUB = UBound(itP1)
    bgUB = UBound(itP2)

End Sub

Private Function Dtr(Degree As Double) As Double

    Dtr = (Atn(1) * 4) * Degree / 180#
    
End Function

Private Function Distance(Point1 As Variant, Point2 As Variant) As Double
    Distance = Sqr((Point2(0) - Point1(0)) ^ 2 + (Point2(1) - Point1(1)) ^ 2)
End Function



