using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using Microsoft.Win32;
using static Hanil.TimeGuard.Service.Interop.NativeMethods;

namespace Hanil.TimeGuard.Service.Interop;

/// <summary>
/// 허용 시간이 아닐 때 원격 데스크톱 접속을 막는다.
///
/// 계정 잠금은 그 계정의 원격 접속까지 막지만, PC 에 다른 계정이 있으면
/// 그 계정으로 원격 접속해 쓸 수 있다. 그래서 차단 중에는 원격 접속 자체를 막는다.
///
/// 허용 시간이 되면 원래대로 되돌린다.
/// 서비스가 멈춘 채로 남아 원격 접속이 영영 막히는 일이 없도록,
/// 서비스가 시작될 때도 상태를 확인해 맞춰 준다.
/// </summary>
[SupportedOSPlatform("windows")]
internal static class RemoteAccessController
{
    private const string TerminalServerKey = @"SYSTEM\CurrentControlSet\Control\Terminal Server";
    private const string DenyValueName = "fDenyTSConnections";

    /// <summary>원래 설정을 기억해 두는 곳. 우리가 바꾸기 전 값을 여기에 남긴다.</summary>
    private const string BackupKey = @"SOFTWARE\HanilTimeGuard";
    private const string BackupValueName = "RemoteAccessOriginal";

    /// <summary>원격 접속을 막는다.</summary>
    internal static (bool Ok, string Detail) Block()
    {
        try
        {
            var current = ReadDenyConnections();

            // 이미 막혀 있다면 손대지 않는다. 원래 막아 둔 PC 를 우리가 열어 주면 안 된다.
            if (current == 1) return (true, "원격 접속은 이미 막혀 있습니다.");

            RememberOriginal(current);

            if (!WriteDenyConnections(1))
                return (false, "원격 접속 설정을 바꾸지 못했습니다.");

            var disconnected = DisconnectRemoteSessions();

            return (true, disconnected > 0
                ? $"원격 접속을 막고 접속 중이던 원격 세션 {disconnected}개를 끊었습니다."
                : "원격 접속을 막았습니다.");
        }
        catch (Exception ex)
        {
            return (false, $"원격 접속을 막는 중 오류: {ex.Message}");
        }
    }

    /// <summary>원격 접속 차단을 푼다. 우리가 막은 경우에만 되돌린다.</summary>
    internal static (bool Ok, string Detail) Unblock()
    {
        try
        {
            var original = ReadRememberedOriginal();

            // 우리가 막은 적이 없으면 아무것도 하지 않는다.
            if (original is null) return (true, string.Empty);

            if (!WriteDenyConnections(original.Value))
                return (false, "원격 접속 설정을 되돌리지 못했습니다.");

            ForgetOriginal();

            return (true, original.Value == 0
                ? "원격 접속 차단을 풀었습니다."
                : "원격 접속 설정을 원래대로 되돌렸습니다.");
        }
        catch (Exception ex)
        {
            return (false, $"원격 접속 설정을 되돌리는 중 오류: {ex.Message}");
        }
    }

    /// <summary>우리가 원격 접속을 막아 둔 상태인지.</summary>
    internal static bool IsBlockedByUs() => ReadRememberedOriginal() is not null;

    // ---- 레지스트리 ----

    private static int ReadDenyConnections()
    {
        using var key = Registry.LocalMachine.OpenSubKey(TerminalServerKey);
        var value = key?.GetValue(DenyValueName);

        return value is int number ? number : 1; // 값이 없으면 막혀 있는 것으로 본다
    }

    private static bool WriteDenyConnections(int value)
    {
        using var key = Registry.LocalMachine.OpenSubKey(TerminalServerKey, writable: true);
        if (key is null) return false;

        key.SetValue(DenyValueName, value, RegistryValueKind.DWord);
        return true;
    }

    private static void RememberOriginal(int value)
    {
        using var key = Registry.LocalMachine.CreateSubKey(BackupKey);
        key?.SetValue(BackupValueName, value, RegistryValueKind.DWord);
    }

    private static int? ReadRememberedOriginal()
    {
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(BackupKey);
            return key?.GetValue(BackupValueName) is int number ? number : null;
        }
        catch (Exception)
        {
            return null;
        }
    }

    private static void ForgetOriginal()
    {
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(BackupKey, writable: true);
            key?.DeleteValue(BackupValueName, throwOnMissingValue: false);
        }
        catch (Exception)
        {
            // 지우지 못해도 다음에 다시 시도한다.
        }
    }

    // ---- 원격 세션 끊기 ----

    /// <summary>
    /// 지금 접속해 있는 원격 세션을 모두 끊는다.
    /// 설정만 바꾸면 이미 들어와 있는 사람은 그대로 쓸 수 있으므로 함께 끊어야 한다.
    /// </summary>
    private static int DisconnectRemoteSessions()
    {
        var buffer = IntPtr.Zero;
        var count = 0;

        try
        {
            if (!WTSEnumerateSessionsW(WTS_CURRENT_SERVER_HANDLE, 0, 1, out buffer, out var sessionCount))
                return 0;

            var size = Marshal.SizeOf<WTS_SESSION_INFO>();
            var console = WTSGetActiveConsoleSessionId();

            for (var i = 0; i < sessionCount; i++)
            {
                var session = Marshal.PtrToStructure<WTS_SESSION_INFO>(buffer + i * size);

                if (session.SessionId == 0) continue;            // 서비스 세션
                if (session.SessionId == console) continue;      // 이 PC 앞에 앉은 사람의 세션

                if (session.State != WTS_CONNECTSTATE_CLASS.WTSActive &&
                    session.State != WTS_CONNECTSTATE_CLASS.WTSConnected)
                    continue;

                // 원격 세션은 이름이 RDP-Tcp#0 처럼 붙는다.
                var name = session.WinStationName ?? string.Empty;
                if (!name.StartsWith("RDP", StringComparison.OrdinalIgnoreCase)) continue;

                if (WTSLogoffSession(WTS_CURRENT_SERVER_HANDLE, session.SessionId, wait: false))
                    count++;
            }

            return count;
        }
        catch (Exception)
        {
            return count;
        }
        finally
        {
            if (buffer != IntPtr.Zero) WTSFreeMemory(buffer);
        }
    }
}
