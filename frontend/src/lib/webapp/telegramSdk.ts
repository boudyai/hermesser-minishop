interface TelegramWebApp {
  initData?: string;
}

interface TelegramSdkOptions {
  scriptUrl?: string;
  bootTimeoutMs?: number;
  actionTimeoutMs?: number;
  miniAppAuthTimeoutMs?: number;
  onStatusChange?: (status: "loading" | "ready" | "unavailable") => void;
  onInitDataChange?: (initData: string) => void;
}

interface MiniAppAuthTimeout {
  promise: Promise<never>;
  readonly signal: AbortSignal | undefined;
  readonly timedOut: boolean;
  clear: () => void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

export function readTelegramMiniAppInitDataFromLocation() {
  if (typeof window === "undefined") return "";
  const queryText = window.location.search.replace(/^\?/, "");
  const hashText = window.location.hash.replace(/^#/, "");
  for (const text of [queryText, hashText]) {
    if (!text) continue;
    const params = new URLSearchParams(text);
    const initData = params.get("tgWebAppData");
    if (initData) return initData;
  }
  return "";
}

export function createTelegramSdk({
  scriptUrl = "",
  bootTimeoutMs = 0,
  actionTimeoutMs = 0,
  miniAppAuthTimeoutMs = 0,
  onStatusChange = () => {},
  onInitDataChange = () => {},
}: TelegramSdkOptions = {}) {
  let tg = resolve();
  let sdkPromise: Promise<TelegramWebApp | null> | null = null;
  let launchParamsDetected = false;
  let initData = tg?.initData || readTelegramMiniAppInitDataFromLocation();
  if (initData) launchParamsDetected = true;

  function resolve(): TelegramWebApp | null {
    return window.Telegram?.WebApp || null;
  }

  function setStatus(status: "loading" | "ready" | "unavailable") {
    onStatusChange(status);
  }

  function refresh() {
    tg = resolve();
    if (tg) setStatus("ready");
    initData = tg?.initData || readTelegramMiniAppInitDataFromLocation();
    onInitDataChange(initData);
    if (initData) launchParamsDetected = true;
    return tg;
  }

  function hasLaunchParams() {
    refresh();
    if (launchParamsDetected || initData) {
      launchParamsDetected = true;
      return true;
    }
    const queryText = window.location.search.replace(/^\?/, "");
    const hashText = window.location.hash.replace(/^#/, "");
    const detected = [queryText, hashText].some((text) => {
      if (!text) return false;
      const params = new URLSearchParams(text);
      return ["tgWebAppData", "tgWebAppVersion", "tgWebAppPlatform", "tgWebAppThemeParams"].some(
        (key) => params.has(key)
      );
    });
    if (detected) launchParamsDetected = true;
    return detected;
  }

  function load(timeoutMs = bootTimeoutMs): Promise<TelegramWebApp | null> {
    if (refresh()) return Promise.resolve(tg);
    if (sdkPromise) return sdkPromise;
    if (typeof document === "undefined") return Promise.resolve(null);

    setStatus("loading");
    const promise = new Promise<TelegramWebApp | null>((resolvePromise) => {
      const existingScript = document.querySelector<HTMLScriptElement>(
        "script[data-rw-telegram-web-app-sdk]"
      );
      const script = existingScript || document.createElement("script");
      let resolved = false;
      let timeoutId: number | null = null;

      const resolveOnce = (value: TelegramWebApp | null) => {
        if (resolved) return;
        resolved = true;
        if (timeoutId) window.clearTimeout(timeoutId);
        resolvePromise(value);
      };

      const refreshFromScript = () => {
        tg = resolve();
        setStatus(tg ? "ready" : "unavailable");
        return tg;
      };

      script.addEventListener("load", () => resolveOnce(refreshFromScript()), { once: true });
      script.addEventListener(
        "error",
        () => {
          setStatus("unavailable");
          resolveOnce(null);
        },
        { once: true }
      );

      if (!existingScript) {
        script.src = scriptUrl;
        script.async = true;
        script.defer = true;
        script.dataset.rwTelegramWebAppSdk = "1";
        document.head.appendChild(script);
      }

      timeoutId = window.setTimeout(() => {
        if (!tg) setStatus("unavailable");
        resolveOnce(tg);
      }, timeoutMs);
    }).finally(() => {
      sdkPromise = null;
    });
    sdkPromise = promise;
    return promise;
  }

  async function ensureForAction(): Promise<TelegramWebApp | null> {
    if (refresh()) return tg;
    return await load(actionTimeoutMs);
  }

  function createMiniAppAuthTimeout(): MiniAppAuthTimeout {
    const controller = typeof AbortController === "undefined" ? null : new AbortController();
    let timedOut = false;
    let timeoutId: number | null = null;
    let timeoutPromise: Promise<never> = new Promise(() => {});

    if (typeof window !== "undefined") {
      timeoutPromise = new Promise((_, reject) => {
        timeoutId = window.setTimeout(() => {
          timedOut = true;
          controller?.abort();
          const error = new Error("telegram_mini_app_auth_timeout");
          error.name = "AbortError";
          reject(error);
        }, miniAppAuthTimeoutMs);
      });
    }

    return {
      promise: timeoutPromise,
      get signal() {
        return controller?.signal;
      },
      get timedOut() {
        return timedOut;
      },
      clear() {
        if (timeoutId) window.clearTimeout(timeoutId);
        timeoutId = null;
      },
    };
  }

  return {
    get tg() {
      return tg;
    },
    get initData() {
      return initData;
    },
    refresh,
    hasLaunchParams,
    load,
    ensureForAction,
    createMiniAppAuthTimeout,
    readInitDataFromLocation: readTelegramMiniAppInitDataFromLocation,
  };
}
