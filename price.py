import asyncio
import requests
import json
import os
import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
import yfinance as yf

# --- 환경 변수 로드 ---
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']
string_session = os.environ['TELEGRAM_STRING_SESSION']

kis_app_key = os.environ.get('KIS_APP_KEY', '')
kis_app_secret = os.environ.get('KIS_APP_SECRET', '')

# --- 한국투자증권 API (한국 주식용) ---
def get_kis_access_token():
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": kis_app_key, "appsecret": kis_app_secret}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200: return res.json().get("access_token")
    except: pass
    return None

def get_kis_stock_price(token, ticker):
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json", "authorization": f"Bearer {token}",
        "appkey": kis_app_key, "appsecret": kis_app_secret, "tr_id": "FHKST01010100"
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker}
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json().get("output", {})
            if data:
                return {
                    "price": float(data.get("stck_prpr", 0)), 
                    "change": float(data.get("prdy_ctrt", 0)), 
                    "unit": "원"
                }
    except: pass
    return None

# --- 야후 파이낸스 (해외 주식, 지수, 원자재용) ---
def get_yahoo_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        # 최신 종가(애프터마켓 포함)와 정확한 전일 정규장 마감가 비교 로직
        latest_data = stock.history(period='1d', prepost=True)
        hist_regular = stock.history(period='5d', prepost=False)
        
        if not latest_data.empty and len(hist_regular) >= 2:
            price = latest_data['Close'].iloc[-1]
            prev_close = hist_regular['Close'].iloc[-2]
            
            change = ((price - prev_close) / prev_close) * 100
            
            unit = "pt" if "^" in ticker else "$"
            if "KRW" in ticker: unit = "원"
            if ticker in ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F", "ZW=F"]: unit = "$"
            
            return {"price": round(price, 2), "change": round(change, 2), "unit": unit}
    except Exception as e:
        pass
    return None

# --- 메인 실행 함수 ---
async def main():
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()
    
    try:
        print("🔄 텔레그램 채팅방 목록 동기화 중...")
        await client.get_dialogs()

        kst = datetime.timezone(datetime.timedelta(hours=9))
        now_str = datetime.datetime.now(kst).strftime('%Y-%m-%d %H:%M KST')
        kis_token = get_kis_access_token()

        # 업데이트된 포트폴리오 목록
        portfolio = {
            "🌐 주요 지수 및 환율": {
                "S&P 500": "^GSPC", "나스닥 종합": "^IXIC", "다우존스": "^DJI", "필라델피아 반도체": "^SOX", "VIX (공포지수)": "^VIX", 
                "달러 인덱스": "DX-Y.NYB", "원/달러 환율": "KRW=X", "엔/원 환율": "JPYKRW=X", "코스피": "^KS11", "코스닥": "^KQ11"
            },
            "📈 주요 레버리지 ETF": {"SOXL": "SOXL", "TQQQ": "TQQQ"},
            "🏛️ 미국 국채 금리 (%)": {
                "2년물": "^IRX", "5년물": "^FVX", "10년물": "^TNX", "30년물": "^TYX"
            },
            "🛢️ 핵심 원자재": {
                "금": "GC=F", "은": "SI=F", "WTI유": "CL=F", 
                "천연가스": "NG=F", "구리": "HG=F", "밀": "ZW=F"
            },
            "💻 반도체 & 장비": {
                "엔비디아": "NVDA", "TSMC": "TSM", "브로드컴": "AVGO", "AMD": "AMD", 
                "ARM": "ARM", "퀄컴": "QCOM", "마이크론": "MU", "인텔": "INTC", 
                "마벨": "MRVL", "테러다인": "TER", "온세미": "ON", "ASML": "ASML", 
                "AMAT": "AMAT", "램리서치": "LRCX",
                "삼성전자": "K:005930", "SK하이닉스": "K:000660", "리노공업": "K:058470", 
                "테스": "K:095610", "루멘텀": "LITE", "대덕전자": "K:353200", 
                "오라클": "ORCL", "코닝": "GLW", "유진테크": "K:084370", "심텍": "K:222800", "원익IPS": "K:240810"
            },
            "⚡ 전력 & 에너지": {
                "효성중공업": "K:298040", "블룸에너지": "BE", "LS일렉트릭": "K:010120"
            },
            "🪖 방산 & 우주 & AI": {
                "팔란티어": "PLTR", "한화에어로스페이스": "K:012450", "LIG넥스원": "K:079550", 
                "KAI": "K:047810", "현대로템": "K:064350", "한화오션": "K:042660",
                "SPCX (SPAC ETF)": "SPCX", "레드와이어": "RDW"
            },
            "🪙 가상자산 생태계": {
                "비트코인": "BTC-USD", "코인베이스": "COIN", "로빈후드": "HOOD", 
                "블록": "SQ", "마이크로스트레티지": "MSTR"
            },
            "🍎 글로벌 빅테크": {
                "마이크로소프트": "MSFT", "테슬라": "TSLA", "구글": "GOOGL", 
                "아마존": "AMZN", "메타(페이스북)": "META", "애플": "AAPL"
            },
            "⚛️ 양자 컴퓨팅": {"아이온큐": "IONQ", "IBM": "IBM"},
            "🏢 헬스케어 & 소비재": {
                "일라이 릴리": "LLY", "삼양식품": "K:003230", "에이피알": "K:278470", 
                "삼성바이오로직스": "K:207940", "한국콜마": "K:161890", "크록스": "CROX", 
                "맥도날드": "MCD", "나이키": "NKE", "넷플릭스": "NFLX", "코르테바": "CTVA"
            },
            "📊 미국 섹터별 ETF": {
                "XLK(기술)": "XLK", "XLV(헬스케어)": "XLV", "XLF(금융)": "XLF", 
                "XLE(에너지)": "XLE", "XLY(소비재)": "XLY", "XLP(필수소비재)": "XLP", 
                "XLU(유틸리티)": "XLU", "XLB(소재)": "XLB", "XLRE(부동산)": "XLRE", "XLC(통신)": "XLC"
            }
        }

        final_message = f"🎯 **[{now_str} 마감 글로벌 시황판]**\n"
        final_message += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        print("정밀 데이터 수집 시작 (색상 수정 반영)...")
        
        for category, items in portfolio.items():
            final_message += f"**{category}**\n"
            for name, ticker in items.items():
                if ticker.startswith("K:"):
                    code = ticker.replace("K:", "")
                    info = get_kis_stock_price(kis_token, code)
                else:
                    info = get_yahoo_price(ticker)
                
                if info:
                    # 💡 [핵심 수정] 빨간색, 파란색 원으로 직관적인 색상 구분
                    if info['change'] > 0:
                        sign = "🔴 +"
                    elif info['change'] < 0:
                        sign = "🔵 " # 음수는 숫자에 이미 '-' 기호가 붙어 나옵니다.
                    else:
                        sign = "⚪️ "
                        
                    if info['unit'] == "원":
                        price_str = f"{int(info['price']):,}"
                    else:
                        price_str = f"{info['price']:,.2f}"
                        
                    final_message += f"▪️ {name}: {price_str}{info['unit']} ({sign}{info['change']}%) \n"
                else:
                    final_message += f"▪️ {name}: 조회 지연/실패\n"
                    
            final_message += "━━━━━━━━━━━━━━━━━━━━\n"
            
        for i in range(0, len(final_message), 4000):
            await client.send_message('주식정리방', final_message[i:i+4000])
            await asyncio.sleep(1)
            
        print("✅ 모든 포트폴리오 전송 완료!")

    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
