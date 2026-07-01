import { recordOrNull } from "./domainTypes.js";
import type { WebappMockSource, WebappRecord } from "./types";

type AuthStoreLike = {
  update(updater: (state: WebappRecord) => WebappRecord): void;
};

const DEMO_AUTH_MODES = ["auth", "login", "register"];
const DEFAULT_DEMO_EMAIL = "3252a8@proton.me";
const DEFAULT_DEMO_TELEGRAM_ID = 7410865527;
const DEFAULT_DEMO_TELEGRAM_USERNAME = "u3252a8";
const DEFAULT_DEMO_TELEGRAM_FIRST_NAME = "3252a8";

function authDemo(source: WebappMockSource): WebappRecord {
  return recordOrNull(source.data?.auth_demo) || {};
}

export function createDemoAuth({
  authStore,
  getCurrentSearchParams,
  getMockSource,
  getParentSearchParams,
  isMockEnabled,
}: {
  authStore: AuthStoreLike;
  getCurrentSearchParams: () => URLSearchParams;
  getMockSource: () => WebappMockSource;
  getParentSearchParams: () => URLSearchParams | null;
  isMockEnabled: () => boolean;
}) {
  function currentMockMode() {
    if (!isMockEnabled()) return "";
    const currentMock = getCurrentSearchParams().get("mock");
    if (currentMock) return String(currentMock).trim().toLowerCase();
    const parentMock = getParentSearchParams()?.get("mock");
    return String(parentMock || "")
      .trim()
      .toLowerCase();
  }

  function isDemoAuthMock() {
    return DEMO_AUTH_MODES.includes(currentMockMode());
  }

  function demoEmail() {
    return String(authDemo(getMockSource()).email || DEFAULT_DEMO_EMAIL).trim();
  }

  function telegramAuthPayload() {
    const demo = authDemo(getMockSource());
    return {
      id: Number(demo.telegram_id || DEFAULT_DEMO_TELEGRAM_ID),
      username: demo.telegram_username || DEFAULT_DEMO_TELEGRAM_USERNAME,
      first_name: demo.telegram_first_name || DEFAULT_DEMO_TELEGRAM_FIRST_NAME,
      last_name: demo.telegram_last_name || "",
    };
  }

  function prepareAuthState() {
    const demo = authDemo(getMockSource());
    authStore.update((state) => ({
      ...state,
      authStatus: "",
      authIsError: false,
      authBusy: false,
      authResendCooldown: 0,
      email: demoEmail(),
      emailPassword: String(demo.password || ""),
      pendingEmail: "",
      emailCode: "",
      passwordLoginMode: false,
      passwordLoginFallback: false,
      loginEmailFieldError: "",
      loginEmailTooltipOpen: false,
      telegramLoginBusy: false,
    }));
  }

  return {
    currentMockMode,
    demoEmail,
    isDemoAuthMock,
    prepareAuthState,
    telegramAuthPayload,
  };
}
