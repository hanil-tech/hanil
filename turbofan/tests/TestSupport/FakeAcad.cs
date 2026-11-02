// 시험 전용 가짜 AutoCAD 도면.
// 변환된 코드가 ThisDrawing.ModelSpace.AddLine ... 처럼 부르는 것을 받아서 기록하고,
// 교점(IntersectWith) 같은 기하 계산은 실제로 해서 돌려준다. 마지막에 SVG 로 그린다.
// 진짜 AutoCAD 와 같은 결과를 보장하지 않는다 — 변환 코드가 끝까지 오류 없이 도는지,
// 그림이 그럴듯한지를 보는 용도다.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;

namespace FakeAcad
{
    public static class Log
    {
        public static readonly List<string> Calls = new List<string>();
        public static void Add(string s) { Calls.Add(s); }
    }

    static class G
    {
        public const double Eps = 1e-9;
        public static double[] P(object o)
        {
            switch (o)
            {
                case double[] d: return new[] { d[0], d[1], d.Length > 2 ? d[2] : 0 };
                case object[] a: return new[] { Convert.ToDouble(a[0]), Convert.ToDouble(a[1]), a.Length > 2 ? Convert.ToDouble(a[2] ?? 0.0) : 0 };
                case Array arr: return new[] { Convert.ToDouble(arr.GetValue(arr.GetLowerBound(0))), Convert.ToDouble(arr.GetValue(arr.GetLowerBound(0) + 1)), 0.0 };
                case null: throw new ArgumentNullException("point", "점(배열)이 비어 있음 (Nothing)");
                default: throw new ArgumentException("점이 배열이 아님: " + o.GetType());
            }
        }
        public static double[] Coords(object o)
        {
            if (o is double[] d) return (double[])d.Clone();
            if (o is Array a) { var r = new double[a.Length]; int i = 0; foreach (var v in a) r[i++] = Convert.ToDouble(v); return r; }
            throw new ArgumentException("좌표 배열이 아님");
        }
        public static double Norm(double a) { a %= 2 * Math.PI; if (a < 0) a += 2 * Math.PI; return a; }
        public static bool OnArc(double ang, double s, double e)
        {
            ang = Norm(ang); s = Norm(s); e = Norm(e);
            if (s <= e) return ang >= s - 1e-9 && ang <= e + 1e-9;
            return ang >= s - 1e-9 || ang <= e + 1e-9;
        }
        public static string F(double v) => v.ToString("0.###", CultureInfo.InvariantCulture);
    }

    // ---- 기하 조각: 선분 / 원호 ----
    abstract class Seg { }
    class LSeg : Seg { public double[] A, B; public bool Infinite; public LSeg(double[] a, double[] b, bool inf = false) { A = a; B = b; Infinite = inf; } }
    class ASeg : Seg { public double[] C; public double R, S, E; public bool Full; public ASeg(double[] c, double r, double s, double e, bool full) { C = c; R = r; S = s; E = e; Full = full; } }

    static class Isect
    {
        public static List<double[]> Of(Seg a, Seg b)
        {
            if (a is LSeg l1 && b is LSeg l2) return LL(l1, l2);
            if (a is LSeg l && b is ASeg c) return LA(l, c);
            if (a is ASeg c2 && b is LSeg l3) return LA(l3, c2);
            return AA((ASeg)a, (ASeg)b);
        }
        static bool OnLine(LSeg l, double t) => l.Infinite || (t >= -1e-9 && t <= 1 + 1e-9);
        static List<double[]> LL(LSeg p, LSeg q)
        {
            var r = new List<double[]>();
            double dx1 = p.B[0] - p.A[0], dy1 = p.B[1] - p.A[1], dx2 = q.B[0] - q.A[0], dy2 = q.B[1] - q.A[1];
            double den = dx1 * dy2 - dy1 * dx2;
            if (Math.Abs(den) < 1e-12) return r;
            double t = ((q.A[0] - p.A[0]) * dy2 - (q.A[1] - p.A[1]) * dx2) / den;
            double u = ((q.A[0] - p.A[0]) * dy1 - (q.A[1] - p.A[1]) * dx1) / den;
            if (OnLine(p, t) && OnLine(q, u)) r.Add(new[] { p.A[0] + t * dx1, p.A[1] + t * dy1, 0 });
            return r;
        }
        static List<double[]> LA(LSeg l, ASeg c)
        {
            var r = new List<double[]>();
            double dx = l.B[0] - l.A[0], dy = l.B[1] - l.A[1];
            double fx = l.A[0] - c.C[0], fy = l.A[1] - c.C[1];
            double a = dx * dx + dy * dy, b = 2 * (fx * dx + fy * dy), cc = fx * fx + fy * fy - c.R * c.R;
            double disc = b * b - 4 * a * cc;
            if (disc < -1e-9 || a < 1e-15) return r;
            disc = Math.Max(0, disc);
            foreach (var t in disc < 1e-12 ? new[] { -b / (2 * a) } : new[] { (-b - Math.Sqrt(disc)) / (2 * a), (-b + Math.Sqrt(disc)) / (2 * a) })
            {
                if (!OnLine(l, t)) continue;
                double x = l.A[0] + t * dx, y = l.A[1] + t * dy;
                if (c.Full || G.OnArc(Math.Atan2(y - c.C[1], x - c.C[0]), c.S, c.E)) r.Add(new[] { x, y, 0 });
            }
            return r;
        }
        static List<double[]> AA(ASeg p, ASeg q)
        {
            var r = new List<double[]>();
            double dx = q.C[0] - p.C[0], dy = q.C[1] - p.C[1], d = Math.Sqrt(dx * dx + dy * dy);
            if (d < 1e-12 || d > p.R + q.R + 1e-9 || d < Math.Abs(p.R - q.R) - 1e-9) return r;
            double a = (p.R * p.R - q.R * q.R + d * d) / (2 * d);
            double h = Math.Sqrt(Math.Max(0, p.R * p.R - a * a));
            double mx = p.C[0] + a * dx / d, my = p.C[1] + a * dy / d;
            var pts = h < 1e-12 ? new[] { new[] { mx, my, 0 } } : new[] { new[] { mx + h * dy / d, my - h * dx / d, 0 }, new[] { mx - h * dy / d, my + h * dx / d, 0 } };
            foreach (var pt in pts)
            {
                bool okp = p.Full || G.OnArc(Math.Atan2(pt[1] - p.C[1], pt[0] - p.C[0]), p.S, p.E);
                bool okq = q.Full || G.OnArc(Math.Atan2(pt[1] - q.C[1], pt[0] - q.C[0]), q.S, q.E);
                if (okp && okq) r.Add(pt);
            }
            return r;
        }
    }

    // ---- 엔티티 ----
    public abstract class Entity
    {
        internal Document Doc;
        public object color { get; set; } = 256;
        public string Linetype { get; set; } = "BYLAYER";
        public double LinetypeScale { get; set; } = 1;
        public string Layer { get; set; } = "0";
        public bool Visible { get; set; } = true;
        public double Lineweight { get; set; }
        internal bool Deleted;
        public abstract string ObjectName { get; }
        public string Handle { get; } = (++counter).ToString("X");
        static int counter;
        public void Update() { }
        public void Highlight(object on) { }
        public void Delete() { Deleted = true; }
        public void Erase() { Deleted = true; }
        internal abstract List<Seg> Segs(bool extend);
        internal abstract Entity CloneRaw();
        internal abstract void Transform(Func<double[], double[]> f, bool mirror);
        public object Copy() { var c = CloneRaw(); c.Doc = Doc; c.color = color; c.Linetype = Linetype; Doc.Space.AddEntity(c); return c; }
        public void Move(object from, object to) { var a = G.P(from); var b = G.P(to); Transform(p => new[] { p[0] + b[0] - a[0], p[1] + b[1] - a[1], 0 }, false); }
        public void Rotate(object basePt, double ang)
        {
            var c = G.P(basePt); double cs = Math.Cos(ang), sn = Math.Sin(ang);
            Transform(p => new[] { c[0] + (p[0] - c[0]) * cs - (p[1] - c[1]) * sn, c[1] + (p[0] - c[0]) * sn + (p[1] - c[1]) * cs, 0 }, false);
            RotateAngles(ang);
        }
        internal virtual void RotateAngles(double a) { }
        public void ScaleEntity(object basePt, double f) { var c = G.P(basePt); Transform(p => new[] { c[0] + (p[0] - c[0]) * f, c[1] + (p[1] - c[1]) * f, 0 }, false); ScaleSize(f); }
        internal virtual void ScaleSize(double f) { }
        public object Mirror(object p1, object p2)
        {
            var a = G.P(p1); var b = G.P(p2);
            double dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy;
            var c = (Entity)Copy();
            c.Transform(p =>
            {
                double t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L;
                double fx = a[0] + t * dx, fy = a[1] + t * dy;
                return new[] { 2 * fx - p[0], 2 * fy - p[1], 0 };
            }, true);
            return c;
        }
        public object ArrayPolar(int n, double fill, object center)
        {
            var res = new List<object>();
            for (int i = 1; i < n; i++) { var c = (Entity)Copy(); c.Rotate(center, fill / (n - 1) * i); res.Add(c); }
            return res.ToArray();
        }
        public object ArrayRectangular(int rows, int cols, int levels, double dr, double dc, double dl)
        {
            var res = new List<object>();
            for (int r = 0; r < rows; r++)
                for (int c = 0; c < cols; c++)
                {
                    if (r == 0 && c == 0) continue;
                    var e = (Entity)Copy(); e.Transform(p => new[] { p[0] + c * dc, p[1] + r * dr, 0 }, false); res.Add(e);
                }
            return res.ToArray();
        }
        public object IntersectWith(object other, int ext)
        {
            var o = (Entity)other;
            var res = new List<double>();
            foreach (var a in Segs(ext == 1 || ext == 3))
                foreach (var b in o.Segs(ext == 2 || ext == 3))
                    foreach (var p in Isect.Of(a, b))
                    {
                        bool dup = false;
                        for (int k = 0; k < res.Count; k += 3) if (Math.Abs(res[k] - p[0]) < 1e-7 && Math.Abs(res[k + 1] - p[1]) < 1e-7) dup = true;
                        if (!dup) res.AddRange(p);
                    }
            return res.ToArray();
        }
        public void GetBoundingBox(ref object min, ref object max)
        {
            double x0 = double.MaxValue, y0 = double.MaxValue, x1 = double.MinValue, y1 = double.MinValue;
            foreach (var p in Samples()) { x0 = Math.Min(x0, p[0]); y0 = Math.Min(y0, p[1]); x1 = Math.Max(x1, p[0]); y1 = Math.Max(y1, p[1]); }
            min = new[] { x0, y0, 0.0 }; max = new[] { x1, y1, 0.0 };
        }
        internal IEnumerable<double[]> Samples()
        {
            foreach (var s in Segs(false))
            {
                if (s is LSeg l) { yield return l.A; yield return l.B; }
                else if (s is ASeg a)
                {
                    double span = a.Full ? 2 * Math.PI : G.Norm(a.E - a.S);
                    for (int i = 0; i <= 24; i++) { double t = a.S + span * i / 24; yield return new[] { a.C[0] + a.R * Math.Cos(t), a.C[1] + a.R * Math.Sin(t), 0 }; }
                }
            }
        }
        internal abstract void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len);
        internal string Stroke()
        {
            int c = color is int i ? i : Convert.ToInt32(color);
            string col = c switch { 1 => "#d00", 2 => "#c90", 3 => "#090", 4 => "#08a", 5 => "#00c", 6 => "#a0a", 40 => "#c60", _ => "#222" };
            string dash = Linetype != null && Linetype.ToUpperInvariant().Contains("CENTER") ? " stroke-dasharray=\"12 3 2 3\"" :
                          Linetype != null && (Linetype.ToUpperInvariant().Contains("HIDDEN") || Linetype.ToUpperInvariant().Contains("DASH")) ? " stroke-dasharray=\"4 3\"" : "";
            return $"stroke=\"{col}\" fill=\"none\" vector-effect=\"non-scaling-stroke\"{dash}";
        }
    }

    public class Line : Entity
    {
        public object StartPoint { get => (double[])s.Clone(); set => s = G.P(value); }
        public object EndPoint { get => (double[])e.Clone(); set => e = G.P(value); }
        double[] s, e;
        internal Line(double[] a, double[] b) { s = a; e = b; }
        public override string ObjectName => "AcDbLine";
        public double Length => Math.Sqrt(Math.Pow(e[0] - s[0], 2) + Math.Pow(e[1] - s[1], 2));
        public double Angle => G.Norm(Math.Atan2(e[1] - s[1], e[0] - s[0]));
        public object Delta => new[] { e[0] - s[0], e[1] - s[1], 0 };
        public object Offset(double d)
        {
            double ang = Math.Atan2(e[1] - s[1], e[0] - s[0]) - Math.PI / 2; // AutoCAD: 양수 = 오른쪽? (근사)
            var l = new Line(new[] { s[0] + d * Math.Cos(ang), s[1] + d * Math.Sin(ang), 0 }, new[] { e[0] + d * Math.Cos(ang), e[1] + d * Math.Sin(ang), 0 }) { Doc = Doc };
            Doc.Space.AddEntity(l); return new object[] { l };
        }
        internal override List<Seg> Segs(bool ext) => new List<Seg> { new LSeg(s, e, ext) };
        internal override Entity CloneRaw() => new Line((double[])s.Clone(), (double[])e.Clone());
        internal override void Transform(Func<double[], double[]> f, bool m) { s = f(s); e = f(e); }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len)
            => sb.Append($"<path d=\"M{pt(s)} L{pt(e)}\" {Stroke()}/>\n");
    }

    public class Xline : Line
    {
        internal Xline(double[] a, double[] b) : base(a, b) { }
        public override string ObjectName => "AcDbXline";
        internal override List<Seg> Segs(bool ext) { var a = G.P(StartPoint); var b = G.P(EndPoint); return new List<Seg> { new LSeg(a, b, true) }; }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len) { }
    }

    public class Arc : Entity
    {
        double[] c; double r, sa, ea;
        internal Arc(double[] c, double r, double s, double e) { this.c = c; this.r = r; sa = G.Norm(s); ea = G.Norm(e); }
        public override string ObjectName => "AcDbArc";
        public object Center { get => (double[])c.Clone(); set => c = G.P(value); }
        public double Radius { get => r; set => r = value; }
        public double StartAngle { get => sa; set => sa = G.Norm(value); }
        public double EndAngle { get => ea; set => ea = G.Norm(value); }
        public object StartPoint => new[] { c[0] + r * Math.Cos(sa), c[1] + r * Math.Sin(sa), 0 };
        public object EndPoint => new[] { c[0] + r * Math.Cos(ea), c[1] + r * Math.Sin(ea), 0 };
        public double TotalAngle => G.Norm(ea - sa);
        public double ArcLength => r * TotalAngle;
        public object Offset(double d) { var a = new Arc((double[])c.Clone(), r + d, sa, ea) { Doc = Doc }; Doc.Space.AddEntity(a); return new object[] { a }; }
        internal override List<Seg> Segs(bool ext) => new List<Seg> { new ASeg(c, r, sa, ea, ext) };
        internal override Entity CloneRaw() => new Arc((double[])c.Clone(), r, sa, ea);
        internal override void Transform(Func<double[], double[]> f, bool mirror)
        {
            var sp = f((double[])StartPoint); var ep = f((double[])EndPoint); c = f(c);
            double a1 = Math.Atan2(sp[1] - c[1], sp[0] - c[0]), a2 = Math.Atan2(ep[1] - c[1], ep[0] - c[0]);
            if (mirror) { sa = G.Norm(a2); ea = G.Norm(a1); } else { sa = G.Norm(a1); ea = G.Norm(a2); }
        }
        internal override void ScaleSize(double f) { r *= f; }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len)
        {
            double span = G.Norm(ea - sa); if (span < 1e-9) span = 2 * Math.PI;
            sb.Append($"<path d=\"M{pt((double[])StartPoint)} A{len(r)},{len(r)} 0 {(span > Math.PI ? 1 : 0)},0 {pt((double[])EndPoint)}\" {Stroke()}/>\n");
        }
    }

    public class Circle : Entity
    {
        double[] c; double r;
        internal Circle(double[] c, double r) { this.c = c; this.r = r; }
        public override string ObjectName => "AcDbCircle";
        public object Center { get => (double[])c.Clone(); set => c = G.P(value); }
        public double Radius { get => r; set => r = value; }
        public double Diameter { get => 2 * r; set => r = value / 2; }
        public double Area => Math.PI * r * r;
        public object Offset(double d) { var a = new Circle((double[])c.Clone(), r + d) { Doc = Doc }; Doc.Space.AddEntity(a); return new object[] { a }; }
        internal override List<Seg> Segs(bool ext) => new List<Seg> { new ASeg(c, r, 0, 2 * Math.PI, true) };
        internal override Entity CloneRaw() => new Circle((double[])c.Clone(), r);
        internal override void Transform(Func<double[], double[]> f, bool m) { c = f(c); }
        internal override void ScaleSize(double f) { r *= f; }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len)
        { var p = pt(c).Split(','); sb.Append($"<circle cx=\"{p[0]}\" cy=\"{p[1]}\" r=\"{len(r)}\" {Stroke()}/>\n"); }
    }

    public class Polyline : Entity
    {
        internal List<double[]> V = new List<double[]>();
        internal List<double> Bulge = new List<double>();
        readonly bool lw;
        internal Polyline(List<double[]> v, bool lw) { V = v; this.lw = lw; Bulge = v.Select(_ => 0.0).ToList(); }
        public override string ObjectName => lw ? "AcDbPolyline" : "AcDb2dPolyline";
        public bool Closed { get; set; }
        public double ConstantWidth { get; set; }
        public void SetBulge(int i, double b) { Bulge[i] = b; }
        public double GetBulge(int i) => Bulge[i];
        public object Coordinates
        {
            get { var r = new List<double>(); foreach (var p in V) { r.Add(p[0]); r.Add(p[1]); if (!lw) r.Add(0); } return r.ToArray(); }
        }
        public object Explode()
        {
            var res = new List<object>();
            foreach (var s in Segs(false))
            {
                Entity e = s is LSeg l ? new Line(l.A, l.B) : (Entity)new Arc(((ASeg)s).C, ((ASeg)s).R, ((ASeg)s).S, ((ASeg)s).E);
                e.Doc = Doc; e.color = color; Doc.Space.AddEntity(e); res.Add(e);
            }
            return res.ToArray();
        }
        public double Area
        {
            get { double a = 0; var pts = Samples().ToList(); for (int i = 0; i < pts.Count; i++) { var p = pts[i]; var q = pts[(i + 1) % pts.Count]; a += p[0] * q[1] - q[0] * p[1]; } return Math.Abs(a / 2); }
        }
        public object Offset(double d)
        {
            // 근사: 무게중심 기준으로 키우거나 줄인다 (부호는 AutoCAD 와 다를 수 있음)
            var pts = V; double cx = pts.Average(p => p[0]), cy = pts.Average(p => p[1]);
            double rad = pts.Average(p => Math.Sqrt(Math.Pow(p[0] - cx, 2) + Math.Pow(p[1] - cy, 2)));
            double f = rad > 0 ? (rad + d) / rad : 1;
            var n = new Polyline(pts.Select(p => new[] { cx + (p[0] - cx) * f, cy + (p[1] - cy) * f, 0 }).ToList(), lw) { Doc = Doc, Closed = Closed, Bulge = new List<double>(Bulge) };
            Doc.Space.AddEntity(n); return new object[] { n };
        }
        internal override List<Seg> Segs(bool ext)
        {
            var r = new List<Seg>();
            int n = V.Count, m = Closed ? n : n - 1;
            for (int i = 0; i < m; i++)
            {
                var a = V[i]; var b = V[(i + 1) % n]; double bu = Bulge[i];
                if (Math.Abs(bu) < 1e-12) { r.Add(new LSeg(a, b)); continue; }
                double th = 4 * Math.Atan(bu), chord = Math.Sqrt(Math.Pow(b[0] - a[0], 2) + Math.Pow(b[1] - a[1], 2));
                double rad = chord / (2 * Math.Sin(Math.Abs(th) / 2));
                double mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, h = Math.Sqrt(Math.Max(0, rad * rad - chord * chord / 4));
                double ux = -(b[1] - a[1]) / chord, uy = (b[0] - a[0]) / chord;
                double sgn = (Math.Abs(th) < Math.PI) == (bu > 0) ? 1 : -1;
                var c = new[] { mx + sgn * h * ux, my + sgn * h * uy, 0 };
                double sa = Math.Atan2(a[1] - c[1], a[0] - c[0]), ea = Math.Atan2(b[1] - c[1], b[0] - c[0]);
                r.Add(bu > 0 ? new ASeg(c, rad, sa, ea, false) : new ASeg(c, rad, ea, sa, false));
            }
            return r;
        }
        internal override Entity CloneRaw() => new Polyline(V.Select(p => (double[])p.Clone()).ToList(), lw) { Closed = Closed, Bulge = new List<double>(Bulge) };
        internal override void Transform(Func<double[], double[]> f, bool m) { V = V.Select(f).ToList(); if (m) Bulge = Bulge.Select(b => -b).ToList(); }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len)
        {
            var d = new StringBuilder();
            foreach (var s in Segs(false))
            {
                if (s is LSeg l) d.Append($"M{pt(l.A)} L{pt(l.B)} ");
                else { var a = (ASeg)s; var sp = new[] { a.C[0] + a.R * Math.Cos(a.S), a.C[1] + a.R * Math.Sin(a.S), 0 }; var ep = new[] { a.C[0] + a.R * Math.Cos(a.E), a.C[1] + a.R * Math.Sin(a.E), 0 }; d.Append($"M{pt(sp)} A{len(a.R)},{len(a.R)} 0 {(G.Norm(a.E - a.S) > Math.PI ? 1 : 0)},0 {pt(ep)} "); }
            }
            sb.Append($"<path d=\"{d}\" {Stroke()}/>\n");
        }
    }

    public class Spline : Entity
    {
        List<double[]> pts;
        internal Spline(List<double[]> p) { pts = p; }
        public override string ObjectName => "AcDbSpline";
        internal override List<Seg> Segs(bool ext) { var r = new List<Seg>(); for (int i = 0; i + 1 < pts.Count; i++) r.Add(new LSeg(pts[i], pts[i + 1])); return r; }
        internal override Entity CloneRaw() => new Spline(pts.Select(p => (double[])p.Clone()).ToList());
        internal override void Transform(Func<double[], double[]> f, bool m) { pts = pts.Select(f).ToList(); }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len)
            => sb.Append($"<path d=\"M{string.Join(" L", pts.Select(pt))}\" {Stroke()}/>\n");
    }

    public class Text : Entity
    {
        double[] ins, align; public string TextString { get; set; } public double Height { get; set; }
        internal Text(string s, double[] p, double h) { TextString = s; ins = p; align = p; Height = h; }
        public override string ObjectName => "AcDbText";
        public object InsertionPoint { get => (double[])ins.Clone(); set => ins = G.P(value); }
        public object TextAlignmentPoint { get => (double[])align.Clone(); set => align = G.P(value); }
        public int Alignment { get; set; }
        public int HorizontalAlignment { get; set; }
        public int VerticalAlignment { get; set; }
        public double Rotation { get; set; }
        public string StyleName { get; set; } = "Standard";
        public double ScaleFactor { get; set; } = 1;
        internal override List<Seg> Segs(bool ext) => new List<Seg>();
        internal override Entity CloneRaw() => new Text(TextString, (double[])ins.Clone(), Height) { Alignment = Alignment, HorizontalAlignment = HorizontalAlignment };
        internal override void Transform(Func<double[], double[]> f, bool m) { ins = f(ins); align = f(align); }
        internal override void RotateAngles(double a) { Rotation += a; }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len)
        {
            bool mid = Alignment != 0 || HorizontalAlignment != 0;
            var p = pt(mid ? align : ins).Split(',');
            string esc = System.Security.SecurityElement.Escape(TextString ?? "");
            sb.Append($"<text x=\"{p[0]}\" y=\"{p[1]}\" font-size=\"{len(Height)}\" fill=\"#a60\" text-anchor=\"{(mid ? "middle" : "start")}\" transform=\"rotate({G.F(-Rotation * 180 / Math.PI)} {p[0]} {p[1]})\">{esc}</text>\n");
        }
    }

    public class Dimension : Entity
    {
        double[] a, b, loc; double rot; bool aligned;
        internal Dimension(double[] a, double[] b, double[] loc, double rot, bool aligned) { this.a = a; this.b = b; this.loc = loc; this.rot = rot; this.aligned = aligned; }
        public override string ObjectName => aligned ? "AcDbAlignedDimension" : "AcDbRotatedDimension";
        public string TextOverride { get; set; } = "";
        public double TextHeight { get; set; }
        public double ScaleFactor { get; set; } = 1;
        public double Measurement { get { var d = Dir(); return Math.Abs((b[0] - a[0]) * d[0] + (b[1] - a[1]) * d[1]); } }
        public int PrimaryUnitsPrecision { get; set; }
        public int ExtensionLineExtend { get; set; }
        public double TextRotation { get; set; }
        public object TextPosition { get; set; }
        public double ArrowheadSize { get; set; }
        double[] Dir() { if (aligned) { double dx = b[0] - a[0], dy = b[1] - a[1], l = Math.Sqrt(dx * dx + dy * dy); return new[] { dx / l, dy / l }; } return new[] { Math.Cos(rot), Math.Sin(rot) }; }
        internal override List<Seg> Segs(bool ext) => new List<Seg>();
        internal override Entity CloneRaw() => new Dimension(a, b, loc, rot, aligned);
        internal override void Transform(Func<double[], double[]> f, bool m) { a = f(a); b = f(b); loc = f(loc); }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len)
        {
            var d = Dir(); var n = new[] { -d[1], d[0] };
            double off = (loc[0] - a[0]) * n[0] + (loc[1] - a[1]) * n[1];
            double tb = (b[0] - a[0]) * d[0] + (b[1] - a[1]) * d[1];
            var p1 = new[] { a[0] + off * n[0], a[1] + off * n[1], 0 };
            var p2 = new[] { p1[0] + tb * d[0], p1[1] + tb * d[1], 0 };
            // 치수선 위치를 측정점의 투영에 맞춘다
            double ta = 0; p2 = new[] { a[0] + (ta + tb) * d[0] + off * n[0], a[1] + (ta + tb) * d[1] + off * n[1], 0 };
            sb.Append($"<path d=\"M{pt(a)} L{pt(p1)} M{pt(b)} L{pt(p2)} M{pt(p1)} L{pt(p2)}\" stroke=\"#3a3\" fill=\"none\" vector-effect=\"non-scaling-stroke\" stroke-width=\"0.6\"/>\n");
            var m = pt(new[] { (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, 0 }).Split(',');
            string label = string.IsNullOrEmpty(TextOverride) || TextOverride == "<>" ? Measurement.ToString("0") : TextOverride.Replace("<>", Measurement.ToString("0"));
            double ang = Math.Atan2(d[1], d[0]) * 180 / Math.PI; if (ang > 90 || ang < -90) ang += 180;
            sb.Append($"<text x=\"{m[0]}\" y=\"{m[1]}\" font-size=\"{len(Doc.DimTxt)}\" fill=\"#3a3\" text-anchor=\"middle\" transform=\"rotate({G.F(-ang)} {m[0]} {m[1]}) translate(0 -2)\">{System.Security.SecurityElement.Escape(label)}</text>\n");
        }
    }

    public class Region : Entity
    {
        readonly List<Entity> loop;
        internal Region(List<Entity> l) { loop = l; }
        public override string ObjectName => "AcDbRegion";
        public double Area { get { double a = 0; var pts = loop.SelectMany(e => e.Samples()).ToList(); for (int i = 0; i < pts.Count; i++) { var p = pts[i]; var q = pts[(i + 1) % pts.Count]; a += p[0] * q[1] - q[0] * p[1]; } return Math.Abs(a / 2); } }
        public object Explode() { var r = new List<object>(); foreach (var e in loop) { var c = e.CloneRaw(); c.color = color; Doc.Space.AddEntity(c); r.Add(c); } return r.ToArray(); }
        public object Centroid { get { var pts = loop.SelectMany(e => e.Samples()).ToList(); return new[] { pts.Average(p => p[0]), pts.Average(p => p[1]) }; } }
        internal override List<Seg> Segs(bool ext) => loop.SelectMany(e => e.Segs(false)).ToList();
        internal override Entity CloneRaw() => new Region(loop.Select(e => { var c = e.CloneRaw(); c.Doc = e.Doc; return c; }).ToList());
        internal override void Transform(Func<double[], double[]> f, bool m) { foreach (var e in loop) e.Transform(f, m); }
        internal override void ScaleSize(double f) { foreach (var e in loop) e.ScaleSize(f); }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len) { }
    }

    public class BlockRef : Entity
    {
        readonly string name; double[] ins; readonly double sx, sy, rot;
        internal BlockRef(string n, double[] p, double sx, double sy, double rot) { name = n; ins = p; this.sx = sx; this.sy = sy; this.rot = rot; }
        public override string ObjectName => "AcDbBlockReference";
        public string Name => System.IO.Path.GetFileNameWithoutExtension(name);
        public object InsertionPoint { get => (double[])ins.Clone(); set => ins = G.P(value); }
        public object Explode() => new object[0];
        internal override List<Seg> Segs(bool ext) => new List<Seg>();
        internal override Entity CloneRaw() => new BlockRef(name, ins, sx, sy, rot);
        internal override void Transform(Func<double[], double[]> f, bool m) { ins = f(ins); }
        internal override void Svg(StringBuilder sb, Func<double[], string> pt, Func<double, string> len)
        {
            var p = pt(ins).Split(',');
            sb.Append($"<g><rect x=\"{p[0]}\" y=\"{p[1]}\" width=\"6\" height=\"6\" fill=\"#f0f\"/><text x=\"{p[0]}\" y=\"{p[1]}\" font-size=\"8\" fill=\"#f0f\">[블록 {System.Security.SecurityElement.Escape(Name)}]</text></g>\n");
        }
    }

    // ---- 도면 / 모형 공간 ----
    public class ModelSpace
    {
        internal Document Doc; internal readonly List<Entity> All = new List<Entity>();
        internal void AddEntity(Entity e) { e.Doc = Doc; All.Add(e); }
        T Add<T>(T e) where T : Entity { AddEntity(e); return e; }
        public int Count => All.Count(e => !e.Deleted);
        public object Item(object i) => All.Where(e => !e.Deleted).ElementAt(Convert.ToInt32(i));
        [System.Runtime.CompilerServices.IndexerName("Indexer")] public object this[object i] => Item(i);
        public object AddLine(object a, object b) => Add(new Line(G.P(a), G.P(b)));
        public object AddXline(object a, object b) => Add(new Xline(G.P(a), G.P(b)));
        public object AddArc(object c, double r, double s, double e) => Add(new Arc(G.P(c), r, s, e));
        public object AddCircle(object c, double r) => Add(new Circle(G.P(c), r));
        public object AddText(string s, object p, double h) => Add(new Text(s, G.P(p), h));
        public object AddDimRotated(object a, object b, object loc, double rot) => Add(new Dimension(G.P(a), G.P(b), G.P(loc), rot, false));
        public object AddDimAligned(object a, object b, object loc) => Add(new Dimension(G.P(a), G.P(b), G.P(loc), 0, true));
        public object AddPolyline(object coords) { var c = G.Coords(coords); var v = new List<double[]>(); for (int i = 0; i + 2 < c.Length + 0 && i + 1 < c.Length; i += 3) v.Add(new[] { c[i], c[i + 1], 0 }); return Add(new Polyline(v, false)); }
        public object AddLightWeightPolyline(object coords) { var c = G.Coords(coords); var v = new List<double[]>(); for (int i = 0; i + 1 < c.Length; i += 2) v.Add(new[] { c[i], c[i + 1], 0 }); return Add(new Polyline(v, true)); }
        public object AddSpline(object coords, object st, object en) { var c = G.Coords(coords); var v = new List<double[]>(); for (int i = 0; i + 2 < c.Length + 1 && i + 1 < c.Length; i += 3) v.Add(new[] { c[i], c[i + 1], 0 }); return Add(new Spline(v)); }
        public object AddRegion(object curves)
        {
            var list = ((Array)curves).Cast<object>().Select(o => (Entity)o).ToList();
            var r = new Region(list.Select(e => e.CloneRaw()).ToList());
            Add(r); return new object[] { r };
        }
        public object InsertBlock(object p, string name, double sx, double sy, double sz, double rot)
        {
            Doc.Inserted.Add(name);
            Log.Add("InsertBlock " + name);
            return Add(new BlockRef(name, G.P(p), sx, sy, rot));
        }
    }

    public class Utility { public void Prompt(string s) { Log.Add("Prompt: " + s); } }
    public class FakeApplication
    {
        public string Path { get; set; } = "/fake/AutoCAD";
        public void ZoomExtents() { } public void ZoomScaled(double s, int t) { } public void Update() { } public void ZoomAll() { }
        public bool Visible { get; set; } = true;
    }
    public class TextStyle { public string Name { get; set; } public string fontFile { get; set; } public string BigFontFile { get; set; } public double Height { get; set; } public double Width { get; set; } public void SetFont(string a, bool b, bool c, int d, int e) { } }
    public class TextStyles { readonly Dictionary<string, TextStyle> d = new Dictionary<string, TextStyle>(StringComparer.OrdinalIgnoreCase) { ["Standard"] = new TextStyle { Name = "Standard" } }; public object Add(string n) { if (!d.ContainsKey(n)) d[n] = new TextStyle { Name = n }; return d[n]; } public object Item(string n) => d.TryGetValue(n, out var s) ? s : throw new Exception("text style 없음 " + n); [System.Runtime.CompilerServices.IndexerName("Indexer")] public object this[string n] => Item(n); }
    public class LinetypeObj { public string Name { get; set; } }
    public class Linetypes : System.Collections.IEnumerable
    {
        readonly List<LinetypeObj> loaded = new List<LinetypeObj> { new LinetypeObj { Name = "ByBlock" }, new LinetypeObj { Name = "ByLayer" }, new LinetypeObj { Name = "Continuous" } };
        public void Load(string n, string f) { if (loaded.Any(l => string.Equals(l.Name, n, StringComparison.OrdinalIgnoreCase))) throw new Exception("이미 있는 선종류: " + n); loaded.Add(new LinetypeObj { Name = n }); Log.Add("Linetypes.Load " + n + " " + f); }
        public object Item(object n) => n is string s ? loaded.First(l => string.Equals(l.Name, s, StringComparison.OrdinalIgnoreCase)) : loaded[Convert.ToInt32(n)];
        public int Count => loaded.Count;
        public System.Collections.IEnumerator GetEnumerator() => loaded.GetEnumerator();
        [System.Runtime.CompilerServices.IndexerName("Indexer")] public object this[object n] => Item(n);
    }
    public class SelectionSet : System.Collections.IEnumerable
    {
        public System.Collections.IEnumerator GetEnumerator() => items.ToList().GetEnumerator();
        readonly Document doc; readonly List<Entity> items = new List<Entity>();
        public string Name { get; }
        internal SelectionSet(Document d, string n) { doc = d; Name = n; }
        public void Select(int mode, object p1, object p2)
        {
            var a = G.P(p1); var b = G.P(p2);
            double x0 = Math.Min(a[0], b[0]), x1 = Math.Max(a[0], b[0]), y0 = Math.Min(a[1], b[1]), y1 = Math.Max(a[1], b[1]);
            foreach (var e in doc.Space.All.Where(e => !e.Deleted))
            {
                var pts = e.Samples().ToList(); if (pts.Count == 0) continue;
                bool any = pts.Any(p => p[0] >= x0 - 1e-6 && p[0] <= x1 + 1e-6 && p[1] >= y0 - 1e-6 && p[1] <= y1 + 1e-6);
                if (any) items.Add(e);
            }
        }
        public int Count => items.Count;
        public object Item(object i) => items[Convert.ToInt32(i)];
        [System.Runtime.CompilerServices.IndexerName("Indexer")] public object this[object i] => Item(i);
        public void Delete() { doc.Sets.Remove(Name); }
        public void Clear() { items.Clear(); }
        public void Erase() { foreach (var e in items) e.Deleted = true; }
    }
    public class SelectionSets
    {
        readonly Document doc; internal SelectionSets(Document d) { doc = d; }
        public object Add(string n) { if (doc.Sets.ContainsKey(n)) throw new Exception("선택 세트가 이미 있음: " + n); var s = new SelectionSet(doc, n); doc.Sets[n] = s; return s; }
        public object Item(object n) => doc.Sets[n.ToString()];
        [System.Runtime.CompilerServices.IndexerName("Indexer")] public object this[object n] => Item(n);
        public int Count => doc.Sets.Count;
    }

    public class Document
    {
        public Document() { Space = new ModelSpace { Doc = this }; SelectionSets = new SelectionSets(this); }
        internal readonly ModelSpace Space;
        internal readonly Dictionary<string, SelectionSet> Sets = new Dictionary<string, SelectionSet>();
        internal readonly List<string> Inserted = new List<string>();
        internal readonly Dictionary<string, object> Vars = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
        internal double DimTxt => Vars.TryGetValue("dimtxt", out var v) ? Convert.ToDouble(v) * (Vars.TryGetValue("dimscale", out var s) ? Convert.ToDouble(s) : 1) : 3;
        public object ModelSpace => Space;
        public Utility Utility { get; } = new Utility();
        public FakeApplication Application { get; } = new FakeApplication();
        public object ActiveTextStyle { get; set; } = new TextStyle { Name = "Standard" };
        public TextStyles TextStyles { get; } = new TextStyles();
        public Linetypes Linetypes { get; } = new Linetypes();
        public SelectionSets SelectionSets { get; }
        public void SetVariable(string n, object v) { Vars[n] = v; }
        public object GetVariable(string n) => Vars.TryGetValue(n, out var v) ? v : (object)0;
        public void SendCommand(string c) { Log.Add("SendCommand " + c.Replace("\n", "\\n")); }
        public void Regen(int w) { }
        public string Name => "test.dwg";

        public int EntityCount => Space.All.Count(e => !e.Deleted);
        public string Summary() => string.Join(", ", Space.All.Where(e => !e.Deleted).GroupBy(e => e.ObjectName).Select(g => g.Key + "×" + g.Count()));

        public string ToSvg(string title)
        {
            var ents = Space.All.Where(e => !e.Deleted && !(e is Xline)).ToList();
            var pts = ents.SelectMany(e => e is Text t ? new[] { (double[])t.InsertionPoint } : e.Samples()).ToList();
            if (pts.Count == 0) return "<svg xmlns=\"http://www.w3.org/2000/svg\"/>";
            double x0 = pts.Min(p => p[0]), x1 = pts.Max(p => p[0]), y0 = pts.Min(p => p[1]), y1 = pts.Max(p => p[1]);
            double W = 1600, pad = 30, sc = (W - 2 * pad) / Math.Max(x1 - x0, 1e-6);
            double H = (y1 - y0) * sc + 2 * pad;
            if (H > 2400) { sc *= 2400 / H; H = 2400; }
            Func<double[], string> pt = p => G.F(pad + (p[0] - x0) * sc) + "," + G.F(H - pad - (p[1] - y0) * sc);
            Func<double, string> len = d => G.F(d * sc);
            var sb = new StringBuilder();
            sb.Append($"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{G.F(W)}\" height=\"{G.F(H + 20)}\" font-family=\"sans-serif\"><rect width=\"100%\" height=\"100%\" fill=\"white\"/>\n");
            sb.Append($"<text x=\"10\" y=\"16\" font-size=\"14\">{System.Security.SecurityElement.Escape(title)}</text>\n");
            foreach (var e in ents) e.Svg(sb, pt, len);
            sb.Append("</svg>\n");
            return sb.ToString();
        }
    }
}
