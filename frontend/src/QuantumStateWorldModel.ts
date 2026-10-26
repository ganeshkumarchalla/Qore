import type { Simulation } from './types';

export type WorldNode = {
  state: string;
  probability: number;
  measured: number;
  x: number;
  y: number;
  z: number;
  phase: number | null;
};

const TAU = Math.PI * 2;

export function hammingWeight(state: string): number {
  return [...state].reduce((weight, bit) => weight + (bit === '1' ? 1 : 0), 0);
}

function outcomePhaseMap(run: Simulation): Map<string, number> {
  const amplitudes = run.statevector_amplitudes ?? [];
  const qubits = run.ir.num_qubits;
  const classicalBits = run.auto_measured ? qubits : run.ir.num_clbits;
  const mapping = run.auto_measured
    ? Array.from({ length: qubits }, (_, qubit) => [qubit, qubit])
    : run.ir.operations.filter(operation => operation.name === 'measure')
      .map(operation => [operation.qubits[0], operation.clbits[0]]);

  // A classical outcome has one ideal amplitude only when every qubit is
  // measured into a distinct classical bit.
  // Partial measurement sums probabilities from multiple quantum basis states,
  // so assigning that outcome any one of their phases would be misleading.
  if (classicalBits < qubits || mapping.length !== qubits || amplitudes.length !== 2 ** qubits
    || new Set(mapping.map(pair => pair[0])).size !== qubits
    || new Set(mapping.map(pair => pair[1])).size !== qubits) return new Map();

  const reference = amplitudes.reduce((largest, amplitude) =>
    amplitude.probability > largest.probability ? amplitude : largest, amplitudes[0]);
  if (reference.probability <= 1e-10) return new Map();
  const phases = new Map<string, number>();
  for (const amplitude of amplitudes) {
    if (amplitude.probability <= 1e-10) continue;
    const basis = Number.parseInt(amplitude.state, 2);
    const outcome = mapping.reduce((bits, [qubit, clbit]) =>
      bits | (((basis >> qubit) & 1) << clbit), 0);
    const state = outcome.toString(2).padStart(classicalBits, '0');
    phases.set(state, Math.atan2(Math.sin(amplitude.phase - reference.phase), Math.cos(amplitude.phase - reference.phase)));
  }
  return phases;
}

export function buildStateWorldNodes(run: Simulation): WorldNode[] {
  const phases = outcomePhaseMap(run);
  const states = [...new Set([
    ...Object.keys(run.theoretical_probabilities),
    ...Object.keys(run.probabilities),
  ])];
  const byWeight = new Map<number, string[]>();
  for (const state of states) {
    const weight = hammingWeight(state);
    const group = byWeight.get(weight) ?? [];
    group.push(state);
    byWeight.set(weight, group);
  }
  for (const group of byWeight.values()) group.sort();
  const width = Math.max(1, ...states.map(state => state.length));
  return states.map(state => {
    const weight = hammingWeight(state);
    const group = byWeight.get(weight) ?? [state];
    const index = Math.max(0, group.indexOf(state));
    const azimuth = group.length === 1 ? 0 : (TAU * index) / group.length;
    const polar = width <= 1 ? 0 : Math.PI * (weight / width);
    return {
      state,
      probability: run.theoretical_probabilities[state] ?? 0,
      measured: run.probabilities[state] ?? 0,
      x: Math.sin(polar) * Math.cos(azimuth),
      y: Math.sin(polar) * Math.sin(azimuth),
      z: Math.cos(polar),
      phase: phases.get(state) ?? null,
    };
  }).filter(node => node.probability > 1e-8 || node.measured > 0)
    .sort((a, b) => Math.max(b.probability, b.measured) - Math.max(a.probability, a.measured));
}
