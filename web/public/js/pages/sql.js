// Read-only view of the database behind the site: tables, live-refreshing rows, free SELECT queries.
import { dbApi, query } from "../api.js";
import { getAuth } from "../auth.js";
import { icon } from "../icons.js";
import { duration, emptyState, errorState, esc, localTime, loginPrompt, onClick, skeleton, toast } from "../ui.js";

const PAGE_SIZE = 20;
const REFRESH_MS = 5000;
const ISO_UTC = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/;
const SAMPLES = {
  "Lịch sử mới nhất": `SELECT p.id, u.username, p.created_at, p.model, p.input_json, p.predicted_label, p.predicted_value
FROM predictions p JOIN users u ON u.id = p.user_id
ORDER BY p.id DESC
LIMIT 20`,
  "Đếm theo mô hình": `SELECT model, task, COUNT(*) AS so_du_doan
FROM predictions
GROUP BY model, task
ORDER BY so_du_doan DESC`,
  "Dự đoán theo tài khoản": `SELECT u.username, COUNT(p.id) AS so_du_doan
FROM users u LEFT JOIN predictions p ON p.user_id = u.id
GROUP BY u.username
ORDER BY so_du_doan DESC`,
  "Kết quả các lần train": `SELECT r.id AS lan_train, r.created_at, m.label, m.r2, m.rmse, m.is_best
FROM training_runs r JOIN model_runs m ON m.run_id = r.id
ORDER BY r.id DESC, m.r2 DESC`,
};
const state = { table: "predictions", offset: 0, live: false, sql: SAMPLES["Lịch sử mới nhất"] };

function cell(value) {
  if (value === null || value === undefined) return `<span class="sub">NULL</span>`;
  if (typeof value === "string" && ISO_UTC.test(value)) return `<span title="${esc(value)} (UTC)">${localTime(value)}</span>`;
  const text = String(value);
  return text.length > 60 ? `<span title="${esc(text)}">${esc(text.slice(0, 59))}…</span>` : esc(text);
}

function dataTable(columns, rows) {
  if (!rows.length) return emptyState("Không có dòng nào", "Bảng hoặc truy vấn này chưa có dữ liệu.");
  const isNum = columns.map((_, i) => rows.every(r => r[i] === null || typeof r[i] === "number"));
  return `<div class="table-wrap"><table class="data sql-data">
    <thead><tr>${columns.map((c, i) => `<th class="${isNum[i] ? "num" : ""}">${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => `<tr>${r.map((v, i) => `<td class="${isNum[i] ? "num" : ""}">${cell(v)}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div>`;
}

export default {
  title: "Dữ liệu SQL",
  subtitle: "Xem trực tiếp CSDL của hệ thống (PostgreSQL trên Render) — chỉ đọc, dữ liệu cập nhật theo thời gian thực",
  icon: "database",

  async render(view, ctx) {
    if (!getAuth()) {
      view.innerHTML = `<div class="card">${loginPrompt("Trang dữ liệu SQL chỉ dành cho tài khoản quản trị <b>admin</b> (mật khẩu là biến ADMIN_PASSWORD).")}</div>`;
      return;
    }
    view.innerHTML = `<div class="card">${skeleton({ lines: 4 })}</div>`;
    try {
      await dbApi("/sql/tables", { auth: true });
    } catch (err) {
      if (!ctx.alive()) return;
      view.innerHTML = err.status === 403
        ? `<div class="card">${emptyState("Chỉ dành cho quản trị viên",
          "Tài khoản đang đăng nhập không có quyền xem CSDL. Đăng xuất rồi đăng nhập bằng tài khoản <b>admin</b>.")}</div>`
        : `<div class="card">${errorState(err.message)}</div>`;
      return;
    }
    if (!ctx.alive()) return;

    view.innerHTML = `
      <section class="card">
        <div class="card-head">
          <div><h2>Các bảng trong CSDL</h2><p class="sub" id="dbName">Đang kết nối…</p></div>
          <div class="btn-row">
            <label class="chip" style="display:inline-flex;gap:6px;align-items:center">
              <input type="checkbox" id="live" ${state.live ? "checked" : ""}>Tự làm mới mỗi ${REFRESH_MS / 1000} giây
            </label>
            <button class="btn ghost small" id="refresh" type="button">${icon("refresh-cw", 14)}Làm mới</button>
          </div>
        </div>
        <div class="btn-row" id="tables">${skeleton({ lines: 1 })}</div>
      </section>

      <section class="card">
        <div class="card-head">
          <div><h2 id="tableTitle">Bảng</h2><p class="sub" id="tableSub"></p></div>
          <span class="sub" id="updated"></span>
        </div>
        <div id="rows">${skeleton({ lines: 6 })}</div>
        <div class="pager" id="pager"></div>
      </section>

      <section class="card">
        <div class="card-head">
          <div><h2>Chạy câu lệnh SQL</h2>
            <p class="sub">Chỉ đọc (SELECT / WITH), mỗi lần một câu, tối đa 500 dòng. Không truy vấn được cột password_hash.</p></div>
        </div>
        <div class="btn-row" style="margin-bottom:10px">
          ${Object.keys(SAMPLES).map(k => `<button class="chip" type="button" data-sample="${esc(k)}">${esc(k)}</button>`).join("")}
        </div>
        <textarea class="input" id="sql" rows="6" spellcheck="false"
          style="font-family:Consolas,'Courier New',monospace;font-size:13px;resize:vertical">${esc(state.sql)}</textarea>
        <div class="btn-row" style="margin:10px 0 14px">
          <button class="btn" id="run" type="button">${icon("terminal", 16)}Chạy (Ctrl + Enter)</button>
          <span class="sub" id="runInfo"></span>
        </div>
        <div id="result"></div>
      </section>`;

    const sqlBox = view.querySelector("#sql");
    view.querySelectorAll("[data-sample]").forEach(chip => chip.addEventListener("click", () => {
      sqlBox.value = SAMPLES[chip.dataset.sample];
      this.run(view, ctx);
    }));
    sqlBox.addEventListener("keydown", e => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); this.run(view, ctx); }
    });
    onClick(view, "#run", () => this.run(view, ctx));
    onClick(view, "#refresh", () => this.loadAll(view, ctx));
    view.querySelector("#live").addEventListener("change", e => { state.live = e.target.checked; });

    // Live refresh: re-read the open table while the page is visible; stops when the user leaves the page.
    const timer = setInterval(() => {
      if (!ctx.alive()) { clearInterval(timer); return; }
      if (state.live && !document.hidden) this.loadAll(view, ctx, { quiet: true });
    }, REFRESH_MS);

    await this.loadAll(view, ctx);
  },

  async loadAll(view, ctx, { quiet = false } = {}) {
    await Promise.all([this.loadTables(view, ctx, quiet), this.loadRows(view, ctx, quiet)]);
  },

  async loadTables(view, ctx, quiet) {
    const box = view.querySelector("#tables");
    let data;
    try {
      data = await dbApi("/sql/tables", { auth: true });
    } catch (err) {
      if (!ctx.alive() || quiet) return;
      box.innerHTML = errorState(err.message);
      view.querySelector("#dbName").textContent = "";
      return;
    }
    if (!ctx.alive()) return;
    view.querySelector("#dbName").textContent = `CSDL: ${data.database} · ${data.tables.length} bảng · chỉ đọc`;
    if (!data.tables.some(t => t.name === state.table)) state.table = data.tables[0]?.name || "";
    box.innerHTML = data.tables.map(t => `
      <button class="chip ${t.name === state.table ? "active" : ""}" type="button" data-table="${esc(t.name)}"
        title="Cột: ${esc(t.columns.join(", "))}">${icon("database", 13)} ${esc(t.name)} · ${t.rows}</button>`).join("");
    box.querySelectorAll("[data-table]").forEach(chip => chip.addEventListener("click", () => {
      state.table = chip.dataset.table;
      state.offset = 0;
      this.loadAll(view, ctx);
    }));
  },

  async loadRows(view, ctx, quiet) {
    const box = view.querySelector("#rows");
    const pager = view.querySelector("#pager");
    if (!state.table) return;
    if (!quiet) box.innerHTML = skeleton({ lines: 6 });
    let data;
    try {
      data = await dbApi(`/sql/tables/${encodeURIComponent(state.table)}${query({ limit: PAGE_SIZE, offset: state.offset })}`, { auth: true });
    } catch (err) {
      if (!ctx.alive() || quiet) return;
      box.innerHTML = errorState(err.message, "retryRows");
      onClick(box, "#retryRows", () => this.loadRows(view, ctx));
      return;
    }
    if (!ctx.alive()) return;
    view.querySelector("#tableTitle").textContent = `Bảng ${data.table}`;
    view.querySelector("#tableSub").textContent = `${data.total} dòng · mới nhất trước · ${data.columns.length} cột`;
    view.querySelector("#updated").textContent = `Cập nhật lúc ${new Date().toLocaleTimeString("vi-VN")}`;
    box.innerHTML = dataTable(data.columns, data.rows);
    const page = Math.floor(state.offset / PAGE_SIZE) + 1;
    const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
    pager.innerHTML = `
      <span>Trang ${page}/${pages}</span>
      <div class="btn-row">
        <button class="btn ghost small" id="prev" ${page <= 1 ? "disabled" : ""}>${icon("chevron-left", 14)}Trước</button>
        <button class="btn ghost small" id="next" ${page >= pages ? "disabled" : ""}>Sau${icon("chevron-right", 14)}</button>
      </div>`;
    onClick(pager, "#prev", () => { state.offset -= PAGE_SIZE; this.loadRows(view, ctx); });
    onClick(pager, "#next", () => { state.offset += PAGE_SIZE; this.loadRows(view, ctx); });
  },

  async run(view, ctx) {
    const sqlBox = view.querySelector("#sql");
    const result = view.querySelector("#result");
    const info = view.querySelector("#runInfo");
    const btn = view.querySelector("#run");
    state.sql = sqlBox.value;
    if (!state.sql.trim()) { toast("Hãy nhập câu lệnh SQL"); return; }
    btn.disabled = true;
    info.textContent = "Đang chạy…";
    result.innerHTML = skeleton({ lines: 4 });
    try {
      const data = await dbApi("/sql/query", { method: "POST", auth: true, body: { sql: state.sql } });
      if (!ctx.alive()) return;
      info.textContent = `${data.rows.length} dòng${data.truncated ? " (đã cắt ở 500)" : ""} · ${duration(data.elapsed_ms)}`;
      result.innerHTML = dataTable(data.columns, data.rows);
    } catch (err) {
      if (!ctx.alive()) return;
      info.textContent = "";
      result.innerHTML = `<div class="state error">${icon("circle-alert", 30)}<b>Không chạy được</b><p>${esc(err.message)}</p></div>`;
    } finally {
      btn.disabled = false;
    }
  },
};
