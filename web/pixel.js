/* Pixel card frames — port of crash_out_window.py drawers. */
(function (global) {
  function shiftHex(color, delta) {
    const raw = (color || "#000000").replace("#", "");
    const rgb = [0, 2, 4].map((i) =>
      Math.max(0, Math.min(255, parseInt(raw.slice(i, i + 2), 16) + delta))
    );
    return `#${rgb.map((n) => n.toString(16).padStart(2, "0")).join("")}`;
  }

  function pixelScale(size) {
    return Math.max(2, Math.floor(size / 28));
  }

  function mcFontSize(size) {
    return Math.max(8, Math.round(size / 8) * 8);
  }

  function rect(ctx, x1, y1, x2, y2, color) {
    if (x2 <= x1 || y2 <= y1) return;
    ctx.fillStyle = color;
    ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
  }

  function frame(ctx, x1, y1, x2, y2, color, s) {
    s = Math.max(1, s);
    rect(ctx, x1, y1, x2, y1 + s, color);
    rect(ctx, x1, y2 - s, x2, y2, color);
    rect(ctx, x1, y1, x1 + s, y2, color);
    rect(ctx, x2 - s, y1, x2, y2, color);
  }

  function block(ctx, x, y, s, color) {
    rect(ctx, x, y, x + s, y + s, color);
  }

  function line(ctx, x0, y0, x1, y1, s, color) {
    s = Math.max(1, s);
    x0 = Math.floor(x0 / s) * s;
    y0 = Math.floor(y0 / s) * s;
    x1 = Math.floor(x1 / s) * s;
    y1 = Math.floor(y1 / s) * s;
    const dx = Math.abs(x1 - x0);
    const dy = Math.abs(y1 - y0);
    const sx = x0 < x1 ? s : -s;
    const sy = y0 < y1 ? s : -s;
    let err = dx - dy;
    let x = x0;
    let y = y0;
    for (let i = 0; i < (dx + dy) / s + 3; i++) {
      block(ctx, x, y, s, color);
      if (x === x1 && y === y1) break;
      const e2 = 2 * err;
      if (e2 > -dy) {
        err -= dy;
        x += sx;
      }
      if (e2 < dx) {
        err += dx;
        y += sy;
      }
    }
  }

  function disk(ctx, cx, cy, r, s, color) {
    s = Math.max(1, s);
    r = Math.max(s, Math.floor(r / s) * s);
    const rr = r * r;
    for (let y = -r; y <= r; y += s) {
      for (let x = -r; x <= r; x += s) {
        if (x * x + y * y <= rr) block(ctx, cx + x, cy + y, s, color);
      }
    }
  }

  function ring(ctx, cx, cy, r, s, color) {
    s = Math.max(1, s);
    r = Math.max(s, Math.floor(r / s) * s);
    const outer = r * r;
    const inner = Math.max(0, r - s) ** 2;
    for (let y = -r; y <= r; y += s) {
      for (let x = -r; x <= r; x += s) {
        const d = x * x + y * y;
        if (inner < d && d <= outer) block(ctx, cx + x, cy + y, s, color);
      }
    }
  }

  function arcTop(ctx, x1, yBase, width, height, s, color) {
    s = Math.max(1, s);
    const cx = x1 + Math.floor(width / 2);
    const rx = Math.max(s, Math.floor(width / 2 / s) * s);
    const ry = Math.max(s, Math.floor(height / s) * s);
    for (let x = -rx; x <= rx; x += s) {
      const xn = x / Math.max(1, rx);
      let yOff = Math.floor(ry * Math.sqrt(Math.max(0, 1 - xn * xn)));
      yOff = Math.floor(yOff / s) * s;
      block(ctx, cx + x, yBase - yOff, s, color);
    }
  }

  const DRAWERS = {
    pixel(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = scale;
      const highlight = shiftHex(fill, 38);
      const shadow = shiftHex(fill, -40);
      const outline = shiftHex(accent, -50);
      rect(ctx, x1 + s, y1, x2 - s, y2, fill);
      rect(ctx, x1, y1 + s, x2, y2 - s, fill);
      rect(ctx, x1 + s, y1, x2 - s, y1 + s, outline);
      rect(ctx, x1 + s, y2 - s, x2 - s, y2, outline);
      rect(ctx, x1, y1 + s, x1 + s, y2 - s, outline);
      rect(ctx, x2 - s, y1 + s, x2, y2 - s, outline);
      rect(ctx, x1 + s, y1 + s, x2 - s, y1 + 2 * s, highlight);
      rect(ctx, x1 + s, y1 + s, x1 + 2 * s, y2 - s, highlight);
      rect(ctx, x1 + s, y2 - 2 * s, x2 - s, y2 - s, shadow);
      rect(ctx, x2 - 2 * s, y1 + s, x2 - s, y2 - s, shadow);
      const inner = 3 * s;
      const ix1 = x1 + inner;
      const iy1 = y1 + inner;
      const ix2 = x2 - inner;
      const iy2 = y2 - inner;
      if (ix2 - ix1 > 4 * s && iy2 - iy1 > 4 * s) {
        rect(ctx, ix1 + s, iy1, ix2 - s, iy1 + s, accent);
        rect(ctx, ix1 + s, iy2 - s, ix2 - s, iy2, accent);
        rect(ctx, ix1, iy1 + s, ix1 + s, iy2 - s, accent);
        rect(ctx, ix2 - s, iy1 + s, ix2, iy2 - s, accent);
      }
    },
    neon(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      [
        [0, accent],
        [s, shiftHex(accent, 40)],
        [2 * s, shiftHex(accent, -35)],
      ].forEach(([inset, color]) =>
        frame(ctx, x1 + inset, y1 + inset, x2 - inset, y2 - inset, color, s)
      );
      const arm = 5 * s;
      [
        [x1 + s, y1 + s, 1, 1],
        [x2 - 2 * s, y1 + s, -1, 1],
        [x1 + s, y2 - 2 * s, 1, -1],
        [x2 - 2 * s, y2 - 2 * s, -1, -1],
      ].forEach(([px, py, dx, dy]) => {
        if (dx > 0) rect(ctx, px, py, px + arm, py + s, accent);
        else rect(ctx, px - arm + s, py, px + s, py + s, accent);
        if (dy > 0) rect(ctx, px, py, px + s, py + arm, accent);
        else rect(ctx, px, py - arm + s, px + s, py + s, accent);
      });
    },
    stone(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, shiftHex(accent, -55));
      frame(ctx, x1, y1, x2, y2, shiftHex(accent, -40), s);
      const rowH = Math.max(3, 3 * s);
      let row = 0;
      let y = y1 + s;
      while (y < y2 - s) {
        const offset = (row % 2) * (4 * s);
        let x = x1 + s + offset;
        while (x < x2 - s) {
          const bw = Math.min(7 * s, x2 - s - x);
          const bh = Math.min(rowH - s, y2 - s - y);
          rect(ctx, x, y, x + bw, y + bh, shiftHex(fill, row % 2 ? 10 : -10));
          x += 8 * s;
        }
        y += rowH;
        row += 1;
      }
    },
    ice(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, accent, s);
      const frost = shiftHex(accent, 50);
      const step = Math.max(2, 3 * s);
      const d = y2 - y1;
      for (let i = x1 - d; i < x2 + d; i += step) line(ctx, i, y1 + s, i + d, y2 - s, s, frost);
      rect(ctx, x1 + s, y1 + s, x2 - s, y1 + 2 * s, "#ffffff");
    },
    lava(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, shiftHex(accent, -30), s);
      const w = x2 - x1;
      const h = y2 - y1;
      [
        [x1 + 3 * s, y1 + 4 * s, x1 + Math.floor(w / 2), y1 + Math.floor(h / 3)],
        [x1 + Math.floor(w / 2), y1 + Math.floor(h / 3), x2 - 4 * s, y2 - 5 * s],
        [x1 + 5 * s, y2 - 6 * s, x2 - 6 * s, y1 + Math.floor(h / 2)],
        [x1 + Math.floor(w / 3), y1 + 6 * s, x1 + Math.floor((2 * w) / 3), y2 - 4 * s],
      ].forEach(([xa, ya, xb, yb]) => {
        line(ctx, xa, ya, xb, yb, s, accent);
        line(ctx, xa + s, ya, xb + s, yb, s, shiftHex(accent, 35));
      });
    },
    arcade(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      const stripe = 2 * s;
      let row = 0;
      for (let y = y1; y < y2; y += stripe, row++) {
        rect(ctx, x1, y, x2, Math.min(y + stripe, y2), shiftHex(fill, row % 2 ? 14 : -14));
      }
      frame(ctx, x1, y1, x2, y2, accent, 2 * s);
      const dot = 2 * s;
      [
        [x1 + dot, y1 + dot],
        [x2 - dot, y1 + dot],
        [x1 + dot, y2 - dot],
        [x2 - dot, y2 - dot],
      ].forEach(([px, py]) => rect(ctx, px - dot, py - dot, px + dot, py + dot, accent));
    },
    gold(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, accent, 2 * s);
      frame(ctx, x1 + 2 * s, y1 + 2 * s, x2 - 2 * s, y2 - 2 * s, shiftHex(accent, 25), s);
      const gem = 2 * s;
      [
        [x1 + 3 * s, y1 + 3 * s],
        [x2 - 3 * s, y1 + 3 * s],
        [x1 + 3 * s, y2 - 3 * s],
        [x2 - 3 * s, y2 - 3 * s],
      ].forEach(([px, py]) => {
        rect(ctx, px - gem, py - gem, px + gem, py + gem, accent);
        frame(ctx, px - gem, py - gem, px + gem, py + gem, shiftHex(accent, 40), s);
      });
    },
    circuit(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, accent, s);
      const step = Math.max(3, 4 * s);
      const dot = Math.max(1, s);
      for (let gx = x1 + 2 * s; gx < x2 - 2 * s; gx += step) {
        for (let gy = y1 + 2 * s; gy < y2 - 2 * s; gy += step) {
          rect(ctx, gx, gy, gx + dot, gy + dot, shiftHex(accent, -15));
        }
      }
      const mid = Math.floor((y1 + y2) / 2);
      rect(ctx, x1 + 4 * s, mid, x2 - 4 * s, mid + s, accent);
      rect(ctx, Math.floor((x1 + x2) / 2), y1 + 4 * s, Math.floor((x1 + x2) / 2) + s, y2 - 4 * s, accent);
    },
    shadow(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      const inset = 2 * s;
      frame(ctx, x1 + inset, y1 + inset, x2 - inset, y2 - inset, accent, s);
      rect(ctx, x1 + inset, y1 + inset + 3 * s, x2 - inset, y1 + inset + 4 * s, shiftHex(accent, -35));
    },
    crimson(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, shiftHex(accent, -40), 2 * s);
      const archY = y1 + Math.floor((y2 - y1) / 3);
      const step = Math.max(6 * s, Math.floor((x2 - x1) / 4));
      for (let x = x1 + 3 * s; x + step < x2 - 2 * s; x += step + s) {
        arcTop(ctx, x, archY, step, 4 * s, s, accent);
      }
      [
        [x1 + 3 * s, y1 + 3 * s],
        [x2 - 3 * s, y1 + 3 * s],
        [x1 + 3 * s, y2 - 3 * s],
        [x2 - 3 * s, y2 - 3 * s],
      ].forEach(([px, py]) => disk(ctx, px, py, s, Math.max(1, Math.floor(s / 2)), accent));
    },
    ocean(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, accent, s);
      const band = Math.max(3, 3 * s);
      let y = y1 + 2 * s;
      let row = 0;
      while (y < y2 - 2 * s) {
        const color = shiftHex(accent, row % 2 === 0 ? 20 : -25);
        const amp = row % 2 === 0 ? 2 * s : s;
        for (let x = x1 + 2 * s; x < x2 - 2 * s; x += 2 * s) {
          const crest = Math.floor(x / s) % 4 < 2 ? amp : 0;
          rect(ctx, x, y + crest, Math.min(x + 2 * s, x2 - 2 * s), y + band + crest, color);
        }
        y += band + s;
        row += 1;
      }
      rect(ctx, x1 + s, y1 + s, x2 - s, y1 + 2 * s, shiftHex(accent, 40));
    },
    sakura(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      const cut = 3 * s;
      rect(ctx, x1 + cut, y1, x2 - cut, y2, fill);
      rect(ctx, x1, y1 + cut, x2, y2 - cut, fill);
      [
        [x1 + cut, y1 + cut],
        [x2 - cut, y1 + cut],
        [x1 + cut, y2 - cut],
        [x2 - cut, y2 - cut],
      ].forEach(([cx, cy]) => disk(ctx, cx, cy, cut, s, fill));
      frame(ctx, x1 + s, y1 + s, x2 - s, y2 - s, accent, s);
      const petal = 2 * s;
      [
        [x1 + 4 * s, y1 + 5 * s],
        [x2 - 4 * s, y1 + 5 * s],
        [x1 + 4 * s, y2 - 5 * s],
        [x2 - 4 * s, y2 - 5 * s],
        [Math.floor((x1 + x2) / 2), y1 + 4 * s],
      ].forEach(([px, py]) => disk(ctx, px, py, petal, s, accent));
    },
    jazz(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, accent, 2 * s);
      const step = Math.max(3, 3 * s);
      const d = y2 - y1;
      const stripe = shiftHex(fill, 18);
      for (let i = x1 - d; i < x2 + d; i += step) line(ctx, i, y1 + s, i + d, y2 - s, s, stripe);
      const corner = 4 * s;
      [
        [x1 + 2 * s, y1 + 2 * s, 1, 1],
        [x2 - 3 * s, y1 + 2 * s, -1, 1],
        [x1 + 2 * s, y2 - 3 * s, 1, -1],
        [x2 - 3 * s, y2 - 3 * s, -1, -1],
      ].forEach(([px, py, dx, dy]) => {
        if (dx > 0) rect(ctx, px, py, px + corner, py + s, accent);
        else rect(ctx, px - corner + s, py, px + s, py + s, accent);
        if (dy > 0) rect(ctx, px, py, px + s, py + corner, accent);
        else rect(ctx, px, py - corner + s, px + s, py + s, accent);
      });
    },
    toxic(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, accent, s);
      const band = Math.max(3, 3 * s);
      [y1 + 2 * s, y2 - 2 * s - band].forEach((sideY) => {
        let x = x1 + 2 * s;
        let flip = 0;
        while (x < x2 - 2 * s) {
          const color = flip % 2 === 0 ? accent : shiftHex(fill, -20);
          for (let stepI = 0; stepI < band; stepI += s) {
            const half = (stepI / s) * s;
            const mid = x + band;
            rect(ctx, mid - half, sideY + band - stepI - s, mid + half + s, sideY + band - stepI, color);
          }
          x += band;
          flip += 1;
        }
      });
      const mid = Math.floor((y1 + y2) / 2);
      rect(ctx, x1 + 3 * s, mid - s, x2 - 3 * s, mid + s, accent);
    },
    solar(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, accent, 2 * s);
      const cx = Math.floor((x1 + x2) / 2);
      const cy = Math.floor((y1 + y2) / 2);
      const radius = Math.floor(Math.min(x2 - x1, y2 - y1) / 2) - 2 * s;
      for (let i = 0; i < 12; i++) {
        const ang = (i * Math.PI) / 6;
        line(
          ctx,
          cx,
          cy,
          cx + Math.floor(Math.cos(ang) * radius),
          cy + Math.floor(Math.sin(ang) * radius),
          s,
          shiftHex(accent, i % 2 ? -20 : 20)
        );
      }
      disk(ctx, cx, cy, 3 * s, s, accent);
      ring(ctx, cx, cy, 4 * s, s, shiftHex(accent, 40));
    },
    aurora(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, accent, s);
      [
        [shiftHex(accent, 30), y1 + Math.floor((y2 - y1) / 4)],
        [accent, y1 + Math.floor((y2 - y1) / 2)],
        [shiftHex(accent, -30), y1 + Math.floor((3 * (y2 - y1)) / 4)],
      ].forEach(([color, baseY]) => {
        let x = x1 + 2 * s;
        let phase = 0;
        while (x <= x2 - 2 * s) {
          const y = baseY + (phase % 2 === 0 ? 2 * s : -2 * s);
          rect(ctx, x, y, Math.min(x + 3 * s, x2 - 2 * s), y + s, color);
          x += 3 * s;
          phase += 1;
        }
      });
      frame(ctx, x1 + 2 * s, y1 + 2 * s, x2 - 2 * s, y2 - 2 * s, shiftHex(accent, 25), s);
    },
    ruins(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      frame(ctx, x1, y1, x2, y2, shiftHex(accent, -30), s);
      rect(ctx, x1 + 2 * s, y1 + 2 * s, x2 - 2 * s, y1 + 5 * s, shiftHex(fill, 15));
      frame(ctx, x1 + 2 * s, y1 + 2 * s, x2 - 2 * s, y1 + 5 * s, accent, s);
      const pillarW = Math.max(3, 3 * s);
      const gap = Math.max(4, Math.floor((x2 - x1 - 4 * s - 3 * pillarW) / 2));
      let px = x1 + 3 * s;
      for (let i = 0; i < 3; i++) {
        rect(ctx, px, y1 + 5 * s, px + pillarW, y2 - 3 * s, shiftHex(fill, -12));
        frame(ctx, px, y1 + 5 * s, px + pillarW, y2 - 3 * s, accent, s);
        px += pillarW + gap;
      }
      line(ctx, x1 + 4 * s, y2 - 5 * s, x2 - 6 * s, y2 - 4 * s, s, accent);
      line(ctx, x1 + 6 * s, y1 + 8 * s, x1 + 10 * s, y1 + 12 * s, s, shiftHex(accent, -20));
    },
    void(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1, y1, x2, y2, fill);
      const cx = Math.floor((x1 + x2) / 2);
      const cy = Math.floor((y1 + y2) / 2);
      [8 * s, 5 * s, 3 * s].forEach((r) => ring(ctx, cx, cy, r, s, accent));
      const star = Math.max(1, s);
      [
        [x1 + 3 * s, y1 + 3 * s],
        [x2 - 3 * s, y1 + 4 * s],
        [x1 + 4 * s, y2 - 4 * s],
        [x2 - 4 * s, y2 - 3 * s],
        [x1 + 6 * s, Math.floor((y1 + y2) / 2)],
        [x2 - 6 * s, Math.floor((y1 + y2) / 2)],
      ].forEach(([px, py]) =>
        rect(ctx, px - star, py - star, px + star, py + star, shiftHex(accent, 30))
      );
    },
    candy(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      rect(ctx, x1 + s, y1 + s, x2 - s, y2 - s, fill);
      const r = 2 * s;
      for (let x = x1 + s; x < x2 - s; x += 2 * r) {
        disk(ctx, x + r, y1 + r, r, s, accent);
        disk(ctx, x + r, y2 - r, r, s, accent);
      }
      for (let y = y1 + s; y < y2 - s; y += 2 * r) {
        disk(ctx, x1 + r, y + r, r, s, accent);
        disk(ctx, x2 - r, y + r, r, s, accent);
      }
      rect(ctx, x1 + 2 * s, y1 + 2 * s, x2 - 2 * s, y2 - 2 * s, fill);
      frame(ctx, x1 + 2 * s, y1 + 2 * s, x2 - 2 * s, y2 - 2 * s, shiftHex(accent, 20), s);
      const dot = 2 * s;
      [
        [x1 + 6 * s, y1 + 7 * s],
        [x2 - 6 * s, y1 + 9 * s],
        [x1 + 7 * s, y2 - 8 * s],
        [x2 - 7 * s, y2 - 7 * s],
        [Math.floor((x1 + x2) / 2), Math.floor((y1 + y2) / 2)],
      ].forEach(([px, py]) => disk(ctx, px, py, dot, s, shiftHex(accent, -15)));
    },
    village(ctx, x1, y1, x2, y2, fill, accent, scale) {
      const s = Math.max(2, scale);
      const grassHi = shiftHex(fill, 40);
      const grassMid = fill;
      const grassLo = shiftHex(fill, -25);
      const dirtHi = shiftHex(accent, 28);
      const dirtMid = accent;
      const dirtLo = shiftHex(accent, -30);
      const dirtRed = shiftHex(accent, -10);
      const stone = "#8a8a8a";
      const outline = shiftHex(dirtLo, -20);
      const w = Math.max(1, x2 - x1);
      const h = Math.max(1, y2 - y1);
      const cols = 16;
      const rows = 16;
      const cellW = Math.max(1, Math.floor(w / cols));
      const cellH = Math.max(1, Math.floor(h / rows));
      const grassDepth = [3, 4, 3, 2, 4, 3, 4, 3, 2, 4, 3, 4, 2, 3, 4, 3];
      const dirtNoise = [
        0, 1, 2, 0, 3, 1, 0, 2, 1, 0, 3, 2, 0, 1, 2, 0, 1, 0, 3, 2, 0, 1, 2, 0, 3, 1, 0, 2, 1, 0, 3, 2,
        2, 3, 0, 1, 2, 0, 3, 1, 0, 2, 1, 3, 0, 2, 1, 0, 0, 2, 1, 3, 0, 2, 1, 0, 2, 0, 3, 1, 2, 0, 1, 3,
        1, 0, 2, 0, 3, 1, 0, 2, 3, 1, 0, 2, 0, 1, 2, 0, 3, 1, 0, 2, 1, 0, 2, 3, 0, 1, 2, 0, 1, 3, 0, 2,
        0, 2, 3, 1, 0, 2, 1, 0, 2, 0, 1, 3, 2, 0, 1, 0, 2, 0, 1, 0, 2, 3, 0, 1, 0, 2, 1, 0, 3, 2, 0, 1,
        1, 3, 0, 2, 1, 0, 2, 0, 1, 3, 0, 2, 1, 0, 2, 0, 0, 1, 2, 0, 3, 1, 0, 2, 0, 1, 2, 3, 0, 1, 0, 2,
        2, 0, 1, 3, 0, 2, 1, 0, 2, 0, 1, 0, 2, 3, 1, 0, 0, 2, 0, 1, 2, 0, 3, 1, 0, 2, 3, 0, 1, 2, 0, 1,
        1, 0, 2, 0, 1, 3, 0, 2, 1, 0, 2, 1, 0, 2, 3, 0,
      ];
      const dirtTones = [dirtMid, dirtHi, dirtLo, dirtRed];
      const pebbles = new Set(["2,7", "5,9", "9,6", "12,11", "4,13", "14,8", "7,12", "11,14"]);
      for (let cy = 0; cy < rows; cy++) {
        for (let cx = 0; cx < cols; cx++) {
          const depth = grassDepth[cx % grassDepth.length];
          let color;
          if (cy < depth) {
            if (cy === 0) color = grassHi;
            else if (cy === depth - 1) color = grassLo;
            else color = (cx + cy) % 2 === 0 ? grassMid : grassHi;
          } else if (pebbles.has(`${cx},${cy}`)) color = stone;
          else color = dirtTones[dirtNoise[(cy * cols + cx) % dirtNoise.length]];
          const px = x1 + cx * cellW;
          const py = y1 + cy * cellH;
          const pw = cx === cols - 1 ? x2 - px : cellW;
          const ph = cy === rows - 1 ? y2 - py : cellH;
          rect(ctx, px, py, px + pw, py + ph, color);
        }
      }
      frame(ctx, x1, y1, x2, y2, outline, Math.max(1, s));
    },
  };

  function drawFrame(ctx, x1, y1, x2, y2, fill, accent, scale, style) {
    (DRAWERS[style] || DRAWERS.pixel)(ctx, x1, y1, x2, y2, fill, accent, scale);
  }

  function wrapText(ctx, text, maxWidth) {
    const words = String(text || "").split(/\s+/);
    const lines = [];
    let line = "";
    words.forEach((word) => {
      const test = line ? `${line} ${word}` : word;
      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);
        line = word;
      } else line = test;
    });
    if (line) lines.push(line);
    return lines.slice(0, 3);
  }

  function cardPalette(theme, card) {
    const art = theme.cards;
    if (card.cooling) return art.disabled;
    if (
      card.exordia ||
      card.cloak ||
      card.lava ||
      card.joker ||
      card.reaper ||
      card.cure
    ) return art.selected;
    if (card.vampire) return art.poison;
    if (card.heal_any || (card.heal > card.damage && !card.steals && !card.heavy_hit && !card.shields && !card.poisons))
      return art.heal;
    if (card.heavy_hit) return art.heavy_hit;
    if (card.steals) return art.steal;
    if (card.shields) return art.selected;
    if (card.poisons) return art.poison;
    return art.normal;
  }

  function faceStats(card) {
    if (card.heal_any) return [`HEAL\n${card.heal}`, "any target"];
    if (card.exordia) return ["EXODIA", card.exordia_charged ? "charged / one-shot" : `${card.exordia_uses || 0}/4 charges`];
    if (card.cloak) return ["CLOAK", "3-turn delay"];
    if (card.lava) return ["LAVA", "mark half / 25% HP"];
    if (card.joker) return ["JOKER", "random 1-use copy"];
    if (card.reaper) return ["REAPER", "15 turns above HP"];
    if (card.cure) return ["CURE", "clear poison / marks"];
    const dmg = card.display_damage ?? card.damage;
    const heal = card.display_heal ?? card.heal;
    let detail = "";
    let stats;
    if (heal <= dmg) {
      stats = `${dmg}\nDMG`;
      detail = heal > 0 ? `+${heal} heal you` : "";
    } else {
      stats = `${heal}\nHEAL`;
      detail = dmg > 0 ? `+${dmg} dmg to target` : "";
    }
    if (card.vampire) {
      detail = `${detail}${detail ? " / " : ""}vampire mark 5t`;
    }
    return [stats, detail];
  }

  function drawCardFace(canvas, theme, card, opts) {
    const w = canvas.width;
    const h = canvas.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, w, h);
    const scale = pixelScale(w);
    const pad = scale;
    const x1 = pad;
    const y1 = pad;
    const x2 = w - pad;
    const y2 = h - pad;
    let [fill, accent, textColor] = cardPalette(theme, card);
    if (opts && opts.hover && !card.cooling) fill = shiftHex(fill, 22);
    drawFrame(ctx, x1, y1, x2, y2, fill, accent, scale, theme.card_style);
    const style = theme.card_style;
    const divX1 = x1 + 5 * scale;
    const divX2 = x2 - 5 * scale;
    if (!["shadow", "circuit", "village"].includes(style)) {
      const d1 = Math.floor(h * 0.3);
      const d2 = Math.floor(h * 0.76);
      rect(ctx, divX1, d1, divX2, d1 + scale, accent);
      rect(ctx, divX1, d2, divX2, d2 + scale, accent);
    } else if (style === "circuit") {
      rect(ctx, divX1, y1 + 5 * scale, divX2, y1 + 5 * scale + Math.max(1, Math.floor(scale / 2)), accent);
    }
    const cx = Math.floor(w / 2);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const family = `"${theme.font_family}", "Press Start 2P", monospace`;
    ctx.fillStyle = textColor;
    ctx.font = `bold ${mcFontSize(Math.max(8, Math.floor(Math.min(w, h) * 0.1)))}px ${family}`;
    wrapText(ctx, String(card.name || "").toUpperCase(), x2 - x1 - 10 * scale).forEach((ln, i) => {
      ctx.fillText(ln, cx, y1 + 7 * scale + i * mcFontSize(10));
    });
    let [stats, detail] = faceStats(card);
    if (card.cooling) detail = "cooling down";
    else if (card.borrowed) detail = "borrowed";
    ctx.fillStyle = style === "village" ? "#000000" : accent;
    ctx.font = `bold ${mcFontSize(Math.max(8, Math.floor(Math.min(w, h) * 0.13)))}px ${family}`;
    stats.split("\n").forEach((ln, i) => {
      ctx.fillText(ln, cx, Math.floor(h * 0.5) + i * mcFontSize(12));
    });
    ctx.fillStyle = textColor;
    ctx.font = `${mcFontSize(Math.max(8, Math.floor(Math.min(w, h) * 0.08)))}px ${family}`;
    wrapText(ctx, detail, x2 - x1 - 8 * scale).forEach((ln, i) => {
      ctx.fillText(ln, cx, y2 - 6 * scale + i * 10);
    });
    if (card.lava_marked) {
      const badgeX = x1 + 3 * scale;
      const badgeY = y1 + 3 * scale;
      const badgeSize = 11 * scale;
      rect(ctx, badgeX, badgeY, badgeX + badgeSize, badgeY + badgeSize, "#ff8a1a");
      frame(ctx, badgeX, badgeY, badgeX + badgeSize, badgeY + badgeSize, "#ffd1a6", Math.max(1, scale / 2));
      ctx.fillStyle = "#fff8ee";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = `bold ${mcFontSize(Math.max(7, Math.floor(Math.min(w, h) * 0.055)))}px ${family}`;
      ctx.fillText("LAVA", badgeX + badgeSize / 2, badgeY + badgeSize / 2);
    }
  }

  function drawHudChip(canvas, theme, player) {
    const w = canvas.width;
    const h = canvas.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, w, h);
    let pal = theme.hud_idle;
    if (!player.alive) pal = theme.hud_dead;
    else if (player.is_active) pal = theme.hud_active;
    const [fill, accent, text] = pal;
    const scale = Math.max(2, Math.floor(Math.min(w, h) / 24));
    DRAWERS.pixel(ctx, 0, 0, w, h, fill, accent, scale);
    const cx = Math.floor(w / 2);
    const family = `"${theme.font_family}", "Press Start 2P", monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = player.is_active ? accent : text;
    ctx.font = `bold ${mcFontSize(Math.max(8, Math.floor(h / 9)))}px ${family}`;
    ctx.fillText(String(player.name || "").toUpperCase(), cx, Math.floor(h * 0.28));
    ctx.fillStyle = player.alive ? accent : text;
    ctx.font = `bold ${mcFontSize(Math.max(12, Math.floor(h / 4)))}px ${family}`;
    ctx.fillText(player.alive ? `${player.hp}/${player.max_hp} HP` : "OUT", cx, Math.floor(h * 0.58));
    ctx.font = `bold ${mcFontSize(Math.max(8, Math.floor(h / 8)))}px ${family}`;
    if (player.alive && player.shield) {
      ctx.fillStyle = accent;
      ctx.fillText("SHIELD", cx, Math.floor(h * 0.88));
    } else if (player.alive && player.poisoned) {
      ctx.fillStyle = theme.cards.poison[1];
      ctx.fillText("POISON", cx, Math.floor(h * 0.88));
    } else if (player.alive && player.reaper_marked) {
      ctx.fillStyle = theme.cards.heavy_hit[1];
      ctx.fillText("REAPER", cx, Math.floor(h * 0.88));
    } else if (player.alive && player.vampire_marked) {
      ctx.fillStyle = theme.cards.poison[1];
      ctx.fillText("VAMPIRE", cx, Math.floor(h * 0.88));
    } else if (player.alive && player.cloak_charges > 0) {
      ctx.fillStyle = accent;
      ctx.fillText(`CLOAK ${player.cloak_charges}`, cx, Math.floor(h * 0.88));
    }
  }

  function drawArtButton(canvas, theme, paletteKey, label, hover) {
    const w = canvas.width;
    const h = canvas.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, w, h);
    let pal = theme.cards[paletteKey] || theme.cards.normal;
    let [fill, accent, text] = pal;
    if (hover) fill = shiftHex(fill, 22);
    const scale = pixelScale(Math.min(w, h * 2));
    const pad = scale;
    drawFrame(ctx, pad, pad, w - pad, h - pad, fill, accent, scale, theme.card_style);
    ctx.fillStyle = text;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `bold ${mcFontSize(Math.max(10, Math.floor(h * 0.28)))}px "${theme.font_family}", "Press Start 2P", monospace`;
    ctx.fillText(String(label).toUpperCase(), Math.floor(w / 2), Math.floor(h / 2));
  }

  function drawUniquePick(canvas, theme, paletteKey, label, selected, locked, hover) {
    const w = canvas.width;
    const h = canvas.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, w, h);
    let pal = locked ? theme.cards.disabled : selected ? theme.cards.selected : theme.cards[paletteKey] || theme.cards.normal;
    let [fill, accent, text] = pal;
    if (hover && !selected && !locked) fill = shiftHex(fill, 22);
    const scale = pixelScale(Math.min(w, h));
    const pad = scale;
    drawFrame(ctx, pad, pad, w - pad, h - pad, fill, accent, scale, theme.card_style);
    ctx.fillStyle = text;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `bold ${mcFontSize(Math.max(12, Math.floor(h / 7)))}px "${theme.font_family}", "Press Start 2P", monospace`;
    ctx.fillText(String(label).toUpperCase(), Math.floor(w / 2), Math.floor(h / 2) - (selected || locked ? 12 : 0));
    if (locked || selected) {
      ctx.fillStyle = accent;
      ctx.font = `bold ${mcFontSize(Math.max(9, Math.floor(h / 10)))}px "${theme.font_family}", "Press Start 2P", monospace`;
      ctx.fillText(locked ? "USED" : "EQUIPPED", Math.floor(w / 2), h - 5 * scale);
    }
  }

  function applyThemeCss(theme) {
    const r = document.documentElement.style;
    r.setProperty("--bg", theme.screen_bg);
    r.setProperty("--panel", theme.panel_bg);
    r.setProperty("--text", theme.body_fg);
    r.setProperty("--title", theme.title_fg);
    r.setProperty("--accent", theme.panel_border);
    r.setProperty("--log-bg", theme.log_bg);
    r.setProperty("--log-fg", theme.log_fg);
    r.setProperty("--ok", theme.cards.heal[1]);
    r.setProperty("--bad", theme.cards.heavy_hit[1]);
    r.setProperty("--poison", theme.cards.poison[1]);
    r.setProperty("--line", theme.panel_border);
    r.setProperty("--font", `"${theme.font_family}", "Press Start 2P", monospace`);
  }

  global.PixelArt = {
    shiftHex,
    pixelScale,
    mcFontSize,
    drawFrame,
    drawCardFace,
    drawHudChip,
    drawArtButton,
    drawUniquePick,
    applyThemeCss,
  };
})(window);
