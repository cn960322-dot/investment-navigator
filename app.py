import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from playwright.sync_api import sync_playwright
import json
import os
import requests
import time
import random

# Linux 서버 환경에서 Playwright 브라우저 강제 설치
if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
    os.system("playwright install chromium")

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="30년차 자산관리사의 투자 나침반", layout="wide")
st.title("📊 30년차 자산관리사의 스마트 자산 형성 대시보드")
st.markdown("> **시장을 예측하지 마십시오. 위험(MDD)과 가치(PER), 그리고 심리(공포지수)를 모니터링하며 동행하십시오.**")

# [강력 우회] 다양한 브라우저 정보 리스트 (야후 감시 회피용)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
]

def get_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    })
    return session

# RSI 계산 함수
def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# MDD 계산 함수
def calculate_mdd_series(series: pd.Series) -> pd.Series:
    rolling_max = series.cummax()
    drawdown = (series - rolling_max) / rolling_max * 100
    return drawdown

# 2. 데이터 캐싱
@st.cache_data(ttl=3600)
def get_all_base_data():
    sess = get_session()
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(years=20)
    tickers = ['^GSPC', '^NDX', 'QLD', 'TQQQ', '^VIX']
    data = yf.download(tickers, start=start_date, end=end_date, session=sess)['Close']
    return data

@st.cache_data(ttl=3600)
def get_big_tech_info():
    tech_tickers = ['MSFT', 'AAPL', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO', 'LLY', 'V']
    rows = []
    
    # 진행바를 표시하여 사용자에게 대기 안내
    progress_text = "야후 보안망을 우회하여 빅테크 정보를 수집 중입니다. 잠시만 기다려주세요..."
    my_bar = st.progress(0, text=progress_text)
    
    for i, ticker in enumerate(tech_tickers):
        try:
            # 🕒 요청마다 1~2초 사이의 랜덤한 시간을 쉬어 사람처럼 행동함
            time.sleep(random.uniform(1.0, 2.0))
            
            sess = get_session()
            t = yf.Ticker(ticker, session=sess)
            
            # 1차 시도: 전체 정보(info)
            info = t.info
            name = info.get('shortName', ticker)
            market_cap = info.get('marketCap', 0) / 1e12
            per = info.get('trailingPE', None)
            current_price = info.get('currentPrice', 0)
            
            # 2차 시도: 만약 info가 막혔다면 fast_info로 시가총액/가격이라도 가져옴
            if market_cap == 0:
                fast = t.fast_info
                market_cap = fast.get('marketCap', 0) / 1e12
                current_price = fast.get('lastPrice', 0)
                name = ticker

            rows.append({
                '티커': ticker, '기업명': name, '현재가($)': current_price, 
                '시가총액(조$)': round(market_cap, 2), '현재 PER': per
            })
        except:
            continue
        my_bar.progress((i + 1) / len(tech_tickers), text=progress_text)
    
    my_bar.empty()
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by='시가총액(조$)', ascending=False)
    return df

# Playwright 기반 CNN 공포지수 수집
@st.cache_data(ttl=1800)
def get_cnn_fear_greed_live():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/current"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=random.choice(USER_AGENTS))
            page.goto(url, timeout=15000)
            content = page.locator("body").text_content()
            browser.close()
            data = json.loads(content)
            fng = data.get('fear_and_greed')
            if fng and 'score' in fng:
                score = int(round(fng['score']))
                rating = fng.get('rating', 'NEUTRAL').upper()
                rating_kr = {'EXTREME FEAR': '극단적 공포 😨', 'FEAR': '공포 📉', 'NEUTRAL': '중립 😐', 'GREED': '탐욕 📈', 'EXTREME GREED': '극단적 탐욕 🚀'}.get(rating, '중립 😐')
                return score, rating_kr
    except: pass
    return None, "데이터 연결 지연"

# 데이터 로드
with st.spinner("금융 데이터를 동기화하는 중입니다..."):
    base_data = get_all_base_data()

# 지표 미리 계산
sp500_dd_all = calculate_mdd_series(base_data['^GSPC'])
nasdaq_dd_all = calculate_mdd_series(base_data['^NDX'])
qld_dd_all = calculate_mdd_series(base_data['QLD'])
tqqq_dd_all = calculate_mdd_series(base_data['TQQQ'])
sp500_rsi_all = calculate_rsi(base_data['^GSPC'])
nasdaq_rsi_all = calculate_rsi(base_data['^NDX'])
qld_rsi_all = calculate_rsi(base_data['QLD'])
tqqq_rsi_all = calculate_rsi(base_data['TQQQ'])

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📈 1. 시장 지수 & MDD", "🚀 2. 레버리지 분석 & RSI", "💎 3. 빅테크 TOP 10 밸류에이션", "🔥 4. 시장 심리 지표"])

# ---- 탭 1 ----
with tab1:
    st.subheader("주요 시장 지수 추이, 역사적 고점 대비 하락률(MDD) 및 RSI")
    years_1 = st.number_input("📅 조회 기간 설정 (1~20년)", min_value=1, max_value=20, value=5, step=1, key="in1")
    filter_date_1 = pd.Timestamp.now() - pd.DateOffset(years=years_1)
    t1_data = base_data[base_data.index >= filter_date_1]
    if not t1_data.empty:
        s_cl, n_cl = t1_data['^GSPC'].dropna(), t1_data['^NDX'].dropna()
        if len(s_cl) > 0:
            st.markdown("### 🎯 주요 시장 지수 실시간 지표 요약")
            c1, c2, c3 = st.columns(3)
            c1.metric("🔹 S&P 500", f"{round(s_cl.iloc[-1], 2)}")
            c2.metric("📉 S&P 500 DD", f"{round(sp500_dd_all[sp500_dd_all.index >= filter_date_1].dropna().iloc[-1], 2)}%")
            c3.metric("🟩 S&P 500 RSI", f"{round(sp500_rsi_all[sp500_rsi_all.index >= filter_date_1].dropna().iloc[-1], 1)}")
            fig1 = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=("Price", "MDD (%)", "RSI"))
            fig1.add_trace(go.Scatter(x=t1_data.index, y=t1_data['^GSPC'], name="S&P 500"), row=1, col=1)
            fig1.add_trace(go.Scatter(x=t1_data.index, y=t1_data['^NDX'], name="NASDAQ 100"), row=1, col=1)
            fig1.update_layout(height=750, hovermode="x unified")
            st.plotly_chart(fig1, use_container_width=True)

# ---- 탭 2 ----
with tab2:
    st.subheader("2배/3배 레버리지 지수 추이, MDD 및 RSI")
    years_2 = st.number_input("📅 조회 기간 설정 (1~20년)", min_value=1, max_value=20, value=5, step=1, key="in2")
    filter_date_2 = pd.Timestamp.now() - pd.DateOffset(years=years_2)
    t2_data = base_data[base_data.index >= filter_date_2]
    if not t2_data.empty:
        q_cl, t_cl = t2_data['QLD'].dropna(), t2_data['TQQQ'].dropna()
        if len(q_cl) > 0:
            st.markdown("### 🎯 레버리지 실시간 지표 요약")
            c1, c2, c3 = st.columns(3)
            c1.metric("🔹 QLD 현재가", f"${round(q_cl.iloc[-1], 2)}")
            c2.metric("📉 QLD DD", f"{round(qld_dd_all[qld_dd_all.index >= filter_date_2].dropna().iloc[-1], 2)}%")
            c3.metric("🟩 QLD RSI", f"{round(qld_rsi_all[qld_rsi_all.index >= filter_date_2].dropna().iloc[-1], 1)}")
            fig2 = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=("Price", "MDD (%)", "RSI"))
            fig2.add_trace(go.Scatter(x=t2_data.index, y=t2_data['QLD'], name="QLD"), row=1, col=1)
            fig2.add_trace(go.Scatter(x=t2_data.index, y=t2_data['TQQQ'], name="TQQQ"), row=1, col=1)
            fig2.update_layout(height=750, hovermode="x unified")
            st.plotly_chart(fig2, use_container_width=True)

# ---- 탭 3 ----
with tab3:
    st.subheader("🇺🇸 미국 시가총액 상위 TOP 10 기업의 실시간 밸류에이션")
    df_tech = get_big_tech_info()
    if not df_tech.empty:
        valid_df = df_tech[df_tech['현재 PER'].notna() & (df_tech['현재 PER'] > 0)].copy()
        if not valid_df.empty:
            total_mcap = valid_df['시가총액(조$)'].sum()
            total_earnings = (valid_df['시가총액(조$)'] / valid_df['현재 PER']).sum()
            weighted_per = total_mcap / total_earnings
            st.markdown("### 🎯 빅테크 바스켓 시장 가치 평가")
            c1, c2, c3 = st.columns(3)
            c1.metric("📊 시총가중평균 PER", f"{round(weighted_per, 1)}")
            c2.metric("💰 TOP 10 총 시가총액", f"${round(total_mcap, 2)}T")
            c3.metric("📈 바스켓 포함 기업", f"{len(valid_df)} 개사")
        st.dataframe(df_tech.style.format({'시가총액(조$)': '{:.2f}T', '현재 PER': '{:.2f}'}), use_container_width=True, hide_index=True)
    else:
        st.error("⚠️ 야후 파이낸스의 강력한 차단으로 데이터를 가져오지 못했습니다. 5분 뒤 다시 시도해주세요.")

# ---- 탭 4 ----
with tab4:
    st.subheader("📊 시장 심리 지표")
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 1) CNN Fear & Greed Index")
        score, rating = get_cnn_fear_greed_live()
        if score: 
            st.metric(rating, f"{score} / 100")
            st.progress(score/100)
    with col2:
        st.write("### 2) VIX 지수")
        v_data = base_data[base_data.index >= pd.Timestamp.now() - pd.DateOffset(years=1)]
        fig3 = go.Figure(go.Scatter(x=v_data.index, y=base_data['^VIX'], name="VIX", line=dict(color='red')))
        fig3.update_layout(height=350)
        st.plotly_chart(fig3, use_container_width=True)
