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

    /// <summary>
    /// 등록 키. 여러 대를 한꺼번에 설치할 때만 쓴다.
    /// 비어 있으면 관리자 승인 방식으로 등록한다.
    /// </summary>
    public string EnrollmentKey { get; set; } = string.Empty;

    /// <summary>
    /// 이 PC 가 스스로 만들어 보관하는 비밀값.
    /// 서버에 자기를 알리고, 승인된 뒤 토큰을 받아 갈 때 쓴다.
    /// 관리자가 받아 적을 일이 없도록 처음 한 번 자동으로 만들어진다.
    /// </summary>
    public string ClientId { get; set; } = string.Empty;

    /// <summary>서버에 연락하는 주기(초).</summary>
    public int PollSeconds { get; set; } = 60;

    /// <summary>
    /// 처음 등록할 때 본 서버 인증서의 지문.
    /// 이후로는 이 지문과 맞는 서버에만 연결한다. 중간에서 가로채는 가짜 서버를 막는다.
    /// 사내에서 쓰는 자체 서명 인증서라 공인 기관 검증 대신 이 방식을 쓴다.
    /// </summary>
    public string CertificateThumbprint { get; set; } = string.Empty;

    /// <summary>암호화된 연결(HTTPS)을 쓰는지.</summary>
    public bool UsesHttps =>
        ServerUrl.StartsWith("https://", StringComparison.OrdinalIgnoreCase);

    /// <summary>서버를 쓰는 상태인지.</summary>
    public bool IsConfigured => !string.IsNullOrWhiteSpace(ServerUrl);

    /// <summary>등록까지 마친 상태인지.</summary>
    public bool IsEnrolled => IsConfigured && !string.IsNullOrWhiteSpace(Token);

    /// <summary>
    /// 이 PC 의 비밀값을 얻는다. 없으면 만들어 저장한다.
    /// </summary>
    public string EnsureClientId(string? path = null)
    {
        if (!string.IsNullOrWhiteSpace(ClientId)) return ClientId;

        ClientId = Convert.ToHexString(System.Security.Cryptography.RandomNumberGenerator.GetBytes(32));
        Save(path);

        return ClientId;
    }

    /// <summary>
    /// 관리자가 화면에서 이 PC 를 알아볼 수 있게 보여 줄 짧은 문자.
    /// 비밀값 자체를 보여 주면 안 되므로 앞부분만 쓴다.
    /// </summary>
    public static string DescribeFingerprint(string clientId) =>
        string.IsNullOrWhiteSpace(clientId) || clientId.Length < 8
            ? "-"
            : clientId[..8];

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
