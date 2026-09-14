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
    internal static (bool Ok, string Detail) Execute(GuardAction action)
    {
        try
        {
            return action switch
            {
                GuardAction.Shutdown => Shutdown(),
                GuardAction.LogOff => LogOff(),
                GuardAction.Lock => LockWorkstation(),
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
