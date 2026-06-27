<script>
  import { cn } from "../utils.js";
  import { normalizeBrand } from "./browser.js";

  const LOGO_LOAD_TIMEOUT_MS = 10000;

  let { brand = {}, logoUrl = "", size = "sm", animate = false, class: className = "" } = $props();

  const SIZE_CLASSES = {
    sm: "",
    md: "brand-mark-lg",
    lg: "brand-mark-xl",
    xl: "brand-mark-xl",
  };

  let loaded = $state(false);
  let failed = $state(false);
  let lastLogoUrl = $state("");
  let logoLoadTimer = null;
  let logoLoadTimerUrl = "";

  const normalizedBrand = $derived(
    normalizeBrand({
      ...brand,
      logoUrl: logoUrl || brand?.logoUrl,
    })
  );
  const normalizedLogoUrl = $derived(normalizedBrand.logoUrl);
  const sizeClass = $derived(SIZE_CLASSES[size] || "");

  $effect(() => {
    if (normalizedLogoUrl !== lastLogoUrl) {
      lastLogoUrl = normalizedLogoUrl;
      loaded = false;
      failed = false;
    }

    if (normalizedLogoUrl && !loaded && !failed) armLogoLoadTimeout();
    if (!normalizedLogoUrl || loaded || failed) clearLogoLoadTimeout();

    return clearLogoLoadTimeout;
  });

  function clearLogoLoadTimeout() {
    if (logoLoadTimer) {
      window.clearTimeout(logoLoadTimer);
      logoLoadTimer = null;
    }
    logoLoadTimerUrl = "";
  }

  function armLogoLoadTimeout() {
    if (typeof window === "undefined") return;
    if (logoLoadTimer && logoLoadTimerUrl === normalizedLogoUrl) return;
    clearLogoLoadTimeout();
    logoLoadTimerUrl = normalizedLogoUrl;
    logoLoadTimer = window.setTimeout(() => {
      if (logoLoadTimerUrl === normalizedLogoUrl && !loaded) failed = true;
    }, LOGO_LOAD_TIMEOUT_MS);
  }
</script>

<div
  class={cn(
    "brand-mark",
    sizeClass,
    animate && "brand-mark-animate",
    normalizedLogoUrl && !failed && !loaded && "brand-mark-loading",
    normalizedLogoUrl && !failed && loaded && "brand-mark-loaded",
    className
  )}
  aria-busy={normalizedLogoUrl && !failed && !loaded ? "true" : undefined}
>
  {#if normalizedLogoUrl && !failed}
    {#if !loaded}
      <span class="brand-mark-spinner" aria-hidden="true"></span>
    {/if}
    <img
      class:loaded
      src={normalizedLogoUrl}
      alt=""
      loading="eager"
      decoding="async"
      fetchpriority="high"
      onload={() => {
        loaded = true;
        clearLogoLoadTimeout();
      }}
      onerror={() => {
        failed = true;
        clearLogoLoadTimeout();
      }}
    />
  {/if}
</div>

<style>
  .brand-mark {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    flex-shrink: 0;
    overflow: visible;
    font-size: 1.625rem;
  }

  .brand-mark img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  .brand-mark img.loaded {
    opacity: 1;
  }

  .brand-mark.brand-mark-lg {
    width: 4.125rem;
    height: 4.125rem;
    font-size: 2.875rem;
  }

  .brand-mark.brand-mark-xl {
    width: 6rem;
    height: 6rem;
    font-size: 4.375rem;
  }

  .brand-mark.brand-mark-animate {
    animation: brand-mark-pulse 2s ease-in-out infinite;
  }

  .brand-mark-spinner {
    position: absolute;
    top: 50%;
    left: 50%;
    width: clamp(1rem, 42%, 2.5rem);
    height: clamp(1rem, 42%, 2.5rem);
    border: 2px solid color-mix(in srgb, currentColor 24%, transparent);
    border-top-color: currentColor;
    border-radius: 50%;
    animation: brand-mark-spin 0.8s linear infinite;
    opacity: 0.65;
    transform: translate(-50%, -50%) rotate(0deg);
    transform-origin: center;
  }

  @keyframes brand-mark-spin {
    100% {
      transform: translate(-50%, -50%) rotate(360deg);
    }
  }

  @keyframes brand-mark-pulse {
    0%,
    100% {
      transform: scale(1);
    }
    50% {
      transform: scale(1.05);
    }
  }
</style>
