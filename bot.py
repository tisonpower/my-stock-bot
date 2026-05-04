import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import datetime
import os

# 1. 깃허브에 숨겨둔 비밀번호 가져오기
api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']
string_session = os.environ['TELEGRAM_STRING_SESSION']
gemini_key = os.environ['GEMINI_KEY']

# 정보 수집용 텔레그램 채널들
target_channels = [
    '@FastStockNewsUSA', '@bornlupin', '@HANAchina', '@kwusa', 
    '@meritz_research', '@EarlyStock1', '@hslpartners', '@valjuman', 
    '@gaoshoukorea', '@Jstockclass', '@daishinstrategy', '@invesqz', 
    '@BRILLER_Research', '@ehdwl', '@djbmanager', '@kisthemacro', 
    '@Vegastooza', '@techkorea', '@yuantaresearch', '@SK_Research_Asset'
]

# (기능 1) 텔레그램 채널 수집 도구
async def fetch_channel(client, channel, today, semaphore):
    async with semaphore:
        messages = []
        try:
            async for message in client.iter_messages(channel, offset_date=today, reverse=True, limit=50):
                if message.text and len(message.text) > 20:
                    messages.append(f"[{channel}] {message.text}")
        except Exception:
            pass
        return messages

# (기능 2) 마크 미너비니 차트 분석 도구
def check_minervini_status(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False)
        if df.empty or len(df) < 200: return "⚠️ 상장 기간이 짧아 데이터가 부족합니다."

        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['MA150'] = df['Close'].rolling(window=150).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()

        close = float(df['Close'].iloc[-1].iloc[0] if isinstance(df['Close'].iloc[-1], pd.Series) else df['Close'].iloc[-1])
        ma50 = float(df['MA50'].iloc[-1].iloc[0] if isinstance(df['MA50'].iloc[-1], pd.Series) else df['MA50'].iloc[-1])
        ma150 = float(df['MA150'].iloc[-1].iloc[0] if isinstance(df['MA150'].iloc[-1], pd.Series) else df['MA150'].iloc[-1])
        ma200 = float(df['MA200'].iloc[-1].iloc[0] if isinstance(df['MA200'].iloc[-1], pd.Series) else df['MA200'].iloc[-1])

        is_uptrend = (close > ma50) and (ma50 > ma150) and (ma150 > ma200)
        ma200_1month_ago = float(df['MA200'].iloc[-20].iloc[0] if isinstance(df['MA200'].iloc[-20], pd.Series) else df['MA200'].iloc[-20])
        is_ma200_rising = ma200 > ma200_1month_ago

        if is_uptrend and is_ma200_rising: return "🟢 완벽한 정배열 상승 추세 (Hold 권장)"
        elif close < ma200: return "🚨 위험: 200일선 아래로 떨어졌습니다. (매도 고려)"
        elif close < ma50: return "🟡 경고: 50일선을 이탈했습니다. 단기 하락 주의."
        else: return "⚪ 베이스(바닥)를 다지는 횡보 구간입니다."
    except Exception:
        return "종목을 찾을 수 없거나 분석 중 오류가 발생했습니다."

# 메인 실행 로직
async def main():
    client = TelegramClient(StringSession(string_session), api_id, api_hash)
    await client.start()
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    now_str = now.strftime('%Y-%m-%d %H:%M KST')

    try:
        # ==========================================
        # [작업 1] 시황 뉴스 수집 및 요약 리포트 전송
        # ==========================================
        semaphore = asyncio.Semaphore(5)
        tasks = [fetch_channel(client, ch, today, semaphore) for ch in target_channels]
        results = await asyncio.gather(*tasks)
        raw_data = "\n\n".join([msg for sublist in results for msg in sublist])

        if raw_data:
            if len(raw_data) > 60000: raw_data = raw_data[:60000]
            prompt_news = f"""
당신은 수석 매크로 전략가입니다. {now_str} 기준 아래 데이터를 분석하세요.
[보고서 필수 양식]
## 📊 오늘의 핵심 테마 (3줄)
## 🏢 섹터별 핵심 동향 (AI/반도체, 매크로 등)
[수집 데이터]\n{raw_data}
"""
            response_news = model.generate_content(prompt_news)
            text = response_news.text
            
            # 텔레그램 서버 에러 방지를 위해 4000자씩 나눠서 전송
            for i in range(0, len(text), 4000):
                await client.send_message('@tisonpowerbot', text[i:i+4000])
                await asyncio.sleep(1) 
        else:
            await client.send_message('@tisonpowerbot', "📥 오늘 수집된 새로운 시장 뉴스가 없습니다.")

        # ==========================================
        # [작업 2] 내 포트폴리오 이미지 찾기 & 차트 분석 전송
        # ==========================================
        image_path = None
        
        # 봇과의 대화방에서 최근 30개 대화를 뒤져서 '가장 마지막 사진' 찾기
        async for message in client.iter_messages('@tisonpowerbot', limit=30):
            if message.photo:
                image_path = await message.download_media()
                break
                
        if image_path:
            # 사진을 구글 AI에게 보여주고 종목 기호(Ticker) 뽑아내기
            myfile = genai.upload_file(image_path)
            prompt_img = "이 주식 계좌 잔고 사진에 있는 종목명을 Yahoo Finance에서 검색 가능한 Ticker 기호로 변환해. (예: AAPL, 005930.KS). 다른 말은 쓰지 말고 쉼표로 구분된 Ticker만 한 줄로 출력해."
            response_img = model.generate_content([myfile, prompt_img])
            tickers = [t.strip() for t in response_img.text.split(',') if t.strip()]
            
            if tickers:
                report_pf = f"🎯 **[{now_str}] 내 포트폴리오 미너비니 진단 리포트**\n\n"
                # 뽑아낸 종목들 차트 분석 시작
                for ticker in tickers:
                    status = check_minervini_status(ticker)
                    report_pf += f"🔹 **{ticker}**\n   └ 상태: {status}\n\n"
                
                await client.send_message('@tisonpowerbot', report_pf)
            
            # 분석 끝난 사진 파일 삭제
            if os.path.exists(image_path):
                os.remove(image_path)
        else:
            await client.send_message('@tisonpowerbot', "📸 내 종목 분석을 원하시면, 채팅방에 주식 잔고 캡처 사진을 올려주세요!")

    except Exception as e:
        await client.send_message('@tisonpowerbot', f"🚨 프로그램 오류 발생: {str(e)[:200]}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
