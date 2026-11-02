"""비공개 원본 → 공개용 CSV 전처리 스크립트

이 스크립트는 비공개 보관 중인 원본(data/raw/)이 있어야 실행됩니다.
공개 저장소에는 결과물(data/processed/)만 포함되며, 공개 분석 노트북(analysis.ipynb)은
data/processed/ 파일만으로 실행됩니다.

원본: YouTube Studio 분석 → 고급 모드 → CSV 내보내기(본인 채널, 2026-11-02 추출)
조회수는 모두 '유효 조회수' 열을 사용합니다.
"""
import pandas as pd

RAW, OUT = 'data/raw', 'data/processed'
START, END = '2019-01-13', '2021-12-31'
SPIKE = ('2019-03-09', '2019-03-22')


def hms(s):
    h, m, sec = map(int, str(s).split(':'))
    return h * 3600 + m * 60 + sec


def band(s):
    for lim, lab in [(60, '1분 미만'), (120, '1–2분'), (300, '2–5분'), (600, '5–10분'),
                     (1200, '10–20분'), (1800, '20–30분'), (2400, '30–40분')]:
        if s < lim:
            return lab
    return '40분 이상'


# ---------- 영상별 (비공개 매핑으로 코드 부여) ----------
MAP = pd.read_csv(f'{RAW}/video_map.csv').set_index('content_id')
v = pd.read_csv(f'{RAW}/videos_2019_2021.csv')
total = v[v['콘텐츠'] == '합계'].iloc[0]
assert (v['유효 조회수'] == v['조회수']).all()
v = v[v['콘텐츠'] != '합계'].copy()
v = v.assign(content_id=v['콘텐츠'].str.strip()).join(MAP, on='content_id')
v = v.rename(columns={'길이': 'length_s', '유효 조회수': 'views', '시청 시간(단위: 시간)': 'watch_h',
                      '구독자': 'subs', '썸네일 노출수': 'impr', '썸네일 클릭률 (%)': 'ctr',
                      '평균 조회율 (%)': 'pct_viewed'})
v['avg_view_s'] = v['평균 시청 지속 시간'].map(hms)
v['published'] = pd.to_datetime(v['동영상 게시 시간'], format='%b %d, %Y')

pub = pd.DataFrame({
    'code': v.code, 'type': v.type.replace({'콘셉트 숏폼(영상통화 형식)': '콘셉트 영상(영상통화 형식)'}), 'status': v.status,
    'year': v.published.dt.year, 'length_band': v.length_s.map(band),
    'impr': (v.impr / 100).round().astype(int) * 100,
    'ctr': v.ctr.round(1),
    'views': (v.views / 10).round().astype(int) * 10,
    'avg_view_s': (v.avg_view_s / 10).round().astype(int) * 10,
    'pct_viewed': v.pct_viewed.round().astype(int),
    'watch_h': v.watch_h.round().astype(int),
    'subs': v.subs,
    'length_rank': v.length_s.rank(ascending=False).astype(int),
}).sort_values('length_rank')
pub.to_csv(f'{OUT}/videos_2019_2021_public.csv', index=False)

# ---------- 채널 합계 ----------
life = pd.read_csv(f'{RAW}/videos_lifetime.csv').iloc[0]
daily = pd.read_csv(f'{RAW}/channel_daily_views_lifetime.csv', parse_dates=['날짜'])
daily.columns = ['date', 'views']
daily = daily.set_index('date').sort_index()['views']
pd.DataFrame([
    ('views_2019_2021', int(total['유효 조회수']), '분석 기간 채널 유효 조회수'),
    ('watch_h_2019_2021', float(total['시청 시간(단위: 시간)']), '분석 기간 채널 시청 시간(시간)'),
    ('impr_2019_2021', int(total['썸네일 노출수']), '분석 기간 채널 썸네일 노출수'),
    ('ctr_2019_2021', float(total['썸네일 클릭률 (%)']), '분석 기간 채널 썸네일 클릭률(%)'),
    ('subs_2019_2021', int(total['구독자']), '분석 기간 채널 구독 순증가'),
    ('views_lifetime_effective', int(life['유효 조회수']), '전체 기간(2019-01-13~2026-11-01 표) 유효 조회수'),
    ('views_lifetime_plain', int(life['조회수']), '전체 기간 표의 일반 조회수 (참고)'),
    ('views_lifetime_daily_sum', int(daily.sum()), '채널 일별 유효 조회수 합계(~2026-10-31)'),
], columns=['key', 'value', 'description'], dtype=object).to_csv(f'{OUT}/channel_totals.csv', index=False)
daily[START:END].rename('views').to_csv(f'{OUT}/channel_daily_views_2019_2021.csv', index_label='date')

# ---------- 집계 범위 점검 ----------
ch = dict(views=int(total['유효 조회수']), watch_h=float(total['시청 시간(단위: 시간)']),
          impr=int(total['썸네일 노출수']), subs=int(total['구독자']))
ex = dict(views=int(v.views.sum()), watch_h=round(float(v.watch_h.sum()), 4), impr=int(v.impr.sum()), subs=int(v.subs.sum()))
pd.DataFrame([
    ('유효 조회수', ch['views'], ex['views'], ch['views'] - ex['views'], '현존 목록 밖 성과(잔여분)'),
    ('시청 시간(시간)', ch['watch_h'], ex['watch_h'], round(ch['watch_h'] - ex['watch_h'], 4), '현존 목록 밖 성과(잔여분)'),
    ('썸네일 노출수', ch['impr'], ex['impr'], ch['impr'] - ex['impr'], '현존 목록 밖 성과(잔여분)'),
    ('구독 순증가', ch['subs'], ex['subs'], ch['subs'] - ex['subs'], '집계 범위 차이 — 특정 영상에 귀속하지 않음'),
], columns=['metric', 'channel_total', 'existing_videos_sum', 'difference', 'interpretation'], dtype=object
).to_csv(f'{OUT}/aggregation_check.csv', index=False)

# ---------- 유입 경로 ----------
ts = pd.read_csv(f'{RAW}/traffic_2019_2021.csv')
assert (ts['유효 조회수'] == ts['조회수']).all()
ts = ts.rename(columns={'트래픽 소스': 'source', '유효 조회수': 'views', '평균 조회율 (%)': 'pct_viewed',
                        '시청 시간(단위: 시간)': 'watch_h', '썸네일 노출수': 'impr', '썸네일 클릭률 (%)': 'ctr'})
ts['avg_view_s'] = ts['평균 시청 지속 시간'].map(hms)
ts[['source', 'impr', 'ctr', 'views', 'avg_view_s', 'pct_viewed', 'watch_h']].to_csv(f'{OUT}/traffic_sources_2019_2021.csv', index=False)

t = pd.read_csv(f'{RAW}/traffic_daily_2019_2021.csv', parse_dates=['날짜'])
t.columns = ['date', 'source', 'views']
t = t[(t.date >= START) & (t.date <= END)]
t['period'] = t.date.between(*SPIKE).map({True: '급증 14일', False: '나머지 기간'})
t.groupby(['period', 'source'], as_index=False).views.sum().to_csv(f'{OUT}/traffic_by_period_source.csv', index=False)
GROUP = {'추천 동영상': '추천·탐색', '탐색 기능': '추천·탐색', 'YouTube 검색': '검색'}
t['group'] = t.source.map(GROUP).fillna('기타')
t.assign(month=t.date.dt.to_period('M').astype(str)).pivot_table(
    index='month', columns='group', values='views', aggfunc='sum').fillna(0).astype(int).to_csv(f'{OUT}/monthly_views_by_source.csv')

# ---------- 구독 ----------
s = pd.read_csv(f'{RAW}/subscribers_daily_lifetime.csv', parse_dates=['날짜'])
s.columns = ['date', 'subs_net']
s.set_index('date').sort_index()[START:END].to_csv(f'{OUT}/subscribers_daily_2019_2021.csv')

# ---------- 영상별 원본에서만 계산 가능한 집계값 ----------
top5 = pd.read_csv(f'{RAW}/top5_video_daily_lifetime.csv', parse_dates=['날짜'])
top5['code'] = top5['콘텐츠'].str.strip().map(MAP.code)
l1 = top5[top5.code == 'L1'].set_index('날짜')['유효 조회수'].sort_index()
t5_sum = top5.groupby('날짜')['유효 조회수'].sum().reindex(daily.index).fillna(0)
resid = daily - t5_sum
rows = [
    ('existing_before_spike', ','.join(v.loc[v.published < SPIKE[0], 'code']), '급증 시작 전 게시된 현존 영상'),
    ('l1_spike_views', int(l1[SPIKE[0]:SPIKE[1]].sum()), 'L1 유효 조회수 합계, 급증 14일'),
    ('l1_spike_daily_min', int(l1[SPIKE[0]:SPIKE[1]].min()), 'L1 일별 유효 조회수 최소, 급증 14일'),
    ('l1_spike_daily_max', int(l1[SPIKE[0]:SPIKE[1]].max()), 'L1 일별 유효 조회수 최대, 급증 14일'),
    ('l1_prior4w_daily_mean', round(float(l1['2019-02-09':'2019-03-08'].mean()), 1), 'L1 일평균 유효 조회수, 2019-02-09~03-08'),
    ('unlisted_views_after_spike', int(resid['2019-03-23':'2019-07-21'].sum()), '현존 영상 외 유효 조회수, 2019-03-23~07-21(당시 현존 영상은 L1뿐)'),
    ('long_form_watch_h', round(float(v[v.code.str.startswith('L')].watch_h.sum()), 4), '롱폼 L1·L2·L3 시청 시간 합계(시간)'),
]
for c in ['L2', 'L3', 'C1']:
    g = top5[top5.code == c].set_index('날짜')['유효 조회수'].sort_index()
    g = g[g[g > 0].index[0]:]
    z = (g == 0)[:END]
    rows.append((f'{c}_max_zero_run_2019_2021', int(z.groupby((z != z.shift()).cumsum()).sum().max()), f'{c} 2019–2021 최장 연속 조회 0일'))
    rows.append((f'{c}_last_view_month', g[g > 0].index[-1].strftime('%Y-%m'), f'{c} 마지막 조회 월(비공개 전환일 아님)'))
pd.DataFrame(rows, columns=['key', 'value', 'description'], dtype=object).to_csv(f'{OUT}/exact_aggregates.csv', index=False)

print('공개용 CSV 생성 완료:', OUT)
