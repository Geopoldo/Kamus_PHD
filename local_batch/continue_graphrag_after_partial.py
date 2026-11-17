"""Continue corpus expansion only after the requested partial graph is published."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
DIRECTORY = HERE / 'results/knowledge_graph/pilot_30'


def main():
    expected = sys.argv[1]
    event = DIRECTORY / 'runs' / expected / 'continuation.json'

    def record(status, **extra):
        event.write_text(json.dumps(dict(status=status, time=time.time(),
                                        after_run=expected, **extra), indent=2))

    record('waiting_for_partial_publication')
    while True:
        active = json.loads((DIRECTORY / 'active.json').read_text())
        manifest = json.loads((DIRECTORY / 'runs' / expected / 'manifest.json').read_text())
        if active.get('run_id') == expected and manifest.get('status') == 'complete':
            break
        state = subprocess.run(['systemctl', '--user', 'is-active',
                                'maph-graphrag-partial-20261116.service'],
                               capture_output=True, text=True).stdout.strip()
        if state not in ('active', 'activating'):
            record('stopped_without_publication', build_status=manifest.get('status'))
            return 1
        time.sleep(15)
    record('starting_corpus_expansion')
    result = subprocess.run([sys.executable, str(HERE / 'graphrag_pilot.py'),
                             '--prepare', '--all-pages', '--run', '--publish'], cwd=HERE.parent)
    record('complete' if result.returncode == 0 else 'stopped', returncode=result.returncode)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
