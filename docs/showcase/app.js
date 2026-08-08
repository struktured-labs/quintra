(() => {
  "use strict";

  const data = window.QUINTRA_SHOWCASE;
  if (!data) throw new Error("Missing generated Quintra showcase data");

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const gallery = $("#gallery");
  const empty = $("#empty");
  const filters = $("#filters");
  const search = $("#search");
  const stageFilter = $("#stage-filter");
  const behaviorFilter = $("#behavior-filter");
  const dialog = $("#lightbox");
  let view = "stages";
  let visibleEntries = [];
  let activeIndex = 0;

  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[character]);

  const pill = (label, value) => `<span class="pill">${escapeHtml(label)} <b>${escapeHtml(value)}</b></span>`;

  function initialize() {
    $("#cart-version").textContent = data.meta.version;
    $("#stage-count").textContent = String(data.meta.stageCount).padStart(2, "0");
    $("#boss-count").textContent = String(data.meta.bossCount).padStart(2, "0");
    $("#monster-count").textContent = data.meta.monsterCount;
    $("#rom-hash").textContent = `ROM ${data.meta.romSha256.slice(0, 12)}…`;

    data.stages.forEach(stage => stageFilter.insertAdjacentHTML(
      "beforeend", `<option value="${stage.id}">${String(stage.id).padStart(2, "0")} · ${escapeHtml(stage.name)}</option>`
    ));
    [...new Set(data.monsters.map(monster => monster.behavior))].sort().forEach(behavior => {
      behaviorFilter.insertAdjacentHTML("beforeend", `<option>${escapeHtml(behavior)}</option>`);
    });

    $$("[data-view]").forEach(button => button.addEventListener("click", () => setView(button.dataset.view)));
    $$("[data-view-jump]").forEach(button => button.addEventListener("click", () => {
      setView(button.dataset.viewJump);
      $(".archive").scrollIntoView({ behavior: "smooth", block: "start" });
    }));
    $$("[data-collage]").forEach(button => button.addEventListener("click", () => openCollage(button.dataset.collage)));
    [search, stageFilter, behaviorFilter].forEach(input => input.addEventListener("input", render));
    $("#random-monster").addEventListener("click", () => {
      setView("monsters");
      const monster = data.monsters[Math.floor(Math.random() * data.monsters.length)];
      const index = visibleEntries.findIndex(entry => entry.id === monster.id);
      openEntry(index >= 0 ? index : 0);
    });
    gallery.addEventListener("click", event => {
      const trigger = event.target.closest("[data-entry-index]");
      if (trigger) openEntry(Number(trigger.dataset.entryIndex));
    });
    $("#lightbox .close").addEventListener("click", () => dialog.close());
    $("#lightbox .previous").addEventListener("click", () => stepLightbox(-1));
    $("#lightbox .next").addEventListener("click", () => stepLightbox(1));
    dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
    document.addEventListener("keydown", event => {
      if (!dialog.open) return;
      if (event.key === "ArrowLeft") stepLightbox(-1);
      if (event.key === "ArrowRight") stepLightbox(1);
    });
    render();
  }

  function setView(next) {
    view = next;
    $$("[data-view]").forEach(button => button.setAttribute("aria-selected", String(button.dataset.view === view)));
    filters.hidden = view !== "monsters";
    render();
  }

  function render() {
    let entries = data[view];
    if (view === "monsters") {
      const query = search.value.trim().toLowerCase();
      const stage = stageFilter.value;
      const behavior = behaviorFilter.value;
      entries = entries.filter(monster => {
        const haystack = `${monster.name} ${monster.description} ${monster.behavior} ${monster.firstSeen}`.toLowerCase();
        return (!query || haystack.includes(query))
          && (stage === "all" || monster.stages.includes(Number(stage)))
          && (behavior === "all" || monster.behavior === behavior);
      });
    }
    visibleEntries = entries;
    gallery.classList.toggle("monster-grid", view === "monsters");
    gallery.innerHTML = entries.map((entry, index) => view === "monsters"
      ? monsterCard(entry, index)
      : standardCard(entry, index, view)).join("");
    empty.hidden = entries.length !== 0;
    $("#results-summary").textContent = `${entries.length} ${view === "bosses" ? "Colossi" : view}`;
  }

  function standardCard(entry, index, type) {
    const isBoss = type === "bosses";
    const kicker = isBoss ? `Stage ${entry.id} · ${entry.stage}` : `Stage ${String(entry.id).padStart(2, "0")} · ${entry.boss}`;
    const meta = isBoss
      ? pill("HP", entry.hp) + pill("DMG", entry.damage) + pill("MOVE", entry.movement)
      : pill("REGION", entry.id) + pill("BOSS", entry.boss);
    return `<article class="card" style="--accent:${entry.accent}">
      <button class="card-media" data-entry-index="${index}" aria-label="Open ${escapeHtml(entry.name)} capture">
        <img src="${entry.image}" alt="${escapeHtml(entry.name)} live cartridge capture" loading="lazy">
        <span class="card-index">${isBoss ? "COLOSSUS" : "REGION"} ${String(entry.id).padStart(2, "0")}</span>
      </button>
      <div class="card-body"><p class="card-kicker">${escapeHtml(kicker)}</p><h3>${escapeHtml(entry.name)}</h3>
      <p class="card-copy">${escapeHtml(entry.description)}</p><div class="pills">${meta}</div></div>
    </article>`;
  }

  function monsterCard(monster, index) {
    const weakness = monster.weakness.length ? monster.weakness.join(" + ") : "None";
    const accent = data.stages[monster.stages[0] - 1]?.accent || "#7ef0bc";
    return `<article class="card monster-card" style="--accent:${accent}">
      <button class="card-media" data-entry-index="${index}" aria-label="Open ${escapeHtml(monster.name)} field capture">
        <img src="${monster.focus}" alt="${escapeHtml(monster.name)} pixel sprite in its stage" loading="lazy">
        <span class="card-index">ID ${String(monster.id).padStart(2, "0")}</span>
      </button>
      <div class="card-body"><p class="card-kicker">${escapeHtml(monster.behavior)} · ${escapeHtml(monster.firstSeen)}</p>
      <h3>${escapeHtml(monster.name)}</h3><p class="card-copy">${escapeHtml(monster.description)}</p>
      <div class="pills">${pill("HP", monster.hp)}${pill("DMG", monster.damage)}${pill("SPD", monster.speed)}${pill("WEAK", weakness)}</div></div>
    </article>`;
  }

  function entryLightbox(entry) {
    if (view === "monsters") {
      return {
        image: entry.field, kicker: `Monster ${String(entry.id).padStart(2, "0")} · ${entry.behavior}`,
        title: entry.name, copy: entry.description,
        meta: [pill("HP", entry.hp), pill("Damage", entry.damage), pill("Speed", entry.speed),
          pill("Poise", entry.poise), pill("Weak", entry.weakness.join(" + ") || "None"), pill("First", entry.firstSeen)].join("")
      };
    }
    if (view === "bosses") {
      return { image: entry.image, kicker: `Stage ${entry.id} final Colossus · ${entry.stage}`,
        title: entry.name, copy: entry.description,
        meta: pill("HP cap", entry.hp) + pill("Damage", entry.damage) + pill("Movement", entry.movement) };
    }
    return { image: entry.image, kicker: `Region ${String(entry.id).padStart(2, "0")} · ${entry.boss}`,
      title: entry.name, copy: entry.description, meta: pill("Final boss", entry.boss) };
  }

  function openEntry(index) {
    if (!visibleEntries.length) return;
    activeIndex = Math.max(0, Math.min(index, visibleEntries.length - 1));
    const detail = entryLightbox(visibleEntries[activeIndex]);
    updateLightbox(detail);
    if (!dialog.open) dialog.showModal();
  }

  function openCollage(key) {
    const labels = {
      stages: ["Nine-region contact sheet", "Every stage", "One representative live field from each procedural dungeon."],
      bosses: ["Maximum-footprint atlas", "All nine Colossi", "The largest captured body pose from every final boss."],
      bossesAnimated: ["Two-second synchronized atlas", "All nine Colossi — animated", "Pursuit, bounce, lunge, blink, pulse, weave, and weak-point travel side by side."],
      monsters: ["Complete contact sheet", "All 33 monsters", "Every registered enemy silhouette in its correct dungeon palette and floor context."],
    };
    visibleEntries = [];
    const [kicker, title, copy] = labels[key];
    updateLightbox({ image: data.collages[key], kicker, title, copy, meta: pill("ROM", data.meta.version) });
    if (!dialog.open) dialog.showModal();
  }

  function updateLightbox(detail) {
    $("#lightbox-image").src = detail.image;
    $("#lightbox-image").alt = detail.title;
    $("#lightbox-kicker").textContent = detail.kicker;
    $("#lightbox-title").textContent = detail.title;
    $("#lightbox-copy").textContent = detail.copy;
    $("#lightbox-meta").innerHTML = detail.meta;
    $$("#lightbox .step").forEach(button => button.hidden = visibleEntries.length < 2);
  }

  function stepLightbox(delta) {
    if (visibleEntries.length < 2) return;
    activeIndex = (activeIndex + delta + visibleEntries.length) % visibleEntries.length;
    updateLightbox(entryLightbox(visibleEntries[activeIndex]));
  }

  initialize();
})();
