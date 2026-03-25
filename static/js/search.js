"use strict";

(function () {
  const input = document.getElementById("search-input");
  const findBtn = document.getElementById("find-btn");
  const detailBox = document.getElementById("player-detail");

  if (!input) return;

  // Hide the no-JS results list if JS is available
  const noJsList = document.getElementById("results-list");
  if (noJsList) noJsList.hidden = true;

  // Convert the form to not submit on Enter (we handle it ourselves)
  const form = document.getElementById("search-form");
  form.addEventListener("submit", (e) => e.preventDefault());

  // --- Dropdown state ---
  let dropdown = null;
  let results = [];
  let selectedIndex = -1;
  let selectedPlayer = null;

  // --- Debounce ---
  let debounceTimer = null;
  function debounce(fn, ms) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, ms);
  }

  // --- Dropdown rendering ---
  function createDropdown() {
    const el = document.createElement("ul");
    el.className = "search-dropdown";
    el.setAttribute("role", "listbox");
    input.parentNode.insertBefore(el, input.nextSibling);
    return el;
  }

  function renderDropdown(players) {
    results = players;
    selectedIndex = -1;

    if (!dropdown) dropdown = createDropdown();

    dropdown.innerHTML = "";

    if (players.length === 0) {
      closeDropdown();
      return;
    }

    players.forEach((player, i) => {
      const li = document.createElement("li");
      li.textContent = player.name;
      li.setAttribute("role", "option");
      li.dataset.index = i;
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        selectPlayer(i);
      });
      dropdown.appendChild(li);
    });

    dropdown.hidden = false;
  }

  function closeDropdown() {
    if (dropdown) dropdown.hidden = true;
    selectedIndex = -1;
  }

  function highlightItem(index) {
    if (!dropdown) return;
    const items = dropdown.querySelectorAll("li");
    items.forEach((li, i) => li.classList.toggle("highlighted", i === index));
    selectedIndex = index;
  }

  // --- Player selection ---
  function selectPlayer(index) {
    const player = results[index];
    if (!player) return;
    selectedPlayer = player;
    input.value = player.name;
    closeDropdown();
    showDetail(player);
  }

  function showDetail(player) {
    detailBox.hidden = false;
    detailBox.innerHTML = `
      <h2>${escHtml(player.name)}</h2>
      <table class="detail-table">
        <tr><th>Player Number</th><td>#${escHtml(String(player.player_number))}</td></tr>
        <tr><th>Current Rating</th><td>${player.current_rating !== null ? escHtml(String(player.current_rating)) : "No rating recorded"}</td></tr>
        ${player.rating_date ? `<tr><th>Rating Date</th><td>${escHtml(player.rating_date)}</td></tr>` : ""}
      </table>`;
  }

  function escHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // --- Search fetch ---
  async function fetchResults(query) {
    if (!query) {
      closeDropdown();
      return;
    }
    try {
      const res = await fetch(`/search/?q=${encodeURIComponent(query)}`, {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) return;
      const players = await res.json();
      renderDropdown(players);
    } catch (_) {
      // Network error — silently ignore, no-JS form still works
    }
  }

  // --- Event listeners ---
  input.addEventListener("input", () => {
    debounce(() => fetchResults(input.value.trim()), 300);
  });

  input.addEventListener("keydown", (e) => {
    if (!dropdown || dropdown.hidden) return;
    const items = dropdown.querySelectorAll("li");

    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlightItem(Math.min(selectedIndex + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlightItem(Math.max(selectedIndex - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex >= 0) selectPlayer(selectedIndex);
    } else if (e.key === "Escape") {
      closeDropdown();
    }
  });

  document.addEventListener("click", (e) => {
    if (!dropdown) return;
    if (!dropdown.contains(e.target) && e.target !== input) closeDropdown();
  });

  findBtn.addEventListener("click", () => {
    if (selectedPlayer) {
      showDetail(selectedPlayer);
    } else if (input.value.trim()) {
      // Trigger a fresh search and show first result
      fetchResults(input.value.trim()).then(() => {
        if (results.length > 0) selectPlayer(0);
      });
    }
  });
})();
