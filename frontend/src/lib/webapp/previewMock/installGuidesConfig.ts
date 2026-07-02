export const INSTALL_GUIDES_CONFIG = {
  version: "1",
  locales: ["ru", "en"],
  brandingSettings: {
    title: "/minishop",
    logoUrl: "https://example.com/logo.svg",
    supportUrl: "https://t.me/support",
  },
  uiConfig: {
    subscriptionInfoBlockType: "collapsed",
    installationGuidesBlockType: "cards",
  },
  baseSettings: {
    metaTitle: "Subscription",
    metaDescription: "Subscription",
    showConnectionKeys: false,
    hideGetLinkButton: false,
  },
  baseTranslations: Object.fromEntries(
    [
      "active",
      "bandwidth",
      "connectionKeysHeader",
      "copyLink",
      "expired",
      "expires",
      "expiresIn",
      "getLink",
      "inactive",
      "indefinitely",
      "installationGuideHeader",
      "linkCopied",
      "linkCopiedToClipboard",
      "name",
      "scanQrCode",
      "scanQrCodeDescription",
      "scanToImport",
      "status",
      "unknown",
    ].map((key) => [
      key,
      {
        ru: key === "installationGuideHeader" ? "Установка и настройка" : key,
        en: key === "installationGuideHeader" ? "Install and configure" : key,
      },
    ])
  ),
  svgLibrary: {
    App: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="5" y="3" width="14" height="18" rx="3"/><path d="M9 7h6M9 17h6"/></svg>',
    Copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="8" y="8" width="10" height="10" rx="2"/><path d="M6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    Desktop:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
    Download:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>',
    Phone:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/></svg>',
  },
  platforms: {
    ios: {
      displayName: "iOS",
      svgIconKey: "Phone",
      apps: [
        {
          name: "Streisand",
          svgIconKey: "App",
          featured: true,
          blocks: [
            {
              svgIconKey: "Download",
              svgIconColor: "green",
              title: { ru: "Установите приложение", en: "Install the app" },
              description: {
                ru: "Откройте App Store и установите клиент.",
                en: "Open the App Store and install the client.",
              },
              buttons: [
                {
                  type: "external",
                  link: "https://apps.apple.com/app/streisand/id6450534064",
                  text: { ru: "Открыть App Store", en: "Open App Store" },
                  svgIconKey: "Download",
                },
                {
                  type: "subscriptionLink",
                  link: "streisand://import/{{SUBSCRIPTION_LINK}}",
                  text: { ru: "Импортировать", en: "Import" },
                  svgIconKey: "App",
                },
                {
                  type: "copyButton",
                  link: "{{SUBSCRIPTION_LINK}}",
                  text: { ru: "Скопировать ссылку", en: "Copy link" },
                  svgIconKey: "Copy",
                },
              ],
            },
          ],
        },
      ],
    },
    android: {
      displayName: "Android",
      svgIconKey: "Phone",
      apps: [
        {
          name: "Happ",
          svgIconKey: "App",
          featured: true,
          blocks: [
            {
              svgIconKey: "Download",
              svgIconColor: "emerald",
              title: { ru: "Установите Happ", en: "Install Happ" },
              description: {
                ru: "Загрузите приложение и добавьте подписку по ссылке.",
                en: "Install the app and add the subscription link.",
              },
              buttons: [
                {
                  type: "external",
                  link: "https://play.google.com/store/apps/details?id=com.happproxy",
                  text: { ru: "Открыть Google Play", en: "Open Google Play" },
                  svgIconKey: "Download",
                },
                {
                  type: "copyButton",
                  link: "{{SUBSCRIPTION_LINK}}",
                  text: { ru: "Скопировать ссылку", en: "Copy link" },
                  svgIconKey: "Copy",
                },
              ],
            },
          ],
        },
      ],
    },
    windows: {
      displayName: "Windows",
      svgIconKey: "Desktop",
      apps: [
        {
          name: "Hiddify",
          svgIconKey: "Desktop",
          featured: true,
          blocks: [
            {
              svgIconKey: "Download",
              svgIconColor: "sky",
              title: { ru: "Установите клиент", en: "Install the client" },
              description: {
                ru: "Скачайте приложение и импортируйте ссылку подписки.",
                en: "Download the client and import the subscription link.",
              },
              buttons: [
                {
                  type: "external",
                  link: "https://github.com/hiddify/hiddify-app/releases",
                  text: { ru: "Открыть релизы", en: "Open releases" },
                  svgIconKey: "Download",
                },
                {
                  type: "copyButton",
                  link: "{{SUBSCRIPTION_LINK}}",
                  text: { ru: "Скопировать ссылку", en: "Copy link" },
                  svgIconKey: "Copy",
                },
              ],
            },
          ],
        },
      ],
    },
  },
};
