using System.Text;
using System.Text.Json;
using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Core.Server;

/// <summary>
/// 이 PC 가 어느 서버에 소속되어 있는지에 대한 정보.
/// 설정 파일과 따로 둔 이유는, 서버에서 받은 정책이 이 파일을 덮어쓰지 않게 하기 위해서다.
/// </summary>
public sealed class ServerSettings
{
    /// <summary>관리 서버 주소. 비어 있으면 서버 없이 단독으로 동작한다.</summary>
    public string ServerUrl { get; set; } = string.Empty;

    /// <summary>서버가 발급한 이 PC 의 식별자.</summary>
    public string DeviceId { get; set; } = string.Empty;

    /// <summary>서버가 발급한 장비 토큰.</summary>
    public string Token { get; set; } = string.Empty;

    /// <summary>등록에 쓴 키. 토큰이 만료되어 다시 등록할 때 쓴다.</summary>
    public string EnrollmentKey { get; set; } = string.Empty;

    /// <summary>서버에 연락하는 주기(초).</summary>
    public int PollSeconds { get; set; } = 60;

    /// <summary>서버를 쓰는 상태인지.</summary>
    public bool IsConfigured => !string.IsNullOrWhiteSpace(ServerUrl);

    /// <summary>등록까지 마친 상태인지.</summary>
    public bool IsEnrolled => IsConfigured && !string.IsNullOrWhiteSpace(Token);

    public static string DefaultPath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "HanilTimeGuard",
            "server.json");

    public static ServerSettings Load(string? path = null)
    {
        path ??= DefaultPath;

        try
        {
            if (!File.Exists(path)) return new ServerSettings();

            var json = File.ReadAllText(path, Encoding.UTF8);
            return JsonSerializer.Deserialize<ServerSettings>(json, IpcJson.Options) ?? new ServerSettings();
        }
        catch (Exception)
        {
            // 읽지 못하면 단독 동작으로 넘어간다. 여기서 예외를 던지면 서비스가 뜨지 못한다.
            return new ServerSettings();
        }
    }

    public void Save(string? path = null)
    {
        path ??= DefaultPath;

        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);

        var json = JsonSerializer.Serialize(this, new JsonSerializerOptions(IpcJson.Options)
        {
            WriteIndented = true
        });

        var temp = path + ".tmp";
        File.WriteAllText(temp, json, new UTF8Encoding(false));

        if (File.Exists(path)) File.Replace(temp, path, null);
        else File.Move(temp, path);
    }
}
