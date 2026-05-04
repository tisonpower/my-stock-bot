import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import datetime
import os

# 1. 열쇠 가져오기
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH'])
string_session = os.environ['TELEGRAM_STRING_SESSION']
gemini_key = os.environ['GEMINI_KEY']

target_channels = [
    '@FastStockNewsUSA', '@bornlupin', '@HANAchina', '@kwusa', 
    '@meritz_research', '@EarlyStock1', '@hslpartners', '@valjuman', 
    '@gaoshoukorea', '@Jstockclass', '@daishinstrategy', '@invesqz', 
    '@BRILLER_Research', '@ehdwl', '@djbmanager', '@kisthemacro', 
    '@Vegastooza', '@techkorea', '@yuantaresearch', '@SK_Research_Asset'
]

async def main():
    # 모델 버전을 1.5 Flash로 낮추어 한도 문제를 해결합니다.
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(hour=0, minute=0, second=0, microsecond=0)
    now_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
    
    raw_data = ""
    print("🚀 데이터 수집 중...")
    
    for channel in target_channels:
        try:
            async for message in client.iter_messages(channel, offset_date=today, reverse=True, limit=50):
                if message.text and len(message.text) > 20:
                    raw_data += f"[{channel}] {message.text}\n\n"
        except Exception as e:
            print(f"Error: {e}")

    if raw_data:
        try:
            print("🧠 AI 분석 중 (Gemini 1.5 Flash)...")
            prompt = f"수석 전략가로서 다음 데이터를 요약 분석해 리포트를 작성하세요. 시각: {now_str}\n\n{raw_data}"
            response = model.generate_content(prompt)
            await client.send_message('@tisonpowerbot', response.text)
            print("✅ 리포트 전송 성공!")
        except Exception as ai_err:
            # AI 한도가 또 걸릴 경우를 대비해 수집된 원문이라도 보냅니다.
            await client.send_message('@tisonpowerbot', f"⚠️ AI 한도 초과로 원문 요약본만 송신합니다.\n\n{raw_data[:500]}...")
    else:
        await client.send_message('@tisonpowerbot', "📥 현재 수집된 새로운 시장 데이터가 없습니다.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
