<script lang="ts">
  import * as Card from "$components/ui/card/index.js";
  import type { AdminStats } from "$lib/admin/statsDerivations";

  type TranslateFn = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  type DateFormatterFn = (value: unknown) => string;

  let {
    at,
    stats,
    fmtDateShort,
  }: {
    at: TranslateFn;
    stats: AdminStats;
    fmtDateShort: DateFormatterFn;
  } = $props();
</script>

<Card.Root>
  <Card.Content class="admin-cn-card-content--flush" style="padding-top:12px;padding-bottom:12px;">
    <div class="admin-sync-strip" style="border:0;background:transparent;padding:0;">
      <span
        ><strong>{at("stats_sync_label", {}, "")}:</strong>
        {stats.panel_sync?.status ?? "—"}{#if stats.panel_sync?.last_sync_time}
          · {at("stats_sync_last", {}, "")}: {fmtDateShort(
            stats.panel_sync.last_sync_time
          )}{/if}</span
      >
      {#if stats.panel_sync && (stats.panel_sync.users_processed > 0 || stats.panel_sync.subscriptions_synced > 0)}
        <span
          >{at(
            "stats_sync_processed",
            {
              users: stats.panel_sync.users_processed,
              subs: stats.panel_sync.subscriptions_synced,
            },
            ""
          )}</span
        >
      {/if}
      {#if stats.queue}
        <span
          ><strong>{at("stats_label_queue", {}, "")}:</strong>
          {stats.queue.user_queue_size ?? 0}{at("stats_queue_users", {}, "")}, {stats.queue
            .group_queue_size ?? 0}{at("stats_queue_groups", {}, "")}</span
        >
      {/if}
    </div>
  </Card.Content>
</Card.Root>
