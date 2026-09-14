using System.Runtime.Versioning;
using System.Security.Principal;

namespace Hanil.TimeGuard.SetupKit;

/// <summary>
/// 설치 프로그램의 화면 출력.
///
/// 더블클릭으로 실행되므로, 전산 담당자가 아니어도 무슨 일이 일어나는지
/// 알 수 있게 한 줄씩 또렷하게 보여 준다.
/// </summary>
[SupportedOSPlatform("windows")]
public static class SetupConsole
{
    public static void Prepare(string title)
    {
        try
        {
            Console.OutputEncoding = System.Text.Encoding.UTF8;
            Console.InputEncoding = System.Text.Encoding.UTF8;
            Console.Title = title;
        }
        catch (Exception)
        {
            // 콘솔 설정을 바꿀 수 없는 환경에서도 그대로 진행한다.
        }
    }

    public static void Banner(string title, string subtitle)
    {
        Console.WriteLine();
        WriteColored("  ════════════════════════════════════════════════", ConsoleColor.Cyan);
        WriteColored($"    {title}", ConsoleColor.Cyan);
        Console.WriteLine($"    {subtitle}");
        WriteColored("  ════════════════════════════════════════════════", ConsoleColor.Cyan);
        Console.WriteLine();
    }

    public static void Step(string message) => WriteColored($"  ▶ {message}", ConsoleColor.Cyan);

    public static void Ok(string message) => WriteColored($"     {message}", ConsoleColor.Green);

    public static void Info(string message) => Console.WriteLine($"     {message}");

    public static void Warn(string message) => WriteColored($"  ! {message}", ConsoleColor.Yellow);

    public static void Error(string message) => WriteColored($"  ✗ {message}", ConsoleColor.Red);

    public static void Dim(string message) => WriteColored($"     {message}", ConsoleColor.DarkGray);

    public static void Blank() => Console.WriteLine();

    private static void WriteColored(string text, ConsoleColor color)
    {
        var previous = Console.ForegroundColor;
        try
        {
            Console.ForegroundColor = color;
            Console.WriteLine(text);
        }
        finally
        {
            Console.ForegroundColor = previous;
        }
    }

    /// <summary>더블클릭으로 실행했을 때 창이 바로 닫히지 않게 한다.</summary>
    public static void WaitForKey(string message = "이 창을 닫으려면 아무 키나 누르세요.")
    {
        Console.WriteLine();
        Dim(message);

        try
        {
            Console.ReadKey(intercept: true);
        }
        catch (InvalidOperationException)
        {
            // 입력을 받을 수 없는 환경(자동 설치 등)에서는 그냥 끝낸다.
        }
    }

    public static bool Confirm(string question, bool defaultYes = true)
    {
        Console.Write($"  {question} {(defaultYes ? "[Y/n]" : "[y/N]")}: ");

        var input = Console.ReadLine()?.Trim();
        if (string.IsNullOrEmpty(input)) return defaultYes;

        return input.StartsWith('y') || input.StartsWith('Y');
    }

    public static string Prompt(string label, string? defaultValue = null)
    {
        Console.Write(defaultValue is null ? $"  {label}: " : $"  {label} [{defaultValue}]: ");

        var input = Console.ReadLine();
        return string.IsNullOrWhiteSpace(input) ? defaultValue ?? string.Empty : input.Trim();
    }

    /// <summary>번호를 고르게 한다. 잘못 누르면 다시 묻는다.</summary>
    public static int Choose(params string[] options)
    {
        while (true)
        {
            Console.WriteLine();
            for (var i = 0; i < options.Length; i++)
                Console.WriteLine($"    {i + 1}. {options[i]}");

            Console.WriteLine("    0. 닫기");
            Console.WriteLine();
            Console.Write("  번호를 누르고 Enter: ");

            var input = Console.ReadLine()?.Trim();

            if (input == "0") return 0;
            if (int.TryParse(input, out var choice) && choice >= 1 && choice <= options.Length)
                return choice;

            Warn("번호를 다시 눌러 주세요.");
        }
    }

    /// <summary>관리자 권한으로 실행 중인지 확인한다.</summary>
    public static bool IsElevated()
    {
        try
        {
            using var identity = WindowsIdentity.GetCurrent();
            return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
        }
        catch (Exception)
        {
            return false;
        }
    }
}
