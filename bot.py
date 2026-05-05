import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import datetime
import os

# 환경 변수 로드
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']
string_session = os.environ['TELEGRAM_STRING_SESSION']
gemini_key = os.environ['GEMINI_KEY']

target_channels = ['@bornlupin', '@kwusa', 
    '@meritz_research', '@EarlyStock1', '@hslpartners', '@valjuman', 
    '@Jstockclass', '@daishinstrategy','@BRILLER_Research', '@ehdwl', '@djbmanager', '@kisthemacro', 
    '@Vegastooza', '@techkorea', '@yuantaresearch', '@SK_Research_Asset'
]

# 병렬 수집 함수 (수집 속도는 빠른 상태 유지)
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

async def main():
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()
    
    try:
        # ✅ 무료 한도가 넉넉하고 안정적인 1.5 Flash 버전으로 원복
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        kst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(kst)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        now_str = now.strftime('%Y-%m-%d %H:%M KST')

        print("🚀 시장 데이터 수집 시작...")
        semaphore = asyncio.Semaphore(5)
        tasks = [fetch_channel(client, ch, today, semaphore) for ch in target_channels]
        results = await asyncio.gather(*tasks)
        
        raw_data = "\n\n".join([msg for sublist in results for msg in sublist])

        if not raw_data:
            await client.send_message('@tisonpowerbot', "📥 오늘 수집된 데이터가 없습니다.")
            return

        # ✅ 용량 에러 방지: 최대 40,000자까지만 전송
        if len(raw_data) > 40000:
            raw_data = raw_data[:40000] + "\n\n...(데이터 과다로 이하 생략)"

        # 전략가 프롬프트 유지
        prompt_news = f"""
당신은 수석 매크로/퀀트 전략가입니다. {now_str} 기준 분석하세요.

[분석 우선순위]
- AI 반도체/전력 인프라 특이 동향 최우선
- 매크로 지표 변화 (VIX, 환율, 금리, 유가)
- 섹터 로테이션 자금 이동 신호

[보고서 필수 양식]
## 📊 핵심 테마 (3줄 요약)
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
        
        # 텔레그램 메시지 잘림 방지용 분할 전송
        text = response.text
        for i in range(0, len(text), 4000):
            await client.send_message('@tisonpowerbot', text[i:i+4000])
            await asyncio.sleep(1)

        print("✅ 전체 전송 완료!")

    except Exception as e:
        await client.send_message('@tisonpowerbot', f"🚨 프로그램 오류 발생:\n{str(e)[:200]}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
