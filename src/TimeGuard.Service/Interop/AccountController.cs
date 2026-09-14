using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.Principal;

namespace Hanil.TimeGuard.Service.Interop;

/// <summary>
/// Windows 계정을 잠그고 푼다.
///
/// 화면 잠금(LockWorkStation)은 직원이 자기 비밀번호로 바로 풀 수 있어 제한이 되지 않는다.
/// 계정을 잠그면 로그인 자체가 되지 않으므로 직원이 풀 수 없다.
/// 허용 시간이 되면 서비스가 자동으로 풀어 준다.
/// </summary>
[SupportedOSPlatform("windows")]
internal static class AccountController
{
    /// <summary>계정이 잠긴 상태임을 나타내는 표시.</summary>
    private const int UF_ACCOUNTDISABLE = 0x0002;

    private const int NERR_Success = 0;
    private const int NERR_UserNotFound = 2221;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct USER_INFO_1
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_name;
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_password;
        public uint usri1_password_age;
        public uint usri1_priv;
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_home_dir;
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_comment;
        public uint usri1_flags;
        [MarshalAs(UnmanagedType.LPWStr)] public string usri1_script_path;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct USER_INFO_1008
    {
        public uint usri1008_flags;
    }

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern int NetUserGetInfo(string? serverName, string userName, int level, out IntPtr buffer);

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern int NetUserSetInfo(string? serverName, string userName, int level, ref USER_INFO_1008 buffer, out int parameterError);

    [DllImport("netapi32.dll")]
    private static extern int NetApiBufferFree(IntPtr buffer);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct LOCALGROUP_USERS_INFO_0
    {
        [MarshalAs(UnmanagedType.LPWStr)] public string lgrui0_name;
    }

    /// <summary>간접 소속(그룹 안의 그룹)까지 포함해 조회한다.</summary>
    private const int LG_INCLUDE_INDIRECT = 0x0001;

    private const int MAX_PREFERRED_LENGTH = -1;

    [DllImport("netapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern int NetUserGetLocalGroups(
        string? serverName, string userName, int level, int flags,
        out IntPtr buffer, int preferredMaximumLength,
        out int entriesRead, out int totalEntries);

    /// <summary>계정 이름에서 도메인 부분을 떼어 낸다.</summary>
    internal static string StripDomain(string userName)
    {
        var slash = userName.IndexOf('\\');
        return slash >= 0 ? userName[(slash + 1)..] : userName;
    }

    /// <summary>
    /// 이 계정을 잠가도 되는지 확인한다.
    /// 관리자 계정을 잠그면 아무도 손쓸 수 없게 되므로 반드시 막아야 한다.
    /// </summary>
    internal static bool CanLock(string userName, out string reason)
    {
        reason = string.Empty;

        var name = StripDomain(userName);

        if (string.IsNullOrWhiteSpace(name))
        {
            reason = "계정 이름이 비어 있습니다.";
            return false;
        }

        // 도메인 계정은 이 PC 에서 잠글 수 없다. 도메인 관리자만 할 수 있는 일이다.
        if (userName.Contains('\\') &&
            !string.Equals(userName.Split('\\')[0], Environment.MachineName, StringComparison.OrdinalIgnoreCase))
        {
            reason = "도메인 계정은 이 PC 에서 잠글 수 없습니다.";
            return false;
        }

        try
        {
            var account = new NTAccount(name);
            var sid = (SecurityIdentifier)account.Translate(typeof(SecurityIdentifier));

            // 내장 Administrator 계정은 절대 잠그지 않는다.
            if (sid.IsWellKnown(WellKnownSidType.AccountAdministratorSid))
            {
                reason = "Windows 내장 관리자 계정은 잠글 수 없습니다.";
                return false;
            }

            // 로컬 관리자 그룹에 속한 계정도 잠그지 않는다.
            // 실수로 잠그면 그 PC 를 복구할 방법이 사라진다.
            // 확인하지 못한 경우에도 잠그지 않는다. 되돌릴 수 없는 일이라 조심하는 편이 낫다.
            var isAdmin = IsLocalAdministrator(name);

            if (isAdmin != false)
            {
                reason = isAdmin == true
                    ? "관리자 권한을 가진 계정은 잠글 수 없습니다."
                    : "계정의 권한을 확인하지 못해 잠그지 않았습니다.";
                return false;
            }
        }
        catch (Exception ex)
        {
            reason = $"계정을 확인하지 못했습니다: {ex.Message}";
            return false;
        }

        return true;
    }

    /// <summary>
    /// 이 계정이 관리자 그룹에 속하는지 확인한다.
    ///
    /// 그룹 이름은 언어에 따라 다르므로("Administrators", "관리자") 이름이 아니라
    /// SID 로 비교한다.
    ///
    /// 확인하지 못하면 null 을 돌려준다.
    /// "모른다" 와 "관리자다" 를 구분해야, 잠금 판단은 안전하게 하면서도
    /// 화면에는 헛된 경고를 띄우지 않을 수 있다.
    /// </summary>
    private static bool? IsLocalAdministrator(string userName)
    {
        var buffer = IntPtr.Zero;

        try
        {
            var administrators = new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null);

            var result = NetUserGetLocalGroups(null, userName, 0, LG_INCLUDE_INDIRECT,
                out buffer, MAX_PREFERRED_LENGTH, out var entriesRead, out _);

            if (result != NERR_Success) return null; // 확인할 수 없음

            var size = Marshal.SizeOf<LOCALGROUP_USERS_INFO_0>();

            for (var i = 0; i < entriesRead; i++)
            {
                var entry = Marshal.PtrToStructure<LOCALGROUP_USERS_INFO_0>(buffer + i * size);
                if (string.IsNullOrWhiteSpace(entry.lgrui0_name)) continue;

                try
                {
                    var groupSid = (SecurityIdentifier)new NTAccount(entry.lgrui0_name)
                        .Translate(typeof(SecurityIdentifier));

                    if (groupSid == administrators) return true;
                }
                catch (Exception)
                {
                    // 이 그룹은 확인할 수 없다. 다음 그룹을 본다.
                }
            }

            return false;
        }
        catch (Exception)
        {
            return null; // 확인할 수 없음
        }
        finally
        {
            if (buffer != IntPtr.Zero) NetApiBufferFree(buffer);
        }
    }

    /// <summary>
    /// 이 계정이 PC 의 관리자 권한을 가졌는지 알려 준다.
    /// 서버에 보고해 관리자가 어느 PC 를 손봐야 하는지 알 수 있게 한다.
    /// </summary>
    internal static bool? IsAdministrator(string userName)
    {
        var name = StripDomain(userName);
        if (string.IsNullOrWhiteSpace(name)) return null;

        try
        {
            var sid = (SecurityIdentifier)new NTAccount(name).Translate(typeof(SecurityIdentifier));

            if (sid.IsWellKnown(WellKnownSidType.AccountAdministratorSid)) return true;
        }
        catch (Exception)
        {
            // 계정을 확인하지 못하면 그룹 소속만으로 판단한다.
        }

        return IsLocalAdministrator(name);
    }

    /// <summary>계정을 잠근다(로그인 불가). 이미 잠겨 있으면 아무 일도 하지 않는다.</summary>
    internal static (bool Ok, string Detail) Lock(string userName) => SetDisabled(userName, disabled: true);

    /// <summary>계정 잠금을 푼다.</summary>
    internal static (bool Ok, string Detail) Unlock(string userName) => SetDisabled(userName, disabled: false);

    private static (bool Ok, string Detail) SetDisabled(string userName, bool disabled)
    {
        var name = StripDomain(userName);
        var buffer = IntPtr.Zero;

        try
        {
            var result = NetUserGetInfo(null, name, 1, out buffer);

            if (result == NERR_UserNotFound)
                return (false, $"'{name}' 계정을 찾지 못했습니다.");

            if (result != NERR_Success)
                return (false, $"'{name}' 계정 정보를 읽지 못했습니다. 오류 {result}");

            var info = Marshal.PtrToStructure<USER_INFO_1>(buffer);
            var flags = info.usri1_flags;

            var alreadyDisabled = (flags & UF_ACCOUNTDISABLE) != 0;
            if (alreadyDisabled == disabled)
                return (true, disabled ? $"'{name}' 계정은 이미 잠겨 있습니다." : $"'{name}' 계정은 이미 풀려 있습니다.");

            var updated = new USER_INFO_1008
            {
                usri1008_flags = disabled
                    ? flags | UF_ACCOUNTDISABLE
                    : flags & ~(uint)UF_ACCOUNTDISABLE
            };

            var setResult = NetUserSetInfo(null, name, 1008, ref updated, out _);

            if (setResult != NERR_Success)
                return (false, $"'{name}' 계정 상태를 바꾸지 못했습니다. 오류 {setResult}");

            return (true, disabled ? $"'{name}' 계정을 잠갔습니다." : $"'{name}' 계정 잠금을 풀었습니다.");
        }
        catch (Exception ex)
        {
            return (false, $"계정 상태를 바꾸는 중 오류: {ex.Message}");
        }
        finally
        {
            if (buffer != IntPtr.Zero) NetApiBufferFree(buffer);
        }
    }
}
