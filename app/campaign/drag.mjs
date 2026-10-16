import {assignAllocation, reorderAllocation, insertionSide} from './storage.mjs';

// Mouse and touch use the same drop geometry and revision checks.
export function bindParcelDrag(root, {getPlan, getRevision, canEdit, onPlan}) {
  let source = null, revision = null, marked = null;
  const clearMark = () => {
    if (marked) marked.classList.remove('drop-before', 'drop-after', 'drop-target');
    marked = null;
  };
  const clear = () => {
    clearMark();
    root.querySelectorAll('.dragging').forEach(el => el.classList.remove('dragging'));
    source = null;
  };
  const valid = () => source && canEdit() && revision === getRevision();
  const candidate = (target, y) => {
    const el = target?.closest('[data-contact],.parcel');
    if (!el || !root.contains(el) || el.disabled || !valid()) return null;
    if (el.dataset.contact) return {el, contact: el.dataset.contact};
    if (el.dataset.parcel === source || !getPlan().some(a => a.parcel === source)
      || !getPlan().some(a => a.parcel === el.dataset.parcel)) return null;
    const rect = el.getBoundingClientRect();
    return {el, parcel: el.dataset.parcel, side: insertionSide(y, rect.top, rect.height)};
  };
  const mark = drop => {
    clearMark();
    if (!drop) return;
    marked = drop.el;
    marked.classList.add(drop.contact ? 'drop-target' : `drop-${drop.side}`);
  };
  const commit = drop => {
    if (!drop || !valid()) {clear(); return;}
    const current = getPlan();
    const next = drop.contact ? assignAllocation(current, source, drop.contact)
      : reorderAllocation(current, source, drop.parcel, drop.side);
    clear();
    // A no-op shouldn't cause a server round trip or make the table blink.
    if (JSON.stringify(next) !== JSON.stringify(current)) onPlan(next);
  };
  root.querySelectorAll('.parcel[draggable=true]').forEach(row => {
    row.ondragstart = e => {
      if (!canEdit() || e.target.closest('button,select,input')) {e.preventDefault(); return;}
      source = row.dataset.parcel; revision = getRevision();
      e.dataTransfer.setData('text/plain', source);
      e.dataTransfer.effectAllowed = 'move';
      row.classList.add('dragging');
    };
    row.ondragend = clear;
    const handle = row.querySelector('.drag-handle');
    if (!handle) return;
    handle.onpointerdown = e => {
      if (e.pointerType === 'mouse' || !canEdit() || !e.isPrimary) return;
      source = row.dataset.parcel; revision = getRevision();
      const x = e.clientX, y = e.clientY;
      let moved = false;
      handle.setPointerCapture(e.pointerId);
      handle.onpointermove = move => {
        if (Math.hypot(move.clientX - x, move.clientY - y) < 8 && !moved) return;
        moved = true; move.preventDefault(); row.classList.add('dragging');
        mark(candidate(root.ownerDocument.elementFromPoint(move.clientX, move.clientY), move.clientY));
      };
      const finish = up => {
        handle.onpointermove = null; handle.onpointerup = null; handle.onpointercancel = null;
        if (handle.hasPointerCapture(up.pointerId)) handle.releasePointerCapture(up.pointerId);
        if (up.type === 'pointercancel' || !moved) {clear(); return;}
        up.preventDefault();
        // Hit-test the release position, not the last pointermove position.
        commit(candidate(root.ownerDocument.elementFromPoint(up.clientX, up.clientY), up.clientY));
      };
      handle.onpointerup = finish;
      handle.onpointercancel = finish;
    };
  });
  root.querySelectorAll('.parcel,[data-contact]').forEach(el => {
    el.ondragover = e => {
      const drop = candidate(el, e.clientY);
      mark(drop);
      if (drop) {e.preventDefault(); e.dataTransfer.dropEffect = 'move';}
    };
    el.ondragleave = e => {if (!el.contains(e.relatedTarget)) clearMark();};
    el.ondrop = e => {
      e.preventDefault(); e.stopPropagation();
      commit(candidate(el, e.clientY));
    };
  });
}
