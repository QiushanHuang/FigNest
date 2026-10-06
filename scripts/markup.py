"""Bounded, non-executable original-pixel markup documents."""
import math
import re

class MarkupConflict(ValueError):
    pass

def validate_document(doc):
    if not isinstance(doc,dict) or set(doc)!={'version','width','height','shapes'} or doc['version']!=1:
        raise ValueError('invalid image markup document')
    def number(value,minimum,maximum):
        if type(value) not in (int,float) or not math.isfinite(value) or not minimum<=value<=maximum:
            raise ValueError('invalid markup pixel coordinate or size')
    number(doc['width'],1,100000);number(doc['height'],1,100000)
    shapes=doc['shapes']
    if not isinstance(shapes,list) or len(shapes)>1000:
        raise ValueError('at most 1000 markup items are supported')
    seen=set();point_count=0
    for shape in shapes:
        if not isinstance(shape,dict) or set(shape)-{'id','type','color','width','points','text','fontSize'}:
            raise ValueError('invalid markup item')
        ident=shape.get('id')
        if not isinstance(ident,str) or not 1<=len(ident)<=80 or ident in seen:
            raise ValueError('markup ids must be unique')
        seen.add(ident)
        kind=shape.get('type')
        if kind not in ('line','arrow','rect','ellipse','pen','text','hguide','vguide','ruler'):
            raise ValueError('unknown markup tool')
        if not isinstance(shape.get('color'),str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',shape['color']):
            raise ValueError('invalid markup color')
        number(shape.get('width'),.1,32)
        points=shape.get('points')
        if not isinstance(points,list):raise ValueError('invalid markup points')
        minimum,maximum=(2,5000) if kind=='pen' else (1,1) if kind in ('text','hguide','vguide') else (2,2)
        if not minimum<=len(points)<=maximum:raise ValueError('wrong number of markup points')
        point_count+=len(points)
        if point_count>50000:raise ValueError('too many markup points')
        for point in points:
            if not isinstance(point,dict) or set(point)!={'x','y'}:raise ValueError('invalid markup point')
            number(point['x'],0,doc['width']);number(point['y'],0,doc['height'])
        if kind=='text':
            if not isinstance(shape.get('text'),str) or not 1<=len(shape['text'])<=500:raise ValueError('invalid markup text')
            number(shape.get('fontSize'),1,10000)
        elif 'text' in shape or 'fontSize' in shape:raise ValueError('unexpected text in markup item')
    return doc
