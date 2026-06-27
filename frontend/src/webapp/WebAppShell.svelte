<script>
  import BrandMark from "$lib/webapp/BrandMark.svelte";
  import BottomNav from "./BottomNav.svelte";

  let {
    screen,
    activeTab,
    brand = {},
    brandTitle,
    devicesEnabled,
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
  } = $props();
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
