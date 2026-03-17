import streamlit as st
import requests
import google.generativeai as genai
import datetime
import pandas as pd
import time
import re
from playwright.sync_api import sync_playwright

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

# 聯賽清單 (如前所述)
LEAGUE_IDS = {
    "英格蘭超級聯賽": 39, "西班牙甲組聯賽": 140, "西班牙乙組聯賽": 141,
    "意大利甲組聯賽": 135, "德國甲組聯賽": 78, "德國乙組聯賽": 79,
    "荷蘭甲組聯賽": 88, "荷蘭乙組聯賽": 89, "葡萄牙超級聯賽": 94,
    "英格蘭冠軍聯賽": 40, "阿根廷甲組聯賽": 128, "巴西甲組聯賽": 71,
    "智利甲組聯賽": 265, "烏拉圭甲組聯賽": 268, "美國職業聯賽": 253,
    "澳洲職業聯賽": 188, "阿聯酋職業聯賽": 301, "泰國甲組聯賽": 296,
    "沙特職業聯賽": 307, "歐洲聯賽冠軍盃": 2, "歐霸盃": 3, "歐洲協會聯賽": 848
}

# ==========================================
# 🧠 2. AI 分析核心函數
# ==========================================
def deep_analyze_agent(match_data):
    prompt = f"""
    【重要指令：你現在是一個具備實時聯網搜索能力的足球精算代理】
    目標賽事：{match_data['home']} vs {match_data['away']} (聯賽：{match_data['league']})

    分析要求：
    1. **實時搜索**：檢索當前最新的各大莊家（Bet365, HKJC）對本場的初盤與現盤走賽。
    2. **傷停與環境**：搜索最新傷病名單與比賽當地天氣預報。
    3. **戰意分析**：考量積分壓力、歷史對賽(H2H)。
    4. **推薦選項**：基於數據，給出一個最穩的投注選項（如：讓球主勝、大2.5、客+1 等）。

    請以專業格式回覆，並在結尾處務必包含以下數據標籤：
    [Score: X-Y]
    [Corners: X-Y]
    [Rec: 這裡填寫推薦投注選項]
    [Win_Conf: X%]
    """
    response = model.generate_content(prompt)
    return response.text

# ==========================================
# 📡 3. 數據抓取函數 (API)
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
# 🎨 4. APP 介面與分頁
# ==========================================
st.set_page_config(page_title="AI 足球精算控制台", layout="wide")
tab1, tab2 = st.tabs(["🎯 AI 深度預測", "📡 馬會賠率雷達"])

# ------------------------------------------
# TAB 1: AI 深度預測
# ------------------------------------------
with tab1:
    st.header("⚽ 指定賽事深度分析")
    selected_leagues = st.multiselect("選擇聯賽：", list(LEAGUE_IDS.keys()))
    
    if st.button("加載賽程"):
        all_data = get_global_matches()
        ids = [LEAGUE_IDS[n] for n in selected_leagues]
        st.session_state['matches'] = [m for m in all_data if m['league']['id'] in ids]

    if 'matches' in st.session_state and st.session_state['matches']:
        match_names = [f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}" for m in st.session_state['matches']]
        targets = st.multiselect("勾選分析賽事：", match_names)
        
        if st.button("執行批量分析"):
            for t in targets:
                with st.status(f"分析中: {t}...", expanded=False):
                    report = deep_analyze_agent(t)
                    st.markdown(report)

# ------------------------------------------
# TAB 2: 馬會賠率雷達
# ------------------------------------------
with tab2:
    st.header("🕵️‍♂️ 馬會即時盤口監測")
    st.info("掃描目標：HAD (2.14/3/3), HHA (-1@3.1), HIL (1.66)")
    
    if st.button("🔍 開始全自動巡邏"):
        with st.status("正在啟動 Playwright 瀏覽器...", expanded=True) as status:
            try:
                with sync_playwright() as p:
                    # 在雲端必須使用 headless=True
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    # 監測清單
                    alerts = []

                    # 掃描 HAD
                    status.write("🌐 正在掃描主客和 (/home)...")
                    page.goto("https://bet.hkjc.com/ch/football/home")
                    page.wait_for_timeout(5000)
                    
                    homes = page.locator('[data-testid$="_homeTeam"]').all()
                    aways = page.locator('[data-testid$="_awayTeam"]').all()
                    h_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_H_odds"]').all()
                    d_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_D_odds"]').all()
                    a_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_A_odds"]').all()

                    for i in range(min(len(homes), len(h_odds))):
                        h, d, a = h_odds[i].inner_text(), d_odds[i].inner_text(), a_odds[i].inner_text()
                        if (h=="2.14" and d=="3.00" and a=="3.00") or (h=="3.00" and d=="3.00" and a=="2.14"):
                            alerts.append(f"🚨 [HAD] {homes[i].inner_text()} vs {aways[i].inner_text()} ({h}/{d}/{a})")

                    # 掃描 HHA
                    status.write("🌐 正在掃描讓球主客和 (/hha)...")
                    page.goto("https://bet.hkjc.com/ch/football/hha")
                    page.wait_for_timeout(5000)
                    hha_homes = page.locator('[data-testid$="_homeTeam"]').all()
                    hha_conds = page.locator('div[data-testid*="_HHA_"].cond').all()
                    hha_odds = page.locator('span[data-testid*="_HHA_"][data-testid$="_H_odds"]').all()
                    
                    for i in range(min(len(hha_homes), len(hha_odds))):
                        if "-1" in hha_conds[i].inner_text() and hha_odds[i].inner_text()=="3.10":
                            alerts.append(f"🚨 [HHA] {hha_homes[i].inner_text()} 讓球-1 @ 3.10")

                    # 掃描 HIL
                    status.write("🌐 正在掃描入球大細 (/hil)...")
                    page.goto("https://bet.hkjc.com/ch/football/hil")
                    page.wait_for_timeout(5000)
                    hil_homes = page.locator('[data-testid$="_homeTeam"]').all()
                    hil_odds = page.locator('span[data-testid*="_HIL_"][data-testid$="_H_odds"]').all()
                    
                    for i in range(min(len(hil_homes), len(hil_odds))):
                        if hil_odds[i].inner_text()=="1.66":
                            alerts.append(f"🚨 [HIL] {hil_homes[i].inner_text()} 大細 @ 1.66")

                    browser.close()
                    status.update(label="✅ 巡邏結束！", state="complete")

                    if alerts:
                        st.success(f"發現 {len(alerts)} 場符合條件賽事！")
                        for a in alerts:
                            st.warning(a)
                    else:
                        st.write("暫無符合條件的賠率。")
            except Exception as e:
                st.error(f"雷達啟動失敗: {e}")
