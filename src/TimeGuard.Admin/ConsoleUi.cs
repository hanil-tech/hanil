namespace Hanil.TimeGuard.Admin;

/// <summary>콘솔 입출력 도우미. 색과 입력 검증을 한곳에 모았다.</summary>
internal static class ConsoleUi
{
    internal static void Title(string text)
    {
        Console.WriteLine();
        WriteColored(text, ConsoleColor.Cyan);
        Console.WriteLine(new string('─', DisplayWidth(text)));
    }

    internal static void Info(string text) => Console.WriteLine(text);

    internal static void Success(string text) => WriteColored("✓ " + text, ConsoleColor.Green);

    internal static void Error(string text) => WriteColored("✗ " + text, ConsoleColor.Red);

    internal static void Warn(string text) => WriteColored("! " + text, ConsoleColor.Yellow);

    internal static void Dim(string text) => WriteColored(text, ConsoleColor.DarkGray);

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

    /// <summary>한글은 콘솔에서 두 칸을 차지하므로 구분선 길이를 맞춰 준다.</summary>
    private static int DisplayWidth(string text) =>
        text.Sum(c => c >= 0x1100 && c <= 0xFFDC ? 2 : 1);

    internal static string Prompt(string label, string? defaultValue = null)
    {
        Console.Write(defaultValue is null ? $"{label}: " : $"{label} [{defaultValue}]: ");
        var input = Console.ReadLine();

        return string.IsNullOrWhiteSpace(input) ? defaultValue ?? string.Empty : input.Trim();
    }

    internal static bool Confirm(string question, bool defaultYes = false)
    {
        var hint = defaultYes ? "[Y/n]" : "[y/N]";
        Console.Write($"{question} {hint}: ");

        var input = Console.ReadLine()?.Trim();
        if (string.IsNullOrEmpty(input)) return defaultYes;

        return input.StartsWith('y') || input.StartsWith('Y') || input == "ㅛ";
    }

    internal static int? PromptInt(string label, int? defaultValue = null, int min = int.MinValue, int max = int.MaxValue)
    {
        while (true)
        {
            var raw = Prompt(label, defaultValue?.ToString());
            if (string.IsNullOrWhiteSpace(raw)) return defaultValue;

            if (!int.TryParse(raw, out var value))
            {
                Error("숫자를 입력해 주세요.");
                continue;
            }

            if (value < min || value > max)
            {
                Error($"{min} 이상 {max} 이하로 입력해 주세요.");
                continue;
            }

            return value;
        }
    }

    /// <summary>입력한 글자가 화면에 보이지 않게 비밀번호를 받는다.</summary>
    internal static string PromptPassword(string label)
    {
        Console.Write($"{label}: ");

        var builder = new System.Text.StringBuilder();

        while (true)
        {
            ConsoleKeyInfo key;
            try
            {
                key = Console.ReadKey(intercept: true);
            }
            catch (InvalidOperationException)
            {
                // 콘솔이 리다이렉트된 환경에서는 그냥 한 줄 읽는다.
                Console.WriteLine();
                return Console.ReadLine() ?? string.Empty;
            }

            if (key.Key == ConsoleKey.Enter)
            {
                Console.WriteLine();
                return builder.ToString();
            }

            if (key.Key == ConsoleKey.Backspace)
            {
                if (builder.Length > 0)
                {
                    builder.Length--;
                    Console.Write("\b \b");
                }
                continue;
            }

            if (key.Key == ConsoleKey.Escape)
            {
                Console.WriteLine();
                return string.Empty;
            }

            if (char.IsControl(key.KeyChar)) continue;

            builder.Append(key.KeyChar);
            Console.Write('*');
        }
    }

    internal static void Pause()
    {
        Console.WriteLine();
        Dim("계속하려면 Enter 를 누르세요.");
        Console.ReadLine();
    }
}
