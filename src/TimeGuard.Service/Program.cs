using System.Runtime.Versioning;
using Hanil.TimeGuard.Core;
using Hanil.TimeGuard.Core.Config;
using Hanil.TimeGuard.Core.Ipc;
using Hanil.TimeGuard.Service;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Hosting.WindowsServices;
using Microsoft.Extensions.Logging;

[assembly: SupportedOSPlatform("windows")]

// 콘솔에서 직접 실행하면 서비스 없이 앞단에서 동작해 동작 확인에 쓸 수 있다.
// 서비스로 등록해 실행하면 Windows 서비스로 동작한다.

if (args.Length > 0 && args[0] is "--help" or "-h" or "/?")
{
    Console.WriteLine("""
        한일 TimeGuard 서비스

        사용법:
          TimeGuard.Service.exe            서비스로 실행(또는 콘솔에서 직접 실행해 동작 확인)
          TimeGuard.Service.exe --help     이 도움말

        설정 파일: %ProgramData%\HanilTimeGuard\config.json
        서버 설정: %ProgramData%\HanilTimeGuard\server.json
        로그 파일: %ProgramData%\HanilTimeGuard\timeguard.log

        설정 변경은 TimeGuard.Admin.exe 로 하십시오.
        관리 서버를 쓰는 경우 시간표는 서버에서만 바꿀 수 있습니다.
        """);
    return 0;
}

var builder = Host.CreateApplicationBuilder(args);

builder.Services.AddWindowsService(options => options.ServiceName = IpcNames.ServiceName);

builder.Services.AddSingleton(_ => new ConfigStore(ConfigStore.DefaultPath));
builder.Services.AddSingleton(_ => new AuditLog(AuditLog.DefaultPath));
builder.Services.AddSingleton<ServiceState>();
builder.Services.AddHostedService<GuardWorker>();
builder.Services.AddHostedService<ControlServer>();
builder.Services.AddHostedService<ServerSync>();

if (WindowsServiceHelpers.IsWindowsService())
{
    builder.Logging.AddEventLog(settings =>
    {
        settings.SourceName = IpcNames.ServiceName;
        settings.LogName = "Application";
    });
}
else
{
    builder.Logging.AddSimpleConsole(options => options.TimestampFormat = "HH:mm:ss ");
    Console.OutputEncoding = System.Text.Encoding.UTF8;
    Console.WriteLine("콘솔 모드로 실행 중입니다. Ctrl+C 로 종료합니다.");
    Console.WriteLine($"설정 파일: {ConfigStore.DefaultPath}");
}

var host = builder.Build();

// 설정 파일이 아직 없으면 차단하지 않는 안전한 기본값으로 하나 만들어 둔다.
EnsureInitialConfig(host.Services.GetRequiredService<ConfigStore>(),
                    host.Services.GetRequiredService<AuditLog>());

await host.RunAsync();
return 0;

static void EnsureInitialConfig(ConfigStore store, AuditLog log)
{
    try
    {
        if (File.Exists(store.Path)) return;

        store.Save(GuardConfig.CreateInitial(), "설치");
        log.Write("설정", "기본 설정 파일을 만들었습니다. 감시는 꺼진 상태입니다.");
    }
    catch (Exception ex)
    {
        log.Write("오류", $"기본 설정 파일을 만들지 못했습니다: {ex.Message}");
    }
}
