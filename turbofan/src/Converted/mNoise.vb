' 원본: mNoise.bas (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Module mNoise

    Public Sub Maker_Noize_Report() 'Word에서 Report 자동 작성 루틴
        Dim wdApp As Object

        'Word로의 접속
        wdApp = CreateObject("Word.Application")
        wdApp.Visible = True
        wdApp.Documents.Add(SupportFolder() & "\Word\소음진동 계산서(Turbo).dot")
        wdApp.Activate
        wdApp.Visible = True

            '고객명 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=2, Column:=2).Range
                .InsertAfter(text:=(frmOutput.txtCustomer.text))
            End With

             '설계일자 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=2, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtDate.text))
            End With

             '풍량 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=5, Column:=1).Range
                .InsertAfter(text:=(frmOutput.txtQ.text))
            End With

             '풍압 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=5, Column:=2).Range
                .InsertAfter(text:=(frmOutput.txtPs.text))
            End With

             '온도 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=5, Column:=3).Range
                .InsertAfter(text:=(frmOutput.txtTemp.text))
            End With

             '밀도 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=5, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtDensity.text))
            End With

            '송풍기 중량 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=7, Column:=2).Range
                .InsertAfter(text:=frmNoise.txtFanWeight.text & " kgf")
            End With

            '모터 중량 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=7, Column:=4).Range
                .InsertAfter(text:=frmNoise.txtMotorWeight.text & " kgf")
            End With

            '총 중량 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=7, Column:=6).Range
                .InsertAfter(text:=frmNoise.txtTotalWeight.text & " kgf")
            End With

            '송풍기 회전수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=8, Column:=2).Range
                .InsertAfter(text:=frmNoise.txtFanRevolution.text & " r.p.m")
            End With

            '방진의 종류 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=8, Column:=4).Range
                .InsertAfter(text:=(frmNoise.cboKind.text))
            End With

            '방진의 변위 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=8, Column:=6).Range
                .InsertAfter(text:=frmNoise.cboDisplacement.text & " cm")
            End With

            '방진의 개수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=2).Range
                .InsertAfter(text:=frmNoise.txtNoSA.text & " EA")
            End With

            '방진 스프링 상수의 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=4).Range
                .InsertAfter(text:=frmNoise.txtSpringConstant.text & " kgf/cm")
            End With

            '고유진동수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=6).Range
                .InsertAfter(text:=frmNoise.txtNaturalF.text & " Hz")
            End With

            '강제진동수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=10, Column:=2).Range
                .InsertAfter(text:=frmNoise.txtForcedF.text & " Hz")
            End With

            '방진효율 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=10, Column:=4).Range
                .InsertAfter(text:=frmNoise.txtSAEff.text & " %")
            End With

            '날개수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=16, Column:=4).Range
                .InsertAfter(text:=frmNoise.txtBladeNo.text & " EA")
            End With

            '소음주파수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=16, Column:=6).Range
                .InsertAfter(text:=frmNoise.txtBPF.text & " Hz")
            End With

            '계산소음 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=17, Column:=2).Range
                .InsertAfter(text:=frmNoise.txtCalculatedSPL.text & " dB")
            End With

    End Sub


End Module
