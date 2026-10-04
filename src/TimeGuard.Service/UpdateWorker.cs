using System.Diagnostics;
using System.Reflection;
using System.Runtime.Versioning;
using Hanil.TimeGuard.Core.Schedule;
using Hanil.TimeGuard.Core.Server;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Hanil.TimeGuard.Service;

/// <summary>
/// 💿⭐⭐⭐ **새 판을 스스로 받아 바꾼다.**
///
///  사용자 「업데이트 시 다시 시작하면 프로그램 받아서」
///
///  ⚠⚠ 예전에는 새 판이 나오면 **PC 열 대를 돌며** 설치 파일을 하나씩 실행해야 했다.
///    그래서 한 대쯤 빠뜨리고, 빠뜨린 PC 는 옛 판으로 돌면서 **왜 다르게 구는지 아무도 모른다.**
///  ⭐ 이제 **관리 서버 한 대만** 새로 깔면 직원 PC 들이 그것을 보고 알아서 따라온다.
///
///  ⚠⚠⚠ **설치는 아무 때나 하지 않는다.** 설치하는 동안 서비스가 잠깐 멈추는데,
///    하필 그때가 **차단을 알리는 중**이거나 **종료 카운트다운 중**이면
///    직원이 그 틈에 빠져나간 것처럼 보인다. 그래서 **조용할 때만** 한다.
///
///  📌 왜 「받아서 설치」까지 하고 「서비스만 바꿔치기」는 안 하는가:
///    실행 중인 프로그램은 자기 자신을 덮어쓸 수 없다. 설치 프로그램은 그 일(멈춤 → 바꿈 → 다시 시작)을
///    이미 할 줄 안다 — **그것을 그대로 쓴다.** 두 벌로 만들면 한쪽만 고쳐진다.
/// </summary>
[SupportedOSPlatform("windows")]
public sealed class UpdateWorker : BackgroundService
{
    /// <summary>켜고 처음 확인하기까지 기다리는 시간. 부팅 직후의 북새통을 피한다.</summary>
    private static readonly TimeSpan FirstDelay = TimeSpan.FromMinutes(3);

    /// <summary>그다음부터 확인하는 간격.</summary>
    private static readonly TimeSpan Interval = TimeSpan.FromHours(6);

    /// <summary>같은 판으로 자꾸 다시 해 보지 않도록 쉬는 시간.</summary>
    private static readonly TimeSpan RetryAfterFailure = TimeSpan.FromHours(12);

    private readonly ServiceState _state;
    private readonly ILogger<UpdateWorker> _logger;

    /// <summary>이 판은 해 봤다가 안 됐다 — 기억해 두고 한동안 다시 안 한다.</summary>
    private string _failedVersion = string.Empty;
    private DateTimeOffset _failedAt = DateTimeOffset.MinValue;

    public UpdateWorker(ServiceState state, ILogger<UpdateWorker> logger)
    {
        _state = state;
        _logger = logger;
    }

    /// <summary>지금 돌고 있는 판.</summary>
    private static Version Current =>
        Assembly.GetExecutingAssembly().GetName().Version ?? new Version(0, 0, 0);

    /// <summary>받은 설치 파일을 두는 자리.</summary>
    private static string DownloadPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
        "HanilTimeGuard", "update", "TimeGuard-Setup.exe");

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try
        {
            await Task.Delay(FirstDelay, stoppingToken);

            while (!stoppingToken.IsCancellationRequested)
            {
                await TryUpdateAsync(stoppingToken);
                await Task.Delay(Interval, stoppingToken);
            }
        }
        catch (OperationCanceledException)
        {
            // 서비스가 멈추는 중이다. 정상이다.
        }
    }

    private async Task TryUpdateAsync(CancellationToken token)
    {
        try
        {
            var settings = ServerSettings.Load();

            //  ⚠ 단독 모드이거나 아직 승인 전이면 할 일이 없다 — 서버가 있어야 받아 올 데가 있다.
            if (!settings.IsEnrolled) return;

            using var connection = new ServerConnection(settings);

            var info = await connection.GetUpdateAsync(token);
            if (info is null || !info.Available) return;

            if (!Version.TryParse(Trim(info.Version), out var offered)) return;
            if (offered <= Current) return;

            //  ⚠ 조금 전에 이 판으로 해 봤다가 안 됐으면 한동안 쉰다 —
            //    5분마다 수십 MB 를 받아 대면 사내망이 느려지고 기록만 지저분해진다.
            if (_failedVersion == info.Version && DateTimeOffset.Now - _failedAt < RetryAfterFailure) return;

            if (!IsQuiet())
            {
                _logger.LogInformation("새 판 {Version} 이 있지만 지금은 조용한 때가 아니라 미룹니다.", info.Version);
                return;
            }

            _state.Log.Write("업데이트", $"새 판 {info.Version} 을 받습니다 (지금 {Current}).");

            var (ok, message) = await connection.DownloadUpdateAsync(DownloadPath, info.Sha256, token);
            if (!ok)
            {
                Fail(info.Version, message);
                return;
            }

            //  ⚠⚠ 받는 사이에 사정이 바뀌었을 수 있다(퇴근 시간이 됐다든지) — **한 번 더** 본다.
            if (!IsQuiet())
            {
                _state.Log.Write("업데이트", "새 판을 받아 두었습니다. 조용할 때 설치합니다.");
                return;
            }

            Install(info.Version);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            //  ⚠ 업데이트는 **못 해도 그만인 일**이다. 여기서 터뜨려 감시를 멈추게 하지 않는다.
            _logger.LogWarning(ex, "새 판을 확인하지 못했습니다.");
        }
    }

    /// <summary>
    /// 지금 설치해도 되는 때인가.
    ///
    /// ⚠⚠ **차단 중·카운트다운 중·경고가 떠 있는 중에는 하지 않는다.**
    ///   그때 서비스가 잠깐 멈추면 직원 화면에서 경고가 사라지고, 사람은 「풀렸구나」로 본다.
    /// </summary>
    private bool IsQuiet()
    {
        try
        {
            var status = _state.Status;

            if (status.CountdownActive) return false;
            if (status.NoticeMinutes is not null) return false;
            if (status.State == GuardState.Blocked) return false;

            //  ⚠ 차단까지 10분도 안 남았으면 지금 건드리지 않는다.
            if (status.RemainingSeconds is { } remaining && remaining < 600) return false;

            return true;
        }
        catch (Exception)
        {
            //  ⚠ 상태를 못 읽었으면 **안 하는 쪽**으로 기운다. 미루는 것은 안전하지만 잘못 끼어드는 것은 아니다.
            return false;
        }
    }

    /// <summary>
    /// 설치 프로그램을 조용히 돌린다.
    ///
    /// ⚠⚠⚠ 이 프로그램이 **이 서비스를 멈추고 파일을 바꾼 뒤 다시 시작**한다.
    ///   그래서 여기서는 결과를 기다리지 않는다 — 기다리면 우리가 멈추는 것을 우리가 기다리는 꼴이 된다.
    ///   (부모가 먼저 죽어도 설치 프로그램은 계속 돈다.)
    /// </summary>
    private void Install(string version)
    {
        try
        {
            var start = new ProcessStartInfo
            {
                FileName = DownloadPath,
                //  ⚠ 조용히 설치하는 명령줄. 직원 화면에 설치 창이 뜨면 안 된다.
                Arguments = "/설치",
                UseShellExecute = false,
                CreateNoWindow = true,
                WorkingDirectory = Path.GetDirectoryName(DownloadPath)!
            };

            var process = Process.Start(start);

            if (process is null)
            {
                Fail(version, "설치 프로그램을 시작하지 못했습니다.");
                return;
            }

            _state.Log.Write("업데이트", $"새 판 {version} 을 설치합니다. 잠시 뒤 서비스가 다시 시작됩니다.");
            _state.QueueEvent("업데이트", $"새 판 {version} 설치를 시작했습니다.");
            _logger.LogInformation("새 판 {Version} 설치를 시작했습니다.", version);
        }
        catch (Exception ex)
        {
            Fail(version, ex.Message);
        }
    }

    private void Fail(string version, string message)
    {
        _failedVersion = version;
        _failedAt = DateTimeOffset.Now;

        _state.Log.Write("업데이트", $"새 판 {version} 을 적용하지 못했습니다: {message}");
        _state.QueueEvent("업데이트", $"새 판 {version} 적용 실패: {message}");
        _logger.LogWarning("새 판 {Version} 을 적용하지 못했습니다: {Message}", version, message);
    }

    private static string Trim(string? text) => (text ?? string.Empty).Trim();
}
