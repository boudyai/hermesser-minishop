import { writable } from "svelte/store";
import { adminErrorMessage } from "../errors.js";

export function createBackupsStore({ api, onToast, at }) {
  const state = writable({
    archives: [],
    backupDir: "",
    backupsLoading: false,
    backupsCreating: false,
    backupsUploading: false,
    backupsRestoring: false,
    lastCreated: null,
    lastRestore: null,
  });

  async function loadArchives() {
    state.update((s) => ({ ...s, backupsLoading: true }));
    try {
      const data = await api("/admin/backups");
      if (data?.ok) {
        state.update((s) => ({
          ...s,
          archives: data.archives || [],
          backupDir: data.backup_dir || "",
        }));
      } else {
        onToast(
          adminErrorMessage(data, at, at("backups_load_failed", {}, "Не удалось загрузить бэкапы"))
        );
      }
    } finally {
      state.update((s) => ({ ...s, backupsLoading: false }));
    }
  }

  async function createBackup() {
    state.update((s) => ({ ...s, backupsCreating: true, lastCreated: null }));
    try {
      const data = await api("/admin/backups/create", {
        method: "POST",
      });
      if (data?.ok) {
        state.update((s) => ({ ...s, lastCreated: data.result || null }));
        onToast(at("backups_create_done", {}, "Бэкап создан"));
        await loadArchives();
        return data.archive || null;
      }
      onToast(
        adminErrorMessage(data, at, at("backups_create_failed", {}, "Не удалось создать бэкап"))
      );
      return null;
    } finally {
      state.update((s) => ({ ...s, backupsCreating: false }));
    }
  }

  async function uploadArchive(file) {
    if (!file) return null;
    state.update((s) => ({ ...s, backupsUploading: true }));
    try {
      const body = new FormData();
      body.append("file", file);
      const data = await api("/admin/backups/upload", {
        method: "POST",
        body,
      });
      if (data?.ok) {
        onToast(at("backups_upload_done", {}, "Архив загружен"));
        await loadArchives();
        return data.archive || null;
      }
      onToast(
        adminErrorMessage(data, at, at("backups_upload_failed", {}, "Не удалось загрузить архив"))
      );
      return null;
    } finally {
      state.update((s) => ({ ...s, backupsUploading: false }));
    }
  }

  async function restoreArchive({ archiveName, restoreDatabase, restoreCompose }) {
    const archive_name = String(archiveName || "").trim();
    if (!archive_name) {
      onToast(at("backups_select_archive", {}, "Выберите архив"));
      return false;
    }
    if (!restoreDatabase && !restoreCompose) {
      onToast(at("backups_select_target", {}, "Выберите, что восстановить"));
      return false;
    }

    state.update((s) => ({ ...s, backupsRestoring: true, lastRestore: null }));
    try {
      const data = await api("/admin/backups/restore", {
        method: "POST",
        body: JSON.stringify({
          archive_name,
          restore_database: Boolean(restoreDatabase),
          restore_compose: Boolean(restoreCompose),
          confirm: true,
        }),
      });
      if (data?.ok) {
        state.update((s) => ({ ...s, lastRestore: data.result || null }));
        onToast(at("backups_restore_done", {}, "Восстановление завершено"));
        return true;
      }
      onToast(
        adminErrorMessage(data, at, at("backups_restore_failed", {}, "Не удалось восстановить"))
      );
      return false;
    } finally {
      state.update((s) => ({ ...s, backupsRestoring: false }));
    }
  }

  return {
    subscribe: state.subscribe,
    loadArchives,
    createBackup,
    uploadArchive,
    restoreArchive,
  };
}
