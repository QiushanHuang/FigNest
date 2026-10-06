/* Original-pixel image markup. DOM text/attributes only; originals stay untouched. */
(function(root){
  'use strict';
  const G=root.FigNestImageGeometry,NS='http://www.w3.org/2000/svg';
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const svg=(tag,attrs={},text)=>{const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;};
  const format=n=>Number(n.toFixed(1)).toString();
  const tools=[['pan','平移'],['select','选择'],['zoom','框选放大'],['ruler','像素测距'],['arrow','箭头'],['line','直线'],['rect','矩形'],['ellipse','椭圆'],['pen','画笔'],['text','文字'],['hguide','水平参考线'],['vguide','垂直参考线']];
  function shapeNode(s,w,h,scale=1,selected=false){
    const group=svg('g',{'data-shape':s.id,stroke:s.color,'stroke-width':s.width/scale,fill:'none','stroke-linecap':'round','stroke-linejoin':'round'});
    const a=s.points[0],b=s.points[1]||a,box=G.box(a,b);
    const line=(p,q,attrs={})=>group.append(svg('line',{x1:p.x,y1:p.y,x2:q.x,y2:q.y,...attrs}));
    const label=(p,text)=>group.append(svg('text',{x:p.x,y:p.y,fill:s.color,stroke:'white','stroke-width':3/scale,'paint-order':'stroke','font-size':12/scale,'font-family':'system-ui, sans-serif'},text));
    if(s.type==='rect')group.append(svg('rect',{...box,fill:'transparent','pointer-events':'all'}));
    else if(s.type==='ellipse')group.append(svg('ellipse',{cx:box.x+box.width/2,cy:box.y+box.height/2,rx:box.width/2,ry:box.height/2,fill:'transparent','pointer-events':'all'}));
    else if(s.type==='pen')group.append(svg('polyline',{points:s.points.map(p=>p.x+','+p.y).join(' ')}));
    else if(s.type==='text')group.append(svg('text',{x:a.x,y:a.y,'font-size':s.fontSize,'font-family':'system-ui, sans-serif',fill:s.color,stroke:'none'},s.text));
    else if(s.type==='hguide'||s.type==='vguide'){
      line(s.type==='hguide'?{x:0,y:a.y}:{x:a.x,y:0},s.type==='hguide'?{x:w,y:a.y}:{x:a.x,y:h},{'stroke-dasharray':6/scale+' '+4/scale});
      label({x:s.type==='hguide'?4/scale:a.x+4/scale,y:s.type==='hguide'?a.y-5/scale:15/scale},(s.type==='hguide'?'y = ':'x = ')+format(s.type==='hguide'?a.y:a.x)+' px');
    }else{
      line(a,b);
      if(s.type==='arrow'){
        const angle=Math.atan2(b.y-a.y,b.x-a.x),size=12/scale;
        group.append(svg('polyline',{points:[{x:b.x-size*Math.cos(angle-.5),y:b.y-size*Math.sin(angle-.5)},b,{x:b.x-size*Math.cos(angle+.5),y:b.y-size*Math.sin(angle+.5)}].map(p=>p.x+','+p.y).join(' ')}));
      }
      if(s.type==='ruler'){
        for(const p of [a,b])group.append(svg('circle',{cx:p.x,cy:p.y,r:3/scale,fill:s.color}));
        const m=G.measure(a,b);label({x:(a.x+b.x)/2+5/scale,y:(a.y+b.y)/2-8/scale},format(m.distance)+' px · Δx '+format(m.dx)+' · Δy '+format(m.dy));
      }
    }
    if(selected)for(const p of [a,b])group.append(svg('rect',{x:p.x-4/scale,y:p.y-4/scale,width:8/scale,height:8/scale,fill:'white',stroke:'#2676d8','stroke-width':1/scale}));
    return group;
  }
  function mount(host,row,options={}){
    const image=host.querySelector('img');if(!image)return null;
    const readonly=Boolean(options.readonly),externalNotify=options.notify||(()=>{});
    let width=0,height=0,view={x:0,y:0,scale:1},mode='fit',tool='pan',shapes=[],history=new G.History([]),saved='[]',revision=0,blob=row.blob;
    let ready=false,disposed=false,selected='',gesture=null,draft=null,show=true,showAxes=true,space=false,saving=null;
    let expanded=options.expanded===true,defaultExpanded=expanded,pendingText=false,errorMessage='',infoMessage='';
    host.classList.add('image-editor');
    host.replaceChildren();
    const controls=node('div',undefined,'image-view-controls');controls.setAttribute('role','toolbar');controls.setAttribute('aria-label','观察工具');
    const toolbar=node('div',undefined,'image-toolbox');toolbar.setAttribute('role','toolbar');toolbar.setAttribute('aria-label','标注工具栏');toolbar.id='image-markup-'+crypto.randomUUID();
    const viewport=node('div',undefined,'image-viewport');viewport.tabIndex=0;viewport.setAttribute('aria-label','图片画布 · 拖动操作，滚轮缩放');
    const stage=node('div',undefined,'image-stage'),overlay=svg('svg',{'aria-label':'图片标注'}),axes=svg('svg',{'class':'image-axes','aria-hidden':'true'});
    image.loading='eager';image.draggable=false;
    stage.append(image,overlay);viewport.append(stage,axes);
    const status=node('div',undefined,'image-status');status.setAttribute('aria-live','off');const dimensions=node('span',undefined,'image-dimensions'),modeHint=node('span',undefined,'image-mode-hint'),coordinates=node('span',undefined,'image-coordinates'),saveState=node('span',undefined,'image-save-state'),errorLine=node('p',undefined,'image-inline-error');saveState.setAttribute('role','status');saveState.setAttribute('aria-live','polite');coordinates.setAttribute('aria-live','off');errorLine.setAttribute('role','alert');errorLine.hidden=true;status.append(dimensions,modeHint,coordinates,saveState);
    host.append(controls,toolbar,viewport,errorLine,status);
    const buttons=new Map();
    const action=(label,fn,cls,target=toolbar)=>{const b=node('button',label,cls);b.type='button';b.onclick=async()=>{activate();try{await fn();}catch(e){notify(e.message,true);}};target.append(b);return b;};
    function notify(message,error=false){if(error)errorMessage=message;else infoMessage=message;renderStatus();externalNotify(message,error);}
    function activate(){options.activate?.(controller);}
    function chooseTool(next){infoMessage='';tool=next;if(!readonly&&!G.observationTools.includes(next))setExpanded(true);selected='';draft=null;viewport.dataset.tool=next;for(const [name,b] of buttons)b.setAttribute('aria-pressed',String(name===next));textInput.hidden=next!=='text';render();}
    for(const [name,label] of tools){
      if(readonly&&!['pan','zoom'].includes(name))continue;
      const b=action(label,()=>chooseTool(name),undefined,G.observationTools.includes(name)?controls:toolbar);b.dataset.tool=name;buttons.set(name,b);
    }
    const color=node('input');color.type='color';color.value='#e84c3d';color.setAttribute('aria-label','标注颜色');
    const thickness=node('select');thickness.setAttribute('aria-label','线宽');
    for(const n of [1,2,3,5,8]){const op=node('option',n+' px');op.value=n;thickness.append(op);}thickness.value=2;
    const textInput=node('input');textInput.type='text';textInput.placeholder='输入文字，再点击图片';textInput.maxLength=500;textInput.setAttribute('aria-label','标注文字');textInput.hidden=true;
    if(!readonly)toolbar.append(color,thickness,textInput);textInput.oninput=()=>{activate();pendingText=Boolean(textInput.value.trim());render();};
    function viewAction(label,fn){const b=node('button',label);b.type='button';b.onclick=()=>{activate();fn();};controls.append(b);return b;}
    viewAction('−',()=>zoom(view.scale/1.25));const zoomLabel=node('output','100%');zoomLabel.setAttribute('aria-label','缩放比例');controls.append(zoomLabel);viewAction('＋',()=>zoom(view.scale*1.25));
    viewAction('适应窗口',fit);viewAction('100%',()=>{mode='manual';view=G.zoomAt(view,{x:viewport.clientWidth/2,y:viewport.clientHeight/2},1);render();});
    const axesButton=viewAction('像素标尺',()=>{showAxes=!showAxes;axesButton.setAttribute('aria-pressed',String(showAxes));render();});axesButton.setAttribute('aria-pressed','true');
    const hideButton=viewAction('显示标注',()=>{show=!show;hideButton.setAttribute('aria-pressed',String(show));render();});hideButton.setAttribute('aria-pressed','true');
    let undo,redo,remove,saveButton,clearButton,expandButton,defaultCheck;
    if(!readonly){
      expandButton=viewAction('标注工具',()=>setExpanded(!expanded));expandButton.setAttribute('aria-controls',toolbar.id);expandButton.setAttribute('aria-label','标注工具');
      clearButton=action('清除标注',()=>{cancelGesture();const count=shapes.length;shapes=history.clear();selected='';render();notify('已清除 '+count+' 个标注，可撤销；点击保存标注后生效。');},undefined,controls);
      undo=action('↶',()=>{shapes=history.undo();selected='';render();},undefined,controls);undo.setAttribute('aria-label','撤销');
      redo=action('↷',()=>{shapes=history.redo();selected='';render();},undefined,controls);redo.setAttribute('aria-label','重做');
      const defaultLabel=node('label',undefined,'image-default-toggle');defaultCheck=node('input');defaultCheck.type='checkbox';defaultCheck.checked=defaultExpanded;defaultLabel.append(defaultCheck,node('span','默认展开标注'));toolbar.append(defaultLabel);
      defaultCheck.onchange=async()=>{activate();const value=defaultCheck.checked;defaultCheck.disabled=true;try{await options.saveExpandedDefault(value);defaultExpanded=value;setExpanded(value);}catch(error){defaultCheck.checked=defaultExpanded;notify(error.message,true);}finally{defaultCheck.disabled=false;}};
      remove=action('删除所选',()=>commit(shapes.filter(s=>s.id!==selected)));
      saveButton=action('保存标注',save,'primary',controls);
      action('导出标注 PNG',exportPNG);
      action('导出标注 JSON',()=>download(new Blob([JSON.stringify(documentValue(),null,2)],{type:'application/json'}),'标注.json'));
    }
    function setExpanded(value){
      expanded=Boolean(value)&&!readonly;toolbar.hidden=!expanded;
      if(expandButton){expandButton.textContent=expanded?'收起标注工具':'展开标注工具';expandButton.setAttribute('aria-expanded',String(expanded));}
      if(!expanded&&!G.observationTools.includes(tool)){cancelGesture();chooseTool('pan');}
    }
    function emitView(){const snapshot=G.viewSnapshot(view,width,height,viewport.clientWidth,viewport.clientHeight);if(snapshot)options.viewChanged?.(controller,snapshot);}
    function documentValue(){return {version:1,width,height,shapes:JSON.parse(JSON.stringify(shapes))};}
    function dirty(){return !readonly&&(pendingText||JSON.stringify(shapes)!==saved);}
    function commit(next){errorMessage='';infoMessage='';if(next.length>1000){notify('最多可保存 1000 个标注。',true);return;}shapes=history.push(next);draft=null;render();}
    function fit(emit=true){if(!width)return;mode='fit';view=G.fitBox({x:0,y:0,width,height},viewport.clientWidth,viewport.clientHeight,28)||view;render();if(emit)emitView();}
    function zoom(scale,point={x:viewport.clientWidth/2,y:viewport.clientHeight/2}){mode='manual';view=G.zoomAt(view,point,scale);render();emitView();}
    function renderStatus(){
      const state=G.editStatus({ready,readonly,revision,dirty:dirty(),pendingText,saving:Boolean(saving),error:Boolean(errorMessage)});saveState.dataset.state=state;const label=({loading:'正在载入',empty:'暂无标注',saved:'已保存',dirty:'未保存',pending:'文字待放置',saving:'正在保存',error:ready?'保存未完成':'载入未完成',snapshot:'只读快照'})[state];if(saveState.textContent!==label)saveState.textContent=label;dimensions.textContent=width?width+' × '+height+' px · '+shapes.length+' 标注':'';modeHint.textContent=infoMessage||({pan:'平移 · 拖动图片',zoom:'框选放大 · 拖出观察区域',ruler:'像素测距 · 拖出两点',select:'选择 · 拖动标注，Delete 删除',text:'文字 · 输入后点击图片放置',pen:'画笔 · 在图片内拖动',hguide:'水平参考线 · 点击图片',vguide:'垂直参考线 · 点击图片',arrow:'箭头 · 在图片内拖动',line:'直线 · 在图片内拖动',rect:'矩形 · 在图片内拖动',ellipse:'椭圆 · 在图片内拖动'})[tool];errorLine.hidden=!errorMessage;if(errorLine.textContent!==errorMessage)errorLine.textContent=errorMessage;
    }
    function render(){
      if(disposed)return;renderStatus();if(!width){options.stateChanged?.();return;}
      stage.style.width=width+'px';stage.style.height=height+'px';stage.style.transform='translate('+view.x+'px,'+view.y+'px) scale('+view.scale+')';
      image.style.width=width+'px';image.style.height=height+'px';overlay.setAttribute('viewBox','0 0 '+width+' '+height);overlay.setAttribute('width',width);overlay.setAttribute('height',height);
      overlay.replaceChildren();
      if(show)for(const s of shapes)overlay.append(shapeNode(s,width,height,view.scale,s.id===selected));
      if(draft){
        if(tool==='zoom'){const b=G.box(draft.points[0],draft.points[1]);overlay.append(svg('rect',{...b,fill:'#2680eb22',stroke:'#2676d8','stroke-width':1.5/view.scale,'stroke-dasharray':5/view.scale+' '+3/view.scale}));}
        else overlay.append(shapeNode(draft,width,height,view.scale));
      }
      axes.replaceChildren();axes.style.display=showAxes?'':'none';
      axes.setAttribute('width',viewport.clientWidth);axes.setAttribute('height',viewport.clientHeight);
      if(showAxes){
        axes.append(svg('rect',{x:0,y:0,width:viewport.clientWidth,height:22,fill:'#f4f6faee'}),svg('rect',{x:0,y:0,width:28,height:viewport.clientHeight,fill:'#f4f6faee'}));
        for(const t of G.ticks(width,viewport.clientWidth,view.scale,view.x))if(t.screen>29){axes.append(svg('line',{x1:t.screen,y1:16,x2:t.screen,y2:22,stroke:'#627188'}),svg('text',{x:t.screen+3,y:12,fill:'#4c596e','font-size':10},format(t.value)));}
        for(const t of G.ticks(height,viewport.clientHeight,view.scale,view.y))if(t.screen>24){axes.append(svg('line',{x1:22,y1:t.screen,x2:28,y2:t.screen,stroke:'#627188'}),svg('text',{x:3,y:t.screen-3,fill:'#4c596e','font-size':10},format(t.value)));}
        axes.append(svg('text',{x:3,y:13,fill:'#4c596e','font-size':10},'px'));
      }
      zoomLabel.value=format(view.scale*100)+'%';zoomLabel.textContent=zoomLabel.value;
      if(!readonly){
        undo.disabled=!ready||!history.canUndo;redo.disabled=!ready||!history.canRedo;remove.disabled=!ready||!selected;clearButton.disabled=!ready||!shapes.length;
        saveButton.disabled=!ready||!dirty()||Boolean(saving);saveButton.textContent=saving?'正在保存…':'保存标注';
        saveButton.hidden=!dirty()&&!saving;
        for(const [name,b] of buttons)b.disabled=!ready&&!['pan','zoom'].includes(name);
      }
      options.stateChanged?.();
      renderStatus();
    }
    function local(event){const rect=viewport.getBoundingClientRect();return {x:event.clientX-rect.left,y:event.clientY-rect.top};}
    function point(event){return G.clampPoint(G.toImage(local(event),view),width,height);}
    function newShape(type,points){return {id:crypto.randomUUID(),type,color:color.value,width:Number(thickness.value),points};}
    viewport.addEventListener('pointerdown',event=>{
      if(!width||!event.isPrimary||(!ready&&!['pan','zoom'].includes(tool)))return;
      if(event.button!==0&&event.button!==1)return;
      activate();const raw=G.toImage(local(event),view);if(!['pan','zoom','select'].includes(tool)&&!space&&event.button!==1&&!G.pointInImage(raw,width,height)){notify('请在图片范围内绘制标注。');return;}viewport.focus({preventScroll:true});event.preventDefault();viewport.setPointerCapture(event.pointerId);
      const start=point(event),screen=local(event);
      if(tool==='pan'||space||event.button===1){gesture={kind:'pan',screen,view:{...view}};return;}
      if(tool==='select'){
        selected=show?event.target.closest('[data-shape]')?.getAttribute('data-shape')||'':'';
        const original=shapes.find(s=>s.id===selected);gesture=original?{kind:'move',start,original,moved:false}:null;render();return;
      }
      if(tool==='text'){
        const text=textInput.value.trim();if(!text){notify('先在工具栏输入标注文字。');return;}
        pendingText=false;commit([...shapes,{...newShape('text',[start]),text,fontSize:Math.min(10000,20/view.scale)}]);return;
      }
      gesture={kind:'draw',start,screen};
      draft=newShape(tool,tool==='hguide'||tool==='vguide'?[start]:[start,start]);render();
    });
    viewport.addEventListener('pointermove',event=>{
      if(!width)return;
      const p=point(event),screen=local(event),raw=G.toImage(screen,view);coordinates.textContent=G.pointInImage(raw,width,height)?'x '+format(p.x)+' · y '+format(p.y)+' px':'图片外';
      if(!gesture)return;
      if(gesture.kind==='pan'){
        mode='manual';view={...gesture.view,x:gesture.view.x+screen.x-gesture.screen.x,y:gesture.view.y+screen.y-gesture.screen.y};
      }else if(gesture.kind==='move'){
        const moved=G.moveShape(gesture.original,p.x-gesture.start.x,p.y-gesture.start.y,width,height);shapes=shapes.map(s=>s.id===selected?moved:s);gesture.moved=true;
      }else if(draft){
        if(tool==='pen'){const last=draft.points[draft.points.length-1];if(draft.points.length<5000&&Math.hypot(last.x-p.x,last.y-p.y)*view.scale>2)draft.points.push(p);}
        else if(tool==='hguide'||tool==='vguide')draft.points=[p];
        else draft.points[1]=p;
      }
      render();if(gesture?.kind==='pan')emitView();
      if(draft?.type==='ruler'){const m=G.measure(...draft.points);coordinates.textContent=format(m.distance)+' px · Δx '+format(m.dx)+' · Δy '+format(m.dy);}
    });
    viewport.addEventListener('pointerup',event=>{
      if(!gesture)return;
      const current=gesture;gesture=null;
      if(current.kind==='move'&&current.moved)commit(shapes);
      else if(current.kind==='draw'&&draft){
        const completed=draft;draft=null;
        if(tool==='zoom'){const b=G.box(...completed.points);if(b.width*view.scale>=5&&b.height*view.scale>=5){view=G.fitBox(b,viewport.clientWidth,viewport.clientHeight,28)||view;mode='manual';emitView();}}
        else if(['hguide','vguide'].includes(tool)||G.measure(completed.points[0],completed.points[completed.points.length-1]).distance*view.scale>2||tool==='pen'&&completed.points.length>2)commit([...shapes,completed]);
      }
      if(viewport.hasPointerCapture(event.pointerId))viewport.releasePointerCapture(event.pointerId);render();
    });
    function cancelGesture(){if(gesture?.kind==='move')shapes=history.entries[history.index].map(s=>JSON.parse(JSON.stringify(s)));gesture=null;draft=null;render();}
    viewport.addEventListener('pointercancel',cancelGesture);
    viewport.addEventListener('wheel',event=>{if(!width)return;event.preventDefault();if(!gesture)zoom(view.scale*Math.exp(-G.clamp(event.deltaY,-150,150)*.003),local(event));},{passive:false});
    async function save(){
      if(pendingText){errorMessage='文字尚未放置：请点击图片放置文字，或按 Escape 取消这段文字。';activate();chooseTool('text');renderStatus();throw Error(errorMessage);}
      if(saving)return saving;if(!ready||!dirty())return;
      errorMessage='';infoMessage='';const doc=documentValue(),snapshot=JSON.stringify(doc.shapes);
      saving=(async()=>{try{const result=await options.save({id:row.id,blob,revision,document:doc});revision=result.revision;saved=snapshot;notify('标注已保存');}catch(error){errorMessage=error.message;renderStatus();throw error;}finally{saving=null;render();}})();
      render();return saving;
    }
    function download(content,suffix){const url=URL.createObjectURL(content),a=node('a');a.href=url;a.download=(row.title||'图片').replace(/[\\/:]/g,'_')+'-'+suffix;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
    async function exportPNG(){
      if(!width)return;
      if(width*height>64000000)throw Error('图片超过 6400 万像素；请导出标注 JSON 保存编辑。');
      const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d');if(!ctx)throw Error('无法创建导出画布');
      ctx.drawImage(image,0,0,width,height);
      const drawing=svg('svg',{xmlns:NS,width,height,viewBox:'0 0 '+width+' '+height});for(const s of shapes)drawing.append(shapeNode(s,width,height));
      // The viewer permits data images. Keep its restrictive image policy intact.
      const layer=new Image();layer.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(new XMLSerializer().serializeToString(drawing));
      await layer.decode();ctx.drawImage(layer,0,0);const result=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!result)throw Error('PNG 导出失败');download(result,'标注.png');
    }
    const observer=new ResizeObserver(()=>{if(width){if(mode==='fit')fit();else render();}});observer.observe(viewport);
    const controller={
      dirty,save,fit,element:host,
      setActive:value=>{host.classList.toggle('is-active',value);const indicator=host.closest('.viewer-panel')?.querySelector('.panel-current');if(indicator)indicator.hidden=!value;},
      getState:()=>({tool,expanded,ready,scale:view.scale,canUndo:history.canUndo,canRedo:history.canRedo,hasAnnotations:shapes.length>0,pendingText,dirty:dirty(),saving:Boolean(saving),show,showAxes}),
      viewSnapshot:()=>G.viewSnapshot(view,width,height,viewport.clientWidth,viewport.clientHeight),
      setViewSnapshot:state=>{const next=G.fromViewSnapshot(state,width,height,viewport.clientWidth,viewport.clientHeight);if(next){view=next;mode='manual';render();}},
      command:name=>{if(G.observationTools.includes(name))chooseTool(name);else if(name==='in')zoom(view.scale*1.25);else if(name==='out')zoom(view.scale/1.25);else if(name==='fit')fit();else if(name==='original')controller.original();else if(name==='axes')axesButton.click();else if(name==='show')hideButton.click();else if(name==='expand')setExpanded(!expanded);else if(name==='clear'&&!readonly)clearButton.click();else if(name==='undo'&&!readonly)undo.click();else if(name==='redo'&&!readonly)redo.click();else if(name==='save')return save();render();},
      setDefaultExpanded:value=>{defaultExpanded=Boolean(value);if(defaultCheck)defaultCheck.checked=defaultExpanded;},original:(emit=true)=>{mode='manual';view=G.zoomAt(view,{x:viewport.clientWidth/2,y:viewport.clientHeight/2},1);render();if(emit)emitView();},
      dispose:()=>{disposed=true;observer.disconnect();},
      releaseKeys:()=>{space=false;delete viewport.dataset.panHeld;},
      key(event){
        if(event.type==='keyup'){if(event.code==='Space'){space=false;delete viewport.dataset.panHeld;}return false;}
        if(G.isSaveShortcut(event)){event.preventDefault();save().catch(error=>notify(error.message,true));return true;}
        if(event.key==='Escape'&&pendingText&&!event.isComposing){event.preventDefault();pendingText=false;textInput.value='';render();return true;}
        if(event.target.closest('input,textarea,select,[contenteditable="true"]'))return false;
        if(event.code==='Space'&&!event.metaKey&&!event.ctrlKey&&!event.altKey){space=true;viewport.dataset.panHeld='true';event.preventDefault();return true;}
        if(event.type==='keyup')return false;
        if(!readonly&&(event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='z'){event.preventDefault();shapes=event.shiftKey?history.redo():history.undo();selected='';render();return true;}
        if(!readonly&&(event.key==='Delete'||event.key==='Backspace')&&selected){event.preventDefault();commit(shapes.filter(s=>s.id!==selected));selected='';return true;}
        const shortcut=G.toolShortcut(event);if(shortcut&&(!readonly||['pan','zoom'].includes(shortcut))){event.preventDefault();chooseTool(shortcut);return true;}
        if(event.key==='Escape'&&gesture){event.preventDefault();cancelGesture();return true;}
        return false;
      }
    };
    chooseTool('pan');
    setExpanded(expanded);
    const decoded=image.complete&&image.naturalWidth?Promise.resolve():new Promise((resolve,reject)=>{image.addEventListener('load',resolve,{once:true});image.addEventListener('error',()=>reject(Error('图片无法解码')),{once:true});});
    const loaded=readonly?Promise.resolve({document:row.markup||null,revision:0,blob}):options.load();
    Promise.all([decoded,loaded]).then(([,result])=>{
      if(disposed)return;width=image.naturalWidth;height=image.naturalHeight;
      if(!width||!height||width>100000||height>100000)throw Error('不支持此图片尺寸');
      blob=result.blob;revision=result.revision;
      if(result.document){if(result.document.width!==width||result.document.height!==height)throw Error('原图尺寸与标注不同，已暂停编辑。');shapes=result.document.shapes;}
      saved=JSON.stringify(shapes);history=new G.History(shapes);ready=true;fit();
    }).catch(error=>{if(disposed)return;width=image.naturalWidth;height=image.naturalHeight;if(width)fit();errorMessage=error.message+'；请关闭后重试。';renderStatus();notify(error.message,true);});
    return controller;
  }
  root.FigNestImageTools={mount};
})(globalThis);
