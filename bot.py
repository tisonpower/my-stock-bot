import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import datetime
import os

# 1. 환경 변수 로드
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

# 2. 병렬 수집 함수 (속도 최적화)
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
    # 텔레그램 로그인
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()
    
    try:
        # 3. AI 모델 설정 (고품질 분석을 위해 2.5 Flash 확정)
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        kst = datetime.timezone(datetime.timedelta(hours=9))
        now = datetime.datetime.now(kst)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        now_str = now.strftime('%Y-%m-%d %H:%M KST')

        print("🚀 병렬 수집 시작 (동시 5개 채널)...")
        semaphore = asyncio.Semaphore(5)
        tasks = [fetch_channel(client, ch, today, semaphore) for ch in target_channels]
        results = await asyncio.gather(*tasks)
        
        # 수집된 데이터 결합
        raw_data = "\n\n".join([msg for sublist in results for msg in sublist])

        if not raw_data:
            await client.send_message('@tisonpowerbot', "📥 오늘 수집된 새로운 데이터가 없습니다.")
            return

        # 4. 데이터 상한선 (토큰 제한 방어, 80,000자 제한)
        if len(raw_data) > 80000:
            raw_data = raw_data[:80000] + "\n\n...(데이터 과다로 이하 생략)"

        # 5. 전문가용 구조화 프롬프트
        prompt = f"""
당신은 20년 경력의 수석 매크로/퀀트 전략가입니다.
분석 기준 시각: {now_str}

[분석 우선순위]
1. AI 반도체 및 전력 인프라 특이 동향 (최우선)
2. 주요 매크로 지표 변화 (VIX, 환율, 금리, 유가)
3. 섹터 로테이션 및 기관/외인 자금 이동 신호

[보고서 필수 양식]
## 📊 핵심 테마 (3줄 요약)
## 🏢 섹터별 핵심 포인트
- AI/반도체:
- 매크로/글로벌:
- 국내(KOSPI/KOSDAQ):
- 기타 섹터:
## 🎯 투자 핵심 키워드 TOP 5
## ⚠️ 리스크 관리 및 내일 주목 일정

[수집된 시장 데이터]
{raw_data}
"""
        print("🧠 수석 전략가 모드로 AI 분석 중 (Gemini 2.5 Flash)...")
        response = model.generate_content(prompt)
        
        # 6. 텔레그램 4000자 단위 청크 분할 전송 (긴 리포트 짤림 방지)
        text = response.text
        max_len = 4000
        for i in range(0, len(text), max_len):
            await client.send_message('@tisonpowerbot', text[i:i+max_len])
            await asyncio.sleep(1) # 연속 전송 시 텔레그램 서버 차단 방지
        
        print("✅ 리포트 전송 완료!")

    except Exception as e:
        # 에러 발생 시 텔레그램으로 알림
        error_msg = f"🚨 리포트 자동 생성 실패\n오류: {str(e)[:200]}"
        await client.send_message('@tisonpowerbot', error_msg)
        print(error_msg)
    finally:
        # 작업이 끝나면 반드시 텔레그램 연결 종료
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
