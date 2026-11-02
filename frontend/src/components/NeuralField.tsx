import { useEffect, useRef } from "react";

/**
 * Decorative topology inspired by the supplied terminal video.
 * This is geometry, NOT market observations or a confidence score.
 */
export function NeuralField({ paused }: { paused: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || (typeof navigator !== "undefined" && navigator.userAgent.includes("jsdom"))) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let animationId = 0;
    let lastFrame = -Infinity;
    const reduceMotion = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const stationary = paused || reduceMotion;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(0);
    };

    const draw = (time: number) => {
      ctx.clearRect(0, 0, width, height);
      const radius = Math.min(width * 0.29, height * 0.36);
      const tube = radius * 0.39;
      const turn = time * 0.00017 + 0.43;
      const tilt = -0.31 + Math.sin(time * 0.00014) * 0.09;
      const cy = height * 0.515;
      const cx = width * 0.5;

      // Structural arcs are symbolic labels/links, not a provider graph.
      for (let i = 0; i < 5; i++) {
        const startY = height * (0.18 + i * 0.155);
        ctx.beginPath();
        ctx.moveTo(0, startY);
        ctx.bezierCurveTo(width * 0.18, startY, width * 0.14, cy, width * 0.36, cy);
        ctx.strokeStyle = i % 2 ? "rgba(70,213,229,.15)" : "rgba(234,180,90,.13)";
        ctx.lineWidth = 0.8;
        ctx.stroke();
      }

      for (let row = 0; row < 30; row++) {
        const phi = row / 30 * Math.PI * 2;
        for (let col = 0; col < 52; col++) {
          const theta = col / 52 * Math.PI * 2;
          const ring = radius + tube * Math.cos(phi);
          const x = ring * Math.cos(theta);
          const y = tube * Math.sin(phi);
          const z = ring * Math.sin(theta);
          const x1 = x * Math.cos(turn) + z * Math.sin(turn);
          const z1 = -x * Math.sin(turn) + z * Math.cos(turn);
          const y1 = y * Math.cos(tilt) - z1 * Math.sin(tilt);
          const z2 = y * Math.sin(tilt) + z1 * Math.cos(tilt);
          const perspective = (radius * 4) / (radius * 4 - z2);
          const px = cx + x1 * perspective;
          const py = cy + y1 * perspective * 0.93;
          const depth = (z2 / (radius + tube) + 1) / 2;
          const gold = ((row * 17 + col * 7) % 19) < 5;
          const alpha = Math.min(0.88, 0.12 + depth * 0.60);
          ctx.fillStyle = gold ? `rgba(255,195,94,${alpha})` : `rgba(112,187,252,${alpha})`;
          ctx.beginPath();
          ctx.arc(px, py, Math.max(0.65, perspective * (gold ? 1.02 : 0.79)), 0, Math.PI * 2);
          ctx.fill();
        }
      }
      // Bright accent nodes in the central mesh.
      for (let j = 0; j < 13; j++) {
        const a = j / 13 * 6.283 + turn;
        const px = cx + Math.cos(a) * radius * 1.09;
        const py = cy + Math.sin(a) * tube * 0.9;
        ctx.fillStyle = j % 3 === 0 ? "#ffbf66" : "#7ce5ee";
        ctx.beginPath();
        ctx.arc(px, py, 1.8, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const animate = (time: number) => {
      if (time - lastFrame >= 32) {
        draw(time);
        lastFrame = time;
      }
      animationId = window.requestAnimationFrame(animate);
    };
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
    observer?.observe(canvas);
    window.addEventListener("resize", resize);
    resize();
    if (!stationary) animationId = window.requestAnimationFrame(animate);
    return () => {
      window.cancelAnimationFrame(animationId);
      observer?.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [paused]);

  return <canvas ref={canvasRef} className="cin-neural-canvas" role="img" aria-label="Decorative animated toroidal network. No live market data represented." />;
}
