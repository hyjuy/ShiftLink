"""One complete ZIP extracts into a CNN train/val/test directory with metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def package(cnn,captures,out):
    cnn,captures,out=map(Path,(cnn,captures,out))
    if out.exists():
        raise ValueError('output already exists')
    rows=[json.loads(line) for line in (cnn/'manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    metadata={p.stem:p for p in captures.rglob('*.json')}
    out.mkdir(parents=True)
    path=out/'equipment-cnn-20261008.zip'
    # PNGs are already compressed; ZIP64 permits a single archive larger than 2 GiB.
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
        for row in rows:
            image=cnn/row['image']
            assert hashlib.sha256(image.read_bytes()).hexdigest()==row['sha256']
            archive.write(image,row['image'])
            archive.write(metadata[row['capture_id']],f"metadata/{row['capture_id']}.json")
        archive.write(cnn/'manifest.jsonl','manifest.jsonl')
        archive.write(cnn/'summary.json','dataset-info/summary.json')
        for name in ('README.md','excluded.jsonl','quality-review.md'):
            if (cnn/name).exists():
                archive.write(cnn/name,'dataset-info/'+name)
    with zipfile.ZipFile(path) as archive:
        for row in rows:
            assert hashlib.sha256(archive.read(row['image'])).hexdigest()==row['sha256']
            assert json.loads(archive.read(f"metadata/{row['capture_id']}.json"))['capture_id']==row['capture_id']
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    archives=[dict(file=path.name,images=len(rows),bytes=path.stat().st_size,sha256=digest)]
    (out/'packages.json').write_text(json.dumps(archives,indent=2),encoding='utf-8')
    (out/'SHA256SUMS').write_text(''.join(f"{row['sha256']}  {row['file']}\n" for row in archives),encoding='utf-8')
    return archives


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cnn',type=Path,required=True)
    parser.add_argument('--captures',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(package(args.cnn,args.captures,args.out),indent=2),flush=True)
