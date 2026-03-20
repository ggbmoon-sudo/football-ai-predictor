import streamlit as st
import requests
import datetime
import pandas as pd
import time
import re
from playwright.sync_api import sync_playwright
import os
import subprocess
from openai import OpenAI  # <--- 改用通用的 OpenAI 客戶端來串接第三方 URL

# ==========================================
# 🔧 雲端環境自動修復：安裝 Playwright 瀏覽器
# ==========================================
def install_playwright_browsers():
    cache_path = "/home/appuser/.cache/ms-playwright"
    if not os.path.exists(cache_path):
        with st.spinner("首次執行：正在為雲端伺服器安裝 Chromium 瀏覽器（需時約 1-2 分鐘）..."):
            try:
                subprocess.run(["playwright", "install", "chromium"], check=True)
                subprocess.run(["playwright", "install-deps"], check=True)
                st.success("✅ 瀏覽器安裝成功！")
            except Exception as e:
                st.error(f"❌ 瀏覽器安裝失敗: {e}")

install_playwright_browsers()

# ==========================================
# ⚙️ 1. 安全設定與 AI 代理初始化
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    FOOTBALL_API_KEY = st.secrets["FOOTBALL_API_KEY"]
except KeyError:
    st.error("❌ 請在 Secrets 設定 GEMINI_API_KEY 與 FOOTBALL_API_KEY")
    st.stop()

# 初始化通用 AI 客戶端，指向你的專屬 URL
client = OpenAI(
    api_key=GEMINI_API_KEY,
    # 👇 關鍵修改：必須是 https，否則會發生重導向導致 POST 變成 GET
    base_url="https://api.mttieeo.com/v1" 
)
# 設定你的專屬模型名稱
MODEL_NAME = "[F]gemini-2.5-flash"

# 擴充版聯賽清單 (已新增日職百年構想聯賽、南韓K1聯賽等)
LEAGUE_IDS = {
    "英格蘭超級聯賽": 39, "西班牙甲組聯賽": 140, "西班牙乙組聯賽": 141,
    "意大利甲組聯賽": 135, "德國甲組聯賽": 78, "德國乙組聯賽": 79,
    "荷蘭甲組聯賽": 88, "荷蘭乙組聯賽": 89, "葡萄牙超級聯賽": 94,
    "英格蘭冠軍聯賽": 40, "阿根廷甲組聯賽": 128, "巴西甲組聯賽": 71,
    "智利甲組聯賽": 265, "烏拉圭甲組聯賽": 268, "美國職業聯賽 (MLS)": 253,
    "澳洲職業聯賽": 188, "阿聯酋職業聯賽": 301, "泰國甲組聯賽": 296,
    "沙特職業聯賽": 307, "歐洲聯賽冠軍盃": 2, "歐霸盃": 3, "歐洲協會聯賽": 848,
    "中北美洲冠軍盃": 16, "挪威盃": 104, "葡萄牙盃": 96, "巴西盃": 73,
    "阿根廷盃": 130, "智利盃": 266, "澳洲盃": 191, "俄羅斯盃": 237,
    "法國足總盃": 66, "英格蘭甲組聯賽": 41, "卡塔爾超級聯賽": 153,
    
    # 👇 本次新增的亞洲區聯賽
    "日職百年構想聯賽 (J3)": 100, 
    "日本職業聯賽 (J1)": 98,       # 順便幫你把 J1 主聯賽也補上，防漏
    "日本職業聯賽 (J2)": 99,       # 順便幫你把 J2 也補上
    "南韓K1聯賽": 292
}

# ==========================================
# 🧠 2. 工具函數：中文化與時區轉換
# ==========================================

def convert_to_hkt(utc_date_str):
    utc_dt = datetime.datetime.fromisoformat(utc_date_str.replace('Z', '+00:00'))
    hkt_dt = utc_dt + datetime.timedelta(hours=8)
    return hkt_dt.strftime("%m-%d %H:%M")

# 利用 AI 批量翻譯隊名 (強化除錯版)
def translate_match_names(match_list):
    if not match_list: return []
    names_to_translate = "\n".join(match_list)
    
    # 強化 Prompt，強制 AI 絕對不能說廢話
    prompt = f"""
    任務：將以下足球對陣清單翻譯為「香港繁體中文」（如：Arsenal vs Chelsea 翻譯為 阿仙奴 vs 車路士）。
    嚴格要求：
    1. 只能回傳翻譯後的對陣，每一行一個對陣。
    2. 絕對不要加上任何開場白、結尾語、或 Markdown 標記 (如 ```)。
    3. 必須保留 'vs' 字眼。
    
    待翻譯清單：
    {names_to_translate}
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                # 加入 System Prompt 設定機器人性格
                {"role": "system", "content": "你是一個專業的足球翻譯機器人，只輸出翻譯結果，絕對不說其他廢話。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3 # 降低隨機性，讓輸出格式更穩定
        )
        
        # 抓取 AI 回傳的純文字
        raw_output = response.choices[0].message.content.strip()
        
        # 移除可能不小心產生的 markdown 標記
        raw_output = raw_output.replace("```text", "").replace("```", "")
        
        # 將文字按行切分，過濾掉空行，並且確保該行有 'vs' 這個字
        translated = [line.strip() for line in raw_output.split('\n') if line.strip() and 'vs' in line.lower()]
        
        # 如果翻譯過濾後的數量與原始清單一致，就成功替換
        if len(translated) == len(match_list):
            return translated
        else:
            # 如果還是失敗，可以把這行印在終端機看看 AI 到底回傳了什麼搗亂的字
            print(f"翻譯行數不符。原:{len(match_list)}行, 翻:{len(translated)}行")
            return match_list
            
    except Exception as e:
        print(f"翻譯請求發生錯誤: {e}")
        return match_list

# ==========================================
# 🧠 AI 分析核心函數 (強化角球與戰術分析)
# ==========================================
def deep_analyze_agent(match_name):
    prompt = f"""
    【系統指令：啟動「蒙地卡羅大數據」與「戰術行為學」預測引擎】
    角色：你是一位擁有 20 年經驗、專為頂級辛迪加(Syndicate)服務的足球博彩精算師。
    
    🎯 目標賽事：{match_name}
    🚨【極重要時區警告】：上述標示的時間為「香港時間 (HKT, UTC+8)」。歐洲當地時間或國際莊家盤口（如 Bet365）通常標示為 UTC 或當地時區（比香港慢 7-8 小時）,並年度一定是現在(2026年)並自行將 (HKT, UTC+8) 換算回歐洲當地時間。
        賽事絕對存在 (無視升降級迷思)：這場比賽已經被官方 API 確認存在！絕對不可因為你內部的歷史數據（例如認定盧頓在英超/英冠）而質疑這場比賽。球隊會有升級與降級，請「無條件接受」他們目前正在這個聯賽對戰的事實！
        禁止罷工：絕對不允許以「查無此賽事」、「時間衝突」或「聯賽級別矛盾」為由中止分析。請直接利用你所能找到的雙方最新戰術特徵、傷停情報與歷史 H2H 數據，強制完成深度推演！

    請聯網檢索最新資訊，並執行以下極度深度的四步推演邏輯，任何敷衍或表面的分析都將不被接受：

    第一步：【進球與失球模型 (xG/xGA) 拆解】
    - 檢索雙方近 5 場的 xG (預期進球) 與 xGA (預期失球)，對比實際進球數。判斷哪隊在前場運氣好/把握力強，哪隊後防有隱患。
    - 分析雙方主客場的進球分佈差異。

    第二步：【戰術相剋與陣容缺陷推演】
    - 檢索最新傷停名單。特別點出「防線核心、中場節奏控制器、主力射手」缺陣對攻防轉換的具體影響。
    - 戰術推演：主隊的進攻發起方式（邊路傳中/中路滲透/防守反擊）是否剛好剋制客隊的防守弱點（如：防空能力差、兩翼身後空檔大）？

    第三步：【環境、戰意與莊家資金劇本】
    - 檢索當地即時天氣與場地狀況（雨天易致失誤、影響短傳與大細盤）。
    - 判斷雙方戰意（爭冠/保級/盃賽輪換/魔鬼賽程體能透支）。
    - 檢視各大莊家（Bet365, HKJC）的初盤至現盤走勢。大細盤與讓球盤的水位變動，暗示了莊家預期這是一場「沉悶防守戰」還是「對攻大戰」？

    第四步：【角球矩陣推算 (Corner Matrix)】
    - 根據上述的控球率預測、邊路進攻依賴度（下底傳中頻率）、以及落後方反撲的機率，推算本場總角球數與分佈。

    【最終精算結論】
    請綜合以上所有變數，給出最具說服力的理據，並在報告最末端嚴格以獨立的行數輸出以下標籤（勿加其他符號）：
    [Score: X-Y]  (這裡必須給出概率最高的最穩比分)
    [Corners: X-Y] (這裡給出總角球數區間，如 9-11)
    [Rec: 這裡填寫 1 個最穩投注選項，如：大2.5、主勝、客+1、角球大10.5]
    [Win_Conf: X%] (勝負/讓球盤信心度，0-100)
    [Corner_Conf: X%] (角球預測信心度，0-100)
    """
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一位擁有 20 年經驗的足球精算師，尤其擅長透過球隊戰術與歷史數據推算角球數量及比分。"},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content
        if not content: return "AI 未能生成報告"
        return content
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota" in error_msg: return "⚠️ ERROR_QUOTA_EXCEEDED"
        return f"API 錯誤: {error_msg}"

# ==========================================
# 📡 3. 數據抓取
# ==========================================
@st.cache_data(ttl=3600)
def get_global_matches():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today}"
    headers = {'x-apisports-key': FOOTBALL_API_KEY}
    try:
        r = requests.get(url, headers=headers)
        return r.json().get('response', [])
    except:
        return []

# ==========================================
# 🎨 4. APP 介面
# ==========================================
st.set_page_config(page_title="AI 足球精算控制台", layout="wide")
tab1, tab2 = st.tabs(["🎯 AI 深度預測", "📡 馬會賠率雷達"])

# ------------------------------------------
# TAB 1: AI 深度預測
# ------------------------------------------
with tab1:
    st.header("⚽ 指定賽事深度分析 (HKT 版)")
    selected_leagues = st.multiselect("選擇聯賽 (可多選)：", list(LEAGUE_IDS.keys()))
    
    if st.button("加載今日賽程"):
        with st.spinner("正在抓取數據並自動翻譯中..."):
            all_data = get_global_matches()
            ids = [LEAGUE_IDS[n] for n in selected_leagues]
            filtered_matches = [m for m in all_data if m['league']['id'] in ids]
            
            if filtered_matches:
                REVERSE_LEAGUE_IDS = {v: k for k, v in LEAGUE_IDS.items()}
                raw_names = [f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}" for m in filtered_matches]
                translated_names = translate_match_names(raw_names)
                
                display_matches = []
                for i, m in enumerate(filtered_matches):
                    # 解析原始 UTC 時間
                    utc_str = m['fixture']['date']
                    utc_dt = datetime.datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
                    
                    # 計算 HKT 時間 (UTC+8)
                    hkt_dt = utc_dt + datetime.timedelta(hours=8)
                    
                    # 格式化雙時區字串 (例如: 03-18 03:45 HKT (UTC 19:45))
                    hkt_time_str = hkt_dt.strftime("%m-%d %H:%M")
                    utc_time_str = utc_dt.strftime("%H:%M")
                    time_display = f"{hkt_time_str} HKT (UTC {utc_time_str})"
                    
                    league_id = m['league']['id']
                    league_cn = REVERSE_LEAGUE_IDS.get(league_id, m['league']['name'])
                    
                    # 將雙時區與聯賽名一起塞入顯示字串
                    display_matches.append({
                        "display": f"[{league_cn}] {time_display} | {translated_names[i]}",
                        "raw": f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}"
                    })
                st.session_state['display_matches'] = display_matches
                st.sidebar.success(f"已加載 {len(display_matches)} 場賽事")
            else:
                st.warning("所選聯賽今日暫無賽程。")

    if 'display_matches' in st.session_state:
        choices = [m['display'] for m in st.session_state['display_matches']]
        targets = st.multiselect("勾選欲分析的場次：", choices)
        
        if st.button("🚀 執行批量 AI 精算分析"):
            summary_data = []
            
            def safe_extract(pattern, text, default="N/A"):
                if not text: return default
                match = re.search(pattern, text)
                return match.group(1).strip() if match else default

            for t in targets:
                with st.status(f"正在深度分析: {t}...", expanded=True) as status:
                    st.write("🌐 正在獲取聯網數據、戰術特徵與賠率走勢...")
                    report = deep_analyze_agent(t)
                    
                    if report == "⚠️ ERROR_QUOTA_EXCEEDED":
                        st.error("🚫 API 額度已耗盡，請檢查代理伺服器狀態。")
                        break
                    
                    st.write("📊 正在解析勝負與角球精算標籤...")
                    
                    # 提取文字結果
                    score = safe_extract(r"\[Score:\s*(.*?)\]", report)
                    corners = safe_extract(r"\[Corners:\s*(.*?)\]", report)
                    rec = safe_extract(r"\[Rec:\s*(.*?)\]", report)
                    
                    # 提取勝負信心 %
                    win_match = re.search(r"\[Win_Conf:\s*(\d+)%?\]", report)
                    win_conf = int(win_match.group(1)) if win_match else 50
                    
                    # 提取角球信心 % (新增)
                    cor_match = re.search(r"\[Corner_Conf:\s*(\d+)%?\]", report)
                    cor_conf = int(cor_match.group(1)) if cor_match else 50
                    
                    summary_data.append({
                        "賽事": t, 
                        "比分": score, 
                        "角球": corners, 
                        "推薦": rec, 
                        "勝負信心%": win_conf,   # 區分勝負
                        "角球信心%": cor_conf,   # 區分角球
                        "報告": report
                    })
                    
                    st.markdown(f"### {t} 分析簡報")
                    st.markdown(report)
                    st.divider()
                    
                    time.sleep(2)
                    status.update(label=f"✅ {t} 完成", state="complete", expanded=False)

            if summary_data:
                st.subheader("📋 批量分析決策中心")
                df = pd.DataFrame(summary_data)
                
                # 更新表格欄位，同時顯示勝負與角球信心
                st.table(df[["賽事", "比分", "角球", "推薦", "勝負信心%", "角球信心%"]])
                
                # 雙圖表顯示：一眼看出哪場適合買波膽，哪場適合買角球
                col1, col2 = st.columns(2)
                with col1:
                    st.write("🎯 勝負預測信心")
                    st.bar_chart(df.set_index("賽事")["勝負信心%"])
                with col2:
                    st.write("🚩 角球預測信心")
                    st.bar_chart(df.set_index("賽事")["角球信心%"], color="#ff2b2b") # 角球圖表改用紅色方便區分

# ------------------------------------------
# TAB 2: 馬會賠率雷達
# ------------------------------------------
with tab2:
    st.header("🕵️‍♂️ 馬會即時盤口監測")
    if st.button("🔍 開始全自動巡邏"):
        with st.status("啟動監測...", expanded=True) as status:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = context.new_page()
                    
                    alerts = []
                    
                    status.write("🌐 正在巡邏主客和盤口...")
                    page.goto("https://bet.hkjc.com/ch/football/home", wait_until="networkidle")
                    page.wait_for_timeout(5000)
                    
                    # (此處保留了你原本提供的完整掃描邏輯結構)
                    homes = page.locator('[data-testid$="_homeTeam"]').all()
                    aways = page.locator('[data-testid$="_awayTeam"]').all()
                    h_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_H_odds"]').all()
                    d_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_D_odds"]').all()
                    a_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_A_odds"]').all()

                    for i in range(min(len(homes), len(h_odds))):
                        h, d, a = h_odds[i].inner_text(), d_odds[i].inner_text(), a_odds[i].inner_text()
                        if (h=="2.14" and d=="3.00" and a=="3.00") or (h=="3.00" and d=="3.00" and a=="2.14"):
                            alerts.append(f"🚨 [HAD] {homes[i].inner_text()} vs {aways[i].inner_text()} ({h}/{d}/{a})")

                    # 掃描 HHA 讓球主客和
                    status.write("🌐 正在掃描讓球主客和 (/hha)...")
                    page.goto("https://bet.hkjc.com/ch/football/hha", wait_until="networkidle")
                    page.wait_for_timeout(5000)
                    hha_homes = page.locator('[data-testid$="_homeTeam"]').all()
                    hha_conds = page.locator('div[data-testid*="_HHA_"].cond').all()
                    hha_odds = page.locator('span[data-testid*="_HHA_"][data-testid$="_H_odds"]').all()
                    
                    for i in range(min(len(hha_homes), len(hha_odds))):
                        if "-1" in hha_conds[i].inner_text() and hha_odds[i].inner_text()=="3.10":
                            alerts.append(f"🚨 [HHA] {hha_homes[i].inner_text()} 讓球-1 @ 3.10")

                    # 掃描 HIL 入球大細
                    status.write("🌐 正在掃描入球大細 (/hil)...")
                    page.goto("https://bet.hkjc.com/ch/football/hil", wait_until="networkidle")
                    page.wait_for_timeout(5000)
                    hil_homes = page.locator('[data-testid$="_homeTeam"]').all()
                    hil_odds = page.locator('span[data-testid*="_HIL_"][data-testid$="_H_odds"]').all()
                    
                    for i in range(min(len(hil_homes), len(hil_odds))):
                        if hil_odds[i].inner_text()=="1.66":
                            alerts.append(f"🚨 [HIL] {hil_homes[i].inner_text()} 大細 @ 1.66")

                    browser.close()
                    status.update(label="✅ 巡邏結束", state="complete")
                    if alerts:
                        st.success(f"發現 {len(alerts)} 場符合條件賽事！")
                        for a in alerts: st.warning(a)
                    else: st.write("目前無符合條件。")
            except Exception as e: st.error(f"雷達報錯: {e}")
