import { createTelegramLaunch } from "./telegramLaunch.js";
import { createTelegramSdk } from "./telegramSdk";
import { shellState } from "./shellState.svelte";

export type TelegramWebApp = Record<string, unknown> & {
  initData?: string;
  openInvoice?: (url: string, callback: (status: string) => void) => void;
  openLink?: (url: string, options?: Record<string, unknown>) => void;
  openTelegramLink?: (url: string) => void;
  platform?: string;
  ready?: () => void;
  expand?: () => void;
};

export type TelegramMiniAppAuthTimeout = {
  signal?: AbortSignal;
  promise: Promise<unknown>;
  clear(): void;
  timedOut: boolean;
};

type TelegramSdkLike<Tg> = {
  initData: string;
  refresh(): Tg;
  hasLaunchParams(): boolean;
  load(timeoutMs?: number): Promise<Tg>;
  readInitDataFromLocation(): string;
  ensureForAction: () => Promise<Tg>;
  createMiniAppAuthTimeout: () => TelegramMiniAppAuthTimeout;
};

type CreateTelegramSdk<Tg> = (options: {
  scriptUrl: string;
  bootTimeoutMs: number;
  actionTimeoutMs: number;
  miniAppAuthTimeoutMs: number;
  onStatusChange: (status: string) => void;
  onInitDataChange: (initData: string) => void;
}) => TelegramSdkLike<Tg>;

export type TelegramRuntime<Tg> = {
  telegramSdk: TelegramSdkLike<Tg>;
  refreshTelegram: () => Tg;
  hasLaunchParams: () => boolean;
  load: (timeoutMs?: number) => Promise<Tg>;
  readInitDataFromLocation: () => string;
};

export function createTelegramRuntime<Tg = TelegramWebApp | null>({
  actionTimeoutMs,
  bootTimeoutMs,
  createSdk = createTelegramSdk as unknown as CreateTelegramSdk<Tg>,
  miniAppAuthTimeoutMs,
  scriptUrl,
}: {
  actionTimeoutMs: number;
  bootTimeoutMs: number;
  createSdk?: CreateTelegramSdk<Tg>;
  miniAppAuthTimeoutMs: number;
  scriptUrl: string;
}): TelegramRuntime<Tg> {
  function setInitData(initData: string) {
    shellState.telegramMiniAppInitData = initData || "";
  }

  function setStatus(status: string) {
    shellState.telegramSdkStatus = status;
  }

  function setTelegram(telegram: Tg) {
    shellState.tg = telegram as TelegramWebApp | null;
  }

  const telegramSdk = createSdk({
    scriptUrl,
    bootTimeoutMs,
    actionTimeoutMs,
    miniAppAuthTimeoutMs,
    onStatusChange: setStatus,
    onInitDataChange: (initData) => setInitData(initData || ""),
  });
  const telegramLaunch = createTelegramLaunch<Tg>({
    telegramSdk,
    defaultTimeoutMs: bootTimeoutMs,
    onLoaded: (value, initData) => {
      setTelegram(value);
      setInitData(initData || "");
    },
  });

  function refreshTelegram({ initial = false }: { initial?: boolean } = {}) {
    const telegram = telegramSdk.refresh();
    setTelegram(telegram);
    if (telegram) setStatus("ready");
    else if (initial) setStatus("idle");
    setInitData(telegramSdk.initData || "");
    return telegram;
  }

  refreshTelegram({ initial: true });

  return {
    telegramSdk,
    refreshTelegram,
    hasLaunchParams: telegramLaunch.hasLaunchParams,
    load: telegramLaunch.load,
    readInitDataFromLocation: telegramLaunch.readInitDataFromLocation,
  };
}
