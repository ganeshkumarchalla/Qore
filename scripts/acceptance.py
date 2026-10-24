"""Exercise the actual HTTP service and persist inspectable acceptance evidence."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="evidence/acceptance.json")
    args = parser.parse_args()

    def api(path, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(args.url + "/api" + path, data=data, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=40) as response:
            return json.load(response)

    health = api("/health")
    examples = api("/examples")
    source = next(e["source"] for e in examples if e["id"] == "bell")
    project = api("/projects", {"name": "Bell · acceptance evidence", "source": source})
    parsed = api("/parse", {"source": source})
    simulation = api("/simulate", {"source": source, "shots": 1024, "seed": 42, "project_id": project["id"]})
    optimization = api("/optimize", {"source": source, "level": 2, "seed": 42, "project_id": project["id"]})
    experiment = api("/experiments", {"name": "Bell · verified workflow", "project_id": project["id"], "source": source,
                                     "simulation_id": simulation["id"], "optimization_id": optimization["id"]})
    reopened = api("/experiments/" + experiment["id"])
    assert reopened == experiment, "Reopened record changed"
    assert sum(simulation["counts"].values()) == 1024
    assert set(simulation["counts"]) <= {"00", "11"}
    assert abs(simulation["theoretical_probabilities"]["00"] - 0.5) < 1e-10
    assert optimization["validation"]["status"] == "validated"
    redundant_source = next(e["source"] for e in examples if e["id"] == "redundant-bell")
    redundant = api("/optimize", {"source": redundant_source, "level": 2, "seed": 42})
    candidate = api("/simulate", {"source": redundant["candidate"]["source"], "shots": 1024, "seed": 42})
    assert redundant["candidate"]["metrics"]["gate_count"] < redundant["original"]["metrics"]["gate_count"]
    assert redundant["validation"]["status"] == "validated"
    evidence = {"recorded_at": datetime.now(timezone.utc).isoformat(), "service": args.url,
                "health": health, "parsed": parsed, "bell_experiment": experiment,
                "reopened_identical": reopened == experiment,
                "redundant_bell_optimization": redundant, "approved_candidate_simulation": candidate}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output": str(output.resolve()), "counts": simulation["counts"],
                      "tvd": simulation["tvd"], "bell_differences": optimization["differences"],
                      "validation": optimization["validation"], "reopened_identical": True,
                      "redundant_bell_differences": redundant["differences"]}, indent=2))


if __name__ == "__main__":
    main()
