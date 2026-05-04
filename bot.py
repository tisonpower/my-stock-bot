import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import datetime
import os

# 1. 깃허브 Secrets에 저장한 열쇠들을 가져옵니다.
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']
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
    # Gemini 설정
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 텔레그램 로그인 (문자열 출입증 사용)
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()

    # 오늘 날짜 설정 (한국 시간 기준)
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(hour=0, minute=0, second=0, microsecond=0)
    now_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
    
    raw_data = ""
    print("🚀 데이터 수집 시작...")
    
    for channel in target_channels:
        try:
            async for message in client.iter_messages(channel, offset_date=today, reverse=True, limit=50):
                if message.text and len(message.text) > 20:
                    raw_data += f"[{channel}] {message.text}\n\n"
        except Exception as e:
            print(f"Error fetching {channel}: {e}")

    if raw_data:
        print("🧠 AI 분석 중...")
        prompt = f"당신은 20년 경력 수석 전략가입니다. 분석 시각 {now_str}. 다음 데이터를 요약 분석하여 투자 리포트를 작성하세요: {raw_data}"
        response = model.generate_content(prompt)
        
        # 주인님의 비서 봇(@tisonpowerbot)으로 리포트 전송
        await client.send_message('@tisonpowerbot', response.text)
        print("✅ 리포트 전송 완료!")
    else:
        print("📥 수집된 데이터가 없습니다.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
