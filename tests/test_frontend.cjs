const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const source = fs.readFileSync(path.join(__dirname,'..','app.js'),'utf8');
const ctx = {
  document: { addEventListener() {}, querySelector() { return { value: '2026-11-23' }; } },
  localStorage: { getItem() {return null}, setItem() {} },
  window: {},
  URL,
  Date,
  console,
  setTimeout,
  clearTimeout
};
vm.createContext(ctx);
vm.runInContext(source + `
 state.selected.add('demo-1');
 var generated = emailHtml();
 var escaped = escapeHtml('<script>"&');
 var urlSafe = safeUrl('javascript:alert(1)');
`, ctx);
assert(ctx.generated.includes('해당 공고문은 한국에너지기술평가원과 무관하므로'), 'required footer');
assert(ctx.generated.includes('기후테크 창업지원 소식'), 'subject header');
assert(ctx.generated.includes('가상 지원기관 A'), 'data source mapped');
assert(ctx.escaped === '&lt;script&gt;&quot;&amp;', 'HTML escaping');
assert(ctx.urlSafe === '', 'unsafe URL rejected');
console.log('Frontend newsletter and HTML safety checks passed.');
