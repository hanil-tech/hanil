using System.Text;
using System.Text.Json;
using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Core.State;

/// <summary>이 서비스가 잠근 계정 하나에 대한 기록.</summary>
public sealed class LockedAccount
{
    public string UserName { get; set; } = string.Empty;
    public DateTimeOffset LockedAt { get; set; }
    public string Reason { get; set; } = string.Empty;
}

/// <summary>
/// 서비스가 잠근 계정을 기록해 둔다.
///
/// 이 기록이 없으면 어떤 계정을 우리가 잠갔는지 알 수 없어 풀어 줄 수 없다.
/// PC 를 껐다 켜도 남아 있어야 하므로 파일에 둔다.
/// </summary>
public sealed class LockedAccountStore
{
    private readonly object _gate = new();
    private readonly string _path;

    public LockedAccountStore(string? path = null) => _path = path ?? DefaultPath;

    public static string DefaultPath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "HanilTimeGuard",
            "locked-accounts.json");

    public string FilePath => _path;

    public List<LockedAccount> Load()
    {
        lock (_gate)
        {
            try
            {
                if (!File.Exists(_path)) return new List<LockedAccount>();

                var json = File.ReadAllText(_path, Encoding.UTF8);
                return JsonSerializer.Deserialize<List<LockedAccount>>(json, IpcJson.Options)
                       ?? new List<LockedAccount>();
            }
            catch (Exception)
            {
                // 기록이 깨졌다면 빈 목록으로 둔다.
                // 잠긴 계정을 놓칠 수 있으나, 관리자 도구로 풀 수 있다.
                return new List<LockedAccount>();
            }
        }
    }

    public void Add(string userName, string reason)
    {
        lock (_gate)
        {
            var entries = LoadUnlocked();

            if (entries.Any(e => string.Equals(e.UserName, userName, StringComparison.OrdinalIgnoreCase)))
                return;

            entries.Add(new LockedAccount
            {
                UserName = userName,
                LockedAt = DateTimeOffset.Now,
                Reason = reason
            });

            SaveUnlocked(entries);
        }
    }

    public void Remove(string userName)
    {
        lock (_gate)
        {
            var entries = LoadUnlocked();
            var removed = entries.RemoveAll(e =>
                string.Equals(e.UserName, userName, StringComparison.OrdinalIgnoreCase));

            if (removed > 0) SaveUnlocked(entries);
        }
    }

    public void Clear()
    {
        lock (_gate)
        {
            try
            {
                if (File.Exists(_path)) File.Delete(_path);
            }
            catch (IOException)
            {
                SaveUnlocked(new List<LockedAccount>());
            }
        }
    }

    private List<LockedAccount> LoadUnlocked()
    {
        try
        {
            if (!File.Exists(_path)) return new List<LockedAccount>();

            var json = File.ReadAllText(_path, Encoding.UTF8);
            return JsonSerializer.Deserialize<List<LockedAccount>>(json, IpcJson.Options)
                   ?? new List<LockedAccount>();
        }
        catch (Exception)
        {
            return new List<LockedAccount>();
        }
    }

    private void SaveUnlocked(List<LockedAccount> entries)
    {
        try
        {
            var directory = Path.GetDirectoryName(_path);
            if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);

            var json = JsonSerializer.Serialize(entries, new JsonSerializerOptions(IpcJson.Options)
            {
                WriteIndented = true
            });

            File.WriteAllText(_path, json, new UTF8Encoding(false));
        }
        catch (Exception)
        {
            // 기록하지 못해도 잠금 자체는 이미 수행됐다.
            // 관리자 도구의 복구 명령으로 풀 수 있다.
        }
    }
}
