import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import yfinance as yf
import pandas as pd
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

# 병렬 수집 함수
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

# ✅ 티커 유효성 검사 함수 (한국 주식 및 잘못된 티커 걸러내기)
def validate_ticker(ticker):
    try:
        test = yf.Ticker(ticker).fast_info
        return hasattr(test, 'last_price') and test.last_price is not None
    except:
        return False

# ✅ 미너비니 진단 및 ATR 손절가 계산 함수
def check_minervini_status(ticker):
    try:
        # 버그 1 수정: 200일선 계산을 위해 18개월 데이터 확보
        df = yf.download(ticker, period="18mo", progress=False)
        if len(df) < 200: 
            return f"⚠️ {ticker}: 데이터 부족 (상장 200일 미만)"
        
        close = float(df['Close'].iloc[-1])
        sma50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
        sma150 = float(df['Close'].rolling(window=150).mean().iloc[-1])
        sma200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
        high_52w = float(df['High'].rolling(window=252).max().iloc[-1])
        low_52w = float(df['Low'].rolling(window=252).min().iloc[-1])

        # 미너비니 조건 검사
        cond1 = close > sma150 and close > sma200
        cond2 = sma150 > sma200
        cond3 = sma50 > sma150 and sma50 > sma200
        cond4 = close > sma50
        cond5 = close >= low_52w * 1.3
        cond6 = close >= high_52w * 0.75

        # 개선 2 반영: ATR 기반 손절가 계산
        high = df['High'].squeeze()
        low = df['Low'].squeeze()
        prev_close = df['Close'].squeeze().shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        atr14 = float(tr.rolling(14).mean().iloc[-1])
        atr_stop = close - (atr14 * 2.5)

        status_str = "🟢 강세 (미너비니 조건 충족)" if all([cond1, cond2, cond3, cond4, cond5, cond6]) else "🔴 조정/약세"
        
        result = f"📌 {ticker} 현재가: ${close:.2f} ({status_str})\n"
        result += f"   └ ATR 손절가: ${atr_stop:.2f} (현재가 대비 {(atr_stop/close-1)*100:.1f}%)"
        return result
    except Exception as e:
        return f"⚠️ {ticker}: 분석 오류"

async def main():
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()
    
    try:
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
            await client.send_message('@tisonpowerbot', "📥 오늘 수집된 데이터 없음")
            return

        if len(raw_data) > 60000:
            raw_data = raw_data[:60000] + "\n\n...(이하 생략)"

        # 개선 3 반영: 구조화된 퀀트 전문가 프롬프트
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
        
        # 텔레그램 분할 전송
        text = response.text
        for i in range(0, len(text), 4000):
            await client.send_message('@tisonpowerbot', text[i:i+4000])
            await asyncio.sleep(1)

        # ----------------------------------------------------
        # 📸 포트폴리오 이미지 기반 분석 플로우 (Gemini 파일 삭제 포함)
        # ----------------------------------------------------
        # (주의: image_path는 텔레그램 등에서 다운로드 받은 이미지 경로를 가정합니다)
        image_path = "portfolio.jpg" 
        
        if os.path.exists(image_path):
            print("📸 포트폴리오 이미지 분석 시작...")
            # 버그 2 반영: Gemini 서버 파일 삭제 보장 로직
            myfile = genai.upload_file(image_path)
            try:
                prompt_img = "이 포트폴리오 이미지에 있는 주식 티커(알파벳)만 쉼표(,)로 구분해서 나열해줘."
                response_img = model.generate_content([myfile, prompt_img])
                
                tickers_raw = [t.strip().upper() for t in response_img.text.split(',') if t.strip()]
                
                # 티커 유효성 검증
                valid_tickers = [t for t in tickers_raw if validate_ticker(t)]
                invalid_tickers = set(tickers_raw) - set(valid_tickers)
                
                report_pf = "\n\n📈 [포트폴리오 종목 미너비니 & ATR 진단]\n\n"
                
                if invalid_tickers:
                    report_pf += f"⚠️ 인식 불가 종목(또는 한국주식): {', '.join(invalid_tickers)}\n\n"

                for t in valid_tickers:
                    report_pf += check_minervini_status(t) + "\n\n"
                
                # 진단 결과 전송
                for i in range(0, len(report_pf), 4000):
                    await client.send_message('@tisonpowerbot', report_pf[i:i+4000])
                    await asyncio.sleep(1)
                    
            finally:
                # 무조건 실행되어 서버 및 로컬 찌꺼기를 치우는 청소부 로직
                genai.delete_file(myfile.name)
                if os.path.exists(image_path):
                    os.remove(image_path)
                    
        print("✅ 전체 전송 완료!")

    except Exception as e:
        await client.send_message('@tisonpowerbot', f"🚨 프로그램 오류 발생:\n{str(e)[:200]}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
