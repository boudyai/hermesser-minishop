export type AdminBadgeVariant = "danger" | "muted" | "success" | "warning";

export type TranslateFn = (
  key: string,
  params?: Record<string, unknown>,
  fallback?: string
) => string;

export type SupportUserLike = {
  user_id?: number | string | null;
  username?: string | null;
  email?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  avatar_url?: string | null;
  photo_url?: string | null;
  is_banned?: boolean | null;
};

export type SupportTicketLike = {
  ticket_id?: number | string;
  subject?: string | null;
  status?: string;
  priority?: string;
  category?: string;
  unread_admin_count?: number | null;
  last_message_at?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
  user?: SupportUserLike | null;
};

export type SupportUserSnapshotLike = {
  name?: string | null;
  tariff?: string | null;
  panel_status?: string | null;
  remaining?: string | null;
};
