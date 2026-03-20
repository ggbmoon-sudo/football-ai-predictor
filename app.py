import streamlit as st
import requests
import datetime
import pandas as pd
import time
import re
from playwright.sync_api import sync_playwright
import os
import subprocess
from openai import OpenAI

# ==========================================
# 🔧 雲端環境自動修復
# ==========================================
def install_playwright_browsers():
    cache_path = "/home/appuser/.cache/ms-playwright"
    if not os.path.exists(cache_path):
        with st.spinner("首次執行：正在為雲端伺服器安裝 Chromium 瀏覽器..."):
            try:
                subprocess.run(["playwright", "install", "chromium"], check=True)
                subprocess.run(["playwright", "install-deps"], check=True)
                st.success("✅ 瀏覽器安裝成功！")
            except Exception as e:
                st.error(f"❌ 瀏覽器安裝失敗: {e}")

install_playwright_browsers()

# ==========================================
# ⚙️ 1. 安全設定與 AI 初始化
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    FOOTBALL_API_KEY = st.secrets["FOOTBALL_API_KEY"]
except KeyError:
    st.error("❌ 請在 Secrets 設定 GEMINI_API_KEY 與 FOOTBALL_API_KEY")
    st.stop()

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://api.mttieeo.com/v1"
)

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
    "日職百年構想聯賽 (J3)": 100, "日本職業聯賽 (J1)": 98, "日本職業聯賽 (J2)": 99,
    "南韓K1聯賽": 292,
    "澳洲女子超級聯賽": 190, "澳洲新南威爾斯超": 193, "澳洲昆士蘭超": 194, "墨西哥甲組聯賽": 262
}

# ==========================================
# 🎨 介面設定與側邊欄
# ==========================================
st.set_page_config(page_title="AI 足球精算控制台", layout="wide")

AVAILABLE_MODELS = {
    "Gemini 2.5 Flash": "[F]gemini-2.5-flash",
    "Gemini 2.5 Pro": "[Y]gemini-2.5-pro",
    
}

st.sidebar.header("⚙️ 核心設定")
selected_model_display = st.sidebar.selectbox("🤖 選擇 AI 模型：", list(AVAILABLE_MODELS.keys()))
active_model = AVAILABLE_MODELS[selected_model_display]

st.sidebar.markdown("---")

# 👇 關鍵升級：Prompt 中加入了 {real_data} 區塊
DEFAULT_PROMPT = """【系統指令：啟動「蒙地卡羅大數據」與「戰術行為學」預測引擎】
角色：你是一位擁有 20 年經驗、專為頂級辛迪加(Syndicate)服務的足球博彩精算師。

🎯 目標賽事：{match_name}

🚨【官方真實數據強制注入 - 絕對事實】：
{real_data}
（注意：請務必以上述提供的「真實排名、積分與得失球」為基礎進行邏輯推演。如果數據顯示強弱懸殊，請順勢分析；如果數據顯示是勢均力敵，請分析戰局膠著原因。絕對不可使用舊記憶編造球隊強弱與傷停！）

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
請綜合以上變數，給出理據，並在報告最末端嚴格以獨立行數輸出以下標籤（勿加其他符號）：
[Score: X-Y]
[Corners: X-Y]
[Rec: 推薦投注選項]
[Win_Conf: X%]
[Corner_Conf: X%]"""

with st.sidebar.expander("📝 編輯自定義 Prompt (進階)"):
    st.warning("⚠️ 請務必保留 `{match_name}` 與 `{real_data}` 變數！")
    user_custom_prompt = st.text_area("修改你的精算指令：", value=DEFAULT_PROMPT, height=500)

# ==========================================
# 📡 3. 數據抓取 API 核心 (加入排名快取)
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

# 👇 關鍵升級：向官方 API 獲取聯賽積分榜
@st.cache_data(ttl=3600)
def get_league_standings(league_id, season):
    url = f"https://v3.football.api-sports.io/standings?league={league_id}&season={season}"
    headers = {'x-apisports-key': FOOTBALL_API_KEY}
    try:
        r = requests.get(url, headers=headers)
        data = r.json().get('response', [])
        if not data: return {}
        
        standings = data[0]['league']['standings'][0]
        team_stats = {}
        for team in standings:
            t_id = team['team']['id']
            team_stats[t_id] = {
                "rank": team['rank'],
                "points": team['points'],
                "form": team.get('form', '無資料'),
                "goals_for": team['all']['goals']['for'],
                "goals_against": team['all']['goals']['against']
            }
        return team_stats
    except:
        return {}

# ==========================================
# 🧠 2. 工具函數與 AI 代理
# ==========================================
def translate_match_names(match_list):
    if not match_list: return []
    names_to_translate = "\n".join(match_list)
    prompt = f"將以下對陣翻譯為香港繁體中文（保留vs）：\n{names_to_translate}"
    try:
        response = client.chat.completions.create(
            model=active_model,
            messages=[
                {"role": "system", "content": "你是一個專業的足球翻譯機器人，只輸出翻譯結果，絕對不說廢話。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        raw_output = response.choices[0].message.content.strip().replace("```text", "").replace("```", "")
        translated = [line.strip() for line in raw_output.split('\n') if line.strip() and 'vs' in line.lower()]
        return translated if len(translated) == len(match_list) else match_list
    except:
        return match_list

def deep_analyze_agent(match_name, prompt_template, model_name, real_data_str):
    # 👇 將真實數據與隊名替換進 Prompt
    final_prompt = prompt_template.replace("{match_name}", match_name).replace("{real_data}", real_data_str)
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一位擁有 20 年經驗的足球精算師，請嚴格根據用戶提供的真實數據進行推演。"},
                {"role": "user", "content": final_prompt}
            ],
            temperature=0.4
        )
        content = response.choices[0].message.content
        if not content: return "AI 未能生成報告"
        return content
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota" in error_msg: return "⚠️ ERROR_QUOTA_EXCEEDED"
        return f"API 錯誤: {error_msg}"

# ==========================================
# 🎨 4. 主畫面 (TAB 1 & TAB 2)
# ==========================================
tab1, tab2 = st.tabs(["🎯 AI 深度預測 (RAG)", "📡 馬會賠率雷達"])

with tab1:
    st.header(f"⚽ 指定賽事深度分析 ({selected_model_display})")
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
                    utc_str = m['fixture']['date']
                    utc_dt = datetime.datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
                    hkt_dt = utc_dt + datetime.timedelta(hours=8)
                    
                    hkt_time_str = hkt_dt.strftime("%Y-%m-%d %H:%M")
                    utc_time_str = utc_dt.strftime("%Y-%m-%d %H:%M")
                    time_display = f"{hkt_time_str} HKT (UTC {utc_time_str})"
                    
                    league_id = m['league']['id']
                    league_cn = REVERSE_LEAGUE_IDS.get(league_id, m['league']['name'])
                    
                    # 👇 關鍵升級：將球隊 ID 與賽季存起來，等一下抓數據要用
                    display_matches.append({
                        "display": f"[{league_cn}] {time_display} | {translated_names[i]}",
                        "raw": f"{m['teams']['home']['name']} vs {m['teams']['away']['name']}",
                        "league_id": league_id,
                        "season": m['league']['season'],
                        "home_id": m['teams']['home']['id'],
                        "home_name": translated_names[i].split(" vs ")[0],
                        "away_id": m['teams']['away']['id'],
                        "away_name": translated_names[i].split(" vs ")[1] if " vs " in translated_names[i] else "客隊"
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
                    # 1. 找出這場比賽的詳細資料
                    match_info = next(m for m in st.session_state['display_matches'] if m['display'] == t)
                    
                    # 2. 獲取該聯賽的即時積分榜
                    st.write("📈 正在向官方資料庫提取真實排名與積分...")
                    standings = get_league_standings(match_info['league_id'], match_info['season'])
                    
                    # 3. 組合主客隊的真實數據字串
                    h_stat = standings.get(match_info['home_id'], {})
                    a_stat = standings.get(match_info['away_id'], {})
                    
                    if h_stat and a_stat:
                        real_data_str = f"""
                        ✅ 主隊 ({match_info['home_name']})：目前聯賽排名第 {h_stat['rank']}，積分 {h_stat['points']}，近5場狀態 {h_stat['form']}，賽季總進球 {h_stat['goals_for']}，總失球 {h_stat['goals_against']}。
                        ✅ 客隊 ({match_info['away_name']})：目前聯賽排名第 {a_stat['rank']}，積分 {a_stat['points']}，近5場狀態 {a_stat['form']}，賽季總進球 {a_stat['goals_for']}，總失球 {a_stat['goals_against']}。
                        """
                    else:
                        real_data_str = "⚠️ 無法獲取官方積分榜，請依賴球隊歷史戰力推演（注意可能是盃賽或賽季剛開始）。"

                    # 4. 將真實數據餵給 AI
                    st.write(f"🌐 正在將數據注入 {selected_model_display} 進行推演...")
                    report = deep_analyze_agent(t, user_custom_prompt, active_model, real_data_str)
                    
                    if report == "⚠️ ERROR_QUOTA_EXCEEDED":
                        st.error("🚫 API 額度已耗盡，請檢查代理伺服器狀態。")
                        break
                    
                    st.write("📊 正在解析勝負與角球精算標籤...")
                    
                    score = safe_extract(r"\[Score:\s*(.*?)\]", report)
                    corners = safe_extract(r"\[Corners:\s*(.*?)\]", report)
                    rec = safe_extract(r"\[Rec:\s*(.*?)\]", report)
                    
                    win_match = re.search(r"\[Win_Conf:\s*(\d+)%?\]", report)
                    win_conf = int(win_match.group(1)) if win_match else 50
                    
                    cor_match = re.search(r"\[Corner_Conf:\s*(\d+)%?\]", report)
                    cor_conf = int(cor_match.group(1)) if cor_match else 50
                    
                    summary_data.append({
                        "賽事": t, "比分": score, "角球": corners, 
                        "推薦": rec, "勝負信心%": win_conf, "角球信心%": cor_conf, "報告": report
                    })
                    
                    # 在畫面上也顯示出我們抓到的真實數據，方便你核對
                    st.markdown(f"### {t} 分析簡報")
                    st.info(f"**🤖 AI 接收到的官方基底數據：**\n{real_data_str}")
                    st.markdown(report)
                    st.divider()
                    time.sleep(2)
                    status.update(label=f"✅ {t} 完成", state="complete", expanded=False)

            if summary_data:
                st.subheader("📋 批量分析決策中心")
                df = pd.DataFrame(summary_data)
                st.table(df[["賽事", "比分", "角球", "推薦", "勝負信心%", "角球信心%"]])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write("🎯 勝負預測信心")
                    st.bar_chart(df.set_index("賽事")["勝負信心%"])
                with col2:
                    st.write("🚩 角球預測信心")
                    st.bar_chart(df.set_index("賽事")["角球信心%"], color="#ff2b2b")

# ------------------------------------------
# TAB 2: 馬會賠率雷達 (保持不變)
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
                    homes = page.locator('[data-testid$="_homeTeam"]').all()
                    aways = page.locator('[data-testid$="_awayTeam"]').all()
                    h_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_H_odds"]').all()
                    d_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_D_odds"]').all()
                    a_odds = page.locator('span[data-testid*="_HAD_"][data-testid$="_A_odds"]').all()

                    for i in range(min(len(homes), len(h_odds))):
                        h, d, a = h_odds[i].inner_text(), d_odds[i].inner_text(), a_odds[i].inner_text()
                        if (h=="2.14" and d=="3.00" and a=="3.00") or (h=="3.00" and d=="3.00" and a=="2.14"):
                            alerts.append(f"🚨 [HAD] {homes[i].inner_text()} vs {aways[i].inner_text()} ({h}/{d}/{a})")

                    status.write("🌐 正在掃描讓球主客和 (/hha)...")
                    page.goto("https://bet.hkjc.com/ch/football/hha", wait_until="networkidle")
                    page.wait_for_timeout(5000)
                    hha_homes = page.locator('[data-testid$="_homeTeam"]').all()
                    hha_conds = page.locator('div[data-testid*="_HHA_"].cond').all()
                    hha_odds = page.locator('span[data-testid*="_HHA_"][data-testid$="_H_odds"]').all()
                    for i in range(min(len(hha_homes), len(hha_odds))):
                        if "-1" in hha_conds[i].inner_text() and hha_odds[i].inner_text()=="3.10":
                            alerts.append(f"🚨 [HHA] {hha_homes[i].inner_text()} 讓球-1 @ 3.10")

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
