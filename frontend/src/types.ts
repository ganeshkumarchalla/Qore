export type Operation = { name: string; qubits: number[]; clbits: number[]; params: number[] };
export type IR = { version: string; num_qubits: number; num_clbits: number; global_phase: number; operations: Operation[] };
export type Metrics = { qubits: number; clbits: number; gate_count: number; depth: number; two_qubit_gate_count: number; measurement_count: number; barrier_count: number; gate_types: Record<string, number>; definition: string };

export type BlochVector = {
  qubit: number;
  x: number;
  y: number;
  z: number;
  theta: number;
  phi: number;
  purity: number;
  is_pure: boolean;
};

export type StatevectorAmplitude = {
  state: string;
  real: number;
  imag: number;
  magnitude: number;
  phase: number;
  probability: number;
};

export type UnitaryCell = {
  real: number;
  imag: number;
  magnitude: number;
  phase: number;
};

export type Parsed = {
  ir: IR;
  metrics: Metrics;
  source_hash: string;
  warnings: string[];
  qasm?: string;
  bloch_vectors?: BlochVector[];
  unitary_matrix?: UnitaryCell[][];
  statevector_amplitudes?: StatevectorAmplitude[];
};

export type Simulation = Parsed & {
  id: string;
  kind: 'simulation';
  created_at: string;
  project_id?: string;
  source: string;
  counts: Record<string, number>;
  probabilities: Record<string, number>;
  theoretical_probabilities: Record<string, number>;
  tvd: number | null;
  shots: number;
  seed: number;
  backend: string;
  versions: Record<string, string>;
  execution_ms: number;
  bit_ordering: string | Record<string, unknown>;
  noise_rate?: number;
  noise_applied?: boolean;
  readout_error?: number;
  simulation_method?: string;
};

export type Validation = { status: 'validated' | 'failed' | 'unavailable' | 'inconclusive'; method: string; details: string; [key: string]: unknown };
export type Optimization = { id: string; kind: 'optimization'; created_at: string; project_id?: string; source: string; source_hash: string; original: { ir: IR; metrics: Metrics }; candidate: { ir: IR; metrics: Metrics; source: string }; settings: Record<string, unknown>; differences: Record<string, { original: number; candidate: number; absolute: number; relative_percent: number | null }>; validation: Validation; explanation: string | string[]; versions: Record<string, string>; warnings: string[] };
export type Project = { id: string; name: string; source: string; created_at: string; updated_at: string };
export type Example = { id: string; name: string; description: string; source: string };
export type ExperimentSummary = { id: string; name: string; project_id?: string; created_at: string; source_hash: string };
export type Experiment = ExperimentSummary & { source: string; ir_version: string; ir?: IR; metrics?: Metrics; versions: Record<string, string>; simulation: Simulation | null; optimization: Optimization | null };
export type Health = { status: string; versions: Record<string, string>; ai_available: boolean; auth_configured?: boolean; auth_required?: boolean; storage?: string; limits: Record<string, unknown> };

export type WorkspaceEntry = {
  id: string; path: string; name: string; type: 'file' | 'folder';
  source: string; kind: 'python' | 'qasm' | 'json' | 'markdown' | null;
  version: number; created_at: string; updated_at: string;
  deleted_at: string | null; expires_at: string | null;
};
export type WorkspaceSnapshot = {
  files: WorkspaceEntry[]; folders: WorkspaceEntry[]; trash: WorkspaceEntry[];
  active_file_id: string | null; last_deleted_id: string | null;
  retention_hours: number; server_time: string;
};

export type Theme =
  | 'obsidian-void'
  | 'hyperion-cyan'
  | 'cobalt-singularity'
  | 'boreal-cryo'
  | 'plasma-nebula'
  | 'dark-modern'
  | 'antigravity'
  | 'azure-quantum'
  | 'nordic-frost';

export type Settings = {
  theme: Theme;
  accentColor: string;
  glassmorphism: boolean;
  fontFamily: string;
  fontSize: number;
  tabSize: number;
  minimap: boolean;
  wordWrap: boolean;
  lineNumbers: 'on' | 'off' | 'relative';
  cursorStyle: 'line' | 'block' | 'underline';
  bracketPairColorization: boolean;
  simulationBackend: 'statevector' | 'matrix_product_state' | 'stabilizer';
  defaultShots: number;
  defaultSeed: number;
  endianness: 'little' | 'big';
  noiseSimulation: boolean;
  depolarizingRate: number;
  readoutErrorRate: number;
  thermalRelaxation?: boolean;
  targetBasis: 'generic' | 'ibm' | 'rigetti' | 'ionq';
  defaultOptLevel: number;
  equivalenceTolerance: string;
  routingMethod?: 'sabre' | 'stochastic' | 'basic' | 'lookahead';
  livePulseAnimation?: boolean;
  autoSave?: boolean;
  maxQubitsGuard?: number;
  uiDensity?: 'compact' | 'balanced' | 'comfortable';
  wireStyle?: 'neon' | 'blueprint' | 'minimal';
  autoCloseBrackets?: boolean;
  formatOnSave?: boolean;
  zeroThreshold?: string;
  hardwareTopology?: 'ideal' | 'ibm_heron' | 'ibm_eagle' | 'rigetti_ankaa' | 'quantinuum_h1';
  errorMitigation?: 'none' | 'inversion' | 'm3_twirled';
  dynamicalDecoupling?: 'none' | 'cpmg' | 'xy4' | 'udd';
  commutationAnalysis?: boolean;
  strictUnitaryCheck?: boolean;
  copilotTemperature?: number;
  autoExplainCircuit?: boolean;
  streamAiTokens?: boolean;
  terminalFontSize?: number;
  terminalBlink?: boolean;
  defaultProvider?: 'ibm' | 'azure' | 'rigetti';
  resourceErrorBudget?: '0.001' | '0.0001' | '0.01';
  precisionMode?: 'fp64' | 'fp32';
};
let apiRequests = new AbortController();
export function invalidateApiRequests() {
  apiRequests.abort();
  apiRequests = new AbortController();
}
export async function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let response: Response;
  const signal = apiRequests.signal;
  try { response = await fetch(`/api${path}`, { method: method ?? (body === undefined ? 'GET' : 'POST'), credentials: 'same-origin', signal, headers: body === undefined ? {} : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) }); }
  catch { throw new Error(signal.aborted ? 'The workspace changed. Please retry.' : 'Cannot connect to the QORE backend. Check your connection, then retry.'); }
  const data = await response.json().catch(() => null);
  if (signal.aborted) throw new Error('The workspace changed. Please retry.');
  if (!response.ok) { const detail = data?.error?.details; throw new Error(`${data?.error?.message ?? data?.detail?.[0]?.msg ?? (typeof data?.detail === 'string' ? data.detail : `Request failed (${response.status})`)}${detail ? ` · ${typeof detail === 'string' ? detail : JSON.stringify(detail)}` : ''}`); }
  return data as T;
}
export const readable = (value: unknown): string => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
export const formatDate = (value: string) => new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
