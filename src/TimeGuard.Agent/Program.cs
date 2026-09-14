using System.Runtime.Versioning;
using Hanil.TimeGuard.Agent;
using static Hanil.TimeGuard.Agent.Interop.Win32;

[assembly: SupportedOSPlatform("windows")]

// 사용자 세션에서 동작하는 알림 프로그램.
// 실제 차단은 서비스가 수행하고, 이 프로그램은 안내만 담당한다.
// 사용자가 강제로 종료하더라도 서비스가 다시 띄우며, 종료되어도 차단은 그대로 실행된다.

// 한 세션에 하나만 떠 있게 한다.
using var singleInstance = new Mutex(initiallyOwned: true, "Local\\HanilTimeGuardAgent", out var isFirstInstance);

if (!isFirstInstance)
    return 0;

try
{
    using var poller = new StatusPoller();
    poller.Start();

    using var window = new AgentWindow(poller);
    window.Run();

    return 0;
}
catch (Exception ex)
{
    // 알림 프로그램이 죽더라도 사용자가 이유를 알 수 있도록 한 번은 알려 준다.
    MessageBoxW(IntPtr.Zero,
        $"TimeGuard 알림 프로그램에서 오류가 발생했습니다.\n\n{ex.Message}",
        "한일 TimeGuard", MB_OK | MB_ICONINFORMATION);
    return 1;
}
