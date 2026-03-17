import streamlit as st
import requests
import google.generativeai as genai
import datetime
import pandas as pd
import time
import re
from playwright.sync_api import sync_playwright
import os

# ==========================================
# 🔧 雲端環境自動修復：安裝 Playwright 瀏覽器
# ==========================================
def install_playwright_browsers():
    # 檢查是否已經安裝過，避免每次執行都重複下載浪費時間
    if not os.path.exists("/home/appuser/.cache/ms-playwright"):
        with st.spinner("首次執行：正在為雲端伺服器安裝 Chromium 瀏覽器..."):
            os.system("playwright install chromium")
            # 某些環境需要額外安裝系統依賴
            os.system("playwright install-deps")

# 在程式一開始就執行
install_playwright_browsers()
# ==========================================
# ⚙️ 1. 安全設定
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    FOOTBALL_API_KEY = st.secrets["FOOTBALL_API_KEY"]
except KeyError:
    st.error("❌ 請在 Secrets 設定 GEMINI_API_KEY 與 FOOTBALL_API_KEY")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# 擴充版聯賽清單 (新增你要求的盃賽與聯賽)
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
    "法國足總盃": 66, "英格蘭甲組聯賽": 41, "卡塔爾超級聯賽": 153
}

# ==========================================
# 🧠 2. 工具函數：中文化與時區轉換
# ==========================================

# 將 UTC 時間轉為香港時間 (HKT)
def convert_to_hkt(utc_date_str):
    # API 傳回格式如 2026-03-17T21:00:00+00:00
    utc_dt = datetime.datetime.fromisoformat(utc_date_str.replace('Z', '+00:00'))
    hkt_dt = utc_dt + datetime.timedelta(hours=8)
    return hkt_dt.strftime("%m-%d %H:%M")

# 利用 AI 批量翻譯隊名 (節省流量與時間)
def translate_match_names(match_list):
    if not match_list: return []
    names_to_translate = "\n".join(match_list)
    prompt = f"請將以下足球賽事對陣清單翻譯成香港繁體中文隊名，保持『隊名A vs 隊名B』格式，直接回傳翻譯後的清單：\n{names_to_translate}"
    try:
        response = model.generate_content(prompt)
        translated = response.text.strip().split('\n')
        return translated if len(translated) == len(match_list) else match_list
    except:
        return match_list

def deep_analyze_agent(match_name):
    prompt = f"""
    【重要指令：你現在是一個具備實時聯網搜索能力的足球精算代理】
    目標賽事：{match_name}

    分析要求：
    1. **實時搜索**：檢索各大莊家（Bet365, HKJC）對本場的初盤與現盤走勢，分析資金熱度。
    2. **傷停與環境**：搜索最新傷病名單（主力門將/前鋒）及比賽當地即時天氣預報。
    3. **戰意分析**：考量積分壓力（保級/奪冠）、過往對賽(H2H)紀錄。
    4. **戰術相剋**：分析雙方攻防風格與預期進球(xG)。

    輸出：
    [Score: X-Y]
    [Corners: X-Y]
    [Rec: 推薦投注選項]
    [Win_Conf: X%]
    [Corner_Conf: X%]
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI 服務異常: {str(e)}"

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
                # 建立原始資料清單
                raw_names = [f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}" for m in filtered_matches]
                # 執行翻譯
                translated_names = translate_match_names(raw_names)
                
                # 儲存轉換後的賽事資訊
                display_matches = []
                for i, m in enumerate(filtered_matches):
                    hkt_time = convert_to_hkt(m['fixture']['date'])
                    display_matches.append({
                        "display": f"{hkt_time} | {translated_names[i]}",
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
            for t in targets:
                with st.status(f"分析中: {t}...", expanded=True) as status:
                    report = deep_analyze_agent(t)
                    
                    try:
                        score = re.search(r"\[Score: (.*?)\]", report).group(1)
                        corners = re.search(r"\[Corners: (.*?)\]", report).group(1)
                        rec = re.search(r"\[Rec: (.*?)\]", report).group(1)
                        win_conf = int(re.search(r"\[Win_Conf: (\d+)%\]", report).group(1))
                    except:
                        score, corners, rec, win_conf = "N/A", "N/A", "N/A", 50
                    
                    summary_data.append({"賽事": t, "比分": score, "角球": corners, "推薦": rec, "信心%": win_conf, "報告": report})
                    st.markdown(report)
                    status.update(label=f"✅ {t} 完成", state="complete")

            if summary_data:
                st.divider()
                df = pd.DataFrame(summary_data)
                st.table(df[["賽事", "比分", "角球", "推薦", "信心%"]])
                st.bar_chart(df.set_index("賽事")["信心%"])

# ------------------------------------------
# TAB 2: 馬會賠率雷達 (修改後的啟動區塊)
# ------------------------------------------
with tab2:
    st.header("🕵️‍♂️ 馬會即時盤口監測")
    if st.button("🔍 開始全自動巡邏"):
        with st.status("啟動監測...", expanded=True) as status:
            try:
                with sync_playwright() as p:
                    # 1. 啟動瀏覽器
                    browser = p.chromium.launch(headless=True)
                    
                    # 2. 建立一個「偽裝身份」的上下文 (取代原本的 browser.new_page)
                    # 這行讓馬會以為你是 Windows 上的 Chrome 瀏覽器
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    
                    # 3. 在這個偽裝好的視窗中打開新分頁
                    page = context.new_page()
                    
                    # --- 以下原本的掃描邏輯不變 ---
                    alerts = []
                    
                    status.write("🌐 正在巡邏主客和盤口...")
                    page.goto("https://bet.hkjc.com/ch/football/home", wait_until="networkidle") # 建議加上等待
                    page.wait_for_timeout(5000)
                    
                    # ... 剩下的 homes, aways, h_odds 抓取邏輯 ...
                    
                    browser.close()
                    status.update(label="✅ 巡邏結束", state="complete")
                    if alerts:
                        for a in alerts: st.warning(a)
                    else: st.write("目前無符合條件。")
            except Exception as e: st.error(f"雷達報錯: {e}")
