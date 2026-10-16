import test from 'node:test';
import assert from 'node:assert/strict';
import {dayFlow} from '../app/campaign/workflow.mjs';

const contracts=[{id:'regular',parcels:[{id:'a'},{id:'b'}]},{id:'urgent',parcels:[{id:'c'}]}];
const state=()=>({accepted:[],plan:{allocations:[]},report:null,claimed:[]});

test('no orders guides the player to choose an order without offering a commit',()=>{
  const next=dayFlow(state(),contracts,2);
  assert.equal(next.phase,0);assert.equal(next.tab,1);assert.equal(next.action,undefined);
});
test('only accepted parcels and unique assignments count toward the plan',()=>{
  const s=state();s.accepted=['regular'];s.plan.allocations=[{parcel:'a'},{parcel:'a'},{parcel:'c'}];
  const next=dayFlow(s,contracts,0);
  assert.equal(next.total,2);assert.equal(next.remaining,1);assert.equal(next.tab,2);
  assert.equal(dayFlow(s,contracts,2).action,'auto');
  assert.equal(s.plan.allocations.length,3);
});
test('a completed plan requires review before the run button is offered',()=>{
  const s=state();s.accepted=['regular'];s.plan.allocations=[{parcel:'a'},{parcel:'b'}];
  assert.equal(dayFlow(s,contracts,0).action,undefined);
  assert.equal(dayFlow(s,contracts,0).tab,2);
  assert.equal(dayFlow(s,contracts,2).action,'commit');
});
test('a fixed result points directly to its settlement regardless of tab or plan',()=>{
  const s=state();s.report={id:'settlement-7'};
  const next=dayFlow(s,contracts,1);
  assert.equal(next.phase,2);assert.equal(next.action,'claim');
  assert.deepEqual(next.fields,{settlement:'settlement-7'});
});
test('a received reward points to the next day and never offers another claim',()=>{
  const s=state();s.report={id:'settlement-7'};s.claimed=['settlement-7'];
  const next=dayFlow(s,contracts,5);
  assert.equal(next.phase,3);assert.equal(next.action,'next');
});
