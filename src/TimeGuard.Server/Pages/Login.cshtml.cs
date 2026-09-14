using System.Security.Claims;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Server.Data;
using Hanil.TimeGuard.Server.Security;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

[AllowAnonymous]
public sealed class LoginModel : PageModel
{
    private readonly GuardDbContext _db;
    private readonly LoginThrottle _throttle;
    private readonly ILogger<LoginModel> _logger;

    public LoginModel(GuardDbContext db, LoginThrottle throttle, ILogger<LoginModel> logger)
    {
        _db = db;
        _throttle = throttle;
        _logger = logger;
    }

    [BindProperty]
    public string UserName { get; set; } = string.Empty;

    [BindProperty]
    public string Password { get; set; } = string.Empty;

    public string? Error { get; private set; }

    public IActionResult OnGet()
    {
        if (User.Identity?.IsAuthenticated == true) return RedirectToPage("/Index");
        return Page();
    }

    public async Task<IActionResult> OnPostAsync(CancellationToken cancellationToken)
    {
        var origin = LoginThrottle.DescribeOrigin(HttpContext.Connection.RemoteIpAddress);

        // 먼저 잠겨 있는지 본다. 잠긴 동안에는 비밀번호를 확인조차 하지 않는다.
        if (!_throttle.IsAllowed(origin, out var retryAfter))
        {
            _logger.LogWarning("잠긴 위치에서 로그인을 시도했습니다: {Origin}", origin);

            Error = $"로그인 시도가 너무 많았습니다. {Math.Ceiling(retryAfter.TotalMinutes):0}분 뒤에 다시 시도해 주세요.";
            return Page();
        }

        if (string.IsNullOrWhiteSpace(UserName) || string.IsNullOrEmpty(Password))
        {
            Error = "아이디와 비밀번호를 입력해 주세요.";
            return Page();
        }

        var user = await _db.AdminUsers
            .FirstOrDefaultAsync(u => u.UserName == UserName, cancellationToken);

        // 아이디가 없을 때와 비밀번호가 틀릴 때를 구분해 알려 주지 않는다.
        if (user is null || !PasswordHasher.Verify(Password, user.PasswordHash))
        {
            var locked = _throttle.RecordFailure(origin);

            _logger.LogWarning("로그인 실패: {UserName} (원격지 {Origin}){Locked}",
                UserName, origin, locked ? " — 한도를 넘어 잠갔습니다." : string.Empty);

            if (locked)
            {
                Error = $"로그인 시도가 너무 많았습니다. {LoginThrottle.LockDuration.TotalMinutes:0}분 뒤에 다시 시도해 주세요.";
            }
            else
            {
                var remaining = _throttle.RemainingAttempts(origin);

                Error = remaining <= 2
                    ? $"아이디 또는 비밀번호가 올바르지 않습니다. {remaining}번 더 틀리면 잠깁니다."
                    : "아이디 또는 비밀번호가 올바르지 않습니다.";
            }

            return Page();
        }

        _throttle.RecordSuccess(origin);

        user.LastLoginAt = DateTimeOffset.Now;
        await _db.SaveChangesAsync(cancellationToken);

        var claims = new List<Claim>
        {
            new(ClaimTypes.Name, user.UserName),
            new(ClaimTypes.NameIdentifier, user.Id.ToString())
        };

        var identity = new ClaimsIdentity(claims, CookieAuthenticationDefaults.AuthenticationScheme);

        await HttpContext.SignInAsync(
            CookieAuthenticationDefaults.AuthenticationScheme,
            new ClaimsPrincipal(identity));

        _logger.LogInformation("로그인: {UserName} (원격지 {Origin})", user.UserName, origin);

        return RedirectToPage("/Index");
    }
}
