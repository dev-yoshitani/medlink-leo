// Describe the next deliberate operation without modifying the saved game.
export function dayFlow(state, contracts, tab = 0) {
  const parcels = contracts.filter(c => state.accepted.includes(c.id)).flatMap(c => c.parcels);
  const assigned = new Set(state.plan.allocations.map(a => a.parcel));
  const remaining = parcels.filter(p => !assigned.has(p.id)).length;
  const base = {total: parcels.length, remaining};
  if (state.report) {
    if (state.claimed.includes(state.report.id))
      return {...base, phase: 3, title: '今日の運用は完了しました',
        body: '設備の強化や研究を済ませたら、翌日へ進みましょう。', label: '翌日へ進む', action: 'next'};
    return {...base, phase: 2, title: '報酬を受け取れます',
      body: '結果は確定しています。配送の再生を待つ必要はありません。', label: '報酬を受け取る', action: 'claim', fields: {settlement: state.report.id}};
  }
  if (!state.accepted.length)
    return {...base, phase: 0, title: 'まずは今日の依頼を選びましょう',
      body: '「定期便」は始めやすい依頼です。期限と報酬を見て受注します。', label: '依頼を選ぶ', tab: 1};
  if (remaining || !parcels.length)
    return {...base, phase: 1, title: `荷物${remaining}件の通信枠が未設定です`,
      body: '「自動で計画」で通信枠を割り当て、到着予測を確認しましょう。',
      label: tab === 2 ? '自動で計画' : '配送計画を作る', ...(tab === 2 ? {action: 'auto'} : {tab: 2})};
  return {...base, phase: 1, title: '計画を確認して運用しましょう',
    body: '「期限内に届く荷物」と「差引利益」を確認します。運用すると今日の計画が確定します。',
    label: tab === 2 ? 'この計画で運用する' : '計画を確認する', ...(tab === 2 ? {action: 'commit'} : {tab: 2})};
}
