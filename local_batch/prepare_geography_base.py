"""Simplify downloaded Natural Earth GeoJSON for the offline map (no runtime network).

Inputs: maph-countries.geojson, ne_10m_lakes.geojson,
ne_10m_rivers_lake_centerlines.geojson from Natural Earth's official repository.
Output includes sources and processing tolerances. User place data stays in results/.
"""
import argparse
import json
import math
from pathlib import Path


def simplify(points, tolerance=.008):
    if len(points) <= 2: return points
    a,b=points[0],points[-1];dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
    def distance(p):
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
        return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
    at=max(range(1,len(points)-1),key=lambda i:distance(points[i]))
    return simplify(points[:at+1],tolerance)[:-1]+simplify(points[at:],tolerance) if distance(points[at])>tolerance else [a,b]


def lines(coords):
    if not coords:return []
    if isinstance(coords[0][0],(int,float)): return [coords]
    return [line for child in coords for line in lines(child)]


def reduce(coords, polygon=False):
    if not coords:return []
    if isinstance(coords[0][0],(int,float)):
        result=simplify(coords)
        if polygon and len(result)<4:result=coords[:]
        return [[round(x,5),round(y,5)] for x,y,*_ in result]
    return [reduce(c,polygon) for c in coords]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-dir',type=Path,default=Path('/tmp'))
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('geography-base.json'));args=parser.parse_args()
    layers=[]
    for name,kind in [('maph-countries','land'),('ne_10m_lakes','lake'),('ne_10m_rivers_lake_centerlines','river')]:
        for feature in json.loads((args.source_dir/(name+'.geojson')).read_text())['features']:
            p=feature['properties'];g=feature['geometry']
            if kind=='land':
                if p.get('ADM0_A3') not in ('CAN','USA','GRL','MEX'):continue
            elif not any(-86<=x<=-75 and 47<=y<=54 for line in lines(g['coordinates']) for x,y,*_ in line):continue
            layers.append({'type':'Feature','properties':{'kind':kind,'name':p.get('NAME') or p.get('name') or ''},
                           'geometry':{'type':g['type'],'coordinates':reduce(g['coordinates'],'Polygon' in g['type'])}})
    value={'type':'FeatureCollection','features':layers,'attribution':'Made with Natural Earth · public domain',
           'source':'https://github.com/nvkelso/natural-earth-vector/tree/master/geojson',
           'license':'https://www.naturalearthdata.com/about/terms-of-use/',
           'notes':'Modern reference geography, not historical boundaries. 1:10m source; simplified at 0.008 degrees. Regional hydrography only, not exhaustive.'}
    args.output.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')))
    print(len(layers),'features;',args.output.stat().st_size,'bytes')

if __name__=='__main__':main()
