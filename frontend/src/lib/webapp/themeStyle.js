/** Maps JSON theme token keys to CSS custom properties used by the Mini App shell. */

const TOKEN_TO_CSS_VAR = {
  accent: "--accent",
  bg: "--bg",
  panel: "--panel",
  panel_2: "--panel-2",
  panel_3: "--panel-3",
  border: "--border",
  border_strong: "--border-strong",
  text: "--text",
  muted: "--muted",
  dim: "--dim",
  danger: "--danger",
  danger_text: "--danger-text",
  danger_soft: "--danger-soft",
  danger_border: "--danger-border",
  success: "--success",
  success_text: "--success-text",
  success_soft: "--success-soft",
  success_border: "--success-border",
  warning: "--warning",
  warning_text: "--warning-text",
  warning_soft: "--warning-soft",
  warning_border: "--warning-border",
  info: "--info",
  info_text: "--info-text",
  info_soft: "--info-soft",
  info_border: "--info-border",
  blue: "--blue",
  radius: "--radius",
  accent_contrast: "--accent-contrast",
  surface_sheen: "--surface-sheen",
  surface_sheen_soft: "--surface-sheen-soft",
  surface_hover: "--surface-hover",
  surface_muted: "--surface-muted",
  surface_subtle: "--surface-subtle",
  surface_subtle_border: "--surface-subtle-border",
  overlay_scrim: "--overlay-scrim",
  nav_bg: "--nav-bg",
  rail_bg: "--rail-bg",
  shadow_soft: "--shadow-soft",
  shadow_strong: "--shadow-strong",
  shadow_popover: "--shadow-popover",
  inset_highlight: "--inset-highlight",
  font_sans: "--font-sans",
  font_logo: "--font-logo",
  font_mono: "--font-mono",
  home_logo_scale: "--home-logo-scale",
  home_logo_scale_desktop: "--home-logo-scale-desktop",
  home_logo_scale_mobile: "--home-logo-scale-mobile",
  admin_bg: "--admin-bg",
  admin_surface: "--admin-surface",
  admin_surface_2: "--admin-surface-2",
  admin_elev: "--admin-elev",
  admin_border: "--admin-border",
  admin_border_strong: "--admin-border-strong",
  admin_text: "--admin-text",
  admin_muted: "--admin-muted",
  admin_dim: "--admin-dim",
  admin_chart_stroke: "--admin-chart-stroke",
  admin_chart_fill: "--admin-chart-fill",
};

const LOGO_SCALE_TOKEN_KEYS = new Set([
  "home_logo_scale",
  "home_logo_scale_desktop",
  "home_logo_scale_mobile",
]);
const THEME_VARIANTS = new Set(["dark", "light"]);
const GOOGLE_FONT_LINK_ID = "webapp-theme-google-fonts";
const SYSTEM_FONT_FAMILIES = new Set([
  "-apple-system",
  "blinkmacsystemfont",
  "system-ui",
  "ui-sans-serif",
  "ui-monospace",
  "sfmono-regular",
  "segoe ui",
  "arial",
  "helvetica",
  "sans-serif",
  "serif",
  "monospace",
  "consolas",
  "menlo",
  "monaco",
  "var(--font-mono)",
]);
const GOOGLE_FONT_SINGLE_WEIGHT_FAMILIES = new Set(["press start 2p"]);

export const THEME_PREVIEW_STORAGE_KEY = "rw_webapp_theme_preview_v1";
export const THEME_PREVIEW_TTL_MS = 10 * 60 * 1000;

export function themeTokensToInlineStyle(tokens, primaryFallback = "#00fe7a", options = {}) {
  const t = tokens && typeof tokens === "object" ? tokens : {};
  const parts = [];
  const useFallbackAccent = options.fallbackAccent !== false;
  const accent = t.accent || (useFallbackAccent ? primaryFallback || "#00fe7a" : "");
  if (accent) parts.push(`--accent:${accent}`);
  for (const [key, cssVar] of Object.entries(TOKEN_TO_CSS_VAR)) {
    if (key === "accent") continue;
    const value = t[key];
    if (value === undefined || value === null || value === "") continue;
    if (LOGO_SCALE_TOKEN_KEYS.has(key)) {
      const scale = Number(value);
      if (!Number.isFinite(scale) || scale <= 0) continue;
      parts.push(`${cssVar}:${scale / 100}`);
      continue;
    }
    parts.push(`${cssVar}:${String(value)}`);
  }
  return parts.join(";");
}

export function findThemeEntry(themesCatalog, key) {
  const themes = themesCatalog?.themes || [];
  return themes.find((entry) => entry && entry.key === key) || null;
}

function normalizeThemeVariant(variant) {
  const value = String(variant || "")
    .trim()
    .toLowerCase();
  return THEME_VARIANTS.has(value) ? value : "";
}

export function resolveThemeEntryTokens(theme, variant = null) {
  const base = theme?.tokens && typeof theme.tokens === "object" ? theme.tokens : {};
  const activeVariant =
    normalizeThemeVariant(variant) ||
    normalizeThemeVariant(theme?.active_variant) ||
    normalizeThemeVariant(base.color_scheme);
  const variantTokens =
    activeVariant &&
    theme?.variants?.[activeVariant] &&
    typeof theme.variants[activeVariant] === "object"
      ? theme.variants[activeVariant]
      : {};
  return { ...base, ...variantTokens };
}

export function materializeThemeEntry(theme, variant = null) {
  if (!theme || typeof theme !== "object") return theme;
  const tokens = resolveThemeEntryTokens(theme, variant);
  const activeVariant =
    normalizeThemeVariant(variant) ||
    normalizeThemeVariant(theme.active_variant) ||
    normalizeThemeVariant(tokens.color_scheme) ||
    "";
  return {
    ...theme,
    active_variant: activeVariant || theme.active_variant,
    tokens,
  };
}

export function materializeThemesCatalog(catalog) {
  const source = catalog && typeof catalog === "object" ? catalog : {};
  return {
    ...source,
    default_theme: source.default_theme || "dark",
    themes: (source.themes || []).map((theme) => materializeThemeEntry(theme)),
  };
}

export function resolveEffectiveThemeKey(themesCatalog) {
  const themes = themesCatalog?.themes || [];
  const byKey = (k) => themes.find((entry) => entry.key === k);
  const def = themesCatalog?.default_theme || themes[0]?.key || "dark";
  return byKey(def) ? def : themes[0]?.key || "dark";
}

export function themePresetClass(tokens) {
  const preset = String(tokens?.style_preset || "")
    .trim()
    .toLowerCase();
  if (!preset || preset === "none") return "";
  if (preset === "win95" || preset === "windows95") return "theme-preset-win95";
  return "";
}

export function themeVariantClass(theme) {
  const variant = String(theme?.active_variant || theme?.tokens?.color_scheme || "")
    .trim()
    .toLowerCase();
  return variant === "light" || variant === "dark" ? `theme-variant-${variant}` : "";
}

export function themeKeyClass(key) {
  const safe = String(key || "")
    .trim()
    .toLowerCase()
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return safe ? `theme-key-${safe}` : "";
}

export function themeCssClass(cssFile) {
  const filename = String(cssFile || "")
    .replace(/\\/g, "/")
    .split("/")
    .filter(Boolean)
    .pop();
  const slug = String(filename || "")
    .replace(/\.css$/i, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug ? `theme-css-${slug}` : "";
}

export function themeRootClass(theme) {
  return [
    themeKeyClass(theme?.key),
    themeVariantClass(theme),
    themeCssClass(theme?.css_file),
    themePresetClass(theme?.tokens),
  ]
    .filter(Boolean)
    .join(" ");
}

export function themeEntryToInlineStyle(theme, primaryFallback = "#00fe7a") {
  const materialized = materializeThemeEntry(theme);
  return themeTokensToInlineStyle(materialized?.tokens, primaryFallback, {
    fallbackAccent: !materialized?.css_file,
  });
}

function stripQuotes(value) {
  return String(value || "")
    .trim()
    .replace(/^["']|["']$/g, "")
    .trim();
}

export function firstFontFamily(fontStack) {
  const first = String(fontStack || "")
    .split(",")
    .map(stripQuotes)
    .find(Boolean);
  return first || "";
}

function shouldLoadGoogleFont(family) {
  const normalized = String(family || "")
    .trim()
    .toLowerCase();
  return (
    normalized &&
    !normalized.startsWith("var(") &&
    !normalized.startsWith("ui-") &&
    !SYSTEM_FONT_FAMILIES.has(normalized)
  );
}

export function googleFontFamiliesFromTokens(tokens) {
  const families = [
    firstFontFamily(tokens?.font_sans),
    firstFontFamily(tokens?.font_logo),
    firstFontFamily(tokens?.font_mono),
  ].filter(shouldLoadGoogleFont);
  return Array.from(new Set(families));
}

export function googleFontsHrefForTheme(theme) {
  const materialized = materializeThemeEntry(theme);
  const families = googleFontFamiliesFromTokens(materialized?.tokens);
  if (!families.length) return "";
  const query = families
    .map((family) => {
      const encodedFamily = encodeURIComponent(family).replace(/%20/g, "+");
      const normalizedFamily = String(family || "")
        .trim()
        .toLowerCase();
      if (GOOGLE_FONT_SINGLE_WEIGHT_FAMILIES.has(normalizedFamily)) {
        return `family=${encodedFamily}`;
      }
      return `family=${encodedFamily}:wght@400;500;600;700;800`;
    })
    .join("&");
  return `https://fonts.googleapis.com/css2?${query}&display=swap`;
}

export function syncThemeGoogleFonts(theme) {
  if (typeof document === "undefined") return;
  const href = googleFontsHrefForTheme(theme);
  let link = document.getElementById(GOOGLE_FONT_LINK_ID);
  if (!href) {
    link?.remove();
    return;
  }
  if (!link) {
    link = document.createElement("link");
    link.id = GOOGLE_FONT_LINK_ID;
    link.rel = "stylesheet";
    document.head.appendChild(link);
  }
  if (link.getAttribute("href") !== href) {
    link.setAttribute("href", href);
  }
}

export function readThemePreviewDraft(previewKey = "") {
  if (typeof window === "undefined" || !previewKey) return null;
  try {
    const requestedKey = String(previewKey || "").trim();
    const raw = window.localStorage?.getItem(THEME_PREVIEW_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const storedKey = String(parsed.preview_key || "").trim();
    if (storedKey && requestedKey && storedKey !== requestedKey) return null;
    if (Number(parsed.expires_at || 0) < Date.now()) {
      window.localStorage?.removeItem(THEME_PREVIEW_STORAGE_KEY);
      return null;
    }
    if (!parsed.catalog || typeof parsed.catalog !== "object") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writeThemePreviewDraft(catalog, previewKey = "") {
  if (typeof window === "undefined" || !catalog) return;
  try {
    window.localStorage?.setItem(
      THEME_PREVIEW_STORAGE_KEY,
      JSON.stringify({
        preview_key: previewKey || "",
        catalog,
        expires_at: Date.now() + THEME_PREVIEW_TTL_MS,
      })
    );
  } catch {
    // Preview is best-effort; opening the persisted theme should still work.
  }
}

function encodeThemeCssPath(path) {
  return String(path || "")
    .replace(/\\/g, "/")
    .split("/")
    .filter(Boolean)
    .map(encodeURIComponent)
    .join("/");
}

function themeAssetsVersion(theme) {
  const version = Number(theme?.assets_version || 0);
  return Number.isFinite(version) && version > 0 ? String(Math.floor(version)) : "";
}

export function themeCssHref(theme) {
  const cssFile = String(theme?.css_file || "").trim();
  if (!cssFile) return "";
  if (/^(?:https?:)?\/\//i.test(cssFile) || cssFile.startsWith("data:")) return "";
  const version = themeAssetsVersion(theme);
  if (cssFile.startsWith("/")) {
    if (!version) return cssFile;
    return `${cssFile}${cssFile.includes("?") ? "&" : "?"}v=${encodeURIComponent(version)}`;
  }
  const normalizedCssFile = cssFile.replace(/\\/g, "/").split("/").filter(Boolean).join("/");
  const key = String(theme?.key || "")
    .trim()
    .replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const themedPath =
    key && normalizedCssFile.split("/")[0] !== key
      ? `${key}/${normalizedCssFile}`
      : normalizedCssFile;
  const encoded = encodeThemeCssPath(themedPath);
  if (!encoded) return "";
  const href = `/webapp-theme-css/${encoded}`;
  return version ? `${href}?v=${encodeURIComponent(version)}` : href;
}

export function localizedThemeName(theme, lang = "en") {
  const names = theme?.names || {};
  const key = String(lang || "")
    .trim()
    .toLowerCase();
  const base = key.split("-")[0];
  return names[key] || names[base] || names.en || theme?.key || "";
}
