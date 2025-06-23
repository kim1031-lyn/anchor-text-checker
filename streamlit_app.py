import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import mammoth 
import io
from streamlit_copy_button import copy_button # 导入复制按钮功能

# --- 页面基础设置 ---
st.set_page_config(page_title="CheckCheckCheck Pro", layout="wide")

# --- 样式定义 ---
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
    .stDataFrame {
        width: 100%;
    }
    /* 复制按钮的样式可以微调 */
    div[data-testid="stCopyButton"] button {
        width: auto;
        padding: 4px 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 核心功能函数 ---

def get_domain_from_url(url):
    try:
        return urlparse(url).hostname.replace('www.', '')
    except:
        return ''

def extract_publish_date(soup):
    selectors = [
        'meta[property="article:published_time"]', 'meta[property="og:published_time"]',
        'meta[name="publication_date"]', 'meta[name="publishdate"]', 'meta[name="date"]',
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if element and element.get('content'):
            return element.get('content').split('T')[0]
    time_tag = soup.select_one('time[datetime]')
    if time_tag and time_tag.get('datetime'):
        return time_tag.get('datetime').split('T')[0]
    return "未找到"

def fetch_and_parse_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        publish_date = extract_publish_date(soup)
        anchors_data = []
        main_content = soup.select_one('main, article, .post-content, #content')
        container = main_content if main_content else soup.body
        for a in container.find_all('a', href=True):
            text = a.get_text(strip=True)
            href_raw = a.get('href')
            if not text or not href_raw: continue
            href = urljoin(url, href_raw)
            target_domain = get_domain_from_url(href)
            if not target_domain: continue
            rel = a.get('rel', [])
            follow_type = 'nofollow' if 'nofollow' in rel else 'dofollow'
            anchors_data.append({
                "来源页面": url, "文章上线时间": publish_date, "锚文本": text,
                "目标链接": href, "目标域名": target_domain, "链接类型": follow_type,
            })
        return anchors_data
    except requests.RequestException as e:
        st.error(f"抓取失败: {url} (原因: {e})")
        return []

def extract_links_from_docx(uploaded_file):
    try:
        result = mammoth.convert_to_html(uploaded_file)
        html_content = result.value
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            href = a.get('href')
            if text and href:
                links.append({"锚文本": text, "链接地址": href})
        if not links:
            st.warning("在文档中未找到任何链接。")
            return pd.DataFrame()
        return pd.DataFrame(links)
    except Exception as e:
        st.error(f"解析Word文档失败: {e}")
        return pd.DataFrame()

# --- 主应用界面与逻辑 ---

def main_app():
    st.title("🚀 CheckCheckCheck Pro (最终版)")

    tab1, tab2 = st.tabs(["🔗 网址锚文本提取", "📄 Word文档链接提取"])

    with tab1:
        st.header("从网页URL提取链接")
        url_input = st.text_area("输入网址 (每行一个)", height=150, placeholder="https://example.com/page1\nhttps://example.com/page2", key="url_input")
        if st.button("🚀 开始提取 (后端模式)", type="primary"):
            urls = [u.strip() for u in url_input.split('\n') if u.strip()]
            if not urls:
                st.warning("请输入至少一个有效网址。")
            else:
                all_results = []
                progress_bar = st.progress(0, text="准备开始抓取...")
                for i, url in enumerate(urls):
                    progress_bar.progress((i) / len(urls), text=f"正在抓取: {url}")
                    results = fetch_and_parse_url(url)
                    if results: all_results.extend(results)
                progress_bar.progress(1.0, text="所有任务完成！")

                if not all_results:
                    st.warning("未能从任何网址中提取到有效链接。")
                    if 'url_results_df' in st.session_state:
                        del st.session_state['url_results_df']
                else:
                    st.session_state.url_results_df = pd.DataFrame(all_results)
        
        df_to_show = pd.DataFrame() # 保证df_to_show一定存在
        if 'url_results_df' in st.session_state and not st.session_state.url_results_df.empty:
            st.success(f"提取完成！共找到 {len(st.session_state.url_results_df)} 条锚文本链接。")
            df_to_show = st.session_state.url_results_df.copy()
            col1, col2 = st.columns(2)
            with col1:
                source_options = ["所有来源"] + list(df_to_show["来源页面"].unique())
                selected_source = st.selectbox("筛选来源页面:", source_options)
                if selected_source != "所有来源": df_to_show = df_to_show[df_to_show["来源页面"] == selected_source]
            with col2:
                domain_options = ["所有域名"] + list(df_to_show["目标域名"].unique())
                selected_domain = st.selectbox("筛选目标域名:", domain_options)
                if selected_domain != "所有域名": df_to_show = df_to_show[df_to_show["目标域名"] == selected_domain]
            st.dataframe(df_to_show, use_container_width=True)
            
            @st.cache_data
            def convert_df_to_csv(df): return df.to_csv(index=False).encode('utf-8-sig')
            csv = convert_df_to_csv(df_to_show)
            st.download_button(label="📥 下载当前筛选结果 (CSV)", data=csv, file_name="url_link_results.csv", mime="text/csv")
        
        # ========= 新增：单行内容复制功能 =========
        st.markdown("---")
        st.subheader("📋 单行内容复制")

        if not df_to_show.empty:
            # 为了在选择框中显示清晰，我们创建一个临时的显示列
            df_to_show['display_text'] = "锚文本: " + df_to_show['锚文本'].str.slice(0, 30) + "... | 目标: " + df_to_show['目标链接'].str.slice(0, 40) + "..."
            
            # 使用索引作为选项，这样更稳定
            selected_index = st.selectbox(
                "选择要复制的行:",
                options=df_to_show.index,
                format_func=lambda x: df_to_show.loc[x, 'display_text']
            )

            if selected_index is not None:
                selected_row = df_to_show.loc[selected_index]
                anchor_text_to_copy = selected_row['锚文本']
                link_to_copy = selected_row['目标链接']

                col_copy_1, col_copy_2 = st.columns(2)
                with col_copy_1:
                    st.text_area("要复制的锚文本", anchor_text_to_copy, height=100, key="copy_anchor")
                    copy_button(anchor_text_to_copy, "复制锚文本")
                
                with col_copy_2:
                    st.text_area("要复制的目标链接", link_to_copy, height=100, key="copy_link")
                    copy_button(link_to_copy, "复制目标链接")
        else:
            st.info("当前没有可复制的数据。")


    with tab2:
        st.header("从Word文档 (.docx) 提取链接")
        uploaded_file = st.file_uploader("上传一个.docx文件", type=["docx"], key="docx_uploader")
        
        if uploaded_file is not None:
            with st.spinner("正在解析文档..."):
                st.session_state.docx_df = extract_links_from_docx(uploaded_file)
        
        if 'docx_df' in st.session_state and not st.session_state.docx_df.empty:
            df_docx_to_show = st.session_state.docx_df
            st.success(f"解析完成！共找到 {len(df_docx_to_show)} 条链接。")
            st.dataframe(df_docx_to_show, use_container_width=True)
            
            @st.cache_data
            def convert_df_to_csv_docx(df): return df.to_csv(index=False).encode('utf-8-sig')

            csv_docx = convert_df_to_csv_docx(df_docx_to_show)
            st.download_button(label="📥 下载结果 (CSV)", data=csv_docx, file_name="docx_link_results.csv", mime="text/csv", key="docx_downloader")


# --- 登录与路由逻辑 (保持不变) ---
if 'users' not in st.session_state: st.session_state['users'] = {"admin": "1008611"}
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

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
        if new_user in st.session_state['users']: st.warning("用户已存在！")
        elif not new_user or not new_pass: st.warning("用户名和密码不能为空！")
        else:
            st.session_state['users'][new_user] = new_pass
            st.success(f"添加用户 {new_user} 成功！")

if not st.session_state['logged_in']:
    login()
else:
    st.sidebar.title("管理菜单")
    option = st.sidebar.selectbox("选择操作", ["主页", "添加用户", "退出登录"])
    if option == "主页": main_app()
    elif option == "添加用户": add_user()
    elif option == "退出登录":
        st.session_state['logged_in'] = False
        st.rerun()