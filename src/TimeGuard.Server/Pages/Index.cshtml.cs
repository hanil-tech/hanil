using Hanil.TimeGuard.Server.Data;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

public sealed class IndexModel : PageModel
{
    private readonly GuardDbContext _db;
    private readonly SettingsService _settings;

    public IndexModel(GuardDbContext db, SettingsService settings)
    {
        _db = db;
        _settings = settings;
    }

    public List<DeviceView> Devices { get; private set; } = new();
    public int PendingRequestCount { get; private set; }
    public int OfflineAfterMinutes { get; private set; } = 5;

    /// <summary>최근 하루 동안의 보안 기록 수.</summary>
    public int RecentSecurityCount { get; private set; }

    /// <summary>직원이 관리자 권한으로 로그인해 제한을 피할 수 있는 PC 수.</summary>
    public int BypassableCount { get; private set; }

    /// <summary>승인을 기다리는 PC 수.</summary>
    public int WaitingApprovalCount { get; private set; }

    public async Task OnGetAsync(CancellationToken cancellationToken)
    {
        OfflineAfterMinutes = await _settings.GetOfflineAfterMinutesAsync(cancellationToken);

        // 승인되지 않은 PC 는 [새 PC 승인] 화면에서 다룬다.
        var devices = await _db.Devices
            .Where(d => d.Approval == ApprovalState.Approved)
            .OrderBy(d => d.DisplayName)
            .ThenBy(d => d.MachineName)
            .ToListAsync(cancellationToken);

        // 대기 중인 요청 수를 PC 별로 한 번에 세어 둔다(목록에서 반복 조회하지 않도록).
        var pendingByDevice = await _db.ExtensionRequests
            .Where(r => r.Status == RequestStatus.Pending)
            .GroupBy(r => r.DeviceId)
            .Select(g => new { DeviceId = g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.DeviceId, x => x.Count, cancellationToken);

        Devices = devices
            .Select(d => DeviceView.From(d, OfflineAfterMinutes,
                pendingByDevice.TryGetValue(d.Id, out var count) ? count : 0))
            .ToList();

        PendingRequestCount = pendingByDevice.Values.Sum();

        var since = DateTimeOffset.Now.AddDays(-1);
        RecentSecurityCount = await _db.DeviceEvents
            .CountAsync(e => e.Category == "보안" && e.At > since, cancellationToken);

        BypassableCount = Devices.Count(d => d.UserCanBypass);

        WaitingApprovalCount = await _db.Devices
            .CountAsync(d => d.Approval == ApprovalState.Pending, cancellationToken);
    }
}
