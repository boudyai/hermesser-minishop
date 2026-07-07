<script lang="ts">
  import type { Snippet } from "svelte";
  import BrandMark from "$lib/webapp/BrandMark.svelte";
  import BottomNav from "./BottomNav.svelte";

  type Translate = (key: string, params?: Record<string, unknown>, fallback?: string) => string;
  type Action = () => void;

  type Props = {
    activeTab?: string;
    brand?: Record<string, unknown>;
    brandTitle?: string;
    children?: Snippet;
    devicesEnabled?: boolean;
    goDevices: Action;
    goHome: Action;
    goInvite: Action;
    goSettings: Action;
    goSupport: Action;
    hasUnlinkedIdentity?: boolean;
    isAdmin?: boolean;
    openAdminPanel: Action;
    screen?: string;
    supportEnabled?: boolean;
    supportUnreadCount?: number;
    supportUnreadLoaded?: boolean;
    supportUnreadLoading?: boolean;
    t: Translate;
  };

  let {
    screen = "home",
    activeTab = "home",
    brand = {},
    brandTitle = "",
    devicesEnabled = false,
    supportEnabled = true,
    supportUnreadCount = 0,
    supportUnreadLoading = false,
    supportUnreadLoaded = false,
    hasUnlinkedIdentity,
    isAdmin,
    openAdminPanel,
    goDevices,
    goHome,
    goInvite,
    goSupport,
    goSettings,
    t,
    children,
  }: Props = $props();
</script>

<div class="phone-screen" class:home-screen={screen === "home"}>
  {#if screen === "install" || screen === "invite" || screen === "devices" || screen === "support" || screen === "settings"}
    <header class="app-header accent-title">
      <div class="brand-row">
        <BrandMark {brand} />
        <strong>{brandTitle}</strong>
      </div>
    </header>
  {/if}

  {@render children?.()}

  <BottomNav
    {activeTab}
    {brand}
    {brandTitle}
    {devicesEnabled}
    {supportEnabled}
    {supportUnreadCount}
    {supportUnreadLoading}
    {supportUnreadLoaded}
    {hasUnlinkedIdentity}
    {isAdmin}
    onAdmin={openAdminPanel}
    onDevices={goDevices}
    onHome={goHome}
    onInvite={goInvite}
    onSupport={goSupport}
    onSettings={goSettings}
    {t}
  />
</div>
