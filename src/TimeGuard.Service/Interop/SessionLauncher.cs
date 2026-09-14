using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using static Hanil.TimeGuard.Service.Interop.NativeMethods;

namespace Hanil.TimeGuard.Service.Interop;

/// <summary>
/// 세션 0 의 서비스에서 로그온한 사용자 세션에 프로세스를 띄운다.
/// 경고 창을 보여 줄 에이전트를 서비스가 직접 기동하기 위해 필요하다.
/// </summary>
[SupportedOSPlatform("windows")]
internal static class SessionLauncher
{
    /// <summary>현재 로그온해 사용 중인 세션 ID 를 찾는다. 없으면 null.</summary>
    internal static uint? FindActiveSessionId()
    {
        var console = WTSGetActiveConsoleSessionId();
        if (console != 0xFFFFFFFF && console != 0) return console;

        // 콘솔 세션이 없으면(원격 데스크톱 등) 활성 세션을 훑어본다.
        var buffer = IntPtr.Zero;
        try
        {
            if (!WTSEnumerateSessionsW(WTS_CURRENT_SERVER_HANDLE, 0, 1, out buffer, out var count))
                return null;

            var size = Marshal.SizeOf<WTS_SESSION_INFO>();
            for (var i = 0; i < count; i++)
            {
                var entry = Marshal.PtrToStructure<WTS_SESSION_INFO>(buffer + i * size);
                if (entry.State == WTS_CONNECTSTATE_CLASS.WTSActive && entry.SessionId != 0)
                    return entry.SessionId;
            }
            return null;
        }
        catch
        {
            return null;
        }
        finally
        {
            if (buffer != IntPtr.Zero) WTSFreeMemory(buffer);
        }
    }

    /// <summary>활성 사용자 세션에서 명령을 실행한다.</summary>
    internal static bool LaunchInActiveSession(string commandLine, bool showWindow, out string error)
    {
        error = string.Empty;

        var sessionId = FindActiveSessionId();
        if (sessionId is null)
        {
            error = "로그온한 사용자 세션이 없습니다.";
            return false;
        }

        return LaunchInSession(sessionId.Value, commandLine, showWindow, out error);
    }

    internal static bool LaunchInSession(uint sessionId, string commandLine, bool showWindow, out string error)
    {
        error = string.Empty;

        var userToken = IntPtr.Zero;
        var primaryToken = IntPtr.Zero;
        var environment = IntPtr.Zero;
        var process = new PROCESS_INFORMATION();

        try
        {
            if (!WTSQueryUserToken(sessionId, out userToken))
            {
                error = $"사용자 토큰을 얻지 못했습니다: {LastError()}";
                return false;
            }

            if (!DuplicateTokenEx(userToken, TOKEN_ALL_ACCESS, IntPtr.Zero,
                    SECURITY_IMPERSONATION_LEVEL.SecurityImpersonation, TOKEN_TYPE.TokenPrimary, out primaryToken))
            {
                error = $"토큰 복제에 실패했습니다: {LastError()}";
                return false;
            }

            if (!CreateEnvironmentBlock(out environment, primaryToken, false))
            {
                // 환경 블록 없이도 실행은 가능하므로 경고만 남기고 계속한다.
                environment = IntPtr.Zero;
            }

            var startupInfo = new STARTUPINFO
            {
                cb = Marshal.SizeOf<STARTUPINFO>(),
                lpDesktop = @"winsta0\default", // 대화형 데스크톱이어야 창이 보인다
                wShowWindow = (short)(showWindow ? 1 : 0),
                dwFlags = 0x00000001 // STARTF_USESHOWWINDOW
            };

            var flags = CREATE_UNICODE_ENVIRONMENT | (showWindow ? 0 : CREATE_NO_WINDOW);

            // CreateProcessAsUserW 는 commandLine 버퍼를 수정할 수 있으므로 복사본을 넘긴다.
            var mutableCommandLine = new string(commandLine.ToCharArray());

            if (!CreateProcessAsUserW(
                    primaryToken,
                    null,
                    mutableCommandLine,
                    IntPtr.Zero,
                    IntPtr.Zero,
                    false,
                    flags,
                    environment,
                    null,
                    ref startupInfo,
                    out process))
            {
                error = $"프로세스를 시작하지 못했습니다: {LastError()}";
                return false;
            }

            return true;
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return false;
        }
        finally
        {
            if (process.hProcess != IntPtr.Zero) CloseHandle(process.hProcess);
            if (process.hThread != IntPtr.Zero) CloseHandle(process.hThread);
            if (environment != IntPtr.Zero) DestroyEnvironmentBlock(environment);
            if (primaryToken != IntPtr.Zero) CloseHandle(primaryToken);
            if (userToken != IntPtr.Zero) CloseHandle(userToken);
        }
    }

    /// <summary>활성 세션에 로그온한 사용자 이름(DOMAIN\user)을 얻는다.</summary>
    internal static string? GetActiveSessionUser()
    {
        var sessionId = FindActiveSessionId();
        if (sessionId is null) return null;

        var token = IntPtr.Zero;
        try
        {
            if (!WTSQueryUserToken(sessionId.Value, out token)) return null;

            using var identity = new System.Security.Principal.WindowsIdentity(token);
            return identity.Name;
        }
        catch
        {
            return null;
        }
        finally
        {
            if (token != IntPtr.Zero) CloseHandle(token);
        }
    }

    private static string LastError() => new Win32Exception(Marshal.GetLastWin32Error()).Message;
}
