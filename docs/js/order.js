/* The order form on the Order page.
 *
 * Without this script the form still works: the list of works opens as a plain
 * list of choices, and sending it shows Formspree's own thank-you page. This
 * adds three things on top: the work named in the address (?work=...) is chosen
 * in advance, the chosen work is shown in the closed list, and the message is
 * sent without leaving the page.
 */
(function () {
  "use strict";
  var form = document.querySelector("[data-order-form]");
  if (!form) return;

  var picker = form.querySelector(".work-picker");
  var current = picker.querySelector(".picker-current");
  var radios = picker.querySelectorAll('input[name="work"]');

  // show the chosen work, picture and title, in the list's closed state
  function showChoice() {
    var chosen = picker.querySelector('input[name="work"]:checked');
    if (!chosen) return;
    var item = chosen.closest(".picker-item");
    current.textContent = "";
    var thumb = item.querySelector(".picker-thumb");
    if (thumb && thumb.tagName === "IMG") {
      var img = thumb.cloneNode();
      img.loading = "eager";
      current.appendChild(img);
    }
    var title = document.createElement("span");
    title.textContent = item.querySelector(".picker-title").textContent;
    current.appendChild(title);
  }

  var wanted = new URLSearchParams(location.search).get("work");
  if (wanted) {
    radios.forEach(function (r) { if (r.dataset.id === wanted) r.checked = true; });
  }
  showChoice();

  radios.forEach(function (r) {
    r.addEventListener("change", function () {
      showChoice();
      picker.open = false;
      picker.querySelector("summary").focus();
    });
  });

  var status = form.querySelector(".form-status");
  var button = form.querySelector('button[type="submit"]');

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var label = button.textContent;
    button.disabled = true;
    button.textContent = button.dataset.sending;
    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { Accept: "application/json" }
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      form.reset();
      showChoice();
      status.textContent = status.dataset.thanks;
      status.hidden = false;
      button.textContent = label;
    }).catch(function () {
      status.textContent = status.dataset.error;
      status.hidden = false;
      button.disabled = false;
      button.textContent = label;
    });
  });
})();
