import test from 'node:test';
import assert from 'node:assert/strict';
import {SAVE_KEY, TUTORIAL_KEY, timeLabel, parcelStatus, parcelPosition, advanceTime,
  readSave, writeSave, tutorialStage, readTutorialPreference, writeTutorialPreference}
  from '../app/game/logic.mjs';

const result = {created:10, departure:100, rf_complete:200, arrival:230,
  delivered:true, on_time:true, station:'gs-sapporo', outcome:'到着'};

test('packet replay follows RF and backhaul boundaries from the engine', () => {
  assert.equal(parcelStatus(result, 0), '未生成');
  assert.equal(parcelStatus(result, 70), '衛星で待機');
  assert.equal(parcelStatus(result, 150), '地上局へ送信中');
  assert.equal(parcelStatus(result, 200), '病院へ転送中');
  assert.equal(parcelStatus(result, 230), '期限内に到着');
  assert.equal(parcelPosition(result, 99), null);
  assert.deepEqual(parcelPosition(result, 100), {x:550, y:140});
  assert.deepEqual(parcelPosition(result, 200), {x:550, y:335});
  assert.deepEqual(parcelPosition(result, 215), {x:775, y:367.5});
  assert.equal(parcelPosition(result, 230), null);
});

test('failed and late deliveries are represented without invented packet motion', () => {
  const failure = {...result, delivered:false, outcome:'通信容量不足', arrival:null};
  assert.equal(parcelStatus(failure, 300), '待機');
  assert.equal(parcelStatus(failure, 300, true), '通信容量不足');
  assert.equal(parcelPosition(failure, 150), null);
  assert.equal(parcelStatus({...result, on_time:false}, 230), '期限を過ぎて到着');
});

test('replay speeds and end boundaries preserve the simulation clock', () => {
  assert.equal(advanceTime(0, 1000, 1, 360), 10);
  assert.equal(advanceTime(0, 1000, 4, 360), 40);
  assert.equal(advanceTime(350, 1000, 16, 360), 360);
  assert.equal(advanceTime(100, 0, 1, 360), 100);
  assert.equal(timeLabel(3670), '01:01:10');
  assert.equal(timeLabel(null), '—');
});

test('automatic saves survive a new browser instance and preserve the previous revision', () => {
  const values = new Map();
  const storage = {getItem:key => values.get(key) ?? null, setItem:(key, value) => values.set(key, value)};
  assert.equal(readSave(storage), null);
  assert.equal(writeSave(storage, {credits:150}), true);
  assert.equal(writeSave(storage, {credits:370}), true);
  assert.deepEqual(JSON.parse(readSave(storage)), {credits:370});
  assert.deepEqual(JSON.parse(storage.getItem(`${SAVE_KEY}.backup`)), {credits:150});
  assert.equal(writeSave(storage, {credits:370}), true);
  assert.deepEqual(JSON.parse(storage.getItem(`${SAVE_KEY}.backup`)), {credits:150});
});

test('storage errors do not claim a successful save', () => {
  const storage = {getItem:() => {throw Error('blocked');}, setItem:() => {throw Error('blocked');}};
  assert.equal(readSave(storage), null);
  assert.equal(writeSave(storage, {}), false);
});

test('guide follows the current operation and replay result', () => {
  const model = {active:null, report:null, state:{dispatches:0},
    stations:[{opened:true, antenna:1, backhaul:1}]};
  assert.equal(tutorialStage(model), 0);
  model.stations[0].antenna = 2;
  assert.equal(tutorialStage(model), 0);
  model.active = {contract_id:'morning'};
  assert.equal(tutorialStage(model), 1);
  model.report = {end_time:360};
  assert.equal(tutorialStage(model, 359), 2);
  assert.equal(tutorialStage(model, 360), 3);
  model.active = null;
  model.report = null;
  model.state.dispatches = 1;
  assert.equal(tutorialStage(model), 5);
  model.stations[0].antenna = 1;
  assert.equal(tutorialStage(model), 4);
  model.active = {contract_id:'second'};
  assert.equal(tutorialStage(model), 1);
});

test('guide visibility is stored separately and invalid preferences recover', () => {
  const values = new Map();
  const storage = {getItem:key => values.get(key) ?? null, setItem:(key, value) => values.set(key, value)};
  assert.deepEqual(readTutorialPreference(storage), {open:true});
  assert.equal(writeTutorialPreference(storage, false), true);
  assert.equal(values.get(TUTORIAL_KEY), '{"open":false}');
  assert.deepEqual(readTutorialPreference(storage), {open:false});
  values.set(TUTORIAL_KEY, '{"open":"false"}');
  assert.deepEqual(readTutorialPreference(storage), {open:true});
  values.set(TUTORIAL_KEY, 'broken');
  assert.deepEqual(readTutorialPreference(storage), {open:true});
  const blocked = {getItem:() => {throw Error('blocked');}, setItem:() => {throw Error('blocked');}};
  assert.deepEqual(readTutorialPreference(blocked), {open:true});
  assert.equal(writeTutorialPreference(blocked, false), false);
});
