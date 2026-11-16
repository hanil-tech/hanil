' 원본 VBA 폼(MSForms)과 같은 이름의 속성·메서드·이벤트를 가진 윈도우 컨트롤.
' 원본 코드(.Caption, .Value, .AddItem, .SetFocus, .SelStart ...)를 그대로 쓰기 위한 껍데기다.
'
' 이벤트는 원본 이름과 같은 뜻으로 따로 낸다:
'   VbClick   — 단추 누름 / 옵션 단추가 선택됨 / 콤보에서 항목을 고름
'   VbChange  — 값이 바뀜
'   VbEnter   — 포커스가 들어옴
'   VbExit    — 포커스가 나감
'   VbKeyDown — 키 누름
' 폼을 만드는 동안(디자인 값 넣는 동안)에는 내지 않는다. 원본도 그때는 이벤트가 없다.
Imports System.ComponentModel
Imports System.Drawing
Imports System.Windows.Forms

Friend Module MsControlHelpers
    ''' <summary>포커스 이벤트 처리 중인지. 이때 포커스를 옮기면 WinForms 가 꼬일 수 있어 미룬다.</summary>
    Friend FocusEventDepth As Integer

    Friend Function IsLoading(c As Control) As Boolean
        Dim f = TryCast(c.FindForm(), MForm)
        If f IsNot Nothing Then Return f.IsInitializing
        ' 아직 폼에 붙지 않은 컨트롤 = 폼을 만드는 중 (디자인 값 넣는 중)
        Return MForm.ConstructionDepth > 0
    End Function

    Private pendingFocus As Control

    ''' <summary>
    ''' 원본의 .SetFocus.
    ''' 포커스 이벤트(Enter/Exit) 안에서 포커스를 옮기면 WinForms 가 꼬이므로 이벤트가 끝난 뒤로 미룬다.
    ''' 이때 처음 요청한 곳으로 간다. 예: 원본 txtD2no_1_Enter 는 입력 오류면 풍량 칸으로 보내고,
    ''' 끝에서 다시 자기 자신(txtD2no_1)을 SetFocus 한다. 자기 자신 요청은 이미 거기 있으니 무시해야
    ''' "오류 메시지 → 다시 들어옴 → 오류 메시지" 가 끝없이 반복되지 않는다.
    ''' </summary>
    Friend Sub VbSetFocus(c As Control)
        If FocusEventDepth = 0 OrElse Not c.IsHandleCreated Then
            c.Focus()
            Return
        End If
        Dim f = c.FindForm()
        If pendingFocus Is Nothing AndAlso f IsNot Nothing AndAlso f.ActiveControl Is c Then Return
        If pendingFocus IsNot Nothing Then Return
        pendingFocus = c
        c.BeginInvoke(New Action(Sub()
                                     Dim target = pendingFocus
                                     pendingFocus = Nothing
                                     If target IsNot Nothing AndAlso target.CanFocus Then target.Focus()
                                 End Sub))
    End Sub

    ''' <summary>OLE 색(&H8000000F 같은 시스템 색 포함)을 Color 로.</summary>
    Public Function OleColor(value As Object) As Color
        If TypeOf value Is Color Then Return CType(value, Color)
        Dim l As Long = CLng(value)
        If l > Integer.MaxValue Then l -= 4294967296L
        Return ColorTranslator.FromOle(CInt(l))
    End Function
End Module

Public Class KeyDownVbEventArgs
    Inherits EventArgs
    Public Property KeyCode As Integer
    Public Property Shift As Integer
End Class

Public Class MTextBox
    Inherits TextBox

    Public Event VbChange As EventHandler
    Public Event VbEnter As EventHandler
    Public Event VbExit As EventHandler
    Public Event VbKeyDown As EventHandler(Of KeyDownVbEventArgs)

    Public Property Value As String
        Get
            Return Text
        End Get
        Set(v As String)
            Text = v
        End Set
    End Property

    Public Property Locked As Boolean
        Get
            Return [ReadOnly]
        End Get
        Set(v As Boolean)
            [ReadOnly] = v
        End Set
    End Property

    <Browsable(False), DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)>
    Public Property SelStart As Integer
        Get
            Return SelectionStart
        End Get
        Set(v As Integer)
            SelectionStart = v
        End Set
    End Property

    <Browsable(False), DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)>
    Public Property SelLength As Integer
        Get
            Return SelectionLength
        End Get
        Set(v As Integer)
            SelectionLength = v
        End Set
    End Property

    Public Sub SetFocus()
        VbSetFocus(Me)
    End Sub

    Protected Overrides Sub OnTextChanged(e As EventArgs)
        ' 한글 입력기의 전각 숫자(３００)는 바로 보통 숫자(300)로 바꾼다 — 계산에서 숫자로 읽히도록
        Dim fixedText = NormalizeDigits(Text)
        If fixedText <> Text Then
            Dim caret = SelectionStart
            Text = fixedText          ' 다시 OnTextChanged 로 들어온다
            SelectionStart = Math.Min(caret, fixedText.Length)
            Return
        End If
        MyBase.OnTextChanged(e)
        If Not IsLoading(Me) Then RaiseEvent VbChange(Me, EventArgs.Empty)
    End Sub

    Protected Overrides Sub OnEnter(e As EventArgs)
        MyBase.OnEnter(e)
        FocusEventDepth += 1
        Try
            RaiseEvent VbEnter(Me, EventArgs.Empty)
        Finally
            FocusEventDepth -= 1
        End Try
    End Sub

    Protected Overrides Sub OnLeave(e As EventArgs)
        MyBase.OnLeave(e)
        FocusEventDepth += 1
        Try
            RaiseEvent VbExit(Me, EventArgs.Empty)
        Finally
            FocusEventDepth -= 1
        End Try
    End Sub

#If Not TESTBUILD Then
    ' Enter 가 대화상자 처리로 빠지지 않고 반드시 KeyDown 으로 오게 한다.
    Protected Overrides Function IsInputKey(keyData As Keys) As Boolean
        If keyData = Keys.Enter Then Return True
        Return MyBase.IsInputKey(keyData)
    End Function

    ' 원본 안내문: "다른 계산은 (Tab Key)나 (Enter Key)를 누르세요".
    ' 값이 있는 칸에서 Tab 을 누르면 Enter 와 같은 처리(원본 KeyDown 의 KeyCode=13)를 한다.
    ' 그 처리에서 포커스를 다른 칸으로 옮겼으면 Tab 이동은 하지 않는다.
    Protected Overrides Function ProcessDialogKey(keyData As Keys) As Boolean
        If (keyData = Keys.Tab OrElse keyData = (Keys.Tab Or Keys.Shift)) AndAlso Text.Trim() <> "" AndAlso Not [ReadOnly] Then
            RaiseEvent VbKeyDown(Me, New KeyDownVbEventArgs With {.KeyCode = 13, .Shift = If(keyData.HasFlag(Keys.Shift), 1, 0)})
            If Not ContainsFocus Then Return True
        End If
        Return MyBase.ProcessDialogKey(keyData)
    End Function
#End If

    Protected Overrides Sub OnKeyDown(e As KeyEventArgs)
        MyBase.OnKeyDown(e)
        Dim a As New KeyDownVbEventArgs With {.KeyCode = e.KeyValue, .Shift = CInt(e.Modifiers) >> 16}
        RaiseEvent VbKeyDown(Me, a)
        If e.KeyCode = Keys.Enter AndAlso Not Multiline Then
            ' MSForms 처럼 Enter 는 다음 칸으로. 이벤트에서 다른 칸으로 옮겼으면 그대로 둔다.
            e.SuppressKeyPress = True
            If ContainsFocus Then
                Dim f = FindForm()
                f?.SelectNextControl(Me, (e.Modifiers And Keys.Shift) = 0, True, True, True)
            End If
        End If
    End Sub
End Class

Public Class MComboBox
    Inherits ComboBox

    Public Event VbClick As EventHandler
    Public Event VbChange As EventHandler
    Public Event VbEnter As EventHandler
    Public Event VbExit As EventHandler
    Public Event VbKeyDown As EventHandler(Of KeyDownVbEventArgs)

    Public Sub AddItem(item As Object, Optional index As Object = Nothing)
        If index Is Nothing Then Items.Add(CStr(item)) Else Items.Insert(CInt(index), CStr(item))
    End Sub

    Public Sub Clear()
        Items.Clear()
    End Sub

    Public Sub RemoveItem(index As Integer)
        Items.RemoveAt(index)
    End Sub

    Public ReadOnly Property ListCount As Integer
        Get
            Return Items.Count
        End Get
    End Property

    Public Property List(index As Integer) As String
        Get
            Return CStr(Items(index))
        End Get
        Set(v As String)
            Items(index) = v
        End Set
    End Property

    <Browsable(False), DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)>
    Public Property ListIndex As Integer
        Get
            Return SelectedIndex
        End Get
        Set(v As Integer)
            SelectedIndex = v
        End Set
    End Property

    Public Property Value As String
        Get
            Return Text
        End Get
        Set(v As String)
            Text = v
        End Set
    End Property

    Public Property Locked As Boolean

    Public Sub SetFocus()
        VbSetFocus(Me)
    End Sub

    Protected Overrides Sub OnSelectedIndexChanged(e As EventArgs)
        MyBase.OnSelectedIndexChanged(e)
        If SelectedIndex >= 0 AndAlso Not IsLoading(Me) Then RaiseEvent VbClick(Me, EventArgs.Empty)
    End Sub

    Protected Overrides Sub OnTextChanged(e As EventArgs)
        Dim fixedText = NormalizeDigits(Text)
        If fixedText <> Text Then
            Text = fixedText
            Return
        End If
        MyBase.OnTextChanged(e)
        If Not IsLoading(Me) Then RaiseEvent VbChange(Me, EventArgs.Empty)
    End Sub

    Protected Overrides Sub OnEnter(e As EventArgs)
        MyBase.OnEnter(e)
        FocusEventDepth += 1
        Try
            RaiseEvent VbEnter(Me, EventArgs.Empty)
        Finally
            FocusEventDepth -= 1
        End Try
    End Sub

    Protected Overrides Sub OnLeave(e As EventArgs)
        MyBase.OnLeave(e)
        FocusEventDepth += 1
        Try
            RaiseEvent VbExit(Me, EventArgs.Empty)
        Finally
            FocusEventDepth -= 1
        End Try
    End Sub

    Protected Overrides Sub OnKeyDown(e As KeyEventArgs)
        If Locked AndAlso e.KeyCode <> Keys.Tab Then e.SuppressKeyPress = True
        MyBase.OnKeyDown(e)
        Dim a As New KeyDownVbEventArgs With {.KeyCode = e.KeyValue, .Shift = CInt(e.Modifiers) >> 16}
        RaiseEvent VbKeyDown(Me, a)
        If e.KeyCode = Keys.Enter AndAlso Not DroppedDown Then
            e.SuppressKeyPress = True
            If ContainsFocus Then
                Dim f = FindForm()
                f?.SelectNextControl(Me, (e.Modifiers And Keys.Shift) = 0, True, True, True)
            End If
        End If
    End Sub
End Class

Public Class MOptionButton
    Inherits RadioButton

    Public Event VbClick As EventHandler
    Public Event VbChange As EventHandler

    Public Property Value As Boolean
        Get
            Return Checked
        End Get
        Set(v As Boolean)
            Checked = v
        End Set
    End Property

    Public Property Caption As String
        Get
            Return Text
        End Get
        Set(v As String)
            Text = v
        End Set
    End Property

    Public Sub SetFocus()
        VbSetFocus(Me)
    End Sub

    Protected Overrides Sub OnCheckedChanged(e As EventArgs)
        MyBase.OnCheckedChanged(e)
        If IsLoading(Me) Then Return
        RaiseEvent VbChange(Me, EventArgs.Empty)
        If Checked Then RaiseEvent VbClick(Me, EventArgs.Empty)
    End Sub
End Class

Public Class MCheckBox
    Inherits CheckBox

    Public Event VbClick As EventHandler
    Public Event VbChange As EventHandler

    Public Property Value As Boolean
        Get
            Return Checked
        End Get
        Set(v As Boolean)
            Checked = v
        End Set
    End Property

    Public Property Caption As String
        Get
            Return Text
        End Get
        Set(v As String)
            Text = v
        End Set
    End Property

    Public Sub SetFocus()
        VbSetFocus(Me)
    End Sub

    Protected Overrides Sub OnCheckedChanged(e As EventArgs)
        MyBase.OnCheckedChanged(e)
        If IsLoading(Me) Then Return
        RaiseEvent VbChange(Me, EventArgs.Empty)
        RaiseEvent VbClick(Me, EventArgs.Empty)
    End Sub
End Class

Public Class MCommandButton
    Inherits Button

    Public Event VbClick As EventHandler

    Public Property Caption As String
        Get
            Return Text
        End Get
        Set(v As String)
            Text = v
        End Set
    End Property

    Public Sub SetFocus()
        VbSetFocus(Me)
    End Sub

    Protected Overrides Sub OnClick(e As EventArgs)
        MyBase.OnClick(e)
        RaiseEvent VbClick(Me, EventArgs.Empty)
    End Sub
End Class

Public Class MLabel
    Inherits Label

    Public Event VbClick As EventHandler

    Public Property Caption As String
        Get
            Return Text
        End Get
        Set(v As String)
            Text = v
        End Set
    End Property

    Protected Overrides Sub OnClick(e As EventArgs)
        MyBase.OnClick(e)
        RaiseEvent VbClick(Me, EventArgs.Empty)
    End Sub
End Class

Public Class MFrame
    Inherits GroupBox

    Public Property Caption As String
        Get
            Return Text
        End Get
        Set(v As String)
            Text = v
        End Set
    End Property
End Class

Public Class MImage
    Inherits PictureBox

    Public Event VbClick As EventHandler

    Public Property Picture As Image
        Get
            Return Image
        End Get
        Set(v As Image)
            ' 원본: 그림 파일이 없으면 오류. 여기서는 있던 그림을 그대로 둔다.
            If v IsNot Nothing Then Image = v
        End Set
    End Property

    Protected Overrides Sub OnClick(e As EventArgs)
        MyBase.OnClick(e)
        RaiseEvent VbClick(Me, EventArgs.Empty)
    End Sub
End Class
