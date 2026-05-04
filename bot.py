import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import datetime
import os

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
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()

    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).replace(hour=0, minute=0, second=0, microsecond=0)
    now_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')
    
    raw_data = ""
    for channel in target_channels:
        try:
            async for message in client.iter_messages(channel, offset_date=today, reverse=True, limit=50):
                if message.text and len(message.text) > 20:
                    raw_data += f"[{channel}] {message.text}\n\n"
        except Exception:
            pass # 에러 메시지 생략

    if raw_data:
        try:
            # 💡 [핵심 수정] 데이터가 너무 길면 앞에서부터 15,000자까지만 자릅니다.
            max_length = 15000 
            if len(raw_data) > max_length:
                raw_data = raw_data[:max_length] + "\n\n... (데이터가 너무 길어 일부 생략됨)"
                
            prompt = f"당신은 20년 경력의 주식 전략가입니다. {now_str} 기준 다음 수집된 정보를 요약 분석하여 투자 리포트를 작성하세요.\n\n{raw_data}"
            response = model.generate_content(prompt)
            await client.send_message('@tisonpowerbot', response.text)
            print("✅ 분석 리포트 전송 성공!")
            
        except Exception as ai_e:
            # 혹시라도 또 에러가 나면 무슨 에러인지 상세히 출력
            print(f"AI 에러 상세: {ai_e}") 
            await client.send_message('@tisonpowerbot', f"⚠️ AI 분석 오류 발생. 수집된 데이터 일부 전송:\n\n{raw_data[:500]}")
    else:
        await client.send_message('@tisonpowerbot', "📥 오늘 수집된 데이터가 없습니다.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
