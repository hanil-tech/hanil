using Microsoft.EntityFrameworkCore;

namespace Hanil.TimeGuard.Server.Data;

public sealed class GuardDbContext : DbContext
{
    public GuardDbContext(DbContextOptions<GuardDbContext> options) : base(options) { }

    public DbSet<Device> Devices => Set<Device>();
    public DbSet<DefaultPolicy> DefaultPolicies => Set<DefaultPolicy>();
    public DbSet<ExtensionRequest> ExtensionRequests => Set<ExtensionRequest>();
    public DbSet<DeviceEvent> DeviceEvents => Set<DeviceEvent>();
    public DbSet<AdminUser> AdminUsers => Set<AdminUser>();
    public DbSet<ServerSetting> Settings => Set<ServerSetting>();

    /// <summary>
    /// 모든 시각을 UTC 틱으로 저장한다.
    /// SQLite 가 DateTimeOffset 정렬을 지원하지 않기 때문이며,
    /// 정수로 저장하면 정렬과 범위 비교가 정확해진다.
    /// </summary>
    protected override void ConfigureConventions(ModelConfigurationBuilder builder)
    {
        builder.Properties<DateTimeOffset>().HaveConversion<UtcTicksConverter>();
    }

    protected override void OnModelCreating(ModelBuilder builder)
    {

        builder.Entity<Device>(entity =>
        {
            entity.HasIndex(d => d.MachineName);

            // 토큰이 아직 없는(승인 대기) PC 가 여럿일 수 있으므로 고유 조건을 걸지 않는다.
            entity.HasIndex(d => d.TokenHash);

            // 승인 대기 목록을 자주 훑는다.
            entity.HasIndex(d => d.Approval);
            entity.HasIndex(d => d.ClientIdHash);
        });

        builder.Entity<ExtensionRequest>(entity =>
        {
            entity.HasOne(r => r.Device)
                  .WithMany()
                  .HasForeignKey(r => r.DeviceId)
                  .OnDelete(DeleteBehavior.Cascade);

            // 대기 중인 요청을 자주 훑으므로 상태와 시각에 색인을 둔다.
            entity.HasIndex(r => new { r.Status, r.RequestedAt });
            entity.HasIndex(r => r.DeviceId);

            // 하트비트마다 "아직 전달하지 않은 결과" 를 찾으므로 색인을 둔다.
            entity.HasIndex(r => new { r.DeviceId, r.NotifiedAt });
        });

        builder.Entity<DeviceEvent>(entity =>
        {
            entity.HasOne(e => e.Device)
                  .WithMany()
                  .HasForeignKey(e => e.DeviceId)
                  .OnDelete(DeleteBehavior.Cascade);

            entity.HasIndex(e => new { e.DeviceId, e.At });
            entity.HasIndex(e => e.At);
        });

        builder.Entity<AdminUser>()
               .HasIndex(u => u.UserName)
               .IsUnique();
    }
}
