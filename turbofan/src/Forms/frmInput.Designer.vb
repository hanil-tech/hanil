' 이 파일은 tools/vba2vb.py 가 원본 .dvb 의 폼 배치에서 만든다. 직접 고치지 말 것.
Imports System.Drawing
Imports System.Windows.Forms

Partial Class frmInput
    Inherits MForm

    Friend WithEvents Frame1 As MFrame
    Friend WithEvents txtCustomer As MTextBox
    Friend WithEvents Label1 As MLabel
    Friend WithEvents Label2 As MLabel
    Friend WithEvents lblDate As MLabel
    Friend WithEvents Frame2 As MFrame
    Friend WithEvents Label3 As MLabel
    Friend WithEvents txtQ As MTextBox
    Friend WithEvents txtPs As MTextBox
    Friend WithEvents txtTemp As MTextBox
    Friend WithEvents Label4 As MLabel
    Friend WithEvents Label5 As MLabel
    Friend WithEvents Label6 As MLabel
    Friend WithEvents Label7 As MLabel
    Friend WithEvents Label8 As MLabel
    Friend WithEvents Label9 As MLabel
    Friend WithEvents Label11 As MLabel
    Friend WithEvents txtDensity As MTextBox
    Friend WithEvents Frame3 As MFrame
    Friend WithEvents lblMessage As MLabel
    Friend WithEvents Frame4 As MFrame
    Friend WithEvents Frame5 As MFrame
    Friend WithEvents txtN_1 As MTextBox
    Friend WithEvents txtD2_1 As MTextBox
    Friend WithEvents txtNs_1 As MTextBox
    Friend WithEvents cmdNsOk_1 As MCommandButton
    Friend WithEvents txtD2no_1 As MTextBox
    Friend WithEvents Label12 As MLabel
    Friend WithEvents Label13 As MLabel
    Friend WithEvents Label14 As MLabel
    Friend WithEvents Label15 As MLabel
    Friend WithEvents Frame6 As MFrame
    Friend WithEvents txtN_2 As MTextBox
    Friend WithEvents txtD2_2 As MTextBox
    Friend WithEvents txtNs_2 As MTextBox
    Friend WithEvents cmdNsOk_2 As MCommandButton
    Friend WithEvents txtD2no_2 As MTextBox
    Friend WithEvents Frame7 As MFrame
    Friend WithEvents Label16 As MLabel
    Friend WithEvents Label17 As MLabel
    Friend WithEvents Label18 As MLabel
    Friend WithEvents Label19 As MLabel
    Friend WithEvents Label20 As MLabel
    Friend WithEvents txtBladeNo As MTextBox
    Friend WithEvents txtBladeThickness As MTextBox
    Friend WithEvents cboBladeMaterial As MComboBox
    Friend WithEvents Frame8 As MFrame
    Friend WithEvents optVbelt As MOptionButton
    Friend WithEvents optDirect As MOptionButton
    Friend WithEvents Frame9 As MFrame
    Friend WithEvents Label21 As MLabel
    Friend WithEvents Label22 As MLabel
    Friend WithEvents Label23 As MLabel
    Friend WithEvents Label24 As MLabel
    Friend WithEvents Label25 As MLabel
    Friend WithEvents Label26 As MLabel
    Friend WithEvents cboMotorOutput As MComboBox
    Friend WithEvents cboMotorVoltage As MComboBox
    Friend WithEvents cboMotorPoles As MComboBox
    Friend WithEvents Frame10 As MFrame
    Friend WithEvents Label27 As MLabel
    Friend WithEvents Frame11 As MFrame
    Friend WithEvents optCW As MOptionButton
    Friend WithEvents optCCW As MOptionButton
    Friend WithEvents Frame12 As MFrame
    Friend WithEvents optUp As MOptionButton
    Friend WithEvents optLeft As MOptionButton
    Friend WithEvents optRight As MOptionButton
    Friend WithEvents Frame13 As MFrame
    Friend WithEvents optMLeft As MOptionButton
    Friend WithEvents optMRight As MOptionButton
    Friend WithEvents imgFan As MImage
    Friend WithEvents cmdRedesign As MCommandButton
    Friend WithEvents cmdEnd As MCommandButton
    Friend WithEvents cmdDesign As MCommandButton
    Friend WithEvents Image1 As MImage

    Private Sub InitializeComponent()
        Me.SuspendLayout()
        Me.AutoScaleMode = AutoScaleMode.Dpi
        Me.AutoScaleDimensions = New SizeF(96.0F, 96.0F)
        Me.Font = New Font("맑은 고딕", 9F)
        Me.ClientSize = New Size(643, 446)
        Me.Text = "Turbo Fan Design"
        Me.Name = "frmInput"
        Me.Frame1 = New MFrame()
        Me.Frame1.Name = "Frame1"
        Me.Frame1.Location = New Point(128, 12)
        Me.Frame1.Size = New Size(392, 40)
        Me.Frame1.TabIndex = 0
        Me.Frame1.Text = ""
        Me.Controls.Add(Me.Frame1)
        Me.txtCustomer = New MTextBox()
        Me.txtCustomer.Name = "txtCustomer"
        Me.txtCustomer.Location = New Point(52, 8)
        Me.txtCustomer.AutoSize = False
        Me.txtCustomer.Size = New Size(156, 23)
        Me.txtCustomer.TabIndex = 0
        Me.txtCustomer.Multiline = True
        Me.txtCustomer.Text = "(주)에코솔루텍"
        Me.Frame1.Controls.Add(Me.txtCustomer)
        Me.Label1 = New MLabel()
        Me.Label1.Name = "Label1"
        Me.Label1.Location = New Point(8, 12)
        Me.Label1.Size = New Size(37, 15)
        Me.Label1.TabIndex = 1
        Me.Label1.Text = "고객명"
        Me.Label1.UseMnemonic = False
        Me.Frame1.Controls.Add(Me.Label1)
        Me.Label2 = New MLabel()
        Me.Label2.Name = "Label2"
        Me.Label2.Location = New Point(216, 12)
        Me.Label2.Size = New Size(56, 15)
        Me.Label2.TabIndex = 2
        Me.Label2.Text = "설계일자 :"
        Me.Label2.UseMnemonic = False
        Me.Frame1.Controls.Add(Me.Label2)
        Me.lblDate = New MLabel()
        Me.lblDate.Name = "lblDate"
        Me.lblDate.Location = New Point(276, 12)
        Me.lblDate.Size = New Size(108, 15)
        Me.lblDate.TabIndex = 3
        Me.lblDate.Text = ""
        Me.lblDate.UseMnemonic = False
        Me.Frame1.Controls.Add(Me.lblDate)
        Me.Frame2 = New MFrame()
        Me.Frame2.Name = "Frame2"
        Me.Frame2.Location = New Point(128, 56)
        Me.Frame2.Size = New Size(392, 68)
        Me.Frame2.TabIndex = 1
        Me.Frame2.Text = ""
        Me.Controls.Add(Me.Frame2)
        Me.Label3 = New MLabel()
        Me.Label3.Name = "Label3"
        Me.Label3.Location = New Point(16, 12)
        Me.Label3.Size = New Size(25, 15)
        Me.Label3.TabIndex = 0
        Me.Label3.Text = "풍량"
        Me.Label3.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label3)
        Me.txtQ = New MTextBox()
        Me.txtQ.Name = "txtQ"
        Me.txtQ.Location = New Point(52, 8)
        Me.txtQ.AutoSize = False
        Me.txtQ.Size = New Size(53, 23)
        Me.txtQ.TabIndex = 1
        Me.txtQ.Multiline = True
        Me.txtQ.TextAlign = HorizontalAlignment.Right
        Me.Frame2.Controls.Add(Me.txtQ)
        Me.txtPs = New MTextBox()
        Me.txtPs.Name = "txtPs"
        Me.txtPs.Location = New Point(252, 8)
        Me.txtPs.AutoSize = False
        Me.txtPs.Size = New Size(53, 23)
        Me.txtPs.TabIndex = 2
        Me.txtPs.Multiline = True
        Me.txtPs.TextAlign = HorizontalAlignment.Right
        Me.Frame2.Controls.Add(Me.txtPs)
        Me.txtTemp = New MTextBox()
        Me.txtTemp.Name = "txtTemp"
        Me.txtTemp.Location = New Point(52, 36)
        Me.txtTemp.AutoSize = False
        Me.txtTemp.Size = New Size(53, 23)
        Me.txtTemp.TabIndex = 3
        Me.txtTemp.Multiline = True
        Me.txtTemp.TextAlign = HorizontalAlignment.Right
        Me.txtTemp.Text = "25"
        Me.Frame2.Controls.Add(Me.txtTemp)
        Me.Label4 = New MLabel()
        Me.Label4.Name = "Label4"
        Me.Label4.Location = New Point(112, 12)
        Me.Label4.Size = New Size(45, 15)
        Me.Label4.TabIndex = 4
        Me.Label4.Text = "m3/min"
        Me.Label4.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label4)
        Me.Label5 = New MLabel()
        Me.Label5.Name = "Label5"
        Me.Label5.Location = New Point(204, 12)
        Me.Label5.Size = New Size(25, 15)
        Me.Label5.TabIndex = 5
        Me.Label5.Text = "정압"
        Me.Label5.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label5)
        Me.Label6 = New MLabel()
        Me.Label6.Name = "Label6"
        Me.Label6.Location = New Point(320, 12)
        Me.Label6.Size = New Size(38, 15)
        Me.Label6.TabIndex = 6
        Me.Label6.Text = "mmAq"
        Me.Label6.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label6)
        Me.Label7 = New MLabel()
        Me.Label7.Name = "Label7"
        Me.Label7.Location = New Point(112, 40)
        Me.Label7.Size = New Size(12, 15)
        Me.Label7.TabIndex = 7
        Me.Label7.Text = "℃"
        Me.Label7.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label7)
        Me.Label8 = New MLabel()
        Me.Label8.Name = "Label8"
        Me.Label8.Location = New Point(16, 40)
        Me.Label8.Size = New Size(25, 15)
        Me.Label8.TabIndex = 8
        Me.Label8.Text = "온도"
        Me.Label8.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label8)
        Me.Label9 = New MLabel()
        Me.Label9.Name = "Label9"
        Me.Label9.Location = New Point(200, 40)
        Me.Label9.Size = New Size(39, 15)
        Me.Label9.TabIndex = 9
        Me.Label9.Text = "밀도(γ)"
        Me.Label9.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label9)
        Me.Label11 = New MLabel()
        Me.Label11.Name = "Label11"
        Me.Label11.Location = New Point(320, 40)
        Me.Label11.Size = New Size(41, 15)
        Me.Label11.TabIndex = 10
        Me.Label11.Text = "kgf/m3"
        Me.Label11.UseMnemonic = False
        Me.Frame2.Controls.Add(Me.Label11)
        Me.txtDensity = New MTextBox()
        Me.txtDensity.Name = "txtDensity"
        Me.txtDensity.Location = New Point(252, 36)
        Me.txtDensity.AutoSize = False
        Me.txtDensity.Size = New Size(53, 23)
        Me.txtDensity.TabIndex = 11
        Me.txtDensity.Enabled = False
        Me.txtDensity.Multiline = True
        Me.txtDensity.TextAlign = HorizontalAlignment.Right
        Me.txtDensity.Text = "1.18"
        Me.Frame2.Controls.Add(Me.txtDensity)
        Me.Frame3 = New MFrame()
        Me.Frame3.Name = "Frame3"
        Me.Frame3.Location = New Point(8, 128)
        Me.Frame3.Size = New Size(116, 260)
        Me.Frame3.TabIndex = 2
        Me.Frame3.Text = "메세지 박스"
        Me.Controls.Add(Me.Frame3)
        Me.lblMessage = New MLabel()
        Me.lblMessage.Name = "lblMessage"
        Me.lblMessage.Location = New Point(8, 16)
        Me.lblMessage.Size = New Size(96, 224)
        Me.lblMessage.TabIndex = 0
        Me.lblMessage.Text = ""
        Me.lblMessage.UseMnemonic = False
        Me.Frame3.Controls.Add(Me.lblMessage)
        Me.Frame4 = New MFrame()
        Me.Frame4.Name = "Frame4"
        Me.Frame4.Location = New Point(128, 128)
        Me.Frame4.Size = New Size(260, 208)
        Me.Frame4.TabIndex = 3
        Me.Frame4.Text = "예비설계"
        Me.Controls.Add(Me.Frame4)
        Me.Frame5 = New MFrame()
        Me.Frame5.Name = "Frame5"
        Me.Frame5.Location = New Point(104, 12)
        Me.Frame5.Size = New Size(72, 176)
        Me.Frame5.TabIndex = 0
        Me.Frame5.Text = "설계 #1"
        Me.Frame4.Controls.Add(Me.Frame5)
        Me.txtN_1 = New MTextBox()
        Me.txtN_1.Name = "txtN_1"
        Me.txtN_1.Location = New Point(8, 40)
        Me.txtN_1.AutoSize = False
        Me.txtN_1.Size = New Size(53, 23)
        Me.txtN_1.TabIndex = 0
        Me.txtN_1.Enabled = False
        Me.txtN_1.Multiline = True
        Me.txtN_1.TextAlign = HorizontalAlignment.Center
        Me.Frame5.Controls.Add(Me.txtN_1)
        Me.txtD2_1 = New MTextBox()
        Me.txtD2_1.Name = "txtD2_1"
        Me.txtD2_1.Location = New Point(8, 68)
        Me.txtD2_1.AutoSize = False
        Me.txtD2_1.Size = New Size(53, 23)
        Me.txtD2_1.TabIndex = 1
        Me.txtD2_1.Enabled = False
        Me.txtD2_1.Multiline = True
        Me.txtD2_1.TextAlign = HorizontalAlignment.Center
        Me.Frame5.Controls.Add(Me.txtD2_1)
        Me.txtNs_1 = New MTextBox()
        Me.txtNs_1.Name = "txtNs_1"
        Me.txtNs_1.Location = New Point(8, 96)
        Me.txtNs_1.AutoSize = False
        Me.txtNs_1.Size = New Size(53, 23)
        Me.txtNs_1.TabIndex = 2
        Me.txtNs_1.Enabled = False
        Me.txtNs_1.Multiline = True
        Me.txtNs_1.TextAlign = HorizontalAlignment.Center
        Me.Frame5.Controls.Add(Me.txtNs_1)
        Me.cmdNsOk_1 = New MCommandButton()
        Me.cmdNsOk_1.Name = "cmdNsOk_1"
        Me.cmdNsOk_1.Location = New Point(8, 128)
        Me.cmdNsOk_1.Size = New Size(53, 31)
        Me.cmdNsOk_1.TabIndex = 3
        Me.cmdNsOk_1.Enabled = False
        Me.cmdNsOk_1.Text = "선택"
        Me.cmdNsOk_1.UseMnemonic = False
        Me.cmdNsOk_1.UseVisualStyleBackColor = True
        Me.Frame5.Controls.Add(Me.cmdNsOk_1)
        Me.txtD2no_1 = New MTextBox()
        Me.txtD2no_1.Name = "txtD2no_1"
        Me.txtD2no_1.Location = New Point(8, 12)
        Me.txtD2no_1.AutoSize = False
        Me.txtD2no_1.Size = New Size(53, 23)
        Me.txtD2no_1.TabIndex = 4
        Me.txtD2no_1.Multiline = True
        Me.txtD2no_1.TextAlign = HorizontalAlignment.Center
        Me.Frame5.Controls.Add(Me.txtD2no_1)
        Me.Label12 = New MLabel()
        Me.Label12.Name = "Label12"
        Me.Label12.Location = New Point(10, 120)
        Me.Label12.Size = New Size(87, 15)
        Me.Label12.TabIndex = 1
        Me.Label12.Text = "비교회전도 (Ns)"
        Me.Label12.UseMnemonic = False
        Me.Frame4.Controls.Add(Me.Label12)
        Me.Label13 = New MLabel()
        Me.Label13.Name = "Label13"
        Me.Label13.Location = New Point(39, 64)
        Me.Label13.Size = New Size(58, 15)
        Me.Label13.TabIndex = 2
        Me.Label13.Text = "회전수 (N)"
        Me.Label13.UseMnemonic = False
        Me.Frame4.Controls.Add(Me.Label13)
        Me.Label14 = New MLabel()
        Me.Label14.Name = "Label14"
        Me.Label14.Location = New Point(4, 92)
        Me.Label14.Size = New Size(93, 15)
        Me.Label14.TabIndex = 3
        Me.Label14.Text = "회전차 외경 (D2)"
        Me.Label14.UseMnemonic = False
        Me.Frame4.Controls.Add(Me.Label14)
        Me.Label15 = New MLabel()
        Me.Label15.Name = "Label15"
        Me.Label15.Location = New Point(13, 36)
        Me.Label15.Size = New Size(84, 15)
        Me.Label15.TabIndex = 4
        Me.Label15.Text = "회전차 번호 (#)"
        Me.Label15.UseMnemonic = False
        Me.Frame4.Controls.Add(Me.Label15)
        Me.Frame6 = New MFrame()
        Me.Frame6.Name = "Frame6"
        Me.Frame6.Location = New Point(180, 12)
        Me.Frame6.Size = New Size(72, 176)
        Me.Frame6.TabIndex = 5
        Me.Frame6.Text = "설계 #2"
        Me.Frame4.Controls.Add(Me.Frame6)
        Me.txtN_2 = New MTextBox()
        Me.txtN_2.Name = "txtN_2"
        Me.txtN_2.Location = New Point(8, 40)
        Me.txtN_2.AutoSize = False
        Me.txtN_2.Size = New Size(53, 23)
        Me.txtN_2.TabIndex = 0
        Me.txtN_2.Enabled = False
        Me.txtN_2.Multiline = True
        Me.txtN_2.TextAlign = HorizontalAlignment.Center
        Me.Frame6.Controls.Add(Me.txtN_2)
        Me.txtD2_2 = New MTextBox()
        Me.txtD2_2.Name = "txtD2_2"
        Me.txtD2_2.Location = New Point(8, 68)
        Me.txtD2_2.AutoSize = False
        Me.txtD2_2.Size = New Size(53, 23)
        Me.txtD2_2.TabIndex = 1
        Me.txtD2_2.Enabled = False
        Me.txtD2_2.Multiline = True
        Me.txtD2_2.TextAlign = HorizontalAlignment.Center
        Me.Frame6.Controls.Add(Me.txtD2_2)
        Me.txtNs_2 = New MTextBox()
        Me.txtNs_2.Name = "txtNs_2"
        Me.txtNs_2.Location = New Point(8, 96)
        Me.txtNs_2.AutoSize = False
        Me.txtNs_2.Size = New Size(53, 23)
        Me.txtNs_2.TabIndex = 2
        Me.txtNs_2.Enabled = False
        Me.txtNs_2.Multiline = True
        Me.txtNs_2.TextAlign = HorizontalAlignment.Center
        Me.Frame6.Controls.Add(Me.txtNs_2)
        Me.cmdNsOk_2 = New MCommandButton()
        Me.cmdNsOk_2.Name = "cmdNsOk_2"
        Me.cmdNsOk_2.Location = New Point(8, 128)
        Me.cmdNsOk_2.Size = New Size(53, 31)
        Me.cmdNsOk_2.TabIndex = 3
        Me.cmdNsOk_2.Enabled = False
        Me.cmdNsOk_2.Text = "선택"
        Me.cmdNsOk_2.UseMnemonic = False
        Me.cmdNsOk_2.UseVisualStyleBackColor = True
        Me.Frame6.Controls.Add(Me.cmdNsOk_2)
        Me.txtD2no_2 = New MTextBox()
        Me.txtD2no_2.Name = "txtD2no_2"
        Me.txtD2no_2.Location = New Point(8, 12)
        Me.txtD2no_2.AutoSize = False
        Me.txtD2no_2.Size = New Size(53, 23)
        Me.txtD2no_2.TabIndex = 4
        Me.txtD2no_2.Multiline = True
        Me.txtD2no_2.TextAlign = HorizontalAlignment.Center
        Me.Frame6.Controls.Add(Me.txtD2no_2)
        Me.Frame7 = New MFrame()
        Me.Frame7.Name = "Frame7"
        Me.Frame7.Location = New Point(392, 128)
        Me.Frame7.Size = New Size(128, 132)
        Me.Frame7.TabIndex = 4
        Me.Frame7.Text = "날개"
        Me.Controls.Add(Me.Frame7)
        Me.Label16 = New MLabel()
        Me.Label16.Name = "Label16"
        Me.Label16.Location = New Point(4, 20)
        Me.Label16.Size = New Size(37, 15)
        Me.Label16.TabIndex = 0
        Me.Label16.Text = "날개수"
        Me.Label16.UseMnemonic = False
        Me.Frame7.Controls.Add(Me.Label16)
        Me.Label17 = New MLabel()
        Me.Label17.Name = "Label17"
        Me.Label17.Location = New Point(96, 20)
        Me.Label17.Size = New Size(15, 15)
        Me.Label17.TabIndex = 1
        Me.Label17.Text = "EA"
        Me.Label17.UseMnemonic = False
        Me.Frame7.Controls.Add(Me.Label17)
        Me.Label18 = New MLabel()
        Me.Label18.Name = "Label18"
        Me.Label18.Location = New Point(4, 48)
        Me.Label18.Size = New Size(49, 15)
        Me.Label18.TabIndex = 2
        Me.Label18.Text = "날개두께"
        Me.Label18.UseMnemonic = False
        Me.Frame7.Controls.Add(Me.Label18)
        Me.Label19 = New MLabel()
        Me.Label19.Name = "Label19"
        Me.Label19.Location = New Point(96, 48)
        Me.Label19.Size = New Size(23, 15)
        Me.Label19.TabIndex = 3
        Me.Label19.Text = "mm"
        Me.Label19.UseMnemonic = False
        Me.Frame7.Controls.Add(Me.Label19)
        Me.Label20 = New MLabel()
        Me.Label20.Name = "Label20"
        Me.Label20.Location = New Point(4, 72)
        Me.Label20.Size = New Size(49, 15)
        Me.Label20.TabIndex = 4
        Me.Label20.Text = "날개재질"
        Me.Label20.UseMnemonic = False
        Me.Frame7.Controls.Add(Me.Label20)
        Me.txtBladeNo = New MTextBox()
        Me.txtBladeNo.Name = "txtBladeNo"
        Me.txtBladeNo.Location = New Point(56, 16)
        Me.txtBladeNo.AutoSize = False
        Me.txtBladeNo.Size = New Size(36, 23)
        Me.txtBladeNo.TabIndex = 5
        Me.txtBladeNo.Multiline = True
        Me.txtBladeNo.TextAlign = HorizontalAlignment.Center
        Me.Frame7.Controls.Add(Me.txtBladeNo)
        Me.txtBladeThickness = New MTextBox()
        Me.txtBladeThickness.Name = "txtBladeThickness"
        Me.txtBladeThickness.Location = New Point(56, 44)
        Me.txtBladeThickness.AutoSize = False
        Me.txtBladeThickness.Size = New Size(36, 23)
        Me.txtBladeThickness.TabIndex = 6
        Me.txtBladeThickness.Multiline = True
        Me.txtBladeThickness.TextAlign = HorizontalAlignment.Center
        Me.Frame7.Controls.Add(Me.txtBladeThickness)
        Me.cboBladeMaterial = New MComboBox()
        Me.cboBladeMaterial.Name = "cboBladeMaterial"
        Me.cboBladeMaterial.Location = New Point(8, 92)
        Me.cboBladeMaterial.DropDownStyle = ComboBoxStyle.DropDown
        Me.cboBladeMaterial.IntegralHeight = False
        Me.cboBladeMaterial.MaxDropDownItems = 12
        Me.cboBladeMaterial.Size = New Size(108, 23)
        Me.cboBladeMaterial.TabIndex = 7
        Me.cboBladeMaterial.Text = "F.R.P"
        Me.Frame7.Controls.Add(Me.cboBladeMaterial)
        Me.Frame8 = New MFrame()
        Me.Frame8.Name = "Frame8"
        Me.Frame8.Location = New Point(392, 264)
        Me.Frame8.Size = New Size(128, 72)
        Me.Frame8.TabIndex = 5
        Me.Frame8.Text = "전동방식"
        Me.Controls.Add(Me.Frame8)
        Me.optVbelt = New MOptionButton()
        Me.optVbelt.Name = "optVbelt"
        Me.optVbelt.Location = New Point(12, 8)
        Me.optVbelt.Size = New Size(64, 25)
        Me.optVbelt.TabIndex = 0
        Me.optVbelt.Text = "V-벨트"
        Me.optVbelt.Checked = True
        Me.Frame8.Controls.Add(Me.optVbelt)
        Me.optDirect = New MOptionButton()
        Me.optDirect.Name = "optDirect"
        Me.optDirect.Location = New Point(12, 32)
        Me.optDirect.Size = New Size(75, 25)
        Me.optDirect.TabIndex = 1
        Me.optDirect.Text = "모터직결"
        Me.Frame8.Controls.Add(Me.optDirect)
        Me.Frame9 = New MFrame()
        Me.Frame9.Name = "Frame9"
        Me.Frame9.Location = New Point(128, 340)
        Me.Frame9.Size = New Size(388, 48)
        Me.Frame9.TabIndex = 6
        Me.Frame9.Text = "모터선정"
        Me.Controls.Add(Me.Frame9)
        Me.Label21 = New MLabel()
        Me.Label21.Name = "Label21"
        Me.Label21.Location = New Point(8, 12)
        Me.Label21.Size = New Size(25, 15)
        Me.Label21.TabIndex = 0
        Me.Label21.Text = "출력"
        Me.Label21.UseMnemonic = False
        Me.Frame9.Controls.Add(Me.Label21)
        Me.Label22 = New MLabel()
        Me.Label22.Name = "Label22"
        Me.Label22.Location = New Point(108, 12)
        Me.Label22.Size = New Size(18, 15)
        Me.Label22.TabIndex = 1
        Me.Label22.Text = "kW"
        Me.Label22.UseMnemonic = False
        Me.Frame9.Controls.Add(Me.Label22)
        Me.Label23 = New MLabel()
        Me.Label23.Name = "Label23"
        Me.Label23.Location = New Point(140, 12)
        Me.Label23.Size = New Size(25, 15)
        Me.Label23.TabIndex = 2
        Me.Label23.Text = "전압"
        Me.Label23.UseMnemonic = False
        Me.Frame9.Controls.Add(Me.Label23)
        Me.Label24 = New MLabel()
        Me.Label24.Name = "Label24"
        Me.Label24.Location = New Point(240, 12)
        Me.Label24.Size = New Size(9, 15)
        Me.Label24.TabIndex = 3
        Me.Label24.Text = "V"
        Me.Label24.UseMnemonic = False
        Me.Frame9.Controls.Add(Me.Label24)
        Me.Label25 = New MLabel()
        Me.Label25.Name = "Label25"
        Me.Label25.Location = New Point(264, 12)
        Me.Label25.Size = New Size(25, 15)
        Me.Label25.TabIndex = 4
        Me.Label25.Text = "극수"
        Me.Label25.UseMnemonic = False
        Me.Frame9.Controls.Add(Me.Label25)
        Me.Label26 = New MLabel()
        Me.Label26.Name = "Label26"
        Me.Label26.Location = New Point(364, 12)
        Me.Label26.Size = New Size(8, 15)
        Me.Label26.TabIndex = 5
        Me.Label26.Text = "P"
        Me.Label26.UseMnemonic = False
        Me.Frame9.Controls.Add(Me.Label26)
        Me.cboMotorOutput = New MComboBox()
        Me.cboMotorOutput.Name = "cboMotorOutput"
        Me.cboMotorOutput.Location = New Point(40, 8)
        Me.cboMotorOutput.DropDownStyle = ComboBoxStyle.DropDown
        Me.cboMotorOutput.IntegralHeight = False
        Me.cboMotorOutput.MaxDropDownItems = 12
        Me.cboMotorOutput.Size = New Size(64, 23)
        Me.cboMotorOutput.TabIndex = 6
        Me.cboMotorOutput.Text = "3.7"
        Me.Frame9.Controls.Add(Me.cboMotorOutput)
        Me.cboMotorVoltage = New MComboBox()
        Me.cboMotorVoltage.Name = "cboMotorVoltage"
        Me.cboMotorVoltage.Location = New Point(172, 8)
        Me.cboMotorVoltage.DropDownStyle = ComboBoxStyle.DropDown
        Me.cboMotorVoltage.IntegralHeight = False
        Me.cboMotorVoltage.MaxDropDownItems = 12
        Me.cboMotorVoltage.Size = New Size(64, 23)
        Me.cboMotorVoltage.TabIndex = 7
        Me.cboMotorVoltage.Text = "380"
        Me.Frame9.Controls.Add(Me.cboMotorVoltage)
        Me.cboMotorPoles = New MComboBox()
        Me.cboMotorPoles.Name = "cboMotorPoles"
        Me.cboMotorPoles.Location = New Point(296, 8)
        Me.cboMotorPoles.DropDownStyle = ComboBoxStyle.DropDown
        Me.cboMotorPoles.IntegralHeight = False
        Me.cboMotorPoles.MaxDropDownItems = 12
        Me.cboMotorPoles.Size = New Size(64, 23)
        Me.cboMotorPoles.TabIndex = 8
        Me.cboMotorPoles.Text = "4"
        Me.Frame9.Controls.Add(Me.cboMotorPoles)
        Me.Frame10 = New MFrame()
        Me.Frame10.Name = "Frame10"
        Me.Frame10.Location = New Point(528, 12)
        Me.Frame10.Size = New Size(108, 376)
        Me.Frame10.TabIndex = 7
        Me.Frame10.Text = "회전 및 방향"
        Me.Controls.Add(Me.Frame10)
        Me.Label27 = New MLabel()
        Me.Label27.Name = "Label27"
        Me.Label27.Location = New Point(8, 84)
        Me.Label27.Size = New Size(86, 13)
        Me.Label27.TabIndex = 0
        Me.Label27.Font = New Font("맑은 고딕", 8.25F)
        Me.Label27.ForeColor = SystemColors.GrayText
        Me.Label27.Text = "흡입구에서 볼 때"
        Me.Label27.UseMnemonic = False
        Me.Label27.TextAlign = ContentAlignment.TopCenter
        Me.Frame10.Controls.Add(Me.Label27)
        Me.Frame11 = New MFrame()
        Me.Frame11.Name = "Frame11"
        Me.Frame11.Location = New Point(4, 104)
        Me.Frame11.Size = New Size(96, 72)
        Me.Frame11.TabIndex = 1
        Me.Frame11.Text = "회전방향"
        Me.Frame10.Controls.Add(Me.Frame11)
        Me.optCW = New MOptionButton()
        Me.optCW.Name = "optCW"
        Me.optCW.Location = New Point(4, 8)
        Me.optCW.Size = New Size(75, 25)
        Me.optCW.TabIndex = 0
        Me.optCW.Text = "시계방향"
        Me.optCW.Checked = True
        Me.Frame11.Controls.Add(Me.optCW)
        Me.optCCW = New MOptionButton()
        Me.optCCW.Name = "optCCW"
        Me.optCCW.Location = New Point(4, 32)
        Me.optCCW.Size = New Size(87, 25)
        Me.optCCW.TabIndex = 1
        Me.optCCW.Text = "반시계방향"
        Me.Frame11.Controls.Add(Me.optCCW)
        Me.Frame12 = New MFrame()
        Me.Frame12.Name = "Frame12"
        Me.Frame12.Location = New Point(4, 184)
        Me.Frame12.Size = New Size(96, 96)
        Me.Frame12.TabIndex = 2
        Me.Frame12.Text = "토출방향"
        Me.Frame10.Controls.Add(Me.Frame12)
        Me.optUp = New MOptionButton()
        Me.optUp.Name = "optUp"
        Me.optUp.Location = New Point(4, 8)
        Me.optUp.Size = New Size(51, 25)
        Me.optUp.TabIndex = 0
        Me.optUp.Text = "상부"
        Me.optUp.Checked = True
        Me.Frame12.Controls.Add(Me.optUp)
        Me.optLeft = New MOptionButton()
        Me.optLeft.Name = "optLeft"
        Me.optLeft.Location = New Point(4, 32)
        Me.optLeft.Size = New Size(51, 25)
        Me.optLeft.TabIndex = 1
        Me.optLeft.Text = "좌측"
        Me.Frame12.Controls.Add(Me.optLeft)
        Me.optRight = New MOptionButton()
        Me.optRight.Name = "optRight"
        Me.optRight.Location = New Point(4, 56)
        Me.optRight.Size = New Size(51, 25)
        Me.optRight.TabIndex = 2
        Me.optRight.Text = "우측"
        Me.Frame12.Controls.Add(Me.optRight)
        Me.Frame13 = New MFrame()
        Me.Frame13.Name = "Frame13"
        Me.Frame13.Location = New Point(4, 288)
        Me.Frame13.Size = New Size(96, 72)
        Me.Frame13.TabIndex = 3
        Me.Frame13.Text = "모터위치"
        Me.Frame10.Controls.Add(Me.Frame13)
        Me.optMLeft = New MOptionButton()
        Me.optMLeft.Name = "optMLeft"
        Me.optMLeft.Location = New Point(4, 8)
        Me.optMLeft.Size = New Size(51, 25)
        Me.optMLeft.TabIndex = 0
        Me.optMLeft.Text = "좌측"
        Me.optMLeft.Checked = True
        Me.Frame13.Controls.Add(Me.optMLeft)
        Me.optMRight = New MOptionButton()
        Me.optMRight.Name = "optMRight"
        Me.optMRight.Location = New Point(4, 32)
        Me.optMRight.Size = New Size(51, 25)
        Me.optMRight.TabIndex = 1
        Me.optMRight.Text = "우측"
        Me.Frame13.Controls.Add(Me.optMRight)
        Me.imgFan = New MImage()
        Me.imgFan.Name = "imgFan"
        Me.imgFan.Location = New Point(9, 12)
        Me.imgFan.Size = New Size(85, 69)
        Me.imgFan.TabIndex = 4
        Me.imgFan.SizeMode = PictureBoxSizeMode.CenterImage
        Me.imgFan.BorderStyle = BorderStyle.FixedSingle
        Me.imgFan.Image = LoadResourceImage("frmInput_imgFan")
        Me.Frame10.Controls.Add(Me.imgFan)
        Me.cmdRedesign = New MCommandButton()
        Me.cmdRedesign.Name = "cmdRedesign"
        Me.cmdRedesign.Location = New Point(20, 408)
        Me.cmdRedesign.Size = New Size(100, 31)
        Me.cmdRedesign.TabIndex = 8
        Me.cmdRedesign.Text = "새로설계"
        Me.cmdRedesign.UseMnemonic = False
        Me.cmdRedesign.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdRedesign)
        Me.cmdEnd = New MCommandButton()
        Me.cmdEnd.Name = "cmdEnd"
        Me.cmdEnd.Location = New Point(128, 408)
        Me.cmdEnd.Size = New Size(100, 31)
        Me.cmdEnd.TabIndex = 9
        Me.cmdEnd.Text = "설계종료"
        Me.cmdEnd.UseMnemonic = False
        Me.cmdEnd.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdEnd)
        Me.cmdDesign = New MCommandButton()
        Me.cmdDesign.Name = "cmdDesign"
        Me.cmdDesign.Location = New Point(516, 408)
        Me.cmdDesign.Size = New Size(100, 31)
        Me.cmdDesign.TabIndex = 10
        Me.cmdDesign.Text = "설계결과"
        Me.cmdDesign.UseMnemonic = False
        Me.cmdDesign.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdDesign)
        Me.Image1 = New MImage()
        Me.Image1.Name = "Image1"
        Me.Image1.Location = New Point(8, 12)
        Me.Image1.Size = New Size(116, 112)
        Me.Image1.TabIndex = 11
        Me.Image1.SizeMode = PictureBoxSizeMode.CenterImage
        Me.Image1.BorderStyle = BorderStyle.FixedSingle
        Me.Image1.Image = LoadResourceImage("frmInput_Image1")
        Me.Controls.Add(Me.Image1)
        Me.ResumeLayout(False)
        Me.PerformLayout()
    End Sub
End Class
