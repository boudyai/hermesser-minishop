import AdminPanel from "./admin/AdminPanel.svelte";
import "./styles-admin.css";

window.SubscriptionWebAppAdminPanel = AdminPanel;
window.dispatchEvent(
  new CustomEvent("subscription-webapp-admin-ready", {
    detail: { AdminPanel },
  })
);
