import {SAVE_KEY, readCampaign, saveCampaign, moveAllocation, assignAllocation,
  timeLabel, parcelStatus} from './storage.mjs';
import {bindParcelDrag} from './drag.mjs';
import {campaignMap, sceneCoords, satelliteX} from './scene.mjs';
import {dayFlow} from './workflow.mjs';

const root = document.getElementById('game');
const tabs = ['通信センター','依頼手帳','配送計画','衛星・設備','研究','運用記録','練習場'];
let model, args, tab = 0, selected = 'gs-sapporo', pending = null, unlockPending = null, pendingAction = null;
let restored = false, expectedSave = null, stale = false, storageOK = true, storageError = '';
let replayId = null, clock = 0, playing = false, speed = 1, lastFrame = null;
let lastHeight = null, manualGuide = null, buyKind = 'small', helpOpen = false, focusNext = false;
const openPanels = new Set();
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = n => Number(n).toLocaleString('ja-JP');
const disabled = yes => yes ? ' disabled' : '';
const button = (label, action, fields = {}, blocked = false, primary = false) =>
  `<button data-action="${action}" data-fields="${esc(JSON.stringify(fields))}"${disabled(blocked || pending || stale)} class="${primary ? 'primary' : ''}">${label}</button>`;
const s = () => model.state;
const fixed = () => !!s().report;
const claimed = () => !!s().report && s().claimed.includes(s().report.id);
const investBlocked = () => fixed() ? !claimed() : s().accepted.length > 0;
function message(type, extra = {}) {parent.postMessage({isStreamlitMessage:true,type,...extra}, '*');}
function fit() {const h = Math.ceil(root.getBoundingClientRect().height) + 5; if(h!==lastHeight){lastHeight=h;message('streamlit:setFrameHeight',{height:h});}}
function exportFile(text, name) {
  const url = URL.createObjectURL(new Blob([text],{type:'application/json'}));
  const link = document.createElement('a'); link.href=url; link.download=name; link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function send(action, fields = {}) {
  if(pending || (stale && !['restore','import','reset'].includes(action))) return;
  const run = async () => {
    try {
      if(storageOK && !['restore','reset'].includes(action) && localStorage.getItem(SAVE_KEY)!==expectedSave)
        throw new Error('別の画面で進行が変わりました。「最新の記録を読み込む」で再開してください。');
      pending = crypto.randomUUID();
      pendingAction = action;
      render();
      const completion = new Promise(resolve => {unlockPending = resolve;});
      message('streamlit:setComponentValue',{value:{id:pending,action,revision:s().revision,...fields},dataType:'json'});
      await completion;
    } catch(error) {storageError=error.message;stale=true;pending=null;render();}
  };
  if(navigator.locks) {
    try {await navigator.locks.request('medlink-leo-fleet-writer',run);}
    catch(error){storageError=`保存ロックを使えません。ファイル保存で続けます。${error.message}`;storageOK=false;await run();}
  } else {
    // No unsafe localStorage lease: unsupported browsers use explicit file saves.
    storageOK=false;storageError='このブラウザーでは自動保存の同時操作保護を使えません。セーブファイルを書き出して続けてください。';await run();
  }
}
function forecast(report = model.preview) {
  if(!s().accepted.length&&!fixed())return '<p class="empty-note">依頼を受注すると、配送の見込みと利益が表示されます。</p>';
  return `<div class="forecast"><div><small>${fixed()?'期限内に届いた荷物':'期限内に届く荷物'}</small><b>${report.on_time} / ${report.total} 件</b></div>
    <div><small>配送報酬・ボーナス</small><b>${money(report.revenue)} C</b></div><div><small>維持費・未達費用</small><b>${money(report.upkeep+report.penalty)} C</b></div>
    <div><small>差引利益</small><b class="${report.profit<0?'bad':'good'}">${report.profit>=0?'+':''}${money(report.profit)} C</b></div></div>`;
}
function workflow() {
  const next=dayFlow(s(),model.contracts,tab);
  const steps=[['依頼を選ぶ',1,`${s().accepted.length}件受注`],['配送を計画する',2,`${next.total-next.remaining} / ${next.total}件設定`],['報酬を受け取る',5,claimed()?'受領済み':fixed()?'受け取れます':'運用後に受領']];
  const cta=next.action?button(next.label,next.action,next.fields??{},false,true):`<button data-tab="${next.tab}" class="primary"${disabled(pending||stale)}>${next.label} →</button>`;
  return `<section class="workflow" aria-label="今日の進め方"><ol class="flow-steps">${steps.map(([label,destination,status],i)=>`<li class="${next.phase>i?'complete':next.phase===i?'current':''}"><button data-tab="${destination}"${next.phase===i?' aria-current="step"':''}><span class="step-number">${next.phase>i?'✓':i+1}</span><span><strong>${label}</strong><small>${status}</small></span></button></li>`).join('')}</ol>
    <div class="next-operation"><div><small>次の操作</small><h2>${next.title}</h2><p>${next.body}</p></div>${cta}</div></section>`;
}
function guide() {
  const guides = [
    ['定期便から始めよう','依頼手帳で定期便を受けます。配送計画の「自動で計画」で通信枠を割り当て、運用開始で結果を確定します。報酬は再生を待たずに受け取れます。'],
    ['送信順を変えてみよう','急ぎの便と大容量便を比べます。荷物を同じ枠へ集めると競合します。「前へ／後ろへ」で順番を変え、期限内の件数を確認しましょう。'],
    ['稼いだ資金で設備を育てよう','決算後にアンテナを強化すると送れる量が増えます。回線の強化は病院への到着を早めます。強化後は翌日の配送計画で効果を見られます。'],
    ['衛星を増やす前に','衛星・設備で軌道プランを比較します。既存の便と重なる衛星と、空白の時間を補う衛星では使い方が違います。地上局の受信枠にも注意しましょう。'],
    ['研究と継続契約','研究ポイントは契約達成で得られます。運用研究Lv.2と第3章で、3日間の継続契約を受けられます。毎日の必要な枠を残しましょう。'],
  ];
  const stage = manualGuide ?? Math.min(4, s().day <= 3 ? s().day-1 : s().chapter+1);
  const acceptedTypes = model.contracts.filter(c=>s().accepted.includes(c.id)).map(c=>c.kind);
  const steps = s().day===1 ? [
    ['定期便を受注する',acceptedTypes.includes('regular')||fixed(),1],
    ['自動計画と到着予測を確認する',s().plan.allocations.length>0,2],
    ['運用開始で結果を確定する',fixed(),2],
    ['報酬を受け取る',claimed(),5],
  ] : s().day===2 ? [
    ['期限の異なる依頼を2件受ける',s().accepted.length>=2,1],
    ['比較案1を保存し、送信順を変えて比較案2も保存する',s().comparisons.length===2,2],
    ['予測を比べて運用し、報酬を受け取る',claimed(),2],
  ] : s().day===3 ? [
    ['配送して報酬を受け取る',claimed(),1],
    ['札幌局のアンテナを強化する',s().facilities.find(f=>f.id==='gs-sapporo').antenna>1,3],
    ['翌日の通信枠で送れる量を確認する',false,2],
  ] : [];
  const next = steps.find(step=>!step[1]);
  const actions = ['受注する依頼を見る','配送計画を開く','配送計画を開く','衛星・設備を開く','研究を開く'];
  const destinations = [1,2,3,3,4];
  const nextDayGuide = manualGuide===null&&s().day===3&&claimed()&&s().facilities.find(f=>f.id==='gs-sapporo').antenna>1;
  return `<section class="guide"><header><h3>運用ガイド ${s().tutorial?`${stage+1} / 5`:''}</h3>${button(s().tutorial?'案内を閉じる':'遊び方を開く','tutorial',{open:!s().tutorial})}</header>
    ${s().tutorial?`<strong>${guides[stage][0]}</strong><p>${guides[stage][1]}</p>${manualGuide===null&&steps.length?`<ul>${steps.map(step=>`<li>${step[1]?'✓ 完了：':'○ 次の操作：'}${step[0]}</li>`).join('')}</ul>`:''}<div class="actions">${nextDayGuide?button('翌日へ進んで容量を確認する','next',{},false,true):`<button data-tab="${manualGuide===null&&next?next[2]:destinations[stage]}" class="primary">${manualGuide===null&&next?next[0]:actions[stage]} →</button>`}<button id="guide-prev"${disabled(stage===0)}>前へ</button><button id="guide-next"${disabled(stage===4)}>次へ</button><button id="guide-current">今の操作へ</button></div>`:''}</section>`;
}
function mapMarkup() {return campaignMap(model,selected,fixed());}
function facilityMarkup(id=selected) {
  const f=model.stations.find(f=>f.id===id), live=f.facility;
  const blockedNote=investBlocked()?`<p class="lock-note">${fixed()?'報酬を受け取ると設備を変更できます。':'受注中は設備を変更できません。今日の報酬を受け取った後に強化できます。'}</p>`:'';
  if(!live) return `<section class="sheet"><img class="facility-art" src="${model.assets.ground_station}" alt="${esc(f.name)}の地上局"/><h2>${esc(f.name)}の通信拠点</h2><p>新しい場所から衛星を受けられます。回線の基本遅延は${f.delay}秒です。</p><p>開放費用 ${money(f.cost)} C・第${f.chapter}章</p>${button('拠点を開く','unlock',{asset:f.id},investBlocked()||s().chapter<f.chapter||s().credits<f.cost,true)}</section>`;
  return `<section class="sheet"><img class="facility-art" src="${model.assets.ground_station}" alt="${esc(f.name)}の地上局"/><h2>${esc(f.name)}の設備</h2><p>${live.active?'稼働中':'休止中'}・受信${live.receivers}台</p>${blockedNote}
    ${['antenna','backhaul','receivers'].map((type,i)=>{const n=live[type], cost=type==='receivers'?300*n:100*n*n;
      const limit=type==='antenna'?(s().research[0]>=3?5:3):type==='backhaul'?2+s().research[1]:1+Math.min(2,s().research[0]);
      return `<h3>${['受信アンテナ','地上回線','受信設備'][i]} Lv.${n}</h3><div class="level">${'●'.repeat(n)}${'○'.repeat(Math.max(0,5-n))}</div><p>${['送れる量を増やす','病院への到着を早める','同時に受ける衛星を増やす'][i]}</p><div class="actions">${button(n>=limit?'研究で上限を開放':`強化 ${money(cost)} C`,'upgrade',{asset:id,equipment:type},investBlocked()||n>=limit||s().credits<cost||(type==='receivers'&&s().chapter<3))}</div>`;}).join('')}
    ${id!=='gs-sapporo'?button(live.active?'設備を休止する':'設備を再開する','toggle',{asset:id},investBlocked()):''}</section>`;
}
function replayMarkup() {
  if(!fixed()) return '';
  return `<section class="replay"><h3>今日の通信を見届ける</h3><div class="actions"><button id="play">${playing?'一時停止':'再生する'}</button>${[.25,1,4,16].map(n=>`<button class="mini" data-speed="${n}">${n}×</button>`).join('')}<button id="finish">最後まで</button></div>
    <input id="replay-seek" type="range" min="0" max="21600" value="${clock}" aria-label="配送再生の時刻"><small id="replay-time">${timeLabel(clock)}・再生速度は結果に影響しません</small></section>`;
}
function dayActions() {
  return `<div class="actions">${!fixed()?button('運用開始','commit',{},!s().accepted.length,true):claimed()?`${button('翌日へ進む','next',{},false,true)}<span class="good">報酬は受領済み</span>`:button('報酬を受け取る','claim',{settlement:s().report.id},false,true)}</div>`;
}
function center() {
  const f=model.stations.find(f=>f.id===selected), live=f.facility;
  return `<div class="layout scene-layout"><div>${mapMarkup()}<section class="facility-overview"><img src="${model.assets.ground_station}" alt=""><div><h3>${esc(f.name)}の通信拠点</h3><p>${live?`${live.active?'稼働中':'休止中'}・アンテナLv.${live.antenna}・回線Lv.${live.backhaul}`:`第${f.chapter}章で開放・${money(f.cost)} C`}</p></div><button data-tab="3">設備を見る →</button></section>${forecast()}${replayMarkup()}</div><aside class="side"><section class="sheet"><h2>今日の運用条件</h2><strong>${esc(s().book.event_title)}</strong><p>${esc(s().book.event_body)}</p>${s().book.recovery?'<p class="bad">復旧モード：基本衛星と札幌局で再開します。100 C以上で通常運営へ戻れます。追加設備は設備画面から再開できます。</p>':''}<p>維持費 ${s().book.upkeep} C / 日</p></section><section class="sheet"><h2>練習してみる</h2><p>${esc(model.daily_challenge.title)}</p><p class="muted">${esc(model.daily_challenge.body)}</p>${button("練習場を開く","exercise",{exercise:model.daily_challenge.id})}</section></aside></div>`;
}
function offers() {
  return `<section class="sheet"><div class="section-head"><h2>今日の依頼手帳</h2><span>受注 ${s().accepted.length} / ${3+s().research[2]}件</span></div><p class="muted">受ける依頼を組み合わせます。未達費用と必要な期限内件数を確認してください。</p>${forecast()}
    <div class="offers">${model.contracts.map(c=>{const accepted=s().accepted.includes(c.id), ongoing=s().ongoing.some(o=>o.id===c.id);return `<article class="offer ${accepted?'accepted':''}"><header><img class="offer-parcel" src="${model.assets.parcel}" alt=""/><h3>${esc(c.title)}</h3><span class="tag">${c.days_left>1?`${c.days_left}日契約`:accepted?'受注中':'今日の依頼'}</span></header>
      ${c.kind==='regular'?'<span class="beginner-tag">はじめて向け</span>':''}<div class="offer-facts"><div><small>配送期限</small><strong>${timeLabel(Math.min(...c.parcels.map(p=>p.due)))}</strong></div><div><small>全件成功時の報酬</small><strong>${money(c.parcels.length*c.payment+c.bonus)} C</strong></div></div><p>荷物 ${c.parcels.length}件 / 合計 ${(c.parcels.reduce((n,p)=>n+p.size_bytes,0)/1e6).toFixed(2)} MB<br>達成条件：${c.target}件を期限内に届ける</p><details class="offer-terms"><summary>報酬の内訳・未達時の費用</summary><p>期限内1件 ${c.payment} C＋達成 ${c.bonus} C<br>未達費用 ${c.penalty} C</p></details>
      ${c.lock?`<p class="muted">${esc(c.lock)}</p>`:''}${ongoing?'<p>継続中：今日の決算まで続きます。</p>':button(accepted?'受注を取り消す':'受注する',accepted?'cancel':'accept',{contract:c.id},fixed()||(!accepted&&(!!c.lock||s().accepted.length>=3+s().research[2])),!accepted&&!c.lock)}</article>`;}).join('')}</div>${fixed()?dayActions():`<button data-tab="2" class="primary"${disabled(!s().accepted.length)}>配送計画を作る →</button>`}</section>`;
}
function timeline() {
  const lanes = [...new Set(model.contacts.map(c=>`${c.satellite}|${c.station}`))];
  return `<div class="timeline"><div class="axis">${[0,1,2,3,4,5,6].map(n=>`<span style="left:${n/6*100}%">${String(6+n).padStart(2,'0')}:00</span>`).join('')}</div>
    ${lanes.map(key=>{const [sat,gs]=key.split('|');return `<div class="lane"><strong>${esc(sat)} / ${esc(model.stations.find(f=>f.id===gs).name)}</strong>${model.contacts.filter(c=>c.satellite===sat&&c.station===gs).map(c=>`<button class="contact-slot" data-contact="${esc(c.id)}" style="left:${c.start/21600*100}%;width:${(c.end-c.start)/21600*100}%" title="${esc(c.name)} ${timeLabel(c.start)}〜${timeLabel(c.end)}・${c.capacity_mb.toFixed(2)} MB / 最大空き${c.remaining_mb.toFixed(2)} MB" aria-label="${esc(c.name)} ${timeLabel(c.start)}からの枠・${c.capacity_mb.toFixed(2)} MB・最大空き${c.remaining_mb.toFixed(2)} MB"${disabled(fixed()||pending||stale)}></button>`).join('')}
      ${model.preview.deliveries.filter(d=>d.satellite===sat&&d.station===gs&&d.departure!==null).map(d=>`<span class="transfers" style="left:${d.departure/21600*100}%;width:${Math.max(.25,(d.completion-d.departure)/21600*100)}%"></span>`).join('')}</div>`;}).join('')}
    <p class="timeline-tip">緑は通信できる時間、黄は予定した送信です。荷物を枠へドラッグするか、下の選択欄を使います。枠を押すと先頭の未割り当て荷物を入れます。空きは、現在の計画後に残る最も大きな連続枠です。荷物の生成時刻や期限によっては使えません。</p></div>`;
}
function planning() {
  const items=model.contracts.filter(c=>s().accepted.includes(c.id)).flatMap(c=>c.parcels.map(p=>({...p,title:c.title})));
  const ordered=[...s().plan.allocations.map(a=>items.find(p=>p.id===a.parcel)),...items.filter(p=>!s().plan.allocations.some(a=>a.parcel===p.id))].filter(Boolean);
  const results=new Map(model.preview.deliveries.map(d=>[d.parcel,d]));
  return `<section class="sheet"><div class="section-head"><h2>配送計画</h2>${button('自動で計画','auto',{},fixed()||!items.length)}</div><p class="muted">まず自動で計画し、到着の予測を確認します。通信枠や送信順は表で調整できます。</p>${forecast()}<details class="advanced"><summary>通信できる時間を見る・ドラッグで割り当てる</summary>${timeline()}</details>
    <div class="table-scroll"><table class="ledger"><thead><tr><th>荷物／生成時刻</th><th>容量／期限</th><th>割り当てる通信枠</th><th>予測と理由</th><th>送信順</th></tr></thead><tbody>
    ${ordered.map(p=>{const d=results.get(p.id), a=s().plan.allocations.find(a=>a.parcel===p.id);return `<tr class="parcel" data-parcel="${p.id}" draggable="${!fixed()&&!pending&&!stale}"><td><span class="drag-handle" title="ここをつかんで荷物を移動" aria-hidden="true">⠿</span>${esc(p.title)}<br><small>${esc(p.id)}・${timeLabel(p.created)}</small></td><td>${(p.size_bytes/1e6).toFixed(2)} MB<br>${timeLabel(p.due)}</td>
      <td><select data-assign="${p.id}" aria-label="${esc(p.id)}の通信枠"${disabled(fixed()||pending||stale)}><option value="">未割り当て</option>${model.contacts.map(c=>`<option value="${esc(c.id)}"${a?.contact===c.id?' selected':''}>${esc(c.satellite)} / ${esc(c.name)} ${timeLabel(c.start)} (${c.capacity_mb.toFixed(1)} MB / 空き${c.remaining_mb.toFixed(1)})</option>`).join('')}</select>${a?`<small>枠の最大空き ${model.contacts.find(c=>c.id===a.contact).remaining_mb.toFixed(2)} MB</small>`:''}</td>
      <td class="${d?.on_time?'good':'bad'}">${timeLabel(d?.arrival)}<br><small data-status="${p.id}">${esc(d?.reason)}</small>${d?.arrival!==null&&d?.arrival!==undefined?`<br><small>期限まで ${Math.round(p.due-d.arrival)}秒</small>`:''}</td><td><button class="mini" data-move="${p.id}" data-step="-1"${disabled(fixed()||!a||pending||stale)}>前へ</button> <button class="mini" data-move="${p.id}" data-step="1"${disabled(fixed()||!a||pending||stale)}>後ろへ</button></td></tr>`;}).join('')}</tbody></table></div>
    ${!items.length?'<p>依頼手帳で受注すると荷物が表示されます。</p>':'<p class="muted">左の⠿をつかんで移動します。行の上半分はその前、下半分はその後へ入ります。挿入位置に金色の線が出ます。通信枠を変更しても送信順は保ちます。</p>'}
    <details class="advanced"><summary>2つの計画を保存して比べる</summary><div class="actions">${[0,1].map(i=>`${button(`案${i+1}を保存`,'compare_save',{slot:i},fixed()||!items.length)}${button(`案${i+1}を使う`,'compare_load',{slot:i},fixed()||!s().comparisons[i])}`).join('')}</div>
    ${model.comparisons.map((r,i)=>`<p>案${i+1}：期限内${r.on_time}/${r.total}件・利益${money(r.profit)} C</p>`).join('')}</details>${dayActions()}${replayMarkup()}</section>`;
}
function fleet() {
  return `<section class="sheet"><h2>衛星を育てる</h2><p class="muted">設備を変更できるのは受注前と決算後です。維持費と通信時間の重なりを比べましょう。</p>
    ${s().satellites.map((sat,i)=>`<div class="fleet-row"><img src="${model.assets.satellite}" alt="${esc(model.types[sat.kind].name)}"><div><h3>${esc(sat.id)}・${esc(model.types[sat.kind].name)}</h3><p>${esc(model.orbits[sat.orbit].name)} / ${sat.active?'稼働中':'休止中'} / 日額${model.types[sat.kind].upkeep} C</p></div><div class="actions">${i?`${button(sat.active?'休止':'再開','toggle',{asset:sat.id},investBlocked())}${button(`売却 ${model.types[sat.kind].cost*.6} C`,'sell',{asset:sat.id},investBlocked())}`:'<small>基本衛星</small>'}</div></div>`).join('')}
    <h3 style="margin-top:20px">新しい衛星を購入</h3><div class="buy-form"><label>機種<select id="buy-kind">${Object.entries(model.types).map(([key,t])=>`<option value="${key}"${key===buyKind?' selected':''}>${esc(t.name)} ${money(t.cost)} C / 日額${t.upkeep} C</option>`).join('')}</select></label><label>軌道プラン<select id="buy-orbit">${Object.entries(model.orbits).map(([key,o])=>`<option value="${key}">${esc(o.name)}</option>`).join('')}</select></label><button id="buy" class="primary"${disabled(investBlocked()||s().chapter<2||s().satellites.length>=6||pending||stale)}>衛星を購入</button></div>
    <p class="muted">小型衛星は第2章、全機種は第4章で開放します。最大6機。比較値は選択中の機種と今日の条件で計算します。受信設備の競合を含める前の合計容量です。</p><div class="orbit-grid">${model.orbit_comparisons.filter(o=>o.kind===buyKind).map(o=>`<div class="orbit-choice"><strong>${esc(model.orbits[o.id].name)}</strong><p>${esc(model.orbits[o.id].description)}<br>通信機会 ${o.windows}回 / 合計${o.capacity_mb.toFixed(1)} MB<br>既存の時間と重複 ${(o.overlap*100).toFixed(0)}%</p><small>高度${model.orbits[o.id].altitude_km} km・傾斜角${model.orbits[o.id].inclination}°（ゲーム設定）</small></div>`).join('')}</div></section>
    <section class="sheet"><h2>地上拠点</h2><div class="actions">${model.stations.map(f=>`<button data-station="${f.id}">${esc(f.name)} ${f.facility?'✓':`第${f.chapter}章`}</button>`).join('')}</div>${facilityMarkup()}</section>`;
}
function research() {
  return `<section class="sheet"><h2>研究</h2><p>契約達成1件で3ポイント。現在 ${s().points}ポイントです。</p><div class="research-grid">${Object.entries(model.research).map(([key,branch],i)=>`<section><h3>${esc(branch.name)}</h3>${branch.effects.map((effect,level)=>`<div class="research-node ${s().research[i]>level?'done':''}"><strong>Lv.${level+1} ${esc(effect)}</strong><p>${80*(level+1)} C・${3*(level+1)}ポイント</p>${s().research[i]>level?'<span class="good">研究済み</span>':button('研究する','research',{branch:key},investBlocked()||s().research[i]!==level||s().points<3*(level+1)||s().credits<80*(level+1))}</div>`).join('')}</section>`).join('')}</div></section>`;
}
function records() {
  const r=model.preview;
  return `<section class="sheet"><h2>${fixed()?'今日の決算':'今日の決算見込み'}</h2>${forecast()}<p>信用 ${r.credit_change>=0?'+':''}${r.credit_change} / 研究ポイント +${r.research_points}</p>
    <div class="table-scroll"><table class="ledger summary"><thead><tr><th>依頼</th><th>期限内／総数</th><th>報酬</th><th>ボーナス</th><th>未達費用</th></tr></thead><tbody>${r.contracts.map(c=>`<tr><td>${esc(c.title)}<br><small>${c.success?'達成':'未達'}</small></td><td>${c.on_time}/${c.total}</td><td>${c.payment} C</td><td>${c.bonus} C</td><td>${c.penalty} C</td></tr>`).join('')}</tbody></table></div>${dayActions()}
    <details><summary>配送結果と計算の記録</summary><div class="table-scroll"><table class="ledger"><thead><tr><th>荷物</th><th>衛星／地上局</th><th>開始 → 到着</th><th>結果</th></tr></thead><tbody>${r.deliveries.map(d=>`<tr><td>${esc(d.parcel)}</td><td>${esc(d.satellite??'—')} / ${esc(model.stations.find(f=>f.id===d.station)?.name??'—')}</td><td>${timeLabel(d.departure)} → ${timeLabel(d.arrival)}</td><td>${esc(d.reason)}</td></tr>`).join('')}</tbody></table></div><p>計算元：${esc(r.source)}。荷物は選択した衛星へ搭載済みとして扱います。</p></details></section>
    <section class="sheet"><h2>これまでの運用</h2><p>契約達成 ${s().successes}件・配送 ${s().delivered}件・期限内 ${s().on_time}件</p><div class="table-scroll"><table class="ledger summary"><thead><tr><th>営業日</th><th>期限内／総数</th><th>利益</th></tr></thead><tbody>${[...s().history].reverse().map(h=>`<tr><td>${h.day}日目</td><td>${h.on_time}/${h.total}</td><td>${h.profit>=0?'+':''}${money(h.profit)} C</td></tr>`).join('')}</tbody></table></div></section>`;
}
function practice() {
  const caseModel = args.exercise;
  return `<section class="sheet"><h2>練習場</h2><p>各章に3つの固定課題があります。計画を変えて結果を比べられます。本番の資金・設備・依頼には影響しません。</p>
    <div class="actions">${model.exercises.map(c=>button(`第${c.chapter}章：${esc(c.title)}`,'exercise',{exercise:c.id},c.chapter>s().chapter)).join('')}</div>
    ${caseModel?`<h3>${esc(caseModel.title)}</h3><p>${esc(caseModel.body)}</p><div class="forecast"><div><small>期限内到着</small><b>${caseModel.on_time} / ${caseModel.total}件</b></div><div><small>練習スコア</small><b>${caseModel.score}点</b></div></div><p class="muted">期限内の大きな荷物は120点、小さな荷物は60点で比較します。資金への加算はありません。</p>
      <div class="actions">${[0,1].map(i=>button(`比較案${i+1}を使う`,'exercise_example',{exercise:caseModel.id,example:i})).join('')}</div>
      <div class="table-scroll"><table class="ledger"><thead><tr><th>荷物・生成時刻</th><th>量・期限</th><th>通信枠</th><th>到着・理由</th><th>順番</th></tr></thead><tbody>
      ${[...caseModel.plan.allocations.map(a=>caseModel.parcels.find(p=>p.id===a.parcel)),...caseModel.parcels.filter(p=>!caseModel.plan.allocations.some(a=>a.parcel===p.id))].filter(Boolean).map(p=>{const a=caseModel.plan.allocations.find(a=>a.parcel===p.id),d=caseModel.deliveries.find(d=>d.parcel===p.id);return `<tr><td>${esc(p.id)}<br>${timeLabel(p.created)}</td><td>${(p.size_bytes/1e6).toFixed(2)} MB<br>${timeLabel(p.due)}</td><td><select data-exercise-assign="${esc(p.id)}" aria-label="練習 ${esc(p.id)}の通信枠"${disabled(pending||stale)}><option value="">未割り当て</option>${caseModel.contacts.map(c=>`<option value="${esc(c.id)}"${a?.contact===c.id?' selected':''}>${esc(c.satellite)} / ${esc(model.stations.find(f=>f.id===c.station)?.name??c.station)} ${timeLabel(c.start)} (${c.capacity_mb.toFixed(1)} MB)</option>`).join('')}</select></td><td class="${d.on_time?'good':'bad'}">${timeLabel(d.arrival)}<br>${esc(d.reason)}</td><td><button class="mini" data-exercise-move="${esc(p.id)}" data-step="-1"${disabled(!a||pending||stale)}>前へ</button><button class="mini" data-exercise-move="${esc(p.id)}" data-step="1"${disabled(!a||pending||stale)}>後ろへ</button></td></tr>`;}).join('')}</tbody></table></div>`:'<p>課題を選んでください。章が進むと新しい課題を開けます。</p>'}</section>`;
}
function render() {
  if(!model)return;
  root.dataset.revision = s().revision;
  root.dataset.ack = args.ack ?? '';
  root.innerHTML=`${pending?'<div class="busy" role="status">記録しています…</div>':''}<header class="masthead"><div><small class="eyebrow">MEDLINK 通信センター</small><h1>${s().chapter===5?'':`第${s().chapter}章 `}${esc(model.title)}</h1></div><div class="stats"><div><small>営業日</small><b>${s().day}日目</b></div><div><small>運用資金</small><b>${money(s().credits)} C</b></div><div><small>信用</small><b>${s().credit}</b></div><div><small>研究ポイント</small><b>${s().points}</b></div></div></header>
    ${args.notice||storageError?`<div class="${storageError||args.error?'notice':'save-notice'}" role="status">${esc(storageError||args.notice)}</div>`:''}${stale?'<div class="notice">記録を保護するため編集を止めています。<button id="stale-reload">最新の記録を読み込む</button></div>':''}
    ${workflow()}<nav class="nav" aria-label="ゲーム画面">${tabs.map((label,i)=>`<button data-tab="${i}" class="${tab===i?'selected':''}" aria-current="${tab===i?'page':'false'}">${i===1?'依頼':i===3?'設備':i===5?'結果・記録':label}</button>`).join('')}</nav>
    <details class="help-panel"${helpOpen?' open':''}><summary>遊び方・操作ガイド</summary>${guide()}<p>Cはゲーム内の通貨です。運用後の「差引利益」が資金に加わります。</p></details>
    <div id="screen-content">${[center,offers,planning,fleet,research,records,practice][tab]()}</div>
    <details class="chapter-panel"><summary>章の目標 ${model.goals.filter(([,v,g])=>v>=g).length} / ${model.goals.length}達成</summary><div class="goals">${model.goals.map(([name,value,goal])=>`<span class="goal ${value>=goal?'done':''}">${esc(name)} ${value} / ${goal}</span>`).join('')}${s().chapter<5?button('次の章へ','chapter',{},model.goals.some(([,v,g])=>v<g)):''}</div><p>すべての目標を達成すると次の章へ進めます。</p></details>
    <footer class="foot">${storageOK?'<span>✓ このブラウザーに自動保存</span>':'<p class="bad">自動保存を使えません。閉じる前にセーブをファイルへ保管してください。</p>'}
    <details class="save-panel"${args.pending_import||stale||!storageOK?' open':''}><summary>セーブの保管・復元</summary><div class="storage-controls"><button id="export">セーブをファイルに保管</button><button id="reload-save">最新の記録を読み込む</button><button id="backup">前のセーブへ戻す</button>${args.pending_import?'<button id="import-save" class="primary">読み込みを確定</button>':''}${stale?'<button id="raw-save">保護した記録を書き出す</button>':''}</div></details><p class="simulation-note">架空の医療データを使ったゲームです。診断・治療には使えません。衛星間中継・診療所からの送信は省略しています。架空の円軌道モデルによる模式図で、過去TLEの解析とは異なります。</p></footer>`;
  root.querySelectorAll('details').forEach(el=>{
    if(el.classList.contains('help-panel')||el.classList.contains('save-panel'))return;
    const key=`${tab}:${el.querySelector('summary')?.textContent}`;
    el.open=openPanels.has(key);
    el.ontoggle=()=>{if(el.open)openPanels.add(key);else openPanels.delete(key);};
  });
  bind();paintReplay();requestAnimationFrame(()=>{
    fit();
    if(focusNext){
      focusNext=false;
      requestAnimationFrame(()=>{
        // Scroll the Streamlit page as well as the component document.
        (window.frameElement??root).scrollIntoView({block:'start'});
      });
    }
  });
}
function bind() {
  root.querySelectorAll('[data-tab]').forEach(el=>el.onclick=()=>{tab=Number(el.dataset.tab);focusNext=true;render();root.querySelector('.nav .selected')?.focus({preventScroll:true});});
  root.querySelectorAll('[data-action]').forEach(el=>el.onclick=()=>{if(el.dataset.action==='exercise')tab=6;send(el.dataset.action,JSON.parse(el.dataset.fields));});
  root.querySelectorAll('[data-exercise-assign]').forEach(el=>el.onchange=()=>send('exercise_plan',{exercise:args.exercise.id,allocations:assignAllocation(args.exercise.plan.allocations,el.dataset.exerciseAssign,el.value)}));
  root.querySelectorAll('[data-exercise-move]').forEach(el=>el.onclick=()=>send('exercise_plan',{exercise:args.exercise.id,allocations:moveAllocation(args.exercise.plan.allocations,el.dataset.exerciseMove,Number(el.dataset.step))}));
  root.querySelectorAll('[data-station]').forEach(el=>{el.onclick=()=>{selected=el.dataset.station;render();};el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();el.click();}};});
  root.querySelectorAll('[data-assign]').forEach(el=>el.onchange=()=>send('plan',{allocations:assignAllocation(s().plan.allocations,el.dataset.assign,el.value)}));
  root.querySelectorAll('[data-move]').forEach(el=>el.onclick=()=>send('plan',{allocations:moveAllocation(s().plan.allocations,el.dataset.move,Number(el.dataset.step))}));
  bindParcelDrag(root,{getPlan:()=>s().plan.allocations,getRevision:()=>s().revision,
    canEdit:()=>!pending&&!stale&&!fixed(),onPlan:allocations=>send('plan',{allocations})});
  root.querySelectorAll('[data-contact]').forEach(el=>{el.onclick=()=>{const items=model.contracts.filter(c=>s().accepted.includes(c.id)).flatMap(c=>c.parcels);const p=items.find(p=>!s().plan.allocations.some(a=>a.parcel===p.id));if(p)send('plan',{allocations:assignAllocation(s().plan.allocations,p.id,el.dataset.contact)});};});
  const click=(id,fn)=>{const el=document.getElementById(id);if(el)el.onclick=fn;};
  const help=root.querySelector('.help-panel');if(help)help.ontoggle=()=>{helpOpen=help.open;fit();};
  const kindSelect=document.getElementById('buy-kind');if(kindSelect)kindSelect.onchange=()=>{buyKind=kindSelect.value;render();};
  click('buy',()=>send('buy',{kind:document.getElementById('buy-kind').value,orbit:document.getElementById('buy-orbit').value}));
  click('export',()=>exportFile(JSON.stringify(s()),'medlink-campaign-v2.json'));
  click('reload-save',()=>{try{expectedSave=localStorage.getItem(SAVE_KEY);stale=false;storageError='';send('restore',{save:readCampaign(localStorage)});}catch(error){storageError=error.message;render();}});
  click('stale-reload',()=>document.getElementById('reload-save').click());
  click('backup',()=>{try{const save=localStorage.getItem(`${SAVE_KEY}.backup`);if(save)send('import',{save});else{storageError='前のセーブがありません。';render();}}catch(error){storageError=error.message;render();}});
  click('raw-save',()=>{try{exportFile(readCampaign(localStorage)??'{}','medlink-protected-save.json');}catch(error){storageError=error.message;render();}});
  click('import-save',()=>send('import',{save:args.pending_import}));
  click('guide-prev',()=>{manualGuide=Math.max(0,(manualGuide??Math.min(4,s().day-1))-1);render();});
  click('guide-next',()=>{manualGuide=Math.min(4,(manualGuide??Math.min(4,s().day-1))+1);render();});
  click('guide-current',()=>{manualGuide=null;render();});
  click('play',()=>{playing=!playing;lastFrame=null;render();});click('finish',()=>{clock=21600;playing=false;render();});
  root.querySelectorAll('[data-speed]').forEach(el=>el.onclick=()=>{speed=Number(el.dataset.speed);playing=true;lastFrame=null;});
  const seek=document.getElementById('replay-seek');if(seek)seek.oninput=()=>{clock=Number(seek.value);paintReplay();};
}
function paintReplay() {
  if(!model||!fixed())return;
  const seek=document.getElementById('replay-seek');if(seek)seek.value=clock;
  const label=document.getElementById('replay-time');if(label)label.textContent=`${timeLabel(clock)}・再生速度は結果に影響しません`;
  for(const d of s().report.deliveries){const el=root.querySelector(`[data-status="${CSS.escape(d.parcel)}"]`);if(el)el.textContent=parcelStatus(d,clock);}
  const packets=document.getElementById('map-packets');if(!packets)return;
  packets.innerHTML=s().report.deliveries.filter(d=>d.departure!==null&&clock>=d.departure&&clock<d.arrival).map(d=>{
    const [stationX,sy]=sceneCoords(d.station), sx=satelliteX(d.satellite,s().satellites);
    let x,y;if(clock<d.completion){const p=(clock-d.departure)/(d.completion-d.departure);x=sx+(stationX-sx)*p;y=93+(sy-93)*p;}else{const p=(clock-d.completion)/(d.arrival-d.completion);x=stationX+(884-stationX)*p;y=sy+(610-sy)*p;}
    return `<image href="${model.assets.parcel}" x="${x-14}" y="${y-12}" width="28" height="24"/>`;
  }).join('');
}
window.addEventListener('storage',e=>{if(e.key===SAVE_KEY&&!pending&&e.newValue!==expectedSave){stale=true;storageError='別の画面で記録が更新されました。最新の記録を読み込んでください。';render();}});
window.addEventListener('message',async event=>{
  if(event.source!==parent||event.data.type!=='streamlit:render')return;
  args=event.data.args;model=args.model;
  if(pending&&args.ack===pending){
    focusNext=['accept','cancel','auto','commit','claim','next','chapter'].includes(pendingAction);
    pendingAction=null;
    if(args.error){storageError=args.notice;if(args.restore_error)stale=true;}
    else if(storageOK){try{expectedSave=saveCampaign(localStorage,s(),expectedSave);storageError='';}catch(error){storageError=error.message;storageOK=false;}}
    const resolve=unlockPending;pending=null;unlockPending=null;if(resolve)resolve();
  }
  // A dropped Streamlit session can start again while this iframe stays alive.
  // Finish the old acknowledgement, then restore before accepting more edits.
  if(!args.restore_requested)restored=false;
  if(!restored&&args.restore_requested&&!pending){restored=true;let save=null;try{save=readCampaign(localStorage);expectedSave=localStorage.getItem(SAVE_KEY);}catch{storageOK=false;}await send('restore',{save});return;}
  const id=s().report?.id??null;if(id!==replayId){replayId=id;clock=0;playing=!!id&&!matchMedia('(prefers-reduced-motion:reduce)').matches;lastFrame=null;}
  render();
});
function frame(now){if(playing&&fixed()){if(lastFrame!==null)clock=Math.min(21600,clock+(now-lastFrame)/1000*21600/36*speed);if(clock>=21600)playing=false;paintReplay();}lastFrame=now;requestAnimationFrame(frame);}
message('streamlit:componentReady',{apiVersion:1});requestAnimationFrame(frame);
new ResizeObserver(fit).observe(root);
