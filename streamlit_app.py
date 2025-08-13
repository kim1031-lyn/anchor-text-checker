import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import mammoth
import io
import streamlit.components.v1 as components
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

# --- 页面基础设置 ---
st.set_page_config(page_title="Time is Gold", layout="wide")

# --- 样式定义 ---
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- JavaScript代码：用于在单元格内创建复制按钮 ---
js_copy_button_renderer = JsCode("""
class CopyButtonRenderer {
    eGui;
    init(params) {
        if (params.value === null || params.value === undefined) {
            this.eGui = document.createElement('span');
            this.eGui.innerText = '';
            return;
        }

        this.eGui = document.createElement('div');
        this.eGui.style.display = 'flex';
        this.eGui.style.alignItems = 'center';
        this.eGui.style.justifyContent = 'space-between';
        
        const text = document.createElement('span');
        text.style.whiteSpace = 'normal';
        text.style.overflow = 'hidden';
        text.style.textOverflow = 'ellipsis';
        text.innerText = params.value;
        this.eGui.appendChild(text);

        if (params.value !== '无法抓取，需要手动打开检查。') {
            const button = document.createElement('button');
            button.innerText = '复制';
            button.style.cssText = "padding: 2px 8px; font-size: 12px; margin-left: 10px; border: 1px solid #ccc; border-radius: 4px; cursor: pointer;";
            
            button.addEventListener('click', () => {
                navigator.clipboard.writeText(params.value).then(() => {
                    button.innerText = '已复制!';
                    setTimeout(() => {
                        button.innerText = '复制';
                    }, 2000);
                }).catch(err => {
                    console.error('无法复制: ', err);
                });
            });
            this.eGui.appendChild(button);
        }
    }
    getGui() {
        return this.eGui;
    }
}
""")


# --- 核心功能与辅助函数 ---
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

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
        return 'success', anchors_data
    except requests.RequestException as e:
        st.error(f"抓取失败: {url} (原因: {e})", icon="🚨")
        return 'failure', url

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
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700&display=swap');
            .title-container { padding: 1.5rem 2rem; border-radius: 15px; text-align: center; color: white; background: linear-gradient(-45deg, #0f2027, #203a43, #2c5364); background-size: 400% 400%; animation: gradientBG 15s ease infinite; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); border: 1px solid rgba(255, 255, 255, 0.18); }
            .title-container h1 { font-family: 'Cinzel', serif; font-size: 3rem; letter-spacing: 0.1em; text-shadow: 2px 2px 8px rgba(0, 0, 0, 0.6); }
            @keyframes gradientBG { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        </style>
        <div class="title-container"><h1>TIME is GOLD</h1></div>
        """,
        unsafe_allow_html=True
    )
    st.write("")

    tab1, tab2 = st.tabs(["🔗 网址锚文本提取", "📄 Word文档链接提取"])

    with tab1:
        st.header("从网页URL提取链接")
        url_input = st.text_area("输入网址 (每行一个)", height=150, placeholder="https://example.com/page1\nhttps://example.com/page2", key="url_input")
        
        if 'url_results_df' not in st.session_state: st.session_state.url_results_df = pd.DataFrame()
        if 'submitted_urls' not in st.session_state: st.session_state.submitted_urls = []

        if st.button("🚀 开始提取 (后端模式)", type="primary"):
            raw_urls = [u.strip() for u in url_input.split('\n') if u.strip()]
            urls = list(dict.fromkeys(raw_urls))
            st.session_state.submitted_urls = urls
            
            if not urls:
                st.warning("请输入至少一个有效网址。")
            else:
                all_results = []
                progress_bar = st.progress(0, text="准备开始抓取...")
                for i, url in enumerate(urls):
                    progress_bar.progress((i + 1) / len(urls), text=f"正在处理: {url}")
                    status, data = fetch_and_parse_url(url)
                    if status == 'success':
                        if not data:
                            all_results.append({ "来源页面": url, "文章上线时间": "N/A", "锚文本": "页面内未找到链接", "目标链接": "N/A", "目标域名": "N/A", "链接类型": "N/A" })
                        else:
                            all_results.extend(data)
                    elif status == 'failure':
                        all_results.append({ "来源页面": data, "文章上线时间": "---", "锚文本": "无法抓取，需要手动打开检查。", "目标链接": "无法抓取，需要手动打开检查。", "目标域名": "---", "链接类型": "---" })
                progress_bar.progress(1.0, text="所有任务完成！")
                if not all_results:
                    st.warning("未能从任何网址中提取到有效链接或所有链接均抓取失败。")
                    st.session_state.url_results_df = pd.DataFrame()
                else:
                    temp_df = pd.DataFrame(all_results)
                    temp_df['来源页面'] = pd.Categorical(temp_df['来源页面'], categories=urls, ordered=True)
                    st.session_state.url_results_df = temp_df.sort_values('来源页面')
        
        if not st.session_state.url_results_df.empty:
            st.success(f"处理完成！共生成 {len(st.session_state.url_results_df)} 条记录。")
            
            st.markdown("##### 筛选与导航")

            # --- Part 1: Initialize all needed state variables ---
            if "current_source_index" not in st.session_state:
                st.session_state.current_source_index = 0
            if "domain_selection" not in st.session_state:
                st.session_state.domain_selection = "所有域名"
            if "is_locked" not in st.session_state:
                st.session_state.is_locked = False

            # --- Part 2: Define Callbacks ---
            def handle_source_change():
                st.session_state.current_source_index = st.session_state.source_options.index(st.session_state.source_selector_widget)

            def handle_domain_change():
                st.session_state.domain_selection = st.session_state.domain_selector_widget

            def handle_lock_change():
                st.session_state.is_locked = st.session_state.lock_widget
                if st.session_state.is_locked:
                    st.session_state.domain_selection = st.session_state.domain_selector_widget

            # --- Part 3: Prepare data for widgets ---
            source_options = ["所有来源"] + st.session_state.get('submitted_urls', [])
            st.session_state.source_options = source_options

            domain_options = ["所有域名"] + sorted(st.session_state.url_results_df["目标域名"].dropna().unique().tolist())

            if st.session_state.current_source_index >= len(source_options):
                st.session_state.current_source_index = 0

            # --- Part 4: Create Widgets ---
            filter_cols = st.columns([2, 0.5, 0.5, 1.5])
            
            with filter_cols[0]:
                selected_source = st.selectbox(
                    "筛选来源页面:", 
                    options=source_options,
                    index=st.session_state.current_source_index,
                    key='source_selector_widget', 
                    on_change=handle_source_change
                )
            with filter_cols[1]:
                st.write(""); st.write("")
                if st.button("⬅️ 上一个", use_container_width=True):
                    if st.session_state.current_source_index > 0:
                        st.session_state.current_source_index -= 1
                        st.rerun()
            with filter_cols[2]:
                st.write(""); st.write("")
                if st.button("下一个 ➡️", use_container_width=True):
                    if st.session_state.current_source_index < len(source_options) - 1:
                        st.session_state.current_source_index += 1
                        st.rerun()
            with filter_cols[3]:
                if st.session_state.is_locked:
                    value_to_show = st.session_state.domain_selection
                else:
                    value_to_show = st.session_state.get('domain_selector_widget', '所有域名')
                
                try:
                    current_domain_index = domain_options.index(value_to_show)
                except ValueError:
                    current_domain_index = 0

                st.checkbox("锁定目标域名", key="lock_widget", value=st.session_state.is_locked, on_change=handle_lock_change)
                selected_domain = st.selectbox(
                    "筛选目标域名:",
                    options=domain_options,
                    index=current_domain_index,
                    key='domain_selector_widget',
                    on_change=handle_domain_change
                )

            # --- Part 5: Apply filters for display ---
            df_to_display = st.session_state.url_results_df.copy()
            if selected_source != "所有来源":
                df_to_display = df_to_display[df_to_display["来源页面"] == selected_source]
            
            final_domain_for_filtering = st.session_state.domain_selection if st.session_state.is_locked else selected_domain
            if final_domain_for_filtering != "所有域名":
                df_to_display = df_to_display[df_to_display["目标域名"] == final_domain_for_filtering]

            gb = GridOptionsBuilder.from_dataframe(df_to_display)
            gb.configure_default_column(resizable=True, wrapText=True, autoHeight=True, sortable=False)
            gb.configure_column("锚文本", cellRenderer=js_copy_button_renderer, width=300)
            gb.configure_column("目标链接", cellRenderer=js_copy_button_renderer, width=450)
            grid_options = gb.build()

            AgGrid(
                df_to_display, 
                gridOptions=grid_options, 
                allow_unsafe_jscode=True, 
                height=600, 
                width='100%', 
                theme='streamlit', 
                enable_enterprise_modules=False, 
                key='result_grid'
            )
            
            csv = convert_df_to_csv(st.session_state.url_results_df) 
            st.download_button(
                label="📥 下载所有结果 (CSV)", 
                data=csv, 
                file_name="url_link_results.csv", 
                mime="text/csv"
            )

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
            csv_docx = convert_df_to_csv(df_docx_to_show)
            st.download_button(
                label="📥 下载结果 (CSV)", 
                data=csv_docx, 
                file_name="docx_link_results.csv", 
                mime="text/csv", 
                key="docx_downloader"
            )

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