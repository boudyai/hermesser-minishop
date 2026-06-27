import type { ApiClient, PostPayload } from "./publicApi";
import {
  buildAdminPaymentPath,
  buildAdminPaymentsExportPath,
  buildAdminPaymentsUserPath,
  buildAdminSupportPath,
  buildAdminUserPath,
  buildAdminUsersPath,
  buildAuthTokenPath,
} from "./publicApi";

type ApiCall = ApiClient["api"];
type PublicApiCall = ApiClient["publicApi"];
type ApiUncheckedCall = ApiClient["apiUnchecked"];

declare const apiCall: ApiCall;
declare const publicApiCall: PublicApiCall;
declare const apiUncheckedCall: ApiUncheckedCall;
declare const authTokenPayload: PostPayload<"/api/auth/token">;
declare const dynamicPath: string;

apiCall("/admin/users");
apiCall("/admin/users?page=1");
apiCall("/api/admin/payments/export.csv");
apiCall(buildAdminUsersPath());
apiCall(buildAdminUserPath(42));
apiCall(buildAdminPaymentPath("payment-id"));
apiCall(buildAdminPaymentsExportPath());
publicApiCall(buildAuthTokenPath(), authTokenPayload);

const supportPathNoId: ReturnType<typeof buildAdminSupportPath> = buildAdminSupportPath();
const supportPathWithId: ReturnType<typeof buildAdminSupportPath> = buildAdminSupportPath(42);
const paymentsUserPathNoId: ReturnType<typeof buildAdminPaymentsUserPath> =
  buildAdminPaymentsUserPath();
const paymentsUserPathWithId: ReturnType<typeof buildAdminPaymentsUserPath> =
  buildAdminPaymentsUserPath(42);

void supportPathNoId;
void supportPathWithId;
void paymentsUserPathNoId;
void paymentsUserPathWithId;

apiUncheckedCall("/random/unknown/path");
apiUncheckedCall(dynamicPath);

// @ts-expect-error: arbitrary API paths should be rejected by typed api signature
apiCall("/random/unknown/path");

// @ts-expect-error: string variables must use typed builders or apiUnchecked
apiCall(dynamicPath);

// @ts-expect-error: parameterized API paths must use typed builders
apiCall("/admin/users/42");

// @ts-expect-error: publicApi follows the same typed path boundary as api
publicApiCall(dynamicPath, authTokenPayload);
