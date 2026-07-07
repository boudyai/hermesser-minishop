import type { PreviewTheme, PreviewThemeTokens } from "./types";

export const DEFAULT_THEME_VARIANTS: Record<string, PreviewThemeTokens> = {
  dark: {
    color_scheme: "dark",
    accent: "#00fe7a",
    accent_contrast: "#001f10",
    bg: "#03070b",
    panel: "#111820",
    panel_2: "#0b1118",
    panel_3: "#17212b",
    text: "#f2f7f4",
    muted: "#a9b4b0",
    dim: "#68736f",
    border: "rgba(255,255,255,0.08)",
    border_strong: "rgba(255,255,255,0.16)",
    surface_hover: "rgba(255,255,255,0.07)",
    surface_muted: "rgba(255,255,255,0.04)",
    nav_bg: "rgba(3,7,11,0.9)",
    rail_bg: "rgba(7,11,18,0.92)",
    radius: "8px",
    font_family: "Inter, Arial, sans-serif",
    mono_font_family: '"JetBrains Mono", Consolas, monospace',
  },
  light: {
    color_scheme: "light",
    accent: "#10b981",
    accent_contrast: "#ffffff",
    bg: "#f7f8fb",
    panel: "#ffffff",
    panel_2: "#f1f5f9",
    panel_3: "#e8edf3",
    text: "#0f172a",
    muted: "#475569",
    dim: "#64748b",
    border: "rgba(15,23,42,0.1)",
    border_strong: "rgba(15,23,42,0.18)",
    surface_hover: "rgba(15,23,42,0.06)",
    surface_muted: "rgba(15,23,42,0.04)",
    nav_bg: "rgba(255,255,255,0.92)",
    rail_bg: "rgba(255,255,255,0.94)",
    radius: "8px",
    font_family: "Inter, Arial, sans-serif",
    mono_font_family: '"JetBrains Mono", Consolas, monospace',
  },
};

export const DEFAULT_DARK_THEME: PreviewTheme = {
  key: "dark",
  names: { ru: "Тёмная", en: "Dark" },
  enabled: true,
  default: true,
  active_variant: "dark",
  tokens: DEFAULT_THEME_VARIANTS.dark,
  variants: DEFAULT_THEME_VARIANTS,
};

export const LEGACY_LIGHT_THEME: PreviewTheme = {
  key: "light",
  names: { ru: "Светлая", en: "Light" },
  enabled: true,
  default: false,
  hidden: true,
  active_variant: "light",
  variant_alias_for: "dark",
  tokens: DEFAULT_THEME_VARIANTS.light,
};

export const WINDOWS_95_THEME: PreviewTheme = {
  key: "windows95",
  names: { ru: "Windows 95", en: "Windows 95" },
  enabled: true,
  default: false,
  css_file: "style.css",
  assets_version: 9,
  tokens: {
    color_scheme: "light",
    style_preset: "win95",
  },
};

export const ASCII_THEME: PreviewTheme = {
  key: "ascii",
  names: { ru: "ASCII", en: "ASCII" },
  enabled: true,
  default: false,
  css_file: "style.css",
  tokens: {
    color_scheme: "dark",
    style_preset: "ascii",
  },
};
