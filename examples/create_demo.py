"""Generate a self-contained synthetic demonstration library (no real user data)."""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from library import Store


def chart(title, variant):
    colors = ('#3977a6', '#cd9866', '#6d9794')
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600">',
             '<rect width="960" height="600" fill="#fff"/>',
             f'<text x="80" y="52" font-family="Arial,sans-serif" font-size="25" fill="#263a50">{title}</text>']
    for i in range(5):
        y = 110 + i*85
        parts.append(f'<path d="M90 {y}H865" stroke="#e7ebef" fill="none"/>')
        parts.append(f'<text x="67" y="{y+5}" font-family="Arial" font-size="14" fill="#718196">{100-i*25}</text>')
    parts.append('<path d="M90 105V465H870" fill="none" stroke="#738295" stroke-width="1.5"/>')
    for i in range(6):
        x = 90+i*155
        parts.append(f'<text x="{x-4}" y="495" font-family="Arial" font-size="14" fill="#718196">{i*20}</text>')
    for series,color in enumerate(colors):
        points=[]
        for i in range(101):
            t=i/100
            if variant%3==0:
                v=(t**(1.6+.35*series))*(.83-.08*series)
            elif variant%3==1:
                v=(1-math.exp(-t*(3+series)))*(.8-.11*series)
            else:
                v=.44+.20*math.sin(t*5.2+series*.4)+t*.13-series*.09
            points.append(f'{90+775*t:.2f},{465-355*v:.2f}')
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3.4"/>')
        parts.append(f'<path d="M{540+series*105} 80h23" stroke="{color}" stroke-width="3"/><text x="{570+series*105}" y="85" font-family="Arial" font-size="13" fill="#54687c">Set {chr(65+series)}</text>')
    parts.append('<text x="390" y="540" font-family="Arial" font-size="16" fill="#53687c">Normalized input</text>')
    parts.append('<text x="80" y="575" font-family="Arial" font-size="12" fill="#8a97a5">Synthetic demonstration · no experimental measurements</text></svg>')
    return ''.join(parts)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--data',required=True)
    args=p.parse_args()
    source=Path(args.output).expanduser().resolve()
    data=Path(args.data).expanduser().resolve()
    if source.exists() or (data/'library.sqlite3').exists():
        raise SystemExit('Use new source and datastore paths for a clean demonstration.')
    source.mkdir(parents=True)
    groups=[('Response','Response comparison'),('Dynamics','Relaxation profile'),('Geometry','Shape response')]
    for g,(folder,title) in enumerate(groups):
        (source/folder).mkdir()
        for j in range(4):
            (source/folder/f'{j+1:02d}.svg').write_text(chart(f'{title} · {j+1:02d}',g))
    cfg={'title':'Materials review','description':'Synthetic demonstration library',
         'roots':[{'id':'demo','label':'Demo figures','path':str(source)}],
         'rules':[{'glob':f'{f}/*','set':{'group':f,'fields':{'collection':'Materials','metric':t,'version':'Review 01'}}} for f,t in groups],
         'overrides':{f'demo:{f}/{j+1:02d}.svg':{'title':f'{t} · {j+1:02d}'} for f,t in groups for j in range(4)}}
    config=source.parent/'demo-config.json'
    config.write_text(json.dumps(cfg))
    store=Store(data)
    lid=store.import_directory(config=config,options={'auto_export':False})['library_id']
    root=store.folder('Presentations')
    child=store.folder('Autumn review',parent_id=root)
    ids=[r['id'] for r in store.state()['images']]
    store.batch(ids[:6],{'favorite':True,'folder_id':child,'present':True,'add_tags':['review']})
    store.annotate(ids[0],{'note':'Compare the response across the three sets before preparing the review slide.'})
    store.folder('Selected comparisons',kind='smart',query={'favorite':True,'tags':['review']})
    store.set_group(lid,'Response',{'favorite':True})
    store.export(library_id=lid)
    print(json.dumps({'source':str(source),'data':str(data),'library_id':lid,'assets':len(ids)}))


if __name__=='__main__': main()
