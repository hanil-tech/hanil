' 이 파일은 tools/vba2vb.py 가 원본 .dvb 의 폼 배치에서 만든다. 직접 고치지 말 것.
Imports System.Drawing
Imports System.Windows.Forms

Partial Class frmOutput
    Inherits MForm

    Friend WithEvents Frame1 As MFrame
    Friend WithEvents Label1 As MLabel
    Friend WithEvents Label2 As MLabel
    Friend WithEvents TextBox1 As MTextBox
    Friend WithEvents txtDate As MTextBox
    Friend WithEvents TextBox65 As MTextBox
    Friend WithEvents txtCustomer As MTextBox
    Friend WithEvents Frame2 As MFrame
    Friend WithEvents Label3 As MLabel
    Friend WithEvents txtN As MTextBox
    Friend WithEvents txtD2 As MTextBox
    Friend WithEvents Label5 As MLabel
    Friend WithEvents txtBeta1 As MTextBox
    Friend WithEvents Label6 As MLabel
    Friend WithEvents txtD1 As MTextBox
    Friend WithEvents Label7 As MLabel
    Friend WithEvents txtY As MTextBox
    Friend WithEvents Label8 As MLabel
    Friend WithEvents txtBeta2 As MTextBox
    Friend WithEvents Label9 As MLabel
    Friend WithEvents Label10 As MLabel
    Friend WithEvents txtBladeNo As MTextBox
    Friend WithEvents Label11 As MLabel
    Friend WithEvents txtB2 As MTextBox
    Friend WithEvents Label12 As MLabel
    Friend WithEvents txtImpMatl As MTextBox
    Friend WithEvents Label13 As MLabel
    Friend WithEvents txtB1 As MTextBox
    Friend WithEvents Label14 As MLabel
    Friend WithEvents txtR As MTextBox
    Friend WithEvents Label15 As MLabel
    Friend WithEvents txtBladeThickness As MTextBox
    Friend WithEvents Frame3 As MFrame
    Friend WithEvents Label16 As MLabel
    Friend WithEvents txtQ As MTextBox
    Friend WithEvents txtPs As MTextBox
    Friend WithEvents Label17 As MLabel
    Friend WithEvents txtTemp As MTextBox
    Friend WithEvents Label23 As MLabel
    Friend WithEvents txtDensity As MTextBox
    Friend WithEvents Label24 As MLabel
    Friend WithEvents Frame4 As MFrame
    Friend WithEvents Label25 As MLabel
    Friend WithEvents txtPowerkw As MTextBox
    Friend WithEvents txtPowerhp As MTextBox
    Friend WithEvents txtPowerTransMethod As MTextBox
    Friend WithEvents Label27 As MLabel
    Friend WithEvents Frame5 As MFrame
    Friend WithEvents Label28 As MLabel
    Friend WithEvents txtShaftDia As MTextBox
    Friend WithEvents Label29 As MLabel
    Friend WithEvents cboShaftMatl As MComboBox
    Friend WithEvents Frame6 As MFrame
    Friend WithEvents Label30 As MLabel
    Friend WithEvents TextBox28 As MTextBox
    Friend WithEvents Label31 As MLabel
    Friend WithEvents cboVbeltType As MComboBox
    Friend WithEvents cmdUp_1 As MCommandButton
    Friend WithEvents cmdDn_1 As MCommandButton
    Friend WithEvents txtVbeltPcs As MTextBox
    Friend WithEvents Frame7 As MFrame
    Friend WithEvents Label32 As MLabel
    Friend WithEvents TextBox30 As MTextBox
    Friend WithEvents Label33 As MLabel
    Friend WithEvents cmdBigSize As MCommandButton
    Friend WithEvents cmdSmallSize As MCommandButton
    Friend WithEvents txtPulleySizeMotor As MTextBox
    Friend WithEvents txtPulleySizeFan As MTextBox
    Friend WithEvents Frame8 As MFrame
    Friend WithEvents Label34 As MLabel
    Friend WithEvents TextBox33 As MTextBox
    Friend WithEvents Label35 As MLabel
    Friend WithEvents cmdUp_2 As MCommandButton
    Friend WithEvents cmdDn_2 As MCommandButton
    Friend WithEvents txtBearingPulley As MTextBox
    Friend WithEvents txtBearingImp As MTextBox
    Friend WithEvents Frame9 As MFrame
    Friend WithEvents Frame10 As MFrame
    Friend WithEvents txtMplateSf As MTextBox
    Friend WithEvents Label36 As MLabel
    Friend WithEvents txtMplateAllowStress As MTextBox
    Friend WithEvents txtMplateStress As MTextBox
    Friend WithEvents Label37 As MLabel
    Friend WithEvents Label38 As MLabel
    Friend WithEvents Frame11 As MFrame
    Friend WithEvents txtBladeSf As MTextBox
    Friend WithEvents Label39 As MLabel
    Friend WithEvents txtBladeAllowStress As MTextBox
    Friend WithEvents txtBladeStress As MTextBox
    Friend WithEvents Label40 As MLabel
    Friend WithEvents Label41 As MLabel
    Friend WithEvents Frame12 As MFrame
    Friend WithEvents Label42 As MLabel
    Friend WithEvents txtImpGap As MTextBox
    Friend WithEvents txtInlet As MTextBox
    Friend WithEvents Label43 As MLabel
    Friend WithEvents txtU2 As MTextBox
    Friend WithEvents Label44 As MLabel
    Friend WithEvents txtDischarge As MTextBox
    Friend WithEvents Label45 As MLabel
    Friend WithEvents Label46 As MLabel
    Friend WithEvents Label47 As MLabel
    Friend WithEvents txtBearingLifeTimeHr As MTextBox
    Friend WithEvents txtBearingLifeTimeYear As MTextBox
    Friend WithEvents Frame13 As MFrame
    Friend WithEvents Label48 As MLabel
    Friend WithEvents txtMMaker As MTextBox
    Friend WithEvents txtMrpm As MTextBox
    Friend WithEvents Label49 As MLabel
    Friend WithEvents txtMeff As MTextBox
    Friend WithEvents Label50 As MLabel
    Friend WithEvents txtMType As MTextBox
    Friend WithEvents Label51 As MLabel
    Friend WithEvents txtMpf As MTextBox
    Friend WithEvents Label52 As MLabel
    Friend WithEvents txtMInsulGrade As MTextBox
    Friend WithEvents Label53 As MLabel
    Friend WithEvents Label54 As MLabel
    Friend WithEvents txtMphPoles As MTextBox
    Friend WithEvents Label55 As MLabel
    Friend WithEvents txtMStartAmp As MTextBox
    Friend WithEvents Label56 As MLabel
    Friend WithEvents txtMGD2 As MTextBox
    Friend WithEvents Label57 As MLabel
    Friend WithEvents txtMFrequency As MTextBox
    Friend WithEvents Label58 As MLabel
    Friend WithEvents txtMWeight As MTextBox
    Friend WithEvents Label59 As MLabel
    Friend WithEvents txtMOutput As MTextBox
    Friend WithEvents Label60 As MLabel
    Friend WithEvents txtMLoadAmp As MTextBox
    Friend WithEvents txtMVoltage As MTextBox
    Friend WithEvents Label61 As MLabel
    Friend WithEvents Label63 As MLabel
    Friend WithEvents txtMFrame As MTextBox
    Friend WithEvents cmdRestart As MCommandButton
    Friend WithEvents cmdOut As MCommandButton
    Friend WithEvents cmdEnd As MCommandButton

    Private Sub InitializeComponent()
        Me.SuspendLayout()
        Me.AutoScaleMode = AutoScaleMode.Dpi
        Me.AutoScaleDimensions = New SizeF(96.0F, 96.0F)
        Me.Font = New Font("맑은 고딕", 9F)
        Me.ClientSize = New Size(777, 635)
        Me.Text = "설계결과"
        Me.Name = "frmOutput"
        Me.Frame1 = New MFrame()
        Me.Frame1.Name = "Frame1"
        Me.Frame1.Location = New Point(8, 8)
        Me.Frame1.Size = New Size(388, 52)
        Me.Frame1.TabIndex = 0
        Me.Frame1.Text = "고객 및 날짜"
        Me.Controls.Add(Me.Frame1)
        Me.Label1 = New MLabel()
        Me.Label1.Name = "Label1"
        Me.Label1.Location = New Point(4, 16)
        Me.Label1.Size = New Size(37, 15)
        Me.Label1.TabIndex = 0
        Me.Label1.Text = "고객명"
        Me.Label1.UseMnemonic = False
        Me.Frame1.Controls.Add(Me.Label1)
        Me.Label2 = New MLabel()
        Me.Label2.Name = "Label2"
        Me.Label2.Location = New Point(208, 16)
        Me.Label2.Size = New Size(49, 15)
        Me.Label2.TabIndex = 1
        Me.Label2.Text = "설계일자"
        Me.Label2.UseMnemonic = False
        Me.Frame1.Controls.Add(Me.Label2)
        Me.TextBox1 = New MTextBox()
        Me.TextBox1.Name = "TextBox1"
        Me.TextBox1.Location = New Point(44, 12)
        Me.TextBox1.AutoSize = False
        Me.TextBox1.Size = New Size(153, 23)
        Me.TextBox1.TabIndex = 2
        Me.TextBox1.Multiline = True
        Me.TextBox1.Text = "삼성엔지니어링주식회사"
        Me.Frame1.Controls.Add(Me.TextBox1)
        Me.txtDate = New MTextBox()
        Me.txtDate.Name = "txtDate"
        Me.txtDate.Location = New Point(260, 12)
        Me.txtDate.AutoSize = False
        Me.txtDate.Size = New Size(116, 23)
        Me.txtDate.TabIndex = 3
        Me.txtDate.Multiline = True
        Me.Frame1.Controls.Add(Me.txtDate)
        Me.TextBox65 = New MTextBox()
        Me.TextBox65.Name = "TextBox65"
        Me.TextBox65.Location = New Point(44, 12)
        Me.TextBox65.AutoSize = False
        Me.TextBox65.Size = New Size(153, 23)
        Me.TextBox65.TabIndex = 4
        Me.TextBox65.Multiline = True
        Me.TextBox65.Text = "삼성엔지니어링주식회사"
        Me.Frame1.Controls.Add(Me.TextBox65)
        Me.txtCustomer = New MTextBox()
        Me.txtCustomer.Name = "txtCustomer"
        Me.txtCustomer.Location = New Point(44, 12)
        Me.txtCustomer.AutoSize = False
        Me.txtCustomer.Size = New Size(153, 23)
        Me.txtCustomer.TabIndex = 5
        Me.txtCustomer.Multiline = True
        Me.Frame1.Controls.Add(Me.txtCustomer)
        Me.Frame2 = New MFrame()
        Me.Frame2.Name = "Frame2"
        Me.Frame2.Location = New Point(400, 8)
        Me.Frame2.Size = New Size(368, 192)
        Me.Frame2.TabIndex = 1
        Me.Frame2.Text = "회전차 규격"
        Me.Controls.Add(Me.Frame2)
        Me.Label3 = New MLabel()
        Me.Label3.Name = "Label3"
        Me.Label3.Location = New Point(4, 16)
        Me.Label3.Size = New Size(37, 15)
        Me.Label3.TabIndex = 0
        Me.Label3.Text = "회전수"
        Me.Label3.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label3)
        Me.txtN = New MTextBox()
        Me.txtN.Name = "txtN"
        Me.txtN.Location = New Point(68, 12)
        Me.txtN.AutoSize = False
        Me.txtN.Size = New Size(92, 23)
        Me.txtN.TabIndex = 1
        Me.txtN.Multiline = True
        Me.txtN.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtN)
        Me.txtD2 = New MTextBox()
        Me.txtD2.Name = "txtD2"
        Me.txtD2.Location = New Point(68, 40)
        Me.txtD2.AutoSize = False
        Me.txtD2.Size = New Size(92, 23)
        Me.txtD2.TabIndex = 2
        Me.txtD2.Multiline = True
        Me.txtD2.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtD2)
        Me.Label5 = New MLabel()
        Me.Label5.Name = "Label5"
        Me.Label5.Location = New Point(4, 44)
        Me.Label5.Size = New Size(25, 15)
        Me.Label5.TabIndex = 3
        Me.Label5.Text = "외경"
        Me.Label5.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label5)
        Me.txtBeta1 = New MTextBox()
        Me.txtBeta1.Name = "txtBeta1"
        Me.txtBeta1.Location = New Point(68, 96)
        Me.txtBeta1.AutoSize = False
        Me.txtBeta1.Size = New Size(92, 23)
        Me.txtBeta1.TabIndex = 4
        Me.txtBeta1.Multiline = True
        Me.txtBeta1.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtBeta1)
        Me.Label6 = New MLabel()
        Me.Label6.Name = "Label6"
        Me.Label6.Location = New Point(4, 72)
        Me.Label6.Size = New Size(25, 15)
        Me.Label6.TabIndex = 5
        Me.Label6.Text = "내경"
        Me.Label6.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label6)
        Me.txtD1 = New MTextBox()
        Me.txtD1.Name = "txtD1"
        Me.txtD1.Location = New Point(68, 68)
        Me.txtD1.AutoSize = False
        Me.txtD1.Size = New Size(92, 23)
        Me.txtD1.TabIndex = 6
        Me.txtD1.Multiline = True
        Me.txtD1.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtD1)
        Me.Label7 = New MLabel()
        Me.Label7.Name = "Label7"
        Me.Label7.Location = New Point(4, 100)
        Me.Label7.Size = New Size(49, 15)
        Me.Label7.TabIndex = 7
        Me.Label7.Text = "입구각도"
        Me.Label7.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label7)
        Me.txtY = New MTextBox()
        Me.txtY.Name = "txtY"
        Me.txtY.Location = New Point(68, 152)
        Me.txtY.AutoSize = False
        Me.txtY.Size = New Size(92, 23)
        Me.txtY.TabIndex = 8
        Me.txtY.Multiline = True
        Me.txtY.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtY)
        Me.Label8 = New MLabel()
        Me.Label8.Name = "Label8"
        Me.Label8.Location = New Point(4, 128)
        Me.Label8.Size = New Size(49, 15)
        Me.Label8.TabIndex = 9
        Me.Label8.Text = "출구각도"
        Me.Label8.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label8)
        Me.txtBeta2 = New MTextBox()
        Me.txtBeta2.Name = "txtBeta2"
        Me.txtBeta2.Location = New Point(68, 124)
        Me.txtBeta2.AutoSize = False
        Me.txtBeta2.Size = New Size(92, 23)
        Me.txtBeta2.TabIndex = 10
        Me.txtBeta2.Multiline = True
        Me.txtBeta2.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtBeta2)
        Me.Label9 = New MLabel()
        Me.Label9.Name = "Label9"
        Me.Label9.Location = New Point(4, 156)
        Me.Label9.Size = New Size(56, 15)
        Me.Label9.TabIndex = 11
        Me.Label9.Text = "작도반경Y"
        Me.Label9.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label9)
        Me.Label10 = New MLabel()
        Me.Label10.Name = "Label10"
        Me.Label10.Location = New Point(196, 156)
        Me.Label10.Size = New Size(56, 15)
        Me.Label10.TabIndex = 12
        Me.Label10.Text = "작도반경R"
        Me.Label10.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label10)
        Me.txtBladeNo = New MTextBox()
        Me.txtBladeNo.Name = "txtBladeNo"
        Me.txtBladeNo.Location = New Point(260, 12)
        Me.txtBladeNo.AutoSize = False
        Me.txtBladeNo.Size = New Size(92, 23)
        Me.txtBladeNo.TabIndex = 13
        Me.txtBladeNo.Multiline = True
        Me.txtBladeNo.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtBladeNo)
        Me.Label11 = New MLabel()
        Me.Label11.Name = "Label11"
        Me.Label11.Location = New Point(196, 16)
        Me.Label11.Size = New Size(37, 15)
        Me.Label11.TabIndex = 14
        Me.Label11.Text = "날개수"
        Me.Label11.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label11)
        Me.txtB2 = New MTextBox()
        Me.txtB2.Name = "txtB2"
        Me.txtB2.Location = New Point(260, 40)
        Me.txtB2.AutoSize = False
        Me.txtB2.Size = New Size(92, 23)
        Me.txtB2.TabIndex = 15
        Me.txtB2.Multiline = True
        Me.txtB2.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtB2)
        Me.Label12 = New MLabel()
        Me.Label12.Name = "Label12"
        Me.Label12.Location = New Point(196, 44)
        Me.Label12.Size = New Size(25, 15)
        Me.Label12.TabIndex = 16
        Me.Label12.Text = "외폭"
        Me.Label12.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label12)
        Me.txtImpMatl = New MTextBox()
        Me.txtImpMatl.Name = "txtImpMatl"
        Me.txtImpMatl.Location = New Point(260, 96)
        Me.txtImpMatl.AutoSize = False
        Me.txtImpMatl.Size = New Size(92, 23)
        Me.txtImpMatl.TabIndex = 17
        Me.txtImpMatl.Multiline = True
        Me.txtImpMatl.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtImpMatl)
        Me.Label13 = New MLabel()
        Me.Label13.Name = "Label13"
        Me.Label13.Location = New Point(196, 72)
        Me.Label13.Size = New Size(25, 15)
        Me.Label13.TabIndex = 18
        Me.Label13.Text = "내폭"
        Me.Label13.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label13)
        Me.txtB1 = New MTextBox()
        Me.txtB1.Name = "txtB1"
        Me.txtB1.Location = New Point(260, 68)
        Me.txtB1.AutoSize = False
        Me.txtB1.Size = New Size(92, 23)
        Me.txtB1.TabIndex = 19
        Me.txtB1.Multiline = True
        Me.txtB1.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtB1)
        Me.Label14 = New MLabel()
        Me.Label14.Name = "Label14"
        Me.Label14.Location = New Point(196, 100)
        Me.Label14.Size = New Size(25, 15)
        Me.Label14.TabIndex = 20
        Me.Label14.Text = "재질"
        Me.Label14.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label14)
        Me.txtR = New MTextBox()
        Me.txtR.Name = "txtR"
        Me.txtR.Location = New Point(260, 152)
        Me.txtR.AutoSize = False
        Me.txtR.Size = New Size(92, 23)
        Me.txtR.TabIndex = 21
        Me.txtR.Multiline = True
        Me.txtR.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtR)
        Me.Label15 = New MLabel()
        Me.Label15.Name = "Label15"
        Me.Label15.Location = New Point(196, 128)
        Me.Label15.Size = New Size(25, 15)
        Me.Label15.TabIndex = 22
        Me.Label15.Text = "두께"
        Me.Label15.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label15)
        Me.txtBladeThickness = New MTextBox()
        Me.txtBladeThickness.Name = "txtBladeThickness"
        Me.txtBladeThickness.Location = New Point(260, 124)
        Me.txtBladeThickness.AutoSize = False
        Me.txtBladeThickness.Size = New Size(92, 23)
        Me.txtBladeThickness.TabIndex = 23
        Me.txtBladeThickness.Multiline = True
        Me.txtBladeThickness.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtBladeThickness)
        Me.Frame3 = New MFrame()
        Me.Frame3.Name = "Frame3"
        Me.Frame3.Location = New Point(8, 64)
        Me.Frame3.Size = New Size(388, 80)
        Me.Frame3.TabIndex = 2
        Me.Frame3.Text = "설계조건"
        Me.Controls.Add(Me.Frame3)
        Me.Label16 = New MLabel()
        Me.Label16.Name = "Label16"
        Me.Label16.Location = New Point(12, 16)
        Me.Label16.Size = New Size(25, 15)
        Me.Label16.TabIndex = 0
        Me.Label16.Text = "풍량"
        Me.Label16.UseMnemonic = False
        Me.Frame3.Controls.Add(Me.Label16)
        Me.txtQ = New MTextBox()
        Me.txtQ.Name = "txtQ"
        Me.txtQ.Location = New Point(76, 12)
        Me.txtQ.AutoSize = False
        Me.txtQ.Size = New Size(92, 23)
        Me.txtQ.TabIndex = 1
        Me.txtQ.Multiline = True
        Me.txtQ.TextAlign = HorizontalAlignment.Center
        Me.Frame3.Controls.Add(Me.txtQ)
        Me.txtPs = New MTextBox()
        Me.txtPs.Name = "txtPs"
        Me.txtPs.Location = New Point(76, 40)
        Me.txtPs.AutoSize = False
        Me.txtPs.Size = New Size(92, 23)
        Me.txtPs.TabIndex = 2
        Me.txtPs.Multiline = True
        Me.txtPs.TextAlign = HorizontalAlignment.Center
        Me.Frame3.Controls.Add(Me.txtPs)
        Me.Label17 = New MLabel()
        Me.Label17.Name = "Label17"
        Me.Label17.Location = New Point(12, 44)
        Me.Label17.Size = New Size(25, 15)
        Me.Label17.TabIndex = 3
        Me.Label17.Text = "정압"
        Me.Label17.UseMnemonic = False
        Me.Frame3.Controls.Add(Me.Label17)
        Me.txtTemp = New MTextBox()
        Me.txtTemp.Name = "txtTemp"
        Me.txtTemp.Location = New Point(268, 12)
        Me.txtTemp.AutoSize = False
        Me.txtTemp.Size = New Size(92, 23)
        Me.txtTemp.TabIndex = 4
        Me.txtTemp.Multiline = True
        Me.txtTemp.TextAlign = HorizontalAlignment.Center
        Me.Frame3.Controls.Add(Me.txtTemp)
        Me.Label23 = New MLabel()
        Me.Label23.Name = "Label23"
        Me.Label23.Location = New Point(196, 16)
        Me.Label23.Size = New Size(25, 15)
        Me.Label23.TabIndex = 5
        Me.Label23.Text = "온도"
        Me.Label23.UseMnemonic = False
        Me.Frame3.Controls.Add(Me.Label23)
        Me.txtDensity = New MTextBox()
        Me.txtDensity.Name = "txtDensity"
        Me.txtDensity.Location = New Point(268, 40)
        Me.txtDensity.AutoSize = False
        Me.txtDensity.Size = New Size(92, 23)
        Me.txtDensity.TabIndex = 6
        Me.txtDensity.Multiline = True
        Me.txtDensity.TextAlign = HorizontalAlignment.Center
        Me.Frame3.Controls.Add(Me.txtDensity)
        Me.Label24 = New MLabel()
        Me.Label24.Name = "Label24"
        Me.Label24.Location = New Point(196, 44)
        Me.Label24.Size = New Size(25, 15)
        Me.Label24.TabIndex = 7
        Me.Label24.Text = "밀도"
        Me.Label24.UseMnemonic = False
        Me.Frame3.Controls.Add(Me.Label24)
        Me.Frame4 = New MFrame()
        Me.Frame4.Name = "Frame4"
        Me.Frame4.Location = New Point(8, 152)
        Me.Frame4.Size = New Size(388, 288)
        Me.Frame4.TabIndex = 3
        Me.Frame4.Text = "동력전달 및 축"
        Me.Controls.Add(Me.Frame4)
        Me.Label25 = New MLabel()
        Me.Label25.Name = "Label25"
        Me.Label25.Location = New Point(12, 16)
        Me.Label25.Size = New Size(49, 15)
        Me.Label25.TabIndex = 0
        Me.Label25.Text = "소요동력"
        Me.Label25.UseMnemonic = False
        Me.Frame4.Controls.Add(Me.Label25)
        Me.txtPowerkw = New MTextBox()
        Me.txtPowerkw.Name = "txtPowerkw"
        Me.txtPowerkw.Location = New Point(76, 12)
        Me.txtPowerkw.AutoSize = False
        Me.txtPowerkw.Size = New Size(92, 23)
        Me.txtPowerkw.TabIndex = 1
        Me.txtPowerkw.Multiline = True
        Me.txtPowerkw.TextAlign = HorizontalAlignment.Center
        Me.Frame4.Controls.Add(Me.txtPowerkw)
        Me.txtPowerhp = New MTextBox()
        Me.txtPowerhp.Name = "txtPowerhp"
        Me.txtPowerhp.Location = New Point(76, 40)
        Me.txtPowerhp.AutoSize = False
        Me.txtPowerhp.Size = New Size(92, 23)
        Me.txtPowerhp.TabIndex = 2
        Me.txtPowerhp.Multiline = True
        Me.txtPowerhp.TextAlign = HorizontalAlignment.Center
        Me.Frame4.Controls.Add(Me.txtPowerhp)
        Me.txtPowerTransMethod = New MTextBox()
        Me.txtPowerTransMethod.Name = "txtPowerTransMethod"
        Me.txtPowerTransMethod.Location = New Point(268, 12)
        Me.txtPowerTransMethod.AutoSize = False
        Me.txtPowerTransMethod.Size = New Size(92, 23)
        Me.txtPowerTransMethod.TabIndex = 3
        Me.txtPowerTransMethod.Multiline = True
        Me.txtPowerTransMethod.TextAlign = HorizontalAlignment.Center
        Me.Frame4.Controls.Add(Me.txtPowerTransMethod)
        Me.Label27 = New MLabel()
        Me.Label27.Name = "Label27"
        Me.Label27.Location = New Point(192, 16)
        Me.Label27.Size = New Size(49, 15)
        Me.Label27.TabIndex = 4
        Me.Label27.Text = "전동방식"
        Me.Label27.UseMnemonic = False
        Me.Frame4.Controls.Add(Me.Label27)
        Me.Frame5 = New MFrame()
        Me.Frame5.Name = "Frame5"
        Me.Frame5.Location = New Point(8, 68)
        Me.Frame5.Size = New Size(180, 92)
        Me.Frame5.TabIndex = 5
        Me.Frame5.Text = "축"
        Me.Frame4.Controls.Add(Me.Frame5)
        Me.Label28 = New MLabel()
        Me.Label28.Name = "Label28"
        Me.Label28.Location = New Point(4, 20)
        Me.Label28.Size = New Size(25, 15)
        Me.Label28.TabIndex = 0
        Me.Label28.Text = "직경"
        Me.Label28.UseMnemonic = False
        Me.Frame5.Controls.Add(Me.Label28)
        Me.txtShaftDia = New MTextBox()
        Me.txtShaftDia.Name = "txtShaftDia"
        Me.txtShaftDia.Location = New Point(64, 16)
        Me.txtShaftDia.AutoSize = False
        Me.txtShaftDia.Size = New Size(92, 23)
        Me.txtShaftDia.TabIndex = 1
        Me.txtShaftDia.Multiline = True
        Me.txtShaftDia.TextAlign = HorizontalAlignment.Center
        Me.Frame5.Controls.Add(Me.txtShaftDia)
        Me.Label29 = New MLabel()
        Me.Label29.Name = "Label29"
        Me.Label29.Location = New Point(4, 48)
        Me.Label29.Size = New Size(25, 15)
        Me.Label29.TabIndex = 2
        Me.Label29.Text = "재질"
        Me.Label29.UseMnemonic = False
        Me.Frame5.Controls.Add(Me.Label29)
        Me.cboShaftMatl = New MComboBox()
        Me.cboShaftMatl.Name = "cboShaftMatl"
        Me.cboShaftMatl.Location = New Point(64, 44)
        Me.cboShaftMatl.DropDownStyle = ComboBoxStyle.DropDown
        Me.cboShaftMatl.IntegralHeight = False
        Me.cboShaftMatl.MaxDropDownItems = 12
        Me.cboShaftMatl.Size = New Size(92, 23)
        Me.cboShaftMatl.TabIndex = 3
        Me.cboShaftMatl.Text = "SM45C"
        Me.Frame5.Controls.Add(Me.cboShaftMatl)
        Me.Frame6 = New MFrame()
        Me.Frame6.Name = "Frame6"
        Me.Frame6.Location = New Point(196, 68)
        Me.Frame6.Size = New Size(180, 92)
        Me.Frame6.TabIndex = 6
        Me.Frame6.Text = "V-벨트"
        Me.Frame4.Controls.Add(Me.Frame6)
        Me.Label30 = New MLabel()
        Me.Label30.Name = "Label30"
        Me.Label30.Location = New Point(12, 48)
        Me.Label30.Size = New Size(37, 15)
        Me.Label30.TabIndex = 0
        Me.Label30.Text = "가닥수"
        Me.Label30.UseMnemonic = False
        Me.Frame6.Controls.Add(Me.Label30)
        Me.TextBox28 = New MTextBox()
        Me.TextBox28.Name = "TextBox28"
        Me.TextBox28.Location = New Point(72, 44)
        Me.TextBox28.AutoSize = False
        Me.TextBox28.Size = New Size(44, 23)
        Me.TextBox28.TabIndex = 1
        Me.TextBox28.Multiline = True
        Me.TextBox28.TextAlign = HorizontalAlignment.Center
        Me.Frame6.Controls.Add(Me.TextBox28)
        Me.Label31 = New MLabel()
        Me.Label31.Name = "Label31"
        Me.Label31.Location = New Point(12, 20)
        Me.Label31.Size = New Size(25, 15)
        Me.Label31.TabIndex = 2
        Me.Label31.Text = "형식"
        Me.Label31.UseMnemonic = False
        Me.Frame6.Controls.Add(Me.Label31)
        Me.cboVbeltType = New MComboBox()
        Me.cboVbeltType.Name = "cboVbeltType"
        Me.cboVbeltType.Location = New Point(72, 16)
        Me.cboVbeltType.DropDownStyle = ComboBoxStyle.DropDown
        Me.cboVbeltType.IntegralHeight = False
        Me.cboVbeltType.MaxDropDownItems = 12
        Me.cboVbeltType.Size = New Size(92, 23)
        Me.cboVbeltType.TabIndex = 3
        Me.Frame6.Controls.Add(Me.cboVbeltType)
        Me.cmdUp_1 = New MCommandButton()
        Me.cmdUp_1.Name = "cmdUp_1"
        Me.cmdUp_1.Location = New Point(124, 44)
        Me.cmdUp_1.Size = New Size(20, 23)
        Me.cmdUp_1.TabIndex = 4
        Me.cmdUp_1.Font = New Font("맑은 고딕", 6F)
        Me.cmdUp_1.Text = "▲"
        Me.cmdUp_1.UseMnemonic = False
        Me.cmdUp_1.UseVisualStyleBackColor = True
        Me.Frame6.Controls.Add(Me.cmdUp_1)
        Me.cmdDn_1 = New MCommandButton()
        Me.cmdDn_1.Name = "cmdDn_1"
        Me.cmdDn_1.Location = New Point(144, 44)
        Me.cmdDn_1.Size = New Size(20, 23)
        Me.cmdDn_1.TabIndex = 5
        Me.cmdDn_1.Font = New Font("맑은 고딕", 6F)
        Me.cmdDn_1.Text = "▼"
        Me.cmdDn_1.UseMnemonic = False
        Me.cmdDn_1.UseVisualStyleBackColor = True
        Me.Frame6.Controls.Add(Me.cmdDn_1)
        Me.txtVbeltPcs = New MTextBox()
        Me.txtVbeltPcs.Name = "txtVbeltPcs"
        Me.txtVbeltPcs.Location = New Point(72, 44)
        Me.txtVbeltPcs.AutoSize = False
        Me.txtVbeltPcs.Size = New Size(48, 23)
        Me.txtVbeltPcs.TabIndex = 6
        Me.txtVbeltPcs.Multiline = True
        Me.txtVbeltPcs.TextAlign = HorizontalAlignment.Center
        Me.Frame6.Controls.Add(Me.txtVbeltPcs)
        Me.Frame7 = New MFrame()
        Me.Frame7.Name = "Frame7"
        Me.Frame7.Location = New Point(196, 172)
        Me.Frame7.Size = New Size(180, 92)
        Me.Frame7.TabIndex = 7
        Me.Frame7.Text = "풀리규격"
        Me.Frame4.Controls.Add(Me.Frame7)
        Me.Label32 = New MLabel()
        Me.Label32.Name = "Label32"
        Me.Label32.Location = New Point(12, 48)
        Me.Label32.Size = New Size(37, 15)
        Me.Label32.TabIndex = 0
        Me.Label32.Text = "모터측"
        Me.Label32.UseMnemonic = False
        Me.Frame7.Controls.Add(Me.Label32)
        Me.TextBox30 = New MTextBox()
        Me.TextBox30.Name = "TextBox30"
        Me.TextBox30.Location = New Point(72, 44)
        Me.TextBox30.AutoSize = False
        Me.TextBox30.Size = New Size(44, 23)
        Me.TextBox30.TabIndex = 1
        Me.TextBox30.Multiline = True
        Me.TextBox30.TextAlign = HorizontalAlignment.Center
        Me.Frame7.Controls.Add(Me.TextBox30)
        Me.Label33 = New MLabel()
        Me.Label33.Name = "Label33"
        Me.Label33.Location = New Point(12, 20)
        Me.Label33.Size = New Size(49, 15)
        Me.Label33.TabIndex = 2
        Me.Label33.Text = "송풍기측"
        Me.Label33.UseMnemonic = False
        Me.Frame7.Controls.Add(Me.Label33)
        Me.cmdBigSize = New MCommandButton()
        Me.cmdBigSize.Name = "cmdBigSize"
        Me.cmdBigSize.Location = New Point(144, 16)
        Me.cmdBigSize.Size = New Size(20, 23)
        Me.cmdBigSize.TabIndex = 3
        Me.cmdBigSize.Font = New Font("맑은 고딕", 6F)
        Me.cmdBigSize.Text = "▲"
        Me.cmdBigSize.UseMnemonic = False
        Me.cmdBigSize.UseVisualStyleBackColor = True
        Me.Frame7.Controls.Add(Me.cmdBigSize)
        Me.cmdSmallSize = New MCommandButton()
        Me.cmdSmallSize.Name = "cmdSmallSize"
        Me.cmdSmallSize.Location = New Point(144, 44)
        Me.cmdSmallSize.Size = New Size(20, 23)
        Me.cmdSmallSize.TabIndex = 4
        Me.cmdSmallSize.Font = New Font("맑은 고딕", 6F)
        Me.cmdSmallSize.Text = "▼"
        Me.cmdSmallSize.UseMnemonic = False
        Me.cmdSmallSize.UseVisualStyleBackColor = True
        Me.Frame7.Controls.Add(Me.cmdSmallSize)
        Me.txtPulleySizeMotor = New MTextBox()
        Me.txtPulleySizeMotor.Name = "txtPulleySizeMotor"
        Me.txtPulleySizeMotor.Location = New Point(72, 44)
        Me.txtPulleySizeMotor.AutoSize = False
        Me.txtPulleySizeMotor.Size = New Size(64, 23)
        Me.txtPulleySizeMotor.TabIndex = 5
        Me.txtPulleySizeMotor.Multiline = True
        Me.txtPulleySizeMotor.TextAlign = HorizontalAlignment.Center
        Me.Frame7.Controls.Add(Me.txtPulleySizeMotor)
        Me.txtPulleySizeFan = New MTextBox()
        Me.txtPulleySizeFan.Name = "txtPulleySizeFan"
        Me.txtPulleySizeFan.Location = New Point(72, 16)
        Me.txtPulleySizeFan.AutoSize = False
        Me.txtPulleySizeFan.Size = New Size(64, 23)
        Me.txtPulleySizeFan.TabIndex = 6
        Me.txtPulleySizeFan.Multiline = True
        Me.txtPulleySizeFan.TextAlign = HorizontalAlignment.Center
        Me.Frame7.Controls.Add(Me.txtPulleySizeFan)
        Me.Frame8 = New MFrame()
        Me.Frame8.Name = "Frame8"
        Me.Frame8.Location = New Point(8, 172)
        Me.Frame8.Size = New Size(180, 92)
        Me.Frame8.TabIndex = 8
        Me.Frame8.Text = "베어링"
        Me.Frame4.Controls.Add(Me.Frame8)
        Me.Label34 = New MLabel()
        Me.Label34.Name = "Label34"
        Me.Label34.Location = New Point(12, 48)
        Me.Label34.Size = New Size(37, 15)
        Me.Label34.TabIndex = 0
        Me.Label34.Text = "풀리측"
        Me.Label34.UseMnemonic = False
        Me.Frame8.Controls.Add(Me.Label34)
        Me.TextBox33 = New MTextBox()
        Me.TextBox33.Name = "TextBox33"
        Me.TextBox33.Location = New Point(72, 44)
        Me.TextBox33.AutoSize = False
        Me.TextBox33.Size = New Size(44, 23)
        Me.TextBox33.TabIndex = 1
        Me.TextBox33.Multiline = True
        Me.TextBox33.TextAlign = HorizontalAlignment.Center
        Me.Frame8.Controls.Add(Me.TextBox33)
        Me.Label35 = New MLabel()
        Me.Label35.Name = "Label35"
        Me.Label35.Location = New Point(12, 20)
        Me.Label35.Size = New Size(49, 15)
        Me.Label35.TabIndex = 2
        Me.Label35.Text = "회전차측"
        Me.Label35.UseMnemonic = False
        Me.Frame8.Controls.Add(Me.Label35)
        Me.cmdUp_2 = New MCommandButton()
        Me.cmdUp_2.Name = "cmdUp_2"
        Me.cmdUp_2.Location = New Point(144, 16)
        Me.cmdUp_2.Size = New Size(20, 23)
        Me.cmdUp_2.TabIndex = 3
        Me.cmdUp_2.Font = New Font("맑은 고딕", 6F)
        Me.cmdUp_2.Text = "▲"
        Me.cmdUp_2.UseMnemonic = False
        Me.cmdUp_2.UseVisualStyleBackColor = True
        Me.Frame8.Controls.Add(Me.cmdUp_2)
        Me.cmdDn_2 = New MCommandButton()
        Me.cmdDn_2.Name = "cmdDn_2"
        Me.cmdDn_2.Location = New Point(144, 44)
        Me.cmdDn_2.Size = New Size(20, 23)
        Me.cmdDn_2.TabIndex = 4
        Me.cmdDn_2.Font = New Font("맑은 고딕", 6F)
        Me.cmdDn_2.Text = "▼"
        Me.cmdDn_2.UseMnemonic = False
        Me.cmdDn_2.UseVisualStyleBackColor = True
        Me.Frame8.Controls.Add(Me.cmdDn_2)
        Me.txtBearingPulley = New MTextBox()
        Me.txtBearingPulley.Name = "txtBearingPulley"
        Me.txtBearingPulley.Location = New Point(72, 44)
        Me.txtBearingPulley.AutoSize = False
        Me.txtBearingPulley.Size = New Size(64, 23)
        Me.txtBearingPulley.TabIndex = 5
        Me.txtBearingPulley.Multiline = True
        Me.txtBearingPulley.TextAlign = HorizontalAlignment.Center
        Me.Frame8.Controls.Add(Me.txtBearingPulley)
        Me.txtBearingImp = New MTextBox()
        Me.txtBearingImp.Name = "txtBearingImp"
        Me.txtBearingImp.Location = New Point(72, 16)
        Me.txtBearingImp.AutoSize = False
        Me.txtBearingImp.Size = New Size(64, 23)
        Me.txtBearingImp.TabIndex = 6
        Me.txtBearingImp.Multiline = True
        Me.txtBearingImp.TextAlign = HorizontalAlignment.Center
        Me.Frame8.Controls.Add(Me.txtBearingImp)
        Me.Frame9 = New MFrame()
        Me.Frame9.Name = "Frame9"
        Me.Frame9.Location = New Point(400, 204)
        Me.Frame9.Size = New Size(368, 128)
        Me.Frame9.TabIndex = 4
        Me.Frame9.Text = "회전차 응력"
        Me.Controls.Add(Me.Frame9)
        Me.Frame10 = New MFrame()
        Me.Frame10.Name = "Frame10"
        Me.Frame10.Location = New Point(12, 8)
        Me.Frame10.Size = New Size(168, 104)
        Me.Frame10.TabIndex = 0
        Me.Frame10.Text = "주판"
        Me.Frame9.Controls.Add(Me.Frame10)
        Me.txtMplateSf = New MTextBox()
        Me.txtMplateSf.Name = "txtMplateSf"
        Me.txtMplateSf.Location = New Point(60, 64)
        Me.txtMplateSf.AutoSize = False
        Me.txtMplateSf.Size = New Size(92, 23)
        Me.txtMplateSf.TabIndex = 0
        Me.txtMplateSf.ForeColor = SystemColors.Highlight
        Me.txtMplateSf.Multiline = True
        Me.txtMplateSf.TextAlign = HorizontalAlignment.Center
        Me.Frame10.Controls.Add(Me.txtMplateSf)
        Me.Label36 = New MLabel()
        Me.Label36.Name = "Label36"
        Me.Label36.Location = New Point(8, 12)
        Me.Label36.Size = New Size(49, 15)
        Me.Label36.TabIndex = 1
        Me.Label36.Text = "허용응력"
        Me.Label36.UseMnemonic = False
        Me.Frame10.Controls.Add(Me.Label36)
        Me.txtMplateAllowStress = New MTextBox()
        Me.txtMplateAllowStress.Name = "txtMplateAllowStress"
        Me.txtMplateAllowStress.Location = New Point(60, 8)
        Me.txtMplateAllowStress.AutoSize = False
        Me.txtMplateAllowStress.Size = New Size(92, 23)
        Me.txtMplateAllowStress.TabIndex = 2
        Me.txtMplateAllowStress.Multiline = True
        Me.txtMplateAllowStress.TextAlign = HorizontalAlignment.Center
        Me.Frame10.Controls.Add(Me.txtMplateAllowStress)
        Me.txtMplateStress = New MTextBox()
        Me.txtMplateStress.Name = "txtMplateStress"
        Me.txtMplateStress.Location = New Point(60, 36)
        Me.txtMplateStress.AutoSize = False
        Me.txtMplateStress.Size = New Size(92, 23)
        Me.txtMplateStress.TabIndex = 3
        Me.txtMplateStress.Multiline = True
        Me.txtMplateStress.TextAlign = HorizontalAlignment.Center
        Me.Frame10.Controls.Add(Me.txtMplateStress)
        Me.Label37 = New MLabel()
        Me.Label37.Name = "Label37"
        Me.Label37.Location = New Point(8, 40)
        Me.Label37.Size = New Size(25, 15)
        Me.Label37.TabIndex = 4
        Me.Label37.Text = "응력"
        Me.Label37.UseMnemonic = False
        Me.Frame10.Controls.Add(Me.Label37)
        Me.Label38 = New MLabel()
        Me.Label38.Name = "Label38"
        Me.Label38.Location = New Point(8, 68)
        Me.Label38.Size = New Size(37, 15)
        Me.Label38.TabIndex = 5
        Me.Label38.Text = "안전율"
        Me.Label38.UseMnemonic = False
        Me.Frame10.Controls.Add(Me.Label38)
        Me.Frame11 = New MFrame()
        Me.Frame11.Name = "Frame11"
        Me.Frame11.Location = New Point(188, 8)
        Me.Frame11.Size = New Size(168, 104)
        Me.Frame11.TabIndex = 1
        Me.Frame11.Text = "날개"
        Me.Frame9.Controls.Add(Me.Frame11)
        Me.txtBladeSf = New MTextBox()
        Me.txtBladeSf.Name = "txtBladeSf"
        Me.txtBladeSf.Location = New Point(60, 64)
        Me.txtBladeSf.AutoSize = False
        Me.txtBladeSf.Size = New Size(92, 23)
        Me.txtBladeSf.TabIndex = 0
        Me.txtBladeSf.ForeColor = SystemColors.Highlight
        Me.txtBladeSf.Multiline = True
        Me.txtBladeSf.TextAlign = HorizontalAlignment.Center
        Me.Frame11.Controls.Add(Me.txtBladeSf)
        Me.Label39 = New MLabel()
        Me.Label39.Name = "Label39"
        Me.Label39.Location = New Point(8, 12)
        Me.Label39.Size = New Size(49, 15)
        Me.Label39.TabIndex = 1
        Me.Label39.Text = "허용응력"
        Me.Label39.UseMnemonic = False
        Me.Frame11.Controls.Add(Me.Label39)
        Me.txtBladeAllowStress = New MTextBox()
        Me.txtBladeAllowStress.Name = "txtBladeAllowStress"
        Me.txtBladeAllowStress.Location = New Point(60, 8)
        Me.txtBladeAllowStress.AutoSize = False
        Me.txtBladeAllowStress.Size = New Size(92, 23)
        Me.txtBladeAllowStress.TabIndex = 2
        Me.txtBladeAllowStress.Multiline = True
        Me.txtBladeAllowStress.TextAlign = HorizontalAlignment.Center
        Me.Frame11.Controls.Add(Me.txtBladeAllowStress)
        Me.txtBladeStress = New MTextBox()
        Me.txtBladeStress.Name = "txtBladeStress"
        Me.txtBladeStress.Location = New Point(60, 36)
        Me.txtBladeStress.AutoSize = False
        Me.txtBladeStress.Size = New Size(92, 23)
        Me.txtBladeStress.TabIndex = 3
        Me.txtBladeStress.Multiline = True
        Me.txtBladeStress.TextAlign = HorizontalAlignment.Center
        Me.Frame11.Controls.Add(Me.txtBladeStress)
        Me.Label40 = New MLabel()
        Me.Label40.Name = "Label40"
        Me.Label40.Location = New Point(8, 40)
        Me.Label40.Size = New Size(25, 15)
        Me.Label40.TabIndex = 4
        Me.Label40.Text = "응력"
        Me.Label40.UseMnemonic = False
        Me.Frame11.Controls.Add(Me.Label40)
        Me.Label41 = New MLabel()
        Me.Label41.Name = "Label41"
        Me.Label41.Location = New Point(8, 68)
        Me.Label41.Size = New Size(37, 15)
        Me.Label41.TabIndex = 5
        Me.Label41.Text = "안전율"
        Me.Label41.UseMnemonic = False
        Me.Frame11.Controls.Add(Me.Label41)
        Me.Frame12 = New MFrame()
        Me.Frame12.Name = "Frame12"
        Me.Frame12.Location = New Point(400, 336)
        Me.Frame12.Size = New Size(368, 104)
        Me.Frame12.TabIndex = 5
        Me.Frame12.Text = "기타사항"
        Me.Controls.Add(Me.Frame12)
        Me.Label42 = New MLabel()
        Me.Label42.Name = "Label42"
        Me.Label42.Location = New Point(8, 40)
        Me.Label42.Size = New Size(65, 15)
        Me.Label42.TabIndex = 0
        Me.Label42.Text = "회전차 간극"
        Me.Label42.UseMnemonic = False
        Me.Frame12.Controls.Add(Me.Label42)
        Me.txtImpGap = New MTextBox()
        Me.txtImpGap.Name = "txtImpGap"
        Me.txtImpGap.Location = New Point(80, 36)
        Me.txtImpGap.AutoSize = False
        Me.txtImpGap.Size = New Size(92, 23)
        Me.txtImpGap.TabIndex = 1
        Me.txtImpGap.Multiline = True
        Me.txtImpGap.TextAlign = HorizontalAlignment.Center
        Me.Frame12.Controls.Add(Me.txtImpGap)
        Me.txtInlet = New MTextBox()
        Me.txtInlet.Name = "txtInlet"
        Me.txtInlet.Location = New Point(80, 64)
        Me.txtInlet.AutoSize = False
        Me.txtInlet.Size = New Size(92, 23)
        Me.txtInlet.TabIndex = 2
        Me.txtInlet.Multiline = True
        Me.txtInlet.TextAlign = HorizontalAlignment.Center
        Me.Frame12.Controls.Add(Me.txtInlet)
        Me.Label43 = New MLabel()
        Me.Label43.Name = "Label43"
        Me.Label43.Location = New Point(8, 68)
        Me.Label43.Size = New Size(37, 15)
        Me.Label43.TabIndex = 3
        Me.Label43.Text = "흡입구"
        Me.Label43.UseMnemonic = False
        Me.Frame12.Controls.Add(Me.Label43)
        Me.txtU2 = New MTextBox()
        Me.txtU2.Name = "txtU2"
        Me.txtU2.Location = New Point(248, 36)
        Me.txtU2.AutoSize = False
        Me.txtU2.Size = New Size(108, 23)
        Me.txtU2.TabIndex = 4
        Me.txtU2.Multiline = True
        Me.txtU2.TextAlign = HorizontalAlignment.Center
        Me.Frame12.Controls.Add(Me.txtU2)
        Me.Label44 = New MLabel()
        Me.Label44.Name = "Label44"
        Me.Label44.Location = New Point(200, 40)
        Me.Label44.Size = New Size(37, 15)
        Me.Label44.TabIndex = 5
        Me.Label44.Text = "주속도"
        Me.Label44.UseMnemonic = False
        Me.Frame12.Controls.Add(Me.Label44)
        Me.txtDischarge = New MTextBox()
        Me.txtDischarge.Name = "txtDischarge"
        Me.txtDischarge.Location = New Point(248, 64)
        Me.txtDischarge.AutoSize = False
        Me.txtDischarge.Size = New Size(108, 23)
        Me.txtDischarge.TabIndex = 6
        Me.txtDischarge.Multiline = True
        Me.txtDischarge.TextAlign = HorizontalAlignment.Center
        Me.Frame12.Controls.Add(Me.txtDischarge)
        Me.Label45 = New MLabel()
        Me.Label45.Name = "Label45"
        Me.Label45.Location = New Point(200, 68)
        Me.Label45.Size = New Size(37, 15)
        Me.Label45.TabIndex = 7
        Me.Label45.Text = "토출구"
        Me.Label45.UseMnemonic = False
        Me.Frame12.Controls.Add(Me.Label45)
        Me.Label46 = New MLabel()
        Me.Label46.Name = "Label46"
        Me.Label46.Location = New Point(224, 12)
        Me.Label46.Size = New Size(12, 15)
        Me.Label46.TabIndex = 8
        Me.Label46.Text = "→"
        Me.Label46.UseMnemonic = False
        Me.Frame12.Controls.Add(Me.Label46)
        Me.Label47 = New MLabel()
        Me.Label47.Name = "Label47"
        Me.Label47.Location = New Point(8, 12)
        Me.Label47.Size = New Size(89, 15)
        Me.Label47.TabIndex = 9
        Me.Label47.Text = "베어링 수명시간"
        Me.Label47.UseMnemonic = False
        Me.Frame12.Controls.Add(Me.Label47)
        Me.txtBearingLifeTimeHr = New MTextBox()
        Me.txtBearingLifeTimeHr.Name = "txtBearingLifeTimeHr"
        Me.txtBearingLifeTimeHr.Location = New Point(108, 8)
        Me.txtBearingLifeTimeHr.AutoSize = False
        Me.txtBearingLifeTimeHr.Size = New Size(107, 23)
        Me.txtBearingLifeTimeHr.TabIndex = 10
        Me.txtBearingLifeTimeHr.Multiline = True
        Me.txtBearingLifeTimeHr.TextAlign = HorizontalAlignment.Center
        Me.Frame12.Controls.Add(Me.txtBearingLifeTimeHr)
        Me.txtBearingLifeTimeYear = New MTextBox()
        Me.txtBearingLifeTimeYear.Name = "txtBearingLifeTimeYear"
        Me.txtBearingLifeTimeYear.Location = New Point(248, 8)
        Me.txtBearingLifeTimeYear.AutoSize = False
        Me.txtBearingLifeTimeYear.Size = New Size(107, 23)
        Me.txtBearingLifeTimeYear.TabIndex = 11
        Me.txtBearingLifeTimeYear.Multiline = True
        Me.txtBearingLifeTimeYear.TextAlign = HorizontalAlignment.Center
        Me.Frame12.Controls.Add(Me.txtBearingLifeTimeYear)
        Me.Frame13 = New MFrame()
        Me.Frame13.Name = "Frame13"
        Me.Frame13.Location = New Point(8, 444)
        Me.Frame13.Size = New Size(760, 136)
        Me.Frame13.TabIndex = 6
        Me.Frame13.Text = "모터명세"
        Me.Controls.Add(Me.Frame13)
        Me.Label48 = New MLabel()
        Me.Label48.Name = "Label48"
        Me.Label48.Location = New Point(4, 16)
        Me.Label48.Size = New Size(37, 15)
        Me.Label48.TabIndex = 0
        Me.Label48.Text = "제작사"
        Me.Label48.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label48)
        Me.txtMMaker = New MTextBox()
        Me.txtMMaker.Name = "txtMMaker"
        Me.txtMMaker.Location = New Point(68, 12)
        Me.txtMMaker.AutoSize = False
        Me.txtMMaker.Size = New Size(92, 23)
        Me.txtMMaker.TabIndex = 1
        Me.txtMMaker.Multiline = True
        Me.txtMMaker.TextAlign = HorizontalAlignment.Center
        Me.txtMMaker.Text = "HICO"
        Me.Frame13.Controls.Add(Me.txtMMaker)
        Me.txtMrpm = New MTextBox()
        Me.txtMrpm.Name = "txtMrpm"
        Me.txtMrpm.Location = New Point(464, 12)
        Me.txtMrpm.AutoSize = False
        Me.txtMrpm.Size = New Size(92, 23)
        Me.txtMrpm.TabIndex = 2
        Me.txtMrpm.Multiline = True
        Me.txtMrpm.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMrpm)
        Me.Label49 = New MLabel()
        Me.Label49.Name = "Label49"
        Me.Label49.Location = New Point(400, 16)
        Me.Label49.Size = New Size(37, 15)
        Me.Label49.TabIndex = 3
        Me.Label49.Text = "회전수"
        Me.Label49.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label49)
        Me.txtMeff = New MTextBox()
        Me.txtMeff.Name = "txtMeff"
        Me.txtMeff.Location = New Point(464, 40)
        Me.txtMeff.AutoSize = False
        Me.txtMeff.Size = New Size(92, 23)
        Me.txtMeff.TabIndex = 4
        Me.txtMeff.Multiline = True
        Me.txtMeff.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMeff)
        Me.Label50 = New MLabel()
        Me.Label50.Name = "Label50"
        Me.Label50.Location = New Point(4, 44)
        Me.Label50.Size = New Size(25, 15)
        Me.Label50.TabIndex = 5
        Me.Label50.Text = "형식"
        Me.Label50.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label50)
        Me.txtMType = New MTextBox()
        Me.txtMType.Name = "txtMType"
        Me.txtMType.Location = New Point(68, 40)
        Me.txtMType.AutoSize = False
        Me.txtMType.Size = New Size(92, 23)
        Me.txtMType.TabIndex = 6
        Me.txtMType.Multiline = True
        Me.txtMType.TextAlign = HorizontalAlignment.Center
        Me.txtMType.Text = "TEFC"
        Me.Frame13.Controls.Add(Me.txtMType)
        Me.Label51 = New MLabel()
        Me.Label51.Name = "Label51"
        Me.Label51.Location = New Point(400, 44)
        Me.Label51.Size = New Size(25, 15)
        Me.Label51.TabIndex = 7
        Me.Label51.Text = "효율"
        Me.Label51.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label51)
        Me.txtMpf = New MTextBox()
        Me.txtMpf.Name = "txtMpf"
        Me.txtMpf.Location = New Point(464, 68)
        Me.txtMpf.AutoSize = False
        Me.txtMpf.Size = New Size(92, 23)
        Me.txtMpf.TabIndex = 8
        Me.txtMpf.Multiline = True
        Me.txtMpf.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMpf)
        Me.Label52 = New MLabel()
        Me.Label52.Name = "Label52"
        Me.Label52.Location = New Point(4, 72)
        Me.Label52.Size = New Size(49, 15)
        Me.Label52.TabIndex = 9
        Me.Label52.Text = "절연등급"
        Me.Label52.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label52)
        Me.txtMInsulGrade = New MTextBox()
        Me.txtMInsulGrade.Name = "txtMInsulGrade"
        Me.txtMInsulGrade.Location = New Point(68, 68)
        Me.txtMInsulGrade.AutoSize = False
        Me.txtMInsulGrade.Size = New Size(92, 23)
        Me.txtMInsulGrade.TabIndex = 10
        Me.txtMInsulGrade.Multiline = True
        Me.txtMInsulGrade.TextAlign = HorizontalAlignment.Center
        Me.txtMInsulGrade.Text = "B"
        Me.Frame13.Controls.Add(Me.txtMInsulGrade)
        Me.Label53 = New MLabel()
        Me.Label53.Name = "Label53"
        Me.Label53.Location = New Point(400, 72)
        Me.Label53.Size = New Size(25, 15)
        Me.Label53.TabIndex = 11
        Me.Label53.Text = "역율"
        Me.Label53.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label53)
        Me.Label54 = New MLabel()
        Me.Label54.Name = "Label54"
        Me.Label54.Location = New Point(592, 72)
        Me.Label54.Size = New Size(49, 15)
        Me.Label54.TabIndex = 12
        Me.Label54.Text = "모터중량"
        Me.Label54.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label54)
        Me.txtMphPoles = New MTextBox()
        Me.txtMphPoles.Name = "txtMphPoles"
        Me.txtMphPoles.Location = New Point(260, 12)
        Me.txtMphPoles.AutoSize = False
        Me.txtMphPoles.Size = New Size(92, 23)
        Me.txtMphPoles.TabIndex = 13
        Me.txtMphPoles.Multiline = True
        Me.txtMphPoles.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMphPoles)
        Me.Label55 = New MLabel()
        Me.Label55.Name = "Label55"
        Me.Label55.Location = New Point(196, 16)
        Me.Label55.Size = New Size(42, 15)
        Me.Label55.TabIndex = 14
        Me.Label55.Text = "상/극수"
        Me.Label55.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label55)
        Me.txtMStartAmp = New MTextBox()
        Me.txtMStartAmp.Name = "txtMStartAmp"
        Me.txtMStartAmp.Location = New Point(656, 12)
        Me.txtMStartAmp.AutoSize = False
        Me.txtMStartAmp.Size = New Size(92, 23)
        Me.txtMStartAmp.TabIndex = 15
        Me.txtMStartAmp.Multiline = True
        Me.txtMStartAmp.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMStartAmp)
        Me.Label56 = New MLabel()
        Me.Label56.Name = "Label56"
        Me.Label56.Location = New Point(592, 16)
        Me.Label56.Size = New Size(49, 15)
        Me.Label56.TabIndex = 16
        Me.Label56.Text = "기동전류"
        Me.Label56.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label56)
        Me.txtMGD2 = New MTextBox()
        Me.txtMGD2.Name = "txtMGD2"
        Me.txtMGD2.Location = New Point(656, 40)
        Me.txtMGD2.AutoSize = False
        Me.txtMGD2.Size = New Size(92, 23)
        Me.txtMGD2.TabIndex = 17
        Me.txtMGD2.Multiline = True
        Me.txtMGD2.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMGD2)
        Me.Label57 = New MLabel()
        Me.Label57.Name = "Label57"
        Me.Label57.Location = New Point(196, 44)
        Me.Label57.Size = New Size(37, 15)
        Me.Label57.TabIndex = 18
        Me.Label57.Text = "주파수"
        Me.Label57.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label57)
        Me.txtMFrequency = New MTextBox()
        Me.txtMFrequency.Name = "txtMFrequency"
        Me.txtMFrequency.Location = New Point(260, 40)
        Me.txtMFrequency.AutoSize = False
        Me.txtMFrequency.Size = New Size(92, 23)
        Me.txtMFrequency.TabIndex = 19
        Me.txtMFrequency.Multiline = True
        Me.txtMFrequency.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMFrequency)
        Me.Label58 = New MLabel()
        Me.Label58.Name = "Label58"
        Me.Label58.Location = New Point(592, 44)
        Me.Label58.Size = New Size(25, 15)
        Me.Label58.TabIndex = 20
        Me.Label58.Text = "GD2"
        Me.Label58.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label58)
        Me.txtMWeight = New MTextBox()
        Me.txtMWeight.Name = "txtMWeight"
        Me.txtMWeight.Location = New Point(656, 68)
        Me.txtMWeight.AutoSize = False
        Me.txtMWeight.Size = New Size(92, 23)
        Me.txtMWeight.TabIndex = 21
        Me.txtMWeight.Multiline = True
        Me.txtMWeight.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMWeight)
        Me.Label59 = New MLabel()
        Me.Label59.Name = "Label59"
        Me.Label59.Location = New Point(196, 72)
        Me.Label59.Size = New Size(25, 15)
        Me.Label59.TabIndex = 22
        Me.Label59.Text = "출력"
        Me.Label59.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label59)
        Me.txtMOutput = New MTextBox()
        Me.txtMOutput.Name = "txtMOutput"
        Me.txtMOutput.Location = New Point(260, 68)
        Me.txtMOutput.AutoSize = False
        Me.txtMOutput.Size = New Size(92, 23)
        Me.txtMOutput.TabIndex = 23
        Me.txtMOutput.Multiline = True
        Me.txtMOutput.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMOutput)
        Me.Label60 = New MLabel()
        Me.Label60.Name = "Label60"
        Me.Label60.Location = New Point(4, 100)
        Me.Label60.Size = New Size(25, 15)
        Me.Label60.TabIndex = 24
        Me.Label60.Text = "전압"
        Me.Label60.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label60)
        Me.txtMLoadAmp = New MTextBox()
        Me.txtMLoadAmp.Name = "txtMLoadAmp"
        Me.txtMLoadAmp.Location = New Point(464, 96)
        Me.txtMLoadAmp.AutoSize = False
        Me.txtMLoadAmp.Size = New Size(92, 23)
        Me.txtMLoadAmp.TabIndex = 25
        Me.txtMLoadAmp.Multiline = True
        Me.txtMLoadAmp.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMLoadAmp)
        Me.txtMVoltage = New MTextBox()
        Me.txtMVoltage.Name = "txtMVoltage"
        Me.txtMVoltage.Location = New Point(68, 96)
        Me.txtMVoltage.AutoSize = False
        Me.txtMVoltage.Size = New Size(92, 23)
        Me.txtMVoltage.TabIndex = 26
        Me.txtMVoltage.Multiline = True
        Me.txtMVoltage.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMVoltage)
        Me.Label61 = New MLabel()
        Me.Label61.Name = "Label61"
        Me.Label61.Location = New Point(400, 100)
        Me.Label61.Size = New Size(49, 15)
        Me.Label61.TabIndex = 27
        Me.Label61.Text = "부하전류"
        Me.Label61.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label61)
        Me.Label63 = New MLabel()
        Me.Label63.Name = "Label63"
        Me.Label63.Location = New Point(196, 100)
        Me.Label63.Size = New Size(37, 15)
        Me.Label63.TabIndex = 28
        Me.Label63.Text = "후렌임"
        Me.Label63.UseMnemonic = False
        Me.Frame13.Controls.Add(Me.Label63)
        Me.txtMFrame = New MTextBox()
        Me.txtMFrame.Name = "txtMFrame"
        Me.txtMFrame.Location = New Point(260, 96)
        Me.txtMFrame.AutoSize = False
        Me.txtMFrame.Size = New Size(92, 23)
        Me.txtMFrame.TabIndex = 29
        Me.txtMFrame.Multiline = True
        Me.txtMFrame.TextAlign = HorizontalAlignment.Center
        Me.Frame13.Controls.Add(Me.txtMFrame)
        Me.cmdRestart = New MCommandButton()
        Me.cmdRestart.Name = "cmdRestart"
        Me.cmdRestart.Location = New Point(8, 596)
        Me.cmdRestart.Size = New Size(107, 31)
        Me.cmdRestart.TabIndex = 7
        Me.cmdRestart.Text = "뒤로"
        Me.cmdRestart.UseMnemonic = False
        Me.cmdRestart.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdRestart)
        Me.cmdOut = New MCommandButton()
        Me.cmdOut.Name = "cmdOut"
        Me.cmdOut.Location = New Point(656, 596)
        Me.cmdOut.Size = New Size(107, 31)
        Me.cmdOut.TabIndex = 8
        Me.cmdOut.Text = "설계결과출력"
        Me.cmdOut.UseMnemonic = False
        Me.cmdOut.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdOut)
        Me.cmdEnd = New MCommandButton()
        Me.cmdEnd.Name = "cmdEnd"
        Me.cmdEnd.Location = New Point(120, 596)
        Me.cmdEnd.Size = New Size(107, 31)
        Me.cmdEnd.TabIndex = 9
        Me.cmdEnd.Text = "설계종료"
        Me.cmdEnd.UseMnemonic = False
        Me.cmdEnd.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdEnd)
        Me.ResumeLayout(False)
        Me.PerformLayout()
    End Sub
End Class
