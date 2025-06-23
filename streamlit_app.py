import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import asyncio

# --- 页面基础设置 ---
st.set_page_config(page_title="CheckCheckCheck Pro", layout="wide")

# --- 样式定义 ---
st.markdown("""
<style>
    /* ... [原有样式可以保留或根据新组件调整] ... */
    .stButton>button {
        width: 100%;
    }
    .stDataFrame {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- 核心抓取与解析函数 (后端执行) ---

def get_domain_from_url(url):
    try:
        return urlparse(url).hostname.replace('www.', '')
    except:
        return ''

def extract_publish_date(soup):
    # 优先使用具有特定属性的meta标签
    selectors = [
        'meta[property="article:published_time"]',
        'meta[property="og:published_time"]',
        'meta[name="publication_date"]',
        'meta[name="publishdate"]',
        'meta[name="date"]',
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if element and element.get('content'):
            return element.get('content').split('T')[0]

    # 其次查找time标签
    time_tag = soup.select_one('time[datetime]')
    if time_tag and time_tag.get('datetime'):
        return time_tag.get('datetime').split('T')[0]
    
    return "未找到"

def fetch_and_parse(url):
    """使用requests在后端抓取和解析单个URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # 如果请求失败则抛出HTTPError

        soup = BeautifulSoup(response.content, 'html.parser')
        publish_date = extract_publish_date(soup)
        
        anchors_data = []
        # 优先在主要内容区查找
        main_content = soup.select_one('main, article, .post-content, #content')
        container = main_content if main_content else soup.body

        for a in container.find_all('a', href=True):
            text = a.get_text(strip=True)
            href_raw = a.get('href')
            
            if not text or not href_raw:
                continue

            href = urljoin(url, href_raw)
            target_domain = get_domain_from_url(href)
            
            if not target_domain:
                continue

            rel = a.get('rel', [])
            follow_type = 'nofollow' if 'nofollow' in rel else 'dofollow'

            anchors_data.append({
                "来源页面": url,
                "文章上线时间": publish_date,
                "锚文本": text,
                "目标链接": href,
                "目标域名": target_domain,
                "链接类型": follow_type,
            })
        
        return anchors_data

    except requests.RequestException as e:
        st.error(f"抓取失败: {url} (原因: {e})")
        return []

# --- Streamlit 应用界面 ---

def main_app():
    st.title("🚀 CheckCheckCheck Pro (后端增强版)")

    # 初始化session_state
    if 'results_df' not in st.session_state:
        st.session_state.results_df = pd.DataFrame()

    url_input = st.text_area(
        "输入网址 (每行一个)", 
        height=150,
        placeholder="https://example.com/page1\nhttps://example.com/page2"
    )

    if st.button("🚀 开始提取 (后端模式)", type="primary"):
        urls = [u.strip() for u in url_input.split('\n') if u.strip()]
        if not urls:
            st.warning("请输入至少一个有效网址。")
            return

        all_results = []
        progress_bar = st.progress(0, text="准备开始抓取...")
        
        for i, url in enumerate(urls):
            progress_bar.progress((i) / len(urls), text=f"正在抓取: {url}")
            results = fetch_and_parse(url)
            if results:
                all_results.extend(results)
        
        progress_bar.progress(1.0, text="所有任务完成！")

        if not all_results:
            st.warning("未能从任何网址中提取到有效链接。")
            st.session_state.results_df = pd.DataFrame()
        else:
            st.session_state.results_df = pd.DataFrame(all_results)

    # --- 结果展示 ---
    if not st.session_state.results_df.empty:
        st.success(f"提取完成！共找到 {len(st.session_state.results_df)} 条锚文本链接。")
        
        df_to_show = st.session_state.results_df.copy()

        # --- 筛选器 ---
        col1, col2 = st.columns(2)
        with col1:
            source_options = ["所有来源"] + list(df_to_show["来源页面"].unique())
            selected_source = st.selectbox("筛选来源页面:", source_options)
            if selected_source != "所有来源":
                df_to_show = df_to_show[df_to_show["来源页面"] == selected_source]

        with col2:
            domain_options = ["所有域名"] + list(df_to_show["目标域名"].unique())
            selected_domain = st.selectbox("筛选目标域名:", domain_options)
            if selected_domain != "所有域名":
                df_to_show = df_to_show[df_to_show["目标域名"] == selected_domain]

        # --- 显示表格 ---
        st.dataframe(df_to_show, use_container_width=True)

        # --- 下载按钮 ---
        @st.cache_data
        def convert_df_to_csv(df):
            return df.to_csv(index=False).encode('utf-8-sig')

        csv = convert_df_to_csv(df_to_show)
        st.download_button(
            label="📥 下载当前筛选结果 (CSV)",
            data=csv,
            file_name="link_check_results.csv",
            mime="text/csv",
        )

# --- 登录逻辑 (保持不变) ---
if 'users' not in st.session_state:
    st.session_state['users'] = {"admin": "1008611"}
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login():
    st.title("登录")
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    if st.button("登录"):
        if username in st.session_state['users'] and st.session_state['users'][username] == password:
            st.session_state['logged_in'] = True
            st.success(f"欢迎 {username}！")
            st.rerun()
        else:
            st.error("用户名或密码错误")

def add_user():
    st.title("添加新用户")
    new_user = st.text_input("新用户名")
    new_pass = st.text_input("新密码", type="password")
    if st.button("添加用户"):
        if new_user in st.session_state['users']:
            st.warning("用户已存在！")
        elif not new_user or not new_pass:
            st.warning("用户名和密码不能为空！")
        else:
            st.session_state['users'][new_user] = new_pass
            st.success(f"添加用户 {new_user} 成功！")

# --- 主程序路由 ---
if not st.session_state['logged_in']:
    login()
else:
    st.sidebar.title("管理菜单")
    option = st.sidebar.selectbox("选择操作", ["主页", "添加用户", "退出登录"])

    if option == "主页":
        main_app()
    elif option == "添加用户":
        add_user()
    elif option == "退出登录":
        st.session_state['logged_in'] = False
        st.rerun()