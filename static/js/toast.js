(function () {
  const DURATION_MS = 3000;
  const region = document.querySelector("[data-toast-region]");
  if (!region) return;

  function dismissLater(toast) {
    setTimeout(() => toast.remove(), DURATION_MS);
  }

  region.querySelectorAll("[data-toast]").forEach(dismissLater);

  window.showToast = function (text) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.dataset.toast = "";
    toast.textContent = text;
    region.append(toast);
    dismissLater(toast);
  };
})();
