' 원본: mReport.bas (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Module mReport


    Public Sub Maker_Report() 'Word에서 Report 자동 작성 루틴
        Dim wdApp As Object

        'Word로의 접속
        wdApp = CreateObject("Word.Application")
        wdApp.Visible = True
        wdApp.Documents.Add(SupportRoot() & "\ALISP\Turbo Fan Design\Word\makerReport.dot")
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
                .InsertAfter(text:=q & " ㎥/min")
            End With

            '풍압 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=5, Column:=2).Range
                .InsertAfter(text:=ps & " mmAq")
            End With

            '온도 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=5, Column:=3).Range
                .InsertAfter(text:=temp & " ℃")
            End With

            '밀도 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=5, Column:=4).Range
                .InsertAfter(text:=Format(gamma, "0.000") & " kg/㎥")
            End With

            '소요동력 kW 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=1).Range
                .InsertAfter(text:=Format(spower, "#.00"))
            End With

            '소요동력 HP 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=2).Range
                .InsertAfter(text:=Format(spower * 1.36, "#.00"))
            End With

            If frmInput.optVbelt.Value Then ' V-Belt 구동시만 표시

                '축경 삽입
                With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=3).Range
                    .InsertAfter(text:="φ" & Format(DS))
                End With

                '축재질 삽입
                With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=4).Range
                    .InsertAfter(text:=(frmOutput.cboShaftMatl.text))
                End With

                '회전차측 베어링 삽입
                With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=5).Range
                    .InsertAfter(text:=(frmOutput.txtBearingImp.text))
                End With

                '풀리측 베어링 삽입
                With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=6).Range
                    .InsertAfter(text:=(frmOutput.txtBearingPulley.text))
                End With

            End If


            '전동방식 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=8, Column:=7).Range
                .InsertAfter(text:=(frmOutput.txtPowerTransMethod.text))
            End With


            If frmInput.optVbelt.Value Then ' V-Belt 구동시만 표시

                'V-Belt형식 삽입
                With wdApp.ActiveDocument.Tables(1).Cell(Row:=7, Column:=7).Range
                    .InsertAfter(text:=(frmOutput.cboVbeltType.text))
                End With

                'V-Belt 가닥수 삽입
                With wdApp.ActiveDocument.Tables(1).Cell(Row:=8, Column:=10).Range
                    .InsertAfter(text:=(frmOutput.txtVbeltPcs.text))
                End With

                '송풍기 풀리 규격 삽입
                With wdApp.ActiveDocument.Tables(1).Cell(Row:=9, Column:=10).Range
                    .InsertAfter(text:=(frmOutput.txtPulleySizeFan.text))
                End With

                '모터측 풀리 규격 삽입
                With wdApp.ActiveDocument.Tables(1).Cell(Row:=10, Column:=10).Range
                    .InsertAfter(text:=(frmOutput.txtPulleySizeMotor.text))
                End With

            End If

            '송풍기 회전수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=13, Column:=1).Range
                .InsertAfter(text:=(frmOutput.txtN.text))
            End With

            '날개수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=13, Column:=2).Range
                .InsertAfter(text:=(frmOutput.txtBladeNo.text))
            End With

            '회전차 외경 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=13, Column:=3).Range
                .InsertAfter(text:=frmOutput.txtD2.text & "(# " & Format((D2 / 0.1524), "0.0") & " )")

            End With

            '회전차 내경 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=13, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtD1.text))
            End With

            '회전차 내폭 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=15, Column:=1).Range
                .InsertAfter(text:=(frmOutput.txtB1.text))
            End With

            '회전차 외폭 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=15, Column:=2).Range
                .InsertAfter(text:=(frmOutput.txtB2.text))
            End With

            '작도반경 Y 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=15, Column:=3).Range
                .InsertAfter(text:=(frmOutput.txtY.text))
            End With

            '작도반경 R 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=15, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtR.text))
            End With

            '회전차 재질 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=17, Column:=1).Range
                .InsertAfter(text:=(frmOutput.txtImpMatl.text))
            End With

            '날개 두께 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=17, Column:=2).Range
                .InsertAfter(text:=(frmOutput.txtBladeThickness.text))
            End With

            '입구각 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=17, Column:=3).Range
                .InsertAfter(text:=(frmOutput.txtBeta1.text))
            End With

            '출구각 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=17, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtBeta2.text))
            End With

            '주판 인장강도 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=18, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtMplateAllowStress.text))
            End With

            '주판의 응력 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=19, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtMplateStress.text))
            End With

            '주판의 안전율 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=20, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtMplateSf.text))
            End With

            '날개의 인장강도 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=21, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtBladeAllowStress.text))
            End With

            '날개의 응력 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=22, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtBladeStress.text))
            End With

            '날개의 안전율 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=23, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtBladeSf.text))
            End With

            '모터 메이커 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=26, Column:=1).Range
                .InsertAfter(text:=(frmOutput.txtMMaker.text))
            End With

            '모터 전압 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=26, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtMVoltage.text))
            End With

            '모터 상/극수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=26, Column:=5).Range
                .InsertAfter(text:=(frmOutput.txtMphPoles.text))
            End With

            '모터 출력 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=28, Column:=1).Range
                .InsertAfter(text:=(frmOutput.txtMOutput.text))
            End With

            '모터 후레임 번호 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=28, Column:=2).Range
                .InsertAfter(text:=(frmOutput.txtMFrame.text))
            End With

            '모터 회전수 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=28, Column:=3).Range
                .InsertAfter(text:=(frmOutput.txtMrpm.text))
            End With

            '모터 효율 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=28, Column:=4).Range
                .InsertAfter(text:=(frmOutput.txtMeff.text))
            End With

            '모터 역율 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=28, Column:=5).Range
                .InsertAfter(text:=(frmOutput.txtMpf.text))
            End With

            '모터 부하 전류 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=28, Column:=6).Range
                .InsertAfter(text:=(frmOutput.txtMLoadAmp.text))
            End With

            '모터 기동 전류 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=30, Column:=1).Range
                .InsertAfter(text:=(frmOutput.txtMStartAmp.text))
            End With

            '모터 부하 토오크 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=30, Column:=2).Range
                .InsertAfter(text:=motorloadtor & " kg-m")
            End With

            '모터 기동 토오크 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=30, Column:=3).Range
                .InsertAfter(text:=motorstarttor & " kg-m")
            End With

            '모터 최대 토오크 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=30, Column:=4).Range
                .InsertAfter(text:=motormaxtor & " kg-m")
            End With

            '모터 GD2 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=30, Column:=5).Range
                .InsertAfter(text:=(frmOutput.txtMGD2.text))
            End With

            '모터 중량 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=30, Column:=6).Range
                .InsertAfter(text:=(frmOutput.txtMWeight.text))
            End With

            '베어링 수명시간 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=31, Column:=3).Range
                .InsertAfter(text:=frmOutput.txtBearingLifeTimeHr.text & " (" & frmOutput.txtBearingLifeTimeYear.text & ")")
            End With

            '회전차 간극 삽입
            With wdApp.ActiveDocument.Tables(1).Cell(Row:=32, Column:=3).Range
                .InsertAfter(text:=(frmOutput.txtImpGap.text))
            End With

    End Sub



End Module
