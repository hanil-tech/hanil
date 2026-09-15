using System.Diagnostics;
using System.Runtime.Versioning;
using System.ServiceProcess;

namespace Hanil.TimeGuard.SetupKit;

/// <summary>
/// Windows 서비스를 등록하고 지운다.
///
/// sc.exe 를 쓰는 이유는, 서비스 등록에 필요한 설정(복구 동작, 접근 권한)을
/// .NET 에서 직접 다루려면 Win32 호출이 길어지는데 sc.exe 는 Windows 에 항상 있고
/// 같은 일을 한 줄로 하기 때문이다.
/// </summary>
[SupportedOSPlatform("windows")]
public static class WindowsServiceSetup
{
    private static readonly TimeSpan WaitTimeout = TimeSpan.FromSeconds(30);

    /// <summary>서비스가 이미 등록되어 있는지.</summary>
    public static bool Exists(string serviceName)
    {
        try
        {
            using var service = new ServiceController(serviceName);
            _ = service.Status;
            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }

    public static ServiceControllerStatus? GetStatus(string serviceName)
    {
        try
        {
            using var service = new ServiceController(serviceName);
            return service.Status;
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>서비스를 멈춘다. 없거나 이미 멈춰 있으면 아무 일도 하지 않는다.</summary>
    public static bool Stop(string serviceName, out string detail)
    {
        detail = string.Empty;

        try
        {
            using var service = new ServiceController(serviceName);

            if (service.Status == ServiceControllerStatus.Stopped) return true;

            if (!service.CanStop)
            {
                // 설치할 때 걸어 둔 보호 때문일 수 있다. 권한을 되돌리고 다시 시도한다.
                ResetAccessRights(serviceName);

                using var retry = new ServiceController(serviceName);
                if (!retry.CanStop)
                {
                    detail = "서비스를 멈출 수 없습니다.";
                    return false;
                }

                retry.Stop();
                retry.WaitForStatus(ServiceControllerStatus.Stopped, WaitTimeout);
                return true;
            }

            service.Stop();
            service.WaitForStatus(ServiceControllerStatus.Stopped, WaitTimeout);
            return true;
        }
        catch (InvalidOperationException)
        {
            return true; // 없는 서비스
        }
        catch (Exception ex)
        {
            detail = ex.Message;
            return false;
        }
    }

    public static bool Start(string serviceName, out string detail)
    {
        detail = string.Empty;

        try
        {
            using var service = new ServiceController(serviceName);

            if (service.Status == ServiceControllerStatus.Running) return true;

            service.Start();
            service.WaitForStatus(ServiceControllerStatus.Running, WaitTimeout);
            return true;
        }
        catch (Exception ex)
        {
            detail = ex.Message;
            return false;
        }
    }

    /// <summary>서비스를 등록하거나, 이미 있으면 실행 파일 위치를 갱신한다.</summary>
    public static bool Register(string serviceName, string displayName, string description,
        string binaryPath, out string detail)
    {
        detail = string.Empty;

        var exists = Exists(serviceName);

        var result = exists
            ? Sc($"config {serviceName} binPath= \"{binaryPath}\" start= auto")
            : Sc($"create {serviceName} binPath= \"{binaryPath}\" start= auto DisplayName= \"{displayName}\"");

        if (result.ExitCode != 0)
        {
            detail = result.Output;
            return false;
        }

        Sc($"description {serviceName} \"{description}\"");

        // 서비스가 멈추면 자동으로 다시 시작하게 한다.
        Sc($"failure {serviceName} reset= 86400 actions= restart/5000/restart/5000/restart/10000");

        // 기본값은 비정상 종료만 복구한다. 스스로 멈춘 경우에도 복구하도록 바꾼다.
        Sc($"failureflag {serviceName} 1");

        return true;
    }

    public static bool Delete(string serviceName, out string detail)
    {
        detail = string.Empty;

        if (!Exists(serviceName)) return true;

        ResetAccessRights(serviceName);
        Stop(serviceName, out _);

        var result = Sc($"delete {serviceName}");

        if (result.ExitCode != 0)
        {
            detail = result.Output;
            return false;
        }

        return true;
    }

    /// <summary>
    /// 서비스를 함부로 멈출 수 없게 접근 권한을 좁힌다.
    ///
    /// SYSTEM 은 그대로 모든 권한을 가지므로 서비스 자신과 제거 프로그램은 문제없이 동작한다.
    /// 관리자 그룹에서는 중지 권한(WP)만 뺀다.
    /// </summary>
    public static bool Protect(string serviceName, out string detail)
    {
        detail = string.Empty;

        // 노리는 것은 일반 직원이 서비스를 멈추지 못하게 하는 것이다.
        // 관리자에게서는 중지 권한(WP)만 뺀다.
        //
        // 권한 되돌리기(WD)와 설정 변경(DC), 삭제(SD)는 남겨 둔다.
        // 이게 없으면 설치 프로그램이 보호를 풀지 못해 다시 설치도, 제거도 막힌다.
        // 어차피 관리자는 소유권을 가져오면 무엇이든 할 수 있으므로 지켜지는 것도 없다.
        const string sddl =
            "D:(A;;CCLCSWRPWPDTLOCRRC;;;SY)" +       // SYSTEM: 전체
            "(A;;CCDCLCSWRPDTLOCRSDRCWDWO;;;BA)" +   // 관리자: 중지 권한만 없음
            "(A;;CCLCSWLOCRRC;;;IU)" +               // 로그인 사용자: 조회만
            "(A;;CCLCSWLOCRRC;;;SU)" +               // 서비스 계정: 조회만
            "S:(AU;FA;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;WD)";

        var result = Sc($"sdset {serviceName} {sddl}");

        if (result.ExitCode != 0)
        {
            detail = result.Output;
            return false;
        }

        return true;
    }

    /// <summary>보호를 되돌린다. 제거할 때 쓴다.</summary>
    public static void ResetAccessRights(string serviceName)
    {
        const string sddl =
            "D:(A;;CCLCSWRPWPDTLOCRRC;;;SY)" +
            "(A;;CCLCSWRPWPDTLOCRRC;;;BA)" +
            "(A;;CCLCSWLOCRRC;;;IU)" +
            "(A;;CCLCSWLOCRRC;;;SU)";

        Sc($"sdset {serviceName} {sddl}");
    }

    private static (int ExitCode, string Output) Sc(string arguments)
    {
        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = "sc.exe",
                Arguments = arguments,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            using var process = Process.Start(startInfo);
            if (process is null) return (-1, "sc.exe 를 실행하지 못했습니다.");

            var output = process.StandardOutput.ReadToEnd() + process.StandardError.ReadToEnd();
            process.WaitForExit(30000);

            return (process.ExitCode, output.Trim());
        }
        catch (Exception ex)
        {
            return (-1, ex.Message);
        }
    }
}
