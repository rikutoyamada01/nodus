/* Nodus Quantitative Interactive Controls (CSP-safe external script) */
(function () {
  "use strict";

  function initIndexFilters() {
    var filterBtns = document.querySelectorAll(".filter-btn[data-filter]");
    var searchInput = document.getElementById("datasetSearch");
    var cards = document.querySelectorAll(".article-card[data-category]");
    if (!filterBtns.length && !searchInput) return;

    var activeFilter = "all";

    function applyFilter() {
      var query = searchInput ? searchInput.value.trim().toLowerCase() : "";
      cards.forEach(function (card) {
        var cat = card.getAttribute("data-category") || "";
        var origin = card.getAttribute("data-origin") || "community";
        var catMatch =
          activeFilter === "all" ||
          (activeFilter === "first_party" && (origin === "first_party" || origin === "hybrid")) ||
          cat === activeFilter;
        var textMatch = !query || card.textContent.toLowerCase().indexOf(query) !== -1;
        if (catMatch && textMatch) {
          card.removeAttribute("hidden");
        } else {
          card.setAttribute("hidden", "hidden");
        }
      });
      var empty = document.getElementById("searchEmpty");
      if (empty) empty.hidden = Array.prototype.some.call(cards, function (card) { return !card.hidden; });
    }

    filterBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        activeFilter = btn.getAttribute("data-filter") || "all";
        filterBtns.forEach(function (b) {
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        applyFilter();
      });
    });

    if (searchInput) {
      searchInput.addEventListener("input", applyFilter);
    }
  }

  function extractSortNumber(cell) {
    if (!cell) return NaN;
    var attrVal = cell.getAttribute("data-sort-value");
    if (attrVal !== null && attrVal !== "") {
      var parsed = parseFloat(attrVal);
      if (!isNaN(parsed)) return parsed;
    }
    var text = cell.textContent.trim();
    var m = text.match(/[-+]?(?:\d+(?:,\d{3})+|\d+)(?:\.\d+)?/);
    return m ? parseFloat(m[0].replace(/,/g, "")) : NaN;
  }

  function initTableSorting() {
    var tables = document.querySelectorAll("table.data-table");
    tables.forEach(function (table) {
      var headers = table.querySelectorAll("thead th");
      var tbody = table.querySelector("tbody");
      if (!tbody) return;

      headers.forEach(function (th, colIdx) {
        var btn = th.querySelector(".th-sort-btn");
        if (!btn) return;
        btn.addEventListener("click", function () {
          var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
          var asc = th.getAttribute("aria-sort") !== "ascending";
          headers.forEach(function (h) {
            h.setAttribute("aria-sort", "none");
          });
          th.setAttribute("aria-sort", asc ? "ascending" : "descending");

          rows.sort(function (a, b) {
            var cellA = a.children[colIdx];
            var cellB = b.children[colIdx];
            var numA = extractSortNumber(cellA);
            var numB = extractSortNumber(cellB);
            if (!isNaN(numA) && !isNaN(numB) && numA !== numB) {
              return asc ? numA - numB : numB - numA;
            }
            var txtA = cellA ? cellA.textContent.trim() : "";
            var txtB = cellB ? cellB.textContent.trim() : "";
            return asc ? txtA.localeCompare(txtB, "ja") : txtB.localeCompare(txtA, "ja");
          });

          rows.forEach(function (r) { tbody.appendChild(r); });
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initIndexFilters();
      initTableSorting();
    });
  } else {
    initIndexFilters();
    initTableSorting();
  }
})();
