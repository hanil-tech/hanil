using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using Hanil.TimeGuard.Core.Config;
using static Hanil.TimeGuard.Service.Interop.NativeMethods;

namespace Hanil.TimeGuard.Service.Interop;

/// <summary>전원 차단·로그오프·화면 잠금을 실제로 수행한다.</summary>
[SupportedOSPlatform("windows")]
internal static class PowerController
{
    /// <summary>
    /// 설정된 조치를 수행한다. 성공 여부와 설명을 돌려준다.
    /// 실패해도 예외를 밖으로 던지지 않고 서비스가 계속 돌게 한다.
    /// </summary>
    internal static (bool Ok, string Detail) Execute(GuardAction action, IReadOnlyList<string>? neverLock = null)
    {
        try
        {
            return action switch
            {
                GuardAction.Shutdown => Shutdown(),
                GuardAction.LogOff => LogOff(),
                GuardAction.Lock => LockWorkstation(),
                GuardAction.AccountLock => LockAccount(neverLock ?? Array.Empty<string>()),
                _ => (false, $"알 수 없는 조치: {action}")
            };
        }
        catch (Exception ex)
        {
            return (false, $"조치 수행 중 오류: {ex.Message}");
        }
    }

    private static (bool, string) Shutdown()
    {
        if (!EnableShutdownPrivilege(out var privilegeError))
            return (false, $"종료 권한을 얻지 못했습니다: {privilegeError}");

        // timeout 0, forceAppsClosed true: 우리 쪽에서 이미 경고와 카운트다운을 마친 뒤라
        // 여기서는 지체 없이 종료한다.
        var ok = InitiateSystemShutdownExW(
            machineName: null,
            message: null,
            timeout: 0,
            forceAppsClosed: true,
            rebootAfterShutdown: false,
            reason: SHTDN_REASON_MAJOR_APPLICATION | SHTDN_REASON_MINOR_MAINTENANCE | SHTDN_REASON_FLAG_PLANNED);

        return ok
            ? (true, "전원 차단을 실행했습니다.")
            : (false, $"전원 차단 실패: {new Win32Exception(Marshal.GetLastWin32Error()).Message}");
    }

    private static (bool, string) LogOff()
    {
        var sessionId = SessionLauncher.FindActiveSessionId();
        if (sessionId is null) return (false, "로그온한 사용자 세션을 찾지 못했습니다.");

        var ok = WTSLogoffSession(WTS_CURRENT_SERVER_HANDLE, sessionId.Value, wait: false);

        return ok
            ? (true, $"세션 {sessionId} 를 로그오프했습니다.")
            : (false, $"로그오프 실패: {new Win32Exception(Marshal.GetLastWin32Error()).Message}");
    }

    private static (bool, string) LockWorkstation()
    {
        // 서비스는 세션 0 에 있어 LockWorkStation 을 직접 부를 수 없다.
        // 사용자 세션에서 rundll32 로 대신 실행한다.
        var system32 = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "rundll32.exe");
        var launched = SessionLauncher.LaunchInActiveSession(
            $"\"{system32}\" user32.dll,LockWorkStation", showWindow: false, out var error);

        return launched
            ? (true, "화면을 잠갔습니다.")
            : (false, $"화면 잠금 실패: {error}");
    }

    /// <summary>
    /// 지금 로그인한 계정을 잠그고 로그오프한다.
    /// 직원이 다시 로그인할 수 없게 되며, 스스로 풀 수도 없다.
    /// </summary>
    /// <returns>성공 여부와 설명. 성공하면 잠근 계정 이름도 함께 돌려준다.</returns>
    internal static (bool Ok, string Detail, string? LockedUser) LockAccountDetailed(IReadOnlyList<string> neverLock)
    {
        var user = SessionLauncher.GetActiveSessionUser();

        if (string.IsNullOrWhiteSpace(user))
            return (false, "로그인한 사용자를 찾지 못했습니다.", null);

        var name = AccountController.StripDomain(user);

        // 관리자가 제외 대상으로 지정한 계정은 잠그지 않는다.
        foreach (var exempt in neverLock)
        {
            if (string.Equals(AccountController.StripDomain(exempt), name, StringComparison.OrdinalIgnoreCase))
                return (false, $"'{name}' 은(는) 제외 계정이라 잠그지 않았습니다.", null);
        }

        // 관리자 계정을 잠그면 그 PC 를 되돌릴 방법이 없어진다.
        if (!AccountController.CanLock(user, out var reason))
            return (false, $"계정을 잠그지 않았습니다: {reason}", null);

        var (locked, detail) = AccountController.Lock(user);
        if (!locked) return (false, detail, null);

        // 잠그기만 하면 이미 로그인한 상태는 그대로 유지되므로 로그오프까지 해야 한다.
        var (loggedOff, logoffDetail) = LogOff();

        return loggedOff
            ? (true, $"{detail} 로그오프했습니다.", name)
            : (true, $"{detail} 다만 로그오프하지 못했습니다: {logoffDetail}", name);
    }

    private static (bool, string) LockAccount(IReadOnlyList<string> neverLock)
    {
        var (ok, detail, _) = LockAccountDetailed(neverLock);
        return (ok, detail);
    }

    /// <summary>계정 잠금을 푼다.</summary>
    internal static (bool Ok, string Detail) UnlockAccount(string userName) =>
        AccountController.Unlock(userName);

    /// <summary>예약된 시스템 종료를 취소한다. InitiateSystemShutdownEx 가 이미 실행된 뒤에는 효과가 없다.</summary>
    internal static bool AbortShutdown()
    {
        try
        {
            EnableShutdownPrivilege(out _);
            return AbortSystemShutdownW(null);
        }
        catch
        {
            return false;
        }
    }

    private static bool EnableShutdownPrivilege(out string error)
    {
        error = string.Empty;
        var token = IntPtr.Zero;

        try
        {
            if (!OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, out token))
            {
                error = new Win32Exception(Marshal.GetLastWin32Error()).Message;
                return false;
            }

            if (!LookupPrivilegeValueW(null, SE_SHUTDOWN_NAME, out var luid))
            {
                error = new Win32Exception(Marshal.GetLastWin32Error()).Message;
                return false;
            }

            var privileges = new TOKEN_PRIVILEGES
            {
                PrivilegeCount = 1,
                Privileges = new LUID_AND_ATTRIBUTES { Luid = luid, Attributes = SE_PRIVILEGE_ENABLED }
            };

            if (!AdjustTokenPrivileges(token, false, ref privileges,
                    Marshal.SizeOf<TOKEN_PRIVILEGES>(), IntPtr.Zero, IntPtr.Zero))
            {
                error = new Win32Exception(Marshal.GetLastWin32Error()).Message;
                return false;
            }

            // AdjustTokenPrivileges 는 일부만 적용돼도 true 를 돌려주므로 마지막 오류를 따로 확인한다.
            var lastError = Marshal.GetLastWin32Error();
            if (lastError != 0)
            {
                error = new Win32Exception(lastError).Message;
                return false;
            }

            return true;
        }
        finally
        {
            if (token != IntPtr.Zero) CloseHandle(token);
        }
    }
}
