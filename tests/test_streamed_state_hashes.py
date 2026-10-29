"""Exercise the actual C# sink with independent Python SHA-256 expectations."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def installed_toolchain():
    dotnet=shutil.which('dotnet')
    if not dotnet and os.name=='nt':
        installed=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'dotnet/dotnet.exe'
        if installed.is_file():dotnet=str(installed)
    if not dotnet:
        raise unittest.SkipTest('An existing .NET SDK is needed for the data-free C# checks.')
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    sdks=subprocess.check_output([dotnet,'--list-sdks'],text=True,creationflags=flags)
    candidates=[]
    for line in sdks.splitlines():
        match=re.fullmatch(r'(\S+) \[(.+)\]',line)
        if not match:
            continue
        version,folder=match.groups()
        compiler=Path(folder)/version/'Roslyn/bincore/csc.dll'
        packs=Path(folder).parent/'packs/Microsoft.NETCore.App.Ref'
        if compiler.is_file() and packs.is_dir():
            candidates.append((version,compiler,packs))
    if not candidates:
        raise unittest.SkipTest('The installed SDK lacks its compiler or reference packs.')
    _,compiler,packs=candidates[-1]
    refs=[]
    for folder in packs.iterdir():
        if (folder/'ref').is_dir():
            refs.extend(p for p in (folder/'ref').iterdir() if re.fullmatch(r'net\d+\.\d+',p.name))
    if not refs:
        raise unittest.SkipTest('No installed .NET reference framework was found.')
    references=max(refs,key=lambda p:tuple(map(int,p.name[3:].split('.'))))
    return dotnet,compiler,references,flags


class StreamedStateHashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dotnet,compiler,references,flags=installed_toolchain()
        with tempfile.TemporaryDirectory(prefix='lsd-hash-stream-') as temp:
            folder=Path(temp);binary=folder/'checks.dll'
            target=references.name[3:]
            (folder/'checks.runtimeconfig.json').write_text(json.dumps({'runtimeOptions':{
                'tfm':references.name,'framework':{'name':'Microsoft.NETCore.App','version':target+'.0'}}}),encoding='utf-8')
            command=[dotnet,'exec',str(compiler),'/nologo','/target:exe','/nostdlib+',
                '/deterministic+','/main:Lsd.Research.Headless.HashStreamChecks','/out:'+str(binary),
                *('/reference:'+str(p) for p in sorted(references.glob('*.dll'))),
                str(ROOT/'research/headless/BoundedSha256Stream.cs'),str(ROOT/'research/headless/HashStreamChecks.cs')]
            compiled=subprocess.run(command,capture_output=True,text=True,timeout=30,creationflags=flags)
            if compiled.returncode:
                raise AssertionError('C# sink fixture did not compile:\n'+compiled.stdout+compiled.stderr)
            observed=subprocess.run([dotnet,str(binary)],capture_output=True,text=True,timeout=30,creationflags=flags)
            if observed.returncode:
                raise AssertionError('C# sink fixture failed:\n'+observed.stdout+observed.stderr)
            cls.observed=json.loads(observed.stdout)

    def test_standard_vectors_and_mixed_write_methods(self):
        for row in self.observed['vectors']:
            expected=bytes((i*17+13)&255 for i in range(row['length']))
            self.assertEqual(row['hash'],hashlib.sha256(expected).hexdigest())
            self.assertEqual(row['position'],len(expected))
        row=self.observed['offset_chunks']
        self.assertEqual(row['length'],5)
        self.assertEqual(row['hash'],hashlib.sha256(bytes((0xA5,3,4,5,6))).hexdigest())

    def test_boundaries_and_rejected_writes_preserve_the_digest(self):
        row=self.observed['boundary']
        self.assertEqual(row['length'],128)
        self.assertEqual(row['overflow'],'IOException')
        self.assertEqual(row['hash'],hashlib.sha256(bytes([7])*128).hexdigest())
        invalid=self.observed['validation']
        self.assertEqual(invalid['length_after_errors'],0)
        self.assertEqual(invalid['hash'],hashlib.sha256(b'').hexdigest())
        self.assertEqual(invalid['errors'],dict(negative_limit='ArgumentOutOfRangeException',null='ArgumentNullException',
            negative_offset='ArgumentOutOfRangeException',negative_count='ArgumentOutOfRangeException',
            out_of_bounds='ArgumentOutOfRangeException',large_count='ArgumentOutOfRangeException',over_limit='IOException'))

    def test_finalization_and_disposal_close_the_write_contract(self):
        row=self.observed['finalization']
        self.assertEqual(row['first'],hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(row['first'],row['second'])
        self.assertFalse(row['can_write'])
        self.assertEqual(row['write_error'],'InvalidOperationException')
        self.assertEqual(row['length'],3)
        disposed=self.observed['disposal']
        self.assertFalse(disposed['can_write'])
        for key in ('write_error','hash_error','length_error'):
            self.assertEqual(disposed[key],'ObjectDisposedException')

    def test_random_access_and_reads_are_explicitly_unsupported(self):
        row=self.observed['unsupported']
        self.assertFalse(row['can_read']);self.assertFalse(row['can_seek'])
        for key in ('read','seek','resize','set_position'):
            self.assertEqual(row[key],'NotSupportedException')

    def test_64_MiB_stream_matches_an_incremental_reference(self):
        row=self.observed['large_stream']
        self.assertEqual(row['length'],64*1024*1024)
        reference=hashlib.sha256()
        chunk=bytes((i*17+13)&255 for i in range(row['chunk_bytes']))
        for _ in range(row['chunk_repetitions']):reference.update(chunk)
        self.assertEqual(row['hash'],reference.hexdigest())


if __name__=='__main__':unittest.main()
