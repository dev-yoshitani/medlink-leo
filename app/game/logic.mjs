export const SAVE_KEY = 'medlink-leo-campaign-v1';
export const TUTORIAL_KEY = 'medlink-leo-tutorial-v1';
export const STATION_X = {'gs-seoul': 250, 'gs-sapporo': 550, 'gs-tokyo': 850};

export function tutorialStage(model, time = 0) {
  if (model?.active) {
    if (!model.report) return 1;
    return time >= model.report.end_time ? 3 : 2;
  }
  if (!model?.state?.dispatches) return 0;
  return model.stations?.some(station => station.opened &&
    (station.antenna > 1 || station.backhaul > 1)) ? 5 : 4;
}

export function readTutorialPreference(storage) {
  try {
    const value = storage.getItem(TUTORIAL_KEY);
    if (value === null) return {open:true};
    const preference = JSON.parse(value);
    return typeof preference?.open === 'boolean' ? {open:preference.open} : {open:true};
  } catch { return {open:true}; }
}

export function writeTutorialPreference(storage, open) {
  try {
    storage.setItem(TUTORIAL_KEY, JSON.stringify({open}));
    return true;
  } catch { return false; }
}

export function timeLabel(value) {
  if (value == null || !Number.isFinite(value)) return '—';
  const seconds = Math.max(0, Math.round(value));
  return [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60]
    .map(part => String(part).padStart(2, '0')).join(':');
}

export function parcelStatus(result, time, ended = false) {
  if (time < result.created) return '未生成';
  if (!result.delivered) return ended ? result.outcome : '待機';
  if (time < result.departure) return '衛星で待機';
  if (time < result.rf_complete) return '地上局へ送信中';
  if (time < result.arrival) return '病院へ転送中';
  return result.on_time ? '期限内に到着' : '期限を過ぎて到着';
}

export function parcelPosition(result, time) {
  if (!result.delivered || time < result.departure || time >= result.arrival) return null;
  const stationX = STATION_X[result.station];
  if (stationX == null) return null;
  if (time < result.rf_complete) {
    const p = (time - result.departure) / Math.max(0.001, result.rf_complete - result.departure);
    const q = 1 - p;
    return {x: q * q * 550 + 2 * q * p * stationX + p * p * stationX,
      y: q * q * 140 + 2 * q * p * 200 + p * p * 260};
  }
  const p = (time - result.rf_complete) / Math.max(0.001, result.arrival - result.rf_complete);
  return {x: stationX + (1000 - stationX) * p, y: 335 + 65 * p};
}

export function advanceTime(time, elapsedMs, speed, endTime) {
  // One normal-speed replay lasts 36 seconds, regardless of simulated horizon.
  return Math.min(endTime, Math.max(0, time) + Math.max(0, elapsedMs) / 1000
    * Math.max(1, endTime) / 36 * speed);
}

export function readSave(storage) {
  try { return storage.getItem(SAVE_KEY); } catch { return null; }
}

export function writeSave(storage, state) {
  try {
    const text = JSON.stringify(state);
    const previous = storage.getItem(SAVE_KEY);
    if (previous && previous !== text) storage.setItem(`${SAVE_KEY}.backup`, previous);
    storage.setItem(SAVE_KEY, text);
    return storage.getItem(SAVE_KEY) === text;
  } catch { return false; }
}
