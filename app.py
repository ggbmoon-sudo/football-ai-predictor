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

# 擴充版聯賽清單 (包含你要求的全部聯賽)
LEAGUE_IDS = {
    "英格蘭超級聯賽": 39, "西班牙甲組聯賽": 140, "西班牙乙組聯賽": 141,
    "意大利甲組聯賽": 135, "德國甲組聯賽": 78, "德國乙組聯賽": 79,
    "荷蘭甲組聯賽": 88, "荷蘭乙組聯賽": 89, "葡萄牙超級聯賽": 94,
    "英格蘭冠軍聯賽": 40, "阿根廷甲組聯賽": 128, "巴西甲組聯賽": 71,
    "智利甲組聯賽": 265, "烏拉圭甲組聯賽": 268, "美國職業聯賽 (MLS)": 253,
    "澳洲職業聯賽": 188, "阿聯酋職業聯賽": 301, "泰國甲組聯賽": 296,
    "沙特職業聯賽": 307, "歐洲聯賽冠軍盃": 2, "歐霸盃": 3, "歐洲協會聯賽": 848
}

# ==========================================
# 🧠 2. AI 分析核心函數 (修正版：處理字串輸入)
# ==========================================
def deep_analyze_agent(match_name):
    prompt = f"""
    【重要指令：你現在是一個具備實時聯網搜索能力的足球精算代理】
    目標賽事：{match_name}

    分析要求：
    1. **實時搜索**：檢索各大莊家（Bet365, HKJC）對本場的初盤與現盤走勢，分析資金熱度。
    2. **傷停與環境**：搜索最新傷病名單（主力門將/前鋒）及比賽當地即時天氣預報。
    3. **戰意分析**：考量積分壓力（保級/奪冠）、過往對賽(H2H)紀錄。
    4. **戰術相剋**：分析雙方攻防風格與預期進球(xG)。

    請以專業精算師口吻回覆理據，並在結尾務必包含以下數據標籤（必須嚴格遵守格式）：
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
# 📡 3. 數據抓取函數 (API)
# ==========================================
@st.cache_data(ttl=3600)
def get_global_matches():
    # 這裡建議改用日期查詢，以避開免費版 next 限制
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
    st.header("⚽ 指定賽事深度分析")
    selected_leagues = st.multiselect("選擇聯賽 (可多選)：", list(LEAGUE_IDS.keys()))
    
    if st.button("加載今日賽程"):
        with st.spinner("正在抓取數據..."):
            all_data = get_global_matches()
            ids = [LEAGUE_IDS[n] for n in selected_leagues]
            st.session_state['matches'] = [m for m in all_data if m['league']['id'] in ids]
            if not st.session_state['matches']:
                st.warning("所選聯賽今日暫無賽程。")

    if 'matches' in st.session_state and st.session_state['matches']:
        match_names = [f"{m['fixture']['date'][11:16]} | {m['teams']['home']['name']} vs {m['teams']['away']['name']}" for m in st.session_state['matches']]
        targets = st.multiselect("勾選欲分析的場次 (批量)：", match_names)
        
        if st.button("🚀 執行批量 AI 精算分析"):
            summary_data = []
            
            for t in targets:
                # 顯示即時生成進度
                with st.status(f"正在深度分析: {t}...", expanded=True) as status:
                    st.write("🔍 正在檢索全球即時數據 (傷停/天氣/賠率)...")
                    report = deep_analyze_agent(t)
                    st.write("📈 正在計算戰術相剋與信心評分...")
                    
                    # 數據解析 (Regex)
                    try:
                        score = re.search(r"\[Score: (.*?)\]", report).group(1)
                        corners = re.search(r"\[Corners: (.*?)\]", report).group(1)
                        rec = re.search(r"\[Rec: (.*?)\]", report).group(1)
                        win_conf = int(re.search(r"\[Win_Conf: (\d+)%\]", report).group(1))
                        cor_conf = int(re.search(r"\[Corner_Conf: (\d+)%\]", report).group(1))
                    except:
                        score, corners, rec, win_conf, cor_conf = "N/A", "N/A", "N/A", 50, 50
                    
                    summary_data.append({
                        "賽事": t,
                        "預測比分": score,
                        "預測角球": corners,
                        "推薦選項": rec,
                        "勝負信心%": win_conf,
                        "角球信心%": cor_conf,
                        "詳細報告": report
                    })
                    
                    st.markdown(f"**{t} 分析簡報**")
                    st.markdown(report)
                    status.update(label=f"✅ {t} 分析完成！", state="complete")

            # 生成結論數據總表與圖表
            if summary_data:
                st.divider()
                st.subheader("📊 批量分析結論摘要")
                df = pd.DataFrame(summary_data)
                st.table(df[["賽事", "預測比分", "預測角球", "推薦選項", "勝負信心%"]])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("📈 勝負信心分佈")
                    st.bar_chart(df.set_index("賽事")["勝負信心%"])
                with col2:
                    st.write("🚩 角球預測信心")
                    st.area_chart(df.set_index("賽事")["角球信心%"])

# ------------------------------------------
# TAB 2: 馬會賠率雷達 (保留原有邏輯)
# ------------------------------------------
with tab2:
    st.header("🕵️‍♂️ 馬會即時盤口監測")
    st.info("監測中：HAD (2.14/3.00), HHA (-1@3.10), HIL (1.66)")
    
    if st.button("🔍 開始全自動巡邏"):
        with st.status("啟動 Playwright 監測中...", expanded=True) as status:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    alerts = []

                    # HAD
                    status.write("🌐 掃描主客和盤口...")
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

                    # HHA
                    status.write("🌐 掃描讓球主客和...")
                    page.goto("https://bet.hkjc.com/ch/football/hha")
                    page.wait_for_timeout(5000)
                    hha_homes = page.locator('[data-testid$="_homeTeam"]').all()
                    hha_conds = page.locator('div[data-testid*="_HHA_"].cond').all()
                    hha_odds = page.locator('span[data-testid*="_HHA_"][data-testid$="_H_odds"]').all()
                    for i in range(min(len(hha_homes), len(hha_odds))):
                        if "-1" in hha_conds[i].inner_text() and hha_odds[i].inner_text()=="3.10":
                            alerts.append(f"🚨 [HHA] {hha_homes[i].inner_text()} @ 3.10")

                    # HIL
                    status.write("🌐 掃描入球大細...")
                    page.goto("https://bet.hkjc.com/ch/football/hil")
                    page.wait_for_timeout(5000)
                    hil_homes = page.locator('[data-testid$="_homeTeam"]').all()
                    hil_odds = page.locator('span[data-testid*="_HIL_"][data-testid$="_H_odds"]').all()
                    for i in range(min(len(hil_homes), len(hil_odds))):
                        if hil_odds[i].inner_text()=="1.66":
                            alerts.append(f"🚨 [HIL] {hil_homes[i].inner_text()} @ 1.66")

                    browser.close()
                    status.update(label="✅ 巡邏結束！", state="complete")

                    if alerts:
                        st.success(f"發現 {len(alerts)} 場目標賽事！")
                        for a in alerts: st.warning(a)
                    else:
                        st.write("暫無符合賠率。")
            except Exception as e:
                st.error(f"雷達報錯: {e}")
