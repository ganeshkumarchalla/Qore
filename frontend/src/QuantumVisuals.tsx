import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons';
import type { BlochVector, StatevectorAmplitude, UnitaryCell } from './types';

// 3D rotation projection function
function rotate3D(
  x: number,
  y: number,
  z: number,
  pDeg: number,
  yDeg: number,
  cx: number,
  cy: number,
  R: number
) {
  const pRad = (pDeg * Math.PI) / 180;
  const yRad = (yDeg * Math.PI) / 180;

  // Yaw (rotation around Y in camera space)
  const x1 = x * Math.cos(yRad) + y * Math.sin(yRad);
  const y1 = -x * Math.sin(yRad) + y * Math.cos(yRad);
  const z1 = z;

  // Pitch (tilt up/down)
  const x2 = x1;
  const y2 = y1 * Math.cos(pRad) - z1 * Math.sin(pRad);
  const z2 = y1 * Math.sin(pRad) + z1 * Math.cos(pRad);

  return {
    px: cx + R * x2,
    py: cy - R * z2,
    depth: y2, // > 0 is towards viewer
  };
}

export function BlochSphereViewer({ vectors }: { vectors?: BlochVector[] }) {
  const reduceMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [selectedQubit, setSelectedQubit] = useState<number>(0);
  const [viewMode, setViewMode] = useState<'focused' | 'grid'>('focused');
  const [pitch, setPitch] = useState<number>(20);
  const [yaw, setYaw] = useState<number>(-35);
  const [autoOrbit, setAutoOrbit] = useState<boolean>(() => !reduceMotion);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragRef = useRef<{ startX: number; startY: number; startPitch: number; startYaw: number }>({
    startX: 0,
    startY: 0,
    startPitch: 20,
    startYaw: -35,
  });

  // Smooth continuous 3D orbit when enabled and not dragging
  useEffect(() => {
    if (!autoOrbit || isDragging) return;
    let animId: number;
    const step = () => {
      setYaw((prev) => (prev + 0.35) % 360);
      animId = requestAnimationFrame(step);
    };
    animId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animId);
  }, [autoOrbit, isDragging]);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const stopOrbit = (event: MediaQueryListEvent) => {
      if (event.matches) setAutoOrbit(false);
    };
    media.addEventListener('change', stopOrbit);
    return () => media.removeEventListener('change', stopOrbit);
  }, []);

  if (!vectors || vectors.length === 0) {
    return (
      <div className="quantum-empty">
        <Icon name="circuit" size={20} />
        <span>No statevector available (requires circuit ≤ 6 qubits).</span>
      </div>
    );
  }

  const active = vectors[selectedQubit] ?? vectors[0];
  const cx = 95;
  const cy = 95;
  const R = 70;

  // Compute 3D projected point for current state vector
  const vecProj = rotate3D(active.x, active.y, active.z, pitch, yaw, cx, cy, R);

  // Compute 3D projected poles
  const northProj = rotate3D(0, 0, 1, pitch, yaw, cx, cy, R);
  const southProj = rotate3D(0, 0, -1, pitch, yaw, cx, cy, R);
  const xPosProj = rotate3D(1, 0, 0, pitch, yaw, cx, cy, R);
  const xNegProj = rotate3D(-1, 0, 0, pitch, yaw, cx, cy, R);
  const yPosProj = rotate3D(0, 1, 0, pitch, yaw, cx, cy, R);
  const yNegProj = rotate3D(0, -1, 0, pitch, yaw, cx, cy, R);

  // Generate 3D Equator circle path
  const equatorPoints =
    Array.from({ length: 48 }, (_, i) => {
      const angle = (i / 48) * 2 * Math.PI;
      const pt = rotate3D(Math.cos(angle), Math.sin(angle), 0, pitch, yaw, cx, cy, R);
      return `${i === 0 ? 'M' : 'L'} ${pt.px.toFixed(2)} ${pt.py.toFixed(2)}`;
    }).join(' ') + ' Z';

  // Generate 3D Prime Meridian circle path
  const meridianPoints =
    Array.from({ length: 48 }, (_, i) => {
      const angle = (i / 48) * 2 * Math.PI;
      const pt = rotate3D(Math.cos(angle), 0, Math.sin(angle), pitch, yaw, cx, cy, R);
      return `${i === 0 ? 'M' : 'L'} ${pt.px.toFixed(2)} ${pt.py.toFixed(2)}`;
    }).join(' ') + ' Z';

  // Mouse drag handlers for full 3D interactive orbit
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startPitch: pitch,
      startYaw: yaw,
    };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    setYaw((dragRef.current.startYaw + dx * 0.7) % 360);
    setPitch(Math.max(-80, Math.min(80, dragRef.current.startPitch - dy * 0.7)));
  };

  const handleMouseUp = () => setIsDragging(false);

  return (
    <div className="bloch-viewer-card interactive-3d-card">
      <div className="bloch-tabs-bar spread">
        <div className="bloch-qubit-selector">
          <span className="bloch-label">REGISTER QUBITS:</span>
          <div className="qubit-pill-group">
            {vectors.map((v) => (
              <button
                key={v.qubit}
                type="button"
                className={`qubit-pill ${viewMode === 'focused' && selectedQubit === v.qubit ? 'active' : ''}`}
                onClick={() => {
                  setSelectedQubit(v.qubit);
                  setViewMode('focused');
                }}
              >
                q[{v.qubit}]
                <span className={`qubit-dot ${v.is_pure ? 'pure' : 'mixed'}`} />
              </button>
            ))}
          </div>
        </div>

        {/* 3D Orbit & Perspective Controls */}
        <div className="bloch-anim-controls">
          <div className="clean-segmented-control mini-seg">
            <button
              type="button"
              className={`seg-btn ${viewMode === 'focused' ? 'active' : ''}`}
              onClick={() => setViewMode('focused')}
              title="Inspect selected single qubit in detail"
            >
              Focused
            </button>
            <button
              type="button"
              className={`seg-btn ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              title="View all register qubits simultaneously"
            >
              All Qubits ({vectors.length})
            </button>
          </div>

          <button
            type="button"
            className={`anim-speed-btn ${autoOrbit ? 'active' : ''}`}
            onClick={() => setAutoOrbit(!autoOrbit)}
            title="Toggle smooth 3D auto orbit"
            aria-pressed={autoOrbit}
          >
            <Icon name="refresh" size={11} />
            <span>Orbit</span>
          </button>
          <button
            type="button"
            className="anim-speed-btn"
            onClick={() => {
              setPitch(20);
              setYaw(-35);
            }}
            title="Reset 3D camera angles"
          >
            <Icon name="cube" size={11} />
            <span>Reset 3D</span>
          </button>
        </div>
      </div>

      {viewMode === 'grid' ? (
        <div className="bloch-grid-gallery">
          {vectors.map((v) => {
            const vProj = rotate3D(v.x, v.y, v.z, pitch, yaw, 65, 65, 46);
            const nP = rotate3D(0, 0, 1, pitch, yaw, 65, 65, 46);
            const sP = rotate3D(0, 0, -1, pitch, yaw, 65, 65, 46);
            const eqPts =
              Array.from({ length: 32 }, (_, i) => {
                const a = (i / 32) * 2 * Math.PI;
                const pt = rotate3D(Math.cos(a), Math.sin(a), 0, pitch, yaw, 65, 65, 46);
                return `${i === 0 ? 'M' : 'L'} ${pt.px.toFixed(1)} ${pt.py.toFixed(1)}`;
              }).join(' ') + ' Z';
            return (
              <button
                type="button"
                key={v.qubit}
                className={`bloch-grid-card ${selectedQubit === v.qubit ? 'active' : ''}`}
                onClick={() => {
                  setSelectedQubit(v.qubit);
                  setViewMode('focused');
                }}
                title="Click to inspect qubit in focused 3D detail"
              >
                <div className="bloch-grid-card-head">
                  <span className="mono">q[{v.qubit}]</span>
                  <span className={`pill small ${v.is_pure ? 'success' : 'violet'}`}>
                    {v.is_pure ? 'Pure (|ψ⟩)' : 'Entangled (ρ)'}
                  </span>
                </div>
                <div className="bloch-grid-svg-wrap">
                  <svg viewBox="0 0 130 130" width="130" height="130" className="bloch-grid-svg">
                    <circle cx="65" cy="65" r="46" fill="rgba(15, 23, 42, 0.65)" stroke="rgba(56, 189, 248, 0.25)" strokeWidth="1" />
                    <path d={eqPts} fill="none" stroke="rgba(148, 163, 184, 0.3)" strokeDasharray="2 3" />
                    <line x1={nP.px} y1={nP.py} x2={sP.px} y2={sP.py} stroke="rgba(100, 116, 139, 0.3)" strokeDasharray="2 2" />
                    <line x1="65" y1="65" x2={vProj.px} y2={vProj.py} stroke="#38bdf8" strokeWidth="2.4" strokeLinecap="round" />
                    <circle cx={vProj.px} cy={vProj.py} r="4" fill="#38bdf8" stroke="#ffffff" strokeWidth="1.2" />
                    <text x={nP.px} y={nP.py - 4} fill="#38bdf8" fontSize="8.5" textAnchor="middle" fontWeight="bold">|0⟩</text>
                    <text x={sP.px} y={sP.py + 10} fill="#94a3b8" fontSize="8.5" textAnchor="middle">|1⟩</text>
                  </svg>
                </div>
                <div className="bloch-grid-card-foot mono">
                  <span>Purity: {v.purity.toFixed(3)}</span>
                  <span>θ: {((v.theta * 180) / Math.PI).toFixed(0)}°</span>
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="bloch-body">
          <div
            className={`bloch-svg-wrap ${isDragging ? 'grabbing' : 'grabbable'}`}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            title="Drag to rotate Bloch sphere in 3D space"
          >
            <svg viewBox="0 0 190 190" className="bloch-svg" width="190" height="190">
              <defs>
                <filter id="blochGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3.5" result="blur" />
                  <feMerge>
                    <feMergeNode in="blur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <radialGradient id="sphereRadial" cx="35%" cy="30%" r="70%">
                  <stop offset="0%" stopColor="#1e293b" stopOpacity="0.85" />
                  <stop offset="65%" stopColor="#0b1329" stopOpacity="0.95" />
                  <stop offset="100%" stopColor="#040714" stopOpacity="0.99" />
                </radialGradient>
                <linearGradient id="vectorGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#38bdf8" />
                  <stop offset="60%" stopColor="#818cf8" />
                  <stop offset="100%" stopColor="#c084fc" />
                </linearGradient>
              </defs>

              {/* Sphere Backdrop Body */}
              <circle cx={cx} cy={cy} r={R} fill="url(#sphereRadial)" stroke="#1e293b" strokeWidth="1.5" className="bloch-sphere-bg" />

              {/* 3D Coordinate Axes */}
              {/* Z-Axis (North-South) */}
              <line
                x1={southProj.px}
                y1={southProj.py}
                x2={northProj.px}
                y2={northProj.py}
                stroke="#334155"
                strokeWidth="1.2"
                strokeDasharray="2 2"
              />
              {/* X-Axis */}
              <line
                x1={xNegProj.px}
                y1={xNegProj.py}
                x2={xPosProj.px}
                y2={xPosProj.py}
                stroke="#334155"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              {/* Y-Axis */}
              <line
                x1={yNegProj.px}
                y1={yNegProj.py}
                x2={yPosProj.px}
                y2={yPosProj.py}
                stroke="#334155"
                strokeWidth="1"
                strokeDasharray="2 2"
              />

              {/* 3D Equator Ellipse */}
              <path d={equatorPoints} stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.35" fill="none" strokeDasharray="3 3" />

              {/* 3D Prime Meridian Ellipse */}
              <path d={meridianPoints} stroke="#818cf8" strokeWidth="1" strokeOpacity="0.3" fill="none" strokeDasharray="3 3" />

              {/* Pole State Labels */}
              <text x={northProj.px} y={northProj.py - 6} fill="#38bdf8" fontSize="10" textAnchor="middle" fontWeight="bold">
                |0⟩
              </text>
              <text x={southProj.px} y={southProj.py + 13} fill="#94a3b8" fontSize="10" textAnchor="middle">
                |1⟩
              </text>
              <text x={xPosProj.px + 7} y={xPosProj.py + 3} fill="#64748b" fontSize="8.5">
                |+⟩
              </text>

              {/* State Vector Arrow with 3D Depth Cueing */}
              <line
                x1={cx}
                y1={cy}
                x2={vecProj.px}
                y2={vecProj.py}
                stroke="url(#vectorGrad)"
                strokeWidth={vecProj.depth >= 0 ? '2.8' : '1.8'}
                strokeOpacity={vecProj.depth >= 0 ? 1 : 0.6}
                strokeLinecap="round"
              />

              {/* Vector Tip with Radiant Glow */}
              <circle
                cx={vecProj.px}
                cy={vecProj.py}
                r={vecProj.depth >= 0 ? 7 : 4}
                fill="#38bdf8"
                opacity={vecProj.depth >= 0 ? 0.35 : 0.15}
                filter="url(#blochGlow)"
              />
              <circle
                cx={vecProj.px}
                cy={vecProj.py}
                r={vecProj.depth >= 0 ? 4.5 : 3}
                fill="#38bdf8"
                stroke="#ffffff"
                strokeWidth="1.2"
              />
            </svg>
            <div className="bloch-3d-hint">Drag to rotate 3D</div>
          </div>

          <div className="bloch-metrics">
            <div className="bloch-metrics-header">
              <h4>Qubit q[{active.qubit}] 3D State</h4>
              <span className={`pill ${active.is_pure ? 'success' : 'violet'}`}>
                <span className="dot" />
                {active.is_pure ? 'Pure State (|ψ⟩)' : 'Entangled / Mixed (ρ)'}
              </span>
            </div>

            <div className="bloch-kv-grid">
              <div className="bloch-kv-cell">
                <span className="kv-label">⟨X⟩ Pauli-X</span>
                <span className="kv-val mono">{active.x >= 0 ? '+' : ''}{active.x.toFixed(4)}</span>
              </div>
              <div className="bloch-kv-cell">
                <span className="kv-label">⟨Y⟩ Pauli-Y</span>
                <span className="kv-val mono">{active.y >= 0 ? '+' : ''}{active.y.toFixed(4)}</span>
              </div>
              <div className="bloch-kv-cell">
                <span className="kv-label">⟨Z⟩ Pauli-Z</span>
                <span className="kv-val mono">{active.z >= 0 ? '+' : ''}{active.z.toFixed(4)}</span>
              </div>
              <div className="bloch-kv-cell">
                <span className="kv-label">Purity Tr(ρ²)</span>
                <span className="kv-val mono highlight">{active.purity.toFixed(4)}</span>
              </div>
              <div className="bloch-kv-cell">
                <span className="kv-label">Polar Angle (θ)</span>
                <span className="kv-val mono">{((active.theta * 180) / Math.PI).toFixed(1)}° ({(active.theta / Math.PI).toFixed(2)}π)</span>
              </div>
              <div className="bloch-kv-cell">
                <span className="kv-label">Azimuthal (φ)</span>
                <span className="kv-val mono">{((active.phi * 180) / Math.PI).toFixed(1)}° ({(active.phi / Math.PI).toFixed(2)}π)</span>
              </div>
            </div>

            {!active.is_pure && (
              <p className="bloch-note">
                <Icon name="info" size={13} />
                Qubit is entangled with other register qubits. Its partial trace reduced density matrix Tr<sub>other</sub>(ρ) is a mixed state inside the Bloch sphere (radius |r| &lt; 1).
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function UnitaryMatrixViewer({ matrix }: { matrix?: UnitaryCell[][] }) {
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number; cell: UnitaryCell } | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: number } | null>(null);
  const [phaseChroma, setPhaseChroma] = useState(true);

  if (!matrix || matrix.length === 0) {
    return (
      <div className="quantum-empty">
        <Icon name="circuit" size={20} />
        <span>Unitary operator calculation is available for circuits ≤ 4 qubits (max 16×16 matrix).</span>
      </div>
    );
  }

  const dim = matrix.length;
  const numQubits = Math.round(Math.log2(dim));
  const formatBasis = (idx: number) => idx.toString(2).padStart(numQubits, '0');

  const formatComplex = (c: UnitaryCell) => {
    if (c.magnitude < 0.001) return '0';
    if (Math.abs(c.imag) < 0.001) return c.real.toFixed(3);
    if (Math.abs(c.real) < 0.001) return `${c.imag.toFixed(3)}i`;
    return `${c.real.toFixed(2)}${c.imag >= 0 ? '+' : ''}${c.imag.toFixed(2)}i`;
  };

  return (
    <div className="unitary-viewer-card">
      <div className="unitary-header spread">
        <div>
          <div className="unitary-title-row">
            <h4>Full Unitary Operator Matrix (U)</h4>
            <span className="unitary-dim mono">{dim} × {dim} ({numQubits} Qubits)</span>
            <span className="unitary-verified-tag" title="Unitary verified: U† · U = I">
              <span className="verified-pulse-dot" />
              U† · U = I (Unitary)
            </span>
          </div>
        </div>

        <div className="unitary-controls">
          <button
            type="button"
            className={`matrix-toggle-btn ${phaseChroma ? 'active' : ''}`}
            onClick={() => setPhaseChroma(!phaseChroma)}
            title="Toggle complex phase color encoding"
          >
            <Icon name="spark" size={12} />
            <span>Phase Chroma</span>
          </button>
        </div>
      </div>

      {selectedCell && (
        <div className="selected-cell-info mono">
          ⟨{formatBasis(selectedCell.row)}| U |{formatBasis(selectedCell.col)}⟩ ={' '}
          <strong className="cell-amp-value">
            {selectedCell.cell.real >= 0 ? '+' : ''}{selectedCell.cell.real.toFixed(4)}{' '}
            {selectedCell.cell.imag >= 0 ? '+' : '-'}{Math.abs(selectedCell.cell.imag).toFixed(4)}i
          </strong>{' '}
          <span className="cell-mag">|U| = {selectedCell.cell.magnitude.toFixed(4)}</span>
          <span className="cell-phase">∠ = {(selectedCell.cell.phase / Math.PI).toFixed(3)}π rad</span>
        </div>
      )}

      <div className="matrix-table-wrap">
        <table className="unitary-matrix-table isometric-3d">
          <thead>
            <tr>
              <th className="corner-th">|row⟩ \ |col⟩</th>
              {matrix.map((_, colIdx) => (
                <th
                  key={colIdx}
                  className={`basis-th mono ${
                    hoveredCell?.col === colIdx || selectedCell?.col === colIdx ? 'laser-highlight' : ''
                  }`}
                >
                  |{formatBasis(colIdx)}⟩
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, rowIdx) => (
              <tr key={rowIdx}>
                <th
                  className={`basis-row-th mono ${
                    hoveredCell?.row === rowIdx || selectedCell?.row === rowIdx ? 'laser-highlight' : ''
                  }`}
                >
                  |{formatBasis(rowIdx)}⟩
                </th>
                {row.map((cell, colIdx) => {
                  const isSelected = selectedCell?.row === rowIdx && selectedCell?.col === colIdx;
                  const isHovered = hoveredCell?.row === rowIdx && hoveredCell?.col === colIdx;
                  const animDelay = (rowIdx * dim + colIdx) * 12;

                  // Complex phase to HSL hue mapping: phase in [-pi, pi] mapped to [0, 360]
                  const phaseDeg = Math.round(((cell.phase * 180) / Math.PI + 360) % 360);
                  const bgAlpha = Math.min(0.85, cell.magnitude * 0.7 + (cell.magnitude > 0.001 ? 0.08 : 0));

                  const bgColor =
                    cell.magnitude <= 0.001
                      ? 'transparent'
                      : phaseChroma
                      ? `hsla(${phaseDeg}, 75%, 45%, ${bgAlpha})`
                      : `rgba(56, 189, 248, ${bgAlpha})`;

                  const borderColor =
                    cell.magnitude > 0.001 && phaseChroma
                      ? `hsla(${phaseDeg}, 90%, 65%, 0.4)`
                      : 'transparent';

                  return (
                    <td
                      key={colIdx}
                      className={`matrix-cell mono ${isSelected ? 'selected' : ''} ${isHovered ? 'hovered' : ''}`}
                      style={{
                        backgroundColor: bgColor,
                        borderColor: borderColor,
                        color: cell.magnitude > 0.35 ? '#ffffff' : cell.magnitude > 0.001 ? '#93c5fd' : '#475569',
                        animationDelay: `${animDelay}ms`,
                      }}
                      onMouseEnter={() => setHoveredCell({ row: rowIdx, col: colIdx })}
                      onMouseLeave={() => setHoveredCell(null)}
                      onClick={() => setSelectedCell({ row: rowIdx, col: colIdx, cell })}
                      title={`|${formatBasis(rowIdx)}⟩ → |${formatBasis(colIdx)}⟩: ${formatComplex(cell)} (phase: ${(
                        cell.phase / Math.PI
                      ).toFixed(2)}π)`}
                    >
                      {formatComplex(cell)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="help">
        Values represent transition amplitudes ⟨i|U|j⟩. Cell hue indicates quantum phase angle, brightness indicates magnitude |U<sub>ij</sub>|.
      </p>
    </div>
  );
}

export function StatevectorAmplitudesViewer({ amplitudes }: { amplitudes?: StatevectorAmplitude[] }) {
  if (!amplitudes || amplitudes.length === 0) return null;

  return (
    <div className="amplitudes-viewer-card">
      <div className="section-head spread">
        <h4>Ideal Statevector Basis Amplitudes</h4>
        <span className="mini-tag">Pure State Decomposition</span>
      </div>
      <div className="amplitudes-list">
        {amplitudes.map((amp, idx) => {
          const phaseDeg = Math.round(((amp.phase * 180) / Math.PI + 360) % 360);
          return (
            <div
              key={amp.state}
              className="amplitude-row amp-animated"
              style={{ animationDelay: `${idx * 40}ms` }}
            >
              <span className="amp-basis mono font-semibold">|{amp.state}⟩</span>
              <div className="amp-bar-track">
                <div
                  className="amp-bar amp-bar-glow"
                  style={{
                    width: `${amp.probability * 100}%`,
                    background: `linear-gradient(90deg, hsla(${phaseDeg}, 80%, 50%, 0.8), #38bdf8)`,
                  }}
                />
              </div>
              <span className="amp-prob mono">{(amp.probability * 100).toFixed(2)}%</span>
              <span className="amp-complex mono">
                {amp.real >= 0 ? '+' : ''}{amp.real.toFixed(3)} {amp.imag >= 0 ? '+' : ''}{amp.imag.toFixed(3)}i
              </span>
              <span className="amp-phase mono">∠ {(amp.phase / Math.PI).toFixed(2)}π</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function QasmViewer({ qasm }: { qasm?: string }) {
  const [copied, setCopied] = useState(false);
  const copiedTimer = useRef<number | null>(null);

  useEffect(() => () => {
    if (copiedTimer.current !== null) window.clearTimeout(copiedTimer.current);
  }, []);

  if (!qasm) {
    return (
      <div className="quantum-empty">
        <Icon name="code" size={20} />
        <span>OpenQASM representation is generated automatically when valid gates are parsed.</span>
      </div>
    );
  }

  const copyQasm = async () => {
    await navigator.clipboard.writeText(qasm);
    setCopied(true);
    if (copiedTimer.current !== null) window.clearTimeout(copiedTimer.current);
    copiedTimer.current = window.setTimeout(() => setCopied(false), 2000);
  };

  const downloadQasm = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([qasm], { type: 'text/plain' }));
    a.download = 'circuit.qasm';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

  return (
    <div className="qasm-viewer-card">
      <div className="section-head spread">
        <div className="qasm-title">
          <Icon name="code" size={15} />
          <h4>OpenQASM 2.0 Export</h4>
        </div>
        <div className="qasm-actions">
          <button type="button" className="button secondary small" onClick={() => void copyQasm()}>
            <Icon name={copied ? 'check' : 'copy'} size={13} />
            {copied ? 'Copied!' : 'Copy QASM'}
          </button>
          <button type="button" className="button secondary small" onClick={downloadQasm}>
            <Icon name="save" size={13} />
            Download .qasm
          </button>
        </div>
      </div>
      <pre className="qasm-code-block mono">{qasm}</pre>
    </div>
  );
}

export function GatePalette({ onInsert }: { onInsert: (snippet: string) => void }) {
  const gates = [
    { label: 'H', desc: 'Hadamard (superposition)', code: 'qc.h(0)\n' },
    { label: 'X', desc: 'Pauli-X (NOT bit-flip)', code: 'qc.x(0)\n' },
    { label: 'Y', desc: 'Pauli-Y (bit & phase flip)', code: 'qc.y(0)\n' },
    { label: 'Z', desc: 'Pauli-Z (phase flip)', code: 'qc.z(0)\n' },
    { label: 'S', desc: 'Phase gate (π/2)', code: 'qc.s(0)\n' },
    { label: 'T', desc: 'π/8 gate (π/4 phase)', code: 'qc.t(0)\n' },
    { label: 'CX', desc: 'Controlled-NOT (entanglement)', code: 'qc.cx(0, 1)\n' },
    { label: 'CZ', desc: 'Controlled-Z', code: 'qc.cz(0, 1)\n' },
    { label: 'SWAP', desc: 'Swap two qubits', code: 'qc.swap(0, 1)\n' },
    { label: 'Rx(θ)', desc: 'X-rotation by angle', code: 'qc.rx(pi / 4, 0)\n' },
    { label: 'Ry(θ)', desc: 'Y-rotation by angle', code: 'qc.ry(pi / 4, 0)\n' },
    { label: 'Rz(θ)', desc: 'Z-rotation by angle', code: 'qc.rz(pi / 4, 0)\n' },
    { label: 'Measure', desc: 'Terminal measurement', code: 'qc.measure(0, 0)\n' },
  ];

  return (
    <div className="gate-palette-bar">
      <span className="palette-title">GATES:</span>
      <div className="gate-buttons">
        {gates.map((g) => (
          <button
            key={g.label}
            type="button"
            className="gate-btn"
            title={`${g.label} - ${g.desc} (Click to append)`}
            onClick={() => onInsert(g.code)}
          >
            {g.label}
          </button>
        ))}
      </div>
    </div>
  );
}
