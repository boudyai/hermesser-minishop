<script lang="ts">
  import { TriangleAlert } from "$components/ui/icons.js";
  import { Tooltip } from "$components/ui/primitives.js";

  import Button from "$components/ui/button.svelte";
  import Dialog from "$components/ui/dialog.svelte";
  import Input from "$components/ui/input.svelte";
  import { StatusMessage } from "$components/patterns/webapp/index.js";
  import EmailCodeScreen from "../auth/EmailCodeScreen.svelte";
  import type { Translate, VoidAction } from "$lib/webapp/types.js";

  let {
    linkEmailBusy = false,
    linkEmailCode = $bindable(""),
    linkEmailFieldError = $bindable(""),
    linkEmailIsError = false,
    linkEmailOpen = false,
    linkEmailPending = "",
    linkEmailResendCooldown = 0,
    linkEmailStatus = "",
    linkEmailValue = $bindable(""),
    closeLinkEmailDialog = () => {},
    requestLinkEmailCode = () => {},
    verifyLinkEmailCode = () => {},
    t = (key) => key,
  }: {
    linkEmailBusy?: boolean;
    linkEmailCode?: string;
    linkEmailFieldError?: string;
    linkEmailIsError?: boolean;
    linkEmailOpen?: boolean;
    linkEmailPending?: string;
    linkEmailResendCooldown?: number;
    linkEmailStatus?: string;
    linkEmailValue?: string;
    closeLinkEmailDialog?: VoidAction;
    requestLinkEmailCode?: VoidAction;
    verifyLinkEmailCode?: VoidAction;
    t?: Translate;
  } = $props();
</script>

{#if linkEmailOpen && linkEmailPending}
  <div class="email-code-fullscreen webapp-link-email-code-dialog" role="dialog" aria-modal="true">
    <EmailCodeScreen
      bind:code={linkEmailCode}
      email={linkEmailPending}
      busy={linkEmailBusy}
      resendCooldown={linkEmailResendCooldown}
      status={linkEmailStatus}
      isError={linkEmailIsError}
      {t}
      onBack={closeLinkEmailDialog}
      onConfirm={verifyLinkEmailCode}
      onResend={requestLinkEmailCode}
    />
  </div>
{/if}

<Dialog
  open={linkEmailOpen && !linkEmailPending}
  title={t("wa_link_email_modal_title")}
  description={t("wa_link_email_modal_desc")}
  closeLabel={t("wa_close")}
  onclose={closeLinkEmailDialog}
  class="payment-dialog-card webapp-link-email-dialog"
>
  <div class="payment-dialog-body">
    <div class="field-error-wrap">
      <Tooltip.Root open={Boolean(linkEmailFieldError)}>
        <Input
          bind:value={linkEmailValue}
          type="email"
          placeholder={t("wa_email_placeholder")}
          autocomplete="email"
          class={linkEmailFieldError ? "input-error" : ""}
          oninput={() => (linkEmailFieldError = "")}
        />
        {#if linkEmailFieldError}
          <Tooltip.Trigger class="field-error-trigger" aria-label={linkEmailFieldError}>
            <span class="field-error-icon" aria-hidden="true"><TriangleAlert size={18} /></span>
          </Tooltip.Trigger>
        {/if}
        {#if linkEmailFieldError}
          <Tooltip.Portal>
            <Tooltip.Content class="field-error-tooltip">{linkEmailFieldError}</Tooltip.Content>
          </Tooltip.Portal>
        {/if}
      </Tooltip.Root>
    </div>
    <Button
      class="wide bottom-action payment-submit-button"
      onclick={requestLinkEmailCode}
      disabled={linkEmailBusy}
    >
      {t("wa_send_code_email")}
    </Button>
    {#if linkEmailStatus}
      <StatusMessage error={linkEmailIsError}>{linkEmailStatus}</StatusMessage>
    {/if}
  </div>
</Dialog>
