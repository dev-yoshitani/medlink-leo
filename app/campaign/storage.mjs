export const SAVE_KEY = 'medlink-leo-fleet-v3';
export const LEGACY_KEYS = ['medlink-leo-campaign-v2', 'medlink-leo-campaign-v1'];
export function readCampaign(storage) {
  const current = storage.getItem(SAVE_KEY);
  if (current !== null) return current;
  return LEGACY_KEYS.map(key => storage.getItem(key)).find(value => value !== null) ?? null;
}
export function saveCampaign(storage, state, expected) {
  const current = storage.getItem(SAVE_KEY);
  if (current !== expected) throw new Error('別の画面で進行が変わりました。最新のセーブを読み込んでください。');
  const text = JSON.stringify(state);
  if (text === current) return text;
  const backup = current ?? LEGACY_KEYS.map(key => storage.getItem(key)).find(value => value !== null);
  if (backup !== undefined && backup !== null) storage.setItem(`${SAVE_KEY}.backup`, backup);
  storage.setItem(SAVE_KEY, text);
  if (storage.getItem(SAVE_KEY) !== text) throw new Error('保存の確認ができませんでした。セーブファイルを書き出してください。');
  return text;
}
export function moveAllocation(allocations, parcel, step) {
  const list = allocations.map(a => ({...a}));
  const i = list.findIndex(a => a.parcel === parcel), target = i + step;
  if (i >= 0 && target >= 0 && target < list.length) [list[i], list[target]] = [list[target], list[i]];
  return list;
}
export function assignAllocation(allocations, parcel, contact) {
  const list = allocations.filter(a => a.parcel !== parcel).map(a => ({...a}));
  if (contact) list.push({parcel, contact});
  return list;
}
export function reorderAllocation(allocations, from, to) {
  const list=allocations.map(a=>({...a}));
  const source=list.findIndex(a=>a.parcel===from);
  if(source<0||!list.some(a=>a.parcel===to)||from===to)return list;
  const [item]=list.splice(source,1);
  const target=list.findIndex(a=>a.parcel===to);
  list.splice(target,0,item);
  return list;
}
export function timeLabel(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const minutes = Math.floor(Math.max(0, seconds) / 60);
  return `${String(6 + Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}
export function parcelStatus(delivery, clock) {
  if (delivery.departure === null) return delivery.reason;
  if (clock < delivery.departure) return '衛星で待機';
  if (clock < delivery.completion) return '地上局へ送信中';
  if (clock < delivery.arrival) return '病院へ転送中';
  return delivery.on_time ? '期限内に到着' : '期限を過ぎて到着';
}
