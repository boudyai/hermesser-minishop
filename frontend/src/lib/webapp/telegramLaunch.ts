type TelegramSdkLike<Tg> = {
  initData: string;
  hasLaunchParams(): boolean;
  load(timeoutMs?: number): Promise<Tg>;
  readInitDataFromLocation(): string;
};

export function createTelegramLaunch<Tg>({
  telegramSdk,
  defaultTimeoutMs,
  onLoaded,
}: {
  telegramSdk: TelegramSdkLike<Tg>;
  defaultTimeoutMs: number;
  onLoaded: (tg: Tg, initData: string) => void;
}) {
  function readInitDataFromLocation() {
    return telegramSdk.readInitDataFromLocation();
  }

  function hasLaunchParams() {
    return telegramSdk.hasLaunchParams();
  }

  function load(timeoutMs = defaultTimeoutMs) {
    return telegramSdk.load(timeoutMs).then((value) => {
      onLoaded(value, telegramSdk.initData);
      return value;
    });
  }

  return {
    hasLaunchParams,
    load,
    readInitDataFromLocation,
  };
}
