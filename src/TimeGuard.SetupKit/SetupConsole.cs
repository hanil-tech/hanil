using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Security.Principal;

namespace Hanil.TimeGuard.SetupKit;

/// <summary>설치 프로그램이 쓰는 Windows 관련 잡일.</summary>
[SupportedOSPlatform("windows")]
public static class SetupConsole
{
    /// <summary>관리자 권한으로 실행되고 있는지.</summary>
    public static bool IsElevated()
    {
        try
        {
            using var identity = WindowsIdentity.GetCurrent();
            var principal = new WindowsPrincipal(identity);

            return principal.IsInRole(WindowsBuiltInRole.Administrator);
        }
        catch (Exception)
        {
            return false;
        }
    }

    /// <summary>
    /// 명령 창에서 실행됐다면 그 창에 결과를 쓸 수 있게 붙는다.
    ///
    /// 설치 프로그램은 창 프로그램(WinExe)이라 자기 명령 창이 없다.
    /// 무인 설치로 부를 때는 부른 쪽 창에 진행 상황이 보이는 편이 낫다.
    /// </summary>
    public static void AttachToParentConsole()
    {
        try
        {
            if (!AttachConsole(unchecked((uint)-1))) return;

            var output = Console.OpenStandardOutput();
            var writer = new StreamWriter(output) { AutoFlush = true };

            Console.SetOut(writer);
            Console.OutputEncoding = System.Text.Encoding.UTF8;
        }
        catch (Exception)
        {
            // 붙지 못해도 설치 자체는 진행된다.
        }
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AttachConsole(uint processId);
}
