(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const dialog = $("admin-dialog"), loginForm = $("admin-login-form"), registerForm = $("admin-register-form");
  const storageKey = "shiftlink.mes.adminToken";
  let token = "", pending = false;
  try { token = sessionStorage.getItem(storageKey) || ""; } catch (_) { /* Session remains in memory when storage is unavailable. */ }

  function message(value, error = false) {
    $("admin-message").textContent = value;
    $("admin-message").classList.toggle("admin-error", error);
  }
  function session(value) {
    token = value;
    try { if (token) sessionStorage.setItem(storageKey, token); else sessionStorage.removeItem(storageKey); } catch (_) { /* In-memory session still works. */ }
    $("admin-open").textContent = token ? "계정 관리" : "관리자 로그인";
    $("admin-logout").hidden = !token;
    $("admin-title").textContent = token ? "작업자 계정 관리" : "관리자 로그인";
    loginForm.hidden = Boolean(token);
    $("admin-management").hidden = !token;
    if (!token) $("admin-account-list").replaceChildren();
  }
  async function request(path, payload) {
    const headers = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    if (payload !== undefined) headers["Content-Type"] = "application/json";
    const response = await fetch(path, {
      method: payload === undefined ? "GET" : "POST", headers,
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: AbortSignal.timeout(10000), cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401) { session(""); loginForm.reset(); registerForm.reset(); }
      throw new Error(data.error || `요청 실패 (${response.status})`);
    }
    return data;
  }
  function render(accounts) {
    const body = $("admin-account-list");
    body.replaceChildren();
    for (const account of accounts.filter((item) => item.role === "operator")) {
      const row = document.createElement("tr");
      for (const value of [account.id, account.name]) {
        const cell = document.createElement("td"); cell.textContent = value; row.appendChild(cell);
      }
      body.appendChild(row);
    }
    if (!body.children.length) {
      const row = document.createElement("tr"), cell = document.createElement("td");
      cell.colSpan = 2; cell.textContent = "등록된 작업자 계정이 없습니다."; row.appendChild(cell); body.appendChild(row);
    }
  }
  async function loadAccounts() {
    $("admin-account-list").replaceChildren();
    const data = await request("/api/admin/accounts");
    render(data.accounts);
  }
  async function run(action) {
    if (pending) return;
    pending = true; message("처리 중…");
    dialog.querySelectorAll('button:not(#admin-close), input').forEach((el) => { el.disabled = true; });
    try { await action(); }
    catch (error) { message(error.name === "TimeoutError" || error.name === "TypeError" ? "서버에 연결하지 못했습니다. 다시 시도해 주세요." : error.message, true); }
    finally {
      pending = false;
      dialog.querySelectorAll("button, input").forEach((el) => { el.disabled = false; });
    }
  }

  $("admin-open").addEventListener("click", () => {
    if (dialog.open || pending) return;
    session(token); message(""); dialog.showModal();
    if (token) run(async () => { await loadAccounts(); message(""); });
  });
  $("admin-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { $("admin-password").value = ""; $("worker-password").value = ""; });
  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (pending) return;
    const payload = { id: $("admin-id").value.trim(), password: $("admin-password").value };
    $("admin-password").value = "";
    run(async () => {
      const data = await request("/api/admin/login", payload);
      session(data.token); loginForm.reset();
      await loadAccounts(); message("관리자로 로그인했습니다.");
      if (dialog.open) $("worker-name").focus();
    });
  });
  registerForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (pending) return;
    const payload = { id: $("worker-id").value.trim(), name: $("worker-name").value.trim(), password: $("worker-password").value };
    $("worker-password").value = "";
    run(async () => {
      await request("/api/admin/accounts", payload);
      registerForm.reset();
      message("작업자 계정을 등록했습니다.");
      try { await loadAccounts(); }
      catch (error) { throw new Error(`계정은 등록되었지만 목록을 불러오지 못했습니다. ${error.message}`); }
    });
  });
  $("admin-refresh").addEventListener("click", () => run(async () => { await loadAccounts(); message("목록을 새로고침했습니다."); }));
  $("admin-logout").addEventListener("click", () => run(async () => {
    await request("/api/admin/logout", {});
    session(""); loginForm.reset(); registerForm.reset(); message("관리자 로그아웃이 완료되었습니다.");
  }));
  session(token);
})();
