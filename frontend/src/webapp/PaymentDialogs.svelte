<script lang="ts">
  import DeviceDisconnectDialog from "./payment-dialogs/DeviceDisconnectDialog.svelte";
  import LinkEmailDialog from "./payment-dialogs/LinkEmailDialog.svelte";
  import PaymentCheckoutDialog from "./payment-dialogs/PaymentCheckoutDialog.svelte";
  import SetPasswordDialog from "./payment-dialogs/SetPasswordDialog.svelte";
  import type {
    DeviceView,
    PaymentMethodView,
    PlanView,
    SubscriptionView,
    TariffView,
    TermUnitLabel,
    Translate,
    VoidAction,
  } from "$lib/webapp/types.js";

  type DeviceToDisconnect = DeviceView & {
    display_name?: string | null;
    index?: number | string | null;
  };

  let {
    createPayment = () => {},
    deviceConfirmOpen = false,
    deviceDisconnectBusy = false,
    deviceToDisconnect = null,
    disconnectDevice = () => {},
    linkEmailBusy = false,
    linkEmailCode = $bindable(""),
    linkEmailFieldError = $bindable(""),
    linkEmailIsError = false,
    linkEmailOpen = false,
    linkEmailPending = "",
    linkEmailResendCooldown = 0,
    linkEmailStatus = "",
    linkEmailValue = $bindable(""),
    hasMultipleTariffs = false,
    methods = [],
    payBusy = false,
    paymentModalOpen = $bindable(false),
    paymentStep = $bindable("tariff"),
    plans = [],
    selectedMethod = $bindable(""),
    selectedPlan = $bindable(null),
    selectedTariff = null,
    selectedTariffKey = $bindable(""),
    selectedTariffPlans = [],
    renewHwidDevices = $bindable(true),
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
    singleTariffMode = false,
    subscription = {},
    subscriptionPurchaseDescription = "",
    tariffCatalog = [],
    tariffMode = false,
    trafficMode = false,
    closeDeviceDisconnectDialog = () => {},
    closeLinkEmailDialog = () => {},
    closePaymentModal = () => {},
    closeSetPasswordDialog = () => {},
    checkoutPromoAppliedCode = "",
    checkoutPromoInput = $bindable(""),
    checkoutPromoIsError = false,
    checkoutPromoPriceText = "",
    checkoutPromoStatus = "",
    checkoutPromoDiscountPercent = 0,
    checkoutPromoAppliesTo = "all",
    checkoutPromoMinSubscriptionMonths = null,
    checkoutPromoMinTrafficGb = null,
    applyCheckoutPromo = () => {},
    backToTariffList = () => {},
    clearCheckoutPromo = () => {},
    continueWithSelectedTariff = () => {},
    requestLinkEmailCode = () => {},
    requestSetPasswordCode = () => {},
    selectTariff = () => {},
    t = (key) => key,
    termUnitLabel = () => "",
    verifyLinkEmailCode = () => {},
    confirmSetPassword = () => {},
  }: {
    createPayment?: VoidAction;
    deviceConfirmOpen?: boolean;
    deviceDisconnectBusy?: boolean;
    deviceToDisconnect?: DeviceToDisconnect | null;
    disconnectDevice?: VoidAction;
    linkEmailBusy?: boolean;
    linkEmailCode?: string;
    linkEmailFieldError?: string;
    linkEmailIsError?: boolean;
    linkEmailOpen?: boolean;
    linkEmailPending?: string;
    linkEmailResendCooldown?: number;
    linkEmailStatus?: string;
    linkEmailValue?: string;
    hasMultipleTariffs?: boolean;
    methods?: PaymentMethodView[];
    payBusy?: boolean;
    paymentModalOpen?: boolean;
    paymentStep?: string;
    plans?: PlanView[];
    selectedMethod?: string;
    selectedPlan?: PlanView | null;
    selectedTariff?: TariffView | null;
    selectedTariffKey?: string;
    selectedTariffPlans?: PlanView[];
    renewHwidDevices?: boolean;
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
    singleTariffMode?: boolean;
    subscription?: SubscriptionView;
    subscriptionPurchaseDescription?: string;
    tariffCatalog?: TariffView[];
    tariffMode?: boolean;
    trafficMode?: boolean;
    closeDeviceDisconnectDialog?: VoidAction;
    closeLinkEmailDialog?: VoidAction;
    closePaymentModal?: VoidAction;
    closeSetPasswordDialog?: VoidAction;
    checkoutPromoAppliedCode?: string;
    checkoutPromoInput?: string;
    checkoutPromoIsError?: boolean;
    checkoutPromoPriceText?: string;
    checkoutPromoStatus?: string;
    checkoutPromoDiscountPercent?: number;
    checkoutPromoAppliesTo?: string;
    checkoutPromoMinSubscriptionMonths?: number | null;
    checkoutPromoMinTrafficGb?: number | null;
    applyCheckoutPromo?: VoidAction;
    backToTariffList?: VoidAction;
    clearCheckoutPromo?: VoidAction;
    continueWithSelectedTariff?: VoidAction;
    requestLinkEmailCode?: VoidAction;
    requestSetPasswordCode?: VoidAction;
    selectTariff?: (tariff: TariffView) => void;
    t?: Translate;
    termUnitLabel?: TermUnitLabel;
    verifyLinkEmailCode?: VoidAction;
    confirmSetPassword?: VoidAction;
  } = $props();
</script>

<PaymentCheckoutDialog
  {createPayment}
  {hasMultipleTariffs}
  {methods}
  {payBusy}
  bind:paymentModalOpen
  bind:paymentStep
  {plans}
  bind:selectedMethod
  bind:selectedPlan
  {selectedTariff}
  bind:selectedTariffKey
  {selectedTariffPlans}
  bind:renewHwidDevices
  {singleTariffMode}
  {subscription}
  {subscriptionPurchaseDescription}
  {tariffCatalog}
  {tariffMode}
  {trafficMode}
  {closePaymentModal}
  {checkoutPromoAppliedCode}
  bind:checkoutPromoInput
  {checkoutPromoIsError}
  {checkoutPromoPriceText}
  {checkoutPromoStatus}
  {checkoutPromoDiscountPercent}
  {checkoutPromoAppliesTo}
  {checkoutPromoMinSubscriptionMonths}
  {checkoutPromoMinTrafficGb}
  {applyCheckoutPromo}
  {backToTariffList}
  {clearCheckoutPromo}
  {continueWithSelectedTariff}
  {selectTariff}
  {t}
  {termUnitLabel}
/>

<DeviceDisconnectDialog
  {deviceConfirmOpen}
  {deviceDisconnectBusy}
  {deviceToDisconnect}
  {disconnectDevice}
  {closeDeviceDisconnectDialog}
  {t}
/>

<SetPasswordDialog
  {setPasswordBusy}
  bind:setPasswordCode
  bind:setPasswordConfirm
  {setPasswordEmail}
  {setPasswordIsError}
  {setPasswordOpen}
  {setPasswordPending}
  {setPasswordResendCooldown}
  {setPasswordStatus}
  bind:setPasswordValue
  {closeSetPasswordDialog}
  {requestSetPasswordCode}
  {confirmSetPassword}
  {t}
/>

<LinkEmailDialog
  {linkEmailBusy}
  bind:linkEmailCode
  bind:linkEmailFieldError
  {linkEmailIsError}
  {linkEmailOpen}
  {linkEmailPending}
  {linkEmailResendCooldown}
  {linkEmailStatus}
  bind:linkEmailValue
  {closeLinkEmailDialog}
  {requestLinkEmailCode}
  {verifyLinkEmailCode}
  {t}
/>
