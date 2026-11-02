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
