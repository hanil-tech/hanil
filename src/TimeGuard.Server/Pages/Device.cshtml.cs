using System.Text.Json;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Server.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

public sealed class DeviceModel : PageModel
{
    private const int RecentEventCount = 30;

    private readonly GuardDbContext _db;
    private readonly SettingsService _settings;
    private readonly PolicyService _policies;

    public DeviceModel(GuardDbContext db, SettingsService settings, PolicyService policies)
    {
        _db = db;
        _settings = settings;
        _policies = policies;
    }

    public DeviceView? View { get; private set; }
    public List<DeviceEvent> RecentEvents { get; private set; } = new();
    public WeeklySchedule EditingSchedule { get; private set; } = WeeklySchedule.CreateDefault();
    public int PendingRequestCount { get; private set; }

    public async Task<IActionResult> OnGetAsync(string id, CancellationToken cancellationToken)
    {
        await LoadAsync(id, cancellationToken);
        return Page();
    }

    // ---- 기본 정보 저장 ----

    public async Task<IActionResult> OnPostSaveAsync(
        string id, string? displayName, bool enforced, string? note, CancellationToken cancellationToken)
    {
        var device = await _db.Devices.FirstOrDefaultAsync(d => d.Id == id, cancellationToken);
        if (device is null) return RedirectToPage("/Index");

        device.DisplayName = (displayName ?? string.Empty).Trim();
        device.Note = (note ?? string.Empty).Trim();

        if (device.Enforced != enforced)
        {
            device.Enforced = enforced;
            device.PolicyVersion++;

            await AddEventAsync(device.Id,
                enforced ? "이 PC 에 제한을 적용하도록 바꿨습니다." : "이 PC 의 제한을 껐습니다.", cancellationToken);
        }

        await _db.SaveChangesAsync(cancellationToken);

        TempData["Ok"] = "저장했습니다.";
        return RedirectToPage(new { id });
    }

    // ---- 시간표 저장 ----

    public async Task<IActionResult> OnPostScheduleAsync(
        string id, bool usesDefaultPolicy, CancellationToken cancellationToken)
    {
        var device = await _db.Devices.FirstOrDefaultAsync(d => d.Id == id, cancellationToken);
        if (device is null) return RedirectToPage("/Index");

        if (usesDefaultPolicy)
        {
            device.UsesDefaultPolicy = true;
            device.PolicyVersion++;

            await AddEventAsync(device.Id, "기본 시간표를 따르도록 바꿨습니다.", cancellationToken);
            await _db.SaveChangesAsync(cancellationToken);

            TempData["Ok"] = "기본 시간표를 따르도록 바꿨습니다.";
            return RedirectToPage(new { id });
        }

        // 전용 시간표: 입력한 요일별 값을 읽어들인다.
        var schedule = new WeeklySchedule();

        foreach (var day in ScheduleText.WeekOrder)
        {
            var raw = Request.Form[$"day_{day}"].ToString();

            if (!ScheduleText.TryParse(raw, out var windows, out var error))
            {
                TempData["Error"] = $"{ScheduleText.KoreanDay(day)}: {error}";
                await LoadAsync(id, cancellationToken);
                return Page();
            }

            schedule.SetDay(day, windows);
        }

        device.UsesDefaultPolicy = false;
        device.CustomScheduleJson = JsonSerializer.Serialize(schedule, IpcJson.Options);
        device.PolicyVersion++;

        await AddEventAsync(device.Id, "이 PC 전용 시간표를 저장했습니다.", cancellationToken);
        await _db.SaveChangesAsync(cancellationToken);

        TempData["Ok"] = "전용 시간표를 저장했습니다. 해당 PC 는 다음 연락 때 바로 반영합니다.";
        return RedirectToPage(new { id });
    }

    // ---- 즉시 조치 ----

    public async Task<IActionResult> OnPostExtendAsync(string id, int minutes, CancellationToken cancellationToken)
    {
        var device = await _db.Devices.FirstOrDefaultAsync(d => d.Id == id, cancellationToken);
        if (device is null) return RedirectToPage("/Index");

        if (minutes <= 0)
        {
            device.ExtensionUntil = null;
            await AddEventAsync(device.Id, "관리자가 연장을 취소했습니다.", cancellationToken);
            TempData["Ok"] = "연장을 취소했습니다.";
        }
        else if (minutes > 1440)
        {
            TempData["Error"] = "연장은 한 번에 최대 1440분(24시간)까지 가능합니다.";
            return RedirectToPage(new { id });
        }
        else
        {
            var until = DateTimeOffset.Now.AddMinutes(minutes);
            device.ExtensionUntil = until;

            await AddEventAsync(device.Id,
                $"관리자가 {minutes}분 연장했습니다({until:MM-dd HH:mm} 까지).", cancellationToken);

            TempData["Ok"] = $"{minutes}분 연장했습니다. {until.ToLocalTime():HH:mm} 까지 사용할 수 있습니다.";
        }

        await _db.SaveChangesAsync(cancellationToken);
        return RedirectToPage(new { id });
    }

    public async Task<IActionResult> OnPostSuspendAsync(string id, int minutes, CancellationToken cancellationToken)
    {
        var device = await _db.Devices.FirstOrDefaultAsync(d => d.Id == id, cancellationToken);
        if (device is null) return RedirectToPage("/Index");

        if (minutes <= 0)
        {
            device.SuspendedUntil = null;
            await AddEventAsync(device.Id, "관리자가 일시 중지를 해제했습니다.", cancellationToken);
            TempData["Ok"] = "일시 중지를 해제했습니다.";
        }
        else
        {
            var until = DateTimeOffset.Now.AddMinutes(minutes);
            device.SuspendedUntil = until;

            await AddEventAsync(device.Id,
                $"관리자가 {minutes}분 동안 감시를 중지했습니다({until:MM-dd HH:mm} 까지).", cancellationToken);

            TempData["Ok"] = $"{minutes}분 동안 감시를 중지했습니다.";
        }

        await _db.SaveChangesAsync(cancellationToken);
        return RedirectToPage(new { id });
    }

    public async Task<IActionResult> OnPostDeleteAsync(string id, CancellationToken cancellationToken)
    {
        var device = await _db.Devices.FirstOrDefaultAsync(d => d.Id == id, cancellationToken);
        if (device is null) return RedirectToPage("/Index");

        _db.Devices.Remove(device); // 기록과 요청은 연쇄 삭제된다
        await _db.SaveChangesAsync(cancellationToken);

        TempData["Ok"] = $"'{device.DisplayName}' 등록을 삭제했습니다.";
        return RedirectToPage("/Index");
    }

    // ---- 공통 ----

    private async Task LoadAsync(string id, CancellationToken cancellationToken)
    {
        var device = await _db.Devices.FirstOrDefaultAsync(d => d.Id == id, cancellationToken);
        if (device is null) return;

        var offlineAfter = await _settings.GetOfflineAfterMinutesAsync(cancellationToken);

        var pending = await _db.ExtensionRequests
            .CountAsync(r => r.DeviceId == device.Id && r.Status == RequestStatus.Pending, cancellationToken);

        View = DeviceView.From(device, offlineAfter, pending);

        PendingRequestCount = await _db.ExtensionRequests
            .CountAsync(r => r.Status == RequestStatus.Pending, cancellationToken);

        RecentEvents = await _db.DeviceEvents
            .Where(e => e.DeviceId == device.Id)
            .OrderByDescending(e => e.At)
            .Take(RecentEventCount)
            .ToListAsync(cancellationToken);

        // 편집 화면에는 실제로 적용 중인 시간표를 보여 준다.
        var effective = await _policies.BuildEffectiveConfigAsync(device, cancellationToken);
        EditingSchedule = effective.Schedule;
    }

    private async Task AddEventAsync(string deviceId, string message, CancellationToken cancellationToken)
    {
        _db.DeviceEvents.Add(new DeviceEvent
        {
            DeviceId = deviceId,
            Category = "관리",
            Message = $"{message} (관리자: {User.Identity?.Name})"
        });

        await Task.CompletedTask;
    }
}
