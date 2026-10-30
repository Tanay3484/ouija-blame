// The séance table and the Ouija board, drawn in code at low resolution and scaled up crisp.
// Everything here is original pixel art: no sprites from anywhere else.

type Phase = "idle" | "summoning" | "speaking" | "silent";

const P = {
  night: "#0d0a1a",
  night2: "#160f2b",
  night3: "#21173d",
  cloth: "#2a1838",
  clothHi: "#4a2a5e",
  fringe: "#7a4a8e",
  brass: "#9a6a26",
  brassHi: "#ffcd75",
  wax: "#e8dcc0",
  waxShade: "#b8a888",
  flame: ["#fff1a8", "#ffcd75", "#ef7d57"],
  mist: ["#1b1035", "#2c1a55", "#4b2c8a", "#7b4fc9", "#a98bf2", "#c8f0ff"],
  ghost: "#eef2f8",
  ghostEdge: "#9fb4d8",
  ghostEye: "#262b44",
  wood: "#4a2e1a",
  woodHi: "#6b4426",
  woodEdge: "#9a6a26",
  letter: "#ffe9b0",
  letterDim: "#c9a46a",
};

const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => v / 16);
const dither = (x: number, y: number) => BAYER[(y & 3) * 4 + (x & 3)];

const GHOST = [
  ".....eeeee.....",
  "...eebbbbbee...",
  "..ebbbbbbbbbe..",
  ".ebbbbbbbbbbbe.",
  ".ebbccbbbccbbe.",
  "ebbbccbbbccbbbe",
  "ebbbbbbbbbbbbbe",
  "ebbbbbcccbbbbbe",
  "ebbbbbbcbbbbbbe",
  "ebbbbbbbbbbbbbe",
  "ebbbbbbbbbbbbbe",
  "ebbbbbbbbbbbbbe",
  "ebbbbbbbbbbbbbe",
  "ebbeebbbeebbbbe",
  "ebe..ebbe..ebbe",
  ".e....ee....ee.",
];
// When the ghost has nothing to say, its eyes close and its mouth is a flat line.
const GHOST_SILENT = GHOST.map((row, y) =>
  y === 4 ? ".ebbbbbbbbbbbe." : y === 5 ? "ebbcccbbbcccbbe" : y === 7 ? "ebbbbcccccbbbbe" : y === 8 ? "ebbbbbbbbbbbbbe" : row,
);

function px(g: CanvasRenderingContext2D, x: number, y: number, c: string, w = 1, h = 1) {
  g.fillStyle = c;
  g.fillRect(Math.round(x), Math.round(y), w, h);
}

function glow(g: CanvasRenderingContext2D, cx: number, cy: number, r: number, c: string, strength: number) {
  for (let y = -r; y <= r; y++)
    for (let x = -r; x <= r; x++) {
      const d = Math.hypot(x, y) / r;
      if (d > 1) continue;
      if ((1 - d) * strength > dither(cx + x, cy + y)) px(g, cx + x, cy + y, c);
    }
}

export class Scene {
  readonly W = 192;
  readonly H = 128;
  private g: CanvasRenderingContext2D;
  private phase: Phase = "idle";
  private ghostAlpha = 0;
  private t0 = performance.now();
  private stars: [number, number, number][] = [];
  private bg: HTMLCanvasElement | null = null;
  private lastFrame = 0;

  constructor(canvas: HTMLCanvasElement) {
    canvas.width = this.W;
    canvas.height = this.H;
    this.g = canvas.getContext("2d")!;
    let s = 7;
    const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 40; i++) this.stars.push([Math.floor(rnd() * this.W), Math.floor(rnd() * 80), rnd() * 6]);
    const loop = (now: number) => {
      if (now - this.lastFrame > 33) {
        this.lastFrame = now;
        this.draw((now - this.t0) / 1000);
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  set(phase: Phase) {
    this.phase = phase;
  }

  private draw(t: number) {
    const g = this.g;
    const { W, H } = this;
    // Night, dithered darker at the top: drawn once, then copied.
    if (!this.bg) {
      this.bg = document.createElement("canvas");
      this.bg.width = W;
      this.bg.height = H;
      const b = this.bg.getContext("2d")!;
      for (let y = 0; y < H; y++)
        for (let x = 0; x < W; x += 1) {
          const v = y / H + dither(x, y) * 0.3;
          px(b, x, y, v > 0.7 ? P.night3 : v > 0.35 ? P.night2 : P.night);
        }
    }
    g.drawImage(this.bg, 0, 0);
    for (const [x, y, ph] of this.stars) if (Math.sin(t * 1.7 + ph) > 0.2) px(g, x, y, "#8b9bb4");

    const summoning = this.phase === "summoning";
    const speaking = this.phase === "speaking" || this.phase === "silent";

    // Candles.
    for (const cx of [26, 166]) {
      const flick = Math.sin(t * 9 + cx) + Math.sin(t * 13.7 + cx * 2);
      glow(g, cx, 74, summoning ? 20 : 16, "#3a2450", 0.9);
      glow(g, cx, 74, 9, "#5d3a40", 0.8);
      px(g, cx - 3, 80, P.wax, 7, 18);
      px(g, cx + 2, 80, P.waxShade, 2, 18);
      px(g, cx, 78, "#3a2a20", 1, 2);
      const fy = 72 + (flick > 1 ? -1 : 0);
      px(g, cx - 1, fy + 2, P.flame[2], 3, 4);
      px(g, cx, fy, P.flame[1], 1, 6);
      px(g, cx, fy + 3, P.flame[0], 1, 2);
    }

    // The table and its cloth.
    px(g, 0, 98, P.clothHi, W, 2);
    px(g, 0, 100, P.cloth, W, H - 100);
    for (let x = 0; x < W; x += 4) px(g, x + 1, 100, P.fringe, 2, 2 + ((x / 4) % 2));

    // Brass stand.
    px(g, 82, 90, P.brass, 28, 8);
    px(g, 78, 96, P.brass, 36, 3);
    px(g, 84, 90, P.brassHi, 24, 1);
    px(g, 80, 96, P.brassHi, 32, 1);

    // Crystal ball: moving mist, faster and brighter while the séance runs.
    const cx = 96;
    const cy = 64;
    const r = 26;
    const speed = summoning ? 2.6 : speaking ? 0.9 : 0.5;
    const bright = summoning ? 1.6 : speaking ? 1.15 : 0.85;
    if (summoning) glow(g, cx, cy, r + 8 + Math.round(Math.sin(t * 4) * 2), "#3b2a6a", 0.7);
    for (let y = -r; y <= r; y++)
      for (let x = -r; x <= r; x++) {
        const d = Math.hypot(x, y);
        if (d > r) continue;
        const n =
          Math.sin(x * 0.21 + t * speed * 1.3) +
          Math.sin(y * 0.19 - t * speed * 0.9) +
          Math.sin((x + y) * 0.13 + t * speed * 0.7) +
          Math.sin(d * 0.35 - t * speed * 1.6);
        let v = ((n + 4) / 8) * bright - (d / r) * 0.45 + dither(x, y) * 0.18;
        v = Math.max(0, Math.min(0.999, v));
        px(g, cx + x, cy + y, P.mist[Math.floor(v * P.mist.length)]);
      }
    // Rim and glint.
    for (let a = 0; a < Math.PI * 2; a += 0.02) px(g, cx + Math.cos(a) * r, cy + Math.sin(a) * r, "#120a24");
    px(g, cx - 14, cy - 15, "#ffffff", 3, 2);
    px(g, cx - 16, cy - 12, "#ffffff", 2, 2);

    // The ghost rises out of the ball once it speaks.
    const target = speaking ? 1 : 0;
    this.ghostAlpha += (target - this.ghostAlpha) * 0.04;
    if (this.ghostAlpha > 0.02) {
      const bob = Math.round(Math.sin(t * 1.8) * 2);
      const gx = cx - 15;
      const gy = 14 + bob + Math.round((1 - this.ghostAlpha) * 30);
      g.globalAlpha = this.ghostAlpha * 0.5;
      glow(g, cx, gy + 14, 20, "#33507a", 0.6);
      g.globalAlpha = this.ghostAlpha * (this.phase === "silent" ? 0.65 : 0.92);
      const rows = this.phase === "silent" ? GHOST_SILENT : GHOST;
      rows.forEach((row, y) => {
        for (let x = 0; x < row.length; x++) {
          const ch = row[x];
          if (ch === ".") continue;
          const c = ch === "b" ? P.ghost : ch === "c" ? P.ghostEye : P.ghostEdge;
          px(g, gx + x * 2, gy + y * 2, c, 2, 2);
        }
      });
      g.globalAlpha = 1;
    }
  }
}

// ---- The Ouija board: the planchette spells what the ghost says, letter by letter ----------------

const ROW1 = "ABCDEFGHIJKLM";
const ROW2 = "NOPQRSTUVWXYZ";

export class Ouija {
  readonly W = 192;
  readonly H = 60;
  private g: CanvasRenderingContext2D;
  private spots = new Map<string, [number, number]>();
  private queue: string[] = [];
  private pos: [number, number] = [96, 44];
  private target: [number, number] = [96, 44];
  private dwell = 0;
  private lit: string | null = null;
  private last = performance.now();

  constructor(canvas: HTMLCanvasElement) {
    canvas.width = this.W;
    canvas.height = this.H;
    this.g = canvas.getContext("2d")!;
    [...ROW1].forEach((ch, i) => this.spots.set(ch, [18 + i * 12.8, 25]));
    [...ROW2].forEach((ch, i) => this.spots.set(ch, [18 + i * 12.8, 38]));
    this.spots.set("YES", [22, 10]);
    this.spots.set("NO", [170, 10]);
    this.spots.set("GOODBYE", [96, 52]);
    const loop = (now: number) => {
      this.step(Math.min(0.05, (now - this.last) / 1000));
      this.last = now;
      this.draw();
      requestAnimationFrame(loop);
    };
    document.fonts?.ready.then(() => this.draw());
    requestAnimationFrame(loop);
  }

  /** Spell a word (letters only), then rest on a final spot such as GOODBYE. */
  spell(word: string, end?: "YES" | "NO" | "GOODBYE") {
    this.queue = [...word.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 12)];
    if (end) this.queue.push(end);
    if (end !== "GOODBYE") this.queue.push("GOODBYE");
  }

  say(spot: "YES" | "NO" | "GOODBYE") {
    this.queue = spot === "GOODBYE" ? [spot] : [spot, "GOODBYE"];
  }

  wander() {
    this.queue = [];
    this.target = [96 + Math.sin(performance.now() / 700) * 40, 32];
  }

  private step(dt: number) {
    const [x, y] = this.pos;
    const [tx, ty] = this.target;
    const k = Math.min(1, dt * 6);
    this.pos = [x + (tx - x) * k, y + (ty - y) * k];
    const near = Math.hypot(tx - x, ty - y) < 1.5;
    if (near) this.dwell += dt;
    if (near && this.dwell > 0.45 && this.queue.length) {
      const next = this.queue.shift()!;
      const spot = this.spots.get(next);
      if (spot) this.target = [spot[0], spot[1] + 3];
      this.lit = next;
      this.dwell = 0;
    }
  }

  private draw() {
    const g = this.g;
    const { W, H } = this;
    g.imageSmoothingEnabled = false;
    px(g, 0, 0, P.night, W, H);
    px(g, 2, 2, P.woodEdge, W - 4, H - 4);
    px(g, 3, 3, P.wood, W - 6, H - 6);
    for (let y = 4; y < H - 4; y += 5) px(g, 4, y, P.woodHi, W - 8, 1);
    g.font = '8px "Press Start 2P", monospace';
    g.textAlign = "center";
    g.textBaseline = "middle";
    for (const [k, [x, y]] of this.spots) {
      g.fillStyle = k === this.lit ? "#ffffff" : k.length > 1 ? P.letterDim : P.letter;
      g.font = k.length > 1 ? '6px "Press Start 2P", monospace' : '8px "Press Start 2P", monospace';
      g.fillText(k, x, y);
    }
    // Planchette: a teardrop with a window over the letter.
    const [x, y] = this.pos;
    g.fillStyle = "rgba(240, 220, 190, 0.85)";
    g.beginPath();
    g.moveTo(x, y - 12);
    g.quadraticCurveTo(x + 11, y - 4, x + 7, y + 8);
    g.lineTo(x - 7, y + 8);
    g.quadraticCurveTo(x - 11, y - 4, x, y - 12);
    g.fill();
    g.fillStyle = "rgba(13, 10, 26, 0.0)";
    g.globalCompositeOperation = "destination-out";
    g.beginPath();
    g.arc(x, y - 3, 3.5, 0, Math.PI * 2);
    g.fill();
    g.globalCompositeOperation = "source-over";
    g.strokeStyle = P.brass;
    g.lineWidth = 1;
    g.beginPath();
    g.arc(x, y - 3, 4, 0, Math.PI * 2);
    g.stroke();
  }
}
