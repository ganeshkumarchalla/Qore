import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import ts from 'typescript';

const source = readFileSync(new URL('../src/QuantumStateWorldModel.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { buildStateWorldNodes } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);

const amplitudes = [
  { state: '00', probability: 0.5, phase: 0 },
  { state: '01', probability: 0.5, phase: Math.PI / 2 },
  { state: '10', probability: 0, phase: 0 },
  { state: '11', probability: 0, phase: 0 },
];

test('swapped classical measurement maps the correct relative amplitude phase', () => {
  const run = {
    ir: { num_qubits: 2, num_clbits: 2, operations: [
      { name: 'measure', qubits: [0], clbits: [1] },
      { name: 'measure', qubits: [1], clbits: [0] },
    ] },
    statevector_amplitudes: amplitudes,
    theoretical_probabilities: { '00': 0.5, '01': 0, '10': 0.5, '11': 0 },
    probabilities: { '00': 0.48, '10': 0.52 },
  };
  const nodes = buildStateWorldNodes(run);
  assert.equal(nodes.find(node => node.state === '00').phase, 0);
  assert.ok(Math.abs(nodes.find(node => node.state === '10').phase - Math.PI / 2) < 1e-10);
  assert.equal(nodes.find(node => node.state === '10').probability, 0.5);
  assert.equal(nodes.find(node => node.state === '10').measured, 0.52);
});

test('partial measurement has no unique outcome phase', () => {
  const run = {
    ir: { num_qubits: 2, num_clbits: 1, operations: [
      { name: 'measure', qubits: [0], clbits: [0] },
    ] },
    statevector_amplitudes: [
      { state: '00', probability: 0.5, phase: 0 },
      { state: '01', probability: 0, phase: 0 },
      { state: '10', probability: 0.5, phase: Math.PI / 2 },
      { state: '11', probability: 0, phase: 0 },
    ],
    theoretical_probabilities: { '0': 1, '1': 0 },
    probabilities: { '0': 1 },
  };
  const nodes = buildStateWorldNodes(run);
  assert.equal(nodes.length, 1);
  assert.equal(nodes[0].phase, null);
});

test('unused classical bits do not erase an injective measurement phase', () => {
  const run = {
    ir: { num_qubits: 1, num_clbits: 2, operations: [
      { name: 'measure', qubits: [0], clbits: [1] },
    ] },
    statevector_amplitudes: [
      { state: '0', probability: 0.5, phase: 0 },
      { state: '1', probability: 0.5, phase: Math.PI / 2 },
    ],
    theoretical_probabilities: { '00': 0.5, '01': 0, '10': 0.5, '11': 0 },
    probabilities: { '00': 0.5, '10': 0.5 },
  };
  const nodes = buildStateWorldNodes(run);
  assert.ok(Math.abs(nodes.find(node => node.state === '10').phase - Math.PI / 2) < 1e-10);
});

test('automatic terminal measurements use the identity bit map', () => {
  const run = {
    auto_measured: true,
    ir: { num_qubits: 2, num_clbits: 0, operations: [] },
    statevector_amplitudes: amplitudes,
    theoretical_probabilities: { '00': 0.5, '01': 0.5, '10': 0, '11': 0 },
    probabilities: { '00': 0.5, '01': 0.5 },
  };
  const nodes = buildStateWorldNodes(run);
  assert.ok(Math.abs(nodes.find(node => node.state === '01').phase - Math.PI / 2) < 1e-10);
});

test('relative phase is invariant under a global phase shift', () => {
  const shifted = amplitudes.map(amplitude => ({ ...amplitude, phase: amplitude.phase + 0.73 }));
  const run = {
    auto_measured: true,
    ir: { num_qubits: 2, num_clbits: 0, operations: [] },
    statevector_amplitudes: shifted,
    theoretical_probabilities: { '00': 0.5, '01': 0.5 },
    probabilities: { '00': 0.5, '01': 0.5 },
  };
  const nodes = buildStateWorldNodes(run);
  assert.equal(nodes.find(node => node.state === '00').phase, 0);
  assert.ok(Math.abs(nodes.find(node => node.state === '01').phase - Math.PI / 2) < 1e-10);
});
