' 프로그램 시작점. 원본 mStart.Main 이 하던 일(frmInput.Show)을 한다.
Imports System.Windows.Forms

Public Module Program

    <STAThread>
    Public Sub Main()
        Application.EnableVisualStyles()
        Application.SetCompatibleTextRenderingDefault(False)
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException)
        AddHandler Application.ThreadException, Sub(s, e) ShowError(e.Exception)

        Try
            MForm.AppIcon = Drawing.Icon.ExtractAssociatedIcon(Reflection.Assembly.GetExecutingAssembly().Location)
        Catch
        End Try

        ' (AutoCAD 가 바쁠 때 다시 시도하게 하는 장치는 AutoCAD 에 붙을 때 등록한다)

        frmInput.Show(1)
        Application.Run()
        ReleaseAutoCad()
    End Sub

    ''' <summary>
    ''' 원본의 End 문, 창의 [X].
    ''' AutoCAD 연결과 COM 필터를 정리하고, 창을 닫아 메시지 루프가 끝나게 한 뒤 Main 에서 정상 종료한다.
    ''' (프로세스를 바로 죽이면 0xc0020001 "unknown software exception" 오류 창이 뜬다.)
    ''' End 뒤의 원본 코드가 이어서 돌지 않도록, stopCurrentCode 이면 지금 처리 중인 코드를 멈춘다.
    ''' </summary>
    Public Sub QuitApplication(Optional stopCurrentCode As Boolean = True)
        If Not quitting Then
            quitting = True
            Try
                ReleaseAutoCad()
            Catch
            End Try
            Application.Exit()
        End If
        If stopCurrentCode Then Throw New QuitSignal()
    End Sub
    Private quitting As Boolean

    ''' <summary>End 이후 코드를 멈추기 위한 신호 (오류 아님).</summary>
    Public Class QuitSignal
        Inherits Exception
    End Class

    ''' <summary>원본에서 "런타임 오류" 창이 뜨던 자리. 메시지를 보여 주고 계속 쓸 수 있게 한다.</summary>
    Public Sub ShowError(ex As Exception)
        If TypeOf ex Is Reflection.TargetInvocationException AndAlso ex.InnerException IsNot Nothing Then ex = ex.InnerException
        If TypeOf ex Is QuitSignal Then Return
        If TypeOf ex Is AutoCadNotAvailableException Then
            MsgBox(ex.Message, MsgBoxStyle.Exclamation, "AutoCAD")
            Return
        End If
        If TypeOf ex Is IO.FileNotFoundException OrElse TypeOf ex Is IO.DirectoryNotFoundException Then
            MsgBox("필요한 파일을 찾을 수 없습니다." & vbCrLf & vbCrLf & ex.Message & vbCrLf & vbCrLf &
                   "원래 매크로를 쓰던 PC 의 AutoCAD 폴더 안 'ALISP\Turbo Fan Design' 폴더(Data, Pics, Acad, Word)가 있어야 합니다." & vbCrLf &
                   "그 ALISP 폴더를 이 프로그램(exe) 옆에 복사한 뒤 프로그램을 다시 실행하세요." & vbCrLf & vbCrLf &
                   "지금 쓰는 자료 폴더: " & SupportFolder(),
                   MsgBoxStyle.Exclamation, "파일 없음")
            Return
        End If
        Dim msg = ex.Message
        If TypeOf ex Is Runtime.InteropServices.COMException Then
            msg = "AutoCAD/Word 와 통신하는 중 오류가 났습니다." & vbCrLf & msg
        End If
        MsgBox(msg & vbCrLf & vbCrLf & "(" & ex.GetType().Name & ")" & vbCrLf & ex.StackTrace?.Split({vbCrLf}, StringSplitOptions.None).FirstOrDefault(),
               MsgBoxStyle.Critical, "오류")
    End Sub

End Module
