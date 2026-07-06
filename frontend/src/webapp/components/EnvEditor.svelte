<script lang="ts">
  import { onMount } from "svelte";
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import { FileText, Save } from "$components/ui/icons.js";

  type Translate = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  type ApiUnchecked = (
    path: string,
    options?: Parameters<typeof fetch>[1]
  ) => Promise<Record<string, unknown>>;
  const missingApi: ApiUnchecked = async () => ({ ok: false, error: "api_unavailable" });

  type Props = {
    apiUnchecked?: ApiUnchecked;
    t?: Translate;
  };

  let { apiUnchecked = missingApi, t = (key) => key }: Props = $props();

  let envContent = $state("");
  let originalContent = $state("");
  let loading = $state(true);
  let saving = $state(false);
  let error = $state("");
  let saved = $state(false);

  onMount(async () => {
    try {
      const data = await apiUnchecked("/env");
      if (data.ok !== false) {
        envContent = typeof data.env_content === "string" ? data.env_content : "";
        originalContent = envContent;
      } else {
        error =
          t("wa_settings_env_load_failed", {}, "Failed to load configuration");
      }
    } catch {
      error = t("wa_settings_env_load_failed", {}, "Failed to load configuration");
    } finally {
      loading = false;
    }
  });

  async function save() {
    saving = true;
    error = "";
    saved = false;
    try {
      const data = await apiUnchecked("/env", {
        method: "PUT",
        body: JSON.stringify({ env_content: envContent }),
      });
      if (data.ok !== false) {
        originalContent = envContent;
        saved = true;
        setTimeout(() => (saved = false), 3000);
      } else {
        error =
          t("wa_settings_env_save_failed", {}, "Failed to save") +
          (data.error ? `: ${String(data.error)}` : "");
      }
    } catch {
      error = t("wa_settings_env_network_error", {}, "Network error");
    } finally {
      saving = false;
    }
  }

  let dirty = $derived(envContent !== originalContent);
</script>

{#if !loading}
  <Card class="settings-env-editor">
    <div class="settings-row" style="padding-bottom:0">
      <FileText size={21} />
      <div>
        <strong>{t("wa_settings_env_title", {}, "Bot Configuration")}</strong>
        <small>{t("wa_settings_env_hint", {}, "Environment variables for your bot (.env)")}</small>
      </div>
    </div>

    <div style="padding:0.75rem 0">
      <textarea
        bind:value={envContent}
        spellcheck="false"
        style="width:100%;min-height:200px;font-family:monospace;font-size:0.85rem;padding:0.75rem;border-radius:8px;border:1px solid var(--border, #333);background:var(--surface, #1a1a1a);color:var(--text, #eee);resize:vertical"
        placeholder={t("wa_settings_env_placeholder", {}, "# Add your environment variables here\nBROWSERBASE_API_KEY=...\nCAMOFOX_URL=http://...")}
      ></textarea>
    </div>

    {#if error}
      <small style="color:var(--danger, #e74c3c);display:block;margin-bottom:0.5rem">{error}</small>
    {/if}
    {#if saved}
      <small style="color:var(--success, #2ecc71);display:block;margin-bottom:0.5rem">
        {t("wa_settings_env_saved", {}, "Saved — bot restarting...")}
      </small>
    {/if}

    <Button variant="primary" size="md" onclick={save} disabled={!dirty || saving}>
      <Save size={16} />
      {saving
        ? t("wa_settings_env_saving", {}, "Saving...")
        : t("wa_settings_env_save", {}, "Save & Restart")}
    </Button>
  </Card>
{/if}
