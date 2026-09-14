using Hanil.TimeGuard.Server.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

public sealed class RequestsModel : PageModel
{
    private const int RecentDecidedCount = 30;

    private readonly GuardDbContext _db;

    public RequestsModel(GuardDbContext db) => _db = db;

    public sealed record RequestView(ExtensionRequest Request, string DeviceName);

    public List<RequestView> Pending { get; private set; } = new();
    public List<RequestView> Decided { get; private set; } = new();

    public async Task OnGetAsync(CancellationToken cancellationToken) => await LoadAsync(cancellationToken);

    public async Task<IActionResult> OnPostApproveAsync(int requestId, int minutes, CancellationToken cancellationToken)
    {
        var request = await _db.ExtensionRequests
            .Include(r => r.Device)
            .FirstOrDefaultAsync(r => r.Id == requestId, cancellationToken);

        if (request is null)
        {
            TempData["Error"] = "요청을 찾을 수 없습니다.";
            return RedirectToPage();
        }

        if (request.Status != RequestStatus.Pending)
        {
            TempData["Error"] = "이미 처리된 요청입니다.";
            return RedirectToPage();
        }

        if (minutes <= 0 || minutes > 1440)
        {
            TempData["Error"] = "승인 시간은 1분에서 1440분 사이여야 합니다.";
            return RedirectToPage();
        }

        var until = DateTimeOffset.Now.AddMinutes(minutes);

        request.Status = RequestStatus.Approved;
        request.GrantedMinutes = minutes;
        request.GrantedUntil = until;
        request.DecidedAt = DateTimeOffset.Now;
        request.DecidedBy = User.Identity?.Name;

        // 승인한 연장을 해당 PC 에 실제로 적용한다.
        // 이미 더 늦은 시각까지 연장돼 있다면 줄이지 않는다.
        if (request.Device is not null)
        {
            if (request.Device.ExtensionUntil is not { } existing || existing < until)
                request.Device.ExtensionUntil = until;

            _db.DeviceEvents.Add(new DeviceEvent
            {
                DeviceId = request.DeviceId,
                Category = "승인",
                Message = $"연장 요청을 승인했습니다. {minutes}분 ({until:MM-dd HH:mm} 까지), 처리자: {User.Identity?.Name}"
            });
        }

        await _db.SaveChangesAsync(cancellationToken);

        TempData["Ok"] = $"승인했습니다. {until.ToLocalTime():HH:mm} 까지 사용할 수 있습니다.";
        return RedirectToPage();
    }

    public async Task<IActionResult> OnPostDenyAsync(int requestId, string? note, CancellationToken cancellationToken)
    {
        var request = await _db.ExtensionRequests
            .FirstOrDefaultAsync(r => r.Id == requestId, cancellationToken);

        if (request is null)
        {
            TempData["Error"] = "요청을 찾을 수 없습니다.";
            return RedirectToPage();
        }

        if (request.Status != RequestStatus.Pending)
        {
            TempData["Error"] = "이미 처리된 요청입니다.";
            return RedirectToPage();
        }

        request.Status = RequestStatus.Denied;
        request.DecidedAt = DateTimeOffset.Now;
        request.DecidedBy = User.Identity?.Name;
        request.DecisionNote = string.IsNullOrWhiteSpace(note) ? null : note.Trim();

        _db.DeviceEvents.Add(new DeviceEvent
        {
            DeviceId = request.DeviceId,
            Category = "거절",
            Message = $"연장 요청을 거절했습니다. 처리자: {User.Identity?.Name}" +
                      (request.DecisionNote is null ? string.Empty : $", 사유: {request.DecisionNote}")
        });

        await _db.SaveChangesAsync(cancellationToken);

        TempData["Ok"] = "거절했습니다.";
        return RedirectToPage();
    }

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        var pending = await _db.ExtensionRequests
            .Include(r => r.Device)
            .Where(r => r.Status == RequestStatus.Pending)
            .OrderBy(r => r.RequestedAt)
            .ToListAsync(cancellationToken);

        var decided = await _db.ExtensionRequests
            .Include(r => r.Device)
            .Where(r => r.Status != RequestStatus.Pending)
            .OrderByDescending(r => r.DecidedAt)
            .Take(RecentDecidedCount)
            .ToListAsync(cancellationToken);

        Pending = pending.Select(r => new RequestView(r, DescribeDevice(r))).ToList();
        Decided = decided.Select(r => new RequestView(r, DescribeDevice(r))).ToList();
    }

    private static string DescribeDevice(ExtensionRequest request)
    {
        if (request.Device is null) return "(삭제된 PC)";

        return string.IsNullOrWhiteSpace(request.Device.DisplayName)
            ? request.Device.MachineName
            : request.Device.DisplayName;
    }
}
