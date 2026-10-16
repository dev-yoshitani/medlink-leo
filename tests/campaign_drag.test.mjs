import test from 'node:test';
import assert from 'node:assert/strict';
import {bindParcelDrag} from '../app/campaign/drag.mjs';

// Unit fixture for bound event handlers; this is not a real browser gesture.
function fixture() {
  let plan = ['a','b','c'].map(parcel => ({parcel,contact:'x'}));
  let revision = 1, editable = true, hit = null;
  const writes = [];
  const element = (dataset, top = 0) => {
    const classes = new Set();
    return {dataset,disabled:false,
      classList:{add:(...names)=>names.forEach(n=>classes.add(n)),remove:(...names)=>names.forEach(n=>classes.delete(n)),contains:n=>classes.has(n)},
      getBoundingClientRect:()=>({top,height:100}),
      closest:selector=>selector==='button,select,input'?null:[...nodes,slot].find(n=>n.dataset===dataset),
      contains:target=>target?.dataset===dataset};
  };
  const nodes = ['a','b','c'].map((parcel,i)=>element({parcel},i*100));
  const slot = element({contact:'y'});
  const handles = nodes.map(()=>({
    setPointerCapture(){this.captured=true;},hasPointerCapture(){return this.captured;},
    releasePointerCapture(){this.captured=false;},
  }));
  nodes.forEach((row,i)=>{row.querySelector=()=>handles[i];});
  const root = {
    contains:el=>[...nodes,slot].includes(el),
    ownerDocument:{elementFromPoint:()=>hit},
    querySelectorAll:selector=>selector==='.parcel[draggable=true]'?nodes:
      selector==='.dragging'?nodes.filter(n=>n.classList.contains('dragging')):[...nodes,slot],
  };
  bindParcelDrag(root,{getPlan:()=>plan,getRevision:()=>revision,canEdit:()=>editable,
    onPlan:next=>{writes.push(next);plan=next;}});
  const event = (target,clientY=0,extra={})=>({target,clientY,clientX:0,pointerId:1,pointerType:'touch',isPrimary:true,
    dataTransfer:{setData(){}},preventDefault(){},stopPropagation(){},...extra});
  return {nodes,handles,slot,writes,event,get plan(){return plan;},
    setHit:el=>{hit=el;},invalidate:()=>{revision++;},lock:()=>{editable=false;}};
}

test('native drop into lower half moves an adjacent row down and marks the same gap',()=>{
  const f=fixture(),[a,b]=f.nodes;
  a.ondragstart(f.event(a));
  b.ondragover(f.event(b,175));
  assert.ok(b.classList.contains('drop-after'));
  b.ondrop(f.event(b,175));
  assert.deepEqual(f.plan.map(a=>a.parcel),['b','a','c']);
  assert.equal(f.writes.length,1);
  assert.ok(!b.classList.contains('drop-after'));
});

test('native drop into upper half moves the last row to the first position',()=>{
  const f=fixture(),[a,,c]=f.nodes;
  c.ondragstart(f.event(c));a.ondragover(f.event(a,20));
  assert.ok(a.classList.contains('drop-before'));
  a.ondrop(f.event(a,20));
  assert.deepEqual(f.plan.map(a=>a.parcel),['c','a','b']);
});

test('changing a contact retains order; identical, external and stale drops do not write',()=>{
  const f=fixture(),[a,b,c]=f.nodes;
  a.ondragstart(f.event(a));a.ondrop(f.event(a,20));
  assert.equal(f.writes.length,0);
  f.slot.ondrop(f.event(f.slot)); // No active in-app drag.
  assert.equal(f.writes.length,0);
  b.ondragstart(f.event(b));f.slot.ondrop(f.event(f.slot));
  assert.deepEqual(f.plan,[{parcel:'a',contact:'x'},{parcel:'b',contact:'y'},{parcel:'c',contact:'x'}]);
  b.ondragstart(f.event(b));f.slot.ondrop(f.event(f.slot));
  assert.equal(f.writes.length,1);
  c.ondragstart(f.event(c));f.invalidate();a.ondrop(f.event(a,20));
  assert.equal(f.writes.length,1);
});

test('touch drop hit-tests the release point instead of the previous move',()=>{
  const f=fixture(),[a,b,c]=f.nodes,handle=f.handles[0];
  handle.onpointerdown(f.event(a,20));
  f.setHit(b);handle.onpointermove(f.event(b,175));
  assert.ok(b.classList.contains('drop-after'));
  f.setHit(c);handle.onpointerup(f.event(c,275));
  assert.deepEqual(f.plan.map(a=>a.parcel),['b','c','a']);
  assert.equal(handle.captured,false);
});

test('touch cancellation and an editing lock do not persist a move',()=>{
  for(const cancel of [true,false]) {
    const f=fixture(),[a,b]=f.nodes,handle=f.handles[0];
    handle.onpointerdown(f.event(a,20));f.setHit(b);handle.onpointermove(f.event(b,175));
    if(cancel)handle.onpointercancel(f.event(b,175,{type:'pointercancel'}));
    else {f.lock();handle.onpointerup(f.event(b,175));}
    assert.equal(f.writes.length,0);assert.equal(handle.captured,false);
  }
});
