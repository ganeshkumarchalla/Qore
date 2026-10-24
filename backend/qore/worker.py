"""Bounded subprocess protocol. User programs are interpreted as data, never executed."""

import json
import sys

from . import quantum


def main():
    try:
        request = json.loads(sys.stdin.read(100_000))
        operation = request["operation"]
        args = request["args"]
        functions = {"parse": quantum.parse_source, "simulate": quantum.simulate, "optimize": quantum.optimize}
        if operation not in functions:
            raise ValueError("Unknown operation")
        result = functions[operation](**args)
        print(json.dumps({"result": result}, allow_nan=False))
    except quantum.QuantumError as error:
        print(json.dumps({"error": {"code": error.code, "message": error.message,
                                    "details": getattr(error, "details", None)}}, allow_nan=False))
    except Exception:
        # Do not expose host paths, environment variables, or provider secrets.
        print(json.dumps({"error": {"code": "quantum_failure", "message": "The quantum worker could not complete this operation.", "details": None}}))


if __name__ == "__main__":
    main()
