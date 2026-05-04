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
    # 2. AI 모델 설정 (최신형 Gemini 3 Flash 모델로 원복)
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-3-flash')
    
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
        except Exception:
            pass

    # 5. 리포트 생성 및 전송
    if raw_data:
        try:
            # 안전장치: 데이터가 너무 방대하면 AI가 읽기 편하게 앞부분 20,000자만 사용
            if len(raw_data) > 20000:
                raw_data = raw_data[:20000] + "\n\n...(이하 생략)"

            print("🧠 AI 분석 중...")
            prompt = f"당신은 주식 투자 전문가입니다. {now_str} 기준 수집된 정보를 바탕으로 인사이트 중심의 투자 리포트를 작성하세요.\n\n{raw_data}"
            response = model.generate_content(prompt)
            
            await client.send_message('@tisonpowerbot', response.text)
            print("✅ 전송 성공!")
        except Exception as ai_e:
            # 한도 초과 시 메시지
            await client.send_message('@tisonpowerbot', f"⚠️ 구글 AI 한도 초과로 요약이 불가능합니다. 수집된 원문 일부를 전송합니다.\n\n{raw_data[:500]}")
    else:
        await client.send_message('@tisonpowerbot', "📥 현재 수집된 새로운 시장 데이터가 없습니다.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
