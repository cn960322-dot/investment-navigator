import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from playwright.sync_api import sync_playwright
import json

# 1. 웹페이지 기본 설정 (사이드바 없이 넓게 사용)
st.set_page_config(page_title="30년차 자산관리사의 투자 나침반", layout="wide")
st.title("📊 30년차 자산관리사의 스마트 자산 형성 대시보드")
st.markdown("> **시장을 예측하지 마십시오. 위험(MDD)과 가치(PER), 그리고 심리(공포지수)를 모니터링하며 동행하십시오.**")

# 2. 데이터 캐싱 (최대 20년치 데이터를 백그라운드에서 한 번에 로드)
@st.cache_data(ttl=3600)
def get_all_base_data():
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(years=20)
    tickers = ['^GSPC', '^NDX', 'QLD', 'TQQQ', '^VIX']
    data = yf.download(tickers, start=start_date, end=end_date)['Close']
    return data

@st.cache_data(ttl=3600)
def get_big_tech_info():
    tech_tickers = ['MSFT', 'AAPL', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'AVGO', 'LLY', 'V']
    rows = []
    for ticker in tech_tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            name = info.get('shortName', ticker)
            market_cap = info.get('marketCap', 0) / 1e12  # 조 달러 단위
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
        # 시가총액 기준으로 내림차순 정렬
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

# MDD 계산 함수
def calculate_mdd_series(series: pd.Series) -> pd.Series:
    rolling_max = series.cummax()
    drawdown = (series - rolling_max) / rolling_max * 100
    return drawdown

# 기본 데이터 로드
with st.spinner("금융 데이터를 동기화하는 중입니다..."):
    base_data = get_all_base_data()

# MDD 미리 계산
sp500_dd_all = calculate_mdd_series(base_data['^GSPC'])
nasdaq_dd_all = calculate_mdd_series(base_data['^NDX'])
qld_dd_all = calculate_mdd_series(base_data['QLD'])
tqqq_dd_all = calculate_mdd_series(base_data['TQQQ'])

# 대시보드 탭 구성
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 1. 시장 지수 & MDD (S&P500 / NASDAQ)", 
    "🚀 2. 레버리지 분석 (QLD / TQQQ)", 
    "💎 3. 빅테크 TOP 10 밸류에이션", 
    "🔥 4. 시장 심리 지표 (공포와 탐욕 / VIX)"
])

# ---- 탭 1: S&P500 & NASDAQ ----
with tab1:
    st.subheader("주요 시장 지수 추이 및 역사적 고점 대비 하락률(MDD)")
    years_1 = st.slider("📅 S&P500 / NASDAQ 조회 기간 설정", 1, 20, 5, key="slider_tab1")
    filter_date_1 = pd.Timestamp.now() - pd.DateOffset(years=years_1)
    t1_data = base_data[base_data.index >= filter_date_1]
    t1_sp500_dd = sp500_dd_all[sp500_dd_all.index >= filter_date_1]
    t1_nasdaq_dd = nasdaq_dd_all[nasdaq_dd_all.index >= filter_date_1]
    
    if not t1_data.empty:
        fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("지수 추이 (Price)", "고점 대비 하락률 (Drawdown, %)"))
        fig1.add_trace(go.Scatter(x=t1_data.index, y=t1_data['^GSPC'], name="S&P 500"), row=1, col=1)
        fig1.add_trace(go.Scatter(x=t1_data.index, y=t1_data['^NDX'], name="NASDAQ 100"), row=1, col=1)
        fig1.add_trace(go.Scatter(x=t1_sp500_dd.index, y=t1_sp500_dd, name="S&P 500 DD(%)", fill='tozeroy'), row=2, col=1)
        fig1.add_trace(go.Scatter(x=t1_nasdaq_dd.index, y=t1_nasdaq_dd, name="NASDAQ 100 DD(%)", fill='tozeroy'), row=2, col=1)
        fig1.update_layout(height=550, hovermode="x unified", margin=dict(t=30, b=10))
        st.plotly_chart(fig1, width='stretch')
        col1, col2 = st.columns(2)
        col1.metric("선택 기간 내 S&P 500 최악의 낙폭 (최대 MDD)", f"{round(t1_sp500_dd.min(), 2)}%")
        col2.metric("선택 기간 내 NASDAQ 100 최악의 낙폭 (최대 MDD)", f"{round(t1_nasdaq_dd.min(), 2)}%")

# ---- 탭 2: QLD & TQQQ ----
with tab2:
    st.subheader("2배/3배 레버리지 지수 추이 및 MDD")
    st.warning("⚠️ 레버리지 상품은 하락장 진입 시 변동성 끌림 현상으로 고점 회복이 매우 느립니다.")
    years_2 = st.slider("📅 QLD / TQQQ 조회 기간 설정", 1, 20, 5, key="slider_tab2")
    filter_date_2 = pd.Timestamp.now() - pd.DateOffset(years=years_2)
    t2_data = base_data[base_data.index >= filter_date_2]
    t2_qld_dd = qld_dd_all[qld_dd_all.index >= filter_date_2]
    t2_tqqq_dd = tqqq_dd_all[tqqq_dd_all.index >= filter_date_2]
    
    if not t2_data.empty:
        fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=("레버리지 주가 추이", "고점 대비 하락률 (Drawdown, %)"))
        fig2.add_trace(go.Scatter(x=t2_data.index, y=t2_data['QLD'], name="QLD (Nas x2)"), row=1, col=1)
        fig2.add_trace(go.Scatter(x=t2_data.index, y=t2_data['TQQQ'], name="TQQQ (Nas x3)"), row=1, col=1)
        fig2.add_trace(go.Scatter(x=t2_qld_dd.index, y=t2_qld_dd, name="QLD DD(%)", fill='tozeroy'), row=2, col=1)
        fig2.add_trace(go.Scatter(x=t2_tqqq_dd.index, y=t2_tqqq_dd, name="TQQQ DD(%)", fill='tozeroy'), row=2, col=1)
        fig2.update_layout(height=550, hovermode="x unified", margin=dict(t=30, b=10))
        st.plotly_chart(fig2, width='stretch')
        col1, col2 = st.columns(2)
        col1.metric("선택 기간 내 QLD(2배) 최악의 낙폭 (최대 MDD)", f"{round(t2_qld_dd.min(), 2)}%")
        col2.metric("선택 기간 내 TQQQ(3배) 최악의 낙폭 (최대 MDD)", f"{round(t2_tqqq_dd.min(), 2)}%")

# ---- 탭 3: 미국 빅테크 TOP 10 (시총가중평균 반영) ----
with tab3:
    st.subheader("🇺🇸 미국 시가총액 상위 TOP 10 기업의 실시간 밸류에이션")
    
    with st.spinner("빅테크 데이터를 수집하고 가중평균을 산출하는 중..."):
        df_tech = get_big_tech_info()
        
        if not df_tech.empty:
            # 🔥 [정밀 수식 구현] PER이 정상적인 기업만 필터링하여 시총가중평균 계산
            valid_df = df_tech[df_tech['현재 PER'].notna() & (df_tech['현재 PER'] > 0)].copy()
            
            if not valid_df.empty:
                total_mcap = valid_df['시가총액(조$)'].sum()
                # 시총 / PER = 개별 기업 순이익 -> 총 순이익 합산
                total_earnings = (valid_df['시가총액(조$)'] / valid_df['현재 PER']).sum()
                # 총 시총 / 총 순이익 = 시총가중평균 PER
                weighted_per = total_mcap / total_earnings
                
                # 🌟 친구분 대시보드 스타일의 상단 KPI 요약 카드 배치
                st.markdown("### 🎯 빅테크 바스켓 시장 가치 평가 (Market PER)")
                c_m1, c_m2, c_m3 = st.columns(3)
                c_m1.metric(label="📊 시가총액 가중평균 PER (Market PER)", value=f"{round(weighted_per, 1)}")
                c_m2.metric(label="💰 TOP 10 총 시가총액 합계", value=f"${round(total_mcap, 2)}T")
                c_m3.metric(label="📈 바스켓 포함 기업 수", value=f"{len(valid_df)} 개사")
                st.markdown("---")
            
            # 하단 상세 데이터 테이블 출력
            st.dataframe(df_tech.style.format({'시가총액(조$)': '{:.2f}T', '현재 PER': '{:.2f}'}), width='stretch', hide_index=True)

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
            st.plotly_chart(fig3, width='stretch')