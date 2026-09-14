using System.Text;

namespace Hanil.TimeGuard.Core;

/// <summary>
/// 조치 내역과 설정 변경을 남기는 단순 텍스트 로그.
/// 파일이 일정 크기를 넘으면 한 세대만 보관하고 새로 시작한다.
/// </summary>
public sealed class AuditLog
{
    private const long MaxBytes = 2 * 1024 * 1024;

    private readonly object _gate = new();
    private readonly string _path;

    public AuditLog(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        _path = path;
    }

    public static string DefaultPath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "HanilTimeGuard",
            "timeguard.log");

    public string FilePath => _path;

    public void Write(string category, string message)
    {
        var line = $"{DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss} [{category}] {message}";

        lock (_gate)
        {
            try
            {
                var directory = System.IO.Path.GetDirectoryName(_path);
                if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);

                Rotate();
                File.AppendAllText(_path, line + Environment.NewLine, new UTF8Encoding(false));
            }
            catch
            {
                // 로그를 남기지 못하는 것이 서비스 중단 사유가 되어서는 안 된다.
            }
        }
    }

    public IReadOnlyList<string> Tail(int lines)
    {
        if (lines <= 0) lines = 50;

        lock (_gate)
        {
            try
            {
                if (!File.Exists(_path)) return Array.Empty<string>();
                var all = File.ReadAllLines(_path, Encoding.UTF8);
                return all.Length <= lines ? all : all[^lines..];
            }
            catch (Exception ex)
            {
                return new[] { $"로그를 읽지 못했습니다: {ex.Message}" };
            }
        }
    }

    private void Rotate()
    {
        var info = new FileInfo(_path);
        if (!info.Exists || info.Length < MaxBytes) return;

        var backup = _path + ".1";
        if (File.Exists(backup)) File.Delete(backup);
        File.Move(_path, backup);
    }
}
