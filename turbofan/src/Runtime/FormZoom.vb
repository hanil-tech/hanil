' 창 크기를 마우스로 늘리면 안의 칸·글자·그림이 같은 비율로 커진다.
' 마지막으로 쓴 배율은 기억해 두었다가 다음에 열 때(다른 창도) 그 크기로 연다.
Imports System.Drawing
Imports System.Windows.Forms
Imports Microsoft.Win32

Friend Class FormZoom
    Private Const RegKey As String = "Software\Hanil\TurboFanDesign"

    Private ReadOnly form As Form
    Private ReadOnly baseClient As Size
    Private ReadOnly baseBounds As New Dictionary(Of Control, Rectangle)
    Private ReadOnly baseFonts As New Dictionary(Of Control, Font)
    Private ReadOnly fontCache As New Dictionary(Of String, Font)
    Private applying As Boolean
    Private ready As Boolean

    ''' <summary>모든 창이 함께 쓰는 배율 (1 = 원본 크기).</summary>
    Friend Shared Property Zoom As Double = LoadZoom()

    Friend Sub New(f As Form)
        form = f
        baseClient = f.ClientSize
        Record(f)
        f.FormBorderStyle = FormBorderStyle.Sizable
        f.MaximizeBox = True
        ' 원본 크기보다 작게는 줄이지 않는다
        f.MinimumSize = f.Size
        AddHandler f.Resize, AddressOf OnResize
        AddHandler f.ResizeEnd, Sub() SaveZoom()
    End Sub

    Private Sub Record(parent As Control)
        For Each c As Control In parent.Controls
            baseBounds(c) = c.Bounds
            baseFonts(c) = c.Font
            Dim pb = TryCast(c, PictureBox)
            If pb IsNot Nothing Then pb.SizeMode = PictureBoxSizeMode.Zoom
            Record(c)
        Next
    End Sub

    ''' <summary>창을 처음 띄울 때: 기억해 둔 배율로 연다 (화면보다 크면 화면에 맞춘다).</summary>
    Friend Sub ApplyInitialSize()
        Dim area = Screen.FromControl(form).WorkingArea
        Dim chrome = form.Size - form.ClientSize
        Dim z = Zoom
        z = Math.Min(z, (area.Width - chrome.Width) / CDbl(baseClient.Width))
        z = Math.Min(z, (area.Height - chrome.Height) / CDbl(baseClient.Height))
        z = Math.Max(1.0, z)
        form.ClientSize = New Size(CInt(baseClient.Width * z), CInt(baseClient.Height * z))
        form.Location = New Point(area.Left + Math.Max(0, (area.Width - form.Width) \ 2), area.Top + Math.Max(0, (area.Height - form.Height) \ 2))
        ready = True
        Apply()
    End Sub

    Private Sub OnResize(sender As Object, e As EventArgs)
        If Not ready OrElse form.WindowState = FormWindowState.Minimized Then Return
        Apply()
        If form.WindowState = FormWindowState.Normal Then Zoom = CurrentFactor()
    End Sub

    Private Function CurrentFactor() As Double
        Dim fx = form.ClientSize.Width / CDbl(baseClient.Width)
        Dim fy = form.ClientSize.Height / CDbl(baseClient.Height)
        Return Math.Max(1.0, Math.Min(fx, fy))
    End Function

    Private Sub Apply()
        If applying Then Return
        applying = True
        Try
            Dim z = CurrentFactor()
            ' 가로세로 비율이 다르면 가운데에 둔다
            Dim ox = CInt((form.ClientSize.Width - baseClient.Width * z) / 2)
            Dim oy = CInt((form.ClientSize.Height - baseClient.Height * z) / 2)
            form.SuspendLayout()
            For Each kv In baseBounds
                Dim c = kv.Key
                Dim r = kv.Value
                Dim isTop = c.Parent Is form
                c.Font = ScaledFont(baseFonts(c), z)
                c.Bounds = New Rectangle(CInt(r.X * z) + If(isTop, ox, 0), CInt(r.Y * z) + If(isTop, oy, 0),
                                         CInt(r.Width * z), CInt(r.Height * z))
            Next
            form.ResumeLayout(True)
        Finally
            applying = False
        End Try
    End Sub

    Private Function ScaledFont(f As Font, z As Double) As Font
        Dim size = CSng(Math.Round(f.SizeInPoints * z * 4) / 4)
        If Math.Abs(z - 1) < 0.001 Then Return f
        Dim key = f.FontFamily.Name & "|" & size & "|" & CInt(f.Style)
        Dim cached As Font = Nothing
        If Not fontCache.TryGetValue(key, cached) Then
            cached = New Font(f.FontFamily, size, f.Style, GraphicsUnit.Point)
            fontCache(key) = cached
        End If
        Return cached
    End Function

    Private Shared Function LoadZoom() As Double
        Try
            Using k = Registry.CurrentUser.OpenSubKey(RegKey)
                Dim v = k?.GetValue("Zoom")
                If v IsNot Nothing Then
                    Dim d As Double
                    If Double.TryParse(CStr(v), Globalization.NumberStyles.Float, Globalization.CultureInfo.InvariantCulture, d) AndAlso d >= 1 AndAlso d <= 4 Then Return d
                End If
            End Using
        Catch
        End Try
        Return 1.0
    End Function

    Friend Shared Sub SaveZoom()
        Try
            Using k = Registry.CurrentUser.CreateSubKey(RegKey)
                k.SetValue("Zoom", Zoom.ToString("0.###", Globalization.CultureInfo.InvariantCulture))
            End Using
        Catch
        End Try
    End Sub
End Class
