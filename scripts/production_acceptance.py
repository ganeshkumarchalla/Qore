"""Repeatable, offline acceptance checks of QORE's actual HTTP/worker workflow.

Uses a temporary database, real Qiskit/Aer, and no external provider credentials.
These checks establish the documented bounded feature set, not arbitrary Python,
all Qiskit APIs, cloud hardware execution, or a proof of quantum advantage.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from qiskit import qasm2
from qiskit.quantum_info import Statevector


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

GHZ = """from qiskit import QuantumCircuit
qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure(0, 0)
qc.measure(1, 1)
qc.measure(2, 2)
"""

GROVER = """from qiskit import QuantumCircuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.h(1)
qc.cz(0, 1)
qc.h(0)
qc.h(1)
qc.x(0)
qc.x(1)
qc.cz(0, 1)
qc.x(0)
qc.x(1)
qc.h(0)
qc.h(1)
qc.measure(0, 0)
qc.measure(1, 1)
"""

# Coherent corrections defer measurement; this is a simulator protocol check.
# Undoing the prepared state at the receiver must give |0> on its measured bit.
TELEPORTATION = """from qiskit import QuantumCircuit
from math import pi
qc = QuantumCircuit(3, 3)
qc.ry(pi / 3, 0)
qc.rz(pi / 5, 0)
qc.h(1)
qc.cx(1, 2)
qc.cx(0, 1)
qc.h(0)
qc.cx(1, 2)
qc.cz(0, 2)
qc.rz(-pi / 5, 2)
qc.ry(-pi / 3, 2)
qc.measure(2, 0)
qc.measure(0, 1)
qc.measure(1, 2)
"""

# Original openqasm/qaoa_cut.qasm gate sequence formerly bundled in Explorer.
# It is kept here as a regression fixture and is never seeded into a workspace.
QAOA_CUT = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
h q[0];
h q[1];
h q[2];
h q[3];
cx q[0], q[1];
rz(0.45) q[1];
cx q[0], q[1];
cx q[1], q[2];
rz(0.45) q[2];
cx q[1], q[2];
rx(0.62) q[0];
rx(0.62) q[1];
rx(0.62) q[2];
rx(0.62) q[3];
measure q -> c;
"""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def positive(probabilities):
    return {state for state, value in probabilities.items() if value > 1e-10}


def matrix_residual(cells):
    matrix = np.array([[complex(cell["real"], cell["imag"]) for cell in row] for row in cells])
    require(matrix.ndim == 2 and matrix.shape[0] == matrix.shape[1] and matrix.size > 0, "Unitary matrix is missing or not square")
    return float(np.max(np.abs(matrix.conj().T @ matrix - np.eye(len(matrix)))))


def main():
    # Never load the user's .env or contact an external identity/model/storage
    # service. Environment changes affect this acceptance process only.
    for name in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
                 "GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "QORE_REQUIRE_AUTH", "QORE_ENV", "RENDER", "RENDER_EXTERNAL_URL"):
        os.environ.pop(name, None)
    os.environ["QORE_STORAGE"] = "sqlite"
    with patch("dotenv.load_dotenv", return_value=False):
        from qore.main import create_app

    checks = []
    evidence = {"recorded_at": datetime.now(timezone.utc).isoformat(), "execution": "Isolated TestClient → API → bounded worker → real Qiskit Aer → temporary SQLite",
                "external_services_used": False, "checks": checks,
                "scope": "Supported bounded Qiskit circuit syntax and OpenQASM 2.0; ideal/noisy local simulation; operator validation within configured limits. No hardware or universal Qiskit compatibility claim."}

    def check(name, action):
        started = time.perf_counter()
        try:
            details = action()
            checks.append({"name": name, "passed": True, "elapsed_seconds": round(time.perf_counter() - started, 3), "details": details})
        except AssertionError as error:
            checks.append({"name": name, "passed": False, "elapsed_seconds": round(time.perf_counter() - started, 3), "error": str(error)})
        except Exception as error:
            checks.append({"name": name, "passed": False, "elapsed_seconds": round(time.perf_counter() - started, 3), "error": "Unexpected runtime failure: " + type(error).__name__})

    with tempfile.TemporaryDirectory(prefix="qore-acceptance-") as directory:
        database = Path(directory) / "acceptance.sqlite3"
        application = create_app(database)
        with TestClient(application) as client:
            def api(path, body=None, method=None):
                response = client.request(method or ("POST" if body is not None else "GET"), "/api" + path, json=body)
                data = response.json()
                code = data.get("error", {}).get("code", "unknown") if isinstance(data, dict) else "unknown"
                require(response.status_code in {200, 201}, f"API {path} failed with HTTP {response.status_code} ({code})")
                return data

            cache = {}

            def health_check():
                health = api("/health")
                require(health["status"] == "ok" and health["storage"] == "sqlite", "Isolated service is unavailable")
                require(not health["ai_available"] and not health["auth_configured"], "External service configuration was inherited")
                require(api("/projects") == [] and api("/experiments") == [] and api("/runs") == [], "New workspace was not empty")
                evidence["versions"], evidence["limits"] = health["versions"], health["limits"]
                return {"initial_records": 0, "external_services_disabled": True}

            def ghz_check():
                result = api("/simulate", {"source": GHZ, "shots": 4096, "seed": 42})
                cache["ghz"] = result
                require(set(result["counts"]) == {"000", "111"}, "GHZ contains an impossible outcome or misses an expected outcome")
                require(sum(result["counts"].values()) == 4096, "GHZ shot total is incorrect")
                require(positive(result["theoretical_probabilities"]) == {"000", "111"}, "GHZ ideal support is incorrect")
                require(all(abs(result["theoretical_probabilities"][state] - .5) < 1e-10 for state in ("000", "111")), "GHZ ideal probabilities are incorrect")
                require(result["tvd"] < .035, "GHZ finite-shot divergence is too large")
                require(len(result["bloch_vectors"]) == 3 and all(abs(vector["purity"] - .5) < .001 for vector in result["bloch_vectors"]), "GHZ reduced-qubit states are incorrect")
                return {"counts": result["counts"], "ideal": {"000": .5, "111": .5}, "tvd": result["tvd"], "reduced_purities": [v["purity"] for v in result["bloch_vectors"]]}

            def grover_check():
                result = api("/simulate", {"source": GROVER, "shots": 2048, "seed": 42})
                require(result["counts"] == {"11": 2048}, "Grover did not identify the marked state")
                require(abs(result["theoretical_probabilities"]["11"] - 1) < 1e-10, "Grover ideal marked probability is incorrect")
                return {"marked_state": "11", "counts": result["counts"], "ideal_success_probability": result["theoretical_probabilities"]["11"]}

            def teleport_check():
                result = api("/simulate", {"source": TELEPORTATION, "shots": 4096, "seed": 42})
                require(sum(result["counts"].values()) == 4096 and all(state.endswith("0") for state in result["counts"]), "Receiver did not recover the prepared state")
                require(positive(result["theoretical_probabilities"]) == {"000", "010", "100", "110"}, "Deferred teleportation ideal support is incorrect")
                return {"counts": result["counts"], "receiver_recovery_probability": sum(p for state, p in result["theoretical_probabilities"].items() if state.endswith("0")), "protocol": "Deferred-measurement coherent teleportation; receiver state verified by inverse preparation"}

            def qaoa_check():
                result = api("/simulate", {"source": QAOA_CUT, "shots": 8192, "seed": 42})
                circuit = qasm2.loads(QAOA_CUT, custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS).remove_final_measurements(inplace=False)
                expected = Statevector.from_instruction(circuit).probabilities_dict()
                error = max(abs(result["theoretical_probabilities"].get(state, 0) - float(probability)) for state, probability in expected.items())
                require(result["metrics"]["qubits"] == 4 and sum(result["counts"].values()) == 8192, "QAOA fixture dimensions or shot total are wrong")
                require(error < 1e-10 and result["tvd"] < .06, "QAOA output disagrees with an independent Qiskit statevector")
                residual = matrix_residual(result["unitary_matrix"])
                require(len(result["unitary_matrix"]) == 16 and residual < .002, "QAOA display unitary is not orthonormal within its four-decimal precision")
                require(len(result["bloch_vectors"]) == 4, "QAOA Bloch evidence is missing")
                return {"fixture": "Original openqasm/qaoa_cut.qasm regression sequence", "qubits": 4, "counts": result["counts"], "tvd": result["tvd"], "ideal_reference_max_error": error, "unitary_dimension": 16, "display_unitary_max_residual": residual, "claim": "Circuit simulation verified; no optimization optimum claim"}

            def noise_check():
                noisy = api("/simulate", {"source": GHZ, "shots": 4096, "seed": 42, "noise_rate": .06, "readout_error": .04})
                off_support = sum(value for state, value in noisy["counts"].items() if state not in {"000", "111"})
                require(noisy["noise_applied"] and off_support > 50 and sum(noisy["counts"].values()) == 4096, "Configured noise did not affect measured outcomes")
                ideal = cache["ghz"]["theoretical_probabilities"]
                require(max(abs(noisy["theoretical_probabilities"][state] - probability) for state, probability in ideal.items()) < 1e-10, "Noise replaced the ideal reference with a sampled histogram")
                return {"counts": noisy["counts"], "off_ideal_support_shots": off_support, "noise_rate": noisy["noise_rate"], "readout_error": noisy["readout_error"], "tvd_to_ideal": noisy["tvd"]}

            def unitary_check():
                parsed = api("/parse", {"source": GHZ})
                residual = matrix_residual(parsed["unitary_matrix"])
                require(len(parsed["unitary_matrix"]) == 8 and residual < .001, "GHZ unitary failed U†U = I within display precision")
                return {"dimension": 8, "max_abs_UdaggerU_minus_I": residual, "display_precision_decimals": 4, "tolerance": .001}

            def forge_check():
                redundant = GHZ.replace("qc.h(0)", "qc.x(0)\nqc.x(0)\nqc.h(0)")
                optimized = api("/optimize", {"source": redundant, "level": 2, "seed": 42})
                require(optimized["validation"]["status"] == "validated", "Forge did not validate operator equivalence")
                require(optimized["candidate"]["metrics"]["gate_count"] < optimized["original"]["metrics"]["gate_count"], "Forge failed to remove cancelling gates")
                result = api("/simulate", {"source": optimized["candidate"]["source"], "shots": 2048, "seed": 42})
                require(positive(result["theoretical_probabilities"]) == {"000", "111"}, "Forge candidate changed the GHZ ideal support")
                require(all(abs(result["theoretical_probabilities"][state] - .5) < 1e-10 for state in ("000", "111")), "Forge candidate changed ideal probabilities")
                return {"original_gates": optimized["original"]["metrics"]["gate_count"], "candidate_gates": optimized["candidate"]["metrics"]["gate_count"], "validation": optimized["validation"]}

            def invalid_check():
                cases = [("/parse", {"source": "import os\nos.remove('never-created')"}),
                         ("/parse", {"source": "from qiskit import QuantumCircuit\nqc=QuantumCircuit(11,11)"}),
                         ("/parse", {"source": "OPENQASM 3.0; qubit q;"}),
                         ("/simulate", {"source": GHZ, "shots": 0}),
                         ("/simulate", {"source": GHZ, "shots": 100001}),
                         ("/parse", {"source": "from qiskit import QuantumCircuit\nqc=QuantumCircuit(1,1)\nqc.unknown_gate(0)"})]
                rejected = []
                for path, payload in cases:
                    response = client.post("/api" + path, json=payload)
                    require(400 <= response.status_code < 500, "Invalid source or configuration was not safely rejected")
                    rejected.append({"status": response.status_code, "code": response.json()["error"]["code"]})
                return {"rejected_cases": len(rejected), "responses": rejected}

            def ledger_check():
                project = api("/projects", {"name": "Acceptance circuit", "source": GHZ})
                run = cache["ghz"]
                saved = api("/experiments", {"name": "Acceptance evidence", "source": GHZ, "project_id": project["id"], "simulation_id": run["id"]})
                require(saved["simulation"] == run, "Ledger did not retain exact run evidence")
                api("/projects/" + project["id"], {"name": "Edited acceptance circuit", "source": GHZ + "# later revision\n"}, method="PUT")
                require(api("/experiments/" + saved["id"]) == saved, "Editing source changed historical evidence")
                require(client.put("/api/experiments/" + saved["id"], json={"name": "tamper"}).status_code == 405, "Ledger incorrectly permits overwrite")
                require(client.delete("/api/experiments/" + saved["id"]).status_code == 405, "Ledger incorrectly permits deletion")
                mismatch = client.post("/api/experiments", json={"name": "Wrong source", "source": GHZ + "# altered\n", "simulation_id": run["id"]})
                require(mismatch.status_code == 409, "Ledger accepted a run from different source")
                cache["snapshot"] = saved
                return {"exact_snapshot_retained": True, "survives_project_edit": True, "overwrite_status": 405, "delete_status": 405, "source_mismatch_status": 409}

            for name, action in (("Empty isolated workspace and health", health_check), ("Three-qubit GHZ and reduced states", ghz_check),
                                 ("Grover search marks 11", grover_check), ("Deferred teleportation receiver recovery", teleport_check),
                                 ("Four-qubit QAOA regression and independent reference", qaoa_check), ("Noise and ideal-reference separation", noise_check),
                                 ("Displayed unitary orthonormality", unitary_check), ("Forge operator equivalence and gate reduction", forge_check),
                                 ("Unsupported source and invalid configuration rejection", invalid_check), ("Immutable ledger and exact-source provenance", ledger_check)):
                check(name, action)

        def restart_check():
            saved = cache["snapshot"]
            with TestClient(create_app(database)) as restarted:
                response = restarted.get("/api/experiments/" + saved["id"])
                require(response.status_code == 200 and response.json() == saved, "Ledger evidence changed after application restart")
            return {"restored_snapshot_identical": True}

        check("Ledger restoration after application restart", restart_check)

    evidence["passed"] = sum(item["passed"] for item in checks)
    evidence["failed"] = len(checks) - evidence["passed"]
    evidence["status"] = "passed" if evidence["failed"] == 0 else "failed"
    output = ROOT / "evidence"
    output.mkdir(exist_ok=True)
    (output / "production_acceptance.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    lines = ["# QORE production acceptance", "", f"Result: **{evidence['status'].upper()}** — {evidence['passed']}/{len(checks)} checks passed.", "", evidence["execution"], "", evidence["scope"], "", "| Check | Result | Seconds |", "| --- | --- | ---: |"]
    lines.extend(f"| {item['name']} | {'PASS' if item['passed'] else 'FAIL'} | {item['elapsed_seconds']} |" for item in checks)
    lines.extend(["", "All data was created in a temporary SQLite database. No live user files, accounts, external services, or credentials were used.", "", "Quantitative results:"])
    for item in checks:
        lines.extend(["", "## " + item["name"], "", "```json", json.dumps(item.get("details", {"error": item.get("error")}), indent=2, ensure_ascii=False), "```"])
    (output / "production_acceptance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "passed": evidence["passed"], "failed": evidence["failed"], "report": str(output / "production_acceptance.json")}))
    return 0 if evidence["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
