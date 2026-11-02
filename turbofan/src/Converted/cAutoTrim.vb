' 원본: cAutoTrim.cls (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Class cAutoTrim

    Public Ent As Object ' 자를 PolyLine

    Dim tEnt As Object ' 잘릴 대상
    Dim tEntName As String ' 잘릴 대상의 종류명
    Dim IntPnt As Object ' 얻어지는 교점
    Dim LineEnt As Object ' Line을 할당
    Dim ArcEnt As Object ' Arc를 할당
    Dim CircleEnt As Object ' Circle을 할당

    Dim oUB As Integer
    Dim bgUB As Integer
    Dim smUB As Integer
    Dim sOffset As Object
    Dim bOffset As Object

    Dim spSin As Boolean
    Dim spBin As Boolean
    Dim epSin As Boolean
    Dim epBin As Boolean


    Dim intP1(2) As Double
    Dim intP2(2) As Double
    Dim intP3(2) As Double
    Dim intP4(2) As Double
    Dim tmpPnt(2) As Object

    Dim tmpLine As Object
    Dim NewLine1 As Object
    Dim NewLine2 As Object
    Dim newLine3 As Object
    Dim Length1 As Double
    Dim Length2 As Double
    Dim Length3 As Double
    Dim i As Integer
    Dim j As Integer
    Dim L(3) As Double
    Dim tmp(2) As Double

    Dim Ang1 As Double
    Dim Ang2 As Double
    Dim sAng As Double
    Dim eAng As Double
    Dim tmpAng As Double
    Dim angLine1 As Object
    Dim angLine2 As Object
    Dim newArc1 As Object
    Dim newArc2 As Object
    Dim aCP(2) As Double
    Dim Rad As Double
    Dim cCp(2) As Double
    Dim cpIn As Boolean
    Dim mAng As Double
    Dim midPnt As Object

    Dim sOfs As Object
    Dim bOfs As Object

    Public Sub DoTrim()
        Dim MinPnt As Object '좌하점
        Dim MaxPnt As Object '우상점
        Dim Sel As Object
        Dim Col As New VBCollection

        ' Ent의 BoundBox 점을 얻어냄
            Ent.GetBoundingBox(MinPnt, MaxPnt)

        ' SelectionSet을 이용하여 Ent에 포함 또는 인접한 Entity를 Collection으로 만듬
            Sel = ThisDrawing.SelectionSets.Add("SSet") ' SelectionSet을 생성
            Sel.Select(acSelectionSetCrossing, MinPnt, MaxPnt) 'Crossing을 이용하여 Entity를 선택

        ' Selection을 Collection에 넘겨줌
            For Each tEnt In Sel
                Col.Add(tEnt)
            Next

        Sel.Delete ' 사용한 Selection을 소멸시킴

    For Each tEnt In Col

            tEntName = VbCopy(tEnt.ObjectName)

        '=============================================================================================
        ' 대상이 Line인 경우
        '=============================================================================================
        If tEntName = "AcDbLine" Then

            LineEnt = tEnt

            '검사
            IntPnt = LineEnt.IntersectWith(Ent, acExtendNone)
            oUB = UBound(IntPnt)
            isUB(LineEnt, Ent)
            spSin = WhetherIn(LineEnt.StartPoint, sOfs)
            spBin = WhetherIn(LineEnt.StartPoint, bOfs)
            epSin = WhetherIn(LineEnt.EndPoint, sOfs)
            epBin = WhetherIn(LineEnt.EndPoint, bOfs)


            '---------------
            ' 교점이 없을 경우
            '---------------
            If oUB = -1 Then
                '양끝점 모두 Ent내부에 있을 경우는 지움
                If smUB = -1 And bgUB = -1 And spSin = True And spBin = True And epSin = True And epBin = True Then
                    LineEnt.Delete
                End If

                If smUB = -1 And bgUB = -1 And spSin = False And spBin = True And epSin = False And epBin = True Then

                    LineEnt.Delete

                End If

            End If

            '----------------
            ' 교점이 1개 일 경우
            '----------------
            If oUB = 2 Then

                If smUB = 2 And bgUB = 2 And spSin = False And spBin = False And epSin = True And epBin = True Then

                    LineEnt.EndPoint = VbCopy(IntPnt)
                    LineEnt.Update

                End If

                If smUB = 2 And bgUB = 2 And spSin = True And spBin = True And epSin = False And epBin = False Then

                    LineEnt.StartPoint = VbCopy(IntPnt)
                    LineEnt.Update

                End If

                If smUB = 2 And bgUB = -1 And spSin = False And spBin = True And epSin = True And epBin = True Then

                    LineEnt.Delete

                End If

                If smUB = 2 And bgUB = -1 And spSin = True And spBin = True And epSin = False And epBin = True Then

                    LineEnt.Delete

                End If

                If smUB = -1 And bgUB = 2 And spSin = False And spBin = True And epSin = False And epBin = False Then

                    LineEnt.StartPoint = VbCopy(IntPnt)
                    LineEnt.Update

                End If

                If smUB = -1 And bgUB = 2 And spSin = False And spBin = False And epSin = False And epBin = True Then

                    LineEnt.EndPoint = VbCopy(IntPnt)
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

                If smUB = -1 And bgUB = 5 And spSin = False And spBin = False And epSin = False And epBin = False Then
                   NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                    NewLine1.color = VbCopy(LineEnt.color)
                    NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(LineEnt.EndPoint, intP2)
                    NewLine2.color = VbCopy(LineEnt.color)
                    NewLine2.Linetype = VbCopy(LineEnt.Linetype)
                    LineEnt.Delete
                    NewLine1.Update
                    NewLine2.Update
                End If

                If smUB = 5 And bgUB = 5 And spSin = False And spBin = False And epSin = False And epBin = False Then
                   NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                    NewLine1.color = VbCopy(LineEnt.color)
                    NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(LineEnt.EndPoint, intP2)
                    NewLine2.color = VbCopy(LineEnt.color)
                    NewLine2.Linetype = VbCopy(LineEnt.Linetype)
                    LineEnt.Delete
                    NewLine1.Update
                    NewLine2.Update

                End If

                If smUB = 5 And bgUB = 5 And spSin = True And spBin = True And epSin = True And epBin = True Then
                    LineEnt.StartPoint = VbCopy(intP1)
                    LineEnt.EndPoint = VbCopy(intP2)
                    LineEnt.Update

                End If

                If smUB = 5 And bgUB = -1 And spSin = False And spBin = True And epSin = False And epBin = True Then
                    LineEnt.Delete

                End If

                If smUB = 5 And bgUB = 2 And spSin = False And spBin = False And epSin = False And epBin = True Then
                    LineEnt.EndPoint = VbCopy(intP1)
                    LineEnt.Update
                End If

                If smUB = 5 And bgUB = 2 And spSin = False And spBin = True And epSin = False And epBin = False Then

                    LineEnt.StartPoint = VbCopy(intP2)
                    LineEnt.Update

                End If

                If smUB = -1 And bgUB = 2 And spSin = False And spBin = False And epSin = False And epBin = True Then

                    LineEnt.EndPoint = VbCopy(intP1)
                    LineEnt.Update

                End If

                If smUB = -1 And bgUB = 2 And spSin = False And spBin = True And epSin = False And epBin = False Then

                    LineEnt.StartPoint = VbCopy(intP2)
                    LineEnt.Update

                End If

                If smUB = 2 And bgUB = -1 And spSin = False And spBin = True And epSin = True And epBin = True Then

                    LineEnt.Delete

                End If

                If smUB = 2 And bgUB = -1 And spSin = True And spBin = True And epSin = False And epBin = True Then

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

                If smUB = 8 And bgUB = 8 And spSin = False And spBin = False And epSin = True And epBin = True Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    LineEnt.Delete
                End If

                If smUB = 8 And bgUB = 8 And spSin = True And spBin = True And epSin = False And epBin = False Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(intP1, intP2)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP3, LineEnt.EndPoint)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    LineEnt.Delete
                End If

                If smUB = -1 And bgUB = 8 And spSin = False And spBin = False And epSin = False And epBin = True Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    LineEnt.Delete

                End If

                If smUB = -1 And bgUB = 8 And spSin = False And spBin = True And epSin = False And epBin = False Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(intP1, intP2)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP3, LineEnt.EndPoint)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    LineEnt.Delete

                End If

                If smUB = -1 And bgUB = 8 And spSin = False And spBin = False And epSin = False And epBin = False Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    LineEnt.Delete

                End If

                If smUB = 5 And bgUB = 8 And spSin = False And spBin = False And epSin = False And epBin = True Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    LineEnt.Delete

                End If

                If smUB = 5 And bgUB = 8 And spSin = False And spBin = True And epSin = False And epBin = False Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP2)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP3, LineEnt.EndPoint)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    LineEnt.Delete

                End If

                If smUB = 5 And bgUB = 5 And spSin = False And spBin = False And epSin = False And epBin = False Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP3, LineEnt.EndPoint)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    LineEnt.Delete

                End If

                If smUB = 5 And bgUB = 2 And spSin = False And spBin = False And epSin = True And epBin = True Then

                    LineEnt.EndPoint = VbCopy(intP1)
                    LineEnt.Update
                End If

                If smUB = 5 And bgUB = 2 And spSin = False And spBin = True And epSin = False And epBin = False Then

                    LineEnt.StartPoint = VbCopy(intP3)
                    LineEnt.Update
                End If

                If smUB = 5 And bgUB = 2 And spSin = False And spBin = False And epSin = False And epBin = True Then

                    LineEnt.EndPoint = VbCopy(intP1)
                    LineEnt.Update
                End If

                If smUB = 8 And bgUB = 5 And spSin = False And spBin = True And epSin = True And epBin = True Then

                    LineEnt.StartPoint = VbCopy(intP2)
                    LineEnt.EndPoint = VbCopy(intP3)
                    LineEnt.Update
                End If

                If smUB = 8 And bgUB = 5 And spSin = True And spBin = True And epSin = False And epBin = True Then

                    LineEnt.StartPoint = VbCopy(intP1)
                    LineEnt.EndPoint = VbCopy(intP2)
                    LineEnt.Update
                End If

                If smUB = 5 And bgUB = -1 And spSin = False And spBin = True And epSin = False And epBin = True Then

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

                If smUB = -1 And bgUB = 5 And spSin = False And spBin = True And epSin = False And epBin = True Then

                    LineEnt.StartPoint = VbCopy(intP2)
                    LineEnt.EndPoint = VbCopy(intP3)
                    LineEnt.Update
                End If

                If smUB = 11 And bgUB = 8 And spSin = False And spBin = False And epSin = False And epBin = True Then

                    LineEnt.EndPoint = VbCopy(intP1)
                    LineEnt.Update
                    NewLine1 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                        NewLine1.Update
                End If

                If smUB = 11 And bgUB = 8 And spSin = False And spBin = True And epSin = False And epBin = False Then

                    LineEnt.StartPoint = VbCopy(intP4)
                    LineEnt.Update
                    NewLine1 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                        NewLine1.Update
                End If

                If smUB = 11 And bgUB = 11 And spSin = False And spBin = False And epSin = False And epBin = False Then

                    NewLine1 = ThisDrawing.ModelSpace.AddLine(LineEnt.StartPoint, intP1)
                        NewLine1.color = VbCopy(LineEnt.color)
                        NewLine1.Linetype = VbCopy(LineEnt.Linetype)
                    NewLine2 = ThisDrawing.ModelSpace.AddLine(intP2, intP3)
                        NewLine2.color = VbCopy(LineEnt.color)
                        NewLine2.Linetype = VbCopy(LineEnt.Linetype)
                    newLine3 = ThisDrawing.ModelSpace.AddLine(intP4, LineEnt.EndPoint)
                        newLine3.color = VbCopy(LineEnt.color)
                        newLine3.Linetype = VbCopy(LineEnt.Linetype)

                    NewLine1.Update
                    NewLine2.Update
                    newLine3.Update
                    LineEnt.Delete

                End If

                If smUB = 11 And bgUB = 5 And spSin = False And spBin = True And epSin = False And epBin = True Then

                    LineEnt.StartPoint = VbCopy(intP2)
                    LineEnt.EndPoint = VbCopy(intP3)
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

            ArcEnt = tEnt

            '검사
            IntPnt = ArcEnt.IntersectWith(Ent, acExtendNone)
            oUB = UBound(IntPnt)

            isUB(ArcEnt, Ent)
            spSin = WhetherIn(ArcEnt.StartPoint, sOfs)
            spBin = WhetherIn(ArcEnt.StartPoint, bOfs)
            epSin = WhetherIn(ArcEnt.EndPoint, sOfs)
            epBin = WhetherIn(ArcEnt.EndPoint, bOfs)


            '---------------
            ' 교점이 없을 경우
            '---------------
            If oUB = -1 Then

                If smUB = -1 And bgUB = -1 And spSin = True And spBin = True And epSin = True And epBin = True Then

                    ArcEnt.Delete

                End If
            End If

            '---------------
            ' 교점이 1개인 경우
            '---------------
            If oUB = 2 Then

                angLine1 = ThisDrawing.ModelSpace.AddLine(ArcEnt.Center, IntPnt)
                Ang1 = VbCopy(angLine1.Angle)

                If smUB = 2 And bgUB = 2 And spSin = True And spBin = True And epSin = False And epBin = False Then

                    ArcEnt.StartAngle = VbCopy(Ang1)
                    ArcEnt.Update

                End If

                If smUB = 2 And bgUB = 2 And spSin = False And spBin = False And epSin = True And epBin = True Then

                    ArcEnt.EndAngle = VbCopy(Ang1)
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

                angLine1 = ThisDrawing.ModelSpace.AddLine(ArcEnt.Center, intP1)
                angLine2 = ThisDrawing.ModelSpace.AddLine(ArcEnt.Center, intP2)
                Ang1 = VbCopy(angLine1.Angle)
                Ang2 = VbCopy(angLine2.Angle)
                sAng = VbCopy(ArcEnt.StartAngle)
                eAng = VbCopy(ArcEnt.EndAngle)
                aCP(0) = ArcEnt.Center(0)
                aCP(1) = ArcEnt.Center(1)
                aCP(2) = ArcEnt.Center(2)
                Rad = VbCopy(ArcEnt.Radius)

                If eAng < sAng Then eAng = eAng + 2 * (Atn(1) * 4)
                If Ang1 < sAng Then Ang1 = Ang1 + 2 * (Atn(1) * 4)
                If Ang2 < sAng Then Ang2 = Ang2 + 2 * (Atn(1) * 4)

                If Ang1 > Ang2 Then
                    tmpAng = VbCopy(Ang1)
                    Ang1 = VbCopy(Ang2)
                    Ang2 = VbCopy(tmpAng)
                End If

                If smUB = 5 And bgUB = -1 And spSin = False And spBin = True And epSin = False And epBin = True Then

                    ArcEnt.Delete

                End If

                If smUB = 5 And bgUB = 5 And spSin = False And spBin = False And epSin = False And epBin = False Then
                    newArc1 = ThisDrawing.ModelSpace.AddArc(aCP, Rad, sAng, Ang1)
                        newArc1.color = VbCopy(ArcEnt.color)
                        newArc1.Linetype = VbCopy(ArcEnt.Linetype)
                    newArc2 = ThisDrawing.ModelSpace.AddArc(aCP, Rad, Ang2, eAng)
                        newArc2.color = VbCopy(ArcEnt.color)
                        newArc2.Linetype = VbCopy(ArcEnt.Linetype)

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

            CircleEnt = tEnt

            '검사
            IntPnt = CircleEnt.IntersectWith(Ent, acExtendNone)
            oUB = UBound(IntPnt)
            cCp(0) = CircleEnt.Center(0)
            cCp(1) = CircleEnt.Center(1)
            cCp(2) = CircleEnt.Center(2)
            Rad = VbCopy(CircleEnt.Radius)
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
                Rad = VbCopy(CircleEnt.Radius)

                angLine1 = ThisDrawing.ModelSpace.AddLine(cCp, intP1)
                angLine2 = ThisDrawing.ModelSpace.AddLine(cCp, intP2)
                Ang1 = VbCopy(angLine1.Angle)
                Ang2 = VbCopy(angLine2.Angle)
                If Ang1 > Ang2 Then
                    tmpAng = VbCopy(Ang1)
                    Ang1 = VbCopy(Ang2)
                    Ang2 = VbCopy(tmpAng)
                End If

                mAng = (Ang1 + Ang2) / 2
                midPnt = PolarPoint(cCp, mAng, Rad)

                If WhetherIn(midPnt, Ent) Then
                    newArc1 = ThisDrawing.ModelSpace.AddArc(cCp, Rad, Ang2, Ang1)
                    newArc1.color = VbCopy(CircleEnt.color)
                    newArc1.Linetype = VbCopy(CircleEnt.Linetype)

                    Else
                    newArc1 = ThisDrawing.ModelSpace.AddArc(cCp, Rad, Ang1, Ang2)
                    newArc1.color = VbCopy(CircleEnt.color)
                    newArc1.Linetype = VbCopy(CircleEnt.Linetype)
                End If

                newArc1.Update
                angLine1.Delete
                angLine2.Delete
                CircleEnt.Delete

            End If ' 교점이 2개일 때


        End If ' Circle일 경우


    Next


    End Sub

    Private Function WhetherIn(ByRef Point As Object, ByRef Entity As Object) As Boolean
        Dim PickPnt As Object
        Dim dLine As Object
        Dim IntP As Object
        Dim UPnt As Object
        Dim PntNo As Integer
        Dim i As Integer
        Dim j As Integer
        Dim tmpPnt(2) As Double

            WhetherIn = False

            UPnt = PolarPoint(Point, Dtr(90), 0.1)
        dLine = ThisDrawing.ModelSpace.AddLine(Point, UPnt)

        IntP = dLine.IntersectWith(Entity, acExtendThisEntity)
            dLine.Delete

            PntNo = (UBound(IntP) - 2) / 3

        ' 얻어진 교점을 Y좌표의 순서대로 정열함

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


    Private Sub isUB(ByRef trimedEnt As Object, ByRef Ent As Object)
        Dim itP1 As Object
        Dim itP2 As Object
        Dim regEnt As Object
        Dim SrEnt As Object
        Dim BrEnt As Object
        Dim bP(2) As Double


            If Ent.ObjectName = "AcDbRegion" Then
                    regEnt = Ent
                    bP(0) = regEnt.Centroid(0)
                    bP(1) = regEnt.Centroid(1)
                    bP(2) = 0

                    sOfs = regEnt.Copy
                    bOfs = regEnt.Copy

                    sOfs.ScaleEntity(bP, 0.999)
                    sOfs.Update
                    bOfs.ScaleEntity(bP, 1.001)
                    bOfs.Update

                Else
                sOffset = Ent.Offset(0.01)
                bOffset = Ent.Offset(-0.01)

                sOfs = sOffset(0)
                bOfs = bOffset(0)

                If sOffset(0).Area > bOffset(0).Area Then
                    sOffset(0).Delete
                    bOffset(0).Delete
                    sOffset = Ent.Offset(-0.01)
                    bOffset = Ent.Offset(0.01)
                End If

                sOfs = sOffset(0)
                bOfs = bOffset(0)

            End If

            itP1 = trimedEnt.IntersectWith(sOfs, acExtendNone)
            itP2 = trimedEnt.IntersectWith(bOfs, acExtendNone)


        smUB = UBound(itP1)
        bgUB = UBound(itP2)

    End Sub

    Private Function Dtr(ByVal Degree As Double) As Double

        Dtr = (Atn(1) * 4) * Degree / 180#

    End Function

    Private Function Distance(ByRef Point1 As Object, ByRef Point2 As Object) As Double
        Distance = Sqr((Point2(0) - Point1(0)) ^ 2 + (Point2(1) - Point1(1)) ^ 2)
    End Function




End Class
