namespace Hanil.TimeGuard.Core.Config;

/// <summary>
/// 널리 쓰이는 원격 제어 프로그램 목록.
///
/// Windows 원격 데스크톱을 막아도 이런 프로그램이 깔려 있으면 밖에서 들어와 쓸 수 있다.
/// 특히 서비스로 상주하는 것들은 로그아웃 상태나 로그인 화면에서도 접속을 받아 준다.
///
/// 이름을 바꿔 두면 이 목록으로는 잡히지 않는다. 그래서 이 기능은
/// "완전히 막는 것" 이 아니라 "보통의 경우를 막고, 시도를 기록에 남기는 것" 이다.
/// 확실히 막으려면 조치를 전원 차단으로 두는 편이 낫다.
/// </summary>
public static class RemoteTools
{
    /// <summary>프로그램 하나에 대한 정보.</summary>
    public sealed record Entry(string DisplayName, string[] ProcessNames, string[] ServiceNames);

    /// <summary>기본으로 막는 프로그램들.</summary>
    public static readonly Entry[] Known =
    {
        new("TeamViewer",
            new[] { "TeamViewer", "TeamViewer_Service", "TeamViewer_Desktop", "tv_w32", "tv_x64" },
            new[] { "TeamViewer" }),

        new("AnyDesk",
            new[] { "AnyDesk" },
            new[] { "AnyDesk" }),

        new("RustDesk",
            new[] { "rustdesk" },
            new[] { "RustDesk" }),

        new("Chrome 원격 데스크톱",
            new[] { "remoting_host", "remote_assistance_host" },
            new[] { "chromoting" }),

        new("UltraVNC",
            new[] { "winvnc", "uvnc_service" },
            new[] { "uvnc_service" }),

        new("TightVNC",
            new[] { "tvnserver" },
            new[] { "tvnserver" }),

        new("RealVNC",
            new[] { "vncserver", "vncserverui" },
            new[] { "vncserver" }),

        new("RemoteView",
            new[] { "rvagent", "rvagtray" },
            new[] { "RVAgent" }),

        new("LogMeIn",
            new[] { "LogMeIn", "LMIGuardianSvc" },
            new[] { "LMIGuardianSvc", "LogMeIn" }),

        new("Splashtop",
            new[] { "SRService", "SRManager", "SRFeature" },
            new[] { "SplashtopRemoteService" }),

        new("Ammyy Admin",
            new[] { "AA_v3", "AMMYY_Admin" },
            Array.Empty<string>()),

        new("Supremo",
            new[] { "Supremo", "SupremoService" },
            new[] { "SupremoService" }),

        new("NetSupport",
            new[] { "client32", "PCICTL" },
            new[] { "Client32" }),

        new("Zoho Assist",
            new[] { "ZohoMeeting", "ZA_Access" },
            Array.Empty<string>()),

        new("GoTo / GoToAssist",
            new[] { "g2mcomm", "GoToAssist" },
            Array.Empty<string>())
    };

    /// <summary>기본 목록의 프로그램 이름들. 관리자가 화면에서 보고 고칠 수 있게 쓴다.</summary>
    public static IEnumerable<string> DefaultDisplayNames => Known.Select(t => t.DisplayName);

    /// <summary>
    /// 관리자가 추가로 적어 넣은 이름을 합쳐 최종 감시 대상을 만든다.
    /// 추가 이름은 프로세스 이름으로만 다룬다.
    /// </summary>
    public static IReadOnlyList<Entry> Resolve(IEnumerable<string>? extraProcessNames)
    {
        var entries = new List<Entry>(Known);

        foreach (var raw in extraProcessNames ?? Enumerable.Empty<string>())
        {
            var name = Normalize(raw);
            if (name.Length == 0) continue;

            // 이미 기본 목록에 있으면 넣지 않는다.
            if (entries.Any(e => e.ProcessNames.Any(p =>
                    string.Equals(p, name, StringComparison.OrdinalIgnoreCase))))
                continue;

            entries.Add(new Entry(name, new[] { name }, Array.Empty<string>()));
        }

        return entries;
    }

    /// <summary>".exe" 를 떼고 공백을 정리한다. 프로세스 이름은 확장자 없이 비교한다.</summary>
    public static string Normalize(string? name)
    {
        var text = (name ?? string.Empty).Trim();

        if (text.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            text = text[..^4];

        return text;
    }
}
