import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import mammoth
import io
import time
import re
from datetime import datetime
from dateutil.parser import parse

# Selenium for dynamic page handling
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
  .ag-theme-streamlit {
      --ag-header-background-color: #f0f2f6;
      --ag-header-foreground-color: #333;
      --ag-row-hover-color: #f5f5f5;
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
def get_domain_from_url(url):
  try:
      return urlparse(url).hostname.replace('www.', '')
  except:
      return ''

def is_valid_link(href, text):
  """链接有效性检查"""
  if not text or not href:
      return False
  
  invalid_patterns = [
      'javascript:', '#', 'tel:', 'mailto:', 
      '.pdf', '.jpg', '.png', '.gif', 
      'weixin.qq.com'  # 微信链接通常无法访问
  ]
  
  href_lower = href.lower()
  return not any(pattern in href_lower for pattern in invalid_patterns)

def extract_publish_date(soup):
  """改进的日期提取函数"""
  date_selectors = [
      'meta[property="article:published_time"]', 
      'meta[property="og:published_time"]',
      'meta[name="publication_date"]', 
      'meta[name="publishdate"]', 
      'meta[name="date"]',
      'time[datetime]',
      '.post-date', 
      '.entry-date',
      '.article-date'
  ]
  
  for selector in date_selectors:
      element = soup.select_one(selector)
      if element:
          date_str = element.get('content') or element.get('datetime') or element.text.strip()
          try:
              return parse(date_str).strftime('%Y-%m-%d')
          except:
              continue
  
  return "未找到"

def setup_selenium_driver():
  """配置Selenium浏览器驱动"""
  chrome_options = Options()
  chrome_options.add_argument('--headless')
  chrome_options.add_argument('--no-sandbox')
  chrome_options.add_argument('--disable-dev-shm-usage')
  
  service = Service(ChromeDriverManager().install())
  driver = webdriver.Chrome(service=service, options=chrome_options)
  return driver

def fetch_and_parse_url(url, use_selenium=False):
  """改进的URL抓取和解析函数"""
  try:
      headers = {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
      }
      
      if use_selenium:
          driver = setup_selenium_driver()
          driver.get(url)
          WebDriverWait(driver, 10).until(
              EC.presence_of_element_located((By.TAG_NAME, 'body'))
          )
          html_content = driver.page_source
          driver.quit()
          soup = BeautifulSoup(html_content, 'lxml')
      else:
          response = requests.get(url, headers=headers, timeout=15)
          response.raise_for_status()
          soup = BeautifulSoup(response.content, 'lxml')
      
      publish_date = extract_publish_date(soup)
      
      # 内容选择器列表
      content_selectors = [
          'main', 'article', '.post-content', '#content', 
          '.content', '.article-body', '.entry-content', 
          'div.content', 'div.main-content', 'section.content', 
          'body'
      ]
      
      container = None
      for selector in content_selectors:
          container = soup.select_one(selector)
          if container:
              break
      
      container = container or soup.body
      
      anchors_data = []
      for a in container.find_all('a', href=True):
          text = a.get_text(strip=True)
          href_raw = a.get('href')
          
          if not is_valid_link(href_raw, text):
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
      
      return 'success', anchors_data
  
  except Exception as e:
      st.error(f"抓取失败: {url} (原因: {str(e)})")
      return 'failure', url

def convert_df_to_csv(df):
  """转换DataFrame为CSV"""
  return df.to_csv(index=False).encode('utf-8-sig')

def extract_links_from_docx(uploaded_file):
  """从Word文档提取链接"""
  try:
      result = mammoth.convert_to_html(uploaded_file)
      html_content = result.value
      soup = BeautifulSoup(html_content, 'lxml')
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

def configure_grid_options(df):
  """配置AgGrid选项"""
  gb = GridOptionsBuilder.from_dataframe(df)
  
  # 为每列设置可复制的渲染器
  for col in df.columns:
      gb.configure_column(
          col, 
          cellRenderer=js_copy_button_renderer, 
          autoHeight=True, 
          wrapText=True
      )
  
  # 设置网格样式和行为
  gb.configure_grid_options(
      enableRangeSelection=True,
      rowHeight=60,
      suppressHorizontalScroll=False,
      suppressVerticalScroll=False
  )
  
  return gb.build()

def main_app():
  """主应用程序界面"""
  st.markdown(
      """
      <style>
          @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@700&display=swap');
          .title-container { 
              padding: 1.5rem 2rem; 
              border-radius: 15px; 
              text-align: center; 
              color: white; 
              background: linear-gradient(-45deg, #0f2027, #203a43, #2c5364); 
              background-size: 400% 400%; 
              animation: gradientBG 15s ease infinite; 
              box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); 
              border: 1px solid rgba(255, 255, 255, 0.18); 
          }
          .title-container h1 { 
              font-family: 'Cinzel', serif; 
              font-size: 3rem; 
              letter-spacing: 0.1em; 
              text-shadow: 2px 2px 8px rgba(0, 0, 0, 0.6); 
          }
          @keyframes gradientBG { 
              0% { background-position: 0% 50%; } 
              50% { background-position: 100% 50%; } 
              100% { background-position: 0% 50%; } 
          }
      </style>
      <div class="title-container"><h1>TIME is GOLD</h1></div>
      """,
      unsafe_allow_html=True
  )
  st.write("")

  tab1, tab2 = st.tabs(["\U0001F517 网址锚文本提取", "\U0001F4C4 Word文档链接提取"])

  with tab1:
      st.header("从网页URL提取链接")
      url_input = st.text_area(
          "输入网址 (每行一个)", 
          height=150, 
          placeholder="https://example.com/page1\nhttps://example.com/page2", 
          key="url_input"
      )
      
      # 初始化会话状态
      if 'url_results_df' not in st.session_state:
          st.session_state.url_results_df = pd.DataFrame()
      if 'submitted_urls' not in st.session_state:
          st.session_state.submitted_urls = []

      # 抓取按钮
      if st.button("\U0001F680 开始提取 (后端模式)", type="primary"):
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
                          all_results.append({
                              "来源页面": url, 
                              "文章上线时间": "N/A", 
                              "锚文本": "页面内未找到链接", 
                              "目标链接": "N/A", 
                              "目标域名": "N/A", 
                              "链接类型": "N/A"
                          })
                      else:
                          all_results.extend(data)
                  elif status == 'failure':
                      all_results.append({
                          "来源页面": data, 
                          "文章上线时间": "---", 
                          "锚文本": "无法抓取，需要手动打开检查。", 
                          "目标链接": "无法抓取，需要手动打开检查。", 
                          "目标域名": "---", 
                          "链接类型": "---"
                      })
              
              progress_bar.progress(1.0, text="所有任务完成！")
              
              if not all_results:
                  st.warning("未能从任何网址中提取到有效链接或所有链接均抓取失败。")
                  st.session_state.url_results_df = pd.DataFrame()
              else:
                  temp_df = pd.DataFrame(all_results)
                  temp_df['来源页面'] = pd.Categorical(temp_df['来源页面'], categories=urls, ordered=True)
                  st.session_state.url_results_df = temp_df.sort_values('来源页面')

      # 结果展示区域
      if not st.session_state.url_results_df.empty:
          st.success(f"处理完成！共生成 {len(st.session_state.url_results_df)} 条记录。")
          
          # 配置网格选项
          grid_options = configure_grid_options(st.session_state.url_results_df)
          
          # 展示AgGrid
          AgGrid(
              st.session_state.url_results_df, 
              gridOptions=grid_options, 
              allow_unsafe_jscode=True, 
              height=600, 
              width='100%', 
              theme='streamlit', 
              enable_enterprise_modules=False, 
              key='result_grid'
          )
          
          # 导出按钮
          csv = convert_df_to_csv(st.session_state.url_results_df)
          st.download_button(
              label="\U0001F4E5 导出结果 (CSV)", 
              data=csv, 
              file_name="url_link_results.csv", 
              mime="text/csv", 
              key="url_results_downloader"
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
          
          # 配置网格选项
          grid_options_docx = configure_grid_options(df_docx_to_show)
          
          # 展示AgGrid
          AgGrid(
              df_docx_to_show, 
              gridOptions=grid_options_docx, 
              allow_unsafe_jscode=True, 
              height=400, 
              width='100%', 
              theme='streamlit', 
              enable_enterprise_modules=False, 
              key='docx_grid'
          )
          
          csv_docx = convert_df_to_csv(df_docx_to_show)
          st.download_button(
              label="\U0001F4E5 下载结果 (CSV)", 
              data=csv_docx, 
              file_name="docx_link_results.csv", 
              mime="text/csv", 
              key="docx_downloader"
          )

# --- 登录与路由逻辑 ---
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

# 主程序入口
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