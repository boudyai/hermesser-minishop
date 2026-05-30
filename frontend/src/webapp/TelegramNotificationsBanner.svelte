<script>
  import { Send } from "$components/ui/icons.js";
  import Button from "$components/ui/button.svelte";
  import Card from "$components/ui/card.svelte";
  import { AttentionDot } from "$components/ui/index.js";

  export let startLink = "";
  export let status = "unknown";
  export let onOpenBot = () => {};
  export let t = (key) => key;

  $: isBlocked = status === "blocked";
  $: title = isBlocked
    ? t("wa_telegram_notifications_blocked_title")
    : t("wa_telegram_notifications_banner_title");
  $: description = isBlocked
    ? t("wa_telegram_notifications_blocked_text")
    : t("wa_telegram_notifications_banner_text");
</script>

<Card class="telegram-notifications-card attention-wrap">
  <AttentionDot class="telegram-notifications-dot" />
  <div class="telegram-notifications-icon">
    <Send size={20} />
  </div>
  <div class="telegram-notifications-copy">
    <strong>{title}</strong>
    <small>{description}</small>
  </div>
  <div class="telegram-notifications-actions">
    <Button
      variant="telegram"
      size="sm"
      class="telegram-notifications-primary"
      onclick={onOpenBot}
      data-start-link={startLink}
    >
      <Send size={15} />
      {t("wa_telegram_notifications_open_bot")}
    </Button>
  </div>
</Card>
