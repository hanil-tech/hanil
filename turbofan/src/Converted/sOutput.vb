' 원본: sOutput.bas (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드.
' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.
Option Strict Off
Option Explicit On

Public Module sOutput

    Public Sub Output_On_Screen() '입력 및 계산결과를 출력화면에 출력한다.
        Dim PowerTransMethod As String

        frmOutput.txtCustomer.text = frmInput.txtCustomer.text
        frmOutput.txtDate.text = frmInput.lblDate.Caption
        frmOutput.txtQ.text = frmInput.txtQ.text + " ㎥/min"
        frmOutput.txtPs.text = frmInput.txtPs.text + " mmAq"
        frmOutput.txtTemp.text = frmInput.txtTemp.text + " ℃"
        frmOutput.txtDensity.text = Format(frmInput.txtDensity.text, "0.###") + " kg/㎥"
        frmOutput.txtPowerkw.text = Format(spower, "0.00") + " kW"
        frmOutput.txtPowerhp.text = Format(spower * 1.36, "0.00") + " HP"

        '전동방식 검사하여 출력폼에 표시

        If frmInput.optVbelt.Value = True Then
            PowerTransMethod = "V-벨트전동"
            Else
            PowerTransMethod = "Motor 직결"
        End If

        frmOutput.txtPowerTransMethod.text = VbCopy(PowerTransMethod)

        'V-Belt 전동시와 직결시 구분하여 출력

        If frmInput.optVbelt.Value = True Then ' V-Belt 전동시

            frmOutput.txtShaftDia.Enabled = True
            frmOutput.cboVbeltType.Enabled = True
            frmOutput.txtVbeltPcs.Enabled = True
            frmOutput.txtBearingImp.Enabled = True
            frmOutput.txtBearingPulley.Enabled = True
            frmOutput.txtPulleySizeFan.Enabled = True
            frmOutput.txtPulleySizeMotor.Enabled = True
            frmOutput.cboShaftMatl.Enabled = True


            frmOutput.txtShaftDia.text = "φ " & DS & " mm"
            frmOutput.cboVbeltType.text = VbCopy(VbeltType)
            frmOutput.txtVbeltPcs.text = PCS & " pcs"

            frmOutput.txtBearingImp.text = "63" & Format(bearingno, "00")
            frmOutput.txtBearingPulley.text = "63" & Format(bearingno, "00")

            frmOutput.txtPulleySizeFan.text = fanPulley & " ˝"
            frmOutput.txtPulleySizeMotor.text = motorPulley & " ˝"
            Bearing_Lifetime


            Else 'Motor직결시

            frmOutput.txtShaftDia.text = ""
            frmOutput.txtShaftDia.Enabled = False
            frmOutput.cboVbeltType.text = ""
            frmOutput.cboVbeltType.Enabled = False
            frmOutput.txtVbeltPcs.text = ""
            frmOutput.txtVbeltPcs.Enabled = False
            frmOutput.txtBearingImp.text = ""
            frmOutput.txtBearingImp.Enabled = False
            frmOutput.txtBearingPulley.text = ""
            frmOutput.txtBearingPulley.Enabled = False
            frmOutput.txtPulleySizeFan.text = ""
            frmOutput.txtPulleySizeFan.Enabled = False
            frmOutput.txtPulleySizeMotor.text = ""
            frmOutput.txtPulleySizeMotor.Enabled = False
            frmOutput.cboShaftMatl.text = ""
            frmOutput.cboShaftMatl.Enabled = False

        End If ' 전동방법

        frmOutput.txtN.text = Format(N, "####") & " r.p.m"
        frmOutput.txtBladeNo.text = frmInput.txtBladeNo.text & " EA"
        frmOutput.txtD2.text = "φ " & Format(D2 * 1000, "####") & " mm"
        frmOutput.txtD1.text = "φ " & Format(D1 * 1000, "####") & " mm"
        frmOutput.txtB1.text = Format(b1 * 1000, "###") & " mm"
        frmOutput.txtB2.text = Format(b2 * 1000, "###") & " mm"

        frmOutput.txtBeta1.text = Format(beta1 * 180 / (Atn(1) * 4), "##.0") & " ˚"
        frmOutput.txtBeta2.text = "45.0 ˚"
        frmOutput.txtY.text = "R " & Format(myy * 1000, "####") & " mm"
        frmOutput.txtR.text = "R " & Format(myr * 1000, "####") & " mm"
        frmOutput.txtImpMatl.text = frmInput.cboBladeMaterial.text
        frmOutput.txtBladeThickness.text = frmInput.txtBladeThickness.text & " t"

        '모터에 관한 내용출력
        frmOutput.txtMVoltage.text = motorvoltage & " V"
        frmOutput.txtMphPoles.text = "3 φ / " & frmInput.cboMotorPoles.text & " P"
        frmOutput.txtMFrequency.text = "60 Hz"
        frmOutput.txtMOutput.text = motoroutput & " kW"
        frmOutput.txtMFrame.text = VbCopy(motorframe)
        frmOutput.txtMrpm.text = motorrpm & " r.p.m"
        frmOutput.txtMeff.text = motoreff & " %"
        frmOutput.txtMpf.text = motorpf & " %"
        frmOutput.txtMLoadAmp.text = Format(motorloadamp, "###.#") & " A"
        frmOutput.txtMStartAmp.text = Format(motorstartamp, "###.#") & " A"
        frmOutput.txtMGD2.text = motorgd2 & " kg-㎡"
        frmOutput.txtMWeight.text = motorwt & " kg"

        '응력해석 결과 출력
        frmOutput.txtMplateAllowStress.text = maxStress & " kg/㎠"
        frmOutput.txtMplateStress.text = Format(mStress, "####") & " kg/㎠"
        frmOutput.txtMplateSf.text = Format(mSf, "##.0")

        frmOutput.txtBladeAllowStress.text = maxStress & " kg/㎠"
        frmOutput.txtBladeStress.text = Format(bladeStress, "####") & " kg/㎠"
        frmOutput.txtBladeSf.text = Format(bSf, "##.0")
        frmOutput.txtImpGap.text = Format(D2 * 10, "##.0") & " mm 이하"
        frmOutput.txtU2.text = Format(u2, "###.0") & " m/sec"

        frmOutput.txtDischarge.text = Lout & "mm ×" & Wout & "mm"
        frmOutput.txtInlet.text = "φ" & DiaInlet & "mm"

    End Sub

End Module
