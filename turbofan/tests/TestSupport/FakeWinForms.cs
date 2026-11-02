// 시험 전용: 리눅스에서 변환된 코드를 돌려 보기 위한 아주 얇은 WinForms 대역.
// 실제 화면은 없고, 텍스트·선택·포커스·이벤트 흐름만 흉내 낸다.
// (실제 프로그램은 진짜 WinForms(.NET Framework 4.8)로 빌드된다.)
using System;
using System.Collections;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;

namespace System.Drawing
{
    public enum FontStyle { Regular = 0, Bold = 1, Italic = 2 }
    public class Font
    {
        public Font(string family, float size, FontStyle style = FontStyle.Regular) { Name = family; Size = size; Style = style; }
        public string Name { get; } public float Size { get; } public FontStyle Style { get; }
    }
    public class Image : IDisposable
    {
        public static Image FromStream(IO.Stream s) => new Bitmap();
        public void Dispose() { }
    }
    public class Bitmap : Image { public Bitmap() { } public Bitmap(Image i) { } }
    public class Icon { public static Icon ExtractAssociatedIcon(string p) => new Icon(); }
    public enum ContentAlignment { TopLeft = 1, TopCenter = 2, TopRight = 4, MiddleLeft = 16, MiddleCenter = 32 }
}

namespace System.Windows.Forms
{
    using System.Drawing;

    public interface IWin32Window { }
    public enum Keys { None = 0, Tab = 9, Enter = 13, Shift = 0x10000, Control = 0x20000, Alt = 0x40000 }
    public class KeyEventArgs : EventArgs
    {
        public KeyEventArgs(Keys k) { KeyData = k; }
        public Keys KeyData { get; }
        public Keys KeyCode => KeyData & (Keys)0xFFFF;
        public int KeyValue => (int)KeyCode;
        public Keys Modifiers => KeyData & (Keys)unchecked((int)0xFFFF0000);
        public bool SuppressKeyPress { get; set; }
        public bool Handled { get; set; }
    }
    public enum CloseReason { None, UserClosing }
    public class FormClosingEventArgs : CancelEventArgs { public CloseReason CloseReason { get; set; } }
    public enum ComboBoxStyle { DropDown, DropDownList, Simple }
    public enum HorizontalAlignment { Left, Right, Center }
    public enum BorderStyle { None, FixedSingle, Fixed3D }
    public enum PictureBoxSizeMode { Normal, StretchImage, AutoSize, CenterImage, Zoom }
    public enum AutoScaleMode { None, Font, Dpi, Inherit }
    public enum FormStartPosition { Manual, CenterScreen }
    public enum FormBorderStyle { None, FixedSingle, FixedDialog, Sizable }
    public enum UnhandledExceptionMode { Automatic, ThrowException, CatchException }

    public static class Application
    {
        // BeginInvoke 로 미룬 일을 처리한다 (실제 메시지 루프 흉내). 끝없이 이어지면 예외.
        internal static readonly Queue<Delegate> Pending = new Queue<Delegate>();
        public static void DoEvents()
        {
            int guard = 0;
            while (Pending.Count > 0)
            {
                if (++guard > 200) { Pending.Clear(); throw new InvalidOperationException("미룬 작업이 끝없이 이어짐 (포커스 무한 반복?)"); }
                Pending.Dequeue().DynamicInvoke();
            }
        }
        public static void EnableVisualStyles() { }
        public static void SetCompatibleTextRenderingDefault(bool b) { }
        public static void SetUnhandledExceptionMode(UnhandledExceptionMode m) { }
        public static event Threading.ThreadExceptionEventHandler ThreadException { add { } remove { } }
        public static void Run() { }
        public static void Exit() { }
    }
    public class Cursor { public static Cursor Current { get; set; } }
    public static class Cursors { public static Cursor WaitCursor = new Cursor(); }

    public class ControlCollection : IEnumerable<Control>
    {
        readonly Control owner; readonly List<Control> list = new List<Control>();
        public ControlCollection(Control o) { owner = o; }
        public void Add(Control c) { list.Add(c); c.Parent = owner; }
        public int Count => list.Count;
        public IEnumerator<Control> GetEnumerator() => list.GetEnumerator();
        IEnumerator IEnumerable.GetEnumerator() => list.GetEnumerator();
    }

    public class Control
    {
        public Control() { Controls = new ControlCollection(this); }
        public string Name { get; set; }
        public Point Location { get; set; }
        public Size Size { get; set; }
        public int TabIndex { get; set; }
        public bool TabStop { get; set; } = true;
        public bool Visible { get; set; } = true;
        public bool Enabled { get; set; } = true;
        public Font Font { get; set; }
        public Color BackColor { get; set; }
        public Color ForeColor { get; set; }
        public bool AutoSize { get; set; }
        public Control Parent { get; set; }
        public ControlCollection Controls { get; }
        public bool IsHandleCreated => true;
        public bool CanFocus => Visible && Enabled;
        public bool ContainsFocus => FindForm()?.ActiveControl == this;
        string text = "";
        public virtual string Text
        {
            get => text;
            set { value = value ?? ""; if (value == text) return; text = value; OnTextChanged(EventArgs.Empty); }
        }
        public event EventHandler TextChanged;
        protected virtual void OnTextChanged(EventArgs e) => TextChanged?.Invoke(this, e);
        protected virtual void OnEnter(EventArgs e) { }
        protected virtual void OnLeave(EventArgs e) { }
        protected virtual void OnKeyDown(KeyEventArgs e) { }
        protected virtual void OnClick(EventArgs e) { }
        public Form FindForm() { var c = this; while (c != null && !(c is Form)) c = c.Parent; return c as Form; }
        public bool Focus()
        {
            var f = FindForm(); if (f == null) return false;
            if (f.ActiveControl == this) return true;
            var old = f.ActiveControl;
            f.SetActive(null);
            old?.OnLeave(EventArgs.Empty);
            f.SetActive(this);
            OnEnter(EventArgs.Empty);
            return true;
        }
        public IAsyncResult BeginInvoke(Delegate d) { Application.Pending.Enqueue(d); return null; }
        public void Hide() { Visible = false; }
        public bool IsDisposed { get; private set; }
        public void Dispose() { IsDisposed = true; }
        public void SuspendLayout() { }
        public void ResumeLayout(bool b) { }
        public void PerformLayout() { }
        // 시험에서 키 누름·클릭을 흉내 낼 때
        public void TestKeyDown(Keys k) => OnKeyDown(new KeyEventArgs(k));
        public void TestClick() => OnClick(EventArgs.Empty);
    }

    public class Form : Control, IWin32Window
    {
        public Size ClientSize { get; set; }
        public AutoScaleMode AutoScaleMode { get; set; }
        public SizeF AutoScaleDimensions { get; set; }
        public FormStartPosition StartPosition { get; set; }
        public FormBorderStyle FormBorderStyle { get; set; }
        public bool MaximizeBox { get; set; }
        public bool MinimizeBox { get; set; }
        public bool ShowInTaskbar { get; set; }
        public bool KeyPreview { get; set; }
        public Icon Icon { get; set; }
        public Control ActiveControl { get; private set; }
        internal void SetActive(Control c) { ActiveControl = c; }
        public new bool Visible { get; private set; }
        public void Show() { Visible = true; }
        public new void Hide() { Visible = false; }
        public void Activate() { }
        public void Close() { }
        protected virtual void OnFormClosing(FormClosingEventArgs e) { }
        public bool SelectNextControl(Control c, bool forward, bool tabOnly, bool nested, bool wrap)
        {
            var all = AllControls(this).Where(x => x.TabStop && x.Enabled && !(x is Label) && !(x is GroupBox) && !(x is PictureBox)).ToList();
            var order = all.OrderBy(TabPath, Comparer<string>.Default).ToList();
            int i = order.IndexOf(c);
            if (order.Count == 0) return false;
            var next = order[(i + (forward ? 1 : -1) + order.Count) % order.Count];
            next.Focus();
            return true;
        }
        static string TabPath(Control c) { var parts = new List<string>(); while (c != null && !(c is Form)) { parts.Insert(0, c.TabIndex.ToString("D4")); c = c.Parent; } return string.Join(".", parts); }
        static IEnumerable<Control> AllControls(Control root) { foreach (var c in root.Controls) { yield return c; foreach (var d in AllControls(c)) yield return d; } }
    }

    public class TextBox : Control
    {
        public bool ReadOnly { get; set; }
        public int SelectionStart { get; set; }
        public int SelectionLength { get; set; }
        public bool Multiline { get; set; }
        public HorizontalAlignment TextAlign { get; set; }
    }

    public class ComboBox : Control
    {
        public class ObjectCollection : IEnumerable
        {
            readonly ComboBox owner; readonly List<object> items = new List<object>();
            public ObjectCollection(ComboBox o) { owner = o; }
            public int Add(object o) { items.Add(o); return items.Count - 1; }
            public void Insert(int i, object o) { items.Insert(i, o); }
            public void RemoveAt(int i) { items.RemoveAt(i); }
            public void Clear() { items.Clear(); owner.SelectedIndex = -1; }
            public int Count => items.Count;
            public object this[int i] { get => items[i]; set => items[i] = value; }
            public int IndexOf(object o) => items.IndexOf(o);
            public IEnumerator GetEnumerator() => items.GetEnumerator();
        }
        public ComboBox() { Items = new ObjectCollection(this); }
        public ObjectCollection Items { get; }
        public ComboBoxStyle DropDownStyle { get; set; }
        public bool IntegralHeight { get; set; }
        public int MaxDropDownItems { get; set; }
        public bool DroppedDown { get; set; }
        int sel = -1;
        public int SelectedIndex
        {
            get => sel;
            set { if (value == sel) return; sel = value; if (sel >= 0) base.Text = Items[sel].ToString(); OnSelectedIndexChanged(EventArgs.Empty); }
        }
        public override string Text
        {
            get => base.Text;
            set
            {
                base.Text = value;
                int i = -1; for (int k = 0; k < Items.Count; k++) if (Items[k].ToString() == value) { i = k; break; }
                if (i != sel) { sel = i; OnSelectedIndexChanged(EventArgs.Empty); }
            }
        }
        protected virtual void OnSelectedIndexChanged(EventArgs e) { }
    }

    public class ButtonBase : Control { public bool UseMnemonic { get; set; } public bool UseVisualStyleBackColor { get; set; } }
    public class Button : ButtonBase { public void PerformClick() => OnClick(EventArgs.Empty); }
    public class RadioButton : ButtonBase
    {
        bool chk;
        public bool Checked
        {
            get => chk;
            set
            {
                if (value == chk) return;
                chk = value;
                if (chk && Parent != null)
                    foreach (var sib in Parent.Controls.OfType<RadioButton>().Where(r => r != this && r.Checked).ToList()) sib.Checked = false;
                OnCheckedChanged(EventArgs.Empty);
            }
        }
        protected virtual void OnCheckedChanged(EventArgs e) { }
    }
    public class CheckBox : ButtonBase
    {
        bool chk;
        public bool Checked { get => chk; set { if (value == chk) return; chk = value; OnCheckedChanged(EventArgs.Empty); } }
        protected virtual void OnCheckedChanged(EventArgs e) { }
    }
    public class Label : Control
    {
        public bool UseMnemonic { get; set; }
        public ContentAlignment TextAlign { get; set; }
        public BorderStyle BorderStyle { get; set; }
    }
    public class GroupBox : Control { }
    public class PictureBox : Control
    {
        public Image Image { get; set; }
        public PictureBoxSizeMode SizeMode { get; set; }
        public BorderStyle BorderStyle { get; set; }
    }
}
