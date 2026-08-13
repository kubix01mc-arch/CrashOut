(() => {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${proto}://${location.host}/ws`;

  let ws = null;
  let token = null;
  let hostToken = null;
  let state = null;

  const $ = (id) => document.getElementById(id);
  const screens = ["home", "lobby", "craft", "play", "over"];

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

  function connect() {
    $("connection").textContent = "Connecting…";
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      $("connection").textContent = "Connected — WiFi / browser mode";
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

  function cardClass(c) {
    if (c.heal_any || (c.heal > c.damage && !c.steals && !c.heavy_hit && !c.poisons && !c.shields))
      return "heal";
    if (c.poisons) return "poison";
    if (c.shields) return "shield";
    if (c.heavy_hit) return "heavy";
    if (c.steals) return "steal";
    return "";
  }

  function cardStats(c) {
    if (c.heal_any) return `HEAL\n${c.heal}`;
    const d = c.display_damage ?? c.damage;
    const h = c.display_heal ?? c.heal;
    if (h <= d) return `${d}\nDMG`;
    return `${h}\nHEAL`;
  }

  function cardDetail(c) {
    if (c.heal_any) return "any target";
    const bits = [];
    const d = c.display_damage ?? c.damage;
    const h = c.display_heal ?? c.heal;
    if (h <= d && h > 0) bits.push(`+${h} heal`);
    if (h > d && d > 0) bits.push(`+${d} dmg`);
    if (c.steals) bits.push("steal");
    if (c.heavy_hit) bits.push("heavy");
    if (c.shields) bits.push("shield");
    if (c.poisons) bits.push("poison");
    if (c.cooling) bits.push("cooldown");
    if (c.borrowed) bits.push("borrowed");
    return bits.join(" · ");
  }

  function renderCard(c, { playable } = {}) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = `card ${cardClass(c)}${c.cooling ? " cooling" : ""}`;
    el.innerHTML = `<div class="name">${escapeHtml(c.name)}</div>
      <div class="stats">${escapeHtml(cardStats(c))}</div>
      <div class="detail">${escapeHtml(cardDetail(c))}</div>`;
    if (playable && !c.cooling) {
      el.onclick = () => send({ action: "play_card", card_id: c.id });
    } else {
      el.disabled = true;
    }
    return el;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function uniqueExclusive(changedId) {
    const ids = ["u-steal", "u-heavy", "u-shield", "u-poison"];
    if (!$(changedId).checked) return;
    ids.forEach((id) => {
      if (id !== changedId) $(id).checked = false;
    });
    if (changedId === "u-shield") $("dmg-slider").value = "0";
    if (changedId === "u-poison") $("dmg-slider").value = $("dmg-slider").max;
    updateSplitPreview();
  }

  function craftBudget() {
    if (!state?.craft) return state?.settings?.power_points || 100;
    const pp = state.settings.power_points;
    if ($("u-steal").checked) return state.craft.budget_steal;
    if ($("u-shield").checked) return state.craft.budget_shield;
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
    if ($("u-shield").checked) {
      dmg = 0;
      slider.value = "0";
      slider.disabled = true;
    } else if ($("u-poison").checked) {
      dmg = budget;
      slider.value = String(budget);
      slider.disabled = true;
    } else {
      slider.disabled = false;
    }
    const heal = budget - dmg;
    $("split-preview").textContent = `${dmg} damage / ${heal} heal (budget ${budget})`;
  }

  function render() {
    if (!state) {
      show("home");
      return;
    }
    if (state.phase === "lobby") {
      show("lobby");
      $("lobby-code").textContent = state.code;
      const list = $("seat-list");
      list.innerHTML = "";
      state.seats.forEach((s) => {
        const li = document.createElement("li");
        li.innerHTML = `<span>Seat ${s.seat + 1}</span><span>${
          s.filled ? escapeHtml(s.name) : "—"
        }</span>`;
        list.appendChild(li);
      });
      const hostPanel = $("host-settings");
      hostPanel.classList.toggle("hidden", !hostToken);
      if (hostToken) {
        $("set-players").value = state.settings.player_count;
        $("set-hp").value = state.settings.starting_hp;
        $("set-pp").value = state.settings.power_points;
        $("set-deck").value = state.settings.deck_size;
        $("lobby-hint").textContent = "Share the room code with friends on the same WiFi.";
      } else {
        $("lobby-hint").textContent = "Waiting for host to start Card Lab…";
      }
      return;
    }

    if (state.phase === "craft") {
      show("craft");
      const c = state.craft;
      if (!c) return;
      $("craft-slot").textContent = c.ready
        ? "READY"
        : `Card ${c.slot}/${state.settings.deck_size}`;
      $("craft-rules").textContent = state.settings.allow_duplicates
        ? "12+ deck: duplicate types allowed. Uniques still one each."
        : "Under 12 cards: each type unique. Uniques one each.";
      $("craft-form").classList.toggle("hidden", c.ready || c.done_craftable);
      $("btn-finish-craft").classList.toggle("hidden", c.ready || !c.done_craftable);
      $("craft-waiting").classList.toggle("hidden", !c.ready);
      $("u-steal").disabled = !c.can_steal;
      $("u-heavy").disabled = !c.can_heavy;
      $("u-shield").disabled = !c.can_shield;
      $("u-poison").disabled = !c.can_poison;
      updateSplitPreview();
      const deck = $("craft-deck");
      deck.innerHTML = "";
      (state.your_deck || []).forEach((card) => deck.appendChild(renderCard(card)));
      return;
    }

    if (state.phase === "play") {
      show("play");
      const hud = $("hud");
      hud.innerHTML = "";
      state.players.forEach((p) => {
        const chip = document.createElement("div");
        chip.className = `chip${p.is_active ? " active" : ""}${p.alive ? "" : " dead"}`;
        let status = "";
        if (p.shield) status = "SHIELD";
        else if (p.poisoned) status = "POISON";
        chip.innerHTML = `<div>${escapeHtml(p.name)}</div>
          <div class="hp">${p.alive ? `${p.hp}/${p.max_hp}` : "OUT"}</div>
          <div class="status">${status}</div>`;
        hud.appendChild(chip);
      });
      const me = state.your_seat;
      const myTurn = me === state.active;
      $("turn-banner").textContent = myTurn
        ? state.pending_card_id
          ? "Choose a target"
          : "Your turn — pick a card"
        : `Waiting for ${state.players[state.active]?.name || "…"}`;
      const hand = $("hand");
      hand.innerHTML = "";
      (state.your_hand || []).forEach((card) => {
        hand.appendChild(renderCard(card, { playable: myTurn && !state.pending_card_id }));
      });
      const targets = $("targets");
      const cancel = $("btn-cancel-target");
      if (myTurn && state.pending_card_id != null) {
        targets.classList.remove("hidden");
        cancel.classList.remove("hidden");
        targets.innerHTML = "";
        state.players.forEach((p) => {
          if (!p.alive) return;
          const b = document.createElement("button");
          b.type = "button";
          b.className = "target";
          b.textContent = p.seat === me ? `${p.name} (you)` : p.name;
          b.onclick = () => send({ action: "choose_target", target: p.seat });
          targets.appendChild(b);
        });
      } else {
        targets.classList.add("hidden");
        cancel.classList.add("hidden");
        targets.innerHTML = "";
      }
      $("play-log").textContent = (state.log || []).join("\n");
      return;
    }

    if (state.phase === "game_over") {
      show("over");
      $("over-title").textContent = state.winner
        ? `${state.winner} wins!`
        : "Game over";
      $("over-log").textContent = (state.log || []).join("\n");
    }
  }

  $("btn-create").onclick = () => {
    send({ action: "create", name: $("name").value || "Host" });
  };
  $("btn-join").onclick = () => {
    send({
      action: "join",
      name: $("name").value || "Player",
      code: ($("room-code").value || "").trim().toUpperCase(),
    });
  };
  $("btn-save-settings").onclick = () => {
    send({
      action: "set_settings",
      host_token: hostToken,
      player_count: Number($("set-players").value),
      starting_hp: Number($("set-hp").value),
      power_points: Number($("set-pp").value),
      deck_size: Number($("set-deck").value),
    });
  };
  $("btn-start-craft").onclick = () => {
    send({ action: "start_craft", host_token: hostToken });
  };
  ["u-steal", "u-heavy", "u-shield", "u-poison"].forEach((id) => {
    $(id).onchange = () => uniqueExclusive(id);
  });
  $("dmg-slider").oninput = updateSplitPreview;
  $("btn-craft").onclick = () => {
    send({
      action: "craft",
      damage: Number($("dmg-slider").value),
      steals: $("u-steal").checked,
      heavy_hit: $("u-heavy").checked,
      shields: $("u-shield").checked,
      poisons: $("u-poison").checked,
    });
    $("u-steal").checked = false;
    $("u-heavy").checked = false;
    $("u-shield").checked = false;
    $("u-poison").checked = false;
  };
  $("btn-finish-craft").onclick = () => send({ action: "finish_craft" });
  $("btn-cancel-target").onclick = () => send({ action: "cancel_pending" });

  fetch("/api/host-info")
    .then((r) => r.json())
    .then((info) => {
      $("host-hint").textContent =
        `Same WiFi friends open http://${info.lan_ip}:8765 and join your room code.`;
    })
    .catch(() => {});

  connect();
  show("home");
})();
