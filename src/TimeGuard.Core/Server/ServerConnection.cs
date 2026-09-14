using System.Net;
using System.Net.Http.Json;
using System.Security.Cryptography.X509Certificates;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Core.Server;

/// <summary>서버와 한 번 주고받은 결과.</summary>
public sealed record SyncResult
{
    /// <summary>서버와 연락이 닿았는지.</summary>
    public required bool Reached { get; init; }

    /// <summary>연락이 닿지 않았을 때의 사유.</summary>
    public string? Error { get; init; }

    /// <summary>정책이 바뀌어 새로 받았으면 담긴다.</summary>
    public GuardConfig? NewPolicy { get; init; }

    public string? PolicyStamp { get; init; }

    public DateTimeOffset? ExtensionUntil { get; init; }
    public DateTimeOffset? SuspendedUntil { get; init; }

    /// <summary>사용자에게 알려야 할 연장 요청 처리 결과.</summary>
    public IReadOnlyList<RequestDecision> Decisions { get; init; } = Array.Empty<RequestDecision>();

    /// <summary>토큰이 더 이상 통하지 않아 다시 등록해야 하는 상태.</summary>
    public bool NeedsReEnrollment { get; init; }

    public static SyncResult Failed(string error) => new() { Reached = false, Error = error };
}

/// <summary>
/// 관리 서버와 통신한다.
/// 서버에 닿지 못하는 것은 정상적인 상황으로 보고 예외를 밖으로 던지지 않는다.
/// </summary>
public sealed class ServerConnection : IDisposable
{
    private static readonly TimeSpan RequestTimeout = TimeSpan.FromSeconds(15);

    private readonly HttpClient _http;
    private readonly ServerSettings _settings;
    private readonly string _settingsPath;

    /// <summary>가장 최근 연결에서 본 서버 인증서의 지문.</summary>
    private string? _observedThumbprint;

    /// <summary>인증서가 기억해 둔 것과 달랐는지.</summary>
    public bool CertificateMismatch { get; private set; }

    public ServerConnection(ServerSettings settings, string? settingsPath = null, HttpMessageHandler? handler = null)
    {
        _settings = settings;
        _settingsPath = settingsPath ?? ServerSettings.DefaultPath;

        _http = handler is null
            ? new HttpClient(CreateHandler(), disposeHandler: true)
            : new HttpClient(handler, disposeHandler: false);

        _http.Timeout = RequestTimeout;

        if (settings.IsConfigured)
            _http.BaseAddress = new Uri(settings.ServerUrl.TrimEnd('/') + "/");
    }

    /// <summary>
    /// 서버 인증서를 확인하는 규칙을 건 통신 핸들러를 만든다.
    ///
    /// 사내에 두는 서버라 공인 인증 기관이 발급한 인증서를 쓰기 어렵다.
    /// 대신 처음 등록할 때 본 인증서를 기억해 두고, 이후 달라지면 연결을 끊는다.
    /// 가짜 서버를 세워 중간에서 가로채는 것을 막기 위해서다.
    /// </summary>
    private HttpClientHandler CreateHandler()
    {
        var handler = new HttpClientHandler();

        handler.ServerCertificateCustomValidationCallback = (_, certificate, _, errors) =>
        {
            if (certificate is null) return false;

            var thumbprint = certificate.GetCertHashString(System.Security.Cryptography.HashAlgorithmName.SHA256);
            _observedThumbprint = thumbprint;

            var expected = _settings.CertificateThumbprint;

            if (string.IsNullOrWhiteSpace(expected))
            {
                // 아직 기억해 둔 인증서가 없다. 등록 과정에서 이 값을 저장한다.
                CertificateMismatch = false;
                return true;
            }

            var matches = string.Equals(thumbprint, expected, StringComparison.OrdinalIgnoreCase);
            CertificateMismatch = !matches;

            // 지문이 맞으면 공인 기관 검증 결과(errors)는 따지지 않는다.
            // 자체 서명 인증서라 어차피 통과하지 못하기 때문이다.
            return matches;
        };

        return handler;
    }

    public ServerSettings Settings => _settings;

    /// <summary>서버가 응답하는지 확인한다.</summary>
    public async Task<bool> PingAsync(CancellationToken token = default)
    {
        if (!_settings.IsConfigured) return false;

        try
        {
            using var response = await _http.GetAsync("api/ping", token);
            return response.IsSuccessStatusCode;
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>
    /// 등록 키 없이 서버에 자기를 알린다.
    /// 관리자가 서버 화면에서 승인할 때까지는 아무것도 받지 못한다.
    /// </summary>
    public async Task<(bool Reached, string State, string Message)> AnnounceAsync(
        string machineName, string osUser, CancellationToken token = default)
    {
        if (!_settings.IsConfigured) return (false, ApprovalStates.Pending, "서버 주소가 설정되지 않았습니다.");

        try
        {
            var request = new AnnounceRequest
            {
                MachineName = machineName,
                OsUser = osUser,
                ClientId = _settings.EnsureClientId(_settingsPath),
                ClientVersion = typeof(ServerConnection).Assembly.GetName().Version?.ToString() ?? "1.0.0"
            };

            using var response = await _http.PostAsJsonAsync(
                ServerRoutes.Announce.TrimStart('/'), request, IpcJson.Options, token);

            if (!response.IsSuccessStatusCode)
                return (false, ApprovalStates.Pending, await ReadErrorAsync(response, token));

            var result = await response.Content.ReadFromJsonAsync<AnnounceResponse>(IpcJson.Options, token);

            return result is null
                ? (false, ApprovalStates.Pending, "서버 응답을 해석하지 못했습니다.")
                : (true, result.State, result.Message);
        }
        catch (Exception) when (CertificateMismatch)
        {
            return (false, ApprovalStates.Pending,
                "서버 인증서가 기억해 둔 것과 다릅니다. 다른 서버이거나 누군가 가로채고 있을 수 있습니다.");
        }
        catch (Exception ex)
        {
            return (false, ApprovalStates.Pending, $"서버에 연결하지 못했습니다: {ex.Message}");
        }
    }

    /// <summary>
    /// 승인되었는지 확인하고, 승인되었으면 토큰을 받아 저장한다.
    /// </summary>
    public async Task<(bool Approved, string State, string Message)> ClaimAsync(
        string machineName, CancellationToken token = default)
    {
        if (!_settings.IsConfigured) return (false, ApprovalStates.Pending, "서버 주소가 설정되지 않았습니다.");

        try
        {
            var request = new ClaimRequest
            {
                ClientId = _settings.EnsureClientId(_settingsPath),
                MachineName = machineName
            };

            using var response = await _http.PostAsJsonAsync(
                ServerRoutes.Claim.TrimStart('/'), request, IpcJson.Options, token);

            if (!response.IsSuccessStatusCode)
                return (false, ApprovalStates.Pending, await ReadErrorAsync(response, token));

            var result = await response.Content.ReadFromJsonAsync<ClaimResponse>(IpcJson.Options, token);
            if (result is null) return (false, ApprovalStates.Pending, "서버 응답을 해석하지 못했습니다.");

            if (result.State != ApprovalStates.Approved || string.IsNullOrWhiteSpace(result.Token))
                return (false, result.State, result.Message);

            _settings.DeviceId = result.DeviceId ?? string.Empty;
            _settings.Token = result.Token;

            // 처음 연결할 때 본 인증서를 기억해 둔다.
            if (_settings.UsesHttps &&
                string.IsNullOrWhiteSpace(_settings.CertificateThumbprint) &&
                !string.IsNullOrWhiteSpace(_observedThumbprint))
            {
                _settings.CertificateThumbprint = _observedThumbprint;
            }

            _settings.Save(_settingsPath);

            return (true, result.State, result.Message);
        }
        catch (Exception) when (CertificateMismatch)
        {
            return (false, ApprovalStates.Pending, "서버 인증서가 기억해 둔 것과 다릅니다.");
        }
        catch (Exception ex)
        {
            return (false, ApprovalStates.Pending, $"서버에 연결하지 못했습니다: {ex.Message}");
        }
    }

    /// <summary>이 PC 를 서버에 등록한다. 성공하면 토큰을 받아 설정 파일에 저장한다.</summary>
    public async Task<(bool Ok, string Message)> EnrollAsync(
        string machineName, string osUser, string enrollmentKey, CancellationToken token = default)
    {
        if (!_settings.IsConfigured) return (false, "서버 주소가 설정되지 않았습니다.");

        try
        {
            var request = new EnrollRequest
            {
                MachineName = machineName,
                OsUser = osUser,
                EnrollmentKey = enrollmentKey,
                ExistingDeviceId = string.IsNullOrWhiteSpace(_settings.DeviceId) ? null : _settings.DeviceId
            };

            using var response = await _http.PostAsJsonAsync(
                ServerRoutes.Enroll.TrimStart('/'), request, IpcJson.Options, token);

            if (!response.IsSuccessStatusCode)
            {
                var error = await ReadErrorAsync(response, token);
                return (false, error);
            }

            var result = await response.Content.ReadFromJsonAsync<EnrollResponse>(IpcJson.Options, token);
            if (result is null) return (false, "서버 응답을 해석하지 못했습니다.");

            _settings.DeviceId = result.DeviceId;
            _settings.Token = result.Token;
            _settings.EnrollmentKey = enrollmentKey;

            // 처음 등록할 때 본 인증서를 기억해 둔다. 이후에는 이 서버에만 연결한다.
            var pinned = false;
            if (_settings.UsesHttps &&
                string.IsNullOrWhiteSpace(_settings.CertificateThumbprint) &&
                !string.IsNullOrWhiteSpace(_observedThumbprint))
            {
                _settings.CertificateThumbprint = _observedThumbprint;
                pinned = true;
            }

            _settings.Save(_settingsPath);

            var note = pinned ? " 서버 인증서를 기억했습니다." : string.Empty;
            return (true, $"'{result.DisplayName}' 이름으로 등록했습니다.{note}");
        }
        catch (Exception) when (CertificateMismatch)
        {
            return (false,
                "서버 인증서가 기억해 둔 것과 다릅니다. 다른 서버이거나 누군가 가로채고 있을 수 있습니다.");
        }
        catch (Exception ex)
        {
            return (false, $"서버에 연결하지 못했습니다: {ex.Message}");
        }
    }

    /// <summary>
    /// 서버에 현재 상태를 알리고 최신 정책을 받아 온다.
    /// 토큰이 거부되면 등록 키로 한 번 자동 재등록을 시도한다.
    /// </summary>
    public async Task<SyncResult> SyncAsync(
        HeartbeatRequest heartbeat, string machineName, CancellationToken token = default)
    {
        if (!_settings.IsEnrolled) return SyncResult.Failed("아직 서버에 등록되지 않았습니다.");

        var result = await SendHeartbeatAsync(heartbeat, token);

        if (!result.NeedsReEnrollment) return result;

        // 서버에서 장비를 지웠거나 재설치로 토큰이 바뀐 경우. 조용히 다시 등록한다.
        if (string.IsNullOrWhiteSpace(_settings.EnrollmentKey))
            return result;

        var (ok, message) = await EnrollAsync(machineName, heartbeat.OsUser, _settings.EnrollmentKey, token);
        if (!ok) return SyncResult.Failed($"다시 등록하지 못했습니다: {message}");

        // 재등록 후에는 정책 표식이 의미를 잃으므로 전체를 새로 받는다.
        heartbeat.PolicyStamp = null;
        return await SendHeartbeatAsync(heartbeat, token);
    }

    private async Task<SyncResult> SendHeartbeatAsync(HeartbeatRequest heartbeat, CancellationToken token)
    {
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, ServerRoutes.Heartbeat.TrimStart('/'))
            {
                Content = JsonContent.Create(heartbeat, options: IpcJson.Options)
            };

            request.Headers.Add(ServerRoutes.TokenHeader, _settings.Token);

            using var response = await _http.SendAsync(request, token);

            if (response.StatusCode == HttpStatusCode.Unauthorized)
                return new SyncResult { Reached = true, NeedsReEnrollment = true, Error = "장비 인증이 거부되었습니다." };

            if (!response.IsSuccessStatusCode)
                return SyncResult.Failed(await ReadErrorAsync(response, token));

            var body = await response.Content.ReadFromJsonAsync<HeartbeatResponse>(IpcJson.Options, token);
            if (body is null) return SyncResult.Failed("서버 응답을 해석하지 못했습니다.");

            return new SyncResult
            {
                Reached = true,
                NewPolicy = body.Policy,
                PolicyStamp = body.PolicyStamp,
                ExtensionUntil = body.ExtensionUntil,
                SuspendedUntil = body.SuspendedUntil,
                Decisions = body.Decisions
            };
        }
        catch (TaskCanceledException) when (!token.IsCancellationRequested)
        {
            return SyncResult.Failed("서버 응답이 없습니다(시간 초과).");
        }
        catch (Exception ex) when (CertificateMismatch)
        {
            return SyncResult.Failed(
                "서버 인증서가 처음 등록할 때와 다릅니다. 연결을 중단했습니다. " +
                $"서버를 다시 설치했다면 이 PC 를 다시 등록해 주세요. ({ex.Message})");
        }
        catch (Exception ex)
        {
            return SyncResult.Failed($"서버와 통신하지 못했습니다: {ex.Message}");
        }
    }

    /// <summary>쌓인 기록을 서버로 올린다.</summary>
    public async Task<bool> ReportEventsAsync(IReadOnlyList<EventEntry> entries, CancellationToken token = default)
    {
        if (!_settings.IsEnrolled || entries.Count == 0) return false;

        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, ServerRoutes.Events.TrimStart('/'))
            {
                Content = JsonContent.Create(new EventReport { Entries = entries.ToList() }, options: IpcJson.Options)
            };

            request.Headers.Add(ServerRoutes.TokenHeader, _settings.Token);

            using var response = await _http.SendAsync(request, token);
            return response.IsSuccessStatusCode;
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>사용자가 올린 연장 요청을 서버로 보낸다.</summary>
    public async Task<(bool Ok, string Message)> RequestExtensionAsync(
        int minutes, string reason, string osUser, CancellationToken token = default)
    {
        if (!_settings.IsEnrolled) return (false, "이 PC 는 관리 서버에 등록되어 있지 않습니다.");

        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, ServerRoutes.ExtensionRequests.TrimStart('/'))
            {
                Content = JsonContent.Create(
                    new ExtensionRequestInput { Minutes = minutes, Reason = reason, OsUser = osUser },
                    options: IpcJson.Options)
            };

            request.Headers.Add(ServerRoutes.TokenHeader, _settings.Token);

            using var response = await _http.SendAsync(request, token);

            if (!response.IsSuccessStatusCode)
                return (false, await ReadErrorAsync(response, token));

            var created = await response.Content.ReadFromJsonAsync<ExtensionRequestCreated>(IpcJson.Options, token);
            return (true, created?.Message ?? "연장 요청을 보냈습니다.");
        }
        catch (Exception ex)
        {
            return (false, $"요청을 보내지 못했습니다: {ex.Message}");
        }
    }

    private static async Task<string> ReadErrorAsync(HttpResponseMessage response, CancellationToken token)
    {
        try
        {
            var error = await response.Content.ReadFromJsonAsync<ApiError>(IpcJson.Options, token);
            if (!string.IsNullOrWhiteSpace(error?.Message)) return error!.Message;
        }
        catch (Exception)
        {
            // 본문이 JSON 이 아닐 수 있다.
        }

        return $"서버가 요청을 거부했습니다 (HTTP {(int)response.StatusCode}).";
    }

    public void Dispose() => _http.Dispose();
}
