using Hanil.TimeGuard.Server.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Pages;

public sealed class EventsModel : PageModel
{
    private const int PageSize = 200;

    private readonly GuardDbContext _db;

    public EventsModel(GuardDbContext db) => _db = db;

    public sealed record EventRow(DateTimeOffset At, string DeviceName, string Category, string Message);
    public sealed record DeviceOption(string Id, string Name);

    [BindProperty(SupportsGet = true)]
    public string? DeviceId { get; set; }

    [BindProperty(SupportsGet = true)]
    public string? Category { get; set; }

    public List<EventRow> Events { get; private set; } = new();
    public List<DeviceOption> DeviceOptions { get; private set; } = new();
    public List<string> CategoryOptions { get; private set; } = new();
    public int PendingRequestCount { get; private set; }

    public async Task OnGetAsync(CancellationToken cancellationToken)
    {
        DeviceOptions = await _db.Devices
            .OrderBy(d => d.DisplayName)
            .Select(d => new DeviceOption(d.Id, d.DisplayName == "" ? d.MachineName : d.DisplayName))
            .ToListAsync(cancellationToken);

        CategoryOptions = await _db.DeviceEvents
            .Select(e => e.Category)
            .Distinct()
            .OrderBy(c => c)
            .ToListAsync(cancellationToken);

        var query = _db.DeviceEvents.Include(e => e.Device).AsQueryable();

        if (!string.IsNullOrWhiteSpace(DeviceId))
            query = query.Where(e => e.DeviceId == DeviceId);

        if (!string.IsNullOrWhiteSpace(Category))
            query = query.Where(e => e.Category == Category);

        var rows = await query
            .OrderByDescending(e => e.At)
            .Take(PageSize)
            .ToListAsync(cancellationToken);

        Events = rows.Select(e => new EventRow(
            e.At,
            e.Device is null
                ? "(삭제됨)"
                : string.IsNullOrWhiteSpace(e.Device.DisplayName) ? e.Device.MachineName : e.Device.DisplayName,
            e.Category,
            e.Message)).ToList();

        PendingRequestCount = await _db.ExtensionRequests
            .CountAsync(r => r.Status == RequestStatus.Pending, cancellationToken);
    }
}
