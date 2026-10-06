"""Image tool persistence and API behavior, using synthetic stores only."""
import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import http.client
import threading

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import library

SVG=b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60"><rect width="120" height="60" fill="white"/></svg>'
DOC={'version':1,'width':120,'height':60,'shapes':[{'id':'one','type':'ruler','color':'#ff3344','width':2,'points':[{'x':0,'y':0},{'x':30,'y':40}]}]}

class ImageToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'data'
        self.store=library.Store(self.root)
        result=self.store.import_uploads('tools',[{'path':'sample.svg','data':base64.b64encode(SVG).decode()}],options={'auto_export':False})
        self.lid=result['library_id']
        self.row=self.store.state()['images'][0]

    def save(self,doc=DOC,revision=0,blob=None):
        return self.store.save_markup(self.row['id'],blob or self.row['blob'],revision,doc)

    def test_persists_independently_of_source_and_reopens(self):
        self.assertTrue(hasattr(self.store,'save_markup'),'persistent image markup is missing')
        self.assertEqual(self.save()['revision'],1)
        loaded=library.Store(self.root).markup(self.row['id'])
        self.assertEqual(loaded['document'],DOC)
        self.assertEqual(self.store.image(self.row['id'])[0],SVG)
        self.store.annotate(self.row['id'],{'note':'keep'})
        self.assertEqual(self.store.markup(self.row['id'])['document'],DOC)

    def test_rejects_stale_save_and_changed_image_bytes(self):
        self.assertTrue(hasattr(self.store,'save_markup'),'persistent image markup is missing')
        self.save()
        with self.assertRaises(ValueError):self.save(revision=0)
        changed=SVG.replace(b'white',b'blue')
        self.store.import_uploads('tools',[{'path':'sample.svg','data':base64.b64encode(changed).decode()}],self.lid,options={'auto_export':False})
        self.assertIsNone(self.store.markup(self.row['id'])['document'])
        with self.assertRaises(ValueError):self.save(revision=1)
        self.store.import_uploads('tools',[{'path':'sample.svg','data':base64.b64encode(SVG).decode()}],self.lid,options={'auto_export':False})
        self.assertEqual(self.store.markup(self.row['id'])['document'],DOC)

    def test_rejects_invalid_geometry_and_preserves_saved_document(self):
        self.assertTrue(hasattr(self.store,'save_markup'),'persistent image markup is missing')
        self.save()
        for mutate in [lambda d:d.update(width=0),lambda d:d['shapes'][0]['points'][0].update(x=float('nan')),lambda d:d['shapes'][0]['points'][0].update(y=61),lambda d:d['shapes'][0].update(type='script'),lambda d:d['shapes'][0].update(color='url(evil)'),lambda d:d['shapes'][0].update(points=[]),lambda d:d.update(shapes=d['shapes']*1001)]:
            broken=copy.deepcopy(DOC);mutate(broken)
            with self.assertRaises(ValueError):self.save(broken,1)
        self.assertEqual(self.store.markup(self.row['id'])['document'],DOC)

    def test_saved_markup_is_in_readonly_offline_snapshot(self):
        self.assertTrue(hasattr(self.store,'save_markup'),'persistent image markup is missing')
        self.save()
        exported=self.store.export(library_id=self.lid)
        page=Path(exported['path']).read_text()
        payload=json.loads(page.split('<script type="application/json" id="catalog">')[1].split('</script>')[0])
        self.assertEqual(payload['images'][0]['markup'],DOC)
        self.assertIn('FigNestImageTools',page)

    def test_http_save_get_conflict_and_authentication(self):
        server=library.make_server(self.store)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        def request(method,path,body=None,token=True):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'Origin':'http://127.0.0.1:'+str(server.server_port),'Content-Type':'application/json'}
            if token:headers['X-Viewer-Token']=server.token
            connection.request(method,path,json.dumps(body) if body else None,headers)
            response=connection.getresponse();content=response.read();code=response.status;connection.close()
            return code,content
        try:
            route='/api/markup?id='+self.row['id']
            self.assertEqual(request('GET',route,token=False)[0],403)
            body={'id':self.row['id'],'blob':self.row['blob'],'revision':0,'document':DOC}
            self.assertEqual(request('POST','/api/markup',body,False)[0],403)
            self.assertEqual(request('POST','/api/markup',body)[0],200)
            code,raw=request('GET',route);self.assertEqual(code,200)
            self.assertEqual(json.loads(raw)['document'],DOC)
            self.assertEqual(request('POST','/api/markup',body)[0],409)
            self.assertEqual(request('GET','/image-tools.js')[0],200)
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
