import { mount } from "svelte";

import App from "./App.svelte";
import PreviewBoard from "./PreviewBoard.svelte";
import { mockApi } from "./lib/webapp/mockApi.js";
import { DEV_MOCK, applyPreviewMock } from "./lib/webapp/previewMock.js";
import "./styles.css";

const RUNTIME_BASE = "/demo/runtime";
const DEFAULT_FAVICON_DIGEST = "19b2a242e5b7bc2d";

function runtimePath(path) {
  return `${RUNTIME_BASE}/${String(path || "").replace(/^\/+/, "")}`;
}

function copyThemeAssets(catalog) {
  const themes = catalog?.themes || [];
  for (const theme of themes) {
    const cssFile = String(theme?.css_file || "").trim();
    if (!theme?.key || !cssFile || cssFile.startsWith("/") || /^(?:https?:)?\/\//i.test(cssFile)) {
      continue;
    }
    theme.css_file = runtimePath(`themes/${theme.key}/${cssFile}`);
  }
}

function prepareMockConfig() {
  const logoUrl = runtimePath("default-brand/default-logo.webp");
  const faviconUrl = runtimePath(`default-brand/favicons/${DEFAULT_FAVICON_DIGEST}/icon-180.png`);
  DEV_MOCK.config.logoUrl = logoUrl;
  DEV_MOCK.config.faviconUrl = faviconUrl;
  DEV_MOCK.config.adminJsAsset = runtimePath("subscription_webapp_admin.js");
  DEV_MOCK.config.adminCssAsset = runtimePath("subscription_webapp_admin.css");
  DEV_MOCK.config.apiBase = "/api";
  copyThemeAssets(DEV_MOCK.config.themesCatalog);
  copyThemeAssets(DEV_MOCK.data.themes_catalog);
}

const params = new URLSearchParams(window.location.search);
applyPreviewMock(params.get("mock"));
prepareMockConfig();

const target = document.getElementById("app");
if (target) {
  target.replaceChildren();
  mount(App, {
    target,
    props: {
      mockRuntime: {
        source: DEV_MOCK,
        applyPreviewMock: () => {},
        mockApi,
        PreviewBoard,
        docsDemo: true,
      },
    },
  });
}
