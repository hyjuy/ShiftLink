"""HPU entry point; all projection and storage logic is equipment-independent."""
from .incident_ontology import project_incident


def project_hpu(bundle):
    return project_incident(bundle, equipment_type='HPU')


def main(argv=None):
    """Run stage-3 diagnostics independently of MES/PDA services."""
    import argparse
    import json
    import os
    from pathlib import Path
    from .ontology_shadow import failure, run_shadow

    parser = argparse.ArgumentParser(description='HPU ontology shadow diagnostics on an approved SQLite copy')
    parser.add_argument('--mode', choices=('off', 'shadow'))
    parser.add_argument('--db', type=Path)
    parser.add_argument('--incident-id')
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--manifest', type=Path, help='source_namespace and verified config_catalog_hashes JSON')
    parser.add_argument('--output', type=Path, help='new JSON file; existing files are never overwritten')
    parser.add_argument('--max-records', type=int, default=30)
    args = parser.parse_args(argv)
    mode = args.mode if args.mode is not None else os.environ.get('SHIFTLINK_HPU_ONTOLOGY', 'off')
    if mode == 'shadow':
        if any(value is None for value in (args.db, args.incident_id, args.catalog, args.manifest)):
            parser.error('shadow requires --db, --incident-id, --catalog and --manifest')
        try:
            manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
            catalog = json.loads(args.catalog.read_text(encoding='utf-8'))
            if not isinstance(manifest, dict) or not isinstance(catalog, dict):
                raise ValueError('JSON objects are required')
            namespace = manifest['source_namespace']
            hashes = manifest.get('config_catalog_hashes', {})
            if not isinstance(hashes, dict):
                raise ValueError('config_catalog_hashes must be an object')
            result = run_shadow(args.db, args.incident_id, source_namespace=namespace,
                catalog=catalog, config_catalog_hashes=hashes, mode=mode, output=args.output,
                max_records=args.max_records)
        except Exception as error:
            result = failure('input', error)
    else:
        result = run_shadow(mode=mode)
    print(json.dumps({k:v for k,v in result.items() if k != 'graph'}, ensure_ascii=False, sort_keys=True))
    return 1 if result['status'] == 'error' else 0


if __name__ == '__main__':
    raise SystemExit(main())
