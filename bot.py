import asyncio
import requests
import json
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import datetime
import os

# --- 1. 환경 변수 로드 (깃허브 비밀 금고에서 가져옴) ---
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']
string_session = os.environ['TELEGRAM_STRING_SESSION']
gemini_key = os.environ['GEMINI_KEY']

kis_app_key = os.environ.get('KIS_APP_KEY', '')
kis_app_secret = os.environ.get('KIS_APP_SECRET', '')

# --- 2. 수집할 텔레그램 채널 목록 ---
target_channels = [
    '@bornlupin', '@kwusa', '@meritz_research', '@EarlyStock1', 
    '@hslpartners', '@valjuman', '@Jstockclass', '@daishinstrategy', 
    '@BRILLER_Research', '@ehdwl', '@djbmanager', '@kisthemacro', 
    '@Vegastooza', '@techkorea', '@yuantaresearch', '@SK_Research_Asset'
]

# --- 3. 한국투자증권 API 통신 함수 ---
def get_kis_access_token():
    """한국투자증권 API에 접속하기 위한 임시 출입증(토큰)을 발급받는 함수"""
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": kis_app_key,
        "appsecret": kis_app_secret
    }
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            return res.json().get("access_token")
    except Exception as e:
        print(f"KIS 토큰 발급 실패: {e}")
    return None

def get_kis_stock_price(token, ticker):
    """종목 코드를 넣으면 현재 가격과 등락률을 가져오는 함수"""
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": kis_app_key,
        "appsecret": kis_app_secret,
        "tr_id": "FHKST01010100" # 국내주식 현재가를 조회하겠다는 암호코드
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", # 주식, ETF 시장
        "FID_INPUT_ISCD": ticker       # 종목코드 (예: 005930)
    }
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json().get("output", {})
            if data:
                return {
                    "현재가": int(data.get("stck_prpr", 0)),
                    "등락률": float(data.get("prdy_ctrt", 0))
                }
    except Exception as e:
        print(f"[{ticker}] 가격 조회 실패: {e}")
    return None

# --- 4. 텔레그램 메시지 수집 함수 ---
async def fetch_channel(client, channel, today, semaphore):
    async with semaphore:
        messages = []
        try:
            async for message in client.iter_messages(channel, offset_date=today, reverse=True, limit=50):
                if message.text and len(message.text) > 20:
                    messages.append(f"[{channel}] {message.text}")
        except Exception as e:
            print(f"[{channel}] 수집 스킵: {e}")
        return messages

# --- 5. 메인 실행 함수 ---
async def main():
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()
    
    try:
        print("🔄 텔레그램 채팅방 목록 동기화 중...")
        await client.get_dialogs()

        # 제미나이 2.5 Flash 모델 준비 
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 한국 시간 설정
        kst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(kst)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        now_str = now.strftime('%Y-%m-%d %H:%M KST')

        # 💡 [새로 추가된 기능] KIS 주가 데이터 수집
        print("📈 KIS 주가 데이터 수집 중...")
        market_data_str = "오늘자 주가 데이터 수집에 실패했습니다."
        kis_token = get_kis_access_token()
        
        if kis_token:
            # 원하는 종목 코드와 이름 설정 
            # 지수(코스피/나스닥)는 ETF 종목 코드로 대체하여 쉽게 가져오도록 세팅했습니다.
            tickers = {
                "005930": "삼성전자", 
                "000660": "SK하이닉스", 
                "069500": "KODEX 200 (코스피 지수 대용)",
                "133690": "TIGER 미국나스닥100"
            }
            market_data_lines = []
            
            for code, name in tickers.items():
                price_info = get_kis_stock_price(kis_token, code)
                if price_info:
                    sign = "+" if price_info['등락률'] > 0 else ""
                    market_data_lines.append(f"- {name}: {price_info['현재가']:,}원 ({sign}{price_info['등락률']}%)")
            
            if market_data_lines:
                market_data_str = "\n".join(market_data_lines)

        # 💡 기존 기능: 텔레그램 뉴스 데이터 수집
        print("🚀 텔레그램 뉴스 데이터 수집 시작...")
        semaphore = asyncio.Semaphore(5)
        tasks = [fetch_channel(client, ch, today, semaphore) for ch in target_channels]
        results = await asyncio.gather(*tasks)
        
        raw_data = "\n\n".join([msg for sublist in results for msg in sublist])

        target_room = '주식정리방'

        if not raw_data:
            await client.send_message(target_room, "📥 오늘 수집된 데이터가 없습니다.")
            return

        if len(raw_data) > 40000:
            raw_data = raw_data[:40000] + "\n\n...(데이터 과다로 이하 생략)"

        # 💡 제미나이에게 내릴 최종 명령서 (주가 데이터 + 뉴스 데이터 결합)
        prompt_news = f"""
당신은 수석 매크로/퀀트 전략가입니다. {now_str} 기준 분석하세요.

[현재 실시간 주식/지수 데이터]
{market_data_str}

[분석 우선순위]
- 위 실시간 데이터(상승/하락)를 아래 텔레그램 뉴스와 연결하여 시장 흐름의 이유를 분석할 것
- AI 반도체/전력 인프라 특이 동향 최우선
- 매크로 지표 변화 (VIX, 환율, 금리, 유가)
- 섹터 로테이션 자금 이동 신호

[보고서 필수 양식]
## 📊 오늘의 시황 및 핵심 테마 (3줄 요약)
## 🏢 섹터별 분석
- AI/반도체:
- 매크로/글로벌:
- 국내(KOSPI):
- 원자력/에너지:
## 🎯 핵심 키워드 TOP 5
## ⚠️ 리스크 및 내일 주목 이벤트

[수집 데이터]
{raw_data}
"""
        print("🧠 시황 리포트 AI 분석 중...")
        response = model.generate_content(prompt_news)
        
        text = response.text
        for i in range(0, len(text), 4000):
            await client.send_message(target_room, text[i:i+4000])
            await asyncio.sleep(1)

        print("✅ 전체 전송 완료!")

    except Exception as e:
        await client.send_message('주식정리방', f"🚨 프로그램 오류 발생:\n{str(e)[:200]}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
