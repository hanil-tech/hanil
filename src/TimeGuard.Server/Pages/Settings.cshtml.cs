using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Server.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

public sealed class SettingsModel : PageModel
{
    private readonly GuardDbContext _db;
    private readonly SettingsService _settings;

    public SettingsModel(GuardDbContext db, SettingsService settings)
    {
        _db = db;
        _settings = settings;
    }

    public string EnrollmentKey { get; private set; } = string.Empty;
    public int OfflineAfterMinutes { get; private set; } = 5;
    public int DeviceCount { get; private set; }
    public int EventCount { get; private set; }
    public string DatabasePath { get; private set; } = string.Empty;
    public int PendingRequestCount { get; private set; }

    /// <summary>설치 명령 예시에 쓸 서버 주소. 지금 접속한 주소를 그대로 보여 준다.</summary>
    public string ServerUrlHint => $"{Request.Scheme}://{Request.Host}";

    public async Task OnGetAsync(CancellationToken cancellationToken) => await LoadAsync(cancellationToken);

    public async Task<IActionResult> OnPostRegenerateKeyAsync(CancellationToken cancellationToken)
    {
        var key = SettingsService.GenerateReadableKey();
        await _settings.SetAsync(SettingsService.EnrollmentKeyName, key, cancellationToken);

        TempData["Ok"] = "등록 키를 새로 만들었습니다.";
        return RedirectToPage();
    }

    public async Task<IActionResult> OnPostOfflineAsync(int minutes, CancellationToken cancellationToken)
    {
        if (minutes < 2 || minutes > 120)
        {
            TempData["Error"] = "2분에서 120분 사이로 입력해 주세요.";
            return RedirectToPage();
        }

        await _settings.SetAsync(SettingsService.OfflineMinutesName, minutes.ToString(), cancellationToken);

        TempData["Ok"] = "저장했습니다.";
        return RedirectToPage();
    }

    public async Task<IActionResult> OnPostPasswordAsync(
        string current, string next, string confirm, CancellationToken cancellationToken)
    {
        var userName = User.Identity?.Name;
        var user = await _db.AdminUsers.FirstOrDefaultAsync(u => u.UserName == userName, cancellationToken);

        if (user is null)
        {
            TempData["Error"] = "관리자 계정을 찾을 수 없습니다.";
            return RedirectToPage();
        }

        if (!PasswordHasher.Verify(current ?? string.Empty, user.PasswordHash))
        {
            TempData["Error"] = "현재 비밀번호가 올바르지 않습니다.";
            return RedirectToPage();
        }

        if (next != confirm)
        {
            TempData["Error"] = "새 비밀번호가 서로 다릅니다.";
            return RedirectToPage();
        }

        if (!PasswordHasher.IsAcceptable(next ?? string.Empty, out var problem))
        {
            TempData["Error"] = problem;
            return RedirectToPage();
        }

        user.PasswordHash = PasswordHasher.Hash(next!);
        await _db.SaveChangesAsync(cancellationToken);

        TempData["Ok"] = "비밀번호를 변경했습니다.";
        return RedirectToPage();
    }

    private async Task LoadAsync(CancellationToken cancellationToken)
    {
        EnrollmentKey = await _settings.GetOrCreateEnrollmentKeyAsync(cancellationToken);
        OfflineAfterMinutes = await _settings.GetOfflineAfterMinutesAsync(cancellationToken);
        DeviceCount = await _db.Devices.CountAsync(cancellationToken);
        EventCount = await _db.DeviceEvents.CountAsync(cancellationToken);
        DatabasePath = _db.Database.GetDbConnection().DataSource;

        PendingRequestCount = await _db.ExtensionRequests
            .CountAsync(r => r.Status == RequestStatus.Pending, cancellationToken);
    }
}
