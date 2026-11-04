import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from './Icons';
import type { Simulation } from './types';
import { buildStateWorldNodes, hammingWeight } from './QuantumStateWorldModel';

const TAU = Math.PI * 2;
const BASE_NODE_RADIUS = 6;
const PROBABILITY_RADIUS = 28;

export function QuantumStateWorld({ run }: { run: Simulation }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const angleRef = useRef(0.35);
  const dragRef = useRef<{ x: number; angle: number } | null>(null);
  const [orbiting, setOrbiting] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [showAccessibleData, setShowAccessibleData] = useState(false);
  const nodes = useMemo(() => buildStateWorldNodes(run), [run]);
  const occupiedNodes = useMemo(() => nodes.filter(node => node.probability > 1e-8 || node.measured > 0), [nodes]);
  const visibleNodes = useMemo(() => occupiedNodes.slice(0, 96), [occupiedNodes]);
  const dominant = occupiedNodes[0];

  useEffect(() => setSelected(null), [run.id]);

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
      if (orbiting && !reducedMotion && !dragRef.current) angleRef.current += delta * 0.00012;

      context.clearRect(0, 0, width, height);
      const cx = width / 2;
      const cy = height * 0.5;
      const radius = Math.min(width * 0.36, height * 0.42, 260);
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

      const projected = visibleNodes.map((node) => {
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

      projected.forEach((node) => {
        const idealRadius = (BASE_NODE_RADIUS + Math.sqrt(node.probability) * PROBABILITY_RADIUS) * node.scale;
        const measuredRadius = (BASE_NODE_RADIUS + Math.sqrt(node.measured) * PROBABILITY_RADIUS) * node.scale;
        const glowRadius = Math.max(idealRadius, measuredRadius) * 2.2;
        const glow = context.createRadialGradient(node.px, node.py, 0, node.px, node.py, glowRadius);
        glow.addColorStop(0, 'rgba(141, 216, 255, 0.28)');
        glow.addColorStop(0.45, 'rgba(95, 159, 232, 0.1)');
        glow.addColorStop(1, 'rgba(95, 159, 232, 0)');
        context.fillStyle = glow;
        context.beginPath();
        context.arc(node.px, node.py, glowRadius, 0, TAU);
        context.fill();

        const core = context.createRadialGradient(
          node.px - idealRadius * 0.35, node.py - idealRadius * 0.35, 0,
          node.px, node.py, idealRadius,
        );
        core.addColorStop(0, selected === node.state ? '#ffffff' : '#e8f8ff');
        core.addColorStop(0.52, '#90d9ff');
        core.addColorStop(1, '#3475ad');
        context.fillStyle = core;
        context.strokeStyle = selected === node.state ? '#ffffff' : 'rgba(228, 244, 255, 0.85)';
        context.lineWidth = selected === node.state ? 2.5 : 1;
        context.beginPath();
        context.arc(node.px, node.py, idealRadius, 0, TAU);
        context.fill();
        context.stroke();

        if (node.measured > 0) {
          context.beginPath();
          context.arc(node.px, node.py, measuredRadius + 3, 0, TAU);
          context.strokeStyle = '#d6adff';
          context.lineWidth = selected === node.state ? 3 : 2;
          context.stroke();
        }
      });

      // Keep a small, collision-free set of labels readable while orbiting.
      // Every outcome, including zeros, remains available in the exact table.
      const topStates = new Set(visibleNodes.slice(0, 10).map(node => node.state));
      const priority = [
        ...projected.filter(node => node.state === selected),
        ...projected.filter(node => node.state !== selected && topStates.has(node.state)),
      ];
      const placed: Array<{ left: number; right: number; top: number; bottom: number }> = [];
      for (const node of priority) {
        const label = `c=${node.state}`;
        context.font = `${node.state === selected ? 700 : 600} 12px ui-monospace, Consolas, monospace`;
        const labelWidth = context.measureText(label).width + 14;
        const markerRadius = (BASE_NODE_RADIUS + Math.sqrt(Math.max(node.probability, node.measured)) * PROBABILITY_RADIUS) * node.scale;
        const labelY = node.py - markerRadius - 13;
        const box = { left: node.px - labelWidth / 2, right: node.px + labelWidth / 2, top: labelY - 15, bottom: labelY + 4 };
        if (box.left < 4 || box.right > width - 4 || box.top < 4 || box.bottom > height - 4) continue;
        if (placed.some(other => box.left < other.right && box.right > other.left && box.top < other.bottom && box.bottom > other.top)) continue;
        placed.push(box);
        context.fillStyle = 'rgba(7, 18, 33, 0.87)';
        context.fillRect(box.left, box.top, labelWidth, 19);
        context.fillStyle = '#f8fbff';
        context.textAlign = 'center';
        context.fillText(label, node.px, labelY);
      }
      frameRef.current = requestAnimationFrame(render);
    };
    frameRef.current = requestAnimationFrame(render);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      observer.disconnect();
      motion.removeEventListener('change', onMotion);
    };
  }, [visibleNodes, orbiting, selected]);

  const selectAt = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas || visibleNodes.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const cx = rect.width / 2;
    const cy = rect.height * 0.5;
    const radius = Math.min(rect.width * 0.36, rect.height * 0.42, 260);
    const angle = angleRef.current;
    const closest = visibleNodes.reduce<{ state: string; distance: number } | null>((best, node) => {
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
          <h3>Measurement outcome orbit</h3>
          <p>
            Solid blue size tracks noiseless ideal probability; the violet outline tracks sampled frequency.
            Latitude groups outcomes by their number of 1 bits. This layout is illustrative; numerical results are below.
          </p>
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
          aria-label={`Interactive outcome orbit showing ${visibleNodes.length} of ${nodes.length} classical outcomes; exact values are below`}
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
      </div>
      <div className="quantum-world-readout" aria-live="polite">
        <span>SELECTED CLASSICAL OUTCOME</span>
        <strong>c = {selectedNode?.state ?? '—'}</strong>
        <dl>
          <div><dt>Ideal</dt><dd>{((selectedNode?.probability ?? 0) * 100).toFixed(6)}%</dd></div>
          <div><dt>Measured</dt><dd>{((selectedNode?.measured ?? 0) * 100).toFixed(6)}%</dd></div>
          <div><dt>Shots</dt><dd>{run.counts[selectedNode?.state ?? ''] ?? 0} / {run.shots}</dd></div>
          <div><dt>1 bits</dt><dd>{selectedNode ? hammingWeight(selectedNode.state) : '—'}</dd></div>
          <div><dt title="Relative to the dominant ideal basis amplitude; available only when one basis amplitude maps to this classical outcome">Relative ideal phase</dt><dd>{selectedNode?.phase !== null && selectedNode?.phase !== undefined ? `${(selectedNode.phase / Math.PI).toFixed(4)}π` : '—'}</dd></div>
        </dl>
      </div>
      <div className="quantum-world-footer">
        <span><i className="world-dot ideal" />Solid: ideal probability</span>
        <span><i className="world-ring" />Outline: measured frequency</span>
        {occupiedNodes.length > visibleNodes.length && <span>Showing {visibleNodes.length} of {occupiedNodes.length} nonzero outcomes</span>}
        <span>Counts exact · percentages rounded to 6 decimals</span>
        <span>Drag to orbit · click a node to inspect</span>
      </div>
      <details className="world-accessible-data" onToggle={event => setShowAccessibleData(event.currentTarget.open)}>
        <summary>All {nodes.length} classical outcomes · including zeros</summary>
        {showAccessibleData && <table><thead><tr><th scope="col">Classical outcome</th><th scope="col">Ideal</th><th scope="col">Measured</th><th scope="col">Counts</th></tr></thead><tbody>
          {nodes.map((node) => <tr key={node.state}><th scope="row"><button type="button" className="world-state-select" onClick={() => setSelected(node.state)}>c = {node.state}</button></th><td>{(node.probability * 100).toFixed(6)}%</td><td>{(node.measured * 100).toFixed(6)}%</td><td>{run.counts[node.state] ?? 0}</td></tr>)}
        </tbody></table>}
      </details>
    </div>
  );
}
