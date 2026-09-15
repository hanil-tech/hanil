using System.Runtime.Versioning;
using System.Security.AccessControl;
using System.Security.Principal;

namespace Hanil.TimeGuard.SetupKit;

/// <summary>프로그램 파일을 복사하고 폴더 권한을 설정한다.</summary>
[SupportedOSPlatform("windows")]
public static class FileSetup
{
    /// <summary>복사에서 뺄 파일들. 설치 프로그램 자신과 임시 파일이다.</summary>
    private static readonly string[] SkipExtensions = { ".pdb", ".tmp" };

    /// <summary>
    /// 설치 파일을 목적지로 복사한다.
    /// 설치 프로그램 자신은 복사하지 않는다. 실행 중이라 잠겨 있고 필요하지도 않다.
    /// </summary>
    public static bool Copy(string source, string destination, string selfFileName, out string detail)
    {
        detail = string.Empty;

        try
        {
            Directory.CreateDirectory(destination);

            foreach (var file in Directory.EnumerateFiles(source, "*", SearchOption.AllDirectories))
            {
                var name = Path.GetFileName(file);

                if (string.Equals(name, selfFileName, StringComparison.OrdinalIgnoreCase)) continue;
                if (SkipExtensions.Contains(Path.GetExtension(file), StringComparer.OrdinalIgnoreCase)) continue;

                var relative = Path.GetRelativePath(source, file);
                var target = Path.Combine(destination, relative);

                var targetDirectory = Path.GetDirectoryName(target);
                if (!string.IsNullOrEmpty(targetDirectory)) Directory.CreateDirectory(targetDirectory);

                File.Copy(file, target, overwrite: true);
            }

            return true;
        }
        catch (Exception ex)
        {
            detail = ex.Message;
            return false;
        }
    }

    /// <summary>
    /// 프로그램 폴더를 보호한다.
    /// 일반 사용자는 실행만 할 수 있고, 지우거나 바꿀 수 없다.
    /// </summary>
    public static bool ProtectProgramFolder(string path, out string detail)
    {
        detail = string.Empty;

        try
        {
            var directory = new DirectoryInfo(path);
            var security = directory.GetAccessControl();

            security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);

            foreach (var sid in new[] { WellKnownSidType.LocalSystemSid, WellKnownSidType.BuiltinAdministratorsSid })
            {
                security.AddAccessRule(new FileSystemAccessRule(
                    new SecurityIdentifier(sid, null),
                    FileSystemRights.FullControl,
                    InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                    PropagationFlags.None,
                    AccessControlType.Allow));
            }

            // 일반 사용자에게는 실행과 읽기만 준다.
            //
            // 여기에 "거부" 규칙을 따로 걸면 안 된다.
            // 관리자 계정도 Users 그룹에 들어 있고 거부는 허용보다 우선하므로,
            // 관리자 권한으로 실행한 설치 프로그램조차 파일을 덮어쓰지 못하게 된다.
            // 상속을 끊고 허용 규칙만 두었으므로 이것만으로 직원은 지울 수 없다.
            security.AddAccessRule(new FileSystemAccessRule(
                new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null),
                FileSystemRights.ReadAndExecute,
                InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                PropagationFlags.None,
                AccessControlType.Allow));

            directory.SetAccessControl(security);
            return true;
        }
        catch (Exception ex)
        {
            detail = ex.Message;
            return false;
        }
    }

    /// <summary>
    /// 자료 폴더 권한을 설정한다.
    /// 설정 파일을 고쳐 제한을 푸는 것을 막기 위해 일반 사용자는 읽기만 하게 한다.
    /// </summary>
    public static bool PrepareDataFolder(string path, bool allowUsersRead, out string detail)
    {
        detail = string.Empty;

        try
        {
            Directory.CreateDirectory(path);

            var directory = new DirectoryInfo(path);
            var security = directory.GetAccessControl();

            security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);

            foreach (var sid in new[] { WellKnownSidType.LocalSystemSid, WellKnownSidType.BuiltinAdministratorsSid })
            {
                security.AddAccessRule(new FileSystemAccessRule(
                    new SecurityIdentifier(sid, null),
                    FileSystemRights.FullControl,
                    InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                    PropagationFlags.None,
                    AccessControlType.Allow));
            }

            if (allowUsersRead)
            {
                security.AddAccessRule(new FileSystemAccessRule(
                    new SecurityIdentifier(WellKnownSidType.BuiltinUsersSid, null),
                    FileSystemRights.ReadAndExecute,
                    InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
                    PropagationFlags.None,
                    AccessControlType.Allow));
            }

            directory.SetAccessControl(security);
            return true;
        }
        catch (Exception ex)
        {
            detail = ex.Message;
            return false;
        }
    }

    /// <summary>
    /// 폴더에 걸린 "거부" 규칙을 모두 풀고 상속을 되살린다.
    ///
    /// 예전 판으로 설치한 PC 에는 거부 규칙이 남아 있다.
    /// 그대로 두면 관리자 권한으로도 파일을 덮어쓰지 못해
    /// 다시 설치하거나 지우는 것이 실패한다.
    /// </summary>
    public static void Unprotect(string path)
    {
        if (!Directory.Exists(path)) return;

        try
        {
            var directory = new DirectoryInfo(path);
            var security = directory.GetAccessControl();

            foreach (FileSystemAccessRule rule in security.GetAccessRules(true, true, typeof(SecurityIdentifier)))
            {
                if (rule.AccessControlType == AccessControlType.Deny)
                    security.RemoveAccessRule(rule);
            }

            security.SetAccessRuleProtection(isProtected: false, preserveInheritance: true);
            directory.SetAccessControl(security);
        }
        catch (Exception)
        {
            // 풀지 못해도 뒤 단계를 시도해 본다.
        }
    }

    /// <summary>제거할 때 폴더 보호를 풀고 지운다.</summary>
    public static bool RemoveFolder(string path, out string detail)
    {
        detail = string.Empty;

        if (!Directory.Exists(path)) return true;

        Unprotect(path);

        try
        {
            Directory.Delete(path, recursive: true);
            return true;
        }
        catch (Exception ex)
        {
            detail = ex.Message;
            return false;
        }
    }
}
