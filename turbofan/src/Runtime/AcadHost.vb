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
    ''' <summary>이번 도면 작업에서 사용자가 CAD 연결을 취소했으면 true — 다시 묻지 않는다.</summary>
    Private _declined As Boolean

    ''' <summary>
    ''' 지원하는 CAD. 모두 AutoCAD 와 같은 COM(ActiveX) 명령 체계를 갖고 있어 같은 코드로 그린다.
    ''' </summary>
    Public Class CadProduct
        Public Name As String
        Public ProgIds As String()
        Public LinFiles As String()
        Public Sub New(name As String, progIds As String(), linFiles As String())
            Me.Name = name : Me.ProgIds = progIds : Me.LinFiles = linFiles
        End Sub
        Public Overrides Function ToString() As String
            Return Name
        End Function
    End Class

    Public ReadOnly CadProducts As CadProduct() = {
        New CadProduct("AutoCAD", {"AutoCAD.Application"}, {"acadiso.lin", "acad.lin"}),
        New CadProduct("ZWCAD", {"ZWCAD.Application", "ZwCAD.Application"}, {"zwcadiso.lin", "zwcad.lin"}),
        New CadProduct("GstarCAD", {"GCAD.Application", "GstarCAD.Application"}, {"gcadiso.lin", "gcad.lin"}),
        New CadProduct("BricsCAD", {"BricscadApp.AcadApplication", "BricsCAD.Application"}, {"iso.lin", "default.lin", "bricscad.lin"}),
        New CadProduct("progeCAD / IntelliCAD", {"progeCAD.Application", "Icad.Application", "IntelliCAD.Application"}, {"icadiso.lin", "icad.lin"})
    }

    ''' <summary>지금 붙어 있는 CAD (없으면 Nothing).</summary>
    Public CurrentCad As CadProduct

    ''' <summary>원본 VBA 의 ThisDrawing — 지금 CAD 에 열려 있는 도면.</summary>
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

    ''' <summary>붙어 있는 CAD 프로그램. 없으면 (이번 작업에서 아직 취소하지 않았다면) 찾거나 고르게 한다.</summary>
    Public ReadOnly Property AcadApplication As Object
        Get
            If IsAlive() Then Return _app
            If _declined Then Throw New AutoCadNotAvailableException("CAD 연결을 취소했습니다.")
            If Not Connect() Then
                _declined = True
                Throw New AutoCadNotAvailableException("CAD 연결을 취소했습니다.")
            End If
            Return _app
        End Get
    End Property

    Private Function IsAlive() As Boolean
        If _app Is Nothing Then Return False
        Try
            Dim unused = _app.Visible
            Return True
        Catch
            _app = Nothing
            _doc = Nothing
            CurrentCad = Nothing
            Return False
        End Try
    End Function

    ''' <summary>
    ''' 도면 단추를 누를 때 먼저 부른다. CAD 에 붙어 있거나 붙으면 True.
    ''' 취소하면 False — 그 작업은 바로 멈춘다 (원본 도면 코드는 오류를 무시하고 계속 진행하므로,
    ''' 여기서 막지 않으면 줄마다 "CAD 를 찾지 못했습니다" 를 다시 묻게 된다).
    ''' </summary>
    Public Function EnsureCad() As Boolean
        If TestDocument IsNot Nothing Then Return True
        _declined = False
        If IsAlive() Then Return True
        If Connect() Then Return True
        _declined = True
        Return False
    End Function

    Public ReadOnly Property IsAutoCadConnected As Boolean
        Get
            Return _app IsNot Nothing
        End Get
    End Property

    Public ReadOnly Property CadName As String
        Get
            Return If(CurrentCad?.Name, "CAD")
        End Get
    End Property

    ''' <summary>AutoCAD·도면 연결을 놓는다 (프로그램을 끝낼 때).</summary>
    Public Sub ReleaseAutoCad()
        For Each o In {_doc, _app}
            Try
                If o IsNot Nothing AndAlso Marshal.IsComObject(o) Then Marshal.FinalReleaseComObject(o)
            Catch
            End Try
        Next
        _doc = Nothing
        _app = Nothing
        CurrentCad = Nothing
        MessageFilter.Unregister()
    End Sub

    ''' <summary>켜져 있는 지원 CAD 들.</summary>
    Public Function FindRunningCads() As List(Of KeyValuePair(Of CadProduct, Object))
        Dim found As New List(Of KeyValuePair(Of CadProduct, Object))
#If NETFRAMEWORK Then
        For Each p In CadProducts
            For Each id In p.ProgIds
                Try
                    Dim o = Marshal.GetActiveObject(id)
                    If o IsNot Nothing Then
                        found.Add(New KeyValuePair(Of CadProduct, Object)(p, o))
                        Exit For
                    End If
                Catch
                End Try
            Next
        Next
#End If
        Return found
    End Function

    ''' <summary>이 PC 에 설치된(등록된) 지원 CAD 와 그 ProgID.</summary>
    Public Function FindInstalledCads() As List(Of KeyValuePair(Of CadProduct, String))
        Dim found As New List(Of KeyValuePair(Of CadProduct, String))
        For Each p In CadProducts
            For Each id In p.ProgIds
                Try
                    If Type.GetTypeFromProgID(id) IsNot Nothing Then
                        found.Add(New KeyValuePair(Of CadProduct, String)(p, id))
                        Exit For
                    End If
                Catch
                End Try
            Next
        Next
        Return found
    End Function

    Private Function Connect() As Boolean
        MessageFilter.Register()
        Dim preferred = LoadCadSetting()
        Do
            Dim running = FindRunningCads()
            If running.Count = 1 Then
                Return UseCad(running(0).Key, running(0).Value)
            End If
            If running.Count > 1 Then
                Dim pref = running.FirstOrDefault(Function(r) r.Key.Name = preferred)
                If pref.Key IsNot Nothing Then Return UseCad(pref.Key, pref.Value)
#If Not TESTBUILD Then
                Dim pick = CadPicker.ChooseRunning(running.Select(Function(r) r.Key).ToList())
                If pick Is Nothing Then Return False
                Dim chosen = running.First(Function(r) r.Key Is pick)
                Return UseCad(chosen.Key, chosen.Value)
#Else
                Return UseCad(running(0).Key, running(0).Value)
#End If
            End If
#If Not TESTBUILD Then
            ' 켜진 CAD 가 없다: 설치된 것 중 골라 실행하거나, 직접 켠 뒤 다시 찾는다.
            Dim result = CadPicker.ChooseToLaunch(FindInstalledCads(), preferred)
            If result.Action = CadPicker.PickAction.Cancel Then Return False
            If result.Action = CadPicker.PickAction.Retry Then Continue Do
            Try
                Dim app As Object
                Using New WaitCursor()
                    app = Interaction.CreateObject(result.ProgId)
                    app.Visible = True
                End Using
                Return UseCad(result.Product, app)
            Catch ex As Exception
                MsgBox(result.Product.Name & " 을(를) 실행하지 못했습니다." & vbCrLf & ex.Message, MsgBoxStyle.Exclamation, "CAD 연결")
            End Try
#Else
            Return False
#End If
        Loop
    End Function

    Private Function UseCad(p As CadProduct, app As Object) As Boolean
        _app = app
        _doc = Nothing
        CurrentCad = p
        SaveCadSetting(p.Name)
        Return True
    End Function

    Private Function LoadCadSetting() As String
        Try
            Using k = Registry.CurrentUser.OpenSubKey("Software\Hanil\TurboFanDesign")
                Return TryCast(k?.GetValue("Cad"), String)
            End Using
        Catch
            Return Nothing
        End Try
    End Function

    Private Sub SaveCadSetting(name As String)
        Try
            Using k = Registry.CurrentUser.CreateSubKey("Software\Hanil\TurboFanDesign")
                k.SetValue("Cad", name)
            End Using
        Catch
        End Try
    End Sub

    ''' <summary>
    ''' 원본의 ThisDrawing.Linetypes.Load "CENTER", "acadiso.lin".
    ''' 선 종류 파일 이름이 CAD 마다 달라서(zwcadiso.lin, gcadiso.lin ...) 안 되면 다른 이름으로 다시 해 본다.
    ''' 끝내 못 불러와도 도면 작업은 계속한다 (그 선만 실선으로 나옴).
    ''' </summary>
    Public Sub LoadLinetype(name As String, file As String)
        Dim files As New List(Of String) From {file}
        If CurrentCad IsNot Nothing Then files.AddRange(CurrentCad.LinFiles)
        For Each p In CadProducts
            files.AddRange(p.LinFiles)
        Next
        For Each f In files.Distinct(StringComparer.OrdinalIgnoreCase)
            Try
                ThisDrawing.Linetypes.Load(name, f)
                Return
            Catch ex As AutoCadNotAvailableException
                Throw
            Catch
            End Try
        Next
    End Sub

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

    ''' <summary>
    ''' 프로그램을 끝내기 전에 꼭 부른다. 등록해 둔 채 끝내면 .NET 이 내려간 뒤에 윈도우가 이 필터를 불러서
    ''' "unknown software exception (0xc0020001)" 오류 창이 뜬다.
    ''' </summary>
    Public Shared Sub Unregister()
        If Not registered Then Return
        Dim old As IOleMessageFilter = Nothing
        Try
            CoRegisterMessageFilter(Nothing, old)
        Catch
        End Try
        registered = False
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
