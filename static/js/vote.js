(function () {
  const form = document.querySelector("[data-vote-form]");
  if (!form) return;

  const poll = document.querySelector("[data-poll]");
  const resultsRegion = poll.querySelector("[data-results]");
  const submitButton = form.querySelector('button[type="submit"]');
  const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
  const toast = (text) => window.showToast && window.showToast(text);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.querySelector('input[name="option"]:checked')) {
      toast("Bir seçenek seç.");
      return;
    }

    submitButton.disabled = true;
    let response;
    let data;
    try {
      response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: {
          "X-CSRFToken": csrfToken,
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
      });
      data = await response.json();
    } catch (error) {
      toast("Bağlantı kurulamadı. Tekrar dene.");
      submitButton.disabled = false;
      return;
    }

    if (!response.ok) toast(data.message || "Oy kaydedilemedi.");
    if (data.results_visible) {
      showResults(data);
    } else {
      submitButton.disabled = false;
    }
  });

  function showResults(data) {
    const list = document.createElement("ul");
    list.className = "option-list";
    const fills = [];

    data.options.forEach((option) => {
      const voted = option.id === data.voted_option_id;
      const row = document.createElement("li");
      row.className = `option-row opt-${option.position} option-row--result${voted ? " option-row--voted" : ""}`;

      const fill = document.createElement("span");
      fill.className = "option-row__fill";
      fill.style.width = "0%";
      fills.push([fill, option.percent]);

      const text = document.createElement("span");
      text.className = "option-row__text";
      text.textContent = option.text;
      if (voted) {
        const check = document.createElement("span");
        check.className = "option-row__check";
        check.textContent = " ✓";
        const label = document.createElement("span");
        label.className = "visually-hidden";
        label.textContent = " (senin oyun)";
        check.append(label);
        text.append(check);
      }

      const percent = document.createElement("span");
      percent.className = "option-row__percent";
      percent.textContent = `%${option.percent}`;

      row.append(fill, text, percent);
      list.append(row);
    });

    form.replaceWith(list);
    poll.querySelector("[data-results-hint]")?.remove();
    updateBar(data);
    updateBadge(data.badge);
    updateTotal(data.total);

    // Force a layout at width 0 so the CSS transition runs from empty to the real value.
    void list.offsetWidth;
    fills.forEach(([fill, value]) => (fill.style.width = `${value}%`));
    resultsRegion.focus({ preventScroll: true });
  }

  function updateBar(data) {
    const bar = poll.querySelector(".decision-bar");
    if (!bar || !data.total) return;
    bar.classList.remove("decision-bar--neutral");
    const segments = bar.querySelectorAll(".decision-bar__segment");
    data.options.forEach((option, index) => {
      if (segments[index]) segments[index].style.flexGrow = option.count;
    });
    bar.setAttribute("aria-label", data.options.map((o) => `${o.text} %${o.percent}`).join(", "));
  }

  function updateBadge(badge) {
    const element = poll.querySelector(".badge");
    if (!element) return;
    element.className = `badge badge--${badge.kind}`;
    element.textContent = badge.text;
  }

  function updateTotal(total) {
    const element = poll.querySelector("[data-total-votes]");
    if (!element) return;
    element.textContent = total ? `${total.toLocaleString("tr-TR")} kişi oy verdi` : "Henüz oy yok";
  }
})();
