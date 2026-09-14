using System.Text.Json;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Server.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

public sealed class PolicyModel : PageModel
{
    private readonly GuardDbContext _db;
    private readonly PolicyService _policies;

    public PolicyModel(GuardDbContext db, PolicyService policies)
    {
        _db = db;
        _policies = policies;
    }

    public WeeklySchedule Schedule { get; private set; } = WeeklySchedule.CreateDefault();
    public WarningSettings Warnings { get; private set; } = new();
    public GuardAction Action { get; private set; } = GuardAction.Shutdown;
    public HolidayPolicy HolidayPolicy { get; private set; } = HolidayPolicy.Blocked;
    public bool BlockRemoteAccess { get; private set; }
    public string HolidaysText { get; private set; } = string.Empty;
    public string ExemptUsersText { get; private set; } = string.Empty;
    public string NoticeMinutesText { get; private set; } = string.Empty;
    public int DevicesUsingDefault { get; private set; }
    public int PendingRequestCount { get; private set; }

    public async Task OnGetAsync(CancellationToken cancellationToken) => await LoadAsync(cancellationToken);

    public async Task<IActionResult> OnPostAsync(
        string action,
        string holidayPolicy,
        bool blockRemoteAccess,
        string? noticeMinutes,
        int countdownSeconds,
        int graceSeconds,
        string? message,
        string? holidays,
        string? exemptUsers,
        CancellationToken cancellationToken)
    {
        var policy = await _policies.GetDefaultPolicyAsync(cancellationToken);

        // --- 시간표 ---
        var schedule = new WeeklySchedule();

        foreach (var day in ScheduleText.WeekOrder)
        {
            var raw = Request.Form[$"day_{day}"].ToString();

            if (!ScheduleText.TryParse(raw, out var windows, out var error))
            {
                TempData["Error"] = $"{ScheduleText.KoreanDay(day)}: {error}";
                await LoadAsync(cancellationToken);
                return Page();
            }

            schedule.SetDay(day, windows);
        }

        // --- 경고 ---
        var minutes = ParseMinutes(noticeMinutes, out var minutesError);
        if (minutesError is not null)
        {
            TempData["Error"] = minutesError;
            await LoadAsync(cancellationToken);
            return Page();
        }

        var warnings = new WarningSettings
        {
            NoticeMinutes = minutes.Count > 0 ? minutes : new List<int> { 10, 5, 1 },
            CountdownSeconds = Math.Clamp(countdownSeconds, 0, 600),
            OutsideWindowGraceSeconds = Math.Clamp(graceSeconds, 0, 3600),
            Message = string.IsNullOrWhiteSpace(message)
                ? "허용된 사용 시간이 끝났습니다. 작업 중인 내용을 저장해 주세요."
                : message.Trim()
        };

        // --- 휴일 ---
        var holidayList = SplitList(holidays);
        var invalidHoliday = holidayList.FirstOrDefault(h => !DateOnly.TryParse(h, out _));

        if (invalidHoliday is not null)
        {
            TempData["Error"] = $"휴일 '{invalidHoliday}' 의 날짜 형식이 올바르지 않습니다. yyyy-MM-dd 로 입력해 주세요.";
            await LoadAsync(cancellationToken);
            return Page();
        }

        var normalizedHolidays = holidayList
            .Select(h => DateOnly.Parse(h).ToString("yyyy-MM-dd"))
            .Distinct()
            .OrderBy(h => h, StringComparer.Ordinal)
            .ToList();

        // --- 저장 ---
        policy.ScheduleJson = JsonSerializer.Serialize(schedule, IpcJson.Options);
        policy.WarningsJson = JsonSerializer.Serialize(warnings, IpcJson.Options);
        policy.Action = Enum.TryParse<GuardAction>(action, out var parsedAction)
            ? parsedAction.ToString()
            : nameof(GuardAction.Shutdown);
        policy.HolidayPolicy = Enum.TryParse<HolidayPolicy>(holidayPolicy, out var parsedHoliday)
            ? parsedHoliday.ToString()
            : nameof(Core.Config.HolidayPolicy.Blocked);
        policy.HolidaysJson = JsonSerializer.Serialize(normalizedHolidays, IpcJson.Options);
        policy.ExemptUsersJson = JsonSerializer.Serialize(SplitList(exemptUsers), IpcJson.Options);
        policy.BlockRemoteAccess = blockRemoteAccess;

        await _policies.BumpDefaultVersionAsync(User.Identity?.Name ?? "관리자", cancellationToken);

        TempData["Ok"] = "기본 시간표를 저장했습니다. 각 PC 가 다음 연락 때 반영합니다.";
        return RedirectToPage();
    }

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        var policy = await _policies.GetDefaultPolicyAsync(cancellationToken);

        Schedule = Deserialize<WeeklySchedule>(policy.ScheduleJson) ?? WeeklySchedule.CreateDefault();
        Warnings = Deserialize<WarningSettings>(policy.WarningsJson) ?? new WarningSettings();
        Action = Enum.TryParse<GuardAction>(policy.Action, out var action) ? action : GuardAction.Shutdown;
        HolidayPolicy = Enum.TryParse<HolidayPolicy>(policy.HolidayPolicy, out var holiday)
            ? holiday
            : Core.Config.HolidayPolicy.Blocked;

        BlockRemoteAccess = policy.BlockRemoteAccess;
        HolidaysText = string.Join(", ", Deserialize<List<string>>(policy.HolidaysJson) ?? new List<string>());
        ExemptUsersText = string.Join(", ", Deserialize<List<string>>(policy.ExemptUsersJson) ?? new List<string>());
        NoticeMinutesText = string.Join(", ", Warnings.OrderedNoticeMinutes);

        DevicesUsingDefault = await _db.Devices.CountAsync(d => d.UsesDefaultPolicy, cancellationToken);
        PendingRequestCount = await _db.ExtensionRequests
            .CountAsync(r => r.Status == RequestStatus.Pending, cancellationToken);
    }

    private static List<int> ParseMinutes(string? input, out string? error)
    {
        error = null;
        var result = new List<int>();

        if (string.IsNullOrWhiteSpace(input)) return result;

        foreach (var part in input.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!int.TryParse(part, out var value) || value <= 0 || value > 1440)
            {
                error = $"'{part}' 는 1 이상 1440 이하의 분 단위 숫자가 아닙니다.";
                return new List<int>();
            }

            result.Add(value);
        }

        return result;
    }

    private static List<string> SplitList(string? input) =>
        string.IsNullOrWhiteSpace(input)
            ? new List<string>()
            : input.Split(new[] { ',', '\n', '\r', ';' }, StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                   .Distinct()
                   .ToList();

    private static T? Deserialize<T>(string? json)
    {
        if (string.IsNullOrWhiteSpace(json)) return default;
        try { return JsonSerializer.Deserialize<T>(json, IpcJson.Options); }
        catch (JsonException) { return default; }
    }
}
