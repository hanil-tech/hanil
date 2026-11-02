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

        ' AutoCAD 가 바쁠 때 호출을 다시 시도하게 (UI 스레드에 한 번)
        MessageFilter.Register()

        frmInput.Show(1)
        Application.Run()
    End Sub

    Public Sub QuitApplication()
        Application.Exit()
        Environment.Exit(0)
    End Sub

    ''' <summary>원본에서 "런타임 오류" 창이 뜨던 자리. 메시지를 보여 주고 계속 쓸 수 있게 한다.</summary>
    Public Sub ShowError(ex As Exception)
        If TypeOf ex Is Reflection.TargetInvocationException AndAlso ex.InnerException IsNot Nothing Then ex = ex.InnerException
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
