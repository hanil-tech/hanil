using System.Security.Claims;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Server.Data;
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
    private readonly ILogger<LoginModel> _logger;

    public LoginModel(GuardDbContext db, ILogger<LoginModel> logger)
    {
        _db = db;
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
            _logger.LogWarning("로그인 실패: {UserName} (원격지 {Ip})",
                UserName, HttpContext.Connection.RemoteIpAddress);

            Error = "아이디 또는 비밀번호가 올바르지 않습니다.";
            return Page();
        }

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

        _logger.LogInformation("로그인: {UserName}", user.UserName);

        return RedirectToPage("/Index");
    }
}
