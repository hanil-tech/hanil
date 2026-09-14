using System.Text;
using System.Text.Json;
using Hanil.TimeGuard.Core.Ipc;

namespace Hanil.TimeGuard.Core.State;

/// <summary>
/// 허용 시간이 아닌데 PC 를 켠 횟수를 센다.
///
/// 유예 시간을 매번 똑같이 주면, 껐다 켜기를 되풀이해 그 시간만큼씩 쓸 수 있다.
/// 다시 켤수록 유예를 줄여 그렇게 쓰지 못하게 한다.
/// PC 를 껐다 켜도 기억해야 하므로 파일에 남긴다.
/// </summary>
public sealed class BootAttemptTracker
{
    /// <summary>유예를 줄여 나가는 비율. 두 번째부터 절반씩 줄어든다.</summary>
    private const double ReductionFactor = 0.5;

    /// <summary>아무리 줄어도 이 시간은 준다. 작업을 저장할 최소한의 여유다.</summary>
    private static readonly TimeSpan MinimumGrace = TimeSpan.FromSeconds(15);

    /// <summary>마지막 시도로부터 이 시간이 지나면 처음부터 다시 센다.</summary>
    private static readonly TimeSpan ForgetAfter = TimeSpan.FromHours(12);

    private readonly object _gate = new();
    private readonly string _path;

    public BootAttemptTracker(string? path = null) => _path = path ?? DefaultPath;

    public static string DefaultPath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "HanilTimeGuard",
            "boot-attempts.json");

    private sealed class State
    {
        public int Count { get; set; }
        public DateTimeOffset LastAt { get; set; }
    }

    /// <summary>
    /// 이번에 줄 유예 시간을 정한다.
    /// 몇 번째 시도인지도 함께 돌려준다.
    /// </summary>
    public TimeSpan NextGrace(TimeSpan baseGrace, DateTimeOffset now, out int attempt)
    {
        lock (_gate)
        {
            var state = Load();

            // 한참 전 기록은 잊는다. 어제 있었던 일로 오늘 유예를 줄이면 안 된다.
            if (now - state.LastAt > ForgetAfter) state.Count = 0;

            state.Count++;
            state.LastAt = now;
            Save(state);

            attempt = state.Count;

            if (baseGrace <= MinimumGrace) return baseGrace;

            var reduced = baseGrace * Math.Pow(ReductionFactor, state.Count - 1);
            return reduced < MinimumGrace ? MinimumGrace : reduced;
        }
    }

    /// <summary>허용 시간이 되면 기록을 지운다.</summary>
    public void Reset()
    {
        lock (_gate)
        {
            try
            {
                if (File.Exists(_path)) File.Delete(_path);
            }
            catch (IOException)
            {
                // 지우지 못해도 시간이 지나면 잊힌다.
            }
        }
    }

    private State Load()
    {
        try
        {
            if (!File.Exists(_path)) return new State();

            var json = File.ReadAllText(_path, Encoding.UTF8);
            return JsonSerializer.Deserialize<State>(json, IpcJson.Options) ?? new State();
        }
        catch (Exception)
        {
            return new State();
        }
    }

    private void Save(State state)
    {
        try
        {
            var directory = Path.GetDirectoryName(_path);
            if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);

            File.WriteAllText(_path, JsonSerializer.Serialize(state, IpcJson.Options), new UTF8Encoding(false));
        }
        catch (Exception)
        {
            // 기록하지 못하면 다음에 처음부터 세게 된다. 동작에는 문제가 없다.
        }
    }
}
