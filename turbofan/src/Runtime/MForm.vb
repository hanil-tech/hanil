' 원본 VBA UserForm 과 같은 사용법의 창.
'   frmX.Show 1   → 이 창을 띄운다 (다른 창은 원본 코드가 직접 Hide 한다)
'   UserForm_Initialize → 창을 처음 만들 때
'   UserForm_Activate   → Show 할 때마다
' 원본은 창 하나만 보이는 "모달" 흐름이었다. 여기서는 창들을 한 메시지 루프에서
' 차례로 보여 주기만 하므로, 원본 코드의 흐름(Hide → 다음 창 Show)이 그대로 맞는다.
Imports System.Windows.Forms

Public Class MForm
    Inherits Form

    ''' <summary>디자인 값을 넣는 동안 true. 이때는 컨트롤 이벤트를 내지 않는다.</summary>
    Friend IsInitializing As Boolean

    ''' <summary>지금 만들어지고 있는 폼 수.</summary>
    Friend Shared ConstructionDepth As Integer

    Public Sub New()
        IsInitializing = True
        ConstructionDepth += 1
        StartPosition = FormStartPosition.CenterScreen
        FormBorderStyle = FormBorderStyle.FixedDialog
        MaximizeBox = False
        MinimizeBox = True
        ShowInTaskbar = True
        KeyPreview = False
        Icon = AppIcon
    End Sub

    Public Shared AppIcon As Drawing.Icon

    Public Property Caption As String
        Get
            Return Text
        End Get
        Set(v As String)
            Text = v
        End Set
    End Property

    ''' <summary>폼 생성자 끝에서 부른다: 디자인 값 넣기가 끝났다.</summary>
    Protected Sub EndInitialize()
        IsInitializing = False
        ConstructionDepth -= 1
    End Sub

    Private initialized As Boolean

    ''' <summary>
    ''' 원본의 UserForm_Initialize. 필요한 폼이 Overrides 한다.
    ''' 원본(VBA)에서는 폼의 기본 인스턴스가 이미 있는 상태에서 불렸다. 생성자 안에서 부르면
    ''' 그 안의 코드가 frmInput.xxx 를 찾다가 아직 없는 인스턴스를 또 만들려 하므로, 처음 Show 할 때 부른다.
    ''' </summary>
    Protected Overridable Sub UserForm_Initialize()
    End Sub

    ''' <summary>원본의 UserForm_Activate. 필요한 폼이 Overrides 한다.</summary>
    Protected Overridable Sub UserForm_Activate()
    End Sub

    ''' <summary>원본의 UserForm.Show [modal]. 인자는 원본과의 호환용이며 쓰지 않는다.</summary>
    Public Shadows Sub Show(Optional modal As Object = Nothing)
        If Not initialized Then
            initialized = True
            UserForm_Initialize()
        End If
        If Not Visible Then
            MyBase.Show()
        End If
        Activate()
        UserForm_Activate()
    End Sub

    ' 창의 [X] 를 누르면 원본처럼 프로그램이 끝난다.
    Protected Overrides Sub OnFormClosing(e As FormClosingEventArgs)
        MyBase.OnFormClosing(e)
        If e.CloseReason = CloseReason.UserClosing Then
            e.Cancel = True
            Program.QuitApplication()
        End If
    End Sub
End Class
