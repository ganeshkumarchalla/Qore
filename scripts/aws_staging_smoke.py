"""Exercise an isolated QORE container without printing workspace or AI data.

Run inside the staging container, which supplies QORE_GATEWAY_TOKEN through its
server-only environment. This script deliberately writes runs only to the
staging copy of SQLite, never to the live production database.
"""

from __future__ import annotations

import os

import httpx


BASE = "http://127.0.0.1:8080"
PUBLIC_ORIGIN = "https://qore-bmh1.onrender.com"
QASM_GHZ = '''OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
cx q[0],q[2];
measure q -> c;
'''
QSHARP_BELL = '''namespace Bell {
    open Std.Intrinsic;
    open Std.Measurement;
    @EntryPoint()
    operation Main() : Result[] {
        use qs = Qubit[2];
        H(qs[0]);
        CX(qs[0], qs[1]);
        return MResetEachZ(qs);
    }
}
'''


def main() -> None:
    token = os.environ.get("QORE_GATEWAY_TOKEN", "")
    assert len(token) >= 32, "Gateway token is unavailable to the staging container"
    origin_headers = {"Origin": PUBLIC_ORIGIN, "Sec-Fetch-Site": "same-origin"}
    with httpx.Client(base_url=BASE, headers={"x-qore-gateway-token": token}, timeout=45) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        assert health.json()["status"] == "ok"
        assert health.json()["ai_available"] is True
        assert httpx.get(BASE + "/api/capabilities", timeout=5).status_code == 403
        capabilities = client.get("/api/capabilities")
        capabilities.raise_for_status()
        assert {"qsharp", "openqasm-2"} <= {item["id"] for item in capabilities.json()["languages"]}
        print("PASS health, language capabilities, direct API protection")

        first = client.get("/api/workspace")
        second = client.get("/api/workspace")
        first.raise_for_status()
        second.raise_for_status()
        assert first.json()["files"] == second.json()["files"]
        assert first.json()["folders"] == second.json()["folders"]
        assert client.cookies.get("qore_workspace")
        print("PASS workspace cookie continuity")

        for label, source, expected in (
            ("OpenQASM GHZ", QASM_GHZ, {"000", "111"}),
            ("Q# Bell", QSHARP_BELL, {"00", "11"}),
        ):
            response = client.post("/api/simulate", json={"source": source, "shots": 256, "seed": 42},
                                   headers=origin_headers)
            response.raise_for_status()
            counts = response.json()["counts"]
            assert set(counts) == expected
            assert sum(counts.values()) == 256
            print(f"PASS {label} measured distribution")

        assistant = client.post("/api/assistant", json={
            "question": "In one sentence, what does a Hadamard gate do to a qubit initially in zero?",
            "view": "Studio",
        }, headers=origin_headers)
        assistant.raise_for_status()
        answer = assistant.json()
        assert answer.get("available") is True and bool(answer.get("answer"))
        assert os.environ.get("GEMINI_API_KEY", "") not in answer["answer"]
        print("PASS QORE Intelligence provider response")


if __name__ == "__main__":
    main()
