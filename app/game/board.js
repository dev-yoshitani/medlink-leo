import {SAVE_KEY, STATION_X, timeLabel, parcelStatus, parcelPosition,
  advanceTime, readSave, writeSave} from './logic.mjs';

const root = document.getElementById('board');
let model, args, selectedStation = 'gs-sapporo', restoreSent = false, pendingId = null;
let storageOK = true, replayKey = null, clock = 0, playing = false, speed = 1, lastFrame = null;
let savedNotice = '';
const esc = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
const money = value => Number(value).toLocaleString('ja-JP');
const disabled = condition => condition ? ' disabled' : '';
const levelPips = level => `<span class="level-pips" aria-label="レベル${level}">${
  Array.from({length:5}, (_, i) => `<i class="${i < level ? 'filled' : ''}"></i>`).join('')}</span>`;

function message(type, extra = {}) {
  parent.postMessage({isStreamlitMessage:true, type, ...extra}, '*');
}
function fit() {
  message('streamlit:setFrameHeight', {height: Math.ceil(root.getBoundingClientRect().height) + 5});
}
function send(action, fields = {}) {
  if (pendingId) return;
  pendingId = crypto.randomUUID();
  root.querySelectorAll('button[data-action]').forEach(button => {button.disabled = true;});
  document.getElementById('busy').hidden = false;
  message('streamlit:setComponentValue', {
    value:{id:pendingId, action, ...fields}, dataType:'json',
  });
}
function facilities() {
  return model.stations.map(station => {
    const x = STATION_X[station.id], current = selectedStation === station.id;
    const buildingWidth = 95 + (station.backhaul - 1) * 8;
    const dishWidth = 94 + (station.antenna - 1) * 5;
    const extraDish = station.antenna >= 3
      ? `<image href="${model.assets.ground_station}" x="${x + 30}" y="281" width="48" height="36"/>` : '';
    return `<g class="station" data-station="${station.id}" role="button" tabindex="0"
      aria-label="${station.name}の設備を選ぶ" opacity="${station.opened ? 1 : .42}">
      <ellipse class="station-pad" cx="${x}" cy="332" rx="86" ry="20"
        fill="${current ? '#c3dcc0' : '#d9e5cc'}" stroke="${current ? '#3d7b64' : '#a5bd9b'}"/>
      <rect x="${x - buildingWidth / 2}" y="300" width="${buildingWidth}" height="31"
        rx="4" fill="${station.opened ? '#eadbc2' : '#d9d8ca'}" stroke="#6e8a74" stroke-width="2"/>
      <path d="M${x - 44} 321h88" stroke="${station.backhaul > 1 ? '#ca954b' : '#839b81'}"
        stroke-width="${2 + station.backhaul}"/>
      <image href="${model.assets.ground_station}" x="${x - dishWidth / 2}" y="246"
        width="${dishWidth}" height="${dishWidth * .75}"/>${extraDish}
      <text x="${x}" y="375" text-anchor="middle" class="map-label">${station.name}</text>
      <text x="${x}" y="396" text-anchor="middle" class="map-sub">${station.opened
        ? `受信 Lv.${station.antenna}　回線 Lv.${station.backhaul}` : '未開放'}</text>
      ${!station.opened ? `<rect x="${x - 12}" y="288" width="24" height="21" rx="3" fill="#9b967e"/>
        <path d="M${x - 7} 288v-5a7 7 0 0 1 14 0v5" fill="none" stroke="#9b967e" stroke-width="4"/>` : ''}
      </g>`;
  }).join('');
}

function mapScene() {
  const selectedRoutes = new Set((model.report?.results || []).filter(r => r.delivered).map(r => r.station));
  const routes = model.stations.filter(s => s.opened).map(station => {
    const x = STATION_X[station.id], active = selectedRoutes.has(station.id);
    return `<path id="rf-${station.id}" class="route ${active ? 'active' : ''}"
      d="M550 140 Q${x} 200 ${x} 260"/>
      <path id="ground-${station.id}" class="route ${active ? 'active' : ''}"
      d="M${x} 335 L1000 400"/>`;
  }).join('');
  const packets = (model.report?.results || []).map((result, i) =>
    `<image id="packet-${i}" href="${model.assets[result.critical
      ? 'medical_packet_critical' : 'medical_packet_normal']}" width="32" height="25" visibility="hidden"/>`).join('');
  return `<section class="map-board" aria-label="通信ネットワークの模式図">
    <div class="map-heading"><span>通信ネットワーク</span><span>衛星 1機 · 地上局 ${
      model.stations.filter(s => s.opened).length}/3</span></div>
    <div class="map-scroll"><svg viewBox="0 0 1100 460" role="img" aria-label="設備と配送経路の模式図">
      <defs><pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse">
        <path d="M36 0H0V36" fill="none" stroke="#e4e8d7" stroke-width="1"/>
      </pattern></defs>
      <rect width="1100" height="460" fill="#f8f7e9"/>
      <rect width="1100" height="460" fill="url(#grid)"/>
      <path d="M0 320Q550 220 1100 330V460H0Z" fill="#e0e9ce"/>
      <path d="M0 320Q550 220 1100 330" fill="none" stroke="#9cb998" stroke-width="3"/>
      <g fill="#bdcfa9"><path d="M90 290l-15 29h30zM110 300l-13 25h26zM950 297l-15 29h30z"/></g>
      ${routes}
      <image href="${model.assets.satellite}" x="492" y="56" width="116" height="87"/>
      <text x="550" y="41" text-anchor="middle" class="map-label">低軌道衛星</text>
      <text x="550" y="164" text-anchor="middle" class="map-sub">データの出発点</text>
      ${facilities()}
      <image href="${model.assets.hospital}" x="958" y="345" width="91" height="75"/>
      <text x="1003" y="441" text-anchor="middle" class="map-sub">病院側の中継点</text>
      ${packets}
    </svg></div>
    <div class="map-foot">模式図・保存済みの過去の軌道で計算 / 診療所から衛星への送信は省略 / 小さな画面では地図を左右に動かせます</div>
  </section>`;
}

function contracts() {
  return `<aside class="request-book" aria-label="依頼手帳">
    <div class="book-title"><h2>依頼手帳</h2><small>繰り返し受注できます。失敗しても資金は減りません。</small></div>
    ${model.contracts.map(contract => {
      const locked = model.state.successes < contract.required;
      return `<article class="contract ${locked ? 'locked' : ''}">
        <h3>${esc(contract.title)}</h3><div class="contract-meta">
        <span>${contract.target}/${contract.total}件を期限内</span><span>達成 +${contract.bounty} C</span></div>
        <p>${esc(contract.description)}</p>
        <button data-action="accept" data-contract="${contract.id}"${disabled(locked || model.active)}>${
          locked ? `達成${contract.required}回で開放` : model.active?.contract_id === contract.id ? '受注中' : '受注する'}</button>
      </article>`;
    }).join('')}
  </aside>`;
}

function parcelRows() {
  return model.active.items.map((item, i) => `<div class="parcel-row">
    <span><b>${esc(item.name)}</b><small>${esc(item.priority)} · 期限 ${timeLabel(item.deadline)}</small></span>
    <span>${item.size_mb.toFixed(2)} MB</span>
    <span id="status-${i}" class="parcel-status">${model.report ? '衛星で待機' : '配送前'}</span>
  </div>`).join('');
}

function operations() {
  if (!model.active) {
    return `<section class="ops-sheet"><div class="section-line"><h2>次の配送を待っています</h2></div>
      <div class="empty-instructions"><img src="${model.assets.medical_packet_normal}" alt="配送するデータ">
      <div><b>依頼を届けて、通信センターを育てよう。</b>
      <p>依頼手帳から受注 → 配送方針を決める → 報酬を受け取る → 設備を強化。</p></div></div>
      <p class="tip">${model.state.dispatches ? '難しい依頼に備えて設備を育てよう。定期便はいつでも受注できます。'
        : '最初の資金は150 C。受信アンテナを強化してから、最初の依頼に挑むこともできます。'}</p>
      </section>`;
  }
  const mission = model.active;
  const planning = !model.report;
  return `<section class="ops-sheet" aria-label="配送の操作">
    <div class="section-line"><h2>${esc(mission.title)}</h2><small>${mission.target}件を期限内に届ける</small></div>
    <p class="tip">${esc(mission.tip)}</p>
    ${!planning ? `<p class="muted"><small>経路：${{
      'deadline-aware':'期限内の到着を優先','earliest-arrival':'病院への到着を早める',
      'next-contact':'次の通信機会を使う'}[mission.strategy]} / 送信順：${{
      edf:'期限が近い順',priority:'優先度順（説明用）',fifo:'生成された順'}[mission.scheduler]}</small></p>` : ''}
    ${planning ? `<div class="policy-controls">
      <label>経路の選び方<select id="strategy">
        <option value="deadline-aware">期限内の到着を優先</option>
        <option value="earliest-arrival">病院への到着を早める</option>
        <option value="next-contact">次の通信機会を使う</option></select></label>
      <label>送る順番<select id="scheduler">
        <option value="edf">期限が近い順</option><option value="priority">優先度順（説明用）</option>
        <option value="fifo">生成された順</option></select></label>
      </div>` : `<div class="playback-controls">
        <button id="play" class="small">${playing ? '一時停止' : '再生'}</button>
        <button id="rewind" class="small">最初から</button>
        <button id="speed" class="small">${speed}×</button>
        <button id="finish" class="small">最後まで</button>
        <time id="clock">${timeLabel(clock)}</time>
      </div><div class="progress-track"><div id="progress" class="progress-fill"></div></div>
      <small>計算結果の再生です。通常速度では約36秒で進みます。</small>`}
    <div class="parcel-list">${parcelRows()}</div>
    ${planning ? `<div class="actions"><button class="primary" data-action="dispatch">配送開始</button>
      <button data-action="abandon">受注を取り下げる</button></div>` : `
      <div id="result-stamp" class="result-stamp ${model.report.success ? '' : 'failed'}" hidden>
        <div><strong>${model.report.success ? '依頼達成！' : '次の運用につなげよう'}</strong>
        <small>期限内 ${model.report.on_time}/${model.report.total}件 · 到着 ${model.report.delivered}件</small></div>
        <b>+${model.report.reward} C</b></div>
      <div class="actions"><button class="primary" data-action="settle" id="claim" disabled>報酬を受け取って次へ</button></div>
      <details><summary>配送結果と計算の記録</summary>
        ${model.report.results.map(result => `<p><b>${esc(mission.items.find(item => item.id === result.id)?.name || result.id)}</b>
          · ${esc(result.outcome)} · 到着 ${timeLabel(result.arrival)}<br>${esc(result.reason)}</p>`).join('')}
      </details>`}
    </section>`;
}

function equipment() {
  const station = model.stations.find(s => s.id === selectedStation) || model.stations[1];
  const locked = !station.opened, busy = !!model.active;
  const rows = (locked ? [] : ['antenna', 'backhaul']).map(kind => {
    const level = station[kind], max = level >= model.max_level, cost = station[`${kind}_cost`];
    const name = kind === 'antenna' ? '受信アンテナ' : '地上回線';
    const description = kind === 'antenna'
      ? `受信利得 ${station.gain_dbi.toFixed(1)} → ${(station.gain_dbi + 2.5).toFixed(1)} dBi`
      : `地上回線の遅延 ${station.delay_s.toFixed(1)} → ${(station.delay_s * .6).toFixed(1)} 秒`;
    return `<div class="upgrade-row"><div><b>${name}</b>${levelPips(level)}
      <small>${max ? '最大レベルです' : description}</small></div>
      <button data-action="upgrade" data-equipment="${kind}"${disabled(max || busy || model.state.credits < cost)}>${
        max ? '強化済み' : `強化 ${money(cost)} C`}</button></div>`;
  });
  return `<section class="ops-sheet" aria-label="地上局の設備">
    <div class="section-line"><h2>設備を育てる</h2><small>配送の前に変更できます</small></div>
    <div class="equipment-head">${model.stations.map(s =>
      `<button data-select-station="${s.id}" class="${s.id === selectedStation ? 'selected' : ''}">${s.name}${s.opened ? '' : '（未開放）'}</button>`).join('')}</div>
    <div class="facility-detail"><img src="${model.assets.ground_station}" alt="${station.name}の地上局">
      <div><h3>${station.name}通信センター</h3>${locked
        ? `<p>依頼達成 ${model.state.successes}/${station.required}回で開放可能。</p>
           <p>必要資金 ${money(station.unlock_cost)} C</p>`
        : `<p>受信したデータを地上回線で病院へ届けます。</p>
           <div class="facility-specs"><span>計算期間内の容量 <b>${station.capacity_mbit.toFixed(1)} Mbit</b></span>
             <span>地上回線 <b>${station.delay_s.toFixed(1)} 秒</b></span></div>`}
      </div></div>
    ${locked ? `<div class="actions"><button class="primary" data-action="unlock"${disabled(
      busy || model.state.successes < station.required || model.state.credits < station.unlock_cost)}>地上局を開放 ${money(station.unlock_cost)} C</button></div>`
      : `<div class="upgrade-list">${rows.join('')}</div>`}
    ${busy ? '<p class="tip">受注中の依頼を終えると、設備を変更できます。</p>' : ''}
  </section>`;
}

function render() {
  if (!model) return;
  root.innerHTML = `<header class="center-head"><div>
    <span class="eyebrow">第${model.chapter}章　${esc(model.chapter_title)}</span><h1>通信センターの運用日誌</h1>
    </div><div class="stats"><div><b>${money(model.state.credits)} <small>C</small></b><small>運用資金</small></div>
      <div><b>${model.state.successes}<small> 回</small></b><small>依頼達成</small></div></div></header>
    <div class="goal-line">次の目標　${esc(model.next_goal)}</div>
    <div class="notice" role="status">${esc(savedNotice || args.notice || '依頼を受け、通信センターを少しずつ育てよう。')}</div>
    <div class="workspace">${contracts()}<div class="map-column">${mapScene()}${operations()}${equipment()}</div></div>
    <details><summary>運用の記録 · 配送 ${model.state.dispatches}回 / 累計到着 ${model.state.delivered}件</summary>
      ${model.state.history.length ? [...model.state.history].reverse().map(record => `<div class="history-row">
        <span>第${record.cycle + 1}便 · ${esc(model.contracts.find(c => c.id === record.contract_id)?.title)}</span>
        <span>${record.success ? '達成' : '未達'} · 期限内 ${record.on_time}/${record.total}</span>
        <b>+${record.reward} C</b></div>`).join('') : '<p>最初の依頼を終えると、記録が残ります。</p>'}
    </details>
    <footer class="save-bar"><small id="save-status">${storageOK
      ? 'このブラウザーに自動保存 · 同じURLで続きから遊べます'
      : '自動保存が使えません。セーブを書き出して保管してください。'}</small>
      <div class="save-actions"><button class="small" id="restore-backup">前のセーブに戻す</button></div>
      <small>書き出し・読み込みは下の「セーブファイル」から</small>
    </footer>
    <p class="muted"><small>資金・報酬・開放条件はゲーム用です。医療データは架空で、優先度は説明用の分類です。
      元の経路・RF計算は画面上部の「経路シミュレーション」「通信リンク」で確認できます。</small></p>
    <div id="busy" class="busy-overlay" hidden>通信センターの記録を更新しています…</div>`;
  bind(); updatePlayback();
  if (pendingId) {
    root.querySelectorAll('button[data-action]').forEach(button => {button.disabled = true;});
    document.getElementById('busy').hidden = false;
  }
  fit();
}

function bind() {
  root.querySelectorAll('[data-station],[data-select-station]').forEach(node => {
    const choose = () => {selectedStation = node.dataset.station || node.dataset.selectStation; render();};
    node.addEventListener('click', choose);
    if (node.matches('[data-station]')) node.addEventListener('keydown', event => {
      if (['Enter', ' '].includes(event.key)) {event.preventDefault(); choose();}
    });
  });
  root.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => {
    const action = button.dataset.action;
    if (action === 'dispatch') send(action, {strategy:document.getElementById('strategy').value,
      scheduler:document.getElementById('scheduler').value});
    else send(action, {contract_id:button.dataset.contract, station_id:selectedStation,
      equipment:button.dataset.equipment});
  }));
  document.getElementById('restore-backup').onclick = () => {
    if (pendingId) return;
    let text; try {text = localStorage.getItem(`${SAVE_KEY}.backup`);} catch {text = null;}
    if (!text) {savedNotice = '前のセーブはまだありません。'; render(); return;}
    if (confirm('前のセーブに戻します。現在の進行も前のセーブとして残ります。')) {
      send('import', {save:text});
    }
  };
  if (model.report) {
    document.getElementById('play').onclick = () => {
      if (clock >= model.report.end_time) clock = 0;
      playing = !playing; lastFrame = null; updatePlayback();
    };
    document.getElementById('rewind').onclick = () => {clock = 0; lastFrame = null; updatePlayback();};
    document.getElementById('speed').onclick = () => {
      const speeds = [.25, 1, 4, 16]; speed = speeds[(speeds.indexOf(speed) + 1) % speeds.length];
      document.getElementById('speed').textContent = `${speed}×`;
    };
    document.getElementById('finish').onclick = () => {
      clock = model.report.end_time; playing = false; updatePlayback(); fit();
    };
  }
}

function updatePlayback() {
  if (!model?.report) return;
  const report = model.report, ended = clock >= report.end_time;
  const play = document.getElementById('play');
  if (!play) return;
  play.textContent = playing ? '一時停止' : ended ? 'もう一度再生' : '再生';
  document.getElementById('clock').textContent = timeLabel(clock);
  document.getElementById('progress').style.width = `${clock / report.end_time * 100}%`;
  document.getElementById('result-stamp').hidden = !ended;
  document.getElementById('claim').disabled = !ended || !!pendingId;
  root.querySelectorAll('.route').forEach(path => path.classList.remove('transmitting'));
  report.results.forEach((result, i) => {
    const itemIndex = model.active.items.findIndex(item => item.id === result.id);
    const status = document.getElementById(`status-${itemIndex}`);
    status.textContent = parcelStatus(result, clock, ended);
    status.className = `parcel-status ${result.delivered && clock >= result.arrival ? 'done'
      : !result.delivered && ended ? 'failed' : ''}`;
    const point = parcelPosition(result, clock), packet = document.getElementById(`packet-${i}`);
    packet.setAttribute('visibility', point ? 'visible' : 'hidden');
    if (point) {
      packet.setAttribute('x', point.x - 16); packet.setAttribute('y', point.y - 12);
      const pathId = `${clock < result.rf_complete ? 'rf' : 'ground'}-${result.station}`;
      document.getElementById(pathId)?.classList.add('transmitting');
    }
  });
}

function tick(now) {
  if (model?.report && playing && !pendingId) {
    if (lastFrame != null) clock = advanceTime(clock, Math.min(now - lastFrame, 300), speed, model.report.end_time);
    if (clock >= model.report.end_time) {playing = false; fit();}
    updatePlayback();
  }
  lastFrame = now;
  requestAnimationFrame(tick);
}

window.addEventListener('message', event => {
  if (event.source !== parent || event.data?.type !== 'streamlit:render') return;
  args = event.data.args; model = args.model;
  if (!model) return;
  if (args.restore_requested && !restoreSent) {
    restoreSent = true;
    let save; try {save = readSave(localStorage);} catch {save = null;}
    root.innerHTML = '<p class="loading">前回の運用記録を確認しています…</p>';
    pendingId = crypto.randomUUID();
    message('streamlit:setComponentValue', {value:{id:pendingId, action:'restore', save}, dataType:'json'});
    return;
  }
  if (args.restore_requested) return;
  if (args.ack === pendingId) {pendingId = null; savedNotice = '';}
  try {storageOK = writeSave(localStorage, model.state);} catch {storageOK = false;}
  const key = model.report ? JSON.stringify([model.active, model.state.stations]) : null;
  if (key !== replayKey) {
    replayKey = key; clock = 0; lastFrame = null; speed = 1;
    playing = !!key && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
  render();
});

new ResizeObserver(fit).observe(root);
message('streamlit:componentReady', {apiVersion:1});
requestAnimationFrame(tick);
