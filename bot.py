import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import datetime
import os

# 1. 환경 변수에서 열쇠 가져오기
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
    # 2. AI 모델 설정 (Gemini 1.5 Flash 사용)
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # 3. 텔레그램 로그인
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()

    # 4. 날짜 및 시간 설정 (한국 시간 기준)
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(hour=0, minute=0, second=0, microsecond=0)
    now_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
    
    raw_data = ""
    print("🚀 시장 데이터 수집 시작...")
    
    for channel in target_channels:
        try:
            async for message in client.iter_messages(channel, offset_date=today, reverse=True, limit=50):
                if message.text and len(message.text) > 20:
                    raw_data += f"[{channel}] {message.text}\n\n"
        except Exception as e:
            print(f"채널 수집 중 오류: {e}")

    # 5. 리포트 생성 및 전송
    if raw_data:
        try:
            print("🧠 AI 분석 중...")
            prompt = f"당신은 20년 경력의 주식 전문가입니다. {now_str} 기준 다음 수집된 정보를 요약 분석하여 투자 리포트를 작성하세요.\n\n{raw_data}"
            response = model.generate_content(prompt)
            
            await client.send_message('@tisonpowerbot', response.text)
            print("✅ 전송 성공!")
        except Exception as ai_e:
            await client.send_message('@tisonpowerbot', f"⚠️ AI 분석 오류 발생. 수집된 데이터 일부를 전송합니다.\n\n{raw_data[:500]}")
    else:
        await client.send_message('@tisonpowerbot', "📥 오늘 수집된 데이터가 없습니다.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
