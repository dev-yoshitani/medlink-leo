import test from 'node:test';
import assert from 'node:assert/strict';
import {SAVE_KEY,LEGACY_KEYS,readCampaign,saveCampaign,moveAllocation,assignAllocation,reorderAllocation,insertionSide,timeLabel,parcelStatus} from '../app/campaign/storage.mjs';
function storage(){const m=new Map();return {getItem:k=>m.get(k)??null,setItem:(k,v)=>m.set(k,v)};}

test('drag reordering preserves every allocation and ignores stale or identical source',()=>{
  const plan=[{parcel:'a',contact:'x'},{parcel:'b',contact:'y'},{parcel:'c',contact:'z'}];
  assert.deepEqual(reorderAllocation(plan,'c','a'),[plan[2],plan[0],plan[1]]);
  assert.deepEqual(reorderAllocation(plan,'a','c'),[plan[1],plan[0],plan[2]]);
  assert.deepEqual(reorderAllocation(plan,'gone','a'),plan);
  assert.deepEqual(reorderAllocation(plan,'c','gone'),plan);
  assert.deepEqual(reorderAllocation(plan,'c',''),plan);
  assert.deepEqual(reorderAllocation(plan,'a','a'),plan);
  assert.equal(plan[0].parcel,'a');
});
test('drops above and below a row move to the indicated gap in both directions',()=>{
  const plan=['a','b','c'].map(parcel=>({parcel,contact:'x'}));
  assert.deepEqual(reorderAllocation(plan,'a','b','after').map(a=>a.parcel),['b','a','c']);
  assert.deepEqual(reorderAllocation(plan,'a','c','after').map(a=>a.parcel),['b','c','a']);
  assert.deepEqual(reorderAllocation(plan,'c','a','before').map(a=>a.parcel),['c','a','b']);
  assert.deepEqual(reorderAllocation(plan,'c','a','after').map(a=>a.parcel),['a','c','b']);
  assert.equal(insertionSide(119,100,40),'before');
  assert.equal(insertionSide(120,100,40),'after');
});
test('legacy migration preserves original and backup; new saves isolate old tabs',()=>{
  const db=storage();db.setItem(LEGACY_KEYS[0],'old');assert.equal(readCampaign(db),'old');
  const fresh=saveCampaign(db,{revision:0,credits:380},null);assert.equal(db.getItem(`${SAVE_KEY}.backup`),'old');
  db.setItem(LEGACY_KEYS[0],'stale');assert.equal(readCampaign(db),fresh);
});
test('compare-and-set prevents a stale tab rolling back a claim',()=>{
  const db=storage(),first=saveCampaign(db,{revision:1,credits:380},null);
  const paid=saveCampaign(db,{revision:2,credits:500},first);
  assert.throws(()=>saveCampaign(db,{revision:2,credits:200},first),/進行/);
  assert.equal(db.getItem(SAVE_KEY),paid);
});
test('saving unchanged state does not rotate backup',()=>{
  const db=storage(),state={revision:1},first=saveCampaign(db,state,null);
  db.setItem(`${SAVE_KEY}.backup`,'original');saveCampaign(db,state,first);
  assert.equal(db.getItem(`${SAVE_KEY}.backup`),'original');
});
test('storage failure is reported, never swallowed',()=>{
  const db=storage();db.setItem=()=>{throw Error('quota');};assert.throws(()=>saveCampaign(db,{revision:1},null),/quota/);
});
test('assignment and ordering do not mutate the live plan',()=>{
  const plan=[{parcel:'a',contact:'x'},{parcel:'b',contact:'y'}];
  assert.equal(moveAllocation(plan,'b',-1)[0].parcel,'b');assert.equal(plan[0].parcel,'a');
  assert.deepEqual(assignAllocation(plan,'a','z'),[{parcel:'a',contact:'z'},{parcel:'b',contact:'y'}]);
  assert.deepEqual(assignAllocation(plan,'a','x'),plan);
  assert.deepEqual(assignAllocation(plan,'c','z'),[...plan,{parcel:'c',contact:'z'}]);
  assert.deepEqual(assignAllocation(plan,'a',''),[{parcel:'b',contact:'y'}]);
});
test('replay only changes visual status',()=>{
  const r={departure:100,completion:200,arrival:240,on_time:true};
  assert.equal(parcelStatus(r,50),'衛星で待機');assert.equal(parcelStatus(r,150),'地上局へ送信中');
  assert.equal(parcelStatus(r,220),'病院へ転送中');assert.equal(parcelStatus(r,240),'期限内に到着');
  assert.equal(timeLabel(21600),'12:00');assert.equal(timeLabel(null),'—');
});
