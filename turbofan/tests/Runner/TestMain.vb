' 시험: 변환된 코드를 사람이 화면에서 하는 순서대로 돌리고, 가짜 AutoCAD 에 그려진 것을 SVG 로 남긴다.
'   dotnet run --project tests/Runner -- <출력 폴더>
' 시험용 자료 파일(fandata.dat, hs200?p.dat)은 원본 폴더에 있던 것이 아니라 그럴듯하게 만든 값이다.
Imports System.IO
Imports System.Windows.Forms

Public Module TestMain

    Private outDir As String
    Private failures As New List(Of String)

    Public Function Main(args As String()) As Integer
        outDir = If(args.Length > 0, args(0), Path.Combine(Path.GetTempPath(), "turbofan-test"))
        Directory.CreateDirectory(outDir)
        MakeTestData()

        RunStep("시작: frmInput 표시", Sub() frmInput.Show(1))
        Check(frmInput.Visible, "frmInput 이 보여야 함")
        Check(frmInput.cboMotorVoltage.Text = "380", "전압 기본값 380")
        Check(frmInput.cboMotorPoles.Text = "4", "극수 기본값 4")
        Check(frmInput.lblDate.Caption.Contains("년"), "날짜 표시: " & frmInput.lblDate.Caption)
        Console.WriteLine("    날짜: " & frmInput.lblDate.Caption & " / 밀도: " & frmInput.txtDensity.Text)

        ' ---- V벨트 구동 설계 ----
        DesignVBelt("300", "150", "4", "12", "3.2")
        Check(frmOutput.Visible, "설계결과 창이 보여야 함")
        DumpOutput()

        RunStep("설계결과 → 출력관리", Sub() frmOutput.cmdOut.PerformClick())
        Check(frmOutMan.Visible AndAlso Not frmOutput.Visible, "출력관리 창")

        For Each dirCase In {("CW", "UP", "ML"), ("CW", "LEFT", "ML"), ("CW", "RIGHT", "MR"), ("CCW", "UP", "MR"), ("CCW", "LEFT", "ML"), ("CCW", "RIGHT", "MR")}
            SetDirection(dirCase.Item1, dirCase.Item2, dirCase.Item3)
            Draw("vbelt-fan-" & Direction, "송풍기 외형도 (V벨트, " & Direction & ")", Sub() frmOutMan.cmdFan.PerformClick())
        Next
        SetDirection("CW", "UP", "ML")
        Draw("impeller", "회전차 도면", Sub() frmOutMan.cmdImp.PerformClick())
        Draw("performance", "성능 곡선도", Sub() frmOutMan.cmdPer.PerformClick())

        RunStep("소음진동계산 창", Sub() frmOutMan.cmdNoise.PerformClick())
        Check(frmNoise.Visible, "소음진동 창")
        Console.WriteLine("    송풍기중량=" & frmNoise.txtFanWeight.Text & " 총중량=" & frmNoise.txtTotalWeight.Text &
                          " 고유진동수=" & frmNoise.txtNaturalF.Text & " 방진효율=" & frmNoise.txtSAEff.Text & " 소음=" & frmNoise.txtCalculatedSPL.Text)
        Check(frmNoise.txtCalculatedSPL.Text <> "", "계산소음 값")
        RunStep("방진 종류 → 고무", Sub() frmNoise.cboKind.Text = "고무")
        Check(frmNoise.cboDisplacement.Text = "0.5", "고무 변위 0.5: " & frmNoise.cboDisplacement.Text)
        RunStep("뒤로 → 출력관리", Sub() frmNoise.cmdBack.PerformClick())
        RunStep("뒤로 → 설계결과", Sub() frmOutMan.cmdBack.PerformClick())
        Check(frmOutput.Visible, "설계결과 창으로")

        ' 설계결과 창의 위/아래 단추
        Dim pcs0 = frmOutput.txtVbeltPcs.Text
        RunStep("V벨트 가닥 ▲", Sub() frmOutput.cmdUp_1.PerformClick())
        Console.WriteLine("    가닥수 " & pcs0 & " → " & frmOutput.txtVbeltPcs.Text)
        Dim brg0 = frmOutput.txtBearingImp.Text
        RunStep("베어링 ▲", Sub() frmOutput.cmdUp_2.PerformClick())
        Console.WriteLine("    베어링 " & brg0 & " → " & frmOutput.txtBearingImp.Text & " 축경 " & frmOutput.txtShaftDia.Text)
        Dim pl0 = frmOutput.txtPulleySizeFan.Text & "/" & frmOutput.txtPulleySizeMotor.Text
        RunStep("풀리 ▲", Sub() frmOutput.cmdBigSize.PerformClick())
        Console.WriteLine("    풀리(송풍기/모터) " & pl0 & " → " & frmOutput.txtPulleySizeFan.Text & "/" & frmOutput.txtPulleySizeMotor.Text)
        RunStep("풀리 ▼", Sub() frmOutput.cmdSmallSize.PerformClick())
        RunStep("V벨트 형식 B", Sub() frmOutput.cboVbeltType.Text = "B Type")
        Console.WriteLine("    B형 → 가닥수 " & frmOutput.txtVbeltPcs.Text & " 풀리 " & frmOutput.txtPulleySizeFan.Text & "/" & frmOutput.txtPulleySizeMotor.Text)

        ' ---- 새로 설계: 모터 직결 ----
        RunStep("뒤로 → 입력", Sub() frmOutput.cmdRestart.PerformClick())
        Check(frmInput.Visible, "입력 창으로")
        RunStep("새로설계", Sub() frmInput.cmdRedesign.PerformClick())
        DesignDirect("120", "８０", "10", "2.3")   ' 전각 숫자(한글 입력기)도 숫자로 받아야 함
        Check(frmInput.txtPs.Text = "80", "전각 숫자 → 보통 숫자: " & frmInput.txtPs.Text)
        DumpOutput()
        RunStep("설계결과 → 출력관리", Sub() frmOutput.cmdOut.PerformClick())
        For Each dirCase In {("CW", "UP", "ML"), ("CW", "LEFT", "ML"), ("CCW", "RIGHT", "ML")}
            SetDirection(dirCase.Item1, dirCase.Item2, dirCase.Item3)
            Draw("direct-fan-" & Direction, "송풍기 외형도 (직결, " & Direction & ")", Sub() frmOutMan.cmdFan.PerformClick())
        Next
        Draw("direct-impeller", "회전차 도면 (직결)", Sub() frmOutMan.cmdImp.PerformClick())
        Draw("direct-performance", "성능 곡선도 (직결)", Sub() frmOutMan.cmdPer.PerformClick())

        ' ---- 큰 송풍기 ----
        RunStep("뒤로", Sub() frmOutMan.cmdBack.PerformClick())
        RunStep("뒤로 → 입력", Sub() frmOutput.cmdRestart.PerformClick())
        RunStep("새로설계", Sub() frmInput.cmdRedesign.PerformClick())
        DesignVBelt("1500", "250", "8", "9", "4.5", bladeEnter:=False)
        DumpOutput()
        Check(Z = 9, "날개수 칸에서 Enter 없이 설계결과를 눌러도 날개수가 반영되어야 함: Z=" & Z)
        RunStep("설계결과 → 출력관리", Sub() frmOutput.cmdOut.PerformClick())
        SetDirection("CW", "UP", "MR")
        Draw("big-fan", "큰 송풍기 외형도", Sub() frmOutMan.cmdFan.PerformClick())
        Draw("big-impeller", "큰 회전차", Sub() frmOutMan.cmdImp.PerformClick())

        ' ---- 사용자 화면 재현: 모터직결, 풍량 100, 정압 100, 날개수 칸 (원본은 Log(0) 오류) ----
        RunStep("뒤로", Sub() frmOutMan.cmdBack.PerformClick())
        RunStep("뒤로 → 입력", Sub() frmOutput.cmdRestart.PerformClick())
        RunStep("새로설계", Sub() frmInput.cmdRedesign.PerformClick())
        RunStep("모터직결 먼저 선택", Sub() frmInput.optDirect.Value = True)
        TypeInto(frmInput.txtQ, "100")
        TypeInto(frmInput.txtPs, "100", enter:=True)
        Console.WriteLine("    포커스: " & If(frmInput.ActiveControl?.Name, "-"))
        Console.WriteLine("    직결 100/100: N=" & frmInput.txtN_1.Text & " D2=" & frmInput.txtD2_1.Text & " Ns=" & frmInput.txtNs_1.Text & " diaratio=" & diaratio)
        TypeInto(frmInput.txtBladeNo, "10")
        Console.WriteLine("    메시지: " & frmInput.lblMessage.Caption.Replace(vbCrLf, " / "))
        RunStep("모터 출력 칸", Sub() frmInput.cboMotorOutput.Focus())
        RunStep("설계결과", Sub() frmInput.cmdDesign.PerformClick())
        RunStep("설계결과 → 출력관리", Sub() frmOutput.cmdOut.PerformClick())

        ' ---- 입력 오류 메시지 ----
        RunStep("뒤로", Sub() frmOutMan.cmdBack.PerformClick())
        RunStep("뒤로 → 입력", Sub() frmOutput.cmdRestart.PerformClick())
        RunStep("새로설계", Sub() frmInput.cmdRedesign.PerformClick())
        TestShims.Messages.Clear()
        RunStep("풍량 없이 회전차 번호", Sub()
                                        frmInput.txtD2no_1.Focus()
                                    End Sub)
        Check(TestShims.Messages.Any(), "풍량이 비었다는 메시지가 나와야 함")

        File.WriteAllLines(Path.Combine(outDir, "acad-calls.txt"), FakeAcad.Log.Calls)
        Console.WriteLine()
        If failures.Count = 0 Then
            Console.WriteLine("모두 통과")
            Return 0
        End If
        Console.WriteLine("실패 " & failures.Count & "건:")
        For Each f In failures
            Console.WriteLine("  - " & f)
        Next
        Return 1
    End Function

    Private Sub DesignVBelt(q As String, ps As String, d2no As String, blades As String, thick As String, Optional bladeEnter As Boolean = True)
        RunStep("V벨트 선택", Sub() frmInput.optVbelt.Value = True)
        TypeInto(frmInput.txtCustomer, "시험 고객")
        TypeInto(frmInput.txtQ, q)
        TypeInto(frmInput.txtPs, ps)
        TypeInto(frmInput.txtTemp, "20")
        RunStep("회전차 번호 " & d2no & " + Enter", Sub()
                                                 frmInput.txtD2no_1.Focus()
                                                 frmInput.txtD2no_1.Text = d2no
                                                 frmInput.txtD2no_1.TestKeyDown(Keys.Enter)
                                             End Sub)
        Console.WriteLine("    #1: N=" & frmInput.txtN_1.Text & " D2=" & frmInput.txtD2_1.Text & " Ns=" & frmInput.txtNs_1.Text)
        Check(frmInput.txtN_1.Text <> "", "예비설계 회전수가 나와야 함")
        RunStep("선택 #1", Sub() frmInput.cmdNsOk_1.PerformClick())
        TypeInto(frmInput.txtBladeNo, blades, enter:=bladeEnter)
        TypeInto(frmInput.txtBladeThickness, thick)
        RunStep("회전차 재질", Sub()
                           frmInput.cboBladeMaterial.Focus()
                           frmInput.cboBladeMaterial.Text = "SS400"
                       End Sub)
        RunStep("모터 출력 칸", Sub() frmInput.cboMotorOutput.Focus())
        Console.WriteLine("    " & frmInput.lblMessage.Caption.Replace(vbCrLf, " / ") & " / 선택된 모터: " & frmInput.cboMotorOutput.Text)
        RunStep("설계결과", Sub() frmInput.cmdDesign.PerformClick())
    End Sub

    Private Sub DesignDirect(q As String, ps As String, blades As String, thick As String)
        TypeInto(frmInput.txtCustomer, "직결 고객")
        TypeInto(frmInput.txtQ, q)
        TypeInto(frmInput.txtPs, ps)
        RunStep("모터직결 선택", Sub() frmInput.optDirect.Value = True)
        Console.WriteLine("    직결: N=" & frmInput.txtN_1.Text & " D2=" & frmInput.txtD2_1.Text & " #=" & frmInput.txtD2no_1.Text & " Ns=" & frmInput.txtNs_1.Text)
        TypeInto(frmInput.txtBladeNo, blades, enter:=True)
        TypeInto(frmInput.txtBladeThickness, thick)
        RunStep("모터 출력 칸", Sub() frmInput.cboMotorOutput.Focus())
        RunStep("설계결과", Sub() frmInput.cmdDesign.PerformClick())
    End Sub

    Private Sub SetDirection(rot As String, outlet As String, motor As String)
        RunStep("방향 " & rot & "/" & outlet & "/" & motor, Sub()
                                                            frmInput.optCW.Value = (rot = "CW")
                                                            frmInput.optCCW.Value = (rot = "CCW")
                                                            frmInput.optUp.Value = (outlet = "UP")
                                                            frmInput.optLeft.Value = (outlet = "LEFT")
                                                            frmInput.optRight.Value = (outlet = "RIGHT")
                                                            If frmInput.optMLeft.Enabled Then frmInput.optMLeft.Value = (motor = "ML")
                                                            If frmInput.optMRight.Enabled Then frmInput.optMRight.Value = (motor = "MR")
                                                        End Sub)
    End Sub

    Private Sub TypeInto(box As Control, text As String, Optional enter As Boolean = False)
        RunStep(box.Name & " = " & text, Sub()
                                          box.Focus()
                                          box.Text = text
                                          If enter Then box.TestKeyDown(Keys.Enter)
                                      End Sub)
    End Sub

    Private Sub Draw(file As String, title As String, action As Action)
        Dim doc As New FakeAcad.Document()
        AcadHost.TestDocument = doc
        RunStep("도면: " & title, action)
        Console.WriteLine("    → 엔티티 " & doc.EntityCount & "개 (" & doc.Summary() & ")")
        Check(doc.EntityCount > 20, title & ": 그려진 것이 너무 적음")
        IO.File.WriteAllText(Path.Combine(outDir, file & ".svg"), doc.ToSvg(title))
    End Sub

    Private Sub DumpOutput()
        Dim f = frmOutput
        Console.WriteLine("    결과: N=" & f.txtN.Text & ", D2=" & f.txtD2.Text & ", D1=" & f.txtD1.Text & ", b1=" & f.txtB1.Text & ", b2=" & f.txtB2.Text &
                          ", β1=" & f.txtBeta1.Text & ", Y=" & f.txtY.Text & ", R=" & f.txtR.Text)
        Console.WriteLine("          동력=" & f.txtPowerkw.Text & " (" & f.txtPowerhp.Text & "), 축=" & f.txtShaftDia.Text & ", 벨트=" & f.cboVbeltType.Text & " " & f.txtVbeltPcs.Text &
                          ", 풀리=" & f.txtPulleySizeFan.Text & "/" & f.txtPulleySizeMotor.Text & ", 베어링=" & f.txtBearingImp.Text)
        Console.WriteLine("          응력: 주판 " & f.txtMplateStress.Text & " (안전율 " & f.txtMplateSf.Text & "), 날개 " & f.txtBladeStress.Text & " (" & f.txtBladeSf.Text & ")" &
                          ", 수명 " & f.txtBearingLifeTimeHr.Text & " " & f.txtBearingLifeTimeYear.Text & ", 주속 " & f.txtU2.Text & ", 토출 " & f.txtDischarge.Text & ", 흡입 " & f.txtInlet.Text)
        Console.WriteLine("          모터: " & f.txtMOutput.Text & " " & f.txtMFrame.Text & " " & f.txtMrpm.Text & " 효율 " & f.txtMeff.Text & " 중량 " & f.txtMWeight.Text)
        Check(f.txtD2.Text.StartsWith("φ"), "D2 표시")
    End Sub

    Private Sub RunStep(name As String, action As Action)
        Console.WriteLine("● " & name)
        Try
            action()
            Application.DoEvents()
        Catch ex As Exception
            Dim e = ex
            If TypeOf e Is Reflection.TargetInvocationException AndAlso e.InnerException IsNot Nothing Then e = e.InnerException
            failures.Add(name & ": " & e.GetType().Name & " " & e.Message)
            Console.WriteLine("    !! " & e.GetType().Name & ": " & e.Message)
            Console.WriteLine(String.Join(vbLf, e.StackTrace.Split(vbLf).Where(Function(l) l.Contains(".vb")).Take(6)))
        End Try
    End Sub

    Private Sub Check(ok As Boolean, what As String)
        If Not ok Then
            failures.Add(what)
            Console.WriteLine("    !! 확인 실패: " & what)
        End If
    End Sub

    ''' <summary>
    ''' 원본 자료(src/Bundle: Data, Pics, Acad, Word)를 시험 폴더의 ALISP\Turbo Fan Design 에 둔다.
    ''' 원본 코드는 경로를 "...\Data\fandata.dat" 처럼 역슬래시로 붙인다(윈도우). 리눅스 시험에서는
    ''' 그 문자열 그대로의 파일 이름으로도 같은 내용을 써 둔다.
    ''' </summary>
    Private Sub MakeTestData()
        Dim bundle = Path.GetFullPath(Path.Combine(AppDir(), "..", "..", "..", "..", "..", "src", "Bundle"))
        Dim target = Path.Combine(AppDir(), "ALISP", "Turbo Fan Design")
        For Each f In Directory.GetFiles(bundle, "*", SearchOption.AllDirectories)
            Dim rel = Path.GetRelativePath(bundle, f)
            Dim dest = Path.Combine(target, rel)
            Directory.CreateDirectory(Path.GetDirectoryName(dest))
            File.Copy(f, dest, True)
            File.Copy(f, target & "\" & rel.Replace("/"c, "\"c), True)
        Next
    End Sub
End Module
