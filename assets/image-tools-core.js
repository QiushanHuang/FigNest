/* Image-space geometry shared by the browser and regression tests. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FigNestImageGeometry=api;})(globalThis,function(){
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const toImage=(p,v)=>({x:(p.x-v.x)/v.scale,y:(p.y-v.y)/v.scale});
  const clampPoint=(p,w,h)=>({x:clamp(p.x,0,w),y:clamp(p.y,0,h)});
  const pointInImage=(p,w,h)=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&w>0&&h>0&&p.x>=0&&p.y>=0&&p.x<=w&&p.y<=h;
  function zoomAt(v,p,scale){scale=clamp(scale,.001,32);const q=toImage(p,v);return {x:p.x-q.x*scale,y:p.y-q.y*scale,scale};}
  const box=(a,b)=>({x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(a.x-b.x),height:Math.abs(a.y-b.y)});
  function fitBox(b,w,h,padding=24){if(b.width<=0||b.height<=0||w<=padding*2||h<=padding*2)return null;const scale=clamp(Math.min((w-padding*2)/b.width,(h-padding*2)/b.height),.001,32);return {x:(w-b.width*scale)/2-b.x*scale,y:(h-b.height*scale)/2-b.y*scale,scale};}
  function viewSnapshot(view,width,height,vw,vh){
    const fit=fitBox({x:0,y:0,width,height},vw,vh,28);if(!fit||!width||!height)return null;
    return {u:(vw/2-view.x)/(width*view.scale),v:(vh/2-view.y)/(height*view.scale),zoom:view.scale/fit.scale};
  }
  function fromViewSnapshot(state,width,height,vw,vh){
    const fit=fitBox({x:0,y:0,width,height},vw,vh,28);if(!fit||!state||![state.u,state.v,state.zoom].every(Number.isFinite)||state.zoom<=0)return null;
    const scale=clamp(fit.scale*state.zoom,.001,32);return {x:vw/2-state.u*width*scale,y:vh/2-state.v*height*scale,scale};
  }
  function measure(a,b){const dx=b.x-a.x,dy=b.y-a.y;return {dx,dy,distance:Math.hypot(dx,dy)};}
  function ticks(dimension,viewport,scale,origin){const target=80/scale,power=10**Math.floor(Math.log10(target));const step=[1,2,5,10].find(n=>n*power>=target)*power;const first=Math.max(0,Math.ceil((-origin/scale)/step)*step),last=Math.min(dimension,(viewport-origin)/scale),result=[];for(let value=first;value<=last&&result.length<100;value+=step)result.push({value,screen:origin+value*scale});return result;}
  function moveShape(shape,dx,dy,w,h){const xs=shape.points.map(p=>p.x),ys=shape.points.map(p=>p.y);dx=clamp(dx,-Math.min(...xs),w-Math.max(...xs));dy=clamp(dy,-Math.min(...ys),h-Math.max(...ys));return {...shape,points:shape.points.map(p=>({x:p.x+dx,y:p.y+dy}))};}
  const clone=value=>JSON.parse(JSON.stringify(value));
  const observationTools=['pan','zoom','ruler'];
  function toolShortcut(event){
    if(event.metaKey||event.ctrlKey||event.altKey||event.editing||event.isComposing||event.repeat)return null;
    return ({v:'pan',z:'zoom',r:'ruler',a:'arrow',l:'line',m:'rect',o:'ellipse',b:'pen',t:'text',h:'hguide',g:'vguide'})[(event.key||'').toLowerCase()]||null;
  }
  const isSaveShortcut=event=>Boolean((event.metaKey||event.ctrlKey)&&!event.altKey&&(event.key||'').toLowerCase()==='s');
  function editStatus(state){
    if(state.error)return 'error';if(state.ready===false)return 'loading';if(state.readonly)return 'snapshot';
    if(state.saving)return 'saving';if(state.pendingText)return 'pending';if(state.dirty)return 'dirty';
    return state.revision>0?'saved':'empty';
  }
  class History{
    constructor(initial){this.entries=[clone(initial)];this.index=0;}
    get canUndo(){return this.index>0;}
    get canRedo(){return this.index<this.entries.length-1;}
    push(value){this.entries.splice(this.index+1);this.entries.push(clone(value));if(this.entries.length>100)this.entries.shift();this.index=this.entries.length-1;return clone(value);}
    undo(){if(this.canUndo)this.index--;return clone(this.entries[this.index]);}
    redo(){if(this.canRedo)this.index++;return clone(this.entries[this.index]);}
    clear(){return this.entries[this.index].length?this.push([]):[];}
  }
  return {clamp,toImage,clampPoint,pointInImage,zoomAt,box,fitBox,viewSnapshot,fromViewSnapshot,measure,ticks,moveShape,History,observationTools,toolShortcut,isSaveShortcut,editStatus};
});
