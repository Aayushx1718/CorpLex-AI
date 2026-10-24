"""Short-lived parser process. No document data is written to disk or logs."""
import json
import sys

# Linux cloud/local deployments enforce process memory and CPU ceilings.
# Other platforms retain the parent-enforced wall-clock timeout.
if sys.platform == 'linux':
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))

from dataclasses import asdict
from app.extraction import ExtractionError, MAX_FILE_BYTES, extract

if __name__ == '__main__':
    try:
        result = extract(sys.stdin.buffer.read(MAX_FILE_BYTES + 1), sys.argv[1], sys.argv[2] or None)
        sys.stdout.write(json.dumps(asdict(result), default=str))
    except ExtractionError as exc:
        sys.stdout.write(json.dumps({'error': str(exc)}))
        sys.exit(2)
    except Exception:
        # Never emit parser tracebacks containing source content.
        sys.exit(3)
