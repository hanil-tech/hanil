using System.Text;
using System.Text.Json;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Core.Server;

/// <summary>
/// 서버에서 받은 정책을 파일로 보관한다.
///
/// 서버와 연락이 끊겨도 마지막으로 받은 시간표를 그대로 적용해야 하므로,
/// 랜선을 뽑거나 서버를 꺼서 제한을 피할 수 없다.
/// </summary>
public sealed class PolicyCache
{
    private readonly object _gate = new();
    private readonly string _path;

    public PolicyCache(string? path = null) => _path = path ?? DefaultPath;

    public static string DefaultPath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "HanilTimeGuard",
            "policy-cache.json");

    public string FilePath => _path;

    /// <summary>보관된 정책과 그 표식을 읽는다. 없으면 null.</summary>
    public CachedPolicy? Load()
    {
        lock (_gate)
        {
            try
            {
                if (!File.Exists(_path)) return null;

                var json = File.ReadAllText(_path, Encoding.UTF8);
                return JsonSerializer.Deserialize<CachedPolicy>(json, IpcJson.Options);
            }
            catch (Exception)
            {
                // 파일이 깨졌으면 없는 것으로 본다. 다음 연락 때 새로 받는다.
                return null;
            }
        }
    }

    public void Save(GuardConfig policy, string stamp)
    {
        ArgumentNullException.ThrowIfNull(policy);

        var cached = new CachedPolicy
        {
            Stamp = stamp,
            ReceivedAt = DateTimeOffset.Now,
            Policy = policy
        };

        lock (_gate)
        {
            var directory = System.IO.Path.GetDirectoryName(_path);
            if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);

            var json = JsonSerializer.Serialize(cached, new JsonSerializerOptions(IpcJson.Options)
            {
                WriteIndented = true
            });

            var temp = _path + ".tmp";
            File.WriteAllText(temp, json, new UTF8Encoding(false));

            if (File.Exists(_path)) File.Replace(temp, _path, null);
            else File.Move(temp, _path);
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
                // 지우지 못해도 다음에 덮어쓰므로 문제되지 않는다.
            }
        }
    }
}

public sealed class CachedPolicy
{
    public string Stamp { get; set; } = string.Empty;
    public DateTimeOffset ReceivedAt { get; set; }
    public GuardConfig Policy { get; set; } = new();
}
