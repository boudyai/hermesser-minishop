<script>
  import { CircleX, Plus, RefreshCw, Smartphone } from "lucide-svelte";

  import Button from "../../lib/components/ui/button.svelte";
  import Card from "../../lib/components/ui/card.svelte";
  import { devicesCountLabel, devicesLimitLabel, devicesPercent } from "../../lib/webapp/devicesLabels.js";

  export let devicesBusy = false;
  export let devicesData = {};
  export let devicesIsError = false;
  export let devicesLoaded = false;
  export let devicesStatus = "";
  export let subscription = {};

  export let loadDevices = () => {};
  export let openDeviceDisconnectDialog = () => {};
  export let openDeviceTopupModal = () => {};
  export let t = (key) => key;

</script>

<main class="content with-nav">
  <Card class="devices-summary-card">
    <div class="devices-summary-head">
      <Smartphone size={28} />
      <span>
        <strong>{t("wa_devices_title")}</strong>
        <small>{devicesCountLabel(devicesData, t)}</small>
      </span>
      <Button variant="icon" size="icon" onclick={() => loadDevices(true)} disabled={devicesBusy} aria-label={t("wa_devices_refresh")}>
        <RefreshCw size={18} />
      </Button>
    </div>
    <div class="progress devices-progress">
      <span style={`width: ${devicesPercent(devicesData)}%`}></span>
    </div>
    {#if subscription?.active && subscription?.max_devices !== 0}
      <Button variant="secondary" class="wide" onclick={openDeviceTopupModal}>
        <Plus size={17} />
        {t("wa_buy_hwid_devices")}
      </Button>
    {/if}
  </Card>

  {#if devicesBusy && !devicesLoaded}
    <Card class="empty-card">{t("wa_devices_loading")}</Card>
  {:else if devicesStatus}
    <Card class="empty-card">
      <p class:error={devicesIsError} class="status-line">{devicesStatus}</p>
    </Card>
  {:else if !devicesData?.devices?.length}
    <Card class="empty-card devices-empty-card">
      <Smartphone size={28} />
      <span>{t("wa_devices_empty")}</span>
      <small>{t("wa_devices_empty_hint", { max: devicesLimitLabel(devicesData, t) })}</small>
    </Card>
  {:else}
    <div class="devices-list">
      {#each devicesData.devices as device (device.token || device.index)}
        <Card class="device-card">
          <div class="device-card-head">
            <div class="device-icon"><Smartphone size={20} /></div>
            <span>
              <strong>{device.display_name || t("wa_device_fallback_name", { index: device.index })}</strong>
              <small>{device.platform_label || t("wa_devices_platform_unknown")}</small>
            </span>
          </div>
          <div class="device-meta">
            {#if device.created_at_text}
              <div>
                <span>{t("wa_devices_connected_at")}</span>
                <strong>{device.created_at_text}</strong>
              </div>
            {/if}
            {#if device.hwid_short}
              <div>
                <span>HWID</span>
                <code>{device.hwid_short}</code>
              </div>
            {/if}
            {#if device.user_agent}
              <div class="device-user-agent">
                <span>User Agent</span>
                <small>{device.user_agent}</small>
              </div>
            {/if}
          </div>
          {#if device.can_disconnect}
            <Button variant="outline" class="wide device-disconnect-button" onclick={() => openDeviceDisconnectDialog(device)}>
              <CircleX size={17} />
              {t("wa_devices_disconnect")}
            </Button>
          {/if}
        </Card>
      {/each}
    </div>
  {/if}
</main>
