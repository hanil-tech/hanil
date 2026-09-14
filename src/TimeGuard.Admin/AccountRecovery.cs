using System.Diagnostics;
using System.Text.Json;
using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Admin;

/// <summary>
/// 계정 잠금 조치를 쓰다가 문제가 생겼을 때를 위한 비상 복구.
///
/// 서비스가 제대로 돌면 허용 시간이 될 때 알아서 풀리지만,
/// 서비스가 멈췄거나 제거된 뒤에는 직원이 로그인하지 못한 채 남을 수 있다.
/// 그 상황을 관리자가 직접 되돌릴 수 있게 한다.
/// </summary>
internal static class AccountRecovery
{
    private sealed class LockedAccountRecord
    {
        public string UserName { get; set; } = string.Empty;
        public DateTimeOffset LockedAt { get; set; }
        public string Reason { get; set; } = string.Empty;
    }

    private static string RecordPath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "HanilTimeGuard",
            "locked-accounts.json");

    internal static int UnlockAll()
    {
        var path = RecordPath;

        if (!File.Exists(path))
        {
            ConsoleUi.Info("이 프로그램이 잠가 둔 계정이 없습니다.");
            return 0;
        }

        List<LockedAccountRecord>? locked;

        try
        {
            locked = JsonSerializer.Deserialize<List<LockedAccountRecord>>(
                File.ReadAllText(path), IpcJson.Options);
        }
        catch (Exception ex)
        {
            ConsoleUi.Error($"잠긴 계정 목록을 읽지 못했습니다: {ex.Message}");
            PrintManualSteps();
            return 2;
        }

        if (locked is null || locked.Count == 0)
        {
            ConsoleUi.Info("이 프로그램이 잠가 둔 계정이 없습니다.");
            return 0;
        }

        ConsoleUi.Title("잠긴 계정 풀기");

        foreach (var entry in locked)
            Console.WriteLine($"  {entry.UserName}  ({entry.LockedAt:yyyy-MM-dd HH:mm} 잠김)");

        Console.WriteLine();

        if (!ConsoleUi.Confirm("위 계정의 잠금을 모두 풀까요?", defaultYes: true))
        {
            ConsoleUi.Info("취소했습니다.");
            return 0;
        }

        var failed = 0;

        foreach (var entry in locked)
        {
            if (string.IsNullOrWhiteSpace(entry.UserName)) continue;

            if (Reactivate(entry.UserName, out var error))
            {
                ConsoleUi.Success($"'{entry.UserName}' 계정을 풀었습니다.");
            }
            else
            {
                ConsoleUi.Error($"'{entry.UserName}' 계정을 풀지 못했습니다. {error}");
                failed++;
            }
        }

        if (failed == 0)
        {
            try
            {
                File.Delete(path);
            }
            catch (IOException)
            {
                // 목록 파일을 지우지 못해도 계정은 이미 풀렸다.
            }

            Console.WriteLine();
            ConsoleUi.Success("모두 풀었습니다.");
        }
        else
        {
            Console.WriteLine();
            PrintManualSteps();
        }

        return failed == 0 ? 0 : 2;
    }

    /// <summary>Windows 계정을 다시 쓸 수 있게 한다. 관리자 권한이 필요하다.</summary>
    private static bool Reactivate(string userName, out string error)
    {
        error = string.Empty;

        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = "net",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            startInfo.ArgumentList.Add("user");
            startInfo.ArgumentList.Add(userName);
            startInfo.ArgumentList.Add("/active:yes");

            using var process = Process.Start(startInfo);

            if (process is null)
            {
                error = "명령을 실행하지 못했습니다.";
                return false;
            }

            var output = process.StandardError.ReadToEnd().Trim();
            process.WaitForExit(15000);

            if (process.ExitCode == 0) return true;

            error = string.IsNullOrWhiteSpace(output)
                ? "관리자 권한으로 실행했는지 확인해 주세요."
                : output;

            return false;
        }
        catch (Exception ex)
        {
            error = ex.Message;
            return false;
        }
    }

    private static void PrintManualSteps()
    {
        ConsoleUi.Dim("  직접 푸는 방법 — 관리자 권한 명령 프롬프트에서 계정 이름을 넣어 실행합니다:");
        ConsoleUi.Dim("    net user 계정이름 /active:yes");
        ConsoleUi.Dim("  관리자 계정으로도 로그인할 수 없다면 안전 모드로 부팅해 같은 명령을 실행하십시오.");
    }
}
