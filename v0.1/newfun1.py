import requests
from bs4 import BeautifulSoup
import logging
import re
import html2text
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import json
import glob
from openpyxl import Workbook

class WebContentProcessor:
    def __init__(self, use_selenium=False):
        self.session = requests.Session()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.h2t = html2text.HTML2Text()
        self.h2t.body_width = 0
        self.h2t.ignore_links = True
        self.h2t.ignore_images = True
        self.h2t.ignore_emphasis = True
        self.keywords = ["简介", "研究方向", "教育背景", "工作经历", "研究成果", "教学工作", "联系方式"]
        self.use_selenium = use_selenium
        if self.use_selenium:
            self.chrome_options = Options()
            self.chrome_options.add_argument("--headless")

    def fetch_webpage(self, url):
        try:
            response = self.session.get(url)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except requests.RequestException as e:
            self.logger.error(f"获取网页时出错: {e}")
            return None

    def fetch_webpage_selenium(self, url):
        driver = webdriver.Chrome(options=self.chrome_options)
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            return driver.page_source
        finally:
            driver.quit()

    def extract_content_v1(self, html, teacher_name):
        soup = BeautifulSoup(html, 'html.parser')
        
        for tag in soup(['header', 'footer']):
            tag.decompose()
        
        body = soup.find('body')
        if not body:
            self.logger.error("网页中未找到body标签")
            return None

        name_element = body.find(text=re.compile(teacher_name))
        if not name_element:
            self.logger.error(f"网页中未找到教师姓名 '{teacher_name}'")
            return None

        content = name_element.find_parent()
        content_html = ''.join(str(tag) for tag in content.next_siblings)
        content_html = str(content) + content_html

        return content_html

    def extract_content_v2(self, html, teacher_name):
        soup = BeautifulSoup(html, 'html.parser')
        
        for tag in soup(['header', 'footer', 'nav', 'aside']):
            tag.decompose()
        
        content = []
        
        name_element = soup.find(text=re.compile(teacher_name))
        if name_element:
            content.append(str(name_element.find_parent()))

        for keyword in self.keywords:
            elements = soup.find_all(text=re.compile(keyword))
            for element in elements:
                parent = element.find_parent()
                if parent:
                    content.append(str(parent))
                    next_sibling = parent.find_next_sibling()
                    if next_sibling:
                        content.append(str(next_sibling))

        if len(content) < 3:
            main_content = soup.find('main') or soup.find(id='content') or soup.find(class_='content')
            if main_content:
                content.append(str(main_content))

        return '\n'.join(self.remove_duplicates(content))

    def remove_duplicates(self, elements):
        seen = set()
        return [x for x in elements if not (x in seen or seen.add(x))]

    def preprocess_text(self, raw_html):
        soup = BeautifulSoup(raw_html, 'html.parser')
        text = soup.get_text()
        
        text = re.sub(r'\|', '', text)
        text = re.sub(r'-{3,}', '', text)
        text = re.sub(r'\n+', '\n', text)
        text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
        
        text = self.clean_encrypted_email(text)
        
        # 额外的去重步骤
        lines = text.split('\n')
        text = '\n'.join(self.remove_duplicates(lines))
        
        return text

    def clean_encrypted_email(self, text):
        return re.sub(r'[a-f0-9]{256,}', '[加密的邮箱地址]', text)

    def html_to_markdown(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')

        for tag in soup(['p', 'div', 'section']):
            if tag.name == 'p':
                tag.insert_after(soup.new_string('\n\n'))
            else:
                tag.insert_before(soup.new_string('\n\n'))
                tag.insert_after(soup.new_string('\n\n'))

        markdown = self.h2t.handle(str(soup))
        markdown = self.clean_markdown(markdown)

        return markdown

    def clean_markdown(self, markdown):
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        markdown = re.sub(r'(\S)\n{2,}(\S)', r'\1\n\n\2', markdown)
        markdown = re.sub(r'^ +', '', markdown, flags=re.MULTILINE)
        
        # 额外的去重步骤
        lines = markdown.split('\n')
        markdown = '\n'.join(self.remove_duplicates(lines))
        
        return markdown.strip()

    def generate_markdown(self, name, content):
        return f"# {name}\n\n{content}"

    def save_output(self, name, markdown_content, text_content, output_dir="output"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        md_filename = os.path.join(output_dir, f"{name}_cleaned.md")
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        text_filename = os.path.join(output_dir, f"{name}_cleaned.txt")
        with open(text_filename, "w", encoding="utf-8") as f:
            f.write(text_content)

        print(f"输出已保存到 {md_filename} 和 {text_filename}")

    def contains_email(self, content):
        return re.search(r'[^\s@]+@[^\s@]+\.[^\s@]+', content) is not None

    def merge_content(self, content1, content2):
        # 合并两个内容并去重
        combined = content1 + '\n' + content2
        lines = combined.split('\n')
        return '\n'.join(self.remove_duplicates(lines))

    def process(self, url, teacher_name):
        html = self.fetch_webpage(url)
        if html:
            content_html_v1 = self.extract_content_v1(html, teacher_name)
            content_html_v2 = self.extract_content_v2(html, teacher_name)
            
            if self.use_selenium and (not self.contains_email(content_html_v1) and not self.contains_email(content_html_v2)):
                self.logger.info("静态内容中未找到邮箱地址，尝试使用Selenium")
                html = self.fetch_webpage_selenium(url)
                content_html_v1 = self.extract_content_v1(html, teacher_name)
                content_html_v2 = self.extract_content_v2(html, teacher_name)
            
            if content_html_v1 and content_html_v2:
                # 合并两种方法的结果并去重
                content_html = self.merge_content(content_html_v1, content_html_v2)
                
                markdown_content = self.html_to_markdown(content_html)
                text_content = self.preprocess_text(content_html)
                markdown_with_title = self.generate_markdown(teacher_name, markdown_content)
                self.save_output(teacher_name, markdown_with_title, text_content)
            else:
                self.logger.error("两种方法都未能提取到内容")
        else:
            self.logger.error("获取网页失败")

def process_teachers(teachers_data, use_selenium=False):
    processor = WebContentProcessor(use_selenium=use_selenium)
    results = []

    for teacher in teachers_data:
        name = teacher['name']
        url = teacher['url']
        print(f"Processing: {name}")
        
        if not url:  # 检查 URL 是否为空字符串
            logging.warning(f"Teacher {name} has no URL. Skipping.")
            results.append({
                'Name': name,
                'URL': '',
                'Markdown Content': f"# {name}\n\n没有可用的URL",
                'Text Content': f"{name}\n没有可用的URL"
            })
            continue
        
        processor.process(url, name)
        
        # 读取生成的文件内容
        md_filename = os.path.join("output", f"{name}_cleaned.md")
        txt_filename = os.path.join("output", f"{name}_cleaned.txt")
        
        try:
            with open(md_filename, "r", encoding="utf-8") as f:
                markdown_content = f.read()
            
            with open(txt_filename, "r", encoding="utf-8") as f:
                text_content = f.read()
        except FileNotFoundError:
            logging.error(f"Files for {name} not found. Skipping.")
            markdown_content = f"# {name}\n\n处理过程中出错"
            text_content = f"{name}\n处理过程中出错"
        
        results.append({
            'Name': name,
            'URL': url,
            'Markdown Content': markdown_content,
            'Text Content': text_content
        })

    return results

def save_to_excel(results, output_file):
    df = pd.DataFrame(results)
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"Results saved to {output_file}")

def read_json_files(folder_path):
    teachers_data = []
    json_files = glob.glob(os.path.join(folder_path, '*.json'))
    
    if not json_files:
        logging.error(f"No JSON files found in {folder_path}")
        return teachers_data

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    logging.warning(f"File {json_file} is empty")
                    continue
                data = json.loads(content)
                teachers_data.extend(data)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error in file {json_file}: {str(e)}")
            with open(json_file, 'r', encoding='utf-8') as f:
                logging.error(f"First 100 characters of file: {f.read(100)}")
        except IOError as e:
            logging.error(f"IO error with file {json_file}: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error processing file {json_file}: {str(e)}")
    
    if not teachers_data:
        logging.warning("No valid teacher data found in any JSON file")
    
    return teachers_data

# 在主程序中
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_folder = os.path.join(script_dir, 'urls')
    
    print(f"Looking for JSON files in: {json_folder}")
    json_files = glob.glob(os.path.join(json_folder, '*.json'))
    print(f"Found {len(json_files)} JSON files")
    
    teachers_data = read_json_files(json_folder)
    if teachers_data:
        print(f"Successfully loaded data for {len(teachers_data)} teachers")
    else:
        print("No teacher data loaded. Check the error logs.")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_folder = os.path.join(script_dir, 'urls')
    output_excel = os.path.join(script_dir, 'teachers_info.xlsx')
    use_selenium = False  # 是否使用 Selenium

    teachers_data = read_json_files(json_folder)
    results = process_teachers(teachers_data, use_selenium=use_selenium)
    save_to_excel(results, output_excel)