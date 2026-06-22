export function createUiChrome({
  getCurrentLang,
  normalizeLangCode,
  setGuestLanguage,
  setLanguageClickGuard,
  setLanguageClickGuardArmed,
  setLanguageMenuOpenState,
}: {
  getCurrentLang: () => string;
  normalizeLangCode: (value: string) => string;
  setGuestLanguage: (value: string) => void;
  setLanguageClickGuard: (value: boolean) => void;
  setLanguageClickGuardArmed: (value: boolean) => void;
  setLanguageMenuOpenState: (value: boolean) => void;
}) {
  let scrollLockApplied = false;
  let languageClickGuardTimer: number | null = null;
  let languageClickGuardArmTimer: number | null = null;

  function syncBodyScrollLock(locked: boolean) {
    if (typeof document === "undefined") return;
    if (locked && !scrollLockApplied) {
      document.body.style.overflow = "hidden";
      scrollLockApplied = true;
      return;
    }
    if (!locked && scrollLockApplied) {
      document.body.style.overflow = "";
      scrollLockApplied = false;
    }
  }

  function clearLanguageClickGuard() {
    if (languageClickGuardTimer) {
      window.clearTimeout(languageClickGuardTimer);
      languageClickGuardTimer = null;
    }
    if (languageClickGuardArmTimer) {
      window.clearTimeout(languageClickGuardArmTimer);
      languageClickGuardArmTimer = null;
    }
    setLanguageClickGuard(false);
    setLanguageClickGuardArmed(false);
  }

  function setLanguageMenuOpen(open: boolean) {
    const nextOpen = Boolean(open);
    setLanguageMenuOpenState(nextOpen);
    clearLanguageClickGuard();
    if (nextOpen) {
      setLanguageClickGuard(true);
      languageClickGuardArmTimer = window.setTimeout(() => {
        setLanguageClickGuardArmed(true);
        languageClickGuardArmTimer = null;
      }, 220);
      return;
    }
    setLanguageClickGuard(true);
    setLanguageClickGuardArmed(false);
    languageClickGuardTimer = window.setTimeout(() => {
      setLanguageClickGuard(false);
      languageClickGuardTimer = null;
    }, 260);
  }

  function updateGuestLanguage(nextValue: string) {
    const language = normalizeLangCode(nextValue);
    setLanguageMenuOpen(false);
    if (!language || language === getCurrentLang()) return;
    setGuestLanguage(language);
  }

  return {
    clearLanguageClickGuard,
    setLanguageMenuOpen,
    syncBodyScrollLock,
    updateGuestLanguage,
  };
}
