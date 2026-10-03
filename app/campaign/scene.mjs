// Positions on the illustrated board. RF calculations use the original lat/lon.
const sites = {'gs-sapporo':[740,270],'gs-seoul':[180,300],'gs-tokyo':[715,440],
  'gs-north':[435,235],'gs-west':[400,420],'gs-south':[235,575]};
export const sceneCoords = id => sites[id];
export const satelliteX = (id, satellites) => 110 + Math.max(0,satellites.findIndex(t=>t.id===id))*155;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function campaignMap(model, selected, fixed) {
  const state=model.state, assets=model.assets;
  const links=model.preview.deliveries.filter(d=>d.arrival!==null);
  return `<section class="map"><div class="map-heading"><span>あなたの通信網</span><span>${state.satellites.length}機 / ${state.facilities.length}拠点</span></div>
    <svg viewBox="0 0 1000 720" role="img" aria-label="衛星と地上拠点の通信網の模式図">
    <image href="${assets.landscape}" width="1000" height="720" preserveAspectRatio="xMidYMid slice"/>
    <path d="M40 98Q500 -15 960 98" fill="none" stroke="#fff9df" stroke-width="2" stroke-dasharray="6 9" opacity=".8"/>
    ${links.map(d=>{const [x,y]=sceneCoords(d.station);return `<path d="M${satelliteX(d.satellite,state.satellites)} 92Q${x} 140 ${x} ${y}" stroke="#fff8d5" stroke-width="4" stroke-dasharray="6 9" opacity="${fixed?'.85':'.55'}" fill="none"/>`;}).join('')}
    ${state.satellites.map(t=>{const x=satelliteX(t.id,state.satellites);return `<g opacity="${t.active&&(!state.book.recovery||t.id===state.satellites[0].id)?'1':'.4'}"><image href="${assets.satellite}" x="${x-72}" y="15" width="${t.kind==='bulk'?150:140}" height="95"/><rect x="${x-72}" y="108" width="144" height="26" rx="8" fill="#fffcf0" opacity=".95"/><text x="${x}" y="126" text-anchor="middle" fill="#294844" font-size="13">${esc(t.id)}・${esc(model.orbits[t.orbit].name)}</text></g>`;}).join('')}
    ${model.stations.map(f=>{const [x,y]=sceneCoords(f.id), live=f.facility, width=live?112+live.antenna*8:110;return `<g class="scene-station" data-station="${f.id}" tabindex="0" role="button" aria-label="${f.name}の設備を選ぶ">
      <ellipse class="pad ${selected===f.id?'selected-pad':''}" cx="${x}" cy="${y+29}" rx="72" ry="21" fill="#fffae6" fill-opacity=".45" stroke="#eadac0"/>
      <image href="${assets.ground_station}" x="${x-width/2}" y="${y-85}" width="${width}" height="${width}" opacity="${live?(live.active?'1':'.55'):'.5'}"/>
      ${live?Array.from({length:live.receivers-1},(_,i)=>`<image href="${assets.ground_station}" x="${x+45+i*23}" y="${y-10}" width="43" height="43"/>`).join(''):''}
      ${live&&live.backhaul>1?`<rect x="${x+48}" y="${y+6-live.backhaul*5}" width="22" height="${17+live.backhaul*5}" rx="3" fill="#e8b865" stroke="#5b7358"/>`:''}
      <rect x="${x-92}" y="${y+42}" width="184" height="46" rx="9" fill="#fffcf0" stroke="${selected===f.id?'#b28029':'#d0c4a5'}" stroke-width="${selected===f.id?3:1}"/>
      <text x="${x}" y="${y+62}" text-anchor="middle" font-size="19" font-weight="bold" fill="#294844">${esc(f.name)}</text>
      <text x="${x}" y="${y+80}" text-anchor="middle" font-size="12" fill="#506251">${live?`アンテナ${live.antenna} / 回線${live.backhaul} / 受信${live.receivers}台`:'未開放・選んで確認'}</text></g>`;}).join('')}
    <g class="scene-destination"><rect x="18" y="540" width="150" height="166" rx="12" fill="#fffcf0" opacity=".93"/><image href="${assets.remote_clinic}" x="25" y="545" width="135" height="125"/><text x="93" y="690" text-anchor="middle" font-size="16" fill="#294844">遠隔地の診療所</text></g>
    <g class="scene-destination"><rect x="792" y="528" width="185" height="178" rx="12" fill="#fffcf0" opacity=".93"/><image href="${assets.hospital}" x="805" y="530" width="160" height="145"/><text x="884" y="690" text-anchor="middle" font-size="16" fill="#294844">病院への中継点</text></g>
    <g id="map-packets"></g></svg><p class="map-caption">施設を選ぶと設備を確認できます。線は配送計画の経路です。背景と配置はゲーム用の模式図です。</p></section>`;
}
