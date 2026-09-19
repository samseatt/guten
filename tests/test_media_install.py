import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import install_media

class InstallMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.target=self.root/'host';self.archive=self.root/'bundle.tar'
    def bundle(self,path='a.png',content=b'image',digest=None,extra=None):
        manifest={'format':1,'invalid':[],'missing':[],'files':[{'path':path,'bytes':len(content),'sha256':digest or hashlib.sha256(content).hexdigest()}]}
        with tarfile.open(self.archive,'w') as tar:
            for name,data in [('assets/'+path,content),('media-manifest.json',json.dumps(manifest).encode())]+(extra or []):
                member=tarfile.TarInfo(name);member.size=len(data);tar.addfile(member,io.BytesIO(data))
        return install_media.sha256(self.archive)
    def test_install_and_refuse_replacement(self):
        digest=self.bundle();result=install_media.install(self.archive,digest,self.target)
        self.assertEqual((self.target/'assets/a.png').read_bytes(),b'image')
        self.assertEqual(result['files'],1)
        with self.assertRaises(ValueError):install_media.install(self.archive,digest,self.target)
    def test_wrong_archive_hash_never_creates_target(self):
        self.bundle()
        with self.assertRaises(ValueError):install_media.install(self.archive,'0'*64,self.target)
        self.assertFalse(self.target.exists())
    def test_traversal_and_bad_content_never_activate(self):
        for path,digest in [('../../escaped',None),('a.png','0'*64)]:
            checksum=self.bundle(path=path,digest=digest)
            with self.assertRaises(ValueError):install_media.install(self.archive,checksum,self.target)
            self.assertFalse((self.target/'assets').exists())
            self.assertFalse((self.root/'escaped').exists())
    def test_extra_or_duplicate_members_rejected(self):
        for name in ('unexpected','assets/a.png'):
            digest=self.bundle(extra=[(name,b'image')])
            with self.assertRaises(ValueError):install_media.install(self.archive,digest,self.target)
            self.assertFalse((self.target/'assets').exists())

if __name__=='__main__':unittest.main()
