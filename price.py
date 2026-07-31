import asyncio
import requests
import json
from telethon import TelegramClient
from telethon.sessions import StringSession
import datetime
import os

# --- 환경 변수 로드 ---
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']
string_session = os.environ['TELEGRAM_STRING_SESSION']

kis_app_key = os.environ.get('KIS_APP_KEY', '')
kis_app_secret = os.environ.get('KIS_APP_SECRET', '')

# --- 한국투자증권 API 통신 함수 ---
def get_kis_access_token():
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": kis_app_key, "appsecret": kis_app_secret}
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        if res.status_code == 200:
            return res.json().get("access_token")
    except Exception as e:
        print(f"토큰 에러: {e}")
    return None

def get_kis_stock_price(token, ticker):
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": kis_app_key,
        "appsecret": kis_app_secret,
        "tr_id": "FHKST01010100"
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker}
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code == 200:
            data = res.json().get("output", {})
            if data:
                return {"현재가": int(data.get("stck_prpr", 0)), "등락률": float(data.get("prdy_ctrt", 0))}
    except Exception as e:
        print(f"가격 에러: {e}")
    return None

# --- 메인 실행 함수 ---
async def main():
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()
    
    try:
        # 💡 [여기가 해결책입니다!] 로봇이 방 이름을 찾을 수 있도록 채팅방 목록을 먼저 불러옵니다.
        print("🔄 텔레그램 채팅방 목록 찾는 중...")
        await client.get_dialogs()

        kst = datetime.timezone(datetime.timedelta(hours=9))
        now_str = datetime.datetime.now(kst).strftime('%Y-%m-%d %H:%M KST')

        kis_token = get_kis_access_token()
        if not kis_token:
            await client.send_message('주식정리방', "KIS 토큰 발급에 실패했습니다.")
            return

        tickers = {
            "005930": "삼성전자", 
            "000660": "SK하이닉스", 
            "069500": "KODEX 200",
            "133690": "TIGER 미국나스닥100"
        }
        
        market_data_lines = [f"📊 **[{now_str} 관심 종목 및 지수 현황]**\n"]
        
        for code, name in tickers.items():
            price_info = get_kis_stock_price(kis_token, code)
            if price_info:
                sign = "+" if price_info['등락률'] > 0 else ""
                market_data_lines.append(f"• {name}: {price_info['현재가']:,}원 ({sign}{price_info['등락률']}%)")
        
        final_message = "\n".join(market_data_lines)
        
        await client.send_message('주식정리방', final_message)
        print("✅ 주가 전송 완료!")

    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
