' 원본: Calculation.bas (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Module Calculation

    Public Sub Initial_Vbelt_Type_Selection() '초기입력에 의한 벨트타입, 가닥수 및 풀리경 선정
        Dim smallPulley As Double
        Dim bigPulley As Double
        Dim PulleyRatio As Double
        Dim ratio As Double
        Dim K As Double
        Dim L As Double
        Dim spowerhp As Double
        Dim speed As Double
        Dim hpt As Double

    If frmInput.optVbelt.Value = True Then


        spowerhp = spower * 1.36
        nRatio = N / motorrpm

        '3HP이하는 A 형식
        If spowerhp <= 3 Then
            VbeltType = "A Type"

            'Pulley 직경 선정
            For K = 3 To 30 Step 0.5
                For L = 3 To 30 Step 0.5
                    ratio = L / K
                    If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
                Next L
            Next K
        End If

        '3HP보다 크고 15HP 이하는 B 형식
        If spowerhp > 3 And spowerhp <= 15 Then
            VbeltType = "B Type"

            'Pulley 직경 선정
            For K = 5 To 50 Step 0.5
                For L = 5 To 50 Step 0.5
                    ratio = L / K
                    If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
                Next L
            Next K

        End If

        '15HP보다 크고 100HP 이하는 C 형식
        If spowerhp > 15 And spowerhp <= 100 Then
            VbeltType = "C Type"

            'Pulley 직경 선정
            For K = 8 To 80 Step 0.5
                For L = 8 To 80 Step 0.5
                    ratio = L / K
                    If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
                Next L
            Next K

        End If

        '100HP보다 크고 150HP 이하는 D 형식
        If spowerhp > 100 And spowerhp <= 150 Then
            VbeltType = "D Type"

            'Pulley 직경 선정
            For K = 14 To 140 Step 0.5
                For L = 14 To 140 Step 0.5
                    ratio = L / K
                    If Abs(nRatio - ratio) / nRatio < 0.05 Then GoTo JUMP1
                Next L
            Next K

        End If

    JUMP1: 

        If nRatio > 1 Then
            If K > L Then
                motorPulley = VbCopy(K)
                fanPulley = VbCopy(L)
                smallPulley = VbCopy(L)
            Else
                motorPulley = VbCopy(L)
                fanPulley = VbCopy(K)
                smallPulley = VbCopy(K)
            End If
        Else
            If K > L Then
                motorPulley = VbCopy(L)
                fanPulley = VbCopy(K)
                smallPulley = VbCopy(L)
            Else
                motorPulley = VbCopy(K)
                fanPulley = VbCopy(L)
                smallPulley = VbCopy(K)
            End If
        End If

        '초기계산 풀리치수
        sFanPulley = VbCopy(fanPulley)
        sMotorPulley = VbCopy(motorPulley)


            speed = (Atn(1) * 4) * smallPulley * motorrpm / 12000

        'V-Belt 1가닥당 전동마력 계산


        If VbeltType = "A Type" Then
            hpt = (1.589 - 2.702 / smallPulley - 0.0146 * speed ^ 2) * speed
        End If

        If VbeltType = "B Type" Then
            hpt = (2.822 - 7.725 / smallPulley - 0.0251 * speed ^ 2) * speed
        End If

        If VbeltType = "C Type" Then
            hpt = (5.822 - 26.971 / smallPulley - 0.0379 * speed ^ 2) * speed
        End If

        If VbeltType = "D Type" Then
            hpt = (12.628 - 96.991 / smallPulley - 0.0815 * speed ^ 2) * speed
        End If

        If VbeltType = "E Type" Then
            hpt = (19.238 - 223.04 / smallPulley - 0.1233 * speed ^ 2) * speed
        End If

        If hpt < 1 Then hpt = 1

        PCS = Int(spowerhp / hpt) + 1

    End If


    End Sub

    Public Sub Calculation_for_Output_Form() '최종출력을 위한 각종 Factor값 계산
        Dim vm1 As Double, vm2 As Double
        Dim qdesh As Single
        Dim bStress1 As Double
        Dim bStress2 As Double

        '각종 Factor의 재계산 및 인식

        q = Val(frmInput.txtQ.text)

        gamma = Val(frmInput.txtDensity.text)

        ps = Val(frmInput.txtPs.text)

        pt = ps + (2.18 * ns ^ -0.32 * Sqr(19.6 * ps / gamma)) ^ 2 * gamma / 19.6

        '각종 속도성분 계산

        u2 = (Atn(1) * 4) * D2 * N / 60
        u1 = (Atn(1) * 4) * D1 * N / 60
        vi = q / (60 * (Atn(1) * 4) * D1 ^ 2 / 4)

        vm1 = VbCopy(vi)

        vm2 = vi / 1.1


        beta1 = Atn(vm1 / u1)

        '누설풍량 계산
        qdesh = q + 60 * gamma * 0.85 * (Atn(1) * 4) * D1 * 0.01 * D2 * Sqr(9.8 * pt ^ 2 / (29.27 * (273.15 + temp)))

        '날개폭 계산
        b1 = qdesh / (60 * vm1 * ((Atn(1) * 4) * D1 - Z * bt / (1000 * Sin(beta1))))
        b2 = qdesh / (60 * vm2 * ((Atn(1) * 4) * D2 - Z * bt / (1000 * Sin(Dtr(45)))))

        myy = (D2 ^ 2 - D1 ^ 2) / (4 * (D2 * Cos(Dtr(45)) - D1 * Cos(beta1)))
        myr = Sqr(D2 ^ 2 / 4 + myy ^ 2 - D2 * myy * Cos(Dtr(45)))

        '축경계산 및 베어링선정

        DS = Int(180 * (spower * 1.36 / N) ^ 0.25)

        If DS < 10 Then
                DS = 10
                bearingno = 0

            ElseIf DS >= 10 And DS < 12 Then
                DS = 12
                bearingno = 1

            ElseIf DS >= 12 And DS < 15 Then
                DS = 15
                bearingno = 2

            ElseIf DS >= 15 And DS < 17 Then
                DS = 17
                bearingno = 3

            ElseIf DS >= 110 Then
                DS = Int(DS - DS Mod 10) + 10
                bearingno = DS / 5

            Else
                DS = Int(DS - DS Mod 5) + 5
                bearingno = DS / 5

        End If

        '예상 소음도 계산 루틴
        SPL = 10 * Log(q) / Log(10) + 10 * Log(pt ^ 2) / Log(10) + 26

        '회전차 강도설계

         '주판의 응력

            mStress = sWeight / (4 * 9.8) * (N * 2 * (Atn(1) * 4) / 60) ^ 2 * (3.3 * (D2 / 2) ^ 2 + 0.7 * (D1 / 2) ^ 2) / 10000#
            bStress1 = 3 * b1 ^ 2 * sWeight * (D1 / 2) * (N * 2 * (Atn(1) * 4) / 60) ^ 2 * Cos(Dtr(45)) / (10000# * 4 * (bt / 1000) * 9.8)
            bStress2 = 3 * b2 ^ 2 * sWeight * (D2 / 2) * (N * 2 * (Atn(1) * 4) / 60) ^ 2 * Cos(Dtr(45)) / (10000# * 4 * (bt / 1000) * 9.8)
            If bStress1 > bStress2 Then
                bladeStress = VbCopy(bStress1)
                Else
                bladeStress = VbCopy(bStress2)
            End If
            mSf = maxStress / mStress
            bSf = maxStress / bladeStress



        Call Initial_Vbelt_Type_Selection '초기 V-Belt 관련 계산루틴 호출

        Call InOutSize '흡토출구 사이즈 결정

    End Sub

    Public Sub Stress_Sweight() '회전차 관련 응력 설계 루틴

        material = frmInput.cboBladeMaterial.text

        If material = "SS400" Then
            maxStress = 4100
            sWeight = 7850
        End If

        If material = "STS304" Then
            maxStress = 5300
            sWeight = 7900
        End If

        If material = "STS316" Then
            maxStress = 5300
            sWeight = 7900
        End If

        If material = "STS316L" Then
            maxStress = 4900
            sWeight = 7900
        End If

        If material = "Ti -Alloy" Then
            maxStress = 3600
            sWeight = 4505
        End If

        If material = "Aluminum" Then
            maxStress = 900
            sWeight = 2700
        End If

        If material = "F.R.P" Then
            maxStress = 810
            sWeight = 1500
        End If

        If material = "P.V.C" Then
            maxStress = 550
            sWeight = 1400
        End If

    End Sub

    Public Sub Bearing_Lifetime() '베어링 수명시간 예측 루틴
        Dim bLoad As Double
        Dim bCapacity As Double
        Dim FN As Double
        Dim Fh As Double

        If frmInput.optVbelt.Value = True Then


        bLoad = 71620 * spower * 1.36 / (N * 2.54 * fanPulley / 2) * 3


        If bearingno = 0 Then bCapacity = 640
        If bearingno = 1 Then bCapacity = 760
        If bearingno = 2 Then bCapacity = 900
        If bearingno = 3 Then bCapacity = 1060
        If bearingno = 4 Then bCapacity = 1250
        If bearingno = 5 Then bCapacity = 1660
        If bearingno = 6 Then bCapacity = 2180
        If bearingno = 7 Then bCapacity = 2610
        If bearingno = 8 Then bCapacity = 3200
        If bearingno = 9 Then bCapacity = 4150
        If bearingno = 10 Then bCapacity = 4850
        If bearingno = 11 Then bCapacity = 5650
        If bearingno = 12 Then bCapacity = 6450
        If bearingno = 13 Then bCapacity = 7300
        If bearingno = 14 Then bCapacity = 8150
        If bearingno = 15 Then bCapacity = 8900
        If bearingno = 16 Then bCapacity = 9650
        If bearingno = 17 Then bCapacity = 10400
        If bearingno = 18 Then bCapacity = 11200
        If bearingno = 19 Then bCapacity = 12000
        If bearingno = 20 Then bCapacity = 13600
        If bearingno = 21 Then bCapacity = 14400
        If bearingno = 22 Then bCapacity = 16100
        If bearingno = 24 Then bCapacity = 16200
        If bearingno = 26 Then bCapacity = 18000
        If bearingno = 28 Then bCapacity = 19800


            FN = (33.3 / N) ^ (1 / 3)
            Fh = FN * bCapacity / bLoad
            Lh = 500 * Fh ^ 3
            LhYear = Int(Lh / 8760)
            LhMonth = Int((Lh Mod 8760) / 720)

        '출력폼에 수명시간 출력
        frmOutput.txtBearingLifeTimeHr.text = Format(Lh, "######") & " hr"
        frmOutput.txtBearingLifeTimeYear.text = LhYear & " 년 " & LhMonth & " 개월"

        End If

    End Sub

    Public Sub Text_Selected() 'Text Box에서 Text 선택하기
        Dim i As Integer
        Dim oTextBox As MTextBox


        If TypeOf frmInput.ActiveControl Is MTextBox Then

            oTextBox = frmInput.ActiveControl
            i = Len(oTextBox.text)
            oTextBox.SelStart = 0
            oTextBox.SelLength = VbCopy(i)

        End If

    End Sub

    Public Sub D2no_Cal() '회전차 규격 변화에 의한 예비설계루틴
        Dim tD2 As Double
        Dim sNs As Double
        Dim bNs As Double
        Dim mNs As Double


            tD2 = tD2NO * 0.1524

            sNs = 135
            bNs = 858
            mNs = (sNs + bNs) / 2

        Do '조건에 의한 루프실행

            Call Ns_Cal(mNs)

            If D2 > tD2 Then

                sNs = VbCopy(mNs)

                ElseIf D2no < tD2NO Then

                    bNs = VbCopy(mNs)

                Else

            End If

            mNs = (sNs + bNs) / 2

        Loop While (bNs - sNs) > 0.01

        ns = VbCopy(mNs)


    End Sub
    Public Sub Ns_Cal(ByVal nNs As Double) '예비설계 계산루틴
        Dim i As Integer
        Dim nsArray(14) As Double
        Dim kuArray(14) As Double
        Dim sigmaArray(14) As Double
        Dim deltaArray(14) As Double
        Dim FilePath As String
        Dim slopeku As Object, cvalueku As Object, slopesigma As Object, cvaluesigma As Object, slopedelta As Object, cvaluedelta As Object
        Dim phai As Double


        q = Val(frmInput.txtQ.text)

        gamma = Val(frmInput.txtDensity.text)

        ps = Val(frmInput.txtPs.text)

        pt = ps + (2.18 * nNs ^ -0.32 * Sqr(19.6 * ps / gamma)) ^ 2 * gamma / 19.6

        N = (nNs * (pt / gamma) ^ 0.75 / Sqr(q))

        'Ns에 관계되는 Data읽어오기

            FilePath = SupportRoot() + "\ALISP\Turbo Fan Design\Data\fandata.dat"

        FileOpen(1, FilePath, OpenMode.Input)

            For i = 1 To 14
                Input(1, nsArray(i)) : Input(1, kuArray(i)) : Input(1, sigmaArray(i)) : Input(1, deltaArray(i))
            Next i

        FileClose(1)

            For i = 1 To 14
                If nNs < nsArray(i) Then Exit For
            Next i

            slopeku = (kuArray(i) - kuArray(i - 1)) / (nsArray(i) - nsArray(i - 1))
            cvalueku = kuArray(i) - slopeku * nsArray(i)
            slopesigma = (sigmaArray(i) - sigmaArray(i - 1)) / (nsArray(i) - nsArray(i - 1))
            cvaluesigma = sigmaArray(i) - slopesigma * nsArray(i)
            slopedelta = (deltaArray(i) - deltaArray(i - 1)) / (nsArray(i) - nsArray(i - 1))
            cvaluedelta = deltaArray(i) - slopedelta * nsArray(i)

            ku = slopeku * nNs + cvalueku
            sigma = slopesigma * nNs + cvaluesigma
            delta = slopedelta * nNs + cvaluedelta

            D2 = 60 * ku * Sqr(2 * 9.8 * pt / gamma) / ((Atn(1) * 4) * N)

            D2no = D2 / 0.1524


            phai = 1 / (sigma * delta ^ 3)
            diaratio = 1.194 * phai ^ (1 / 3)
            D1 = diaratio * D2

    End Sub

    Public Function Dtr(ByVal a As Double) As Object '라디안을 각도값으로 바꿈

        Dtr = a * (Atn(1) * 4) / 180#

    End Function

    Public Sub InOutSize() '송풍기 흡,토출구 Size 계산
        Dim Aout As Double
        Dim kFactor As Double
        Dim LengthDis As Double

        ' 토출구 규격 계산


        Select Case ns
            Case Is < 150
                kFactor = 0.32
            Case 150 To 160
                kFactor = 0.34
            Case 160 To 170
                kFactor = 0.365
            Case 170 To 180
                kFactor = 0.4
            Case 180 To 190
                kFactor = 0.42
            Case 190 To 200
                kFactor = 0.46
            Case 200 To 220
                kFactor = 0.515
            Case 220 To 240
                kFactor = 0.58
            Case 240 To 260
                kFactor = 0.64
            Case 260 To 280
                kFactor = 0.7
            Case 280 To 300
                kFactor = 0.74
            Case 300 To 320
                kFactor = 0.77
            Case 320 To 340
                kFactor = 0.81
            Case 340 To 360
                kFactor = 0.84
            Case 360 To 380
                kFactor = 0.87
            Case 380 To 450
                kFactor = 0.9
            Case 450 To 500
                kFactor = 0.92
            Case 500 To 550
                kFactor = 0.94
            Case 550 To 600
                kFactor = 0.95
            Case Is > 600
                kFactor = 0.98

        End Select

            Aout = kFactor * (Atn(1) * 4) * D1 ^ 2 / 4
            LengthDis = Sqr(Aout)

        Select Case LengthDis
            Case Is <= 3 * b1
                Lout = Int(LengthDis * 100) * 10 + 10
                Wout = VbCopy(Lout)
            Case 3 * b1 To 4 * b1
                Lout = Int(1.1 * LengthDis * 100) * 10 + 10
                Wout = Int(0.9 * Lout / 10) * 10 + 10
            Case Is > 4 * b1
                Lout = Int(1.15 * LengthDis * 100) * 10 + 10
                Wout = Int(0.95 * Lout / 10) * 10 + 10
        End Select

        '흡입구경 계산

        DiaInlet = Int(Sqr(4 * q / ((Atn(1) * 4) * 60 * 15)) * 100) * 10
        If DiaInlet < D1 * 1000 Then
            DiaInlet = D1 * 1000
            ElseIf DiaInlet > 1.3 * D1 * 1000 Then
                DiaInlet = Int(1.3 * D1 * 100) * 10 + 10
        End If

    End Sub

    Public Sub input_check_1() '입력값 검사 루틴

        errCheck = False

        ' 풍량 입력값 검사

        ' Null 입력검사
        If frmInput.txtQ.text = "" Then
            MsgBox("풍량에 대한 입력 값이 없습니다." & vbCrLf & "풍량 값을 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")
            frmInput.txtQ.SetFocus
            errCheck = True
            Exit Sub
        End If

        ' 숫자인지를 검사
        If Not (IsNumeric(frmInput.txtQ.text)) Then
            MsgBox("풍량에 대한 입력 값이 숫자가 아닙니다." & vbCrLf & "풍량 값을 옳바르게 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")
            frmInput.txtQ.SetFocus
            errCheck = True
            Exit Sub
        End If

        ' 압력 입력값 검사

        ' Null 입력검사
        If frmInput.txtPs.text = "" Then
            MsgBox("압력에 대한 입력 값이 없습니다." & vbCrLf & "압력 값을 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")
            frmInput.txtPs.SetFocus
            errCheck = True
            Exit Sub
        End If

        ' 숫자인지를 검사
        If Not (IsNumeric(frmInput.txtPs.text)) Then
            MsgBox("압력에 대한 입력 값이 숫자가 아닙니다." & vbCrLf & "압력 값을 옳바르게 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")
            frmInput.txtPs.SetFocus
            errCheck = True
            Exit Sub
        End If

    End Sub

    Public Sub input_check_2() '입력값 검사 루틴

        ' D2no_1의 입력값 검사

        errCheck = False

        If frmInput.txtD2no_1.text = "" Then
            errCheck = True
            MsgBox("입력 값이 없습니다." & vbCrLf & "다시 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")
            Exit Sub
        End If

        If frmInput.txtD2no_1.text <> "" And Val(frmInput.txtD2no_1.text) < 1 Then
            MsgBox("입력 값이 #1 보다 작습니다." & vbCrLf & "다시 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")

            errCheck = True

            frmInput.txtD2no_1.SetFocus
            Text_Selected

            frmInput.txtN_1.text = ""
            frmInput.txtD2_1.text = ""
            frmInput.txtNs_1.text = ""

            Exit Sub

        End If

        If frmInput.txtD2no_1.text <> "" And Val(frmInput.txtD2no_1.text) > 15 Then
            MsgBox("입력 값이 #15 보다 큽니다." & vbCrLf & "다시 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")

            errCheck = True

            frmInput.txtD2no_1.SetFocus
            Text_Selected
            frmInput.txtN_1.text = ""
            frmInput.txtD2_1.text = ""
            frmInput.txtNs_1.text = ""

            Exit Sub

        End If

    End Sub

    Public Sub input_check_3() '입력값 검사 루틴

        ' D2no_2의 입력값 검사

        errCheck = False

        If frmInput.txtD2no_2.text = "" Then
            errCheck = True
            MsgBox("입력 값이 없습니다." & vbCrLf & "다시 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")
            Exit Sub
        End If

        If frmInput.txtD2no_2.text <> "" And Val(frmInput.txtD2no_2.text) < 1 Then
            MsgBox("입력 값이 #1 보다 작습니다." & vbCrLf & "다시 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")

            errCheck = True

            frmInput.txtD2no_2.SetFocus
            Text_Selected

            frmInput.txtN_2.text = ""
            frmInput.txtD2_2.text = ""
            frmInput.txtNs_2.text = ""

            Exit Sub

        End If

        If frmInput.txtD2no_2.text <> "" And Val(frmInput.txtD2no_2.text) > 15 Then
            MsgBox("입력 값이 #15 보다 큽니다." & vbCrLf & "다시 입력하여 주십시오.", vbOKOnly + vbExclamation, "입력에러")

            errCheck = True

            frmInput.txtD2no_2.SetFocus
            Text_Selected
            frmInput.txtN_2.text = ""
            frmInput.txtD2_2.text = ""
            frmInput.txtNs_2.text = ""

            Exit Sub

        End If

    End Sub

    Public Sub Motor_Selection() 'Motor의 규격을 결정하는 루틴
        Dim mcapa(19) As Double
        Dim mframe(19) As String
        Dim mrpm(19) As Double
        Dim meff(19) As Double
        Dim mpf(19) As Double
        Dim mloadamp(19) As Double
        Dim mstartamp(19) As Double
        Dim mloadtor(19) As Double
        Dim mstarttor(19) As Double
        Dim mmaxtor(19) As Double
        Dim mgd2(19) As Double
        Dim mwt(19) As Double
        Dim i As Integer
        Dim FileName As String
        Dim MP As String
        Dim MV As Double
        Dim filePath1 As String

        ns = 450

        '우선 풍량과 풍압이 숫자인지를 판별하여 양자가 모두 숫자값이 존재할 경우 Routine을 실행
        If IsNumeric(frmInput.txtQ.text) And IsNumeric(frmInput.txtPs.text) Then

            q = Val(frmInput.txtQ.text)
            gamma = Val(frmInput.txtDensity.text)
            ps = Val(frmInput.txtPs.text)
            pt = ps + (2.18 * ns ^ -0.32 * Sqr(19.6 * ps / gamma)) ^ 2 * gamma / 19.6

            If FanEff = 0 Then FanEff = 0.7

            spower = pt * q * 1.2 / (6120 * FanEff) '축동력 계산

            '설계범위초과 자동종료
            If spower > 200 Then
                MsgBox("예상 소요 동력이 200kw(272HP)가 넘습니다. 본 설계 프로그램의 " & vbCrLf & "설계 범위를 초과하여 프로그램을 자동 종료합니다.", vbOKOnly + vbCritical, "설계 범위 초과")
                End
            End If

            'Motor에 관계되는 Data읽어오기

            'Data file name 결정하기

            MP = frmInput.cboMotorPoles.text
            MV = CDbl(frmInput.cboMotorVoltage.text)

                filePath1 = SupportRoot() + "\ALISP\Turbo Fan Design\Data\hs200" + MP + "p.dat"

            FileOpen(1, filePath1, OpenMode.Input)
                    For i = 1 To 19

                        Input(1, mcapa(i)) : Input(1, mframe(i)) : Input(1, mrpm(i)) : Input(1, meff(i)) : Input(1, mpf(i)) : Input(1, mloadamp(i)) : Input(1, mstartamp(i)) : Input(1, mloadtor(i)) : Input(1, mstarttor(i)) : Input(1, mmaxtor(i)) : Input(1, mgd2(i)) : Input(1, mwt(i))

                        If spower < mcapa(i) Then
                            motorcapa = mcapa(i)
                            motorframe = mframe(i)
                            motorrpm = mrpm(i)
                            motoreff = meff(i)
                            motorpf = mpf(i)
                            motorloadamp = mloadamp(i) * 220 / MV
                            motorstartamp = mstartamp(i) * 220 / MV
                            motorloadtor = mloadtor(i)
                            motorstarttor = mstarttor(i)
                            motormaxtor = mmaxtor(i)
                            motorgd2 = mgd2(i)
                            motorwt = mwt(i)
                            Exit For
                        End If

                    Next i
            FileClose(1)

            frmInput.cboMotorOutput.text = CStr(motorcapa)

        End If

    End Sub

    Public Sub motor_direct_calculation() 'Motor 직결시 각종 Factor계산 루틴

        If IsNumeric(frmInput.txtQ.text) And IsNumeric(frmInput.txtPs.text) Then

            q = frmInput.txtQ.text

            gamma = Val(frmInput.txtDensity.text)

            ps = Val(frmInput.txtPs.text)

            pt = ps + (2.18 * ns ^ -0.32 * Sqr(19.6 * ps / gamma)) ^ 2 * gamma / 19.6

            ns = motorrpm * Sqr(q) / (pt / gamma) ^ 0.75


            '비교회전도 허용범위 안에서만 계산
            If ns >= 135 And ns <= 858 Then
                Ns_Cal((ns))
                frmInput.txtNs_1.text = Format(ns, "0.0")
                frmInput.txtN_1.text = VbCopy(motorrpm)
                frmInput.txtD2_1.text = Format(D2, "0.000")
                frmInput.txtD2no_1.text = Format(D2no, "0.0")

                Else
                '에러처리
                MsgBox("설계비교회전도 범위(135~858)를 초과합니다." & vbCrLf & "모터의 극수를 적당히 조정하십시오.", vbOKOnly + vbCritical, "비교회전도 범위초과")
                frmInput.cboMotorPoles.SetFocus
                frmInput.txtD2_1.text = ""
                frmInput.txtD2no_1.text = ""
                frmInput.txtN_1.text = ""
                frmInput.txtNs_1.text = ""

            End If

        End If

    End Sub

    Public Sub Fan_Efficiency_Calculation()
        Dim slope As Double
        Dim C As Double


        If ns <= 200 Then
            slope = 0.0649
            C = 52.02
        End If
        If ns > 200 And ns <= 300 Then
            slope = 0.057
            C = 53.6
        End If
        If ns > 300 And ns <= 400 Then
            slope = 0.0493
            C = 55.91
        End If
        If ns > 400 And ns <= 500 Then
            slope = 0.0336
            C = 62.19
        End If
        If ns > 500 And ns <= 600 Then
            slope = 0.0101
            C = 73.94
        End If
        If ns > 600 And ns <= 700 Then
            slope = -0.0172
            C = 90.32
        End If
        If ns > 700 And ns <= 800 Then
            slope = -0.0328
            C = 101.24
        End If
        If ns > 800 And ns <= 900 Then
            slope = -0.0391
            C = 106.28
        End If

        FanEff = (ns * slope + C) * ((D2 ^ 2 * N) / 1100) ^ 0.1 / 100


    End Sub

    Public Sub Redesign_Ns_Calculation() ' 1차계산후 다시 풍량,풍압,온도를 수정한 경우

        If frmInput.txtQ.text <> "" And frmInput.txtPs.text <> "" Then
            If frmInput.txtD2no_1.text <> "" Then

                '예비 Ns 설계
                ns = Val(frmInput.txtNs_1.text)
                Ns_Cal((ns))
                frmInput.txtN_1.text = Format(N, "####")
                frmInput.txtD2_1.text = Format(D2, "0.000")
                frmInput.txtD2no_1.text = Format(D2no, "0.00")
            End If

            If frmInput.txtNs_2.text <> "" Then
                '예비 Ns 설계
                ns = Val(frmInput.txtNs_2.text)
                Ns_Cal((ns))
                frmInput.txtN_2.text = Format(N, "####")
                frmInput.txtD2_2.text = Format(D2, "0.000")
                frmInput.txtD2no_2.text = Format(D2no, "0.00")
            End If
        End If

    End Sub

    Public Sub Load_LT()
        Dim MyLT As Object
        Dim MyExist As Boolean


        'Center Type로딩

        MyExist = False

        For Each MyLT In ThisDrawing.Linetypes
            If MyLT.Name = "CENTER" Then
                MyExist = True
            End If
        Next

        If MyExist = False Then
            ThisDrawing.Linetypes.Load("CENTER", "acadiso.lin")
        End If

        'Hidden Type로딩

        MyExist = False

        For Each MyLT In ThisDrawing.Linetypes
            If MyLT.Name = "HIDDEN" Then
                MyExist = True
            End If
        Next

        If MyExist = False Then
            ThisDrawing.Linetypes.Load("HIDDEN", "acadiso.lin")
        End If

        'Phantom Type로딩

        MyExist = False

        For Each MyLT In ThisDrawing.Linetypes
            If MyLT.Name = "PHANTOM" Then
                MyExist = True
            End If
        Next

        If MyExist = False Then
            ThisDrawing.Linetypes.Load("PHANTOM", "acadiso.lin")
        End If

    End Sub



End Module
