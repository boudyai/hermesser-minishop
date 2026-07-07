const DEMO_ADMIN_EMAIL = "3252a8@proton.me";
const DEMO_ADMIN_GRAVATAR_HASH = "e06e9ae24816fb1d6ed86b58e6fd00d3abe7860b8d51128b8a3e848f208d5e92";
const DEMO_ADMIN_GRAVATAR_URL = `https://www.gravatar.com/avatar/${DEMO_ADMIN_GRAVATAR_HASH}?d=mp&s=160`;

export type DemoAvatarUser = Record<string, unknown> & {
  email?: string | null;
  telegram_linked?: boolean | null;
  telegram_id?: number | string | null;
  user_id?: number | string | null;
  id?: number | string | null;
  username?: string | null;
};

function normalizedEmail(value: unknown): string {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function hasLinkedTelegram(user: DemoAvatarUser | null | undefined): boolean {
  if (!user || user.telegram_linked === false) return false;
  return Boolean(user.telegram_linked || Number(user.telegram_id || 0) > 0);
}

function avatarSeed(user: DemoAvatarUser | null | undefined): string {
  return encodeURIComponent(
    String(
      user?.telegram_id || user?.user_id || user?.id || user?.username || user?.email || "user"
    )
  );
}

export function demoAvatarUrl(user: DemoAvatarUser | null | undefined, size = 96): string {
  if (!user) return "";
  if (normalizedEmail(user.email) === DEMO_ADMIN_EMAIL) return DEMO_ADMIN_GRAVATAR_URL;
  if (!hasLinkedTelegram(user)) return "";
  return `https://i.pravatar.cc/${size}?u=remnawave-minishop-demo-${avatarSeed(user)}`;
}

export function withDemoAvatar<T extends DemoAvatarUser | null | undefined>(
  user: T,
  size = 96
): T | DemoAvatarUser {
  if (!user || typeof user !== "object") return user;
  const avatarUrl = demoAvatarUrl(user, size);
  if (!avatarUrl) return user;
  return {
    ...user,
    avatar_url: avatarUrl,
    telegram_photo_url: avatarUrl,
  };
}

export function withDemoAvatarDetail<T extends Record<string, unknown> | null | undefined>(
  detail: T,
  size = 96
): T | Record<string, unknown> {
  if (!detail || typeof detail !== "object") return detail;
  return {
    ...detail,
    user: withDemoAvatar(detail.user as DemoAvatarUser | null | undefined, size),
  };
}

export function withDemoAvatarTicket<T extends Record<string, unknown> | null | undefined>(
  ticket: T,
  size = 96
): T | Record<string, unknown> {
  if (!ticket || typeof ticket !== "object") return ticket;
  return {
    ...ticket,
    user: withDemoAvatar(ticket.user as DemoAvatarUser | null | undefined, size),
  };
}
