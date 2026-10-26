import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './Icons';
import type { Simulation } from './types';

type Node3D = {
  state: string;
  probability: number;
  measured: number;
  x: number;
  y: number;
  z: number;
  phase: number;
};

const TAU = Math.PI * 2;

function stateSeed(state: string) {
  return [...state].reduce((value, bit, index) => value + (bit === '1' ? 31 : 13) * (index + 1), 17);
}

function buildNodes(run: Simulation): Node3D[] {
  const amplitudes = new Map((run.statevector_amplitudes ?? []).map((item) => [item.state, item]));
  const states = new Set([
    ...Object.keys(run.theoretical_probabilities),
    ...Object.keys(run.probabilities),
  ]);
  return [...states]
    .map((state) => {
      const seed = stateSeed(state);
      const fraction = (seed * 0.61803398875) % 1;
      const inclination = Math.acos(1 - 2 * ((seed * 0.17320508075) % 1));
      const azimuth = TAU * fraction;
      const amplitude = amplitudes.get(state);
      return {
        state,
        probability: run.theoretical_probabilities[state] ?? 0,
        measured: run.probabilities[state] ?? 0,
        x: Math.sin(inclination) * Math.cos(azimuth),
        y: Math.sin(inclination) * Math.sin(azimuth),
        z: Math.cos(inclination),
        phase: amplitude?.phase ?? azimuth,
      };
    })
    .filter((node) => node.probability > 1e-8 || node.measured > 0)
    .sort((a, b) => b.probability - a.probability);
}

export function QuantumStateWorld({ run }: { run: Simulation }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const angleRef = useRef(0.35);
  const dragRef = useRef<{ x: number; angle: number } | null>(null);
  const [orbiting, setOrbiting] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const nodes = useMemo(() => buildNodes(run), [run]);
  const dominant = nodes[0];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!context) return;
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let reducedMotion = motion.matches;
    let width = 1;
    let height = 1;
    let previous = performance.now();
    let elapsed = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const onMotion = (event: MediaQueryListEvent) => { reducedMotion = event.matches; };
    motion.addEventListener('change', onMotion);

    const render = (now: number) => {
      const delta = Math.min(40, now - previous);
      previous = now;
      elapsed += delta;
      if (orbiting && !reducedMotion && !dragRef.current) angleRef.current += delta * 0.00012;

      context.clearRect(0, 0, width, height);
      const cx = width / 2;
      const cy = height * 0.5;
      const radius = Math.min(width * 0.33, height * 0.38, 240);
      const angle = angleRef.current;

      const background = context.createRadialGradient(cx, cy, 10, cx, cy, radius * 1.55);
      background.addColorStop(0, 'rgba(41, 102, 148, 0.2)');
      background.addColorStop(0.52, 'rgba(33, 31, 89, 0.11)');
      background.addColorStop(1, 'rgba(3, 6, 17, 0)');
      context.fillStyle = background;
      context.fillRect(0, 0, width, height);

      context.save();
      context.translate(cx, cy);
      context.strokeStyle = 'rgba(117, 147, 191, 0.14)';
      context.lineWidth = 1;
      for (let ring = 1; ring <= 3; ring += 1) {
        context.beginPath();
        context.ellipse(0, 0, radius * (ring / 3), radius * 0.3 * (ring / 3), angle, 0, TAU);
        context.stroke();
      }
      context.restore();

      const projected = nodes.map((node) => {
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        const rx = node.x * cos - node.z * sin;
        const rz = node.x * sin + node.z * cos;
        const tilt = 0.34;
        const ry = node.y * Math.cos(tilt) - rz * Math.sin(tilt);
        const depth = node.y * Math.sin(tilt) + rz * Math.cos(tilt);
        const scale = 0.72 + (depth + 1) * 0.18;
        return { ...node, px: cx + rx * radius, py: cy + ry * radius, depth, scale };
      }).sort((a, b) => a.depth - b.depth);

      const active = projected.filter((node) => node.probability > 0.015);
      for (let first = 0; first < active.length; first += 1) {
        for (let second = first + 1; second < active.length; second += 1) {
          const a = active[first];
          const b = active[second];
          const gradient = context.createLinearGradient(a.px, a.py, b.px, b.py);
          gradient.addColorStop(0, 'rgba(87, 217, 255, 0.05)');
          gradient.addColorStop(0.5, 'rgba(154, 131, 255, 0.3)');
          gradient.addColorStop(1, 'rgba(87, 217, 255, 0.05)');
          context.strokeStyle = gradient;
          context.lineWidth = Math.max(0.7, Math.min(a.probability, b.probability) * 5);
          context.beginPath();
          context.moveTo(a.px, a.py);
          context.lineTo(b.px, b.py);
          context.stroke();
        }
      }

      projected.forEach((node) => {
        const pulse = reducedMotion ? 0 : Math.sin(elapsed * 0.0022 + node.phase) * 1.6;
        const size = (5 + Math.sqrt(Math.max(node.probability, node.measured)) * 22 + pulse) * node.scale;
        const hue = ((node.phase / TAU) * 360 + 220 + 360) % 360;
        const glow = context.createRadialGradient(node.px, node.py, 0, node.px, node.py, size * 2.9);
        glow.addColorStop(0, `hsla(${hue}, 95%, 72%, 0.7)`);
        glow.addColorStop(0.32, `hsla(${hue}, 90%, 58%, 0.22)`);
        glow.addColorStop(1, `hsla(${hue}, 90%, 55%, 0)`);
        context.fillStyle = glow;
        context.beginPath();
        context.arc(node.px, node.py, size * 2.9, 0, TAU);
        context.fill();

        context.fillStyle = selected === node.state ? '#ffffff' : `hsl(${hue} 92% 67%)`;
        context.strokeStyle = selected === node.state ? '#57d9ff' : 'rgba(238, 246, 255, 0.72)';
        context.lineWidth = selected === node.state ? 3 : 1;
        context.beginPath();
        context.arc(node.px, node.py, size, 0, TAU);
        context.fill();
        context.stroke();

        if (node.probability >= 0.01 || selected === node.state) {
          context.font = `${selected === node.state ? 700 : 600} 11px Inter, sans-serif`;
          context.fillStyle = 'rgba(242, 248, 255, 0.92)';
          context.textAlign = 'center';
          context.fillText(`|${node.state}⟩`, node.px, node.py - size - 9);
        }
      });
      frameRef.current = requestAnimationFrame(render);
    };
    frameRef.current = requestAnimationFrame(render);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      observer.disconnect();
      motion.removeEventListener('change', onMotion);
    };
  }, [nodes, orbiting, selected]);

  const selectAt = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas || nodes.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height * 0.5;
    const radius = Math.min(rect.width * 0.33, rect.height * 0.38, 240);
    const angle = angleRef.current;
    const closest = nodes.reduce<{ state: string; distance: number } | null>((best, node) => {
      const rx = node.x * Math.cos(angle) - node.z * Math.sin(angle);
      const rz = node.x * Math.sin(angle) + node.z * Math.cos(angle);
      const ry = node.y * Math.cos(0.34) - rz * Math.sin(0.34);
      const distance = Math.hypot(rect.left + cx + rx * radius - clientX, rect.top + cy + ry * radius - clientY);
      return !best || distance < best.distance ? { state: node.state, distance } : best;
    }, null);
    if (closest && closest.distance < 38) setSelected(closest.state);
  };

  const selectedNode = nodes.find((node) => node.state === selected) ?? dominant;
  return (
    <div className="quantum-world-card">
      <div className="quantum-world-head">
        <div>
          <span className="eyebrow">SIMULATION STATE WORLD</span>
          <h3>Navigate the outcome constellation</h3>
          <p>Node size follows ideal probability; glow responds to finite-shot measurements. Lines connect simultaneously probable outcomes.</p>
        </div>
        <button type="button" className={`matrix-toggle-btn ${orbiting ? 'active' : ''}`} onClick={() => setOrbiting((value) => !value)} aria-pressed={orbiting}>
          <Icon name={orbiting ? 'refresh' : 'play'} size={12} />
          {orbiting ? 'Pause orbit' : 'Resume orbit'}
        </button>
      </div>
      <div className="quantum-world-stage">
        <canvas
          ref={canvasRef}
          className="quantum-world-canvas"
          aria-label={`Interactive three-dimensional measurement world with ${nodes.length} visible basis states`}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            dragRef.current = { x: event.clientX, angle: angleRef.current };
          }}
          onPointerMove={(event) => {
            if (dragRef.current) angleRef.current = dragRef.current.angle + (event.clientX - dragRef.current.x) * 0.008;
          }}
          onPointerUp={(event) => {
            const moved = dragRef.current ? Math.abs(event.clientX - dragRef.current.x) : 0;
            dragRef.current = null;
            if (moved < 5) selectAt(event.clientX, event.clientY);
          }}
          onPointerCancel={() => { dragRef.current = null; }}
        />
        <div className="quantum-world-reticle" aria-hidden="true" />
        <div className="quantum-world-axis" aria-hidden="true"><span>X</span><span>Y</span><span>Z</span></div>
      </div>
      <div className="quantum-world-readout">
        <span>SELECTED BASIS STATE</span>
        <strong>|{selectedNode?.state ?? '—'}⟩</strong>
        <dl>
          <div><dt>Ideal</dt><dd>{((selectedNode?.probability ?? 0) * 100).toFixed(3)}%</dd></div>
          <div><dt>Measured</dt><dd>{((selectedNode?.measured ?? 0) * 100).toFixed(3)}%</dd></div>
          <div><dt>Shots</dt><dd>{run.counts[selectedNode?.state ?? ''] ?? 0}</dd></div>
        </dl>
      </div>
      <div className="quantum-world-footer">
        <span><i className="world-dot ideal" />Ideal statevector probability</span>
        <span><i className="world-line" />Co-present outcome relationship</span>
        <span>Drag to orbit · click a node to inspect</span>
      </div>
      <details className="world-accessible-data">
        <summary>Accessible state-world data</summary>
        <table><thead><tr><th>Basis state</th><th>Ideal</th><th>Measured</th><th>Counts</th></tr></thead><tbody>
          {nodes.map((node) => <tr key={node.state}><td>|{node.state}⟩</td><td>{(node.probability * 100).toFixed(4)}%</td><td>{(node.measured * 100).toFixed(4)}%</td><td>{run.counts[node.state] ?? 0}</td></tr>)}
        </tbody></table>
      </details>
    </div>
  );
}
