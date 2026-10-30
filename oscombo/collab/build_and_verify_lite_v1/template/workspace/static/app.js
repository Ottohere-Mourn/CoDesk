/* OrderDesk browser filter UI. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.BuildVerifyOrderDesk = api;
  if (typeof document !== "undefined" && typeof window !== "undefined") {
    api.mount(document, window.fetch.bind(window));
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[char]));
  }

  function mount(doc, fetchImpl) {
    const form = doc.getElementById("filter-form");
    const query = doc.getElementById("order-query");
    const status = doc.getElementById("order-status");
    const body = doc.getElementById("order-results");
    const count = doc.getElementById("result-count");
    const empty = doc.getElementById("empty-state");
    const apply = doc.getElementById("apply-filters");
    let keyboardSubmit = false;

    async function refresh(method) {
      const q = query.value || "";
      const s = status.value || "All";
      const params = new URLSearchParams({ query: q, status: s });
      const response = await fetchImpl(`/api/orders?${params.toString()}`);
      const result = await response.json();
      body.innerHTML = result.orders.map((row) => `<tr><td>${escapeHtml(row.order_id)}</td><td>${escapeHtml(row.customer)}</td><td>${escapeHtml(row.region)}</td><td>${escapeHtml(row.status)}</td><td>$${(row.total_cents / 100).toFixed(2)}</td></tr>`).join("");
      count.textContent = `${result.orders.length} orders shown`;
      empty.hidden = result.orders.length !== 0;
      await fetchImpl("/api/test-events", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ method, query: q, status: s, visible_ids: result.orders.map((row) => row.order_id) })
      });
      return result;
    }

    for (const control of [query, status]) {
      control.addEventListener("keydown", (event) => {
        if (event.key === "Enter") keyboardSubmit = true;
      });
    }
    apply.addEventListener("pointerdown", () => { keyboardSubmit = false; });
    apply.addEventListener("keydown", () => { keyboardSubmit = false; });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      // Chrome supplies the default button as submitter even for Enter in the
      // search field. Use the preceding keyboard event to distinguish it.
      const method = keyboardSubmit || !event.submitter ? "enter" : "button";
      keyboardSubmit = false;
      return refresh(method);
    });
    doc.getElementById("clear-filters").addEventListener("click", (event) => {
      event.preventDefault();
      query.value = "";
      status.value = "All";
      refresh("clear");
    });
    // The QA browser opens with the first regression query prepared, but not
    // submitted. The initial all-orders view remains visible until Enter.
    const ready = refresh("initial").then(() => {
      query.value = "Dana";
      status.value = "Processing";
    });
    return { ready, refresh };
  }

  return { mount };
});
