using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Server.Data;
using Hanil.TimeGuard.Server.Security;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

public sealed class SettingsModel : PageModel
{
    private readonly GuardDbContext _db;
    private readonly SettingsService _settings;
    private readonly AdminAccessPolicy _adminAccess;

    public SettingsModel(GuardDbContext db, SettingsService settings, AdminAccessPolicy adminAccess)
    {
        _db = db;
        _settings = settings;
        _adminAccess = adminAccess;
    }

    public string EnrollmentKey { get; private set; } = string.Empty;
    public int OfflineAfterMinutes { get; private set; } = 5;
    public int DeviceCount { get; private set; }
    public int EventCount { get; private set; }
    public string DatabasePath { get; private set; } = string.Empty;
    public int PendingRequestCount { get; private set; }

    /// <summary>관리 화면을 열 수 있는 주소. 비어 있으면 제한 없음.</summary>
    public string AdminAddresses { get; private set; } = string.Empty;

    public bool AdminAddressesEnabled { get; private set; }

    /// <summary>지금 이 화면을 보고 있는 PC 의 주소.</summary>
    public string CurrentAddress { get; private set; } = string.Empty;

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

    /// <summary>관리 화면 접근을 제한한다. 빈 값이면 제한을 푼다.</summary>
    public async Task<IActionResult> OnPostAdminAccessAsync(string? addresses, CancellationToken cancellationToken)
    {
        var problems = _adminAccess.Update(addresses);

        if (problems.Count > 0)
        {
            // 잘못 적은 항목이 있으면 저장하지 않는다. 반쯤 적용되면 오히려 위험하다.
            _adminAccess.Update(await _settings.GetAdminAddressesAsync(cancellationToken));

            TempData["Error"] = $"다음 주소를 알아볼 수 없습니다: {string.Join(", ", problems)}";
            return RedirectToPage();
        }

        await _settings.SetAsync(SettingsService.AdminAddressesName, addresses?.Trim() ?? string.Empty, cancellationToken);

        TempData["Ok"] = string.IsNullOrWhiteSpace(addresses)
            ? "접근 제한을 풀었습니다. 이제 사내망 어느 PC 에서나 관리 화면이 열립니다."
            : "저장했습니다. 지정한 주소에서만 관리 화면이 열립니다.";

        return RedirectToPage();
    }

    /// <summary>지금 접속 중인 PC 만 허용하도록 한 번에 설정한다.</summary>
    public async Task<IActionResult> OnPostRestrictToMeAsync(CancellationToken cancellationToken)
    {
        var address = DescribeCurrentAddress();

        if (string.IsNullOrWhiteSpace(address) || address == "::1" || address == "127.0.0.1")
        {
            TempData["Error"] = "서버 PC 에서 직접 접속 중이라 제한할 주소를 알 수 없습니다. " +
                                "관리자 PC 에서 접속한 뒤 다시 눌러 주세요.";
            return RedirectToPage();
        }

        _adminAccess.Update(address);
        await _settings.SetAsync(SettingsService.AdminAddressesName, address, cancellationToken);

        TempData["Ok"] = $"이제 {address} 와 서버 PC 에서만 관리 화면이 열립니다.";
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

        AdminAddresses = _adminAccess.Configured;
        AdminAddressesEnabled = _adminAccess.Enabled;
        CurrentAddress = DescribeCurrentAddress();
    }

    /// <summary>지금 접속 중인 PC 의 주소를 사람이 읽을 수 있게 만든다.</summary>
    private string DescribeCurrentAddress()
    {
        var address = HttpContext.Connection.RemoteIpAddress;
        if (address is null) return string.Empty;

        // IPv6 으로 감싸인 IPv4 는 원래 형태로 되돌려 보여 준다.
        if (address.IsIPv4MappedToIPv6) address = address.MapToIPv4();

        return address.ToString();
    }
}
