<script lang="ts">
  import { LockKeyhole } from "$components/ui/icons.js";

  import Button from "$components/ui/button.svelte";
  import Dialog from "$components/ui/dialog.svelte";
  import Input from "$components/ui/input.svelte";
  import { StatusMessage } from "$components/patterns/webapp/index.js";
  import EmailCodeScreen from "../auth/EmailCodeScreen.svelte";
  import type { Translate, VoidAction } from "$lib/webapp/types.js";

  let {
    setPasswordBusy = false,
    setPasswordCode = $bindable(""),
    setPasswordConfirm = $bindable(""),
    setPasswordEmail = "",
    setPasswordIsError = false,
    setPasswordOpen = false,
    setPasswordPending = false,
    setPasswordResendCooldown = 0,
    setPasswordStatus = "",
    setPasswordValue = $bindable(""),
    closeSetPasswordDialog = () => {},
    requestSetPasswordCode = () => {},
    confirmSetPassword = () => {},
    t = (key) => key,
  }: {
    setPasswordBusy?: boolean;
    setPasswordCode?: string;
    setPasswordConfirm?: string;
    setPasswordEmail?: string;
    setPasswordIsError?: boolean;
    setPasswordOpen?: boolean;
    setPasswordPending?: boolean;
    setPasswordResendCooldown?: number;
    setPasswordStatus?: string;
    setPasswordValue?: string;
    closeSetPasswordDialog?: VoidAction;
    requestSetPasswordCode?: VoidAction;
    confirmSetPassword?: VoidAction;
    t?: Translate;
  } = $props();
</script>

<Dialog
  open={setPasswordOpen && !setPasswordPending}
  title={t("wa_password_modal_title")}
  description={t("wa_password_modal_desc")}
  closeLabel={t("wa_close")}
  onclose={closeSetPasswordDialog}
  class="payment-dialog-card webapp-set-password-dialog"
>
  <div class="payment-dialog-body">
    <Input
      bind:value={setPasswordValue}
      type="password"
      placeholder={t("wa_password_new_placeholder")}
      autocomplete="new-password"
    />
    <Input
      bind:value={setPasswordConfirm}
      type="password"
      placeholder={t("wa_password_confirm_placeholder")}
      autocomplete="new-password"
      onkeydown={(event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        requestSetPasswordCode();
      }}
    />
    <Button
      class="wide bottom-action payment-submit-button"
      onclick={requestSetPasswordCode}
      disabled={setPasswordBusy}
    >
      <LockKeyhole size={17} />
      {t("wa_password_send_code_action")}
    </Button>
    {#if setPasswordStatus}
      <StatusMessage error={setPasswordIsError}>{setPasswordStatus}</StatusMessage>
    {/if}
  </div>
</Dialog>

{#if setPasswordOpen && setPasswordPending}
  <div
    class="email-code-fullscreen webapp-set-password-code-dialog"
    role="dialog"
    aria-modal="true"
  >
    <EmailCodeScreen
      bind:code={setPasswordCode}
      email={setPasswordEmail || ""}
      busy={setPasswordBusy}
      resendCooldown={setPasswordResendCooldown}
      status={setPasswordStatus}
      isError={setPasswordIsError}
      {t}
      onBack={closeSetPasswordDialog}
      onConfirm={confirmSetPassword}
      onResend={requestSetPasswordCode}
    />
  </div>
{/if}
