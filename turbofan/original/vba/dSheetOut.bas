Attribute VB_Name = "dSheetOut"
Option Explicit

Public Sub datasheet() 'Word에서 송풍기 Data Sheet 자동 작성 루틴

On Error Resume Next

'Word로의 접속
Dim wdApp As New Word.Application
    wdApp.Visible = True
    wdApp.Documents.Add ThisDrawing.Application.Path & "\ALISP\Turbo Fan Design\Word\Fandatasheet.dot"
    wdApp.Activate
    wdApp.Visible = True
    
    ' Book Mark 삽입
    With wdApp.ActiveDocument
        .Bookmarks("CName1").Range.InsertAfter CName
        .Bookmarks("CName2").Range.InsertAfter CName
        .Bookmarks("Date1").Range.InsertAfter frmOutput.txtDate.text
    End With

    ' 회사로고 넣기
    'If LogoFile <> "" Then
    '    wdApp.ActiveDocument.InlineShapes.AddPicture LogoFile, , , wdApp.ActiveDocument _
    '        .Tables(1).Cell(6, 1).Range
        'wdApp.ActiveDocument.InlineShapes(1).Height = 41
        'wdApp.ActiveDocument.InlineShapes(1).Width = 267
    'End If

    
        '고객명 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=1, Column:=1).Range
            .Delete
            .InsertAfter text:="Messrs : " & frmOutput.txtCustomer.text
        End With
        
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=2).Range
            .Delete
            .InsertAfter text:=frmOutput.txtCustomer.text
        End With
        
        '날짜 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=4).Range
            .Delete
            .InsertAfter text:=frmOutput.txtDate.text
        End With
        
        '풍량 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=14, Column:=2).Range
            .Delete
            .InsertAfter text:=Format(q, "###.0")
        End With
        
        '풍압 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=15, Column:=2).Range
            .Delete
            .InsertAfter text:=Format(ps, "###")
        End With
        
        '회전수 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=16, Column:=2).Range
            .Delete
            .InsertAfter text:=Format(N, "####")
        End With
        
        '축동력 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=17, Column:=2).Range
            .Delete
            .InsertAfter text:=Format(spower, "###.00")
        End With
        
        'Fan 효율 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=18, Column:=2).Range
            .Delete
            .InsertAfter text:=Format(FanEff * 100, "##.0")
        End With
        
        '온도 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=15, Column:=5).Range
            .Delete
            .InsertAfter text:=temp
        End With
        
        '가스밀도 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=16, Column:=5).Range
            .Delete
            .InsertAfter text:=Format(gamma, "0.000")
        End With
        
        '흡입구 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=22, Column:=3).Range
            .Delete
            .InsertAfter text:=Format(frmOutput.txtInlet.text, "###")
        End With
        
        '토출구 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=23, Column:=3).Range
            .Delete
            .InsertAfter text:=Lout & "×" & Wout & " mm"
        End With
        
        '회전차외경 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=24, Column:=3).Range
            .Delete
            .InsertAfter text:="φ " & Format(D2 * 1000, "###")
        End With
        
        '회전차내경 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=25, Column:=3).Range
            .Delete
            .InsertAfter text:="φ " & Format(D1 * 1000, "###")
        End With
        
        
        
        '케이싱 재질 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=25, Column:=4).Range
            .Delete
            .InsertAfter text:=frmOutput.txtImpMatl.text '회전차 재질과 동일하게 선정
        End With
        
        '회전차 재질 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=25, Column:=5).Range
            .Delete
            .InsertAfter text:=frmOutput.txtImpMatl.text
        End With
        
        '축 재질 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=25, Column:=7).Range
            .Delete
            .InsertAfter text:=frmOutput.cboShaftMatl.text
        End With
                
        '베어링경 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=26, Column:=3).Range
            .Delete
            .InsertAfter text:=frmOutput.txtBearingImp.text
        End With
        
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=27, Column:=3).Range
            .Delete
            .InsertAfter text:=frmOutput.txtBearingPulley.text
        End With
        
        '전동방식 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=26, Column:=5).Range
            .Delete
            .InsertAfter text:=frmOutput.txtPowerTransMethod.text
        End With
        
        
        '모터 Maker 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=34, Column:=2).Range
            .Delete
            .InsertAfter text:=frmOutput.txtMMaker.text
        End With
        
        
        '모터 전압 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=35, Column:=2).Range
            .Delete
            .InsertAfter text:=motorvoltage + " V"
        End With
        
        '모터 상-극수 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=35, Column:=4).Range
            Dim phasepoles As String
                phasepoles = "3 φ  /  " + motorpoles + " P"
            .Delete
            .InsertAfter text:=phasepoles
        End With
        
        '모터 출력 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=36, Column:=2).Range
            .Delete
            .InsertAfter text:=motoroutput + " kW"
        End With
        
        '모터 후레임 번호 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=36, Column:=4).Range
            .Delete
            .InsertAfter text:=motorframe
        End With
        
        '모터 회전수 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=36, Column:=6).Range
            .Delete
            .InsertAfter text:=motorrpm & " r.p.m"
        End With
        
        '모터 효율 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=37, Column:=2).Range
            .Delete
            .InsertAfter text:=motoreff & " %"
        End With
        
        '모터 역율 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=37, Column:=4).Range
            .Delete
            .InsertAfter text:=motorpf & " %"
        End With
        
        '모터 부하 전류 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=37, Column:=6).Range
            .Delete
            .InsertAfter text:=Format(motorloadamp, "###.0") & " A"
        End With
        
        '모터 기동 전류 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=38, Column:=2).Range
            .Delete
            .InsertAfter text:=Format(motorstartamp, "###.0") & " A"
        End With
        
        '모터 부하 토오크 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=38, Column:=4).Range
            .Delete
            .InsertAfter text:=motorloadtor & " kg-m"
        End With
        
        '모터 기동 토오크 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=38, Column:=6).Range
            .Delete
            .InsertAfter text:=motorstarttor & " kg-m"
        End With
        
        '모터 기동 토오크 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=39, Column:=2).Range
            .Delete
            .InsertAfter text:=motormaxtor & " kg-m"
        End With
        
        '모터 GD2 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=39, Column:=4).Range
            .Delete
            .InsertAfter text:=motorgd2 & " kg-㎡"
        End With
        
        '모터 중량 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=39, Column:=6).Range
            .Delete
            .InsertAfter text:=motorwt & " kg"
        End With
        
        '송풍기 방향 삽입
        With wdApp.ActiveDocument.Tables(1).Cell(Row:=42, Column:=2).Range
            .Delete
            .InsertAfter text:=Direction
        End With
        

End Sub
