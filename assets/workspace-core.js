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
  return {descendants, rangeSelection, isImage, matches, isSettingsShortcut, sameImportOptions};
});
