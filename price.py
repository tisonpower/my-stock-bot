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
                    "price": int(data.get("stck_prpr", 0)), 
                    "change": float(data.get("prdy_ctrt", 0)), 
                    "unit": "원"
                }
    except: pass
    return None

# --- 야후 파이낸스 (해외 주식, 지수, 원자재용) ---
def get_yahoo_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        todays_data = stock.history(period='1d')
        if not todays_data.empty:
            price = todays_data['Close'].iloc[0]
            # 어제 종가 대비 등락률 계산
            prev_close = stock.fast_info.previous_close
            change = ((price - prev_close) / prev_close) * 100
            
            # 환율이나 지수는 소수점 2자리, 주식은 2자리
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

        # 💡 사용자가 요청한 엄청난 포트폴리오 리스트입니다!
        # K: 로 시작하는 것은 한국 주식(한국투자증권), 나머지는 야후 파이낸스(미국/글로벌)입니다.
        portfolio = {
            "🌐 지수 및 환율": {
                "다우존스": "^DJI", "필라델피아 반도체": "^SOX", "VIX": "^VIX", 
                "달러환율": "KRW=X", "일본환율": "JPYKRW=X", "코스피": "^KS11", "코스닥": "^KQ11"
            },
            "📈 주요 ETF": {"SOXL": "SOXL", "TQQQ": "TQQQ"},
            "🏛️ 채권 금리 (%)": {
                "미국채 2년": "^IRX", "미국채 5년": "^FVX", "미국채 10년": "^TNX", "미국채 30년": "^TYX"
                # 한국채는 무료 API 제공이 안 되어 제외되었습니다. 양해 부탁드립니다.
            },
            "🛢️ 원자재": {
                "금": "GC=F", "은": "SI=F", "WTI": "CL=F", 
                "천연가스": "NG=F", "구리": "HG=F", "밀": "ZW=F"
            },
            "💻 반도체": {
                "TSMC": "TSM", "브로드컴": "AVGO", "엔비디아": "NVDA", "AMD": "AMD", 
                "마이크론": "MU", "인텔": "INTC", "마벨": "MRVL", "테러다인": "TER", 
                "온세미": "ON", "ASML": "ASML", "어플라이드머티어리얼즈(AMTA)": "AMAT", "램리서치": "LRCX",
                "삼성전자": "K:005930", "SK하이닉스": "K:000660", "리노공업": "K:058470", 
                "테스": "K:095610", "루멘텀": "LITE", "대덕전자": "K:353200", 
                "오라클": "ORCL", "코닝": "GLW", "유진테크": "K:084370", "심텍": "K:222800", "원익IPS": "K:240810"
            },
            "⚡ 전력 에너지": {
                "효성중공업": "K:298040", "블룸에너지": "BE", "LS일렉트릭": "K:010120"
            },
            "🪖 방산기업": {
                "한화에어로스페이스": "K:012450", "LIG넥스원": "K:079550", "KAI": "K:047810", 
                "현대로템": "K:064350", "한화오션": "K:042660"
            },
            "🚀 우주": {"스페이스X(상장전이라 불가)": "NONE", "레드와이어": "RDW"},
            "🪙 비트코인 및 코인관련": {
                "비트코인": "BTC-USD", "코인베이스": "COIN", "로빈후드": "HOOD", 
                "블록": "SQ", "마이크로스트레티지": "MSTR"
            },
            "🍎 빅테크": {
                "마이크로소프트": "MSFT", "테슬라": "TSLA", "구글": "GOOGL", 
                "아마존": "AMZN", "메타(페이스북)": "META", "애플": "AAPL"
            },
            "⚛️ 양자관련": {"아이온큐": "IONQ", "IBM": "IBM"},
            "🏢 기타회사": {
                "삼양식품": "K:003230", "에이피알": "K:278470", "삼성바이오로직스": "K:207940", 
                "한국콜마": "K:161890", "크록스": "CROX", "맥도날드": "MCD", 
                "나이키": "NKE", "넷플릭스": "NFLX", "코르테바": "CTVA"
            },
            "📊 미국 섹터별 ETF": {
                "XLK(기술)": "XLK", "XLV(헬스케어)": "XLV", "XLF(금융)": "XLF", 
                "XLE(에너지)": "XLE", "XLY(소비재)": "XLY", "XLP(필수소비재)": "XLP", 
                "XLU(유틸리티)": "XLU", "XLB(소재)": "XLB", "XLRE(부동산)": "XLRE", "XLC(통신)": "XLC"
            }
        }

        # 결과 텍스트 만들기
        final_message = f"🎯 **[{now_str} 글로벌 마감 시황]**\n\n"
        
        print("데이터 수집 시작 (시간이 1~2분 정도 걸릴 수 있습니다)...")
        
        for category, items in portfolio.items():
            final_message += f"**[{category}]**\n"
            for name, ticker in items.items():
                if ticker == "NONE": continue
                
                # 한국 주식 처리
                if ticker.startswith("K:"):
                    code = ticker.replace("K:", "")
                    info = get_kis_stock_price(kis_token, code)
                # 해외 주식/지수 처리
                else:
                    info = get_yahoo_price(ticker)
                
                # 데이터가 정상적으로 들어왔다면 메시지에 추가
                if info:
                    sign = "🔴+" if info['change'] > 0 else "🔵"
                    if info['change'] == 0: sign = "⚪️"
                    
                    # 가격 포맷팅 (원화는 콤마, 달러는 소수점)
                    if info['unit'] == "원":
                        price_str = f"{int(info['price']):,}"
                    else:
                        price_str = f"{info['price']:,.2f}"
                        
                    final_message += f"• {name}: {price_str}{info['unit']} ({sign}{info['change']}%) \n"
                else:
                    final_message += f"• {name}: 조회 실패\n"
                    
            final_message += "\n" # 카테고리별 줄바꿈
            
        # 텔레그램 메시지는 너무 길면 안 되므로 잘라서 보냅니다.
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
