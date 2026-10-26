import type { IR, Metrics, Operation } from './types';
import { Icon } from './Icons';

const param = (v: number) => {
  if (Math.abs(v - Math.PI) < 1e-5) return 'π';
  if (Math.abs(v - Math.PI / 2) < 1e-5) return 'π/2';
  if (Math.abs(v - Math.PI / 4) < 1e-5) return 'π/4';
  return Number(v.toFixed(3)).toString();
};

function Gate({
  op,
  x,
  qy,
  cy,
  index,
  animated = true,
}: {
  op: Operation;
  x: number;
  qy: (q: number) => number;
  cy: (c: number) => number;
  index: number;
  animated?: boolean;
}) {
  const controlCount =
    op.name === 'mcx'
      ? op.qubits.length - 1
      : op.name === 'ccx'
      ? 2
      : ['cx', 'cy', 'cz', 'ch', 'cp', 'crx', 'cry', 'crz', 'cu', 'csx', 'cswap'].includes(op.name)
      ? 1
      : 0;
  const ys = op.qubits.map(qy);
  const isSwap = op.name === 'swap' || op.name === 'cswap';
  const delay = (index * 0.08).toFixed(2);

  return (
    <g
      className={`circuit-gate-group ${animated ? 'gate-animated' : ''}`}
      style={{ animationDelay: `${delay}s` }}
    >
      <title>
        {`${op.name} ${op.params.length ? `(${op.params.map(param).join(', ')}) ` : ''}q[${op.qubits.join(', ')}]${
          op.clbits.length ? ` → c[${op.clbits.join(', ')}]` : ''
        }`}
      </title>

      {op.name === 'barrier' ? (
        <>
          {ys.map((y) => (
            <rect key={y} x={x - 4} y={y - 22} width="8" height="44" fill="#71809c" opacity=".35" rx="2" />
          ))}
          <line
            x1={x}
            y1={Math.min(...ys) - 22}
            x2={x}
            y2={Math.max(...ys) + 22}
            stroke="#71809c"
            strokeDasharray="4 4"
            className="barrier-dash"
          />
        </>
      ) : op.name === 'measure' ? (
        <>
          {op.clbits.map((c, i) => (
            <g key={c} className="measure-wire-flow">
              <path
                d={`M${x - 2} ${ys[i] + 18}V${cy(c) - 4}m4 ${-(cy(c) - ys[i] - 22)}V${cy(c) - 4}`}
                stroke="#A18BE9"
                fill="none"
                strokeWidth="1.5"
                strokeDasharray="5 3"
                className="measure-dash-line"
              />
              <path d={`m${x - 6} ${cy(c) - 7} 6 7 6-7`} fill="none" stroke="#A18BE9" strokeWidth="1.5" />
            </g>
          ))}
          {ys.map((y) => (
            <g key={y} className="gate-box-measure">
              <rect
                x={x - 18}
                y={y - 18}
                width="36"
                height="36"
                rx="6"
                fill="#201a34"
                stroke="#9A83FF"
                strokeWidth="1.5"
                className="gate-rect glow-violet"
              />
              {/* Dial arc */}
              <path d={`M${x - 10} ${y + 6}a10 10 0 0 1 20 0`} stroke="#D4C8FF" strokeWidth="1.5" fill="none" />
              {/* Oscillating measurement needle */}
              <line
                x1={x}
                y1={y + 6}
                x2={x + 7}
                y2={y - 6}
                stroke="#57D9FF"
                strokeWidth="1.8"
                strokeLinecap="round"
                className="measure-animated-needle"
              />
              <circle cx={x} cy={y + 6} r="2" fill="#D4C8FF" />
            </g>
          ))}
        </>
      ) : (
        <>
          {/* Multi-qubit coupling beam with live laser pulse */}
          {ys.length > 1 && (
            <g className="entangling-coupling-group">
              <line
                x1={x}
                y1={Math.min(...ys)}
                x2={x}
                y2={Math.max(...ys)}
                stroke="#57D9FF"
                strokeWidth="2"
                className="coupling-beam-base"
              />
              <line
                x1={x}
                y1={Math.min(...ys)}
                x2={x}
                y2={Math.max(...ys)}
                stroke="#A78BFA"
                strokeWidth="2.5"
                strokeDasharray="6 4"
                className="coupling-beam-laser"
              />
            </g>
          )}

          {ys.map((y, index) =>
            index < controlCount ? (
              <g key={y} className="control-node-group">
                <circle cx={x} cy={y} r="5" fill="#57D9FF" className="control-dot glow-cyan" />
                <circle cx={x} cy={y} r="9" fill="none" stroke="#57D9FF" strokeWidth="1" opacity="0.4" className="control-ring" />
              </g>
            ) : isSwap ? (
              <g key={y} className="swap-cross-group">
                <path d={`m${x - 7} ${y - 7} 14 14m-14 0 14-14`} stroke="#57D9FF" strokeWidth="2.2" strokeLinecap="round" />
              </g>
            ) : op.name === 'cx' || op.name === 'ccx' || op.name === 'mcx' ? (
              <g key={y} className="target-cx-group">
                <circle cx={x} cy={y} r="15" fill="#0c1d2c" stroke="#57D9FF" strokeWidth="1.8" className="cx-circle glow-cyan" />
                <path d={`M${x - 9} ${y}h18M${x} ${y - 9}v18`} stroke="#57D9FF" strokeWidth="2" strokeLinecap="round" />
              </g>
            ) : (
              <g key={y} className="unitary-gate-box">
                <rect
                  x={x - 19}
                  y={y - 18}
                  width="38"
                  height="36"
                  rx="6"
                  fill="#0e1f30"
                  stroke="#38bdf8"
                  strokeWidth="1.5"
                  className="gate-rect glow-cyan"
                />
                <text
                  x={x}
                  y={y + 5}
                  textAnchor="middle"
                  fill="#E0F7FF"
                  fontSize="12.5"
                  fontWeight="700"
                  fontFamily="'JetBrains Mono', monospace"
                  letterSpacing="0.04em"
                >
                  {(controlCount ? op.name.slice(1) : op.name).toUpperCase()}
                </text>
                {op.params.length > 0 && (
                  <text
                    x={x}
                    y={y - 23}
                    textAnchor="middle"
                    fill="#94a3b8"
                    fontSize="9.5"
                    fontFamily="'JetBrains Mono', monospace"
                  >
                    {op.params.map(param).join(',')}
                  </text>
                )}
              </g>
            )
          )}
        </>
      )}
    </g>
  );
}

export function Circuit({ ir, compact = false }: { ir: IR | null; compact?: boolean }) {
  const livePulse = true;

  if (!ir) {
    return (
      <div className="empty-state circuit-empty">
        <div className="empty-icon-wrap">
          <Icon name="circuit" size={24} />
        </div>
        <h3>No Circuit Parsed</h3>
        <p>
          Click <strong>Parse & Visualize</strong> or run simulation to inspect the circuit diagram.
        </p>
      </div>
    );
  }

  const qy = (q: number) => 60 + q * 64;
  const cy = (c: number) => 60 + ir.num_qubits * 64 + c * 32;
  const height = 80 + ir.num_qubits * 64 + ir.num_clbits * 32;
  const width = Math.max(380, ir.operations.length * 72 + 150);

  return (
    <div className={`circuit-scroll ${compact ? 'compact' : ''}`}>
      {/* Circuit Dynamic Status Bar */}
      <div className="circuit-animation-bar">
        <div className="circuit-meta-pill">
          <span className="live-pulse-indicator active" />
          <span className="live-pulse-text">Coherent Wave Propagation</span>
        </div>
        <div className="circuit-reg-tag">
          <span>{ir.num_qubits} Qubits</span>
          <span className="tag-sep">·</span>
          <span>{ir.operations.length} Gates</span>
          <span className="tag-sep">·</span>
          <span>{ir.num_clbits} Clbits</span>
        </div>
      </div>

      <svg
        role="img"
        aria-label={`Quantum Circuit with ${ir.num_qubits} qubits and ${ir.operations.length} operations`}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="circuit-svg-canvas"
      >
        <defs>
          {/* Cyan Glow Filter */}
          <filter id="cyanGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Violet Glow Filter */}
          <filter id="violetGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Linear Quantum Laser Gradient */}
          <linearGradient id="laserBeamGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
            <stop offset="50%" stopColor="#a78bfa" stopOpacity="1" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.9" />
          </linearGradient>

          {/* Wire Wave Gradient */}
          <linearGradient id="wirePulseGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0" />
            <stop offset="50%" stopColor="#38bdf8" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Quantum Wire Registers */}
        {Array.from({ length: ir.num_qubits }, (_, q) => {
          const y = qy(q);
          const dur = (2.2 + q * 0.35).toFixed(2);
          return (
            <g key={`q${q}`} className="quantum-wire-row">
              {/* Register Label */}
              <text x="22" y={y + 5} fill="#B4C2D9" fontSize="12" fontWeight="600" fontFamily="'JetBrains Mono', monospace">
                q[{q}]
              </text>
              <text x="67" y={y + 5} fill="#65718A" fontSize="11" fontFamily="'JetBrains Mono', monospace">
                |0⟩
              </text>

              {/* Base Qubit Wire Line */}
              <line x1="96" y1={y} x2={width - 24} y2={y} stroke="#222b3d" strokeWidth="2" className="wire-base" />

              {/* Glowing Active Wire Line */}
              <line x1="96" y1={y} x2={width - 24} y2={y} stroke="#334155" strokeWidth="1.2" className="wire-glow-line" />

              {/* Live Quantum Wave Particle Traversal */}
              {livePulse && (
                <circle cx="96" cy={y} r="3.2" fill="#38bdf8" filter="url(#cyanGlow)" className="quantum-live-particle">
                  <animate
                    attributeName="cx"
                    from="96"
                    to={width - 24}
                    dur={`${dur}s`}
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0; 0.9; 1; 0.9; 0"
                    dur={`${dur}s`}
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="r"
                    values="2.5; 4.2; 2.5"
                    dur={`${dur}s`}
                    repeatCount="indefinite"
                  />
                </circle>
              )}
            </g>
          );
        })}

        {/* Classical Bit Registers */}
        {Array.from({ length: ir.num_clbits }, (_, c) => {
          const y = cy(c);
          return (
            <g key={`c${c}`} className="classical-wire-row">
              <text x="22" y={y + 5} fill="#9688BE" fontSize="12" fontWeight="600" fontFamily="'JetBrains Mono', monospace">
                c[{c}]
              </text>
              <line x1="96" y1={y - 1.5} x2={width - 24} y2={y - 1.5} stroke="#393049" strokeWidth="1.2" />
              <line x1="96" y1={y + 1.5} x2={width - 24} y2={y + 1.5} stroke="#393049" strokeWidth="1.2" />
            </g>
          );
        })}

        {/* Quantum Gate Instructions */}
        {ir.operations.map((op, i) => (
          <Gate key={i} op={op} x={128 + i * 72} qy={qy} cy={cy} index={i} animated={livePulse} />
        ))}
      </svg>

      {ir.global_phase !== 0 && (
        <span className="phase-note">
          <Icon name="spark" size={12} />
          Global phase: {param(ir.global_phase)} rad
        </span>
      )}
    </div>
  );
}

export function MetricCards({ metrics }: { metrics: Metrics | null }) {
  return (
    <div className="metric-cards">
      {[
        ['Qubits', metrics?.qubits, 'qubits-metric'],
        ['Gates', metrics?.gate_count, 'gates-metric'],
        ['Depth', metrics?.depth, 'depth-metric'],
        ['2-qubit gates', metrics?.two_qubit_gate_count, 'twoqubit-metric'],
      ].map(([name, value, cls]) => (
        <div className={`metric ${cls}`} key={String(name)}>
          <span>{name}</span>
          <strong>{value ?? '—'}</strong>
          <span className="metric-glow-bar" />
        </div>
      ))}
    </div>
  );
}
