' 이 파일은 tools/vba2vb.py 가 원본 .dvb 의 폼 배치에서 만든다. 직접 고치지 말 것.
Imports System.Drawing
Imports System.Windows.Forms

Partial Class frmNoise
    Inherits MForm

    Friend WithEvents Frame1 As MFrame
    Friend WithEvents txtFanWeight As MTextBox
    Friend WithEvents cboKind As MComboBox
    Friend WithEvents txtNoSA As MTextBox
    Friend WithEvents txtMotorWeight As MTextBox
    Friend WithEvents Label12 As MLabel
    Friend WithEvents Label1 As MLabel
    Friend WithEvents Label2 As MLabel
    Friend WithEvents Label3 As MLabel
    Friend WithEvents Label4 As MLabel
    Friend WithEvents Label5 As MLabel
    Friend WithEvents Label6 As MLabel
    Friend WithEvents TextBox4 As MTextBox
    Friend WithEvents Label7 As MLabel
    Friend WithEvents Label8 As MLabel
    Friend WithEvents Label9 As MLabel
    Friend WithEvents Label10 As MLabel
    Friend WithEvents Label11 As MLabel
    Friend WithEvents Label13 As MLabel
    Friend WithEvents txtSpringConstant As MTextBox
    Friend WithEvents Label14 As MLabel
    Friend WithEvents Label15 As MLabel
    Friend WithEvents Label16 As MLabel
    Friend WithEvents txtNaturalF As MTextBox
    Friend WithEvents Label17 As MLabel
    Friend WithEvents txtForcedF As MTextBox
    Friend WithEvents Label19 As MLabel
    Friend WithEvents txtSAEff As MTextBox
    Friend WithEvents Label20 As MLabel
    Friend WithEvents Label21 As MLabel
    Friend WithEvents txtTotalWeight As MTextBox
    Friend WithEvents Label22 As MLabel
    Friend WithEvents txtFanRevolution As MTextBox
    Friend WithEvents cboDisplacement As MComboBox
    Friend WithEvents Frame2 As MFrame
    Friend WithEvents Label23 As MLabel
    Friend WithEvents txtBPF As MTextBox
    Friend WithEvents Label24 As MLabel
    Friend WithEvents txtBladeNo As MTextBox
    Friend WithEvents Label25 As MLabel
    Friend WithEvents Label26 As MLabel
    Friend WithEvents Label27 As MLabel
    Friend WithEvents Label28 As MLabel
    Friend WithEvents txtCalculatedSPL As MTextBox
    Friend WithEvents cmdBack As MCommandButton
    Friend WithEvents cmdEnd As MCommandButton
    Friend WithEvents cmdReport As MCommandButton
    Friend WithEvents cmdCatalogue As MCommandButton

    Private Sub InitializeComponent()
        Me.SuspendLayout()
        Me.AutoScaleMode = AutoScaleMode.Dpi
        Me.AutoScaleDimensions = New SizeF(96.0F, 96.0F)
        Me.Font = New Font("맑은 고딕", 9F)
        Me.ClientSize = New Size(629, 272)
        Me.Text = "소음진동계산"
        Me.Name = "frmNoise"
        Me.Frame1 = New MFrame()
        Me.Frame1.Name = "Frame1"
        Me.Frame1.Location = New Point(8, 8)
        Me.Frame1.Size = New Size(612, 136)
        Me.Frame1.TabIndex = 0
        Me.Frame1.Text = "방진계산"
        Me.Controls.Add(Me.Frame1)
        Me.txtFanWeight = New MTextBox()
        Me.txtFanWeight.Name = "txtFanWeight"
        Me.txtFanWeight.Location = New Point(292, 15)
        Me.txtFanWeight.AutoSize = False
        Me.txtFanWeight.Size = New Size(80, 23)
        Me.txtFanWeight.TabIndex = 0
        Me.txtFanWeight.Multiline = True
        Me.txtFanWeight.TextAlign = HorizontalAlignment.Center
        Me.Frame1.Controls.Add(Me.txtFanWeight)
        Me.cboKind = New MComboBox()
        Me.cboKind.Name = "cboKind"
        Me.cboKind.Location = New Point(292, 43)
        Me.cboKind.DropDownStyle = ComboBoxStyle.DropDown
        Me.cboKind.IntegralHeight = False
        Me.cboKind.MaxDropDownItems = 12
        Me.cboKind.Size = New Size(80, 23)
        Me.cboKind.TabIndex = 1
        Me.cboKind.Text = "스프링"
        Me.Frame1.Controls.Add(Me.cboKind)
        Me.txtNoSA = New MTextBox()
        Me.txtNoSA.Name = "txtNoSA"
        Me.txtNoSA.Location = New Point(92, 71)
        Me.txtNoSA.AutoSize = False
        Me.txtNoSA.Size = New Size(80, 23)
        Me.txtNoSA.TabIndex = 2
        Me.txtNoSA.Multiline = True
        Me.txtNoSA.TextAlign = HorizontalAlignment.Center
        Me.txtNoSA.Text = "6"
        Me.Frame1.Controls.Add(Me.txtNoSA)
        Me.txtMotorWeight = New MTextBox()
        Me.txtMotorWeight.Name = "txtMotorWeight"
        Me.txtMotorWeight.Location = New Point(92, 15)
        Me.txtMotorWeight.AutoSize = False
        Me.txtMotorWeight.Size = New Size(80, 23)
        Me.txtMotorWeight.TabIndex = 3
        Me.txtMotorWeight.Enabled = False
        Me.txtMotorWeight.Multiline = True
        Me.txtMotorWeight.TextAlign = HorizontalAlignment.Center
        Me.Frame1.Controls.Add(Me.txtMotorWeight)
        Me.Label12 = New MLabel()
        Me.Label12.Name = "Label12"
        Me.Label12.Location = New Point(580, 75)
        Me.Label12.Size = New Size(16, 15)
        Me.Label12.TabIndex = 4
        Me.Label12.Text = "Hz"
        Me.Label12.UseMnemonic = False
        Me.Label12.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label12)
        Me.Label1 = New MLabel()
        Me.Label1.Name = "Label1"
        Me.Label1.Location = New Point(220, 19)
        Me.Label1.Size = New Size(65, 15)
        Me.Label1.TabIndex = 5
        Me.Label1.Text = "송풍기 중량"
        Me.Label1.UseMnemonic = False
        Me.Label1.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label1)
        Me.Label2 = New MLabel()
        Me.Label2.Name = "Label2"
        Me.Label2.Location = New Point(376, 19)
        Me.Label2.Size = New Size(18, 15)
        Me.Label2.TabIndex = 6
        Me.Label2.Text = "kgf"
        Me.Label2.UseMnemonic = False
        Me.Label2.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label2)
        Me.Label3 = New MLabel()
        Me.Label3.Name = "Label3"
        Me.Label3.Location = New Point(32, 19)
        Me.Label3.Size = New Size(53, 15)
        Me.Label3.TabIndex = 7
        Me.Label3.Text = "모터 중량"
        Me.Label3.UseMnemonic = False
        Me.Label3.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label3)
        Me.Label4 = New MLabel()
        Me.Label4.Name = "Label4"
        Me.Label4.Location = New Point(176, 19)
        Me.Label4.Size = New Size(18, 15)
        Me.Label4.TabIndex = 8
        Me.Label4.Text = "kgf"
        Me.Label4.UseMnemonic = False
        Me.Label4.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label4)
        Me.Label5 = New MLabel()
        Me.Label5.Name = "Label5"
        Me.Label5.Location = New Point(580, 19)
        Me.Label5.Size = New Size(18, 15)
        Me.Label5.TabIndex = 9
        Me.Label5.Text = "kgf"
        Me.Label5.UseMnemonic = False
        Me.Label5.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label5)
        Me.Label6 = New MLabel()
        Me.Label6.Name = "Label6"
        Me.Label6.Location = New Point(448, 19)
        Me.Label6.Size = New Size(41, 15)
        Me.Label6.TabIndex = 10
        Me.Label6.Text = "총 중량"
        Me.Label6.UseMnemonic = False
        Me.Label6.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label6)
        Me.TextBox4 = New MTextBox()
        Me.TextBox4.Name = "TextBox4"
        Me.TextBox4.Location = New Point(92, 43)
        Me.TextBox4.AutoSize = False
        Me.TextBox4.Size = New Size(80, 23)
        Me.TextBox4.TabIndex = 11
        Me.TextBox4.Multiline = True
        Me.TextBox4.TextAlign = HorizontalAlignment.Center
        Me.TextBox4.Text = "1220"
        Me.Frame1.Controls.Add(Me.TextBox4)
        Me.Label7 = New MLabel()
        Me.Label7.Name = "Label7"
        Me.Label7.Location = New Point(176, 47)
        Me.Label7.Size = New Size(29, 15)
        Me.Label7.TabIndex = 12
        Me.Label7.Text = "r.p.m"
        Me.Label7.UseMnemonic = False
        Me.Label7.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label7)
        Me.Label8 = New MLabel()
        Me.Label8.Name = "Label8"
        Me.Label8.Location = New Point(8, 47)
        Me.Label8.Size = New Size(77, 15)
        Me.Label8.TabIndex = 13
        Me.Label8.Text = "송풍기 회전수"
        Me.Label8.UseMnemonic = False
        Me.Label8.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label8)
        Me.Label9 = New MLabel()
        Me.Label9.Name = "Label9"
        Me.Label9.Location = New Point(220, 47)
        Me.Label9.Size = New Size(65, 15)
        Me.Label9.TabIndex = 14
        Me.Label9.Text = "방진의 종류"
        Me.Label9.UseMnemonic = False
        Me.Label9.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label9)
        Me.Label10 = New MLabel()
        Me.Label10.Name = "Label10"
        Me.Label10.Location = New Point(580, 47)
        Me.Label10.Size = New Size(18, 15)
        Me.Label10.TabIndex = 15
        Me.Label10.Text = "cm"
        Me.Label10.UseMnemonic = False
        Me.Label10.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label10)
        Me.Label11 = New MLabel()
        Me.Label11.Name = "Label11"
        Me.Label11.Location = New Point(424, 47)
        Me.Label11.Size = New Size(65, 15)
        Me.Label11.TabIndex = 16
        Me.Label11.Text = "방진의 변위"
        Me.Label11.UseMnemonic = False
        Me.Label11.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label11)
        Me.Label13 = New MLabel()
        Me.Label13.Name = "Label13"
        Me.Label13.Location = New Point(220, 75)
        Me.Label13.Size = New Size(65, 15)
        Me.Label13.TabIndex = 17
        Me.Label13.Text = "스프링 상수"
        Me.Label13.UseMnemonic = False
        Me.Label13.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label13)
        Me.txtSpringConstant = New MTextBox()
        Me.txtSpringConstant.Name = "txtSpringConstant"
        Me.txtSpringConstant.Location = New Point(292, 71)
        Me.txtSpringConstant.AutoSize = False
        Me.txtSpringConstant.Size = New Size(80, 23)
        Me.txtSpringConstant.TabIndex = 18
        Me.txtSpringConstant.Enabled = False
        Me.txtSpringConstant.Multiline = True
        Me.txtSpringConstant.TextAlign = HorizontalAlignment.Center
        Me.Frame1.Controls.Add(Me.txtSpringConstant)
        Me.Label14 = New MLabel()
        Me.Label14.Name = "Label14"
        Me.Label14.Location = New Point(376, 75)
        Me.Label14.Size = New Size(40, 15)
        Me.Label14.TabIndex = 19
        Me.Label14.Text = "kgf/cm"
        Me.Label14.UseMnemonic = False
        Me.Label14.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label14)
        Me.Label15 = New MLabel()
        Me.Label15.Name = "Label15"
        Me.Label15.Location = New Point(20, 75)
        Me.Label15.Size = New Size(65, 15)
        Me.Label15.TabIndex = 20
        Me.Label15.Text = "방진의 갯수"
        Me.Label15.UseMnemonic = False
        Me.Label15.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label15)
        Me.Label16 = New MLabel()
        Me.Label16.Name = "Label16"
        Me.Label16.Location = New Point(176, 75)
        Me.Label16.Size = New Size(15, 15)
        Me.Label16.TabIndex = 21
        Me.Label16.Text = "EA"
        Me.Label16.UseMnemonic = False
        Me.Label16.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label16)
        Me.txtNaturalF = New MTextBox()
        Me.txtNaturalF.Name = "txtNaturalF"
        Me.txtNaturalF.Location = New Point(496, 71)
        Me.txtNaturalF.AutoSize = False
        Me.txtNaturalF.Size = New Size(80, 23)
        Me.txtNaturalF.TabIndex = 22
        Me.txtNaturalF.Enabled = False
        Me.txtNaturalF.Multiline = True
        Me.txtNaturalF.TextAlign = HorizontalAlignment.Center
        Me.Frame1.Controls.Add(Me.txtNaturalF)
        Me.Label17 = New MLabel()
        Me.Label17.Name = "Label17"
        Me.Label17.Location = New Point(428, 75)
        Me.Label17.Size = New Size(61, 15)
        Me.Label17.TabIndex = 23
        Me.Label17.Text = "고유진동수"
        Me.Label17.UseMnemonic = False
        Me.Label17.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label17)
        Me.txtForcedF = New MTextBox()
        Me.txtForcedF.Name = "txtForcedF"
        Me.txtForcedF.Location = New Point(92, 99)
        Me.txtForcedF.AutoSize = False
        Me.txtForcedF.Size = New Size(80, 23)
        Me.txtForcedF.TabIndex = 24
        Me.txtForcedF.Enabled = False
        Me.txtForcedF.Multiline = True
        Me.txtForcedF.TextAlign = HorizontalAlignment.Center
        Me.Frame1.Controls.Add(Me.txtForcedF)
        Me.Label19 = New MLabel()
        Me.Label19.Name = "Label19"
        Me.Label19.Location = New Point(236, 103)
        Me.Label19.Size = New Size(49, 15)
        Me.Label19.TabIndex = 25
        Me.Label19.Text = "방진효율"
        Me.Label19.UseMnemonic = False
        Me.Label19.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label19)
        Me.txtSAEff = New MTextBox()
        Me.txtSAEff.Name = "txtSAEff"
        Me.txtSAEff.Location = New Point(292, 99)
        Me.txtSAEff.AutoSize = False
        Me.txtSAEff.Size = New Size(80, 23)
        Me.txtSAEff.TabIndex = 26
        Me.txtSAEff.Enabled = False
        Me.txtSAEff.Multiline = True
        Me.txtSAEff.TextAlign = HorizontalAlignment.Center
        Me.Frame1.Controls.Add(Me.txtSAEff)
        Me.Label20 = New MLabel()
        Me.Label20.Name = "Label20"
        Me.Label20.Location = New Point(376, 103)
        Me.Label20.Size = New Size(11, 15)
        Me.Label20.TabIndex = 27
        Me.Label20.Text = "%"
        Me.Label20.UseMnemonic = False
        Me.Label20.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label20)
        Me.Label21 = New MLabel()
        Me.Label21.Name = "Label21"
        Me.Label21.Location = New Point(20, 103)
        Me.Label21.Size = New Size(65, 15)
        Me.Label21.TabIndex = 28
        Me.Label21.Text = "강제 진동수"
        Me.Label21.UseMnemonic = False
        Me.Label21.TextAlign = ContentAlignment.TopRight
        Me.Frame1.Controls.Add(Me.Label21)
        Me.txtTotalWeight = New MTextBox()
        Me.txtTotalWeight.Name = "txtTotalWeight"
        Me.txtTotalWeight.Location = New Point(496, 15)
        Me.txtTotalWeight.AutoSize = False
        Me.txtTotalWeight.Size = New Size(80, 23)
        Me.txtTotalWeight.TabIndex = 29
        Me.txtTotalWeight.Enabled = False
        Me.txtTotalWeight.Multiline = True
        Me.txtTotalWeight.TextAlign = HorizontalAlignment.Center
        Me.Frame1.Controls.Add(Me.txtTotalWeight)
        Me.Label22 = New MLabel()
        Me.Label22.Name = "Label22"
        Me.Label22.Location = New Point(176, 103)
        Me.Label22.Size = New Size(16, 15)
        Me.Label22.TabIndex = 30
        Me.Label22.Text = "Hz"
        Me.Label22.UseMnemonic = False
        Me.Label22.AutoSize = True
        Me.Frame1.Controls.Add(Me.Label22)
        Me.txtFanRevolution = New MTextBox()
        Me.txtFanRevolution.Name = "txtFanRevolution"
        Me.txtFanRevolution.Location = New Point(92, 43)
        Me.txtFanRevolution.AutoSize = False
        Me.txtFanRevolution.Size = New Size(80, 23)
        Me.txtFanRevolution.TabIndex = 31
        Me.txtFanRevolution.Enabled = False
        Me.txtFanRevolution.Multiline = True
        Me.txtFanRevolution.TextAlign = HorizontalAlignment.Center
        Me.Frame1.Controls.Add(Me.txtFanRevolution)
        Me.cboDisplacement = New MComboBox()
        Me.cboDisplacement.Name = "cboDisplacement"
        Me.cboDisplacement.Location = New Point(496, 43)
        Me.cboDisplacement.DropDownStyle = ComboBoxStyle.DropDown
        Me.cboDisplacement.IntegralHeight = False
        Me.cboDisplacement.MaxDropDownItems = 12
        Me.cboDisplacement.Size = New Size(80, 23)
        Me.cboDisplacement.TabIndex = 32
        Me.cboDisplacement.Text = "2.5"
        Me.Frame1.Controls.Add(Me.cboDisplacement)
        Me.Frame2 = New MFrame()
        Me.Frame2.Name = "Frame2"
        Me.Frame2.Location = New Point(8, 156)
        Me.Frame2.Size = New Size(608, 48)
        Me.Frame2.TabIndex = 1
        Me.Frame2.Text = "Frame2"
        Me.Controls.Add(Me.Frame2)
        Me.Label23 = New MLabel()
        Me.Label23.Name = "Label23"
        Me.Label23.Location = New Point(196, 19)
        Me.Label23.Size = New Size(85, 15)
        Me.Label23.TabIndex = 0
        Me.Label23.Text = "날개소음주파수"
        Me.Label23.UseMnemonic = False
        Me.Label23.TextAlign = ContentAlignment.TopRight
        Me.Frame2.Controls.Add(Me.Label23)
        Me.txtBPF = New MTextBox()
        Me.txtBPF.Name = "txtBPF"
        Me.txtBPF.Location = New Point(288, 15)
        Me.txtBPF.AutoSize = False
        Me.txtBPF.Size = New Size(80, 23)
        Me.txtBPF.TabIndex = 1
        Me.txtBPF.Enabled = False
        Me.txtBPF.Multiline = True
        Me.txtBPF.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtBPF)
        Me.Label24 = New MLabel()
        Me.Label24.Name = "Label24"
        Me.Label24.Location = New Point(372, 19)
        Me.Label24.Size = New Size(16, 15)
        Me.Label24.TabIndex = 2
        Me.Label24.Text = "Hz"
        Me.Label24.UseMnemonic = False
        Me.Label24.AutoSize = True
        Me.Frame2.Controls.Add(Me.Label24)
        Me.txtBladeNo = New MTextBox()
        Me.txtBladeNo.Name = "txtBladeNo"
        Me.txtBladeNo.Location = New Point(88, 15)
        Me.txtBladeNo.AutoSize = False
        Me.txtBladeNo.Size = New Size(80, 23)
        Me.txtBladeNo.TabIndex = 3
        Me.txtBladeNo.Enabled = False
        Me.txtBladeNo.Multiline = True
        Me.txtBladeNo.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtBladeNo)
        Me.Label25 = New MLabel()
        Me.Label25.Name = "Label25"
        Me.Label25.Location = New Point(172, 19)
        Me.Label25.Size = New Size(15, 15)
        Me.Label25.TabIndex = 4
        Me.Label25.Text = "EA"
        Me.Label25.UseMnemonic = False
        Me.Label25.AutoSize = True
        Me.Frame2.Controls.Add(Me.Label25)
        Me.Label26 = New MLabel()
        Me.Label26.Name = "Label26"
        Me.Label26.Location = New Point(40, 19)
        Me.Label26.Size = New Size(41, 15)
        Me.Label26.TabIndex = 5
        Me.Label26.Text = "날개 수"
        Me.Label26.UseMnemonic = False
        Me.Label26.TextAlign = ContentAlignment.TopRight
        Me.Frame2.Controls.Add(Me.Label26)
        Me.Label27 = New MLabel()
        Me.Label27.Name = "Label27"
        Me.Label27.Location = New Point(440, 19)
        Me.Label27.Size = New Size(49, 15)
        Me.Label27.TabIndex = 6
        Me.Label27.Text = "계산소음"
        Me.Label27.UseMnemonic = False
        Me.Label27.TextAlign = ContentAlignment.TopRight
        Me.Frame2.Controls.Add(Me.Label27)
        Me.Label28 = New MLabel()
        Me.Label28.Name = "Label28"
        Me.Label28.Location = New Point(580, 19)
        Me.Label28.Size = New Size(15, 15)
        Me.Label28.TabIndex = 7
        Me.Label28.Text = "dB"
        Me.Label28.UseMnemonic = False
        Me.Label28.AutoSize = True
        Me.Frame2.Controls.Add(Me.Label28)
        Me.txtCalculatedSPL = New MTextBox()
        Me.txtCalculatedSPL.Name = "txtCalculatedSPL"
        Me.txtCalculatedSPL.Location = New Point(496, 15)
        Me.txtCalculatedSPL.AutoSize = False
        Me.txtCalculatedSPL.Size = New Size(80, 23)
        Me.txtCalculatedSPL.TabIndex = 8
        Me.txtCalculatedSPL.Enabled = False
        Me.txtCalculatedSPL.Multiline = True
        Me.txtCalculatedSPL.TextAlign = HorizontalAlignment.Center
        Me.Frame2.Controls.Add(Me.txtCalculatedSPL)
        Me.cmdBack = New MCommandButton()
        Me.cmdBack.Name = "cmdBack"
        Me.cmdBack.Location = New Point(148, 228)
        Me.cmdBack.Size = New Size(107, 31)
        Me.cmdBack.TabIndex = 2
        Me.cmdBack.Text = "뒤로"
        Me.cmdBack.UseMnemonic = False
        Me.cmdBack.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdBack)
        Me.cmdEnd = New MCommandButton()
        Me.cmdEnd.Name = "cmdEnd"
        Me.cmdEnd.Location = New Point(372, 228)
        Me.cmdEnd.Size = New Size(107, 31)
        Me.cmdEnd.TabIndex = 3
        Me.cmdEnd.Text = "설계종료"
        Me.cmdEnd.UseMnemonic = False
        Me.cmdEnd.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdEnd)
        Me.cmdReport = New MCommandButton()
        Me.cmdReport.Name = "cmdReport"
        Me.cmdReport.Location = New Point(260, 228)
        Me.cmdReport.Size = New Size(107, 31)
        Me.cmdReport.TabIndex = 4
        Me.cmdReport.Text = "리포트작성"
        Me.cmdReport.UseMnemonic = False
        Me.cmdReport.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdReport)
        Me.cmdCatalogue = New MCommandButton()
        Me.cmdCatalogue.Name = "cmdCatalogue"
        Me.cmdCatalogue.Location = New Point(8, 228)
        Me.cmdCatalogue.Size = New Size(107, 31)
        Me.cmdCatalogue.TabIndex = 5
        Me.cmdCatalogue.Text = "방진카타로그"
        Me.cmdCatalogue.UseMnemonic = False
        Me.cmdCatalogue.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdCatalogue)
        Me.ResumeLayout(False)
        Me.PerformLayout()
    End Sub
End Class
