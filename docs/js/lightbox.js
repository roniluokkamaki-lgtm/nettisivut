/*
 * Gallery lightbox — the one dynamic piece of this site.
 * Progressive enhancement: every trigger element is a real <a> with a real
 * href (a per-painting section anchor or the full-size image itself), so
 * with this script disabled or failing, the page still works via normal
 * navigation. With it, clicking opens a fitted overlay with prev/next,
 * keyboard control and an optional full-resolution zoom.
 */
(function () {
  "use strict";

  var TRIGGER_SELECTOR = ".thumb[data-full], .painting-img-link[data-full], .btn-view[data-full]";

  // UI strings for the current language, written into the page by build.py.
  // The English defaults keep the viewer usable if that block is ever missing.
  var S = {
    close: "Close", prev: "Previous painting", next: "Next painting",
    zoom_on: "zoom: on", zoom_off: "zoom: off", dialog: "Painting viewer"
  };
  try {
    var el = document.getElementById("lb-strings");
    if (el) {
      var parsed = JSON.parse(el.textContent);
      for (var k in parsed) { if (parsed[k]) S[k] = parsed[k]; }
    }
  } catch (e) { /* keep the defaults */ }

  var triggers = Array.prototype.slice.call(document.querySelectorAll(TRIGGER_SELECTOR));
  if (!triggers.length) return;

  // Build the navigable item list from the full-list section only — each
  // painting appears there exactly once, in gallery order — so prev/next
  // moves through the whole collection regardless of which element (thumb,
  // image, or "View closer" link) was clicked to open it.
  var items = Array.prototype.slice
    .call(document.querySelectorAll(".painting-img-link[data-full]"))
    .map(function (el) { return readItem(el); });

  if (!items.length) return;

  var indexById = {};
  items.forEach(function (it, i) { indexById[it.id] = i; });

  function readItem(el) {
    return {
      id: el.getAttribute("data-id"),
      full: el.getAttribute("data-full"),
      zoom: el.getAttribute("data-zoom"),
      fullW: el.getAttribute("data-full-w"),
      fullH: el.getAttribute("data-full-h"),
      title: el.getAttribute("data-title") || "",
      caption: el.getAttribute("data-caption") || "",
    };
  }

  // ---------------------------------------------------------------- build

  var root = document.createElement("div");
  root.className = "lightbox";
  root.hidden = true;
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.setAttribute("aria-label", S.dialog);

  root.innerHTML =
    '<div class="lightbox-controls">' +
      '<button type="button" class="lightbox-zoom" aria-pressed="false">' + S.zoom_off + "</button>" +
      '<button type="button" class="lightbox-close" aria-label="' + S.close + '">&times; ' + S.close + "</button>" +
    "</div>" +
    '<button type="button" class="lightbox-nav lightbox-prev" aria-label="' + S.prev + '">&#8249;</button>' +
    '<button type="button" class="lightbox-nav lightbox-next" aria-label="' + S.next + '">&#8250;</button>' +
    '<div class="lightbox-stage"><img alt=""></div>' +
    '<p class="lightbox-caption"><span class="lightbox-title"></span><span class="lightbox-meta"></span></p>';

  document.body.appendChild(root);

  var stage = root.querySelector(".lightbox-stage");
  var img = root.querySelector(".lightbox-stage img");
  var titleEl = root.querySelector(".lightbox-title");
  var metaEl = root.querySelector(".lightbox-meta");
  var btnClose = root.querySelector(".lightbox-close");
  var btnPrev = root.querySelector(".lightbox-prev");
  var btnNext = root.querySelector(".lightbox-next");
  var btnZoom = root.querySelector(".lightbox-zoom");

  var current = -1;
  var zoomed = false;
  var lastFocused = null;

  function preload(src) {
    if (!src) return;
    var im = new Image();
    im.src = src;
  }

  function render() {
    var it = items[current];
    if (!it) return;
    zoomed = false;
    stage.classList.remove("is-zoomed");
    btnZoom.textContent = S.zoom_off;
    btnZoom.setAttribute("aria-pressed", "false");
    img.src = it.full;
    img.alt = it.title;
    if (it.fullW) img.setAttribute("width", it.fullW);
    if (it.fullH) img.setAttribute("height", it.fullH);
    titleEl.textContent = it.title;
    metaEl.innerHTML = it.caption ? " &mdash; " + it.caption : "";

    // preload neighbours
    preload(items[(current + 1) % items.length].full);
    preload(items[(current - 1 + items.length) % items.length].full);
  }

  function open(id) {
    var i = indexById[id];
    if (i === undefined) return;
    current = i;
    lastFocused = document.activeElement;
    render();
    root.hidden = false;
    document.body.style.overflow = "hidden";
    btnClose.focus();
    document.addEventListener("keydown", onKeydown, true);
  }

  function close() {
    root.hidden = true;
    document.body.style.overflow = "";
    document.removeEventListener("keydown", onKeydown, true);
    if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
  }

  function step(delta) {
    current = (current + delta + items.length) % items.length;
    render();
  }

  function toggleZoom() {
    var it = items[current];
    if (!it || !it.zoom) return;
    zoomed = !zoomed;
    stage.classList.toggle("is-zoomed", zoomed);
    img.src = zoomed ? it.zoom : it.full;
    if (zoomed) {
      img.removeAttribute("width");
      img.removeAttribute("height");
      stage.scrollLeft = 0;
      stage.scrollTop = 0;
    } else if (it.fullW) {
      img.setAttribute("width", it.fullW);
      img.setAttribute("height", it.fullH);
    }
    btnZoom.textContent = zoomed ? S.zoom_on : S.zoom_off;
    btnZoom.setAttribute("aria-pressed", String(zoomed));
  }

  var FOCUSABLE = 'button, [href], [tabindex]:not([tabindex="-1"])';

  function onKeydown(e) {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key === "ArrowRight") { e.preventDefault(); step(1); return; }
    if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); return; }
    if (e.key === "Tab") {
      var focusable = Array.prototype.slice.call(root.querySelectorAll(FOCUSABLE));
      if (!focusable.length) return;
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }

  triggers.forEach(function (el) {
    el.addEventListener("click", function (e) {
      var id = el.getAttribute("data-id");
      if (!id || indexById[id] === undefined) return; // let the real href work
      e.preventDefault();
      open(id);
    });
  });

  btnClose.addEventListener("click", close);
  btnPrev.addEventListener("click", function () { step(-1); });
  btnNext.addEventListener("click", function () { step(1); });
  btnZoom.addEventListener("click", toggleZoom);
  root.addEventListener("click", function (e) {
    if (e.target === root) close();
  });
})();
