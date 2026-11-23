' 이 파일은 tools/vba2vb.py 가 원본 .dvb 의 폼 배치에서 만든다. 직접 고치지 말 것.
Imports System.Drawing
Imports System.Windows.Forms

Partial Class frmOutMan
    Inherits MForm

    Friend WithEvents cmdFan As MCommandButton
    Friend WithEvents cmdImp As MCommandButton
    Friend WithEvents cmdPer As MCommandButton
    Friend WithEvents cmdResult As MCommandButton
    Friend WithEvents cmdEnd As MCommandButton
    Friend WithEvents cmdBack As MCommandButton
    Friend WithEvents cmdDSheet As MCommandButton
    Friend WithEvents cmdNoise As MCommandButton

    Private Sub InitializeComponent()
        Me.SuspendLayout()
        Me.AutoScaleMode = AutoScaleMode.Dpi
        Me.AutoScaleDimensions = New SizeF(96.0F, 96.0F)
        Me.Font = New Font("맑은 고딕", 9F)
        Me.ClientSize = New Size(270, 330)
        Me.Text = "출력관리"
        Me.Name = "frmOutMan"
        Me.cmdFan = New MCommandButton()
        Me.cmdFan.Name = "cmdFan"
        Me.cmdFan.Location = New Point(16, 16)
        Me.cmdFan.Size = New Size(236, 40)
        Me.cmdFan.TabIndex = 0
        Me.cmdFan.Text = "송풍기 외형도 출력"
        Me.cmdFan.UseMnemonic = False
        Me.cmdFan.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdFan)
        Me.cmdImp = New MCommandButton()
        Me.cmdImp.Name = "cmdImp"
        Me.cmdImp.Location = New Point(16, 60)
        Me.cmdImp.Size = New Size(236, 40)
        Me.cmdImp.TabIndex = 1
        Me.cmdImp.Text = "회전차 도면 출력"
        Me.cmdImp.UseMnemonic = False
        Me.cmdImp.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdImp)
        Me.cmdPer = New MCommandButton()
        Me.cmdPer.Name = "cmdPer"
        Me.cmdPer.Location = New Point(16, 104)
        Me.cmdPer.Size = New Size(236, 40)
        Me.cmdPer.TabIndex = 2
        Me.cmdPer.Text = "성능 곡선도 출력"
        Me.cmdPer.UseMnemonic = False
        Me.cmdPer.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdPer)
        Me.cmdResult = New MCommandButton()
        Me.cmdResult.Name = "cmdResult"
        Me.cmdResult.Location = New Point(16, 192)
        Me.cmdResult.Size = New Size(236, 40)
        Me.cmdResult.TabIndex = 3
        Me.cmdResult.Text = "설계보고서 출력"
        Me.cmdResult.UseMnemonic = False
        Me.cmdResult.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdResult)
        Me.cmdEnd = New MCommandButton()
        Me.cmdEnd.Name = "cmdEnd"
        Me.cmdEnd.Location = New Point(139, 288)
        Me.cmdEnd.Size = New Size(84, 31)
        Me.cmdEnd.TabIndex = 4
        Me.cmdEnd.Text = "종료"
        Me.cmdEnd.UseMnemonic = False
        Me.cmdEnd.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdEnd)
        Me.cmdBack = New MCommandButton()
        Me.cmdBack.Name = "cmdBack"
        Me.cmdBack.Location = New Point(47, 288)
        Me.cmdBack.Size = New Size(84, 31)
        Me.cmdBack.TabIndex = 5
        Me.cmdBack.Text = "뒤로"
        Me.cmdBack.UseMnemonic = False
        Me.cmdBack.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdBack)
        Me.cmdDSheet = New MCommandButton()
        Me.cmdDSheet.Name = "cmdDSheet"
        Me.cmdDSheet.Location = New Point(16, 148)
        Me.cmdDSheet.Size = New Size(236, 40)
        Me.cmdDSheet.TabIndex = 6
        Me.cmdDSheet.Text = "데이터 시트 출력"
        Me.cmdDSheet.UseMnemonic = False
        Me.cmdDSheet.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdDSheet)
        Me.cmdNoise = New MCommandButton()
        Me.cmdNoise.Name = "cmdNoise"
        Me.cmdNoise.Location = New Point(16, 236)
        Me.cmdNoise.Size = New Size(236, 40)
        Me.cmdNoise.TabIndex = 7
        Me.cmdNoise.Text = "소음진동계산서"
        Me.cmdNoise.UseMnemonic = False
        Me.cmdNoise.UseVisualStyleBackColor = True
        Me.Controls.Add(Me.cmdNoise)
        Me.ResumeLayout(False)
        Me.PerformLayout()
    End Sub
End Class
