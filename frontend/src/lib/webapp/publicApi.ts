import { readCookie } from "./session.js";
import type { paths } from "../api/openapi.generated";

type HttpMethod = "get" | "put" | "post" | "delete" | "patch";
export type ApiPath = keyof paths;
type ApiPathFor<Path extends string> = Path extends `/api${string}` ? Path : `/api${Path}`;
type KnownApiPath<Path extends string> = ApiPathFor<Path> & ApiPath;
type OperationFor<Path extends string, Method extends HttpMethod> =
  KnownApiPath<Path> extends never ? never : NonNullable<paths[KnownApiPath<Path>][Method]>;
type JsonRequestBody<Operation> = Operation extends {
  requestBody: { content: { "application/json": infer Body } };
}
  ? Body
  : Record<string, unknown>;
type JsonResponse<Operation> = Operation extends {
  responses: { 200: { content: { "application/json": infer Body } } };
}
  ? Body
  : Record<string, unknown>;
export type ApiResponse<Path extends string> =
  | JsonResponse<OperationFor<Path, "get">>
  | JsonResponse<OperationFor<Path, "post">>
  | JsonResponse<OperationFor<Path, "put">>
  | JsonResponse<OperationFor<Path, "patch">>
  | JsonResponse<OperationFor<Path, "delete">>;
export type GetResponse<Path extends string> = JsonResponse<OperationFor<Path, "get">>;
export type PostPayload<Path extends string> = JsonRequestBody<OperationFor<Path, "post">>;
export type PostResponse<Path extends string> = JsonResponse<OperationFor<Path, "post">>;

export type BootstrapResponse = GetResponse<"/api/bootstrap">;
export type MeResponse = GetResponse<"/api/me">;
export type AccountEmailRequestResponse = PostResponse<"/api/account/email/request">;
export type AccountEmailVerifyResponse = PostResponse<"/api/account/email/verify">;
export type AccountLanguageResponse = PostResponse<"/api/account/language">;
export type AccountPasswordRequestResponse = PostResponse<"/api/account/password/request">;
export type AccountPasswordConfirmResponse = PostResponse<"/api/account/password/confirm">;
export type AccountTelegramLinkResponse = PostResponse<"/api/account/telegram/link">;
export type AuthEmailMagicResponse = PostResponse<"/api/auth/email/magic">;
export type AuthEmailPasswordResponse = PostResponse<"/api/auth/email/password">;
export type AuthEmailRequestResponse = PostResponse<"/api/auth/email/request">;
export type AuthEmailVerifyResponse = PostResponse<"/api/auth/email/verify">;
export type AuthLogoutResponse = PostResponse<"/api/auth/logout">;
export type AuthTokenResponse = PostResponse<"/api/auth/token">;
export type DevicesResponse = GetResponse<"/api/devices">;
export type DevicesDisconnectResponse = PostResponse<"/api/devices/disconnect">;
export type DeviceTopupOptionsResponse = GetResponse<"/api/devices/topup-options">;
export type PaymentCreateResponse = PostResponse<"/api/payments">;
export type PaymentStatusResponse = GetResponse<"/api/payments/{payment_id}">;
export type PromoApplyResponse = PostResponse<"/api/promo/apply">;
export type ReferralWelcomeBonusResponse = PostResponse<"/api/referral/welcome-bonus/claim">;
export type SubscriptionGuidesResponse = GetResponse<"/api/subscription-guides">;
export type PublicSubscriptionGuidesResponse =
  GetResponse<"/api/subscription-guides/public/{share_token}">;
export type SubscriptionAutoRenewResponse = PostResponse<"/api/subscription/auto-renew">;
export type SupportTicketsResponse = GetResponse<"/api/support/tickets">;
export type SupportTicketCreateResponse = PostResponse<"/api/support/tickets">;
export type SupportTicketDetailResponse = GetResponse<"/api/support/tickets/{id}">;
export type SupportTicketReplyResponse = PostResponse<"/api/support/tickets/{id}/messages">;
export type SupportTicketReadResponse = PostResponse<"/api/support/tickets/{id}/read">;
export type SupportUnreadResponse = GetResponse<"/api/support/unread">;
export type TariffChangeResponse = PostResponse<"/api/tariffs/change">;
export type TariffChangeOptionsResponse = GetResponse<"/api/tariffs/change-options">;
export type TariffChangePaymentResponse = PostResponse<"/api/tariffs/change-payment">;
export type TariffTopupOptionsResponse = GetResponse<"/api/tariffs/topup-options">;
export type TrialActivateResponse = PostResponse<"/api/trial/activate">;

type MockContext = Record<string, unknown>;
export type MockApi = (
  path: string,
  options: RequestInit,
  context: MockContext
) => unknown | Promise<unknown>;

type ApiClientOptions = {
  apiBase?: string;
  csrfCookieName?: string;
  getCsrfToken?: () => string;
  onUnauthorized?: () => void;
  mockApi?: MockApi | null;
  getMockContext?: () => MockContext;
};

export type ApiClient = {
  api<Path extends string>(path: Path, options?: RequestInit): Promise<ApiResponse<Path>>;
  publicApi<Path extends string>(
    path: Path,
    payload?: PostPayload<Path>,
    options?: Pick<RequestInit, "signal">
  ): Promise<PostResponse<Path>>;
};

export function unwrap<T extends { ok: boolean }>(response: T): Extract<T, { ok: true }> {
  if (!response.ok) throw response;
  return response as Extract<T, { ok: true }>;
}

export function createApiClient({
  apiBase = "",
  csrfCookieName = "rw_webapp_csrf",
  getCsrfToken = () => "",
  onUnauthorized = () => {},
  mockApi = null,
  getMockContext = () => ({}),
}: ApiClientOptions = {}): ApiClient {
  const isFormDataBody = (body: BodyInit | null | undefined) =>
    typeof FormData !== "undefined" && body instanceof FormData;

  async function api<Path extends string>(
    path: Path,
    options: RequestInit = {}
  ): Promise<ApiResponse<Path>> {
    if (mockApi) return (await mockApi(path, options, getMockContext())) as ApiResponse<Path>;

    const method = String(options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers);

    const csrf = getCsrfToken() || readCookie(csrfCookieName) || "";
    if (csrf && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      headers.set("X-CSRF-Token", csrf);
    }
    if (options.body && !headers.has("Content-Type") && !isFormDataBody(options.body)) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${apiBase}${path}`, {
      ...options,
      headers,
      credentials: "same-origin",
    });
    const payload = await response.json().catch(() => ({}));
    if (response.status === 401) onUnauthorized();
    return payload as ApiResponse<Path>;
  }

  async function publicApi<Path extends string>(
    path: Path,
    payload: PostPayload<Path> = {} as PostPayload<Path>,
    options: Pick<RequestInit, "signal"> = {}
  ): Promise<PostResponse<Path>> {
    if (mockApi) {
      return (await mockApi(
        path,
        { method: "POST", body: JSON.stringify(payload) },
        getMockContext()
      )) as PostResponse<Path>;
    }
    const response = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: options.signal,
      credentials: "same-origin",
    });
    return (await response.json()) as PostResponse<Path>;
  }

  return { api, publicApi };
}
