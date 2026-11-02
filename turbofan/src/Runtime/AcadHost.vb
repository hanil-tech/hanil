' AutoCAD 연결.
' 원본 VBA 는 AutoCAD 안에서 돌았기 때문에 "ThisDrawing" 이 늘 있었다.
' 이 프로그램은 밖에서 실행되므로, 켜져 있는 AutoCAD 에 COM 으로 붙어서
' 같은 이름(ThisDrawing)으로 지금 열린 도면을 넘겨준다.
Imports System.IO
Imports System.Runtime.InteropServices
Imports Microsoft.Win32

Public Module AcadHost

    ' ---- AutoCAD 상수 (원본에서 쓰는 것만) ----
    Public Const acRed As Integer = 1
    Public Const acYellow As Integer = 2
    Public Const acGreen As Integer = 3
    Public Const acCyan As Integer = 4
    Public Const acBlue As Integer = 5
    Public Const acMagenta As Integer = 6
    Public Const acWhite As Integer = 7
    Public Const acByLayer As Integer = 256

    Public Const acActiveViewport As Integer = 1
    Public Const acAllViewports As Integer = 0

    Public Const acAlignmentLeft As Integer = 0
    Public Const acAlignmentCenter As Integer = 1
    Public Const acAlignmentRight As Integer = 2
    Public Const acAlignmentAligned As Integer = 3
    Public Const acAlignmentMiddle As Integer = 4
    Public Const acAlignmentFit As Integer = 5

    Public Const acHorizontalAlignmentLeft As Integer = 0
    Public Const acHorizontalAlignmentCenter As Integer = 1
    Public Const acHorizontalAlignmentRight As Integer = 2
    Public Const acHorizontalAlignmentAligned As Integer = 3
    Public Const acHorizontalAlignmentMiddle As Integer = 4
    Public Const acHorizontalAlignmentFit As Integer = 5

    Public Const acExtendNone As Integer = 0
    Public Const acExtendThisEntity As Integer = 1
    Public Const acExtendOtherEntity As Integer = 2
    Public Const acExtendBoth As Integer = 3

    Public Const acSelectionSetWindow As Integer = 0
    Public Const acSelectionSetCrossing As Integer = 1
    Public Const acSelectionSetFence As Integer = 2
    Public Const acSelectionSetPrevious As Integer = 3
    Public Const acSelectionSetLast As Integer = 4
    Public Const acSelectionSetAll As Integer = 5

    Public Const acZoomScaledAbsolute As Integer = 0
    Public Const acZoomScaledRelative As Integer = 1
    Public Const acZoomScaledRelativePSpace As Integer = 2

    ''' <summary>시험용: AutoCAD 대신 쓸 가짜 도면 객체 (테스트에서만 넣는다).</summary>
    Public TestDocument As Object

    Private _app As Object
    Private _doc As Object
    Private _docCheckedAt As DateTime = DateTime.MinValue

    ''' <summary>원본 VBA 의 ThisDrawing — 지금 AutoCAD 에 열려 있는 도면.</summary>
    Public ReadOnly Property ThisDrawing As Object
        Get
            If TestDocument IsNot Nothing Then Return TestDocument
            ' 같은 도면을 계속 쓰되, 1초마다 사용자가 다른 도면으로 바꿨는지 확인한다.
            If _doc IsNot Nothing AndAlso (DateTime.Now - _docCheckedAt).TotalSeconds < 1 Then Return _doc
            _doc = AcadApplication.ActiveDocument
            _docCheckedAt = DateTime.Now
            Return _doc
        End Get
    End Property

    ''' <summary>켜져 있는 AutoCAD. 없으면 켤지 물어본다.</summary>
    Public ReadOnly Property AcadApplication As Object
        Get
            If _app IsNot Nothing Then
                Try
                    Dim unused = _app.Visible   ' 살아 있는지 확인
                    Return _app
                Catch
                    _app = Nothing
                    _doc = Nothing
                End Try
            End If
            _app = ConnectAutoCad()
            Return _app
        End Get
    End Property

    Public ReadOnly Property IsAutoCadConnected As Boolean
        Get
            Return _app IsNot Nothing
        End Get
    End Property

    Private Function ConnectAutoCad() As Object
        MessageFilter.Register()
#If NETFRAMEWORK Then
        Try
            Return Marshal.GetActiveObject("AutoCAD.Application")
        Catch
        End Try
#End If
        Dim answer = MsgBox("실행 중인 AutoCAD 를 찾지 못했습니다." & vbCrLf & vbCrLf &
                            "AutoCAD 를 지금 실행할까요? (시작하는 데 시간이 조금 걸립니다)" & vbCrLf &
                            "[아니요] 를 누르면 도면 작업을 취소합니다.",
                            MsgBoxStyle.YesNo Or MsgBoxStyle.Question, "AutoCAD 연결")
        If answer <> MsgBoxResult.Yes Then
            Throw New AutoCadNotAvailableException("AutoCAD 가 실행되어 있지 않습니다.")
        End If
        Dim app As Object
        Try
            Using New WaitCursor()
                app = Interaction.CreateObject("AutoCAD.Application")
                app.Visible = True
            End Using
        Catch ex As Exception
            Throw New AutoCadNotAvailableException("AutoCAD 를 실행하지 못했습니다." & vbCrLf & ex.Message)
        End Try
        Return app
    End Function

    ''' <summary>원본의 ThisDrawing.Application.Path 자리 (자료 폴더의 두 단계 위). 원본 코드 호환용.</summary>
    Public Function SupportRoot() As String
        Dim f = SupportFolder()
        Return If(Directory.GetParent(f)?.Parent?.FullName, f)
    End Function

    Private Const SettingsKey As String = "Software\Hanil\TurboFanDesign"
    Private _supportFolder As String

    ''' <summary>
    ''' 원본이 쓰던 자료 폴더 "…\ALISP\Turbo Fan Design" (안에 Data, Pics, Acad, Word).
    ''' 찾는 순서: 전에 고른 폴더, exe 옆, 실행 중인 AutoCAD 폴더, 설치된 AutoCAD 폴더들,
    ''' Program Files\Autodesk 아래, C:\ D:\ 바로 아래. 없으면 프로그램 안에 넣어 둔 자료를 꺼내 쓴다.
    ''' </summary>
    Public Function SupportFolder() As String
        If _supportFolder IsNot Nothing Then Return _supportFolder
        For Each candidate In SupportFolderCandidates()
            If IsSupportFolder(candidate) Then
                _supportFolder = candidate
                Return candidate
            End If
        Next
        ' PC 에 자료 폴더가 없으면 프로그램 안에 넣어 둔 원본 자료(Data, Pics, Acad, Word)를 꺼내 쓴다.
        Dim bundled = ExtractBundle()
        If bundled IsNot Nothing Then
            _supportFolder = bundled
            Return bundled
        End If
        Return Path.Combine(AppDir(), "ALISP", "Turbo Fan Design")
    End Function

    ''' <summary>폴더 안에 원본 자료(Data\fandata.dat)가 있는지.</summary>
    Private Function IsSupportFolder(folder As String) As Boolean
        Try
            Return Directory.Exists(folder) AndAlso File.Exists(Path.Combine(folder, "Data", "fandata.dat"))
        Catch
            Return False
        End Try
    End Function

    Private Iterator Function SupportFolderCandidates() As IEnumerable(Of String)
        Dim saved = LoadSetting()
        If saved IsNot Nothing Then Yield saved
        Dim roots As New List(Of String) From {AppDir()}
        Dim parent = Directory.GetParent(AppDir())
        If parent IsNot Nothing Then roots.Add(parent.FullName)
        If _app IsNot Nothing Then
            Try
                roots.Add(CStr(_app.Path))
            Catch
            End Try
        End If
        roots.AddRange(InstalledAutoCadFolders())
        For Each pf In {Environment.GetEnvironmentVariable("ProgramFiles"), Environment.GetEnvironmentVariable("ProgramFiles(x86)"), Environment.GetEnvironmentVariable("ProgramW6432")}
            If String.IsNullOrEmpty(pf) Then Continue For
            Dim autodesk = Path.Combine(pf, "Autodesk")
            Dim subs As String() = {}
            Try
                If Directory.Exists(autodesk) Then subs = Directory.GetDirectories(autodesk)
            Catch
            End Try
            roots.AddRange(subs.OrderByDescending(Function(d) d))
        Next
        roots.Add("C:\")
        roots.Add("D:\")
        For Each r In roots
            If String.IsNullOrEmpty(r) Then Continue For
            Yield Path.Combine(r, "ALISP", "Turbo Fan Design")
            Yield Path.Combine(r, "Turbo Fan Design")
        Next
    End Function

    ''' <summary>
    ''' exe 안의 원본 자료(리소스 이름 "bundle/Data/fandata.dat" 등)를
    ''' %LOCALAPPDATA%\Hanil\TurboFanDesign\<버전>\Turbo Fan Design 에 풀어 놓고 그 경로를 돌려준다.
    ''' </summary>
    Public Function ExtractBundle() As String
        Try
            Dim asm = Reflection.Assembly.GetExecutingAssembly()
            Dim ver = asm.GetName().Version.ToString()
            Dim target = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                                      "Hanil", "TurboFanDesign", ver, "Turbo Fan Design")
            Dim any = False
            For Each name In asm.GetManifestResourceNames()
                Dim n = name.Replace("\"c, "/"c)
                If Not n.StartsWith("bundle/", StringComparison.OrdinalIgnoreCase) Then Continue For
                any = True
                Dim rel = n.Substring(7).Replace("/"c, Path.DirectorySeparatorChar)
                Dim dest = Path.Combine(target, rel)
                Using src = asm.GetManifestResourceStream(name)
                    If File.Exists(dest) AndAlso New FileInfo(dest).Length = src.Length Then Continue For
                    Directory.CreateDirectory(Path.GetDirectoryName(dest))
                    Using fs = File.Create(dest)
                        src.CopyTo(fs)
                    End Using
                End Using
            Next
            If any AndAlso IsSupportFolder(target) Then Return target
        Catch
        End Try
        Return Nothing
    End Function

    Private Function LoadSetting() As String
        Try
            Using k = Registry.CurrentUser.OpenSubKey(SettingsKey)
                Return TryCast(k?.GetValue("SupportFolder"), String)
            End Using
        Catch
            Return Nothing
        End Try
    End Function

    Private Sub SaveSetting(folder As String)
        Try
            Using k = Registry.CurrentUser.CreateSubKey(SettingsKey)
                k.SetValue("SupportFolder", folder)
            End Using
        Catch
        End Try
    End Sub

    Public Function AppDir() As String
        Return Path.GetDirectoryName(Reflection.Assembly.GetExecutingAssembly().Location)
    End Function

    ''' <summary>레지스트리에 적힌 AutoCAD 설치 폴더들 (최신 버전 먼저).</summary>
    Public Function InstalledAutoCadFolders() As List(Of String)
        Dim found As New List(Of String)
        For Each hive In {Registry.LocalMachine, Registry.CurrentUser}
            For Each view In {RegistryView.Registry64, RegistryView.Registry32}
                Try
                    Using baseKey = RegistryKey.OpenBaseKey(If(hive Is Registry.LocalMachine, RegistryHive.LocalMachine, RegistryHive.CurrentUser), view)
                        Using acad = baseKey.OpenSubKey("SOFTWARE\Autodesk\AutoCAD")
                            If acad Is Nothing Then Continue For
                            Dim releases = acad.GetSubKeyNames().OrderByDescending(Function(n) n).ToList()
                            For Each rel In releases
                                Using relKey = acad.OpenSubKey(rel)
                                    If relKey Is Nothing Then Continue For
                                    For Each prod In relKey.GetSubKeyNames()
                                        Using prodKey = relKey.OpenSubKey(prod)
                                            Dim loc = TryCast(prodKey?.GetValue("AcadLocation"), String)
                                            If Not String.IsNullOrEmpty(loc) AndAlso Not found.Contains(loc, StringComparer.OrdinalIgnoreCase) Then found.Add(loc)
                                        End Using
                                    Next
                                End Using
                            Next
                        End Using
                    End Using
                Catch
                End Try
            Next
        Next
        Return found
    End Function

    ''' <summary>
    ''' 원본의 ThisDrawing.Utility.PolarPoint 와 같은 계산.
    ''' (AutoCAD 에 매번 물어보면 프로그램 밖이라 느려서 여기서 바로 계산한다.)
    ''' </summary>
    Public Function PolarPoint(pt As Object, angle As Double, distance As Double) As Object
        Dim r(2) As Double
        r(0) = CDbl(pt(0)) + distance * Math.Cos(angle)
        r(1) = CDbl(pt(1)) + distance * Math.Sin(angle)
        r(2) = If(UBound(pt) >= 2, CDbl(pt(2)), 0.0)
        Return r
    End Function

End Module

Public Class AutoCadNotAvailableException
    Inherits Exception
    Public Sub New(message As String)
        MyBase.New(message)
    End Sub
End Class

Public Class WaitCursor
    Implements IDisposable
    Private ReadOnly previous As Windows.Forms.Cursor
    Public Sub New()
        previous = Windows.Forms.Cursor.Current
        Windows.Forms.Cursor.Current = Windows.Forms.Cursors.WaitCursor
    End Sub
    Public Sub Dispose() Implements IDisposable.Dispose
        Windows.Forms.Cursor.Current = previous
    End Sub
End Class

''' <summary>
''' AutoCAD 가 바쁠 때(명령 실행 중 등) COM 호출이 "거부"되면 잠시 뒤 다시 시도하게 한다.
''' 프로그램 밖에서 AutoCAD 를 부를 때 꼭 필요한 장치다.
''' </summary>
Public Class MessageFilter
    Implements IOleMessageFilter

    Private Shared registered As Boolean

    Public Shared Sub Register()
        If registered Then Return
        Dim old As IOleMessageFilter = Nothing
        Try
            CoRegisterMessageFilter(New MessageFilter(), old)
            registered = True
        Catch
        End Try
    End Sub

    Private Function HandleInComingCall(dwCallType As Integer, hTaskCaller As IntPtr, dwTickCount As Integer, lpInterfaceInfo As IntPtr) As Integer Implements IOleMessageFilter.HandleInComingCall
        Return 0 ' SERVERCALL_ISHANDLED
    End Function

    Private Function RetryRejectedCall(hTaskCallee As IntPtr, dwTickCount As Integer, dwRejectType As Integer) As Integer Implements IOleMessageFilter.RetryRejectedCall
        ' SERVERCALL_RETRYLATER(2) 또는 REJECTED(1): 2분까지 0.1초 간격으로 다시
        If (dwRejectType = 2 OrElse dwRejectType = 1) AndAlso dwTickCount < 120000 Then Return 100
        Return -1
    End Function

    Private Function MessagePending(hTaskCallee As IntPtr, dwTickCount As Integer, dwPendingType As Integer) As Integer Implements IOleMessageFilter.MessagePending
        Return 2 ' PENDINGMSG_WAITDEFPROCESS
    End Function

    <DllImport("Ole32.dll")>
    Private Shared Function CoRegisterMessageFilter(newFilter As IOleMessageFilter, ByRef oldFilter As IOleMessageFilter) As Integer
    End Function
End Class

<ComImport(), Guid("00000016-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)>
Public Interface IOleMessageFilter
    <PreserveSig> Function HandleInComingCall(dwCallType As Integer, hTaskCaller As IntPtr, dwTickCount As Integer, lpInterfaceInfo As IntPtr) As Integer
    <PreserveSig> Function RetryRejectedCall(hTaskCallee As IntPtr, dwTickCount As Integer, dwRejectType As Integer) As Integer
    <PreserveSig> Function MessagePending(hTaskCallee As IntPtr, dwTickCount As Integer, dwPendingType As Integer) As Integer
End Interface
