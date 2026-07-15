"""One-command repair and verification for Operator Learning Pipeline."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT=Path("learning")

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

def main():
    command=[sys.executable,str(ROOT/"engine"/"setup_bootdev.py"),"--apply-history"]
    result=subprocess.run(command,text=True,capture_output=True)
    print(result.stdout,end="")
    if result.returncode:
        print(result.stderr,end="",file=sys.stderr)
        raise SystemExit(result.returncode)

    print("\nPIPELINE VERIFICATION")
    print("-"*68)
    expected={
        "bootdev_learn_python":42,
        "bootdev_learn_linux":9,
        "bootdev_learn_sql":9,
    }
    found={}
    for metadata_path in (ROOT/"tracks").rglob("metadata.json"):
        metadata=load(metadata_path)
        rid=metadata.get("resource_id")
        if rid not in expected:
            continue
        progress=load(metadata_path.parent/"progress.json")
        count=max(
            len(progress.get("completed_units",[])),
            int(progress.get("external_completed_units",0) or 0),
        )
        found[rid]=(count,metadata.get("hierarchy"),metadata_path.parent)

    ok=True
    for rid,count in expected.items():
        actual=found.get(rid)
        if not actual:
            ok=False
            print(f"FAIL {rid}: track missing")
            continue
        state="PASS" if actual[0]>=count else "FAIL"
        ok=ok and state=="PASS"
        print(f"{state} {rid}: {actual[0]} completed · {' > '.join(actual[1])}")
    print("\n" + ("PIPELINE READY" if ok else "PIPELINE NEEDS ATTENTION"))
    raise SystemExit(0 if ok else 1)

if __name__=="__main__":
    main()
