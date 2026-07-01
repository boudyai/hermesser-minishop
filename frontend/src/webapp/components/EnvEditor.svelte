<script lang="ts">
  import { onMount } from "svelte";
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import { FileText, Save } from "$components/ui/icons.js";

  type Translate = (key: string, params?: Record<string, unknown>, fallback?: string) => string;

  type Props = {
    t?: Translate;
  };

  let { t = (key) => key }: Props = $props();

  let envContent = $state("");
  let originalContent = $state("");
  let loading = $state(true);
  let saving = $state(false);
  let error = $state("");
  let saved = $state(false);

  onMount(async () => {
    try {
      const resp = await fetch("/api/env");
      if (resp.ok) {
        const data = await resp.json();
        envContent = data.env_content || "";
        originalContent = envContent;
      }
    } catch {
      error = "Failed to load configuration";
    } finally {
      loading = false;
    }
  });

  async function save() {
    saving = true;
    error = "";
    saved = false;
    try {
      const resp = await fetch("/api/env", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ env_content: envContent }),
      });
      if (resp.ok) {
        originalContent = envContent;
        saved = true;
        setTimeout(() => (saved = false), 3000);
      } else {
        error = "Failed to save";
      }
    } catch {
      error = "Network error";
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
        placeholder="# Add your environment variables here&#10;BROWSERBASE_API_KEY=...&#10;CAMOFOX_URL=http://..."
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
