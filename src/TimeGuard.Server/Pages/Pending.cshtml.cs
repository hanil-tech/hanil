using Hanil.TimeGuard.Server.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

/// <summary>
/// 사내망에서 발견된 PC 를 승인하거나 거절한다.
///
/// 등록 키를 받아 적지 않아도 되도록, 직원 PC 가 스스로 자기를 알리고
/// 관리자가 목록에서 확인해 승인하는 방식이다.
/// </summary>
public sealed class PendingModel : PageModel
{
    private const int RecentRejectedCount = 20;

    private readonly GuardDbContext _db;
    private readonly ILogger<PendingModel> _logger;

    public PendingModel(GuardDbContext db, ILogger<PendingModel> logger)
    {
        _db = db;
        _logger = logger;
    }

    public List<Device> Pending { get; private set; } = new();
    public List<Device> Rejected { get; private set; } = new();
    public int PendingRequestCount { get; private set; }

    public async Task OnGetAsync(CancellationToken cancellationToken) => await LoadAsync(cancellationToken);

    public async Task<IActionResult> OnPostApproveAsync(string deviceId, CancellationToken cancellationToken)
    {
        var device = await _db.Devices.FirstOrDefaultAsync(d => d.Id == deviceId, cancellationToken);

        if (device is null)
        {
            TempData["Error"] = "해당 PC 를 찾을 수 없습니다.";
            return RedirectToPage();
        }

        Approve(device);
        await _db.SaveChangesAsync(cancellationToken);

        TempData["Ok"] = $"'{device.MachineName}' 을(를) 승인했습니다. 곧 시간표를 받아 갑니다.";
        return RedirectToPage();
    }

    public async Task<IActionResult> OnPostApproveAllAsync(CancellationToken cancellationToken)
    {
        var pending = await _db.Devices
            .Where(d => d.Approval == ApprovalState.Pending)
            .ToListAsync(cancellationToken);

        foreach (var device in pending) Approve(device);

        await _db.SaveChangesAsync(cancellationToken);

        TempData["Ok"] = $"{pending.Count} 대를 승인했습니다.";
        return RedirectToPage();
    }

    public async Task<IActionResult> OnPostRejectAsync(string deviceId, CancellationToken cancellationToken)
    {
        var device = await _db.Devices.FirstOrDefaultAsync(d => d.Id == deviceId, cancellationToken);

        if (device is null)
        {
            TempData["Error"] = "해당 PC 를 찾을 수 없습니다.";
            return RedirectToPage();
        }

        device.Approval = ApprovalState.Rejected;
        device.DecidedAt = DateTimeOffset.Now;
        device.DecidedBy = User.Identity?.Name ?? "관리자";

        // 토큰을 지워 두면 혹시 남아 있던 연결도 끊긴다.
        device.TokenHash = string.Empty;

        _db.DeviceEvents.Add(new DeviceEvent
        {
            DeviceId = device.Id,
            Category = "등록",
            Message = $"관리자가 등록을 거절했습니다. (처리자: {device.DecidedBy})"
        });

        await _db.SaveChangesAsync(cancellationToken);

        _logger.LogInformation("PC 등록을 거절했습니다: {Machine}", device.MachineName);

        TempData["Ok"] = $"'{device.MachineName}' 의 등록을 거절했습니다.";
        return RedirectToPage();
    }

    private void Approve(Device device)
    {
        if (device.Approval == ApprovalState.Approved) return;

        device.Approval = ApprovalState.Approved;
        device.DecidedAt = DateTimeOffset.Now;
        device.DecidedBy = User.Identity?.Name ?? "관리자";

        _db.DeviceEvents.Add(new DeviceEvent
        {
            DeviceId = device.Id,
            Category = "등록",
            Message = $"관리자가 승인했습니다. (처리자: {device.DecidedBy})"
        });

        _logger.LogInformation("PC 를 승인했습니다: {Machine}", device.MachineName);
    }

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        Pending = await _db.Devices
            .Where(d => d.Approval == ApprovalState.Pending)
            .OrderBy(d => d.AnnouncedAt)
            .ToListAsync(cancellationToken);

        Rejected = await _db.Devices
            .Where(d => d.Approval == ApprovalState.Rejected)
            .OrderByDescending(d => d.DecidedAt)
            .Take(RecentRejectedCount)
            .ToListAsync(cancellationToken);

        PendingRequestCount = await _db.ExtensionRequests
            .CountAsync(r => r.Status == RequestStatus.Pending, cancellationToken);
    }
}
