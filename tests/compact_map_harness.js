// Test harness for tests/test_compact_map.py. Runs the page script from a built map page
// against a minimal fake DOM (no browser) and prints one JSON document.
//   node compact_map_harness.js <page.html> <scenario.json>
// scenario: {view, mode?, writer?, resaver?, expand?: [attrs...], hover?: [attrs...], click?: [attrs...]}
// hover/click entries are attribute dicts of an element the page rendered; each is turned into a
// fake element that answers matches()/closest()/dataset/getAttribute from those attributes, then
// the page's own document-level mouseover, focusin and click listeners are fired on it.
const fs = require('fs');
const vm = require('vm');

const [, , pagePath, scenarioPath] = process.argv;
const page = fs.readFileSync(pagePath, 'utf8');
const scenario = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));
const script = page.match(/<script>([\s\S]*)<\/script>/)[1];

const els = {};
const listeners = {};
const defaults = {view: 'main', mode: 'coverage', status: 'all', pair: 'all', format: 'all'};
class Option { constructor(text, value) { this.text = text; this.value = value === undefined ? text : value; } }
class El {
  constructor(id) {
    this.id = id; this._value = defaults[id]; this.options = []; this._html = ''; this.textContent = '';
    this.hidden = false; this.disabled = false; this.dataset = {}; this.style = {}; this.onchange = null; this.onclick = null;
    this.offsetHeight = 20; this.className = '';
    this.classList = {add() {}, remove() {}, contains() { return false; }, toggle() {}};
  }
  get value() { return this._value !== undefined ? this._value : (this.options[0] ? this.options[0].value : ''); }
  set value(v) { this._value = v; }
  get innerHTML() { return this._html; }
  set innerHTML(v) { this._html = v; if (v === '') { this.options.length = 0; this._value = defaults[this.id]; } }
  get selectedOptions() { return [this.options.find(o => o.value === this.value) || {text: ''}]; }
  add(o) { this.options.push(o); }
  closest(sel) { return sel === 'label' ? new El('label-dummy') : null; }
  setAttribute() {} getAttribute() { return null; } focus() {} querySelector() { return null; } querySelectorAll() { return []; }
  getBoundingClientRect() { return {left: 0, right: 16, top: 0, bottom: 16, width: 16, height: 16}; }
}
const $ = id => (els[id] = els[id] || new El(id));
const document = {
  getElementById: $, addEventListener: (t, f) => (listeners[t] = listeners[t] || []).push(f),
  querySelector: () => null, querySelectorAll: () => [],
};
const ctx = vm.createContext({
  document, window: {addEventListener() {}}, location: {hash: '', pathname: '/map.html'},
  history: {replaceState() {}}, Option, URLSearchParams, innerWidth: 1400, innerHeight: 900,
  matchMedia: () => ({matches: false}), console,
});
vm.runInContext(script, ctx);

function camel(s) { return s.replace(/-([a-z])/g, (_, c) => c.toUpperCase()); }
function matchOne(el, sel) {
  const m = sel.trim().match(/^([a-zA-Z][\w-]*)?((?:\.[\w-]+)*)((?:\[[^\]]+\])*)$/);
  if (!m) return false;
  if (m[1] && m[1].toLowerCase() !== el.tagName.toLowerCase()) return false;
  const classes = (el.attrs.class || '').split(/\s+/);
  for (const c of (m[2] || '').split('.').filter(Boolean)) if (!classes.includes(c)) return false;
  for (const a of (m[3] || '').match(/\[[^\]]+\]/g) || []) {
    const p = a.slice(1, -1).match(/^([\w-]+)(?:([\^*$~|]?=)"?([^"]*)"?)?$/);
    if (!p) return false;
    const v = el.attrs[p[1]];
    if (v === undefined) return false;
    if (p[2] === '=' && v !== p[3]) return false;
    if (p[2] === '^=' && !v.startsWith(p[3])) return false;
    if (p[2] === '*=' && !v.includes(p[3])) return false;
    if (p[2] === '$=' && !v.endsWith(p[3])) return false;
  }
  return true;
}
function fake(attrs) {
  const el = {tagName: 'BUTTON', attrs, dataset: {}, parentElement: null, hidden: false, textContent: ''};
  for (const k of Object.keys(attrs)) if (k.startsWith('data-')) el.dataset[camel(k.slice(5))] = attrs[k];
  el.getAttribute = n => (n in attrs ? attrs[n] : null);
  el.hasAttribute = n => n in attrs;
  el.setAttribute = () => {};
  el.matches = sel => sel.split(',').some(s => matchOne(el, s));
  el.closest = sel => (el.matches(sel) ? el : null);
  el.classList = {contains: c => (attrs.class || '').split(/\s+/).includes(c), add() {}, remove() {}};
  el.getBoundingClientRect = () => ({left: 100, right: 116, top: 100, bottom: 116, width: 16, height: 16});
  el.focus = () => {};
  return el;
}
function fire(type, attrs) {
  const el = fake(attrs);
  for (const f of listeners[type] || []) f({target: el, key: 'Enter', preventDefault() {}, stopPropagation() {}});
}

const view = $('view');
view.value = scenario.view; view.onchange();
if (scenario.mode) { $('mode').value = scenario.mode; $('mode').onchange(); }
if (scenario.view === 'comparison') {
  $('writer').value = scenario.writer; $('writer').onchange();
  $('resaver').value = scenario.resaver; $('resaver').onchange();
}
// expand: attribute dicts of group toggle buttons (taken from a render of the same view); each is
// clicked in order with the page's own click listener, and #views is recorded after every click
// (the page must re-render #views.innerHTML when a group opens or closes). Hover and click
// scenarios run after the expansions, so a viewCells index taken from the expanded render holds.
const afterExpand = [];
for (const attrs of scenario.expand || []) {
  fire('click', attrs);
  afterExpand.push($('views').innerHTML);
}
const out = {
  after_expand: afterExpand,
  views: $('views').innerHTML, grid: $('grid').innerHTML, summary_html: $('summary').innerHTML,
  summary_text: $('summary').textContent, legend_html: $('legend').innerHTML, method: $('method').textContent,
  instructions: $('instructions').textContent,
  icons: vm.runInContext('typeof icons==="undefined"?null:icons', ctx),
  tooltips: [], panels: [],
};
const tip = $('tooltip');
for (const attrs of scenario.hover || []) {
  const rec = {};
  for (const [name, type] of [['hover', 'mouseover'], ['focus', 'focusin']]) {
    tip.hidden = true; tip.textContent = '';
    try { fire(type, attrs); rec[name] = tip.hidden ? '' : tip.textContent; } catch (e) { rec[name] = ''; rec[name + '_error'] = String(e); }
  }
  out.tooltips.push(rec);
}
for (const attrs of scenario.click || []) {
  const panel = $('panel'), details = $('details');
  panel.hidden = true; details.innerHTML = '';
  const rec = {};
  try { fire('click', attrs); } catch (e) { rec.error = String(e); }
  rec.hidden = panel.hidden; rec.html = details.innerHTML;
  out.panels.push(rec);
}
process.stdout.write(JSON.stringify(out));
