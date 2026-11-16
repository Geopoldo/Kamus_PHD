"""Controlled supervisor test: fail once, then succeed. Does not use the GPU."""
from pathlib import Path
p=Path(__file__).resolve().parent/'results/recovery_test_count.txt'
n=int(p.read_text())+1 if p.exists() else 1
p.write_text(str(n))
raise SystemExit(1 if n==1 else 0)
