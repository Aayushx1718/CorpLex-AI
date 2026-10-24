"""Run from backend/: .venv/bin/python -m app.ml.cli --help."""
import argparse
import json
from pathlib import Path
from app.ml.data import fetch_archive, prepare, verify_license
from app.ml.training import train


def main():
    parser = argparse.ArgumentParser(description='CorpLex clause-type experiment tooling; not a risk classifier.')
    commands = parser.add_subparsers(dest='command', required=True)
    fetch = commands.add_parser('fetch-cuad')
    fetch.add_argument('--output', type=Path, required=True)
    data = commands.add_parser('prepare-cuad')
    data.add_argument('--archive', type=Path, required=True)
    data.add_argument('--output', type=Path, required=True)
    license_command = commands.add_parser('verify-license')
    license_command.add_argument('--dataset', type=Path, required=True)
    license_command.add_argument('--url', required=True)
    training = commands.add_parser('train')
    training.add_argument('--dataset', type=Path, required=True)
    training.add_argument('--output', type=Path, required=True)
    activation = commands.add_parser('activate', help='After reviewing a non-synthetic experiment report')
    activation.add_argument('--run', type=Path, required=True)
    activation.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'fetch-cuad':
            print(fetch_archive(args.output))
        elif args.command == 'prepare-cuad':
            result = prepare(args.archive, args.output)
            print(json.dumps({'counts': result['counts'], 'license': result['license']}, indent=2))
        elif args.command == 'verify-license':
            print(json.dumps(verify_license(args.dataset, args.url), indent=2))
        elif args.command == 'activate':
            from app.ml.service import activate
            activate(args.run, args.root)
            print('Local clause-type model activated; business-risk prediction remains unavailable.')
        else:
            result = train(args.dataset, args.output)
            print(json.dumps({'selected_model': result['selected_model'], 'validation_scope': result['validation_scope']}, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
