"""Create/verify a committed-blob and SHA256 inventory of this proof bundle."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from watch.inspection_runtime import retain


def verify(proof: Path, create: bool = False) -> dict:
    repo=Path(__file__).resolve().parents[1]
    proof=proof.resolve()
    if not proof.is_relative_to(repo): raise ValueError('proof outside repository')
    relative=proof.relative_to(repo).as_posix()
    index=proof/'ARTIFACTS.json'
    if create:
        raw=subprocess.run(['git','ls-files','--stage','-z','--',relative],cwd=repo,capture_output=True,check=True).stdout
        entries=[]
        for entry in raw.split(b'\0'):
            if not entry: continue
            metadata,name=entry.split(b'\t',1)
            mode,blob,stage=metadata.decode().split()
            path=repo/name.decode('utf-8')
            if path==index: continue
            if stage!='0' or mode=='120000': raise ValueError('unmerged or symlink evidence')
            if not path.resolve().is_relative_to(proof): raise ValueError('artifact escape')
            data=path.read_bytes()
            expected_blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if expected_blob!=blob: raise ValueError('working bytes differ from staged Git blob: '+str(path))
            entries.append({'path':path.relative_to(proof).as_posix(),'sha256':hashlib.sha256(data).hexdigest(),
                'git_blob':expected_blob,'bytes':len(data)})
        if not entries: raise ValueError('no staged proof artifacts')
        retain(index,{'schema':'watch.relationship-artifacts/v1','files':entries,
            'scope':'inventory excludes itself and later appended review reports; execution receipts retain their own code hashes'})
    manifest=json.loads(index.read_bytes())
    if not manifest['files'] or len({r['path'] for r in manifest['files']})!=len(manifest['files']):
        raise ValueError('empty or duplicate artifact inventory')
    for row in manifest['files']:
        path=(proof/row['path']).resolve()
        if not path.is_relative_to(proof): raise ValueError('artifact escape')
        data=path.read_bytes()
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise ValueError('artifact hash mismatch: '+row['path'])
        if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=row['git_blob']:
            raise ValueError('Git blob mismatch: '+row['path'])
    return {'status':'verified','files':len(manifest['files']),'bytes':sum(r['bytes'] for r in manifest['files'])}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--proof',type=Path,default=Path('proofs/watch-relationships'))
    p.add_argument('--create',action='store_true')
    args=p.parse_args()
    sys.stdout.write(json.dumps(verify(args.proof,args.create))+'\n')
