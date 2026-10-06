/* Pure workspace behavior, shared by the UI and Node regression suite. */
(function(root, factory) {
  const core = factory();
  if (typeof module === 'object' && module.exports) module.exports = core;
  else root.FigNestCore = core;
})(typeof globalThis === 'object' ? globalThis : this, function() {
  function descendants(folders, id) {
    const found = new Set([id]);
    for (;;) {
      const size = found.size;
      for (const f of folders) if (found.has(f.parent_id)) found.add(f.id);
      if (found.size === size) return found;
    }
  }
  function rangeSelection(previous, order, anchor, target, additive) {
    const result = additive ? new Set(previous) : new Set();
    const a = order.indexOf(anchor), b = order.indexOf(target);
    if (a < 0 || b < 0) {result.add(target); return result;}
    for (const id of order.slice(Math.min(a,b), Math.max(a,b)+1)) result.add(id);
    return result;
  }
  const isImage = row => row.asset_kind ? row.asset_kind === 'image' : /\.(svg|png|jpe?g|webp|gif|bmp)$/i.test(row.filename);
  function activeFilters(view){
    const result=[];
    for(const key of ['search','kind','group'])if(String(view[key]||'').trim())result.push({kind:key,key,value:String(view[key]).trim()});
    for(const [key,value] of Object.entries(view.filters||{}))if(value)result.push({kind:'field',key,value});
    return result;
  }
  function removeFilter(view,token){
    const result={...view,filters:{...view.filters},page:1};
    if(token.kind==='field')delete result.filters[token.key];else result[token.key]='';
    return result;
  }
  const widenSearch=view=>({...view,mode:'all',library:'',folder:'',group:'',filters:{},onlySelected:false,page:1});
  function selectionSummary(ids,matching){
    const picked=new Set(ids),visibleIDs=new Set(matching),visible=[...picked].filter(id=>visibleIDs.has(id)).length;
    return {total:picked.size,visible,outside:picked.size-visible};
  }
  function gridNeighbor(ids,current,key,columns=1){
    const index=Math.max(0,ids.indexOf(current));
    if(key==='Home')return ids[0];if(key==='End')return ids[ids.length-1];
    const next=index+({ArrowLeft:-1,ArrowRight:1,ArrowUp:-columns,ArrowDown:columns}[key]||0);
    return ids[next]||ids[index];
  }
  const folderMembershipState=(count,total)=>({checked:total>0&&count===total,indeterminate:count>0&&count<total});
  function comparisonColumns(count,width,height,ratios=[]){
    if(count<=1||width<700)return 1;let best=2,bestScore=-1;
    for(const cols of [...new Set([2,count])]){
      const rows=Math.ceil(count/cols),cellWidth=(width-12*(cols-1))/cols;
      if(cellWidth<190)continue;
      const availableWidth=Math.max(1,cellWidth-56),availableHeight=Math.max(1,(height-12*(rows-1))/rows-146);
      const score=Math.min(...Array.from({length:count},(_,index)=>{const ratio=ratios[index]||5/3,h=Math.min(availableHeight,availableWidth/ratio);return h*h*ratio;}));
      if(score>bestScore){best=cols;bestScore=score;}
    }
    return best;
  }
  function comparisonRows(rows,clicked){
    const unique=[...new Map([...rows,...(clicked?[clicked]:[])].filter(Boolean).map(row=>[row.id,row])).values()];
    return unique.length>=2&&unique.length<=4&&unique.every(isImage)?unique:[];
  }
  function matches(row, query) {
    const haystack = [row.title,row.filename,row.relative_path,row.note,row.caption,row.group,...row.tags||[],...Object.values(row.fields||{})].join(' ').toLocaleLowerCase();
    return (query.search||'').toLocaleLowerCase().split(/\s+/).filter(Boolean).every(w=>haystack.includes(w))
      && (!query.library_id || row.library_id===query.library_id)
      && (!query.group || row.group===query.group)
      && (!query.kind || row.asset_kind===query.kind)
      && (query.favorite===undefined || Boolean(row.favorite)===query.favorite)
      && (query.tags||[]).every(t=>(row.tags||[]).includes(t))
      && Object.entries(query.fields||{}).every(([k,v])=>!v || row.fields?.[k]===v);
  }
  const isSettingsShortcut = event => Boolean((event.metaKey || event.ctrlKey) && event.key === ',' && !event.altKey && !event.shiftKey);
  const sameImportOptions = (a={},b={}) => (a.folder_id||null)===(b.folder_id||null)
    && JSON.stringify(a.tags||[])===JSON.stringify(b.tags||[])
    && Boolean(a.hierarchy)===Boolean(b.hierarchy) && (a.auto_export!==false)===(b.auto_export!==false);
  return {descendants, rangeSelection, isImage, activeFilters, removeFilter, widenSearch, selectionSummary, gridNeighbor, folderMembershipState, comparisonColumns, comparisonRows, matches, isSettingsShortcut, sameImportOptions};
});
