<script lang="ts">
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";

  type AnyRecord = Record<string, any>;
  type ApiUnchecked = (
    path: string,
    options?: Parameters<typeof fetch>[1]
  ) => Promise<Record<string, unknown>>;

  let {
    apiUnchecked,
    t = (key: string, _params?: AnyRecord, fallback?: string) => fallback || key,
  }: {
    apiUnchecked?: ApiUnchecked;
    t?: (key: string, params?: AnyRecord, fallback?: string) => string;
  } = $props();

  let busy = $state(false);
  let info = $state<string | null>(null);
  let error = $state<string | null>(null);
  let fileInput: HTMLInputElement | undefined = $state(undefined);

  async function doBackup() {
    busy = true;
    error = null;
    info = null;
    try {
      const data = await apiUnchecked?.("/tenant/backup", { method: "POST" });
      if (data && data.ok === false) throw new Error(String(data.error || "backup_failed"));
      info = t("wa_backup_queued", {}, "Backup queued. The file will be sent from your bot.");
    } catch (e) {
      error = e instanceof Error ? e.message : "Backup failed";
    } finally {
      busy = false;
    }
  }

  function pickFile() {
    fileInput?.click();
  }

  async function doRestore() {
    const f = fileInput?.files?.[0];
    if (!f) return;
    if (f.size > 50_000_000) {
      error = "File too large (max 50MB)";
      return;
    }
    if (!f.name.endsWith(".zip")) {
      error = "Only .zip files accepted";
      return;
    }
    busy = true;
    error = null;
    info = null;
    try {
      const data = await apiUnchecked?.("/tenant/restore", {
        method: "POST",
        body: f,
        headers: { "Content-Type": "application/zip" },
      });
      if (data && data.ok === false) throw new Error(String(data.error || "restore_failed"));
      info = t("wa_restore_queued", {}, "Restore queued. The bot will restart shortly.");
    } catch (e) {
      error = e instanceof Error ? e.message : "Restore failed";
    } finally {
      busy = false;
      if (fileInput) fileInput.value = "";
    }
  }
</script>

<Card compact>
  <p style="margin:0 0 8px;color:var(--muted);font-size:12px;">
    {t("wa_backup_desc", {}, "Save bot settings, memory, and skills. Restore from a previously saved backup.")}
  </p>
  <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
    <Button variant="secondary" onclick={doBackup} disabled={busy}>
      {t("backup", {}, "Backup")}
    </Button>
    <Button variant="secondary" onclick={pickFile} disabled={busy}>
      {t("restore", {}, "Restore")}
    </Button>
    <input
      type="file"
      accept=".zip"
      bind:this={fileInput}
      onchange={doRestore}
      style="display:none"
    />
  </div>
  {#if info}
    <p style="margin:6px 0 0;color:var(--muted);font-size:12px;">{info}</p>
  {/if}
  {#if error}
    <p style="margin:6px 0 0;color:var(--danger);font-size:12px;">{error}</p>
  {/if}
</Card>
