' 입력 창의 "회전 및 방향" 그림.
' 원본은 방향마다 ALISP\Turbo Fan Design\Pics\<방향>.bmp (예: RH-L.bmp) 를 읽었다.
' 그 파일이 없으면 여기서 같은 모양으로 그린다:
'   초록 = 케이싱, 주황 = 회전차, 노란 화살표 = 토출 방향, M = 모터 위치 (흡입구에서 볼 때)
' 이름 규칙(원본 GetControlDirection): [R=시계|L=반시계][H=상부|L=좌측|R=우측][-L|-R 모터 좌/우, V벨트만]
Imports System.Drawing
Imports System.Drawing.Drawing2D

Public Module DirectionPicture

    Public Function Make(direction As String) As Image
        direction = direction.ToUpperInvariant()
        If direction.Length < 2 Then Return Nothing
        Dim cw = direction(0) = "R"c
        Dim outlet = direction(1)                     ' H, L, R
        Dim motor As Char = If(direction.Length >= 4, direction(3), " "c)

        Const W As Integer = 249, H As Integer = 201  ' 원본 그림(83x67)의 3배
        Dim bmp As New Bitmap(W, H)
        Using g = Graphics.FromImage(bmp)
            g.SmoothingMode = SmoothingMode.AntiAlias
            g.Clear(Color.White)
            Dim cx = W / 2.0F + 12, cy = H / 2.0F + 10

            ' 시계방향 기준 그림을 돌리고, 반시계면 좌우를 뒤집는다.
            ' (반시계에서 좌측 토출 = 시계 우측 토출의 거울상)
            Dim o = outlet
            If Not cw Then o = If(outlet = "L"c, "R"c, If(outlet = "R"c, "L"c, outlet))
            Dim angle = If(o = "L"c, -90.0F, If(o = "R"c, 90.0F, 0.0F))

            Dim state = g.Save()
            g.TranslateTransform(W / 2.0F, H / 2.0F)
            If Not cw Then g.ScaleTransform(-1, 1)
            g.TranslateTransform(-W / 2.0F, -H / 2.0F)
            g.TranslateTransform(cx, cy)
            g.RotateTransform(angle)

            ' 케이싱: 둥근 몸통 + 왼쪽 위로 뻗은 토출구 (시계방향, 상부 토출)
            Dim R = 62.0F
            Using green As New SolidBrush(Color.FromArgb(40, 150, 80))
                g.FillEllipse(green, -R, -R, 2 * R, 2 * R)
                g.FillRectangle(green, -R, -R - 30, 46, R + 30)
            End Using
            ' 회전차
            Using orange As New SolidBrush(Color.FromArgb(247, 148, 29))
                g.FillEllipse(orange, -40, -36, 80, 80)
            End Using
            ' 토출 화살표 (위쪽)
            Using yellow As New Pen(Color.FromArgb(255, 230, 0), 6),
                  yb As New SolidBrush(Color.FromArgb(255, 230, 0))
                g.DrawLine(yellow, -R + 23, -R + 14, -R + 23, -R - 8)
                g.FillPolygon(yb, {New PointF(-R + 23, -R - 26), New PointF(-R + 11, -R - 8), New PointF(-R + 35, -R - 8)})
            End Using
            ' 회전 방향 (회전차 위 호 화살표, 시계방향)
            Using rotPen As New Pen(Color.White, 4), wb As New SolidBrush(Color.White)
                g.DrawArc(rotPen, -24, -18, 48, 48, -160, 110)
                ' 호 끝(-50도)에서 시계방향 접선으로 화살촉
                Dim a = -50 * Math.PI / 180, ex = CSng(24 * Math.Cos(a)), ey = CSng(6 + 24 * Math.Sin(a))
                Dim tx = CSng(-Math.Sin(a)), ty = CSng(Math.Cos(a))      ' 진행 방향
                Dim nx = -ty, ny = tx
                g.FillPolygon(wb, {New PointF(ex + tx * 11, ey + ty * 11), New PointF(ex + nx * 7, ey + ny * 7), New PointF(ex - nx * 7, ey - ny * 7)})
            End Using
            g.Restore(state)

            ' 모터 위치 (V벨트: 아래 왼쪽/오른쪽)
            If motor = "L"c OrElse motor = "R"c Then
                Dim mx = If(motor = "L"c, 30.0F, W - 30.0F), my = H - 30.0F
                Using gray As New SolidBrush(Color.FromArgb(200, 200, 200)),
                      edge As New Pen(Color.FromArgb(120, 120, 120), 2),
                      f As New Font("Arial", 20, FontStyle.Bold),
                      sf As New StringFormat With {.Alignment = StringAlignment.Center, .LineAlignment = StringAlignment.Center}
                    g.FillEllipse(gray, mx - 24, my - 24, 48, 48)
                    g.DrawEllipse(edge, mx - 24, my - 24, 48, 48)
                    g.DrawString("M", f, Brushes.Black, mx, my + 1, sf)
                End Using
            End If
        End Using
        Return bmp
    End Function

End Module
