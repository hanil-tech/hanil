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

    public async Task OnGetAsync(CancellationToken cancellationToken)
    {
        OfflineAfterMinutes = await _settings.GetOfflineAfterMinutesAsync(cancellationToken);

        var devices = await _db.Devices
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
    }
}
