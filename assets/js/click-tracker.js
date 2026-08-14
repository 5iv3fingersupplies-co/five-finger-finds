(function () {
  const KEY = "fiveFingerFindsAffiliateClicks";

  function readStore() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || "{}");
    } catch (_error) {
      return {};
    }
  }

  function writeStore(payload) {
    try {
      localStorage.setItem(KEY, JSON.stringify(payload));
    } catch (_error) {
      // Static hosting has no server-side log receiver. Local storage keeps this first-party and private.
    }
  }

  document.addEventListener("click", function (event) {
    const link = event.target.closest("a[data-affiliate]");
    if (!link) return;
    const store = readStore();
    const key = link.dataset.affiliate || "unknown";
    const now = new Date().toISOString().slice(0, 10);
    store[key] = store[key] || { total: 0, byDay: {} };
    store[key].total += 1;
    store[key].byDay[now] = (store[key].byDay[now] || 0) + 1;
    writeStore(store);
  });
})();
