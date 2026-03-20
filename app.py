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

# 初始化通用 AI 客戶端
client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://api.mttieeo.com/v1"
)

# 擴充版聯賽清單
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
    "南韓K1聯賽": 292
}

# ==========================================
# 🎨 介面設定與側邊欄 (模型與 Prompt 控制)
# ==========================================
st.set_page_config(page_title="AI 足球精算控制台", layout="wide")

# 定義可選模型 (代理商的名稱可能會帶有前綴，如 [F])
AVAILABLE_MODELS = {
    "Gemini 2.5 Flash": "[F]gemini-2.5-flash", # 保留你原本能用的代理名稱
    "Gemini 2.5 Pro": "[Y]gemini-2.5-pro",

}

st.sidebar.header("⚙️ 核心設定")
selected_model_display = st.sidebar.selectbox("🤖 選擇 AI 模型：", list(AVAILABLE_MODELS.keys()))
active_model = AVAILABLE_MODELS[selected_model_display]

st.sidebar.markdown("---")
# 預設的 Prompt 模板
DEFAULT_PROMPT = """【系統指令：啟動「蒙地卡羅大數據」與「戰術行為學」預測引擎】
角色：你是一位擁有 20 年經驗、專為頂級辛迪加(Syndicate)服務的足球博彩精算師。

🎯 絕對確定的目標賽事：{match_name}

🚨【極重要系統時間與現實設定 - 必讀】：
1. 當前時間線：請注意標題中的「年份」。絕對不要使用舊記憶來判斷球隊級別！如果某支球隊現在出現在次級聯賽，代表他們已經降級，這是一場真實比賽。
2. 禁止假想模擬：這絕對不是「假設性推演」。請完全基於他們當前賽季真實的戰力進行分析。
3. 雙時區基準：標題已提供 HKT 與 UTC。檢索時優先使用 UTC 對照，或直接依賴對陣名稱。禁止以查無此賽為由罷工！

【分析要求】
1. 進球與失球模型 (xG/xGA) 拆解。
2. 戰術相剋與近期傷停陣容推演。
3. 判斷雙方戰意與莊家(Bet365)資金劇本。
4. 根據控球與下底頻率，推算角球矩陣。

【最終精算結論】
請綜合以上變數，給出理據，並在報告最末端嚴格以獨立行數輸出以下標籤（勿加其他符號）：
[Score: X-Y]
[Corners: X-Y]
[Rec: 推薦投注選項]
[Win_Conf: X%]
[Corner_Conf: X%]"""

with st.sidebar.expander("📝 編輯自定義 Prompt (進階)"):
    st.warning("⚠️ 提示：請務必保留 `{match_name}` 這個變數，以及結尾的五個 `[標籤]`，否則圖表將無法生成！")
    user_custom_prompt = st.text_area("修改你的精算指令：", value=DEFAULT_PROMPT, height=450)

# ==========================================
# 🧠 2. 工具函數與 AI 代理
# ==========================================
def convert_to_hkt(utc_date_str):
    utc_dt = datetime.datetime.fromisoformat(utc_date_str.replace('Z', '+00:00'))
    hkt_dt = utc_dt + datetime.timedelta(hours=8)
    return hkt_dt.strftime("%Y-%m-%d %H:%M")

def translate_match_names(match_list):
    if not match_list: return []
    names_to_translate = "\n".join(match_list)
    prompt = f"將以下對陣翻譯為香港繁體中文（保留vs）：\n{names_to_translate}"
    try:
        response = client.chat.completions.create(
            model=active_model,  # 使用前端選擇的模型
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

# 將前端的 Prompt 和 模型參數傳入函數
def deep_analyze_agent(match_name, prompt_template, model_name):
    # 將用戶設定的 {match_name} 替換為真實對陣
    final_prompt = prompt_template.replace("{match_name}", match_name)
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一位擁有 20 年經驗的足球精算師，嚴格服從指令。"},
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
# 📡 3. 數據抓取與主畫面
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

tab1, tab2 = st.tabs(["🎯 AI 深度預測", "📡 馬會賠率雷達"])

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
                    st.write(f"🌐 正在使用 {selected_model_display} 獲取數據...")
                    # 傳入用戶自定義的 Prompt 和 選擇的模型
                    report = deep_analyze_agent(t, user_custom_prompt, active_model)
                    
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
                    
                    st.markdown(f"### {t} 分析簡報")
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
