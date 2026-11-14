(function () {
  const fieldset = document.querySelector("[data-poll-options]");
  if (!fieldset) return;

  const MIN = 2;
  const rows = Array.from(fieldset.querySelectorAll("[data-option-row]"));
  const inputs = rows.map((row) => row.querySelector("input"));
  const removeButtons = rows.map((row) => row.querySelector("[data-remove-option]"));
  const addButton = fieldset.querySelector("[data-add-option]");
  const MAX = rows.length;

  const lastFilled = inputs.reduce((last, input, index) => (input.value.trim() ? index + 1 : last), 0);
  let count = Math.max(MIN, lastFilled);

  function render() {
    rows.forEach((row, index) => {
      row.hidden = index >= count;
      removeButtons[index].hidden = count <= MIN;
    });
    addButton.hidden = false;
    addButton.disabled = count >= MAX;
  }

  addButton.addEventListener("click", () => {
    if (count >= MAX) return;
    count += 1;
    render();
    inputs[count - 1].focus();
  });

  removeButtons.forEach((button, index) => {
    button.addEventListener("click", () => {
      if (count <= MIN) return;
      const values = inputs.slice(0, count).map((input) => input.value);
      values.splice(index, 1);
      count -= 1;
      inputs.forEach((input, i) => {
        input.value = values[i] || "";
      });
      render();
      inputs[Math.min(index, count - 1)].focus();
    });
  });

  render();
})();
