import { mount, unmount } from "svelte";

import AdminPanel from "./admin/AdminPanel.svelte";
import { createAdminMountProps } from "./adminMountProps.svelte.js";
import "./styles-admin.css";

function mountAdminPanel(target, props = {}) {
  if (!target) throw new Error("admin_mount_target_missing");

  const mountProps = createAdminMountProps(props);
  const instance = mount(AdminPanel, { target, props: mountProps.props });
  let destroyed = false;

  return {
    update(nextProps = {}) {
      if (destroyed) return;
      mountProps.update(nextProps);
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      void unmount(instance);
      target.replaceChildren();
    },
  };
}

window.SubscriptionWebAppAdmin = {
  AdminPanel,
  mount: mountAdminPanel,
};
window.SubscriptionWebAppAdminPanel = AdminPanel;
window.dispatchEvent(
  new CustomEvent("subscription-webapp-admin-ready", {
    detail: window.SubscriptionWebAppAdmin,
  })
);
