// The Ouija board. The ghost moves the planchette to spell its name; the visitor can move it too.
//
// Drag the planchette (mouse or touch) and rest it on a spot for a moment: letters spell, and YES, NO and
// GOODBYE are controls. Clicking a spot sends the planchette there. A drag takes over from a spelling ghost.
import { glow, P, px } from "./art";

export type Spot = string; // a letter, or "YES", "NO", "GOODBYE"

const ROW1 = "ABCDEFGHIJKLM";
const ROW2 = "NOPQRSTUVWXYZ";
const WORDS = ["YES", "NO", "GOODBYE"];
const REST_S = 0.45;
/** Where the planchette waits: between YES and NO, clear of every letter. */
const HOME: [number, number] = [96, 17];

export interface OuijaEvents {
  /** The visitor rested the planchette on a spot (never fired while the ghost spells). */
  onRest?: (spot: Spot) => void;
}

export class Ouija {
  readonly W = 192;
  readonly H = 60;
  private g: CanvasRenderingContext2D;
  private spots = new Map<string, [number, number]>();
  private queue: string[] = [];
  private pos: [number, number] = [...HOME];
  private target: [number, number] = [...HOME];
  private dwell = 0;
  private lit: string | null = null;
  private hover: string | null = null;
  private last = performance.now();
  private dragging = false;
  private grab: [number, number] = [0, 0];
  private reported: string | null = null;
  private wandering = false;
  private ghostMoving = false;
  private touched = false; // nothing counts until the visitor has touched the board

  constructor(
    private canvas: HTMLCanvasElement,
    private events: OuijaEvents = {},
  ) {
    canvas.width = this.W;
    canvas.height = this.H;
    this.g = canvas.getContext("2d")!;
    [...ROW1].forEach((ch, i) => this.spots.set(ch, [18 + i * 12.8, 25]));
    [...ROW2].forEach((ch, i) => this.spots.set(ch, [18 + i * 12.8, 38]));
    this.spots.set("YES", [26, 10]);
    this.spots.set("NO", [166, 10]);
    this.spots.set("GOODBYE", [96, 52]);
    canvas.style.touchAction = "none";
    canvas.addEventListener("pointerdown", (e) => this.down(e));
    canvas.addEventListener("pointermove", (e) => this.move(e));
    canvas.addEventListener("pointerup", (e) => this.up(e));
    canvas.addEventListener("pointercancel", () => (this.dragging = false));
    canvas.addEventListener("pointerleave", () => (this.hover = null));
    const loop = (now: number) => {
      this.step(Math.min(0.05, (now - this.last) / 1000));
      this.last = now;
      this.draw();
      requestAnimationFrame(loop);
    };
    document.fonts?.ready.then(() => this.draw());
    requestAnimationFrame(loop);
  }

  /** The ghost spells a word (letters only), rests on `end`, then says GOODBYE. */
  spell(word: string, end?: "YES" | "NO") {
    this.queue = [...word.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 12)];
    if (end) this.queue.push(end);
    this.queue.push("GOODBYE", "HOME");
    this.wandering = false;
    this.ghostMoving = true;
  }

  say(spot: "YES" | "NO" | "GOODBYE") {
    this.queue = spot === "GOODBYE" ? [spot, "HOME"] : [spot, "GOODBYE", "HOME"];
    this.wandering = false;
    this.ghostMoving = true;
  }

  /** Drift over the board while the séance runs. */
  wander() {
    this.queue = [];
    this.wandering = true;
    this.ghostMoving = true;
  }

  private toBoard(e: PointerEvent): [number, number] {
    const r = this.canvas.getBoundingClientRect();
    return [((e.clientX - r.left) * this.W) / r.width, ((e.clientY - r.top) * this.H) / r.height];
  }

  private spotAt(x: number, y: number): string | null {
    let best: string | null = null;
    let bestD = Infinity;
    for (const [k, [sx, sy]] of this.spots) {
      const reach = WORDS.includes(k) ? 13 : 6.4;
      const d = Math.hypot(sx - x, sy - y);
      if (d < reach && d < bestD) {
        best = k;
        bestD = d;
      }
    }
    return best;
  }

  private onPlanchette(x: number, y: number): boolean {
    return Math.hypot(this.pos[0] - x, this.pos[1] - 2 - y) < 11;
  }

  /** The visitor takes the planchette from the ghost. */
  private takeOver() {
    this.queue = [];
    this.wandering = false;
    this.ghostMoving = false;
    this.reported = this.spotAt(this.pos[0], this.pos[1] - 3);
  }

  private down(e: PointerEvent) {
    const [x, y] = this.toBoard(e);
    this.canvas.setPointerCapture?.(e.pointerId);
    this.takeOver();
    this.touched = true;
    if (this.onPlanchette(x, y)) {
      this.dragging = true;
      this.grab = [this.pos[0] - x, this.pos[1] - y];
      return;
    }
    // A click on a spot: the planchette glides there and the spot counts at once.
    const s = this.spotAt(x, y);
    if (s) {
      this.target = this.windowOver(s);
      this.reported = s;
      this.events.onRest?.(s);
    }
  }

  private move(e: PointerEvent) {
    const [x, y] = this.toBoard(e);
    if (this.dragging) {
      this.pos = [Math.max(8, Math.min(this.W - 8, x + this.grab[0])), Math.max(10, Math.min(this.H - 6, y + this.grab[1]))];
      this.target = this.pos;
      this.canvas.style.cursor = "grabbing";
      return;
    }
    this.hover = this.spotAt(x, y);
    this.canvas.style.cursor = this.onPlanchette(x, y) ? "grab" : this.hover ? "pointer" : "default";
  }

  private up(e: PointerEvent) {
    this.dragging = false;
    this.canvas.releasePointerCapture?.(e.pointerId);
  }

  /** Where the planchette sits so that its window is over a spot. */
  private windowOver(s: string): [number, number] {
    if (s === "HOME") return [...HOME];
    const [sx, sy] = this.spots.get(s)!;
    return [sx, sy + 3];
  }

  private step(dt: number) {
    if (this.wandering) {
      const t = performance.now() / 1000;
      this.target = [96 + Math.sin(t * 0.9) * 62, 31 + Math.sin(t * 1.7) * 7];
    }
    if (!this.dragging) {
      const k = Math.min(1, dt * 6);
      this.pos = [this.pos[0] + (this.target[0] - this.pos[0]) * k, this.pos[1] + (this.target[1] - this.pos[1]) * k];
    }
    const under = this.spotAt(this.pos[0], this.pos[1] - 3);
    const settled = this.dragging || Math.hypot(this.target[0] - this.pos[0], this.target[1] - this.pos[1]) < 1.5;
    this.dwell = settled && under !== null && under === this.lit ? this.dwell + dt : 0;
    this.lit = under;

    if (this.ghostMoving) {
      // The ghost's spelling: pause on each spot, then glide to the next.
      if (this.queue.length && (settled || under === null) && (this.dwell > REST_S || this.lit === null)) {
        this.target = this.windowOver(this.queue.shift()!);
        this.dwell = 0;
      } else if (!this.queue.length && !this.wandering && settled && (under === null || this.dwell > REST_S)) {
        this.ghostMoving = false;
        this.reported = under; // where the ghost left it is not the visitor's choice
      }
      return;
    }
    // The visitor's hand: a spot counts once the planchette has rested on it.
    if (!this.touched) return;
    if (under === null) this.reported = null;
    else if (this.dwell > REST_S && this.reported !== under) {
      this.reported = under;
      this.events.onRest?.(under);
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
    // A sun by YES and a moon by NO, as on an old board.
    glow(g, 10, 10, 4, P.brassHi, 1);
    glow(g, 182, 10, 4, "#c8d0e8", 1);
    px(g, 183, 8, P.wood, 2, 4);
    g.textAlign = "center";
    g.textBaseline = "middle";
    for (const [k, [x, y]] of this.spots) {
      const word = WORDS.includes(k);
      const on = k === this.lit;
      if (on) glow(g, Math.round(x), Math.round(y), word ? 10 : 6, "#8a5a2a", 0.85);
      g.fillStyle = on ? "#ffffff" : k === this.hover ? "#fff6d8" : word ? P.letterDim : P.letter;
      g.font = word ? '6px "Press Start 2P", monospace' : '8px "Press Start 2P", monospace';
      g.fillText(k, x, y);
    }
    // The planchette: a teardrop with a window over the spot.
    const [x, y] = this.pos;
    g.fillStyle = this.dragging ? "rgba(255, 240, 214, 0.95)" : "rgba(240, 220, 190, 0.85)";
    g.beginPath();
    g.moveTo(x, y - 12);
    g.quadraticCurveTo(x + 11, y - 4, x + 7, y + 8);
    g.lineTo(x - 7, y + 8);
    g.quadraticCurveTo(x - 11, y - 4, x, y - 12);
    g.fill();
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
