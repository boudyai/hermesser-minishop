import { TableHandler } from "@vincjo/datatables";

export function createAdminDatatable(rows = [], options = {}) {
  return new TableHandler(Array.isArray(rows) ? rows : [], options);
}

export function syncAdminDatatable(table, rows = []) {
  table.setRows(Array.isArray(rows) ? rows : []);
}

export function datatablePageToAdminPage(table) {
  return Math.max(0, Number(table?.currentPage || 1) - 1);
}

export function adminPageToDatatablePage(page) {
  return Math.max(1, Math.floor(Number(page) || 0) + 1);
}
