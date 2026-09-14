using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Hanil.TimeGuard.Core.Config;

/// <summary>설정 파일 읽기/쓰기. 쓰기는 임시 파일 후 교체 방식이라 중간에 끊겨도 파일이 깨지지 않는다.</summary>
public sealed class ConfigStore
{
    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        Converters = { new JsonStringEnumConverter(), new TimeOnlyConverter() },
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    private readonly object _gate = new();

    public string Path { get; }

    public ConfigStore(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        Path = path;
    }

    /// <summary>기본 설정 경로: %ProgramData%\HanilTimeGuard\config.json</summary>
    public static string DefaultPath =>
        System.IO.Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "HanilTimeGuard",
            "config.json");

    /// <summary>
    /// 설정을 읽는다. 파일이 없거나 내용이 깨졌으면 차단하지 않는 안전한 기본값을 돌려준다.
    /// 설정을 못 읽었다고 해서 PC 를 꺼 버리는 일이 없도록 의도적으로 열린 쪽으로 실패한다.
    /// </summary>
    public GuardConfig Load(out string? loadError)
    {
        loadError = null;
        lock (_gate)
        {
            try
            {
                if (!File.Exists(Path))
                {
                    loadError = "설정 파일이 없습니다. 기본값(감시 꺼짐)으로 동작합니다.";
                    return GuardConfig.CreateInitial();
                }

                var json = File.ReadAllText(Path, Encoding.UTF8);
                var config = JsonSerializer.Deserialize<GuardConfig>(json, Options);

                if (config is null)
                {
                    loadError = "설정 파일이 비어 있습니다. 기본값(감시 꺼짐)으로 동작합니다.";
                    return GuardConfig.CreateInitial();
                }

                config.Schedule ??= WeeklySchedule.CreateDefault();
                config.Warnings ??= new WarningSettings();
                config.Holidays ??= new List<string>();
                config.ExemptUsers ??= new List<string>();
                return config;
            }
            catch (Exception ex)
            {
                loadError = $"설정 파일을 읽지 못했습니다({ex.Message}). 기본값(감시 꺼짐)으로 동작합니다.";
                return GuardConfig.CreateInitial();
            }
        }
    }

    public GuardConfig Load() => Load(out _);

    public void Save(GuardConfig config, string modifiedBy)
    {
        ArgumentNullException.ThrowIfNull(config);

        config.LastModified = DateTimeOffset.Now;
        config.LastModifiedBy = modifiedBy;

        lock (_gate)
        {
            var directory = System.IO.Path.GetDirectoryName(Path);
            if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);

            var json = JsonSerializer.Serialize(config, Options);
            var temp = Path + ".tmp";

            File.WriteAllText(temp, json, new UTF8Encoding(false));

            if (File.Exists(Path))
                File.Replace(temp, Path, null);
            else
                File.Move(temp, Path);
        }
    }
}

/// <summary>
/// TimeOnly 를 "HH:mm" 문자열로 다룬다.
/// 설정 파일과 서버 통신에서 같은 형식을 써서 사람이 읽고 고칠 수 있게 한다.
/// </summary>
public sealed class TimeOnlyConverter : JsonConverter<TimeOnly>
{
    public override TimeOnly Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        var text = reader.GetString();
        if (string.IsNullOrWhiteSpace(text)) return TimeOnly.MinValue;
        if (text is "24:00") return TimeOnly.MinValue;
        return TimeOnly.TryParseExact(text, "HH:mm", out var value) ? value : TimeOnly.Parse(text);
    }

    public override void Write(Utf8JsonWriter writer, TimeOnly value, JsonSerializerOptions options) =>
        writer.WriteStringValue(value.ToString("HH\\:mm"));
}
