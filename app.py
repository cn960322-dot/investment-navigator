import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from playwright.sync_api import sync_playwright
import json
import os
import requests

# Linux 서버 환경에서 Playwright 브라우저 강제 설치 안내용 코드
if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
    os.system("playwright install chromium")

# 1. 웹페이지 기본 설정 (사이드바 없이 넓게 사용)
st.set_page_config(page_title="30년차 자산관리사의 투자 나침반", layout="wide")
st.title("📊 30년차 자산관리사의 스마트 자산 형성 대시보드")
st.markdown("> **시장을 예측하지 마십시오. 위험(MDD)과 가치(PER), 그리고 심리(공포지수)를 모니터링하며 동행하십시오.**")

# [보안 우회] 야후 파이낸스 IP 차단을 막기 위한 크롬 브라우저 위장 세션 생성
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
})

# RSI(상대강도지수) 계산 함수
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
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(years=20)
    tickers = ['^GSPC', '^NDX', 'QLD', 'TQQQ', '^VIX']
    data = yf.download(tickers, start=start_date, end=end_date, session=session)['Close']
    return data

@st.cache_data(ttl=3600)
def get_big_tech_info():
    tech_tickers = ['MSFT', 'AAPL', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO', 'LLY', 'V']
    rows = []
    for ticker in tech_tickers:
        try:
            t = yf.Ticker(ticker, session=session)
            info = t.info
            name = info.get('shortName', ticker)
            market_cap = info.get('marketCap', 0) / 1e12
            per = info.get('trailingPE', None)
            current_price = info.get('currentPrice', 0)
            rows.append({
                '티커': ticker, '기업명': name, '현재가($)': current_price, 
                '시가총액(조$)': round(market_cap, 2), '현재 PER': per
            })
        except:
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by='시가총액(조$)', ascending=False)
    return df

# Playwright 기반 CNN 공포지수 수집 함수
@st.cache_data(ttl=1800)
def get_cnn_fear_greed_live():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/current"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page.goto(url, timeout=15000)
            content = page.locator("body").text_content()
            browser.close()
            
            data = json.loads(content)
            fng = data.get('fear_and_greed')
            if fng and 'score' in fng:
                score = int(round(fng['score']))
                rating = fng.get('rating', 'NEUTRAL').upper()
                
                rating_kr = {
                    'EXTREME FEAR': '극단적 공포 😨', 'FEAR': '공포 📉',
                    'NEUTRAL': '중립 😐', 'GREED': '탐욕 📈', 'EXTREME GREED': '극단적 탐욕 🚀'
                }.get(rating, '중립 😐')
                
                return score, rating_kr
    except:
        pass
    return None, "데이터 연결 지연"

# 기본 데이터 로드
with st.spinner("금융 데이터를 동기화하는 중입니다..."):
    base_data = get_all_base_data()

# 지표 미리 계산
sp500_dd_all = calculate_mdd_series(base_data['^GSPC'])
nasdaq_dd_all = calculate_mdd_series(base_data['^NDX'])
qld_dd_all = calculate_mdd_series(base_data['QLD'])
tqqq_dd_all = calculate_mdd_series(base_data['TQQQ'])

# RSI 지표 미리 계산
sp500_rsi_all = calculate_rsi(base_data['^GSPC'])
nasdaq_rsi_all = calculate_rsi(base_data['^NDX'])
qld_rsi_all = calculate_rsi(base_data['QLD'])
tqqq_rsi_all = calculate_rsi(base_data['TQQQ'])

# 대시보드 탭 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 1. 시장 지수 & MDD (S&P500 / NASDAQ)", 
    "🚀 2. 레버리지 분석 & RSI (QLD / TQQQ)", 
    "💎 3. 빅테크 TOP 10 밸류에이션", 
    "🔥 4. 시장 심리 지표 (공포와 탐욕 / VIX)"
])

# ---- 탭 1: S&P500 & NASDAQ ----
with tab1:
    st.subheader("주요 시장 지수 추이, 역사적 고점 대비 하락률(MDD) 및 RSI")
    years_1 = st.number_input("📅 S&P500 / NASDAQ 조회 기간 설정 (1~20년)", min_value=1, max_value=20, value=5, step=1, key="input_tab1")
    filter_date_1 = pd.Timestamp.now() - pd.DateOffset(years=years_1)
    
    t1_data = base_data[base_data.index >= filter_date_1]
    t1_sp500_dd = sp500_dd_all[sp500_dd_all.index >= filter_date_1]
    t1_nasdaq_dd = nasdaq_dd_all[nasdaq_dd_all.index >= filter_date_1]
    t1_sp500_rsi = sp500_rsi_all[sp500_rsi_all.index >= filter_date_1]
    t1_nasdaq_rsi = nasdaq_rsi_all[nasdaq_rsi_all.index >= filter_date_1]
    
    if not t1_data.empty:
        sp500_clean = t1_data['^GSPC'].dropna()
        nasdaq_clean = t1_data['^NDX'].dropna()
        
        if len(sp500_clean) > 0 and len(nasdaq_clean) > 0:
            now_sp500_price = sp500_clean.iloc[-1]
            now_nasdaq_price = nasdaq_clean.iloc[-1]
            now_sp500_dd = t1_sp500_dd.dropna().iloc[-1]
            now_nasdaq_dd = t1_nasdaq_dd.dropna().iloc[-1]
            now_sp500_rsi = t1_sp500_rsi.dropna().iloc[-1]
            now_nasdaq_rsi = t1_nasdaq_rsi.dropna().iloc[-1]
            
            st.markdown("### 🎯 주요 시장 지수 실시간 지표 요약 (Current Status)")
            c_s1, c_s2, c_s3 = st.columns(3)
            c_s1.metric(label="🔹 S&P 500 현재 지수", value=f"{round(now_sp500_price, 2)}")
            c_s2.metric(label="📉 S&P 500 현재 고점대비 하락률(DD)", value=f"{round(now_sp500_dd, 2)}%")
            c_s3.metric(label="🟩 S&P 500 현재 RSI (14)", value=f"{round(now_sp500_rsi, 1)}")
            
            c_n1, c_n2, c_n3 = st.columns(3)
            c_n1.metric(label="🔸 NASDAQ 100 현재 지수", value=f"{round(now_nasdaq_price, 2)}")
            c_n2.metric(label="📉 NASDAQ 100 현재 고점대비 하락률(DD)", value=f"{round(now_nasdaq_dd, 2)}%")
            c_n3.metric(label="🟥 NASDAQ 100 현재 RSI (14)", value=f"{round(now_nasdaq_rsi, 1)}")
            st.markdown("---")
            
            fig1 = make_subplots(
                rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, 
                subplot_titles=("지수 추이 (Price)", "고점 대비 하락률 (Drawdown, %)", "RSI 심리 지표 (과매수 70 / 과매도 30)")
            )
            fig1.add_trace(go.Scatter(x=t1_data.index, y=t1_data['^GSPC'], name="S&P 500", line=dict(color='#1f77b4')), row=1, col=1)
            fig1.add_trace(go.Scatter(x=t1_data.index, y=t1_data['^NDX'], name="NASDAQ 100", line=dict(color='#ff7f0e')), row=1, col=1)
            fig1.add_trace(go.Scatter(x=t1_sp500_dd.index, y=t1_sp500_dd, name="S&P 500 DD(%)", fill='tozeroy', line=dict(color='rgba(31, 119, 180, 0.7)')), row=2, col=1)
            fig1.add_trace(go.Scatter(x=t1_nasdaq_dd.index, y=t1_nasdaq_dd, name="NASDAQ 100 DD(%)", fill='tozeroy', line=dict(color='rgba(255, 127, 14, 0.7)')), row=2, col=1)
            fig1.add_trace(go.Scatter(x=t1_data.index, y=t1_sp500_rsi, name="S&P 500 RSI (14)", line=dict(color='#2ca02c')), row=3, col=1)
            fig1.add_trace(go.Scatter(x=t1_data.index, y=t1_nasdaq_rsi, name="NASDAQ 100 RSI (14)", line=dict(color='#d62728')), row=3, col=1)
            fig1.add_hline(y=70, line_dash="dash", line_color="rgba(214, 39, 40, 0.6)", row=3, col=1)
            fig1.add_hline(y=30, line_dash="dash", line_color="rgba(31, 119, 180, 0.6)", row=3, col=1)
            fig1.update_layout(height=750, hovermode="x unified", margin=dict(t=30, b=10))
            st.plotly_chart(fig1, use_container_width=True)
            
            col1, col2 = st.columns(2)
            col1.metric("선택 기간 내 S&P 500 최악의 낙폭 (최대 MDD)", f"{round(t1_sp500_dd.min(), 2)}%")
            col2.metric("선택 기간 내 NASDAQ 100 최악의 낙폭 (최대 MDD)", f"{round(t1_nasdaq_dd.min(), 2)}%")
        else:
            st.error("⚠️ 야후 파이낸스(Yahoo Finance)의 요청 제한(Rate Limit)으로 인해 일시적으로 데이터를 호출하지 못했습니다. 잠시 후(1~2분 뒤) 새로고침(F5)을 해주세요.")

# ---- 탭 2: QLD & TQQQ ----
with tab2:
    st.subheader("2배/3배 레버리지 지수 추이, MDD 및 과매수/과매도(RSI)")
    st.warning("⚠️ 레버리지 상품은 하락장 진입 시 변동성 끌림 현상으로 고점 회복이 매우 느립니다. RSI 지표를 활용하여 무릎 이하에서 분할 매수하는 전략을 권장합니다.")
    years_2 = st.number_input("📅 QLD / TQQQ 조회 기간 설정 (1~20년)", min_value=1, max_value=20, value=5, step=1, key="input_tab2")
    filter_date_2 = pd.Timestamp.now() - pd.DateOffset(years=years_2)
    
    t2_data = base_data[base_data.index >= filter_date_2]
    t2_qld_dd = qld_dd_all[qld_dd_all.index >= filter_date_2]
    t2_tqqq_dd = tqqq_dd_all[tqqq_dd_all.index >= filter_date_2]
    t2_qld_rsi = qld_rsi_all[qld_rsi_all.index >= filter_date_2]
    t2_tqqq_rsi = tqqq_rsi_all[tqqq_rsi_all.index >= filter_date_2]
    
    if not t2_data.empty:
        qld_clean = t2_data['QLD'].dropna()
        tqqq_clean = t2_data['TQQQ'].dropna()
        
        if len(qld_clean) > 0 and len(tqqq_clean) > 0:
            now_qld_price = qld_clean.iloc[-1]
            now_tqqq_price = tqqq_clean.iloc[-1]
            now_qld_dd = t2_qld_dd.dropna().iloc[-1]
            now_tqqq_dd = t2_tqqq_dd.dropna().iloc[-1]
            now_qld_rsi = t2_qld_rsi.dropna().iloc[-1]
            now_tqqq_rsi = t2_tqqq_rsi.dropna().iloc[-1]
            
            st.markdown("### 🎯 레버리지 상품 실시간 지표 요약 (Current Status)")
            c_q1, c_q2, c_q3 = st.columns(3)
            c_q1.metric(label="🔹 QLD 현재가", value=f"${round(now_qld_price, 2)}")
            c_q2.metric(label="📉 QLD 현재 고점대비 하락률(DD)", value=f"{round(now_qld_dd, 2)}%")
            c_q3.metric(label="🟩 QLD 현재 RSI (14)", value=f"{round(now_qld_rsi, 1)}")
            
            c_t1, c_t2, c_t3 = st.columns(3)
            c_t1.metric(label="🔸 TQQQ 현재가", value=f"${round(now_tqqq_price, 2)}")
            c_t2.metric(label="📉 TQQQ 현재 고점대비 하락률(DD)", value=f"{round(now_tqqq_dd, 2)}%")
            c_t3.metric(label="🟥 TQQQ 현재 RSI (14)", value=f"{round(now_tqqq_rsi, 1)}")
            st.markdown("---")
            
            fig2 = make_subplots(
                rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, 
                subplot_titles=("레버리지 주가 추이", "고점 대비 하락률 (Drawdown, %)", "RSI 심리 지표 (과매수 70 / 과매도 30)")
            )
            fig2.add_trace(go.Scatter(x=t2_data.index, y=t2_data['QLD'], name="QLD (Nas x2)", line=dict(color='#1f77b4')), row=1, col=1)
            fig2.add_trace(go.Scatter(x=t2_data.index, y=t2_data['TQQQ'], name="TQQQ (Nas x3)", line=dict(color='#ff7f0e')), row=1, col=1)
            fig2.add_trace(go.Scatter(x=t2_qld_dd.index, y=t2_qld_dd, name="QLD DD(%)", fill='tozeroy', line=dict(color='rgba(31, 119, 180, 0.7)')), row=2, col=1)
            fig2.add_trace(go.Scatter(x=t2_tqqq_dd.index, y=t2_tqqq_dd, name="TQQQ DD(%)", fill='tozeroy', line=dict(color='rgba(255, 127, 14, 0.7)')), row=2, col=1)
            fig2.add_trace(go.Scatter(x=t2_data.index, y=t2_qld_rsi, name="QLD RSI (14)", line=dict(color='#2ca02c')), row=3, col=1)
            fig2.add_trace(go.Scatter(x=t2_data.index, y=t2_tqqq_rsi, name="TQQQ RSI (14)", line=dict(color='#d62728')), row=3, col=1)
            fig2.add_hline(y=70, line_dash="dash", line_color="rgba(214, 39, 40, 0.6)", row=3, col=1)
            fig2.add_hline(y=30, line_dash="dash", line_color="rgba(31, 119, 180, 0.6)", row=3, col=1)
            fig2.update_layout(height=750, hovermode="x unified", margin=dict(t=30, b=10))
            st.plotly_chart(fig2, use_container_width=True)
            
            col1, col2 = st.columns(2)
            col1.metric("선택 기간 내 QLD(2배) 최악의 낙폭 (최대 MDD)", f"{round(t2_qld_dd.min(), 2)}%")
            col2.metric("선택 기간 내 TQQQ(3배) 최악의 낙폭 (최대 MDD)", f"{round(t2_tqqq_dd.min(), 2)}%")
        else:
            st.error("⚠️ 야후 파이낸스(Yahoo Finance)의 요청 제한(Rate Limit)으로 인해 일시적으로 데이터를 호출하지 못했습니다. 잠시 후(1~2분 뒤) 새로고침(F5)을 해주세요.")

# ---- 탭 3: 미국 빅테크 TOP 10 (에러 방어막 강화) ----
with tab3:
    st.subheader("🇺🇸 미국 시가총액 상위 TOP 10 기업의 실시간 밸류에이션")
    
    with st.spinner("빅테크 데이터를 수집하고 가중평균을 산출하는 중..."):
        df_tech = get_big_tech_info()
        
        # 🛡️ [정밀 보완] 차단 등으로 데이터가 비어있을 때 빈 화면 대신 에러 안내문 출력
        if not df_tech.empty:
            valid_df = df_tech[df_tech['현재 PER'].notna() & (df_tech['현재 PER'] > 0)].copy()
            
            if not valid_df.empty:
                total_mcap = valid_df['시가총액(조$)'].sum()
                total_earnings = (valid_df['시가총액(조$)'] / valid_df['현재 PER']).sum()
                weighted_per = total_mcap / total_earnings
                
                st.markdown("### 🎯 빅테크 바스켓 시장 가치 평가 (Market PER)")
                c_m1, c_m2, c_m3 = st.columns(3)
                c_m1.metric(label="📊 시가총액 가중평균 PER (Market PER)", value=f"{round(weighted_per, 1)}")
                c_m2.metric(label="💰 TOP 10 총 시가총액 합계", value=f"${round(total_mcap, 2)}T")
                c_m3.metric(label="📈 바스켓 포함 기업 수", value=f"{len(valid_df)} 개사")
                st.markdown("---")
            
            st.dataframe(df_tech.style.format({'시가총액(조$)': '{:.2f}T', '현재 PER': '{:.2f}'}), width='stretch', hide_index=True)
        else:
            st.error("⚠️ 야후 파이낸스 서버에서 빅테크 10개 기업의 상세 정보(PER, 시가총액) 호출이 일시적으로 거부되었습니다. 개별 종목 정보는 지수 데이터보다 보안 결계가 높아 풀리는 데 시간이 조금 더 걸릴 수 있습니다. 잠시 후(3~5분 뒤) 새로고침(F5)을 해주세요.")

# ---- 탭 4: 시장 심리 지표 ----
with tab4:
    st.subheader("📊 시장의 탐욕과 공포 측정")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("### 1) CNN 공포와 탐욕 지수 (Fear & Greed Index)")
        with st.spinner("CNN 보안 우회 터널을 생성하는 중입니다..."):
            score, rating = get_cnn_fear_greed_live()
        
        if score is not None:
            st.metric(label=f"현재 시장 심리 상태: {rating}", value=f"{score} / 100")
            st.progress(score / 100)
            st.info("💡 **투자 공식:** 20 이하(극단적 공포) = 매수 적기 / 80 이상(극단적 탐욕) = 현금 비중 확대")
        else:
            st.warning("⚠️ CNN 일시적 응답 지연. 수동 확인은 아래 버튼을 이용하세요.")
            st.link_button("🌐 CNN 실시간 웹사이트 확인", "https://www.cnn.com/markets/fear-and-greed", type="primary")

    with col2:
        st.write("### 2) VIX 지수 (공포지수) 추이")
        vix_date = pd.Timestamp.now() - pd.DateOffset(years=1)
        t4_data = base_data[base_data.index >= vix_date]
        if not t4_data.empty:
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=t4_data.index, y=t4_data['^VIX'], name="VIX 지수", line=dict(color='red')))
            fig3.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig3, use_container_width=True)
