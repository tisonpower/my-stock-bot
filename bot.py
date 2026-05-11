import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import datetime
import os

# 1. 환경 변수 로드 (GitHub Secrets에서 안전하게 가져옵니다)
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']
string_session = os.environ['TELEGRAM_STRING_SESSION']
gemini_key = os.environ['GEMINI_KEY']

# 주인님이 직접 선별하신 채널 리스트
target_channels = [
    '@bornlupin', '@kwusa', '@meritz_research', '@EarlyStock1', 
    '@hslpartners', '@valjuman', '@Jstockclass', '@daishinstrategy', 
    '@BRILLER_Research', '@ehdwl', '@djbmanager', '@kisthemacro', 
    '@Vegastooza', '@techkorea', '@yuantaresearch', '@SK_Research_Asset'
]

# 병렬 수집 함수 (속도와 안정성을 동시에 잡는 방식)
async def fetch_channel(client, channel, today, semaphore):
    async with semaphore:
        messages = []
        try:
            async for message in client.iter_messages(channel, offset_date=today, reverse=True, limit=50):
                if message.text and len(message.text) > 20:
                    messages.append(f"[{channel}] {message.text}")
        except Exception as e:
            print(f"[{channel}] 수집 중 오류 발생(무시하고 진행): {e}")
        return messages

async def main():
    # 텔레그램 로봇 접속 시작
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()
    
    try:
        # 2. 고성능 AI 모델 설정 (2.5 Flash)
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 한국 시간 기준 설정
        kst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(kst)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        now_str = now.strftime('%Y-%m-%d %H:%M KST')

        print("🚀 시장 데이터 병렬 수집 시작...")
        semaphore = asyncio.Semaphore(5) # 동시에 5개 채널씩 작업
        tasks = [fetch_channel(client, ch, today, semaphore) for ch in target_channels]
        results = await asyncio.gather(*tasks)
        
        # 수집된 모든 글을 하나로 합침
        raw_data = "\n\n".join([msg for sublist in results for msg in sublist])

        # 배달 장소 설정: '주식정리방'
        target_room = '주식정리방'

        if not raw_data:
            await client.send_message(target_room, "📥 오늘 수집된 데이터가 없습니다.")
            return

        # 3. 데이터 용량 제한 (주인님이 설정하신 40,000자)
        if len(raw_data) > 40000:
            raw_data = raw_data[:40000] + "\n\n...(데이터 과다로 일부 생략됨)"

        # 4. 수석 전략가 모드 프롬프트
        prompt_news = f"""
당신은 20년 경력의 수석 매크로/퀀트 전략가입니다. 
분석 기준 시각: {now_str}

[분석 우선순위]
- AI 반도체 및 전력 인프라 특이 동향 (최우선)
- 매크로 지표 변화 (VIX, 환율, 금리, 유가)
- 섹터 로테이션 및 자금 이동 신호

[보고서 필수 양식]
## 📊 핵심 테마 (3줄 요약)
## 🏢 섹터별 분석
- AI/반도체:
- 매크로/글로벌:
- 국내(KOSPI):
- 원자력/에너지:
## 🎯 핵심 키워드 TOP 5
## ⚠️ 리스크 및 내일 주목 일정

[수집 데이터]
{raw_data}
"""
        print("🧠 시황 리포트 AI 분석 중...")
        response = model.generate_content(prompt_news)
        
        # 5. 텔레그램 메시지 전송 (4000자씩 나눠서 안전하게 배달)
        text = response.text
        for i in range(0, len(text), 4000):
            await client.send_message(target_room, text[i:i+4000])
            await asyncio.sleep(1) # 연속 전송 방지용 휴식

        print("✅ 모든 리포트가 비밀방으로 전송되었습니다!")

    except Exception as e:
        # 에러 발생 시에도 비밀방으로 알림을 보냅니다.
        await client.send_message('주식정리방', f"🚨 프로그램 오류 발생:\n{str(e)[:200]}")
    finally:
        # 모든 작업 후 연결 종료
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
