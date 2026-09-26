const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../assets/workspace.js'), 'utf8');
const code = html.match(/function entryFile[\s\S]*?let dragDepth=0;/)?.[0];
assert.ok(code, 'actual drop traversal is present');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(code + '\nthis.walkDropped = walkDropped;', ctx);
const file = name => ({name, isFile: true, file(callback) {callback({name})}});
const directory = (name, children) => ({name, isDirectory: true, createReader() {
  let done = false;
  return {readEntries(callback) {if(done) callback([]); else {done = true; callback(children)}}};
}});
const root = directory('selected-parent', [directory('Group A', [file('one.svg')]), directory('Group B', [file('two.svg')])]);
ctx.walkDropped(root, '', true).then(items => {
  assert.deepEqual(Array.from(items, x => x.path), ['Group A/one.svg', 'Group B/two.svg']);
  console.log('drop folder traversal: 2 groups, no outer selection directory');
}).catch(error => {console.error(error); process.exitCode = 1});
