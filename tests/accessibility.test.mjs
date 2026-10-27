import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../src/patient_follow_up_system/web/accessibility.js', import.meta.url), 'utf8');
const key = 'patient-follow-up-large-text';

function setup({stored, blocked = false, loading = false} = {}) {
  const classes = new Set(), listeners = {}, windowListeners = {}, elements = [], writes = [];
  const storage = new Map(stored === undefined ? [] : [[key, stored]]);
  const make = () => ({children: [], attributes: {}, events: {}, className: '',
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(name, fn) { this.events[name] = fn; },
    appendChild(el) { this.children.push(el); }, prepend(el) { this.children.unshift(el); }});
  const host = make();
  const buttons = () => elements.filter(el => el.className === 'text-size-toggle');
  const context = vm.createContext({document: {
    documentElement: {classList: {toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); }, contains: name => classes.has(name)}},
    readyState: loading ? 'loading' : 'complete', body: host,
    createElement() { const el = make(); elements.push(el); return el; },
    querySelector(selector) { return selector === '.text-size-toggle' ? buttons()[0] : selector === '.doctor-main' ? host : null; },
    querySelectorAll: buttons,
    addEventListener(name, fn) { listeners[name] = fn; },
  }, localStorage: {
    getItem(name) { if (blocked) throw new Error('storage unavailable'); return storage.get(name) ?? null; },
    setItem(name, value) { if (blocked) throw new Error('storage unavailable'); storage.set(name, value); writes.push([name, value]); },
  }, window: {addEventListener(name, fn) { windowListeners[name] = fn; }}});
  vm.runInContext(source, context);
  return {classes, listeners, windowListeners, storage, buttons, writes};
}

test('saved large-text preference applies before the first page render and persists on the next page', () => {
  const first = setup({stored: 'true', loading: true});
  assert.ok(first.classes.has('large-text'));
  assert.equal(first.buttons().length, 0);
  first.listeners.DOMContentLoaded();
  const button = first.buttons()[0];
  assert.equal(button.attributes['aria-pressed'], 'true');
  assert.match(button.textContent, /开/);
  button.events.click();
  assert.equal(first.classes.has('large-text'), false);
  assert.deepEqual(first.writes, [[key, 'false']]);
  assert.equal(setup({stored: first.storage.get(key)}).classes.has('large-text'), false);
});

test('toggle works without storage access and remains a non-submit button', () => {
  const state = setup({blocked: true});
  const button = state.buttons()[0];
  assert.equal(button.type, 'button');
  button.events.click();
  assert.ok(state.classes.has('large-text'));
  assert.equal(button.attributes['aria-pressed'], 'true');
  button.events.click();
  assert.equal(state.classes.has('large-text'), false);
});

test('open pages synchronize font preference without writing or triggering business requests', () => {
  const state = setup();
  state.storage.set(key, 'true');
  state.windowListeners.storage({key});
  assert.ok(state.classes.has('large-text'));
  assert.equal(state.buttons()[0].attributes['aria-pressed'], 'true');
  state.storage.set(key, 'false');
  state.windowListeners.storage({key: 'unrelated-setting'});
  assert.ok(state.classes.has('large-text'));
  state.windowListeners.storage({key});
  assert.equal(state.classes.has('large-text'), false);
  assert.deepEqual(state.writes, []);
});

test('clearing browser preferences resets the font size in other open pages', () => {
  const state = setup({stored: 'true'});
  state.storage.clear();
  state.windowListeners.storage({key: null});
  assert.equal(state.classes.has('large-text'), false);
  assert.equal(state.buttons()[0].attributes['aria-pressed'], 'false');
});
