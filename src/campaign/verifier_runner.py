import contextlib
import json
import math
import sys
import traceback
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print(json.dumps({"ok": False, "error": "usage: verifier candidate"}))
        return 2

    verifier_path = Path(sys.argv[1])
    candidate_path = Path(sys.argv[2])
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        namespace = {"__name__": "arena_verifier"}
        with contextlib.redirect_stdout(sys.stderr):
            exec(compile(verifier_path.read_text(encoding="utf-8"), str(verifier_path), "exec"), namespace)
            evaluate = namespace.get("evaluate")
            if not callable(evaluate):
                raise RuntimeError("verifier does not define callable evaluate")
            score = float(evaluate(candidate))
        if not math.isfinite(score):
            raise ValueError("verifier returned a non-finite score")
        print(json.dumps({"ok": True, "score": score}, separators=(",", ":")))
        return 0
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

