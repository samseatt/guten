"""Referenced media packaging tests; synthetic content, no database writes."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import package_media as media

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.assets=self.root/'source';self.assets.mkdir()
        (self.assets/'default.png').write_bytes(b'fallback')
        (self.assets/'used.png').write_bytes(b'referenced')
        (self.assets/'unused.png').write_bytes(b'unused')
        self.rows=[{'schema':schema,'table':'pages','record':{'id':1,'primary_image':'/assets/used.png'}} for schema in ('draft','published')]

    def test_references_and_url_boundaries(self):
        self.assertEqual(media.references('![x](/assets/a(b).png) <img src="/assets/c%20d.png"> background:url(/assets/e.png)',set()),{'a(b).png','c d.png','e.png'})
        self.assertEqual(media.references('/assets/a b(1).png',set(),True),{'a b(1).png'})
        self.assertEqual(media.references('https://ours.example/assets/x.png?q=1',{'ours.example'},True),{'x.png'})
        self.assertEqual(media.references('https://other.example/assets/x.png',{'ours.example'},True),set())
        for value in ('/assets/../secret','/assets/%2e%2e/secret','/assets/a%5cb','/assets/a//b'):
            with self.assertRaises(ValueError):media.local_path(value,set())

    def test_bundle_includes_union_fallback_and_manifest_not_unused(self):
        report=media.inventory(self.rows,self.assets)
        target=self.root/'media.tar'
        digest=media.bundle(report,self.assets,target)
        self.assertEqual(digest,hashlib.sha256(target.read_bytes()).hexdigest())
        with tarfile.open(target) as archive:
            self.assertEqual(set(archive.getnames()),{'assets/default.png','assets/used.png','media-manifest.json'})
            self.assertEqual(json.load(archive.extractfile('media-manifest.json')),report)
        self.assertEqual(len(report['files'][1]['locations']),2)
        with self.assertRaises(ValueError):media.bundle(report,self.assets,target)
        self.assertTrue((self.assets/'unused.png').exists())

    def test_changed_source_does_not_leave_completed_bundle(self):
        report=media.inventory(self.rows,self.assets)
        (self.assets/'used.png').write_bytes(b'changed')
        target=self.root/'media.tar'
        with self.assertRaises(ValueError):media.bundle(report,self.assets,target)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.glob('.media-*')),[])

    def test_missing_requires_exact_acknowledgment(self):
        (self.assets/'used.png').unlink()
        report=media.inventory(self.rows,self.assets)
        with self.assertRaises(ValueError):media.bundle(report,self.assets,self.root/'fail.tar')
        media.bundle(report,self.assets,self.root/'ok.tar',['used.png'])

    def test_symlink_swap_and_traversal_inventory_rejected(self):
        report=media.inventory(self.rows,self.assets)
        (self.assets/'used.png').unlink()
        (self.root/'outside').write_bytes(b'referenced')
        (self.assets/'used.png').symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):media.bundle(report,self.assets,self.root/'fail.tar')
        self.assertTrue(media.inventory(self.rows,self.assets)['invalid'])
        report['files'][0]['path']='../outside'
        with self.assertRaises(ValueError):media.bundle(report,self.assets,self.root/'bad.tar')

    def test_relative_favicon_is_reported_not_guessed(self):
        self.rows.append({'schema':'published','table':'sites','record':{'id':2,'name':'test','url':'test.example','favicon':'favicon.ico','logo':'/assets/used.png'}})
        report=media.inventory(self.rows,self.assets)
        self.assertEqual(report['unresolved_image_fields'][0]['value'],'favicon.ico')
        self.assertEqual(report['domains'][0]['host'],'test.example')

if __name__=='__main__':unittest.main()
