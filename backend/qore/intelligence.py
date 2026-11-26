"""QORE Quantum AI model (qore-quantum-rl-dl-v1).

Combines:
1. Trained Deep Learning + LogisticRegression intent ensemble & LSA semantic
   retriever over quantum computing & QORE knowledge passages.
2. Trained Deep Learning IBM hardware fidelity & routing overhead neural
   predictors (trained on qiskit_ibm_runtime.fake_provider calibration models:
   FakeManilaV2, FakeBelemV2, FakeAthensV2, FakeBrisbane, FakeTorino).
3. Trained Reinforcement Learning (Q-value neural policy) pass-level advisor
   for Forge optimization levels 0-3.
4. Live neuro-symbolic QORE-IR parser, gate-by-gate statevector tracer, and
   verified dynamic quantum circuit synthesizer.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from . import quantum
from .examples import EXAMPLES

MODEL_PATH = Path(__file__).resolve().with_name("qore_ai_model.joblib")
DEFAULT_MODEL_ID = "qore-quantum-rl-dl-v1"
MODEL_ID = DEFAULT_MODEL_ID

_INJECTION_RE = re.compile(
    r"(reveal|print|dump|leak|show|expose|ignore\s+previous|disregard\s+system|"
    r"system\s+prompt|gemini_api_key|api[_\s-]?key|\.env\b|os\.environ|"
    r"qore_gateway_token|secret[_\s-]?key|service[_\s-]?role|execute\s+shell|run\s+bash)",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _load_bundle() -> dict[str, Any]:
    if not MODEL_PATH.exists():
        # Lazy fallback: train on demand if artifact is missing
        import sys
        scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from train_qore_ai import train_and_save
        train_and_save()
    return joblib.load(MODEL_PATH)


def model_metadata() -> dict[str, Any]:
    bundle = _load_bundle()
    return {
        "model_id": bundle.get("model_id", DEFAULT_MODEL_ID),
        "trained_at": bundle.get("trained_at"),
        "metrics": bundle.get("metrics", {}),
    }


def _extract_circuit_features_from_ir(ir: dict[str, Any], metrics: dict[str, Any]) -> np.ndarray:
    ops = [op for op in ir.get("operations", []) if op.get("name") not in ("measure", "barrier")]
    n_qubits = max(1, int(metrics.get("qubits", ir.get("num_qubits", 1))))
    gate_count = len(ops)
    depth = max(0, int(metrics.get("depth", 0)))
    two_q = sum(1 for op in ops if len(op.get("qubits", [])) == 2)
    three_plus_q = sum(1 for op in ops if len(op.get("qubits", [])) >= 3)
    param_gates = sum(1 for op in ops if len(op.get("params", [])) > 0)
    clifford_names = {"h", "x", "y", "z", "s", "sdg", "cx", "cy", "cz", "swap"}
    clifford_count = sum(1 for op in ops if op.get("name") in clifford_names)

    adj_cancels = 0
    for idx in range(len(ops) - 1):
        a, b = ops[idx], ops[idx + 1]
        if a.get("name") == b.get("name") and a.get("name") in {"x", "y", "z", "h", "cx", "cz", "swap"}:
            if a.get("qubits") == b.get("qubits"):
                adj_cancels += 1

    return np.array([
        float(n_qubits),
        float(gate_count),
        float(depth),
        float(two_q),
        float(three_plus_q),
        float(param_gates),
        float(adj_cancels),
        float(two_q / max(1, gate_count)),
        float(clifford_count / max(1, gate_count)),
        float(param_gates / max(1, gate_count)),
    ], dtype=np.float64)


def predict_rl_and_ibm(ir: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    """Run trained RL Q-networks (levels 0-3) and Deep Learning IBM fidelity predictor."""
    bundle = _load_bundle()
    feat = _extract_circuit_features_from_ir(ir, metrics)

    # 1. RL Compiler Pass Policy Q-values
    rl = bundle["rl_forge"]
    s_scaled = rl["scaler"].transform(feat.reshape(1, -1))
    q_values = [round(float(net.predict(s_scaled)[0]), 3) for net in rl["q_nets"]]
    recommended_level = int(np.argmax(q_values))

    # 2. Deep Learning IBM Hardware Fidelity & Overhead prediction (Manila/Falcon baseline at opt level 0 vs 2)
    dl = bundle["dl_ibm"]
    x_l0 = np.concatenate([feat, np.array([0.0, 0.0])]).reshape(1, -1)
    x_l2 = np.concatenate([feat, np.array([2.0, 0.0])]).reshape(1, -1)
    fid_l0 = float(np.clip(dl["fidelity_net"].predict(dl["scaler"].transform(x_l0))[0], 0.0, 1.0))
    fid_l2 = float(np.clip(dl["fidelity_net"].predict(dl["scaler"].transform(x_l2))[0], 0.0, 1.0))
    ov_l2 = float(max(0.5, dl["overhead_net"].predict(dl["scaler"].transform(x_l2))[0]))

    return {
        "rl_recommended_level": recommended_level,
        "rl_q_values": {f"level_{lvl}": q_values[lvl] for lvl in range(4)},
        "dl_ibm_predicted_fidelity_l0": round(fid_l0, 3),
        "dl_ibm_predicted_fidelity_l2": round(fid_l2, 3),
        "dl_ibm_predicted_2q_overhead_l2": round(ov_l2, 2),
    }


def classify_intent(
    question: str,
    *,
    view: str = "Studio",
    has_source: bool = False,
    has_simulation: bool = False,
    has_optimization: bool = False,
    has_diagnostics: bool = False,
) -> tuple[str, float]:
    """Classify query intent using the trained DeepMLP + LogisticRegression ensemble."""
    bundle = _load_bundle()
    X = bundle["intent_features"].transform([question])
    probs = bundle["classifier"].predict_proba(X)[0].copy()
    classes: list[str] = bundle["classes"]

    def boost(label: str, delta: float) -> None:
        if label in classes:
            probs[classes.index(label)] += delta

    q = question.lower()
    if has_diagnostics and any(w in q for w in ("error", "fail", "fix", "wrong", "why", "warning", "broken")):
        boost("diagnose_error", 0.24)
    if any(w in q for w in ("write", "create", "generate", "build", "propose", "make a", "give me code")):
        boost("propose_code", 0.20)
    if any(w in q for w in ("bloch", "purity", "amplitude", "statevector", "unitary", "theta", "phi")):
        boost("analyze_state", 0.18)
    if any(w in q for w in ("hardware", "qpu", "advantage", "real quantum computer", "supremacy")):
        boost("hardware_vs_sim", 0.26)
    if any(w in q for w in ("matrix", "derive", "formula", "equation", "prove", "eigen")):
        boost("math_derivation", 0.18)
    if any(w in q for w in ("compare", "difference between", " vs ", "versus")):
        boost("compare_concepts", 0.22)
    if has_optimization or view == "Forge":
        if any(w in q for w in ("forge", "optimi", "candidate", "transpil", "equivalen", "delta", "reduc", "rl", "level")):
            boost("optimize_forge", 0.22)
    if has_simulation or view == "Lab":
        if any(w in q for w in ("shot", "count", "probab", "tvd", "histogram", "noise", "result", "simulat", "ibm", "fidelity")):
            boost("interpret_simulation", 0.18)
    if view == "Research" and any(w in q for w in ("ledger", "snapshot", "reproduc", "history", "hash", "saved")):
        boost("experiment_ledger", 0.22)

    total = float(np.sum(probs))
    if total > 0:
        probs = probs / total
    idx = int(np.argmax(probs))
    return classes[idx], round(float(probs[idx]), 3)


def retrieve_knowledge(query: str, top_k: int = 2) -> list[dict[str, Any]]:
    """Retrieve the top-k most relevant quantum knowledge passages using hybrid TF-IDF + LSA cosine similarity."""
    bundle = _load_bundle()
    q_tfidf = bundle["kb_vectorizer"].transform([query])
    q_dense = bundle["kb_normalizer"].transform(bundle["kb_svd"].transform(q_tfidf))

    dense_sims = (bundle["kb_embeddings"] @ q_dense.T).ravel()
    sparse_sims = (bundle["kb_tfidf"] @ q_tfidf.T).toarray().ravel()
    scores = 0.65 * sparse_sims + 0.35 * dense_sims

    ranked = np.argsort(-scores)
    results: list[dict[str, Any]] = []
    for idx in ranked[:top_k]:
        if scores[idx] >= 0.08:
            passage = dict(bundle["knowledge_base"][int(idx)])
            passage["score"] = round(float(scores[idx]), 3)
            results.append(passage)
    return results


def _format_ket(sv: Statevector, n_qubits: int, max_terms: int = 4) -> str:
    data = np.asarray(sv.data, dtype=complex)
    terms: list[tuple[float, str]] = []
    for idx, amp in enumerate(data):
        prob = float(abs(amp) ** 2)
        if prob > 1e-6:
            bitstr = format(idx, f"0{n_qubits}b")
            re_v, im_v = float(np.real(amp)), float(np.imag(amp))
            if abs(im_v) < 1e-4:
                coeff = f"{re_v:+.3f}"
            elif abs(re_v) < 1e-4:
                coeff = f"{im_v:+.3f}i"
            else:
                coeff = f"({re_v:+.2f}{im_v:+.2f}i)"
            terms.append((prob, f"{coeff}|{bitstr}⟩"))
    terms.sort(key=lambda x: -x[0])
    shown = " ".join(t[1] for t in terms[:max_terms])
    if len(terms) > max_terms:
        shown += f" (+{len(terms) - max_terms} terms)"
    return shown.lstrip("+")


def _trace_circuit_evolution(ir: dict[str, Any], max_steps: int = 10) -> list[str]:
    """Compute real step-by-step Qiskit Statevector evolution for small circuits (<= 4 qubits)."""
    n = int(ir.get("num_qubits", 0))
    unitary_ops = [op for op in ir.get("operations", []) if op.get("name") not in ("measure", "barrier")]
    if n < 1 or n > 4 or not unitary_ops or len(unitary_ops) > 16:
        return []
    try:
        step_qc = QuantumCircuit(n)
        trace = [f"• Init: |{'0' * n}⟩"]
        for idx, op in enumerate(unitary_ops[:max_steps]):
            name = op["name"]
            q = op["qubits"]
            p = op.get("params", [])
            if name == "mcx":
                from qiskit.circuit.library import MCXGate
                step_qc.append(MCXGate(len(q) - 1), q)
            else:
                getattr(step_qc, name)(*p, *q)
            sv = Statevector.from_instruction(step_qc)
            q_label = ",".join(f"q{i}" for i in q)
            p_label = f"({', '.join(f'{v:.2f}' for v in p)})" if p else ""
            trace.append(f"• Step {idx + 1} `{name}{p_label}({q_label})`: {_format_ket(sv, n)}")
        if len(unitary_ops) > max_steps:
            trace.append(f"• … ({len(unitary_ops) - max_steps} more unitary operations)")
        return trace
    except Exception:
        return []


def _extract_requested_qubits(question: str, default: int, minimum: int = 2, maximum: int = 8) -> int:
    match = re.search(r"\b(\d{1,2})\s*[- ]?\s*qubit", question, re.IGNORECASE)
    if match:
        val = int(match.group(1))
        return max(minimum, min(maximum, val))
    word_map = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    for word, val in word_map.items():
        if re.search(rf"\b{word}\s+qubit", question, re.IGNORECASE):
            return max(minimum, min(maximum, val))
    return default


def _verify_proposal(proposal: dict[str, str] | None) -> dict[str, str] | None:
    if not proposal:
        return None
    try:
        quantum.parse_source(proposal["code"])
        return proposal
    except quantum.QuantumError:
        return None


def _build_proposal(question: str, source: str, parsed: dict[str, Any] | None) -> dict[str, str] | None:
    q = question.lower()
    want_qasm = "openqasm" in q or "qasm" in q

    if "ghz" in q:
        n = _extract_requested_qubits(question, default=3, minimum=2, maximum=8)
        if want_qasm:
            cx_lines = "\n".join(f"cx q[{i}], q[{i + 1}];" for i in range(n - 1))
            code = f'OPENQASM 2.0;\ninclude "qelib1.inc";\n\nqreg q[{n}];\ncreg c[{n}];\n\nh q[0];\n{cx_lines}\nmeasure q -> c;\n'
            return _verify_proposal({"title": f"{n}-Qubit GHZ State (OpenQASM 2.0)", "language": "qasm", "code": code,
                                     "note": f"Verified {n}-qubit GHZ OpenQASM circuit. Review before applying to the editor."})
        cx_lines = "\n".join(f"qc.cx({i}, {i + 1})" for i in range(n - 1))
        meas_lines = "\n".join(f"qc.measure({i}, {i})" for i in range(n))
        code = f"# {n}-Qubit GHZ Entangled State\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit({n}, {n})\nqc.h(0)\n{cx_lines}\n{meas_lines}\n"
        return _verify_proposal({"title": f"{n}-Qubit GHZ State", "language": "python", "code": code,
                                 "note": f"Synthesized and AST-verified {n}-qubit GHZ circuit. Click Apply to Editor to load."})

    if "qft" in q or "fourier" in q:
        n = _extract_requested_qubits(question, default=3, minimum=2, maximum=5)
        lines = [f"# {n}-Qubit Quantum Fourier Transform", "from qiskit import QuantumCircuit", "from math import pi", "", f"qc = QuantumCircuit({n}, {n})"]
        lines.append("qc.x(0)")
        for j in range(n):
            lines.append(f"qc.h({j})")
            for k in range(j + 1, n):
                denom = 2 ** (k - j)
                lines.append(f"qc.cp(pi / {denom}, {k}, {j})")
        for j in range(n // 2):
            lines.append(f"qc.swap({j}, {n - 1 - j})")
        for j in range(n):
            lines.append(f"qc.measure({j}, {j})")
        return _verify_proposal({"title": f"{n}-Qubit Quantum Fourier Transform", "language": "python", "code": "\n".join(lines) + "\n",
                                 "note": f"Synthesized and verified {n}-qubit QFT circuit. Review before applying."})

    if "deutsch" in q:
        code = (
            "# Deutsch-Jozsa Algorithm (2 input qubits + 1 phase ancilla, balanced oracle)\n"
            "from qiskit import QuantumCircuit\n\n"
            "qc = QuantumCircuit(3, 2)\n"
            "qc.x(2)\n"
            "qc.h(0)\nqc.h(1)\nqc.h(2)\n"
            "# Balanced XOR oracle via phase kickback\n"
            "qc.cx(0, 2)\nqc.cx(1, 2)\n"
            "qc.h(0)\nqc.h(1)\n"
            "qc.measure(0, 0)\nqc.measure(1, 1)\n"
        )
        return _verify_proposal({"title": "Deutsch-Jozsa (Balanced Oracle)", "language": "python", "code": code,
                                 "note": "Measures |11⟩ deterministically for this balanced oracle."})

    if "bernstein" in q or "vazirani" in q:
        code = (
            "# Bernstein-Vazirani Algorithm (recovers hidden string s = '101')\n"
            "from qiskit import QuantumCircuit\n\n"
            "qc = QuantumCircuit(4, 3)\n"
            "qc.x(3)\n"
            "qc.h(0)\nqc.h(1)\nqc.h(2)\nqc.h(3)\n"
            "# Oracle for s = 101 (q0 and q2)\n"
            "qc.cx(0, 3)\nqc.cx(2, 3)\n"
            "qc.h(0)\nqc.h(1)\nqc.h(2)\n"
            "qc.measure(0, 0)\nqc.measure(1, 1)\nqc.measure(2, 2)\n"
        )
        return _verify_proposal({"title": "Bernstein-Vazirani (s = 101)", "language": "python", "code": code,
                                 "note": "Single-query hidden string recovery via phase kickback."})

    for key, ex_id in (("bell", "bell"), ("epr", "bell"), ("grover", "grover"), ("teleport", "teleportation"),
                       ("superdense", "superdense"), ("qaoa", "qaoa"), ("realamplitudes", "library-ansatz"),
                       ("ansatz", "library-ansatz"), ("variational", "library-ansatz"), ("pauli", "library-evolution"),
                       ("sparsepauliop", "library-evolution"), ("state prep", "library-state"), ("+i", "library-state")):
        if key in q:
            ex = next((e for e in EXAMPLES if e["id"] == ex_id), None)
            if ex:
                lang = "qasm" if ex["source"].lstrip().startswith("OPENQASM") else "python"
                return _verify_proposal({"title": ex["name"], "language": lang, "code": ex["source"],
                                         "note": "AST-verified circuit template. Click Apply to Editor to inspect and run."})

    if "efficientsu2" in q:
        code = (
            "# Parameter-bound EfficientSU2 ansatz\n"
            "from qiskit.circuit.library import efficient_su2\n\n"
            "qc = efficient_su2(2, reps=1)\n"
            "qc = qc.assign_parameters([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])\n"
            "qc.measure_all()\n"
        )
        return _verify_proposal({"title": "Bound EfficientSU2 Ansatz", "language": "python", "code": code,
                                 "note": "2-qubit EfficientSU2 variational circuit with bound parameters."})

    if "superposition" in q:
        n = _extract_requested_qubits(question, default=2, minimum=1, maximum=8)
        h_lines = "\n".join(f"qc.h({i})" for i in range(n))
        m_lines = "\n".join(f"qc.measure({i}, {i})" for i in range(n))
        code = f"# Equal {n}-Qubit Superposition\nfrom qiskit import QuantumCircuit\n\nqc = QuantumCircuit({n}, {n})\n{h_lines}\n{m_lines}\n"
        return _verify_proposal({"title": f"{n}-Qubit Equal Superposition", "language": "python", "code": code,
                                 "note": f"Prepares uniform superposition over all 2^{n} computational basis states."})

    if parsed and parsed["metrics"]["measurement_count"] == 0 and any(k in q for k in ("measure", "improv", "fix", "propos", "suggest")):
        n = parsed["metrics"]["qubits"]
        if not source.lstrip().startswith("OPENQASM"):
            candidate = source.rstrip() + "\nqc.measure_all(add_bits=False)\n" if parsed["metrics"]["clbits"] >= n else source.rstrip() + "\nqc.measure_all()\n"
            return _verify_proposal({"title": "Add explicit terminal measurements", "language": "python", "code": candidate,
                                     "note": "Adds explicit classical measurement mappings to your active circuit."})

    if any(k in q for k in ("starter", "example", "create a", "write a", "generate a", "build a")):
        ex = next((e for e in EXAMPLES if e["id"] == "bell"), None)
        if ex:
            return _verify_proposal({"title": ex["name"], "language": "python", "code": ex["source"],
                                     "note": "Verified Bell-state starter circuit for Studio, Lab, and Forge."})
    return None


def _top_outcomes(dist: dict[str, float] | dict[str, int] | None, limit: int = 4) -> list[tuple[str, float]]:
    if not isinstance(dist, dict):
        return []
    items = [(str(k), float(v)) for k, v in dist.items() if float(v) > 0]
    items.sort(key=lambda pair: (-pair[1], pair[0]))
    return items[:limit]


def _describe_circuit(parsed: dict[str, Any], file_name: str, rl_dl: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    ir = parsed["ir"]
    m = parsed["metrics"]
    ops = ir["operations"]
    gates = [op for op in ops if op["name"] not in ("measure", "barrier")]
    measures = [op for op in ops if op["name"] == "measure"]
    entangling = [op for op in gates if len(op["qubits"]) >= 2]
    top_types = ", ".join(f"{name}×{count}" for name, count in sorted(m["gate_types"].items(), key=lambda x: (-x[1], x[0]))[:6])

    lines = [
        f"Circuit telemetry{f' for `{file_name}`' if file_name else ''}: {m['qubits']} qubit(s), "
        f"{m['clbits']} classical bit(s), {m['gate_count']} gate(s), depth {m['depth']}, "
        f"and {m['two_qubit_gate_count']} two-qubit gate(s)."
    ]
    if top_types:
        lines.append(f"Gate breakdown: {top_types}.")
    if entangling:
        pairs = ", ".join(f"{op['name']}(q{','.join(str(q) for q in op['qubits'])})" for op in entangling[:5])
        if len(entangling) > 5:
            pairs += f" (+{len(entangling) - 5} more)"
        lines.append(f"Multi-qubit interactions: {pairs}.")
    else:
        lines.append("Single-qubit product evolution (no multi-qubit entangling gates present).")
    if measures:
        mappings = ", ".join(f"q[{op['qubits'][0]}]→c[{op['clbits'][0]}]" for op in measures[:6])
        lines.append(f"Terminal measurements ({len(measures)}): {mappings}.")
    else:
        lines.append("No explicit measurements declared (Lab auto-measures all qubits).")

    trace = _trace_circuit_evolution(ir)
    if trace:
        lines.append("Live statevector evolution:\n" + "\n".join(trace))

    ev = [f"QORE-IR ({m['qubits']}Q, {m['gate_count']} gates, depth {m['depth']})"]
    if rl_dl:
        lines.append(
            f"Neural & RL estimates (trained on IBM Falcon/Eagle/Heron `FakeBackend` snapshots + Qiskit transpiler episodes): "
            f"RL policy recommends Forge level {rl_dl['rl_recommended_level']} "
            f"(Q-values L0:{rl_dl['rl_q_values']['level_0']}, L1:{rl_dl['rl_q_values']['level_1']}, "
            f"L2:{rl_dl['rl_q_values']['level_2']}, L3:{rl_dl['rl_q_values']['level_3']}); "
            f"DL predicted IBM Falcon noisy fidelity ≈ {rl_dl['dl_ibm_predicted_fidelity_l2']*100:.1f}% at opt level 2."
        )
        ev.append(f"RL policy (L{rl_dl['rl_recommended_level']})")
        ev.append("DL IBM fidelity model")
    return "\n".join(lines), ev


def _describe_simulation(sim: dict[str, Any]) -> tuple[str, list[str]]:
    shots = sim.get("shots", 0)
    seed = sim.get("seed")
    backend = sim.get("backend", "Qiskit Aer")
    top_emp = _top_outcomes(sim.get("probabilities"), 4)
    top_ideal = _top_outcomes(sim.get("theoretical_probabilities"), 4)
    lines = [f"Attached simulation ({shots} shots, seed {seed}, `{backend}`):"]
    if top_emp:
        lines.append("• Sampled probabilities: " + ", ".join(f"|{k}⟩: {v * 100:.2f}%" for k, v in top_emp) + ".")
    if top_ideal:
        lines.append("• Ideal reference: " + ", ".join(f"|{k}⟩: {v * 100:.2f}%" for k, v in top_ideal) + ".")
    tvd = sim.get("tvd")
    if tvd is not None:
        lines.append(f"• TVD = {float(tvd):.5f}, classical fidelity = {float(sim.get('classical_fidelity', 0.0)):.5f}, Hellinger = {float(sim.get('hellinger_distance', 0.0)):.5f}.")
    if sim.get("noise_applied"):
        lines.append(f"• Modeled noise active (gate={sim.get('noise_rate', 0)}, readout={sim.get('readout_error', 0)}); off-ideal outcomes reflect modeled noise + finite-shot sampling, not live QPU telemetry.")
    else:
        lines.append("• Noiseless simulation: deviations from ideal theory are strictly finite-shot sampling variance.")
    if sim.get("bit_ordering"):
        lines.append(f"• Bit ordering: {sim['bit_ordering']}")
    return "\n".join(lines), [f"Simulation ({shots} shots, TVD {float(tvd):.4f})" if tvd is not None else f"Simulation ({shots} shots)"]


def _describe_state(parsed: dict[str, Any]) -> tuple[str, list[str]]:
    bloch = parsed.get("bloch_vectors") or []
    amps = parsed.get("statevector_amplitudes") or []
    unitarity = parsed.get("unitarity")
    lines: list[str] = []
    ev: list[str] = []
    if bloch:
        lines.append("Reduced single-qubit Bloch states (partial trace ρ_k):")
        for b in bloch[:6]:
            if not b.get("direction_defined", True):
                lines.append(f"• q[{b['qubit']}]: center (|r|={b.get('r', 0):.4f}, purity={b['purity']:.4f}) — direction (θ, φ) undefined due to entanglement.")
            elif not b.get("azimuth_defined", True):
                lines.append(f"• q[{b['qubit']}]: Z-pole (z={b['z']:.4f}, |r|={b.get('r', 0):.4f}, purity={b['purity']:.4f}) — azimuth φ undefined on Z-axis.")
            else:
                lines.append(f"• q[{b['qubit']}]: ({b['x']:.3f}, {b['y']:.3f}, {b['z']:.3f}), |r|={b.get('r', 0):.3f}, purity={b['purity']:.3f} ({'pure' if b.get('is_pure') else 'mixed'}).")
        ev.append(f"Bloch states ({len(bloch)}Q)")
    else:
        lines.append("Bloch vectors and statevector amplitudes are computed up to 6 qubits.")
    if amps:
        non_zero = sorted([a for a in amps if a.get("probability", 0) > 1e-6], key=lambda a: -a["probability"])[:4]
        if non_zero:
            lines.append("Dominant amplitudes: " + ", ".join(f"|{a['state']}⟩ ({a['real']:+.3f}{a['imag']:+.3f}i, {a['probability']*100:.2f}%)" for a in non_zero) + ".")
            ev.append(f"Statevector ({len(amps)} states)")
    if isinstance(unitarity, dict):
        lines.append(f"Operator unitarity: {'verified' if unitarity.get('is_unitary') else 'failed'} (max |U†U − I| = {unitarity.get('max_deviation', 0):.2e}).")
        ev.append("Unitarity report")
    return "\n".join(lines), ev


def _describe_optimization(opt: dict[str, Any], rl_dl: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    diffs = opt.get("differences") or {}
    val = opt.get("validation") or {}
    settings = opt.get("settings") or {}
    parts = []
    for key, label in (("gate_count", "gates"), ("depth", "depth"), ("two_qubit_gate_count", "2Q gates")):
        d = diffs.get(key)
        if isinstance(d, dict):
            parts.append(f"{label}: {d.get('original')} → {d.get('candidate')} ({d.get('absolute'):+d})")
    lines = [f"Attached Forge optimization (level {settings.get('level', '?')}):"]
    if parts:
        lines.append("• Resource deltas: " + "; ".join(parts) + ".")
    status = val.get("status", "unknown")
    lines.append(f"• Equivalence check: {status} ({val.get('method', 'unknown')}). {val.get('details', '')}".strip())
    if val.get("max_absolute_error") is not None:
        lines.append(f"• Max operator error: {val['max_absolute_error']:.2e} (process fidelity {val.get('process_fidelity')}).")
    if rl_dl:
        best_lvl = rl_dl["rl_recommended_level"]
        best_q = rl_dl["rl_q_values"][f"level_{best_lvl}"]
        lines.append(f"• RL Policy Q-advice: optimal Forge pass level for this structure is Level {best_lvl} (Q={best_q}).")
    return "\n".join(lines), [f"Forge ({status})"]


def run_local_intelligence(
    *,
    question: str,
    source: str = "",
    view: str = "Studio",
    file_name: str = "",
    workspace_summary: str = "",
    diagnostics: str = "",
    simulation: dict[str, Any] | None = None,
    optimization: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run qore-quantum-rl-dl-v1 to produce a conversational, evidence-grounded answer."""
    clean_question = question.strip()
    injection_flagged = bool(_INJECTION_RE.search(clean_question) or _INJECTION_RE.search(source))

    parsed: dict[str, Any] | None = None
    parse_err: dict[str, Any] | None = None
    if source.strip():
        try:
            parsed = quantum.parse_source(source)
        except quantum.QuantumError as exc:
            parse_err = {"code": exc.code, "message": exc.message, "details": exc.details}

    rl_dl = predict_rl_and_ibm(parsed["ir"], parsed["metrics"]) if parsed else None

    effective_question = clean_question
    if history and len(clean_question.split()) <= 7 and any(w in clean_question.lower() for w in ("why", "more", "what about", "explain that", "fix it", "optimize it", "how", "math")):
        last_user = next((h.get("text", "") for h in reversed(history) if h.get("role") == "user" and h.get("text")), "")
        if last_user:
            effective_question = f"{last_user} {clean_question}"

    has_diag = bool(diagnostics.strip() or parse_err)
    intent, confidence = classify_intent(
        effective_question,
        view=view,
        has_source=bool(source.strip()),
        has_simulation=bool(simulation),
        has_optimization=bool(optimization),
        has_diagnostics=has_diag,
    )

    kb_hits = retrieve_knowledge(effective_question, top_k=2)
    sections: list[str] = []
    evidence_used: list[str] = []
    suggested_actions: list[str] = []

    if injection_flagged:
        sections.append(
            "Security boundary: I cannot reveal server credentials, environment variables, system prompts, or execute host commands. "
            "I can still assist with your quantum circuits and QORE evidence below."
        )

    if intent == "greeting_meta":
        meta = model_metadata()
        m = meta.get("metrics", {})
        sections.append(
            f"Hello! I am **QORE Intelligence** powered by `{meta['model_id']}` — a domain-trained quantum engineering model combining:\n"
            f"• **Deep Learning NLP & Semantic Retrieval**: {m.get('nlp_architecture', 'DeepMLP + LSA')} ({m.get('nlp_corpus_examples', 0)} training intents, {m.get('knowledge_passages', 0)} quantum passages).\n"
            f"• **Deep Learning IBM Calibration Estimator**: trained on {m.get('ibm_dl_samples', 0)} real IBM `FakeBackend` + Qiskit Aer runs (`FakeManilaV2`, `FakeBelemV2`, `FakeAthensV2`, `FakeBrisbane` 127Q Eagle, `FakeTorino` 133Q Heron).\n"
            f"• **Reinforcement Learning Compiler Policy**: trained across {m.get('rl_transpile_episodes', 0)} real Qiskit transpilation episodes to recommend Forge optimization levels 0–3.\n"
            f"• **Live QORE-IR & Statevector Tracer**: inspects your active circuit, Bloch states, simulation counts, and Forge diffs directly."
        )
        if parsed:
            circ_text, circ_ev = _describe_circuit(parsed, file_name, rl_dl)
            sections.append(circ_text)
            evidence_used.extend(circ_ev)
        else:
            suggested_actions.extend(["new-file", "lab"])
        evidence_used.append(f"Model ({meta['model_id']})")

    elif intent in ("general_quantum_concept", "compare_concepts", "math_derivation"):
        if kb_hits:
            for hit in kb_hits:
                sections.append(f"**{hit['title']}**\n{hit['summary']}")
                evidence_used.append(f"KB: {hit['title']}")
        else:
            sections.append("I can explain quantum gates, entanglement, Bloch reduced states, QFT, Grover, QAOA/VQE, IBM Falcon/Eagle/Heron architectures, and QORE verification. Ask about any specific gate, algorithm, or equation.")
        if parsed and any(w in effective_question.lower() for w in ("this", "my", "current", "active", "circuit", "qubit")):
            circ_text, circ_ev = _describe_circuit(parsed, file_name, rl_dl)
            sections.append(circ_text)
            evidence_used.extend(circ_ev)

    elif intent == "hardware_vs_sim":
        sections.append(
            "All QORE Lab simulations execute locally on Qiskit Aer (never live IBM cloud QPUs). "
            "Finite-shot counts and depolarizing/readout error rates are mathematical models, not physical device runs or proof of quantum advantage."
        )
        if rl_dl:
            sections.append(
                f"IBM Hardware Calibration Estimate (from DL model trained on `FakeManilaV2`/`FakeBelemV2`/`FakeAthensV2` + `FakeBrisbane`/`FakeTorino` routing): "
                f"predicted IBM Falcon noisy fidelity ≈ {rl_dl['dl_ibm_predicted_fidelity_l2']*100:.1f}% (opt level 2) vs {rl_dl['dl_ibm_predicted_fidelity_l0']*100:.1f}% (opt level 0), "
                f"estimated routed 2Q overhead factor ≈ {rl_dl['dl_ibm_predicted_2q_overhead_l2']}×."
            )
            evidence_used.append("DL IBM calibration estimate")
        if simulation:
            sim_text, sim_ev = _describe_simulation(simulation)
            sections.append(sim_text)
            evidence_used.extend(sim_ev)
        suggested_actions.extend(["lab", "research"])

    elif intent == "diagnose_error":
        if parse_err:
            loc = f" (line {parse_err['details']['line']})" if isinstance(parse_err.get("details"), dict) and parse_err["details"].get("line") else ""
            sections.append(f"Active circuit parser error [{parse_err['code']}]{loc}: {parse_err['message']}")
            evidence_used.append(f"Parser error ({parse_err['code']})")
        if diagnostics.strip():
            sections.append(f"Active diagnostics:\n{diagnostics.strip()[:800]}")
            evidence_used.append("Active diagnostics")
        if kb_hits:
            sections.append(f"**Reference Guidance — {kb_hits[0]['title']}**\n{kb_hits[0]['summary']}")
        if not parse_err and not diagnostics.strip():
            if parsed:
                sections.append("Your active source parses cleanly with zero syntax or QORE-IR errors.")
                circ_text, circ_ev = _describe_circuit(parsed, file_name, rl_dl)
                sections.append(circ_text)
                evidence_used.extend(circ_ev)
            else:
                sections.append("No active circuit errors or diagnostics are present.")
        suggested_actions.extend(["studio", "terminal"])

    elif intent == "interpret_simulation":
        if simulation:
            sim_text, sim_ev = _describe_simulation(simulation)
            sections.append(sim_text)
            evidence_used.extend(sim_ev)
            if rl_dl:
                sections.append(f"DL IBM hardware reference estimate for this circuit (opt level 2): ≈ {rl_dl['dl_ibm_predicted_fidelity_l2']*100:.1f}% fidelity on calibrated Falcon topology.")
                evidence_used.append("DL IBM calibration estimate")
        elif parsed:
            sections.append("No simulation is attached for the current source yet. Run the simulator in Lab to gather shot counts and TVD.")
            circ_text, circ_ev = _describe_circuit(parsed, file_name, rl_dl)
            sections.append(circ_text)
            evidence_used.extend(circ_ev)
            suggested_actions.append("simulate")
        else:
            sections.append("Open or create a circuit and run a local Aer simulation in Lab to inspect counts and probabilities.")
            suggested_actions.extend(["new-file", "lab"])

    elif intent == "analyze_state":
        if parsed:
            state_text, state_ev = _describe_state(parsed)
            sections.append(state_text)
            evidence_used.extend(state_ev)
            trace = _trace_circuit_evolution(parsed["ir"])
            if trace:
                sections.append("Gate-by-gate statevector evolution:\n" + "\n".join(trace))
                evidence_used.append("Statevector trace")
            suggested_actions.append("lab")
        elif parse_err:
            sections.append(f"Cannot compute quantum state because parsing failed [{parse_err['code']}]: {parse_err['message']}")
            evidence_used.append(f"Parser error ({parse_err['code']})")
        else:
            if kb_hits:
                sections.append(f"**{kb_hits[0]['title']}**\n{kb_hits[0]['summary']}")
                evidence_used.append(f"KB: {kb_hits[0]['title']}")
            else:
                sections.append("Open a supported circuit (≤6 qubits) to inspect Bloch vectors, reduced purities, and amplitudes.")
            suggested_actions.append("new-file")

    elif intent == "optimize_forge":
        if optimization:
            opt_text, opt_ev = _describe_optimization(optimization, rl_dl)
            sections.append(opt_text)
            evidence_used.extend(opt_ev)
            suggested_actions.append("forge")
        elif parsed and rl_dl:
            m = parsed["metrics"]
            sections.append(
                f"No Forge candidate is attached yet for this {m['qubits']}Q, {m['gate_count']}-gate ({m['two_qubit_gate_count']} 2Q) circuit. "
                f"Our RL compiler policy recommends **Forge Level {rl_dl['rl_recommended_level']}** "
                f"(Q-values: L0={rl_dl['rl_q_values']['level_0']}, L1={rl_dl['rl_q_values']['level_1']}, "
                f"L2={rl_dl['rl_q_values']['level_2']}, L3={rl_dl['rl_q_values']['level_3']}). "
                "Note: full operator equivalence verification is available up to 6 qubits."
            )
            evidence_used.extend([f"QORE-IR ({m['qubits']}Q, {m['gate_count']} gates)", f"RL policy (L{rl_dl['rl_recommended_level']})"])
            suggested_actions.extend(["optimize", "forge"])
        else:
            if kb_hits:
                sections.append(f"**{kb_hits[0]['title']}**\n{kb_hits[0]['summary']}")
            else:
                sections.append("Load a circuit in Studio first, then open Forge to generate and verify an optimized candidate.")
            suggested_actions.append("forge")

    elif intent == "experiment_ledger":
        sections.append(
            "Research Ledger persists immutable SQLite snapshots storing exact source, SHA-256 hash, QORE-IR, shots, seed, dependency versions, "
            "and referenced simulation/optimization runs. Reopened snapshots remain read-only until cloned or edited."
        )
        if workspace_summary:
            sections.append(f"Workspace summary: {workspace_summary}.")
            evidence_used.append("Workspace summary")
        suggested_actions.append("research")

    elif intent == "workspace_guide":
        view_tips = {
            "Studio": "You are in Studio: write Qiskit Python or OpenQASM 2.0, inspect live circuits/Bloch/unitarity, then simulate in Lab or optimize in Forge.",
            "Lab": "You are in Quantum Lab: set shots, seed, Aer method (statevector / MPS / stabilizer), and optional modeled noise, then compare sampled vs ideal probabilities.",
            "Forge": "You are in Forge: compile candidates at optimization levels 0–3, inspect gate/depth deltas and operator equivalence (≤6Q), and explicitly approve changes.",
            "Research": "You are in Research Ledger: inspect immutable experiment snapshots and restore drafts without altering recorded history.",
        }
        sections.append(view_tips.get(view, view_tips["Studio"]))
        if parsed:
            circ_text, circ_ev = _describe_circuit(parsed, file_name, rl_dl)
            sections.append(circ_text)
            evidence_used.extend(circ_ev)
            suggested_actions.append("simulate" if not simulation else "optimize")
        else:
            suggested_actions.extend(["new-file", "terminal"])
        if workspace_summary:
            evidence_used.append("Workspace summary")

    else:  # explain_circuit or propose_code
        if parsed:
            circ_text, circ_ev = _describe_circuit(parsed, file_name, rl_dl)
            sections.append(circ_text)
            evidence_used.extend(circ_ev)
            if simulation:
                sim_text, sim_ev = _describe_simulation(simulation)
                sections.append(sim_text)
                evidence_used.extend(sim_ev)
            if optimization:
                opt_text, opt_ev = _describe_optimization(optimization, rl_dl)
                sections.append(opt_text)
                evidence_used.extend(opt_ev)
            if not simulation:
                suggested_actions.append("simulate")
            if not optimization:
                suggested_actions.append("optimize")
        elif parse_err:
            sections.append(f"Active source has a parse error [{parse_err['code']}]: {parse_err['message']}")
            evidence_used.append(f"Parser error ({parse_err['code']})")
            suggested_actions.append("terminal")
        elif kb_hits and intent != "propose_code":
            sections.append(f"**{kb_hits[0]['title']}**\n{kb_hits[0]['summary']}")
            evidence_used.append(f"KB: {kb_hits[0]['title']}")
        else:
            sections.append("No circuit source is open yet. Use Get Started or Apply to Editor on a synthesized circuit below.")
            suggested_actions.append("new-file")

    proposal = _build_proposal(clean_question, source, parsed) if (
        intent == "propose_code" or any(w in clean_question.lower() for w in ("write ", "create ", "generate ", "build ", "propose ", "add measurement", "starter"))
    ) else None
    if proposal:
        sections.append(f"Synthesized & AST-verified circuit proposal: **{proposal['title']}** ({proposal['language']}). Review it below before clicking Apply to Editor.")
        evidence_used.append("Verified code synthesis")

    unique_actions: list[str] = []
    for action in suggested_actions:
        if action not in unique_actions:
            unique_actions.append(action)

    return {
        "available": True,
        "answer": "\n\n".join(sections),
        "model": DEFAULT_MODEL_ID,
        "engine": "local",
        "intent": intent,
        "confidence": confidence,
        "evidence_used": evidence_used,
        "rl_dl_telemetry": rl_dl,
        "proposal": proposal,
        "suggested_actions": unique_actions[:4],
    }
