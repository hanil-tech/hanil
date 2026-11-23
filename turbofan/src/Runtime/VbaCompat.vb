' VBA 에만 있고 VB.NET 에는 없거나 동작이 다른 함수들.
' 원본 VBA 코드를 거의 그대로 옮겨 오기 위해 같은 이름으로 둔다.
' (같은 이름의 Microsoft.VisualBasic 함수보다 이 모듈이 먼저 찾아진다.)
Imports System.Globalization
Imports System.IO
Imports System.Text.RegularExpressions

Public Module VbaCompat

    ' ---- 수학 함수 (VBA 이름) ----
    Public Function Sqr(x As Double) As Double
        If x < 0 Then Throw New ArgumentException("Sqr 에 음수가 들어왔습니다: " & x)
        Return Math.Sqrt(x)
    End Function
    Public Function Atn(x As Double) As Double
        Return Math.Atan(x)
    End Function
    Public Function Sgn(x As Double) As Integer
        Return Math.Sign(x)
    End Function
    Public Function Log(x As Double) As Double
        If x <= 0 Then Throw New ArgumentException("Log 에 0 이하 값이 들어왔습니다: " & x)
        Return Math.Log(x)
    End Function
    Public Function Exp(x As Double) As Double
        Return Math.Exp(x)
    End Function
    Public Function Sin(x As Double) As Double
        Return Math.Sin(x)
    End Function
    Public Function Cos(x As Double) As Double
        Return Math.Cos(x)
    End Function
    Public Function Tan(x As Double) As Double
        Return Math.Tan(x)
    End Function
    Public Function Abs(x As Double) As Double
        Return Math.Abs(x)
    End Function
    ' VBA Round 는 "은행가 반올림"(짝수 쪽) — Math.Round 기본값과 같다.
    Public Function Round(x As Double, Optional digits As Integer = 0) As Double
        Return Math.Round(x, digits)
    End Function

    ' ---- IsNumeric / Val: 한글 입력기의 전각 숫자(３００, －, ．)도 숫자로 ----
    ' 원본(VBA, 한글 윈도우)은 전각 숫자도 숫자로 받았다. .NET 은 받지 않아서
    ' "300" 을 넣었는데 "숫자가 아닙니다" 가 나올 수 있었다.
    Public Function NormalizeDigits(s As String) As String
        If s Is Nothing Then Return ""
        Dim sb As New Text.StringBuilder(s.Length)
        For Each ch In s
            Select Case AscW(ch)
                Case &HFF10 To &HFF19 : sb.Append(ChrW(AscW(ch) - &HFF10 + 48))
                Case &HFF0E : sb.Append("."c)
                Case &HFF0D, &H2212 : sb.Append("-"c)
                Case &HFF0B : sb.Append("+"c)
                Case &HFF0C : sb.Append(","c)
                Case &H3000, &HA0, &H2000 To &H200A : sb.Append(" "c)
                Case Else
                    ' 보이지 않는 글자(폭 없는 공백, 방향 표시, 제어 문자 등)는 버린다
                    Dim cat = Char.GetUnicodeCategory(ch)
                    If cat = Globalization.UnicodeCategory.Format OrElse cat = Globalization.UnicodeCategory.Control Then Continue For
                    sb.Append(ch)
            End Select
        Next
        Return sb.ToString()
    End Function

    Public Function IsNumeric(value As Object) As Boolean
        If TypeOf value Is String Then
            Dim ok = Information.IsNumeric(NormalizeDigits(CStr(value)).Trim())
            LastNonNumeric = If(ok, Nothing, CStr(value))
            Return ok
        End If
        Return Information.IsNumeric(value)
    End Function

    ''' <summary>마지막으로 숫자가 아니라고 판단한 글자 (오류 창에 그대로 보여 주기 위함).</summary>
    Friend LastNonNumeric As String

    ''' <summary>"[100]  (31 30 30)" 처럼 글자와 문자 코드를 보여 준다.</summary>
    Public Function DescribeText(s As String) As String
        If s Is Nothing Then Return "(없음)"
        Return "[" & s & "]  (" & String.Join(" ", s.Select(Function(c) Hex(AscW(c)))) & ")"
    End Function

#If Not TESTBUILD Then
    ''' <summary>
    ''' 원본 MsgBox 그대로. 다만 "숫자가 아닙니다" 오류에는 실제로 칸에 들어 있던 글자와 문자 코드를 덧붙인다
    ''' (화면에는 숫자로 보이는데 오류가 나는 경우 원인을 알 수 있게).
    ''' </summary>
    Public Function MsgBox(Prompt As Object, Optional Buttons As MsgBoxStyle = MsgBoxStyle.OkOnly, Optional Title As Object = Nothing) As MsgBoxResult
        Dim text = CStr(Prompt)
        If text IsNot Nothing AndAlso text.Contains("숫자가 아닙니다") AndAlso LastNonNumeric IsNot Nothing Then
            text &= vbCrLf & vbCrLf & "입력된 값: " & DescribeText(LastNonNumeric)
        End If
        Return Interaction.MsgBox(text, Buttons, Title)
    End Function
#End If

    Public Function Val(value As Object) As Double
        If value Is Nothing Then Return 0
        If TypeOf value Is String Then Return Conversion.Val(NormalizeDigits(CStr(value)))
        Return Conversion.Val(value)
    End Function

    ' ---- Input #n, 변수: 원본(VBA)처럼 숫자 변수에 숫자가 아닌 값(예: fandata.dat 첫 줄 "Ns,ku,...")이
    '      오면 0 으로 읽는다. .NET 의 FileSystem.Input 은 여기서 오류가 난다.
    Public Sub Input(fileNumber As Integer, ByRef value As Double)
        Dim s As String = Nothing
        FileSystem.Input(fileNumber, s)
        s = NormalizeDigits(If(s, "")).Trim()
        value = If(s <> "" AndAlso Information.IsNumeric(s), CDbl(s), 0.0)
    End Sub
    Public Sub Input(fileNumber As Integer, ByRef value As Integer)
        Dim d As Double
        Input(fileNumber, d)
        value = CInt(d)
    End Sub
    Public Sub Input(fileNumber As Integer, ByRef value As String)
        FileSystem.Input(fileNumber, value)
    End Sub
    Public Sub Input(fileNumber As Integer, ByRef value As Object)
        Dim s As String = Nothing
        FileSystem.Input(fileNumber, s)
        value = s
    End Sub

    ' ---- Str: 숫자 앞에 공백(양수) — 문자열 숫자도 받는다 ----
    Public Function Str(value As Object) As String
        Dim d As Double
        If TypeOf value Is String Then
            If Not Double.TryParse(CStr(value), NumberStyles.Float, CultureInfo.InvariantCulture, d) Then
                d = Conversion.Val(CStr(value))
            End If
            Return Conversion.Str(d)
        End If
        If value Is Nothing Then Return " 0"
        Return Conversion.Str(value)
    End Function

    ' ---- Format: VBA 의 숫자·날짜 서식 ----
    Public Function Format(value As Object, Optional fmt As String = "") As String
        If value Is Nothing Then value = 0
        If TypeOf value Is DateTime Then
            Return FormatDate(CType(value, DateTime), fmt)
        End If
        Dim num As Double
        Dim isNum As Boolean = False
        If TypeOf value Is String Then
            Dim s As String = CStr(value).Trim()
            s = NormalizeDigits(s).Trim()
            If s <> "" AndAlso Information.IsNumeric(s) Then
                num = CDbl(s) : isNum = True
            Else
                Return CStr(value)
            End If
        ElseIf TypeOf value Is Boolean Then
            Return If(CBool(value), "True", "False")
        Else
            Try
                num = Convert.ToDouble(value, CultureInfo.CurrentCulture) : isNum = True
            Catch
                Return CStr(value)
            End Try
        End If
        If fmt = "" Then
            Return Conversion.Str(num).Trim()
        End If
        If Double.IsNaN(num) OrElse Double.IsInfinity(num) Then Return ""
        Return num.ToString(fmt, CultureInfo.CurrentCulture)
    End Function

    Private Function FormatDate(d As DateTime, fmt As String) As String
        If fmt = "" Then Return d.ToString(CultureInfo.CurrentCulture)
        ' VBA: Y/D 대문자 허용, .NET: 소문자만
        Dim f As String = Regex.Replace(fmt, "Y+", Function(m) New String("y"c, m.Length))
        f = Regex.Replace(f, "D+", Function(m) New String("d"c, m.Length))
        ' 한 글자 서식("M" 등)이 .NET 표준 서식으로 읽히지 않게
        If f.Length = 1 Then f = "%" & f
        ' 한글 등 문자는 .NET 에서도 그대로 나온다. 마침표/공백도 리터럴.
        Return d.ToString(f, CultureInfo.CurrentCulture)
    End Function

    ' ---- 배열 복사: VBA 는 배열·Variant 를 대입하면 복사한다 ----
    Public Function VbCopy(value As Object) As Object
        Dim arr = TryCast(value, Array)
        If arr IsNot Nothing Then Return arr.Clone()
        Return value
    End Function

    ' ---- 그림 불러오기: 파일이 없으면 Nothing (원본처럼 멈추지 않게) ----
    Public Function LoadPicture(path As String) As System.Drawing.Image
        Try
            If File.Exists(path) Then
                Using fs As New FileStream(path, FileMode.Open, FileAccess.Read)
                    Return New System.Drawing.Bitmap(System.Drawing.Image.FromStream(fs))
                End Using
            End If
        Catch
        End Try
#If Not TESTBUILD Then
        ' 방향 그림(Pics\RH-L.bmp 등)이 없으면 같은 모양으로 그려서 보여 준다.
        Try
            Dim norm = path.Replace("/"c, "\"c)
            Dim dir = IO.Path.GetDirectoryName(norm)
            If dir IsNot Nothing AndAlso dir.EndsWith("\Pics", StringComparison.OrdinalIgnoreCase) Then
                Return DirectionPicture.Make(IO.Path.GetFileNameWithoutExtension(norm))
            End If
        Catch
        End Try
#End If
        Return Nothing
    End Function

    ' ---- 파일 열기 (원본은 shell32 ShellExecute 를 직접 불렀다) ----
    Public Function GetDesktopWindow() As Integer
        Return 0
    End Function
    Public Function ShellExecute(hWnd As Object, op As String, file As String, params As String, dir As String, show As Object) As Integer
        Try
            If Not System.IO.File.Exists(file) Then
                MsgBox("파일을 찾을 수 없습니다." & vbCrLf & file, MsgBoxStyle.Exclamation, "파일 없음")
                Return 2
            End If
            Process.Start(New ProcessStartInfo(file) With {.UseShellExecute = True})
            Return 42
        Catch ex As Exception
            MsgBox("파일을 열 수 없습니다." & vbCrLf & file & vbCrLf & ex.Message, MsgBoxStyle.Exclamation)
            Return 0
        End Try
    End Function

    Public Sub DoEvents()
        System.Windows.Forms.Application.DoEvents()
    End Sub

End Module

''' <summary>VBA Collection 과 같게 동작하되, 넣을 때 배열을 복사한다 (VBA 와 같은 의미).</summary>
Public Class VBCollection
    Implements IEnumerable

    Private ReadOnly inner As New Microsoft.VisualBasic.Collection()

    Public Sub Add(item As Object, Optional key As String = Nothing, Optional before As Object = Nothing, Optional after As Object = Nothing)
        inner.Add(VbCopy(item), key, before, after)
    End Sub

    Default Public ReadOnly Property Item(index As Object) As Object
        Get
            If TypeOf index Is String Then Return inner.Item(CStr(index))
            Return inner.Item(CInt(index))
        End Get
    End Property

    Public ReadOnly Property Count As Integer
        Get
            Return inner.Count
        End Get
    End Property

    Public Sub Remove(index As Object)
        If TypeOf index Is String Then inner.Remove(CStr(index)) Else inner.Remove(CInt(index))
    End Sub

    Public Function GetEnumerator() As IEnumerator Implements IEnumerable.GetEnumerator
        Return inner.GetEnumerator()
    End Function
End Class

Public Module ResourceImages
    ''' <summary>폼에 들어 있던 그림(원본 .dvb 에서 꺼낸 것)을 읽는다.</summary>
    Public Function LoadResourceImage(name As String) As System.Drawing.Image
        Dim s = Reflection.Assembly.GetExecutingAssembly().GetManifestResourceStream(name)
        If s Is Nothing Then Return Nothing
        Return System.Drawing.Image.FromStream(s)
    End Function
End Module
