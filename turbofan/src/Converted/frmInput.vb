' 원본: frmInput.frm (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Partial Class frmInput

    Public Sub New()
        InitializeComponent()
        EndInitialize()
    End Sub

    Const beta2 = 0.785398165

    Private Sub cboBladeMaterial_Click() Handles cboBladeMaterial.VbClick

        Call Stress_Sweight

    End Sub

    Private Sub cboBladeMaterial_Enter() Handles cboBladeMaterial.VbEnter

        lblMessage.Caption = "회전차 재질을 입력하시오."
        Call Stress_Sweight

    End Sub

    Private Sub cboBladeMaterial_Exit() Handles cboBladeMaterial.VbExit
            Dim Cancel As Boolean = False

        cmdDesign.SetFocus

    End Sub

    Private Sub cboMotorOutput_Click() Handles cboMotorOutput.VbClick

        If optDirect.Value = True Then
            motor_direct_calculation
        End If
        mtPower = Val(cboMotorOutput.text)
        Bool_Motor_Sel = True

    End Sub

    Private Sub cboMotorOutput_Enter() Handles cboMotorOutput.VbEnter
        lblMessage.Caption = ""
        input_check_1

        If Not (errCheck) Then
            '동력소요량 계산
            spower = pt * q * 1.2 / (6120 * FanEff)
            lblMessage.Caption = "모터의 출력을 입력하시오." & vbCrLf & "예상 동력 소요량은 " & Format(spower, "0.0") & " kW 입니다."

        End If

    End Sub


    Private Sub cboMotorOutput_KeyDown(sender As Object, vbE As KeyDownVbEventArgs) Handles cboMotorOutput.VbKeyDown
            Dim KeyCode As Integer = vbE.KeyCode
            Dim Shift As Integer = vbE.Shift

        If KeyCode = 13 Then
            If optDirect.Value = True Then
                motor_direct_calculation
            End If
        End If

    End Sub

    Private Sub cboMotorPoles_Click() Handles cboMotorPoles.VbClick

            If optDirect.Value = True Then
                Motor_Selection
                Fan_Efficiency_Calculation
                Motor_Selection
                motor_direct_calculation
            End If

    End Sub

    Private Sub cboMotorPoles_Enter() Handles cboMotorPoles.VbEnter

        lblMessage.Caption = "모터의 극수를 입력하시오."

    End Sub

    Private Sub cboMotorPoles_KeyDown(sender As Object, vbE As KeyDownVbEventArgs) Handles cboMotorPoles.VbKeyDown
            Dim KeyCode As Integer = vbE.KeyCode
            Dim Shift As Integer = vbE.Shift

        If KeyCode = 13 Then
            If Bool_Motor_Sel = False Then
                Motor_Selection
            End If

            If optDirect.Value = True Then
                motor_direct_calculation
            End If

        End If

    End Sub

    Private Sub cboMotorVoltage_Click() Handles cboMotorVoltage.VbClick
        If Bool_Motor_Sel = False Then
            Motor_Selection
        End If

    End Sub

    Private Sub cboMotorVoltage_Enter() Handles cboMotorVoltage.VbEnter
        lblMessage.Caption = "사용 전원의 전압을 입력하시오."
    End Sub

    Private Sub cboMotorVoltage_KeyDown(sender As Object, vbE As KeyDownVbEventArgs) Handles cboMotorVoltage.VbKeyDown
            Dim KeyCode As Integer = vbE.KeyCode
            Dim Shift As Integer = vbE.Shift

        If KeyCode = 13 Then
            If Bool_Motor_Sel = False Then
                Motor_Selection
            End If
        End If

    End Sub

    Private Sub cmdDesign_Click() Handles cmdDesign.VbClick '최종 설계 수행

         input_check_1 '풍량, 풍압이 입력되었는가 검사한다.

        If errCheck = True Then
            Exit Sub
            errCheck = False
        End If

        If txtD2no_1.text = "" And txtD2no_2.text = "" Then
            MsgBox("예비설계를 수행하지 않았습니다." & vbCrLf & "예비설계를 수행하신뒤 설계결과를 볼 수 있습니다.", vbOKOnly + vbExclamation, "입력에러")
            txtD2no_1.SetFocus
            Exit Sub
        End If

        If txtBladeNo.text = "" Then
            MsgBox("날개수를 입력하지 않았습니다." & vbCrLf & "날개수를 입력하신뒤 설계결과를 볼 수 있습니다.", vbOKOnly + vbExclamation, "입력에러")
            txtBladeNo.SetFocus
            Exit Sub
        End If

        If Not (IsNumeric(txtBladeNo.text)) Then
            MsgBox("입력하신 날개수가 숫자가 아닙니다." & vbCrLf & "날개수를 옳바르게 재입력하십시오.", vbOKOnly + vbExclamation, "입력에러")
            txtBladeNo.SetFocus
            Exit Sub
        End If

        If Val(txtBladeNo.text) < 2 Then
            MsgBox("입력하신 날개수가 너무 작은 숫자입니다." & vbCrLf & "날개수를 옳바르게 재입력하십시오.", vbOKOnly + vbExclamation, "입력에러")
            txtBladeNo.SetFocus
            Exit Sub
        End If

        If txtBladeThickness.text = "" Then
            MsgBox("날개두께를 입력하지 않았습니다." & vbCrLf & "날개두께를 입력하신뒤 설계결과를 볼 수 있습니다.", vbOKOnly + vbExclamation, "입력에러")
            txtBladeThickness.SetFocus
            Exit Sub
        End If

        If Not (IsNumeric(txtBladeThickness.text)) Then
            MsgBox("입력하신 날개두께가 숫자가 아닙니다." & vbCrLf & "날개두께를 옳바르게 재입력하십시오.", vbOKOnly + vbExclamation, "입력에러")
            txtBladeThickness.SetFocus
            Exit Sub
        End If

        If Val(txtBladeNo.text) < 0 Then
            MsgBox("입력하신 날개두께가 음수입니다." & vbCrLf & "날개두께를 옳바르게 재입력하십시오.", vbOKOnly + vbExclamation, "입력에러")
            txtBladeThickness.SetFocus
            Exit Sub
        End If

        material = cboBladeMaterial.text
        motoroutput = cboMotorOutput.text
        motorvoltage = cboMotorVoltage.Text
        motorpoles = cboMotorPoles.text
        temp = Val(txtTemp.text)

        If optVbelt.Value = True Then
            drvmethod = "V-Belt Drive"
            Else
            drvmethod = "Motor Direct"
        End If

        If Me.optVbelt.Value = True Then
            Initial_Vbelt_Type_Selection 'V-Belt에 대한 계산수행
        End If

        Z = Val(txtBladeNo.Text) ' (수정) 날개수 칸에서 Enter 를 안 눌러도 반영
        bt = Val(txtBladeThickness.text)

        Call Calculation_for_Output_Form '출력폼이 로드될 때 잔여 Factor 계산
        Call Output_On_Screen '출력폼의 출력칸을 채움

        Me.Hide
        frmOutput.Show(1)

    End Sub

    Private Sub cmdEnd_Click() Handles cmdEnd.VbClick
        Dim answer As Integer

            answer = MsgBox("정말로 끝내시겠습니까?", vbYesNo + vbQuestion, "종료확인")
        If answer = vbYes Then
            QuitApplication()
        End If

    End Sub

    Private Sub cmdNsOk_1_Click() Handles cmdNsOk_1.VbClick

        '예비계산결과 수용
        ns = Val(txtNs_1.text)
        N = Val(txtN_1.text)
        D2 = Val(txtD2_1.text)
        D2no = Val(txtD2no_1.text)

        ' 계산2 결과 지우기
        txtNs_2.text = ""
        txtN_2.text = ""
        txtD2_2.text = ""
        txtD2no_2.text = ""

        ' 예비계산버튼 비활성화
        cmdNsOk_1.Enabled = False
        cmdNsOk_2.Enabled = False

        'txtBladeNo로 촛점이동
        txtBladeNo.SetFocus
        Fan_Efficiency_Calculation

        Motor_Selection '여기가 문제

    End Sub

    Private Sub cmdNsOk_2_Click() Handles cmdNsOk_2.VbClick

        '계산결과 수용
        ns = Val(txtNs_2.text)
        N = Val(txtN_2.text)
        D2 = Val(txtD2_2.text)
        D2no = Val(txtD2no_2.text)

        '계산1 결과 지우기
        txtNs_1.text = ""
        txtN_1.text = ""
        txtD2_1.text = ""
        txtD2no_1.text = ""

        '예비계산버튼 비활성화
        cmdNsOk_1.Enabled = False
        cmdNsOk_2.Enabled = False

        'txtBladeNo로 촛점이동
        txtBladeNo.SetFocus

        Fan_Efficiency_Calculation
        Motor_Selection

    End Sub

    Private Sub cmdRedesign_Click() Handles cmdRedesign.VbClick

        Me.txtCustomer.text = ""
        Me.txtQ.text = ""
        Me.txtPs.text = ""

        Me.txtNs_1.text = ""
        Me.txtN_1.text = ""
        Me.txtD2_1.text = ""
        Me.txtD2no_1.text = ""
        Me.txtNs_2.text = ""
        Me.txtN_2.text = ""
        Me.txtD2_2.text = ""
        Me.txtD2no_2.text = ""

        Me.txtBladeNo.text = ""
        Me.txtBladeThickness.text = ""

        Me.cboBladeMaterial.text = "FRP"

        Me.optVbelt.Value = True

        Me.cboMotorOutput.text = ""
        Me.cboMotorVoltage.Text = "380"
        Me.cboMotorPoles.Text = "4"

        Me.txtCustomer.SetFocus

    End Sub

    Private Sub optCCW_Click() Handles optCCW.VbClick
        GetControlDirection

    End Sub

    Private Sub optCW_Click() Handles optCW.VbClick
        GetControlDirection

    End Sub

    Private Sub optDirect_Click() Handles optDirect.VbClick

        txtNs_1.text = ""
        txtNs_2.text = ""
        txtNs_1.BackColor = OleColor(&H80000004)
        txtNs_2.BackColor = OleColor(&H80000004)
        txtNs_1.text = ""
        txtN_1.text = ""
        txtD2_1.text = ""
        txtD2no_1.Enabled = False
        txtNs_2.text = ""
        txtN_2.text = ""
        txtD2_2.text = ""
        txtD2no_2.Enabled = False

        Motor_Selection
        Fan_Efficiency_Calculation
        Motor_Selection
        motor_direct_calculation

        GetControlDirection

    End Sub

    Private Sub optLEFT_Click() Handles optLeft.VbClick
        GetControlDirection

    End Sub

    Private Sub optMLeft_Click() Handles optMLeft.VbClick
        GetControlDirection

    End Sub

    Private Sub optMRight_Click() Handles optMRight.VbClick
        GetControlDirection

    End Sub

    Private Sub optRIGHT_Click() Handles optRight.VbClick
        GetControlDirection

    End Sub

    Private Sub optUP_Click() Handles optUp.VbClick
        GetControlDirection

    End Sub

    Private Sub optVbelt_Click() Handles optVbelt.VbClick

        If IsNumeric(txtQ.text) And IsNumeric(txtPs.text) Then
            txtD2no_1.Enabled = True
            txtD2no_2.Enabled = True
            txtD2no_1.SetFocus
        End If

        Call GetControlDirection

    End Sub

    Private Sub txtBladeNo_Enter() Handles txtBladeNo.VbEnter
        Dim zmin As Integer

    '풍량, 풍압에 대한 입력값 검사
        input_check_1

    If Me.optVbelt.Value = True Then

        '예비설계에 대한 검사
        If Not (errCheck) Then
            If diaratio = 0 Or IsNothing(diaratio) Then
                MsgBox("예비설계를 수행하지 않았습니다." & vbCrLf & "예비설계를 수행한 후에 날개수를 입력할 수 있습니다.", vbOKOnly + vbExclamation, "입력에러")
                txtD2no_1.SetFocus
                errCheck = True
            End If
        End If

        If Not (errCheck) Then
            Text_Selected
                zmin = Int(-8.16 * Sin(Dtr(45)) / Log(diaratio))
                lblMessage.Caption = "설계 날개수를 입력하시오." & vbCrLf & "필요한 최소의 날개수는 " & zmin & " 개 입니다. (필수사항)"
        End If

    Else
        Motor_Selection
        Fan_Efficiency_Calculation
        Motor_Selection
        motor_direct_calculation

        zmin = Int(-8.16 * Sin(Dtr(45)) / Log(diaratio)) ' 에러발생 추후에 고칠것 , 직결에서

        lblMessage.Caption = "설계 날개수를 입력하시오." & vbCrLf & "필요한 최소의 날개수는 " & zmin & " 개 입니다. (필수사항)"
    End If

    End Sub

    Private Sub txtBladeNo_KeyDown(sender As Object, vbE As KeyDownVbEventArgs) Handles txtBladeNo.VbKeyDown
            Dim KeyCode As Integer = vbE.KeyCode
            Dim Shift As Integer = vbE.Shift

        If KeyCode = 13 Then

            Z = Val(txtBladeNo.text) '날개수의 숫자화

        End If

    End Sub

    Private Sub txtBladeThickness_Enter() Handles txtBladeThickness.VbEnter

        '풍량, 풍압에 대한 입력값 검사
        input_check_1
        '예비설계에 대한 검사
        If Not (errCheck) Then
            If diaratio = 0 Or IsNothing(diaratio) Then
                MsgBox("예비설계를 수행하지 않았습니다." & vbCrLf & "예비설계를 수행한 후에 날개수를 입력할 수 있습니다.", vbOKOnly + vbExclamation, "입력에러")
                txtD2no_1.SetFocus
                errCheck = True
            End If
        End If

        Text_Selected
        lblMessage.Caption = "날개두께를 mm단위로 입력하시오." & vbCrLf & "(필수사항)"

    End Sub

    Private Sub txtCustomer_Enter() Handles txtCustomer.VbEnter
        Text_Selected
        lblMessage.Caption = "거래 고객의 상호를 입력하세요." & vbCrLf & "(선택사항)"
    End Sub

    Private Sub txtCustomer_LostFocus() Handles txtCustomer.VbExit
        Customer = txtCustomer.text
        lblMessage.Caption = ""
    End Sub

    Private Sub txtD2no_1_Enter() Handles txtD2no_1.VbEnter

        input_check_1 '풍량, 풍압에 대한 입력값 검사

        If optDirect.Value = False Then

            'Text_Selected '텍스트선택 루틴 가동

            ' 메시지 박스에 메시지 출력
            lblMessage.Caption = "회전차 번호를 입력하세요. (#1은 회전차 지름 φ152.4mm(φ6 inch)입니다." & vbCrLf & "회전수, 회전차 지름과 비교회전도는 자동으로 계산됩니다." & vbCrLf & "계산결과를 채택하시려면 (확인)을 누르시고 다른 계산은  (Tab Key)나 " & "(Enter Key)를 누르세요." & vbCrLf & "(필수사항)"
            Else
                txtNs_1.text = ""
                txtNs_2.text = ""
                txtNs_1.text = ""
                txtN_1.text = ""
                txtD2_1.text = ""
                txtD2no_1.Enabled = False
                txtNs_2.text = ""
                txtN_2.text = ""
                txtD2_2.text = ""
                txtD2no_2.Enabled = False

                Motor_Selection
                Fan_Efficiency_Calculation
                Motor_Selection
                motor_direct_calculation
                GetControlDirection

        End If

        txtD2no_1.SetFocus

    End Sub

    Private Sub txtD2no_2_Enter() Handles txtD2no_2.VbEnter

        '풍량, 풍압에 대한 입력값 검사
        input_check_1

        'Text_Selected

        ' 메시지 박스에 메시지 출력
        lblMessage.Caption = "회전차 번호를 입력하세요. (#1은 회전차 지름 φ152.4mm(φ6 inch)입니다." & vbCrLf & "회전수, 회전차 지름과 비교회전도는 자동으로 계산됩니다." & vbCrLf & "계산결과를 채택하시려면 (확인)을 누르시고 다른 계산은  (Tab Key)나 " & "(Enter Key)를 누르세요." & vbCrLf & "(필수사항)"

        txtD2no_2.SetFocus

    End Sub

    Private Sub txtD2no_1_KeyDown(sender As Object, vbE As KeyDownVbEventArgs) Handles txtD2no_1.VbKeyDown '엔터키 인식
            Dim KeyCode As Integer = vbE.KeyCode
            Dim Shift As Integer = vbE.Shift

        If KeyCode = 13 Then

            input_check_2

            If Not (errCheck) Then

                cmdNsOk_1.Enabled = True
                cmdNsOk_2.Enabled = False

                tD2NO = Val(Me.txtD2no_1.text)

                Call D2no_Cal

                txtD2no_1.text = Format(D2 / 0.1524, "0.0#")
                txtN_1.text = Format(N, "####")
                txtD2_1.text = Format(D2, "0.000#")
                txtNs_1.text = Format(ns, "0.0")

                With txtD2no_2
                    .SetFocus
                    .SelStart = 0
                    .SelLength = Len(.text)
                End With

            End If

        End If

    End Sub

    Private Sub txtD2no_2_KeyDown(sender As Object, vbE As KeyDownVbEventArgs) Handles txtD2no_2.VbKeyDown '엔터키 인식
            Dim KeyCode As Integer = vbE.KeyCode
            Dim Shift As Integer = vbE.Shift

        If KeyCode = 13 Then

            input_check_3

            If Not (errCheck) Then
                cmdNsOk_2.Enabled = True
                cmdNsOk_1.Enabled = False

                tD2NO = Val(Me.txtD2no_2.text)

                Call D2no_Cal

                txtD2no_2.text = Format(D2 / 0.1524, "0.0#")
                txtN_2.text = Format(N, "####")
                txtD2_2.text = Format(D2, "0.000#")
                txtNs_2.text = Format(ns, "0.0")

                With txtD2no_1
                    .SetFocus
                    .SelStart = 0
                    .SelLength = Len(.text)
                End With

            End If

        End If

    End Sub

    Private Sub txtPs_Enter() Handles txtPs.VbEnter

        Text_Selected
        lblMessage.Caption = "설계 송풍기 전압력을 mmAq (kg/㎡) 단위로 입력하세요." & vbCrLf & "(필수사항)"
        Motor_Selection

        txtD2no_1.text = ""
        txtD2_1.text = ""
        txtN_1.text = ""
        txtNs_1.text = ""
        txtD2no_2.text = ""
        txtD2_2.text = ""
        txtN_2.text = ""
        txtNs_2.text = ""

    End Sub

    Private Sub txtQ_Enter() Handles txtQ.VbEnter

        Text_Selected
        lblMessage.Caption = "설계 풍량을 입구기준으로 액추얼 값으로 입력하세요." & vbCrLf & "(필수사항)"
        Motor_Selection

        txtD2no_1.text = ""
        txtD2_1.text = ""
        txtN_1.text = ""
        txtNs_1.text = ""
        txtD2no_2.text = ""
        txtD2_2.text = ""
        txtN_2.text = ""
        txtNs_2.text = ""

    End Sub

    Private Sub txtTemp_Change() Handles txtTemp.VbChange

        txtDensity.text = 1.293 * 273.15 / (273.15 + Val(txtTemp.text))

    End Sub

    Private Sub txtTemp_Enter() Handles txtTemp.VbEnter

        Text_Selected

        lblMessage.Caption = "가스의 입구온도를 ℃단위로 입력하세요." & vbCrLf & "가스의 밀도는 자동으로 계산되어 입력 됩니다." & vbCrLf & "(필수사항)"

        Motor_Selection

        txtD2no_1.text = ""
        txtD2_1.text = ""
        txtN_1.text = ""
        txtNs_1.text = ""
        txtD2no_2.text = ""
        txtD2_2.text = ""
        txtN_2.text = ""
        txtNs_2.text = ""

    End Sub

    Private Sub GetControlDirection()
        Dim RD As String
        Dim d As String
        Dim M As String
        Dim FileName As String
        Dim Path As String

        If optVbelt.Value Then

            If optCW.Value Then
                RD = "R"
                Else
                RD = "L"
            End If

            If optUp.Value Then
                d = "H"

                ElseIf optLeft.Value Then
                d = "L"

                Else
                d = "R"
            End If

            If optMLeft.Value Then
                M = "-L"

                Else
                M = "-R"

            End If

            Direction = RD + d + M

            If Direction = "RL-L" Or Direction = "RL-R" Then
                optMLeft.Value = False
                optMLeft.Enabled = False
                optMRight.Value = True
                optMRight.Enabled = False
                M = "-R"

                ElseIf Direction = "LR-R" Or Direction = "LR-L" Then
                optMLeft.Value = True
                optMLeft.Enabled = False
                optMRight.Value = False
                optMRight.Enabled = False
                M = "-L"

                Else
                optMLeft.Enabled = True
                optMRight.Enabled = True
            End If

            Direction = RD + d + M

            FileName = Direction + ".bmp"
            Path = VbCopy(SupportRoot())
            imgFan.Picture = LoadPicture(SupportFolder() & "\Pics\" + FileName)

        End If ' V-Belt 구동일 때

        If optDirect.Value Then

            optMLeft.Enabled = False
            optMRight.Enabled = False

            If optCW.Value Then
                RD = "R"
                Else
                RD = "L"
            End If

            If optUp.Value Then
                d = "H"

                ElseIf optLeft.Value Then
                d = "L"

                Else
                d = "R"
            End If

            Direction = RD + d

            FileName = Direction + ".bmp"
            Path = SupportFolder() & ""
            imgFan.Picture = LoadPicture(SupportFolder() & "\Pics\" + FileName)

        End If

    End Sub

    Private Sub txtTemp_KeyDown(sender As Object, vbE As KeyDownVbEventArgs) Handles txtTemp.VbKeyDown
            Dim KeyCode As Integer = vbE.KeyCode
            Dim Shift As Integer = vbE.Shift

        If KeyCode = 13 Then

            txtD2no_1.SetFocus

        End If

    End Sub

    Protected Overrides Sub UserForm_Initialize()

        ' Main루틴시작
        ' 콤보박스에 List를 채움
        cboBladeMaterial.AddItem("SS400")
        cboBladeMaterial.AddItem("STS304")
        cboBladeMaterial.AddItem("STS316")
        cboBladeMaterial.AddItem("STS316L")
        cboBladeMaterial.AddItem("Ti-Alloy")
        cboBladeMaterial.AddItem("F.R.P")
        cboBladeMaterial.AddItem("P.V.C")

        cboMotorOutput.AddItem("0.4")
        cboMotorOutput.AddItem("0.75")
        cboMotorOutput.AddItem("1.1")
        cboMotorOutput.AddItem("1.5")
        cboMotorOutput.AddItem("2.2")
        cboMotorOutput.AddItem("3.7")
        cboMotorOutput.AddItem("5.5")
        cboMotorOutput.AddItem("7.5")
        cboMotorOutput.AddItem("11")
        cboMotorOutput.AddItem("15")
        cboMotorOutput.AddItem("18.5")
        cboMotorOutput.AddItem("22")
        cboMotorOutput.AddItem("30")
        cboMotorOutput.AddItem("37")
        cboMotorOutput.AddItem("45")
        cboMotorOutput.AddItem("55")
        cboMotorOutput.AddItem("75")
        cboMotorOutput.AddItem("90")
        cboMotorOutput.AddItem("110")
        cboMotorOutput.AddItem("132")
        cboMotorOutput.AddItem("160")
        cboMotorOutput.AddItem("200")

        cboMotorVoltage.AddItem("220")
        cboMotorVoltage.AddItem("380")
        cboMotorVoltage.AddItem("440")
        cboMotorVoltage.text = "380"

        cboMotorPoles.AddItem("2")
        cboMotorPoles.AddItem("4")
        cboMotorPoles.AddItem("6")
        cboMotorPoles.AddItem("8")
        cboMotorPoles.text = "4"

        '현재날짜 삽입
        lblDate.Caption = Format(DateTime.Today, "YYYY년 M월 D일")

        ' 예비계산 버튼 비활성화
        cmdNsOk_1.Enabled = False
        cmdNsOk_2.Enabled = False

        ' 디폴트 온도에 대한 밀도값 계산후 txtDensity.Txt 에 표시
        txtDensity.text = 1.293 * 273.15 / (273.15 + Val(txtTemp.text))

        ' 회전수, 회전차외경, 비교회전도 비활성화
        txtN_1.Enabled = False
        txtD2_1.Enabled = False
        txtN_2.Enabled = False
        txtD2_2.Enabled = False
        txtNs_1.Enabled = False
        txtNs_2.Enabled = False

        '날개재질에 대한 인장강도 및 비중량 읽어오기
        material = cboBladeMaterial.text
        Stress_Sweight

        Bool_Motor_Sel = False

        GetControlDirection

    End Sub



End Class
