using System.Diagnostics;
using System.Runtime.Versioning;
using System.ServiceProcess;
using Hanil.TimeGuard.Core.Config;

namespace Hanil.TimeGuard.Service.Interop;

/// <summary>차단 과정에서 일어난 일 하나.</summary>
/// <param name="ToolName">어떤 프로그램인지.</param>
/// <param name="Detail">사람이 읽을 설명.</param>
/// <param name="Blocked">실제로 막았는지. false 면 발견했지만 막지 못한 것이다.</param>
internal sealed record RemoteToolFinding(string ToolName, string Detail, bool Blocked);

/// <summary>
/// 허용 시간이 아닐 때 원격 제어 프로그램이 도는 것을 막는다.
///
/// Windows 원격 데스크톱을 막아도 팀뷰어 같은 프로그램이 깔려 있으면 밖에서 들어와 쓸 수 있다.
/// 이런 프로그램은 서비스로 상주하는 경우가 많아, 로그아웃 상태나 로그인 화면에서도 접속을 받는다.
///
/// 한계가 있다. 실행 파일 이름을 바꿔 두면 이 방식으로는 잡히지 않는다.
/// 그래서 막는 것뿐 아니라 **발견한 사실을 기록에 남기는 것**을 함께 한다.
/// 확실히 막으려면 조치를 전원 차단으로 두는 편이 낫다.
/// </summary>
[SupportedOSPlatform("windows")]
internal static class RemoteToolGuard
{
    /// <summary>서비스를 멈출 때 기다리는 시간.</summary>
    private static readonly TimeSpan ServiceStopTimeout = TimeSpan.FromSeconds(10);

    /// <summary>
    /// 돌고 있는 원격 제어 프로그램을 찾아 멈춘다.
    /// 무엇을 찾았고 어떻게 했는지 모두 돌려준다. 호출한 쪽에서 기록에 남긴다.
    /// </summary>
    internal static List<RemoteToolFinding> Enforce(IEnumerable<string>? extraNames)
    {
        var findings = new List<RemoteToolFinding>();
        var tools = RemoteTools.Resolve(extraNames);

        // 우리 자신은 절대 건드리지 않는다.
        var ownProcessId = Environment.ProcessId;

        foreach (var tool in tools)
        {
            StopProcesses(tool, ownProcessId, findings);
            StopServices(tool, findings);
        }

        return findings;
    }

    private static void StopProcesses(RemoteTools.Entry tool, int ownProcessId, List<RemoteToolFinding> findings)
    {
        foreach (var processName in tool.ProcessNames)
        {
            Process[] running;

            try
            {
                running = Process.GetProcessesByName(processName);
            }
            catch (Exception)
            {
                continue;
            }

            foreach (var process in running)
            {
                using (process)
                {
                    if (process.Id == ownProcessId) continue;

                    try
                    {
                        if (process.HasExited) continue;

                        process.Kill(entireProcessTree: true);
                        process.WaitForExit(5000);

                        findings.Add(new RemoteToolFinding(
                            tool.DisplayName,
                            $"{tool.DisplayName} 프로그램({processName})이 돌고 있어 종료했습니다.",
                            Blocked: true));
                    }
                    catch (Exception ex)
                    {
                        // 권한이 모자라거나 이미 끝난 경우. 발견한 사실만이라도 남긴다.
                        findings.Add(new RemoteToolFinding(
                            tool.DisplayName,
                            $"{tool.DisplayName} 프로그램({processName})을 발견했지만 종료하지 못했습니다: {ex.Message}",
                            Blocked: false));
                    }
                }
            }
        }
    }

    private static void StopServices(RemoteTools.Entry tool, List<RemoteToolFinding> findings)
    {
        foreach (var serviceName in tool.ServiceNames)
        {
            try
            {
                using var service = new ServiceController(serviceName);

                // 없는 서비스면 여기서 예외가 난다.
                var status = service.Status;

                if (status is ServiceControllerStatus.Stopped or ServiceControllerStatus.StopPending)
                    continue;

                if (!service.CanStop)
                {
                    findings.Add(new RemoteToolFinding(
                        tool.DisplayName,
                        $"{tool.DisplayName} 서비스({serviceName})를 멈출 수 없습니다.",
                        Blocked: false));
                    continue;
                }

                service.Stop();
                service.WaitForStatus(ServiceControllerStatus.Stopped, ServiceStopTimeout);

                findings.Add(new RemoteToolFinding(
                    tool.DisplayName,
                    $"{tool.DisplayName} 서비스({serviceName})가 돌고 있어 멈췄습니다.",
                    Blocked: true));
            }
            catch (InvalidOperationException)
            {
                // 이 PC 에 없는 서비스다. 정상이다.
            }
            catch (System.ServiceProcess.TimeoutException)
            {
                findings.Add(new RemoteToolFinding(
                    tool.DisplayName,
                    $"{tool.DisplayName} 서비스({serviceName})를 멈추는 데 시간이 걸리고 있습니다.",
                    Blocked: false));
            }
            catch (Exception ex)
            {
                findings.Add(new RemoteToolFinding(
                    tool.DisplayName,
                    $"{tool.DisplayName} 서비스({serviceName})를 멈추지 못했습니다: {ex.Message}",
                    Blocked: false));
            }
        }
    }

    /// <summary>
    /// 지금 이 PC 에 원격 제어 프로그램이 깔려 있는지 살펴본다.
    /// 막지는 않고 확인만 한다. 관리자가 미리 알아 두도록 설치 직후 한 번 보고한다.
    /// </summary>
    internal static List<string> FindInstalled(IEnumerable<string>? extraNames)
    {
        var found = new List<string>();

        foreach (var tool in RemoteTools.Resolve(extraNames))
        {
            var present = false;

            foreach (var processName in tool.ProcessNames)
            {
                try
                {
                    if (Process.GetProcessesByName(processName).Length > 0) present = true;
                }
                catch (Exception)
                {
                    // 확인할 수 없는 프로세스는 건너뛴다.
                }

                if (present) break;
            }

            if (!present)
            {
                foreach (var serviceName in tool.ServiceNames)
                {
                    try
                    {
                        using var service = new ServiceController(serviceName);
                        _ = service.Status;   // 없으면 예외
                        present = true;
                        break;
                    }
                    catch (Exception)
                    {
                        // 이 PC 에 없는 서비스다.
                    }
                }
            }

            if (present) found.Add(tool.DisplayName);
        }

        return found;
    }
}
