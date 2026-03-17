import datetime
import streamlit as st
import requests
import google.generativeai as genai

# ==========================================
# ⚙️ 1. 從 Streamlit Secrets 安全讀取金鑰
# ==========================================
# 這樣你的程式碼上傳到 GitHub 就沒有洩漏風險了
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    FOOTBALL_API_KEY = st.secrets["FOOTBALL_API_KEY"]
except KeyError:
    st.error("❌ 找不到 API Key 設定！請在 Streamlit Cloud 的 Secrets 中設定金鑰。")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================
# 🏆 2. 擴充版：全球聯賽資料庫 ID
# ==========================================
LEAGUE_IDS = {
    "歐冠盃 (UEFA Champions League)": 2,
    "英超 (Premier League)": 39,
    "英冠 (Championship)": 40,
    "英甲 (League One)": 41,
    "西甲 (La Liga)": 140,
    "西乙 (Segunda Division)": 141,
    "德甲 (Bundesliga)": 78,
    "德乙 (2. Bundesliga)": 79,
    "意甲 (Serie A)": 135,
    "法甲 (Ligue 1)": 61,
    "澳超 (A-League)": 188,
    "阿甲 (Liga Profesional)": 128,
    "荷乙 (Eerste Divisie)": 89,
    "韓K聯 (K League 1)": 292,
    "美冠盃 (CONCACAF Champions Cup)": 16,
    "卡塔爾聯 (Stars League)": 153,
    "哥倫甲春 (Primera A)": 119,
    "阿聯酋超 (Pro League)": 301,
    "日職聯 (J1 League)": 98,
    "比甲 (Pro League)": 144,
    "蘇超 (Premiership)": 179
}

# ==========================================
# 📡 3. 獲取真實賽事數據函數 (終極繞行版)
# ==========================================
def get_real_matches(league_id):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    headers = {
        'x-apisports-key': FOOTBALL_API_KEY
    }
    
    match_list = []
    dates_to_check = [today, tomorrow]
    
    try:
        for d in dates_to_check:
            # 💡 破解點：拿掉 league 參數，直接抓當天「全球」所有比賽！
            url = f"https://v3.football.api-sports.io/fixtures?date={d}"
            response = requests.get(url, headers=headers)
            data = response.json()
            
            if 'errors' in data and data['errors']:
                if isinstance(data['errors'], dict) and len(data['errors']) > 0:
                    st.sidebar.error(f"❌ API 錯誤: {data['errors']}")
                    return []
                    
            if data.get('response'):
                for match in data['response']:
                    # 💡 破解點：在我們自己的 Python 程式裡進行「聯賽 ID」比對過濾
                    if match['league']['id'] == league_id:
                        status = match['fixture']['status']['short']
                        if status in ['NS', 'TBD']: # 確保只抓「還沒開打」的比賽
                            home = match['teams']['home']['name']
                            away = match['teams']['away']['name']
                            time_str = match['fixture']['date'][11:16]
                            match_list.append(f"{d} {time_str} | {home} vs {away}")
                            
        return match_list
        
    except Exception as e:
        st.sidebar.error(f"⚠️ 網路連線失敗: {e}")
        return []

# ==========================================
# 🧠 4. AI 分析函數 (20年精算師)
# ==========================================
def analyze_match(match_string):
    prompt = f"""
    角色設定：
    你是一位擁有 20 年經驗的足球職業博彩精算師與大數據模型專家。你的任務是綜合分析以下數據，為我預測一場足球比賽的結果（波膽/比分）以及角球數。
    
    即將進行的比賽：{match_string}
    
    分析要求（請按此邏輯客觀回答）：
    1. xG/xGA 分析： 比較兩隊的預期進球與失球，推算真實攻防效率。
    2. 戰術相剋： 分析主隊的進攻方式與客隊的防守風格是否存在對位優勢。
    3. 角球預測： 根據兩隊邊路進攻頻率，預測總角球數與分佈。
    4. 莊家意圖： 分析近期這兩隊常見的賠率走勢是否存在誘導。
    
    最終輸出：
    - 預測比分： 給出 2 個最可能的比分。
    - 預測角球： 給出角球區間。
    - 信心評分： (0-100%) 以及核心理據。
    """
    response = model.generate_content(prompt)
    return response.text

# ==========================================
# 🎨 5. APP 網頁介面設計
# ==========================================
st.set_page_config(page_title="AI 賽事精算師", page_icon="⚽", layout="wide")

st.title("⚽ AI 賽事精算師系統 (Gemini 驅動)")
st.markdown("一鍵獲取真實賽事，自動生成深度數據預測報告與過關推薦。")

st.sidebar.header("🔍 賽事搜尋器")
selected_league = st.sidebar.selectbox("選擇想分析的聯賽：", list(LEAGUE_IDS.keys()))

if st.sidebar.button("獲取未來賽事"):
    with st.spinner("📡 正在從全球資料庫抓取最新賽程..."):
        league_id = LEAGUE_IDS[selected_league]
        matches = get_real_matches(league_id)
        
        if matches:
            st.session_state['matches'] = matches
            st.sidebar.success(f"✅ 成功抓取 {len(matches)} 場比賽！")
        else:
            if 'matches' in st.session_state:
                del st.session_state['matches']
            st.sidebar.warning("目前該聯賽近期無賽事，或請檢查上方紅色的錯誤提示。")

if 'matches' in st.session_state and st.session_state['matches']:
    st.subheader("🎯 選擇一場比賽進行深度分析")
    selected_match = st.selectbox("賽事列表：", st.session_state['matches'])
    
    if st.button("🚀 呼叫 AI 精算師進行預測"):
        with st.spinner("🧠 正在啟動 20 年經驗大數據模型分析中，請稍候... (需時約 10-20 秒)"):
            try:
                report = analyze_match(selected_match)
                st.success("✅ 分析完成！")
                st.markdown("---")
                st.markdown(report)
                st.markdown("---")
            except Exception as e:
                st.error(f"AI 產生報告時發生錯誤 (可能是 API Key 沒填好或地區限制): {e}")
