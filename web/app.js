(() => {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${proto}://${location.host}/ws`;

  let ws = null;
  let token = null;
  let hostToken = null;
  let state = null;
  let uniquePick = null;
  let deckSize = 10;
  let theme = null;
  const query = new URLSearchParams(location.search);
  const queryJoinCode = query.get("join") || "";
  const requestedJoinCode = /^[0-9]{6}$/.test(queryJoinCode) ? queryJoinCode : "";
  const requestedPlayerName = query.get("name");

  const UNIQUE_META = {
    steal: { label: "Steal", palette: "steal", flag: "steals", can: "steal" },
    heavy: { label: "Heavy Hit", palette: "heavy_hit", flag: "heavy_hit", can: "heavy" },
    shield: { label: "Shield", palette: "selected", flag: "shields", can: "shield" },
    poison: { label: "Poison", palette: "poison", flag: "poisons", can: "poison" },
    exordia: { label: "Exodia", palette: "selected", flag: "exordia", can: "exordia", zeroBudget: true },
    cloak: { label: "Cloak", palette: "selected", flag: "cloak", can: "cloak", zeroBudget: true },
    lava: { label: "Floor is Lava", palette: "selected", flag: "lava", can: "lava", zeroBudget: true },
    joker: { label: "Joker", palette: "selected", flag: "joker", can: "joker", zeroBudget: true },
    reaper: { label: "Reaper", palette: "selected", flag: "reaper", can: "reaper", zeroBudget: true },
    vampire: { label: "Vampire", palette: "poison", flag: "vampire", can: "vampire" },
    cure: { label: "Cure", palette: "selected", flag: "cure", can: "cure", zeroBudget: true },
  };

  const $ = (id) => document.getElementById(id);
  const screens = ["home", "lobby", "craft", "play", "over"];

  const matchSize = $("match-size");
  for (let count = 5; count <= 100; count += 1) {
    const option = document.createElement("option");
    option.value = String(count);
    option.textContent = `${count} players`;
    matchSize.appendChild(option);
  }

  function show(name) {
    screens.forEach((s) => {
      $(`screen-${s}`).classList.toggle("hidden", s !== name);
    });
  }

  function toast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 3500);
  }

  function send(payload) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      toast("Not connected");
      return;
    }
    ws.send(JSON.stringify(payload));
  }

  function hudChipSize(player) {
    const ref = Math.max(Number(player.max_hp) || 1, 1);
    let factor = 0.78 + 0.2 * Math.log10(ref + 20);
    factor = Math.max(0.82, Math.min(1.7, factor));
    const hpText = player.alive ? `${player.hp}/${player.max_hp} HP` : "OUT";
    const charW = Math.max(8, Math.round(9.5 * factor));
    let width = Math.max(Math.round(152 * factor), hpText.length * charW + 28);
    let height = Math.max(Math.round(72 * factor), Math.round(64 * factor));
    if (
      player.alive &&
      (player.shield ||
        player.poisoned ||
        player.reaper_marked ||
        player.vampire_marked ||
        player.cloak_charges > 0)
    ) {
      height = Math.max(height, Math.round(80 * factor));
    }
    return [width - (width % 2), height - (height % 2)];
  }

  function reloadGameFont(family) {
    const name = family || "CrashOutGame";
    let el = document.getElementById("crash-font");
    if (el) el.remove();
    el = document.createElement("style");
    el.id = "crash-font";
    el.textContent = `
      @font-face {
        font-family: "${name}";
        src: url("/api/font?t=${Date.now()}") format("truetype");
        font-display: swap;
      }
      @font-face {
        font-family: "CrashOutGame";
        src: url("/api/font?t=${Date.now()}") format("truetype");
        font-display: swap;
      }
    `;
    document.head.appendChild(el);
    return document.fonts.load(`16px "${name}"`).catch(() => {});
  }

  function applyWallpaper() {
    const w = Math.min(640, Math.max(320, Math.floor(window.innerWidth / 2)));
    const h = Math.min(360, Math.max(180, Math.floor(window.innerHeight / 2)));
    document.body.style.backgroundImage = `url("/api/wallpaper?w=${w}&h=${h}&t=${Date.now()}")`;
  }

  function ensureCanvas(host, w, h) {
    let c = host.tagName === "CANVAS" ? host : host.querySelector("canvas");
    if (!c) {
      c = document.createElement("canvas");
      host.appendChild(c);
    }
    if (c.width !== w) c.width = w;
    if (c.height !== h) c.height = h;
    return c;
  }

  function paintArtButton(btn) {
    if (!theme || !window.PixelArt) return;
    const rect = btn.getBoundingClientRect();
    const w = Math.max(120, Math.floor(rect.width) || 200);
    const h = Math.max(44, Math.floor(rect.height) || 52);
    const canvas = ensureCanvas(btn, w, h);
    PixelArt.drawArtButton(
      canvas,
      theme,
      btn.dataset.palette || "normal",
      btn.dataset.label || "",
      btn.matches(":hover")
    );
  }

  function paintChrome() {
    if (!theme || !window.PixelArt) return;
    document.querySelectorAll(".art-btn").forEach(paintArtButton);
    paintUniquePicks();
  }

  function paintUniquePicks() {
    if (!theme || !window.PixelArt) return;
    const craft = state?.craft;
    Object.keys(UNIQUE_META).forEach((key) => {
      const meta = UNIQUE_META[key];
      const canvas = $(`pick-${key}`);
      if (!canvas) return;
      const locked = craft ? !craft[`can_${meta.can}`] : false;
      canvas.classList.toggle("disabled", locked);
      canvas.classList.toggle("on", uniquePick === key);
      PixelArt.drawUniquePick(
        canvas,
        theme,
        meta.palette,
        meta.label,
        uniquePick === key,
        locked,
        canvas.matches(":hover")
      );
    });
  }

  function applyThemePayload(data) {
    theme = data.theme;
    if (window.PixelArt) PixelArt.applyThemeCss(theme);
    const sel = $("theme-pick");
    const names = data.names || [];
    const current = sel.value;
    if (sel.options.length !== names.length) {
      sel.innerHTML = names
        .map((n) => `<option value="${escapeHtml(n)}">${escapeHtml(n)}</option>`)
        .join("");
    }
    if (names.includes(theme.name)) sel.value = theme.name;
    else if (current) sel.value = current;
    $("theme-label").textContent = theme.name;
    applyWallpaper();
    reloadGameFont(theme.font_family).then(() => {
      paintChrome();
      if (state) render();
    });
    paintChrome();
  }

  async function loadTheme() {
    const res = await fetch("/api/theme");
    applyThemePayload(await res.json());
  }

  async function setTheme(action, name) {
    const res = await fetch("/api/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, name }),
    });
    applyThemePayload(await res.json());
  }

  function setupRulesText() {
    const n = deckSize;
    const lines = [
      `Max HP = 2× starting. Last card (${n}) = Mercy (25 heal any target).`,
      `Deck size 3–20.`,
      "Special cards: Steal, Heavy Hit, Shield, Poison, Exodia, Cloak, Floor is Lava, Joker, Reaper, Vampire, and Cure.",
    ];
    if (n >= 12) {
      lines.push("12+ cards: duplicate types allowed (uniques still one each).");
    } else {
      lines.push("Under 12 cards: each type is unique (duplicates unlock at 12+).");
    }
    const match = Number($("match-size").value);
    if (match === 1) {
      lines.push("Vs bot: Steal is disabled.");
    }
    $("setup-rules").textContent = lines.join("\n");
  }

  function syncDeckLabel() {
    $("setup-deck").value = String(deckSize);
    $("setup-deck-label").textContent = String(deckSize);
    setupRulesText();
  }

  function connect() {
    $("connection").textContent = "Connecting…";
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      $("connection").textContent = "Ready";
      if (requestedJoinCode) {
        send({
          action: "join",
          name: requestedPlayerName || "Player",
          code: requestedJoinCode,
        });
      }
    };
    ws.onclose = () => {
      $("connection").textContent = "Disconnected — refresh to retry";
    };
    ws.onerror = () => toast("WebSocket error");
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "error") {
        toast(msg.message || "Error");
        return;
      }
      if (msg.type === "joined") {
        token = msg.token;
        if (msg.host_token) hostToken = msg.host_token;
        state = msg.state;
        render();
        return;
      }
      if (msg.type === "state") {
        state = msg.state;
        render();
      }
    };
  }

  function renderCard(c, { playable } = {}) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "card-face";
    el.setAttribute("aria-label", `${c.name || "Card"}. ${c.effect || "No description available."}`);
    const canvas = document.createElement("canvas");
    canvas.width = 120;
    canvas.height = 168;
    el.appendChild(canvas);
    if (theme && window.PixelArt) PixelArt.drawCardFace(canvas, theme, c, {});
    el.onmouseenter = (event) => {
      if (theme && window.PixelArt) {
        PixelArt.drawCardFace(canvas, theme, c, { hover: true });
      }
      showCardTooltip(c, event.clientX, event.clientY);
    };
    el.onmousemove = (event) => positionCardTooltip(event.clientX, event.clientY);
    el.onmouseleave = () => {
      if (theme && window.PixelArt) PixelArt.drawCardFace(canvas, theme, c, {});
      hideCardTooltip();
    };
    el.onfocus = () => {
      const rect = el.getBoundingClientRect();
      showCardTooltip(c, rect.right, rect.top + rect.height / 2);
    };
    el.onblur = hideCardTooltip;
    if (playable && !c.cooling) {
      el.onclick = () => send({ action: "play_card", card_id: c.id });
    } else {
      el.disabled = true;
    }
    return el;
  }

  function showCardTooltip(card, x, y) {
    $("card-tooltip-title").textContent = card.name || "Card";
    $("card-tooltip-description").textContent =
      card.effect || "No description available.";
    $("card-tooltip").classList.remove("hidden");
    $("card-tooltip").setAttribute("aria-hidden", "false");
    positionCardTooltip(x, y);
  }

  function positionCardTooltip(x, y) {
    const tooltip = $("card-tooltip");
    if (tooltip.classList.contains("hidden")) return;
    const gap = 14;
    const rect = tooltip.getBoundingClientRect();
    const left =
      x + gap + rect.width <= window.innerWidth
        ? x + gap
        : Math.max(gap, x - rect.width - gap);
    const top =
      y + gap + rect.height <= window.innerHeight
        ? y + gap
        : Math.max(gap, y - rect.height - gap);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  }

  function hideCardTooltip() {
    $("card-tooltip").classList.add("hidden");
    $("card-tooltip").setAttribute("aria-hidden", "true");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function craftBudget() {
    if (!state?.craft) return state?.settings?.power_points || 100;
    const pp = state.settings.power_points;
    if (UNIQUE_META[uniquePick]?.zeroBudget) return 0;
    if (uniquePick === "steal") return state.craft.budget_steal;
    if (uniquePick === "shield") return state.craft.budget_shield;
    return pp;
  }

  function updateSplitPreview() {
    const budget = craftBudget();
    const slider = $("dmg-slider");
    slider.max = String(budget);
    let dmg = Number(slider.value);
    if (dmg > budget) {
      dmg = budget;
      slider.value = String(budget);
    }
    if (uniquePick === "shield") {
      dmg = 0;
      slider.value = "0";
      slider.disabled = true;
    } else if (uniquePick === "poison") {
      dmg = budget;
      slider.value = String(budget);
      slider.disabled = true;
    } else if (budget === 0) {
      dmg = 0;
      slider.value = "0";
      slider.disabled = true;
    } else {
      slider.disabled = false;
    }
    const heal = budget - dmg;
    $("split-preview").textContent = `${dmg} damage / ${heal} heal (budget ${budget})`;
  }

  function syncUniquePicks(craft) {
    Object.keys(UNIQUE_META).forEach((key) => {
      if (!craft[`can_${UNIQUE_META[key].can}`] && uniquePick === key) {
        uniquePick = null;
      }
    });
    paintUniquePicks();
  }

  function hostPayload() {
    const count = Number($("match-size").value);
    return {
      action: "create",
      name: $("name").value || "Player",
      vs_bot: count === 1,
      player_count: count,
      starting_hp: Number($("setup-hp").value),
      power_points: Number($("setup-pp").value),
      deck_size: deckSize,
    };
  }

  function render() {
    if (!state) {
      show("home");
      paintChrome();
      return;
    }
    if (state.phase === "lobby") {
      show("lobby");
      $("lobby-code").textContent = state.code;
      const list = $("seat-list");
      list.innerHTML = "";
      state.seats.forEach((s) => {
        const li = document.createElement("li");
        const label = s.is_bot
          ? `${escapeHtml(s.name || "bot")} (AI)`
          : s.filled
            ? escapeHtml(s.name)
            : "waiting…";
        li.innerHTML = `<span>Seat ${s.seat + 1}</span><span>${label}</span>`;
        list.appendChild(li);
      });
      const startBtn = $("btn-start-craft");
      startBtn.classList.toggle("hidden", !hostToken);
      if (state.vs_bot) {
        $("lobby-hint").textContent = "Vs bot — press Start Card Lab when ready.";
      } else if (hostToken) {
        $("lobby-hint").textContent =
          "Share the room code. When everyone has joined, start Card Lab.";
      } else {
        $("lobby-hint").textContent = "Waiting for host to start Card Lab…";
      }
      paintChrome();
      return;
    }

    if (state.phase === "craft") {
      show("craft");
      const c = state.craft;
      if (!c) return;
      $("craft-slot").textContent = c.ready
        ? "READY"
        : `Card ${c.slot} / ${state.settings.deck_size}`;
      $("craft-rules").textContent = [
        state.settings.allow_duplicates
          ? "12+ deck: duplicate types allowed. Uniques still one each."
          : "Under 12 cards: each type unique. Uniques one each.",
        state.vs_bot ? "Vs bot: Steal disabled." : "",
      ]
        .filter(Boolean)
        .join(" ");
      $("craft-form").classList.toggle("hidden", !!c.ready);
      $("btn-finish-craft").classList.toggle("hidden", c.ready || !c.done_craftable);
      $("btn-craft").classList.toggle("hidden", c.ready || c.done_craftable);
      $("unique-picks").classList.toggle("hidden", !!(c.ready || c.done_craftable));
      const sliderLabel = $("dmg-slider").closest("label");
      if (sliderLabel) {
        sliderLabel.classList.toggle("hidden", !!(c.ready || c.done_craftable));
      }
      $("split-preview").classList.toggle("hidden", !!(c.ready || c.done_craftable));
      $("craft-waiting").classList.toggle("hidden", !c.ready);
      $("craft-waiting").textContent = state.vs_bot
        ? "Starting match vs bot…"
        : "Waiting for other players…";
      syncUniquePicks(c);
      updateSplitPreview();
      const deck = $("craft-deck");
      deck.innerHTML = "";
      (state.your_deck || []).forEach((card) => deck.appendChild(renderCard(card)));
      paintChrome();
      return;
    }

    if (state.phase === "play") {
      show("play");
      const hud = $("hud");
      hud.innerHTML = "";
      state.players.forEach((p) => {
        const [w, h] = hudChipSize(p);
        const canvas = document.createElement("canvas");
        canvas.className = "hud-chip";
        canvas.width = w;
        canvas.height = h;
        canvas.title = [
          p.shield ? "Shield" : "",
          p.poisoned ? "Poisoned" : "",
          p.reaper_marked ? "Reaper-marked" : "",
          p.vampire_marked ? "Vampire-marked" : "",
          p.cloak_charges > 0 ? `Cloak (${p.cloak_charges} delayed uses)` : "",
        ]
          .filter(Boolean)
          .join(" · ");
        if (theme && window.PixelArt) PixelArt.drawHudChip(canvas, theme, p);
        hud.appendChild(canvas);
      });
      const me = state.your_seat;
      const myTurn = me === state.active;
      $("turn-banner").textContent = myTurn
        ? state.pending_card_id
          ? "Choose a target"
          : `Turn — ${state.players[me]?.name || "you"}`
        : `Turn — ${state.players[state.active]?.name || "…"}`;
      const hand = $("hand");
      hand.innerHTML = "";
      (state.your_hand || []).forEach((card) => {
        hand.appendChild(
          renderCard(card, { playable: myTurn && !state.pending_card_id })
        );
      });
      const targets = $("targets");
      const cancel = $("btn-cancel-target");
      if (myTurn && state.pending_card_id != null) {
        targets.classList.remove("hidden");
        cancel.classList.remove("hidden");
        targets.innerHTML = "";
        const allowedTargets = new Set(
          state.pending_targets || state.players.map((p) => p.seat)
        );
        state.players.forEach((p) => {
          if (!p.alive || !allowedTargets.has(p.seat)) return;
          const b = document.createElement("button");
          b.type = "button";
          b.className = "target art-btn";
          b.dataset.label = p.seat === me ? `${p.name} (you)` : p.name;
          b.dataset.palette = p.seat === me ? "heal" : "normal";
          b.onclick = () => send({ action: "choose_target", target: p.seat });
          targets.appendChild(b);
        });
      } else {
        targets.classList.add("hidden");
        cancel.classList.add("hidden");
        targets.innerHTML = "";
      }
      $("play-log").textContent = (state.log || []).join("\n");
      paintChrome();
      return;
    }

    if (state.phase === "game_over") {
      show("over");
      $("over-title").textContent = state.winner
        ? `${state.winner} wins!`
        : "Game over";
      $("over-log").textContent = (state.log || []).join("\n");
      if (theme) {
        document.body.style.backgroundColor = state.winner
          ? theme.win_bg
          : theme.lose_bg;
      }
    }
  }

  $("deck-down").onclick = () => {
    deckSize = Math.max(3, deckSize - 1);
    syncDeckLabel();
  };
  $("deck-up").onclick = () => {
    deckSize = Math.min(20, deckSize + 1);
    syncDeckLabel();
  };
  $("match-size").onchange = setupRulesText;

  $("btn-host").onclick = () => send(hostPayload());
  $("btn-join").onclick = () => {
    const code = ($("room-code").value || "").trim();
    if (!/^[0-9]{6}$/.test(code)) {
      toast("Enter the six-digit room code");
      return;
    }
    send({
      action: "join",
      name: $("name").value || "Player",
      code,
    });
  };
  $("btn-start-craft").onclick = () => {
    send({ action: "start_craft", host_token: hostToken });
  };

  Object.keys(UNIQUE_META).forEach((key) => {
    const canvas = $(`pick-${key}`);
    const toggle = () => {
      if (canvas.classList.contains("disabled")) return;
      uniquePick = uniquePick === key ? null : key;
      if (uniquePick === "shield") $("dmg-slider").value = "0";
      if (uniquePick === "poison") $("dmg-slider").value = $("dmg-slider").max;
      if (UNIQUE_META[uniquePick]?.zeroBudget) $("dmg-slider").value = "0";
      if (state?.craft) syncUniquePicks(state.craft);
      else paintUniquePicks();
      updateSplitPreview();
    };
    canvas.onclick = toggle;
    canvas.onkeydown = (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle();
      }
    };
    canvas.onmouseenter = () => paintUniquePicks();
    canvas.onmouseleave = () => paintUniquePicks();
  });

  $("dmg-slider").oninput = updateSplitPreview;
  $("btn-craft").onclick = () => {
    const flags = {};
    Object.entries(UNIQUE_META).forEach(([key, meta]) => {
      flags[meta.flag] = uniquePick === key;
    });
    send({
      action: "craft",
      damage: Number($("dmg-slider").value),
      ...flags,
    });
    uniquePick = null;
  };
  $("btn-finish-craft").onclick = () => send({ action: "finish_craft" });
  $("btn-cancel-target").onclick = () => send({ action: "cancel_pending" });

  $("theme-pick").onchange = () => setTheme("pick", $("theme-pick").value);
  $("btn-theme-random").onclick = () => setTheme("random");

  document.querySelectorAll(".art-btn").forEach((btn) => {
    btn.addEventListener("mouseenter", () => paintArtButton(btn));
    btn.addEventListener("mouseleave", () => paintArtButton(btn));
  });

  window.addEventListener("resize", () => {
    applyWallpaper();
    paintChrome();
  });

  fetch("/api/host-info")
    .then((r) => r.json())
    .then((info) => {
      $("host-hint").textContent = info.hint;
    })
    .catch(() => {});

  syncDeckLabel();
  loadTheme().catch(() => toast("Could not load theme"));
  connect();
  show("home");
})();
