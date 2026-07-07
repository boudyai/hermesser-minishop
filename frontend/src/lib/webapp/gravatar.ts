function bytesToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function sha256Hex(value: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return "";
  const data = new TextEncoder().encode(value);
  const hashBuffer = await subtle.digest("SHA-256", data);
  return bytesToHex(hashBuffer);
}

export async function buildGravatarUrl(emailValue: unknown): Promise<string> {
  const email = String(emailValue || "")
    .trim()
    .toLowerCase();
  if (!email || !globalThis.crypto?.subtle) return "";
  try {
    const hash = await sha256Hex(email);
    return hash ? `https://www.gravatar.com/avatar/${hash}?d=identicon&s=160` : "";
  } catch {
    return "";
  }
}

type ProfileAvatarUser = {
  telegram_photo_url?: string | null;
  telegram_linked?: boolean | null;
} | null;

export function resolveProfileAvatarUrl(user: ProfileAvatarUser, emailAvatarUrl = ""): string {
  const telegramAvatar = String(user?.telegram_photo_url || "").trim();
  if (user?.telegram_linked && telegramAvatar) return telegramAvatar;
  return String(emailAvatarUrl || "").trim();
}
