/*
 * Gallery filter — narrows the thumbnails and the full list to one category,
 * year and/or tag. Progressive enhancement: the form ships hidden and is only
 * revealed here, so without this script the gallery shows every work.
 *
 * Each work carries its filter values as data-* attributes written by build.py:
 *   data-cats  space-separated categories, e.g. "painting painting-large"
 *   data-year  the year, or empty
 *   data-tags  tag keys separated by "|"
 */
(function () {
  "use strict";

  var form = document.querySelector("form.filters");
  if (!form) return;

  var works = Array.prototype.slice.call(
    document.querySelectorAll(".thumb[data-cats], .painting[data-cats]"));
  var selects = Array.prototype.slice.call(form.querySelectorAll("select"));
  var countEl = form.querySelector(".filter-count");
  var clearBtn = form.querySelector(".filter-clear");
  var noneEl = document.querySelector(".filter-none");
  var total = Number(form.getAttribute("data-total")) || 0;
  var showingText = form.getAttribute("data-showing") || "{n} / {total}";

  function matches(el, choice) {
    if (choice.category &&
        (el.getAttribute("data-cats") || "").split(" ").indexOf(choice.category) < 0) return false;
    if (choice.year && el.getAttribute("data-year") !== choice.year) return false;
    if (choice.tag &&
        (el.getAttribute("data-tags") || "").split("|").indexOf(choice.tag) < 0) return false;
    return true;
  }

  function apply() {
    var choice = {};
    var active = false;
    selects.forEach(function (s) {
      choice[s.name] = s.value;
      if (s.value) active = true;
    });

    var shown = 0;
    works.forEach(function (el) {
      var ok = matches(el, choice);
      el.hidden = !ok;
      // each work appears twice (thumbnail and list entry); count it once
      if (ok && el.classList.contains("painting")) shown++;
    });

    countEl.textContent = active
      ? showingText.replace("{n}", shown).replace("{total}", total)
      : "";
    clearBtn.hidden = !active;
    if (noneEl) noneEl.hidden = shown > 0;
  }

  selects.forEach(function (s) { s.addEventListener("change", apply); });
  // the reset button restores every menu to "all"; apply once that has happened
  form.addEventListener("reset", function () { setTimeout(apply, 0); });
  form.addEventListener("submit", function (e) { e.preventDefault(); });

  form.hidden = false;
  apply();
})();
