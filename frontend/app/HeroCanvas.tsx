"use client";

import { useEffect, useRef } from "react";

export default function HeroCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const SRC = { x: 110, y: 170 };
    const VAULT = { x: 0, y: 0, w: 210, h: 96 };
    const BEST = { x: 0, y: 0, w: 210, h: 96 };
    const APY_TARGET = 5.12;
    const TX_TARGET = 4;
    const MAX_PARTS = 40;

    let parts: { x: number; y: number; vx: number; vy: number; r: number; c: string }[] = [];
    let t = 0;
    let acc = 0;
    let spawned = 0;
    let apy = 0;
    let txCount = 0;
    let done = false;
    let raf = 0;

    function resize() {
      const r = cv.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      cv.width = r.width * dpr;
      cv.height = r.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      layout();
    }

    function layout() {
      const w = cv.getBoundingClientRect().width;
      const h = cv.getBoundingClientRect().height;
      VAULT.x = w - 240;
      VAULT.y = h / 2 - 48;
      SRC.x = 110;
      SRC.y = h / 2;
      BEST.x = w / 2 - 105;
      BEST.y = h / 2 - 48;
    }

    function spawn() {
      parts.push({
        x: SRC.x,
        y: SRC.y,
        vx: Math.random() * 2.4 + 1.4,
        vy: (Math.random() - 0.5) * 1.6,
        r: Math.random() * 2.2 + 1.2,
        c: Math.random() < 0.72 ? "#533afd" : "#ea2261",
      });
    }

    function rrect(x: number, y: number, w: number, h: number, r: number) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    }

    function draw() {
      const w = cv.getBoundingClientRect().width;
      const h = cv.getBoundingClientRect().height;
      ctx.clearRect(0, 0, w, h);
      ctx.strokeStyle = "rgba(83,58,253,0.05)";
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 36) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += 36) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
      ctx.fillStyle = "#fff";
      ctx.strokeStyle = "#d6d9fc";
      ctx.lineWidth = 1;
      rrect(SRC.x - 86, SRC.y - 34, 96, 68, 6);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#061b31";
      ctx.font = "600 11px Source Sans 3";
      ctx.fillText("ORG WALLET", SRC.x - 64, SRC.y - 12);
      ctx.fillStyle = "#64748d";
      ctx.font = "400 12px Source Code Pro";
      ctx.fillText("1,890 USDC", SRC.x - 64, SRC.y + 10);
      ctx.fillStyle = "#fff";
      ctx.strokeStyle = "#b9b9f9";
      rrect(BEST.x, BEST.y, BEST.w, BEST.h, 6);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#533afd";
      ctx.font = "600 10px Source Sans 3";
      ctx.fillText("RANK #1 · SKY SAVINGS", BEST.x + 14, BEST.y + 22);
      ctx.fillStyle = "#061b31";
      ctx.font = "300 22px Source Sans 3";
      ctx.fillText(apy.toFixed(2) + "% APY", BEST.x + 14, BEST.y + 52);
      ctx.fillStyle = "#108c3d";
      ctx.font = "400 10px Source Code Pro";
      ctx.fillText(txCount > 0 ? "✓ deposit sponsored x" + txCount : "waiting for flow…", BEST.x + 14, BEST.y + 74);
      ctx.fillStyle = "#1c1e54";
      rrect(VAULT.x, VAULT.y, VAULT.w, VAULT.h, 6);
      ctx.fill();
      ctx.fillStyle = "#b9b9f9";
      ctx.font = "600 10px Source Sans 3";
      ctx.fillText("KEEPERHUB EXECUTION", VAULT.x + 14, VAULT.y + 22);
      ctx.fillStyle = "rgba(255,255,255,0.85)";
      ctx.font = "300 18px Source Sans 3";
      ctx.fillText("gate → sponsored", VAULT.x + 14, VAULT.y + 50);
      ctx.fillStyle = "rgba(255,255,255,0.5)";
      ctx.font = "400 10px Source Code Pro";
      ctx.fillText("contract-call · audit", VAULT.x + 14, VAULT.y + 74);
      for (const p of parts) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = p.c;
        ctx.fill();
      }
      ctx.strokeStyle = "rgba(83,58,253,0.35)";
      ctx.setLineDash([4, 5]);
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(SRC.x + 10, SRC.y);
      ctx.lineTo(BEST.x - 6, BEST.y + BEST.h / 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(BEST.x + BEST.w + 6, BEST.y + BEST.h / 2);
      ctx.lineTo(VAULT.x - 6, VAULT.y + VAULT.h / 2);
      ctx.stroke();
      ctx.setLineDash([]);
      const apyEl = document.getElementById("apyStat");
      const txEl = document.getElementById("txStat");
      if (apyEl) apyEl.textContent = apy.toFixed(2) + "%";
      if (txEl) txEl.innerHTML = txCount + " <span>·</span>";
    }

    function tick() {
      t++;
      acc += 0.8;
      if (acc > 1 && spawned < MAX_PARTS) {
        acc = 0;
        spawned++;
        spawn();
      }
      const w = cv.getBoundingClientRect().width;
      for (let i = parts.length - 1; i >= 0; i--) {
        const p = parts[i];
        p.x += p.vx;
        p.y += p.vy;
        if (p.y > VAULT.y - 6 && p.y < VAULT.y + VAULT.h + 6 && p.x > VAULT.x - 2) {
          parts.splice(i, 1);
          continue;
        }
        if (p.x > w + 24) parts.splice(i, 1);
      }
      if (t > 25) apy = Math.min(APY_TARGET, apy + 0.05);
      if (spawned >= MAX_PARTS && parts.length === 0 && !done) {
        done = true;
        txCount = TX_TARGET;
      }
      draw();
      raf = requestAnimationFrame(tick);
    }

    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <div className="hero-visual">
      <div className="flow-stats">
        <div className="flow-stat">
          <div className="k">Best venue APY</div>
          <div className="v" id="apyStat">
            0.00%
          </div>
        </div>
        <div className="flow-stat">
          <div className="k">Sponsored txs</div>
          <div className="v" id="txStat">
            0 <span>·</span>
          </div>
        </div>
      </div>
      <div className="canvas-wrap">
        <canvas id="flow" ref={canvasRef}></canvas>
        <div className="canvas-caption">plow scan 0x1776…4Bf &nbsp;·&nbsp; 2 venues ranked &nbsp;·&nbsp; 1 deposit sponsored</div>
      </div>
    </div>
  );
}
