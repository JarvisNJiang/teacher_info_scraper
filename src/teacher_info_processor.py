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
from tqdm import tqdm

class WebContentProcessor:
    def is_valid_name(self, name):
        # 定义一个合法姓名的模式，可以根据实际需求调整
        pattern = r'^[\u4e00-\u9fa5a-zA-Z\s]{2,20}$'
        return bool(re.match(pattern, name))

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
                content_html = self.merge_content(content_html_v1, content_html_v2)
                
                markdown_content = self.html_to_markdown(content_html)
                text_content = self.preprocess_text(content_html)
                markdown_with_title = self.generate_markdown(teacher_name, markdown_content)
                return markdown_with_title, text_content
            else:
                self.logger.error("两种方法都未能提取到内容")
                return None, None
        else:
            self.logger.error("获取网页失败")
            return None, None



def process_teachers(teachers_data, use_selenium=False, pbar=None):
    processor = WebContentProcessor(use_selenium=use_selenium)
    results = []

    for teacher in teachers_data:
        name = teacher['name']
        url = teacher['url']
        
        if not processor.is_valid_name(name):
            logging.warning(f"Invalid teacher name: '{name}'. Skipping.")
            results.append({
                '姓名': name,
                '人员简介': f"# {name}\n\n无效的教师姓名",
                'URL': url
            })
            if pbar:
                pbar.update(1)
            continue

        if not url:
            logging.warning(f"Teacher {name} has no URL. Skipping.")
            results.append({
                '姓名': name,
                '人员简介': f"# {name}\n\n没有可用的URL",
                'URL': ''
            })
            if pbar:
                pbar.update(1)
            continue
        
        markdown_content, _ = processor.process(url, name)
        
        if markdown_content is None:
            logging.error(f"Processing failed for {name}. Skipping.")
            markdown_content = f"# {name}\n\n处理过程中出错"
        
        results.append({
            '姓名': name,
            '人员简介': markdown_content,
            'URL': url
        })
        if pbar:
            pbar.update(1)

    return results

def save_to_excel(results, output_file):
    df = pd.DataFrame(results)
    # 确保列的顺序正确
    df = df[['姓名', '人员简介', 'URL']]
    df.to_excel(output_file, index=False, engine='openpyxl')
    print(f"Results saved to {output_file}")

def read_json_files(folder_path):
    all_data = []
    processor = WebContentProcessor()  # 创建一个实例来使用 is_valid_name 方法
    for filename in os.listdir(folder_path):
        if filename.endswith('.json'):
            file_path = os.path.join(folder_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if not content.strip():
                        logging.warning(f"File {filename} is empty. Skipping.")
                        continue
                    data = json.loads(content)
                    # 过滤掉无效的教师名称
                    valid_data = [teacher for teacher in data if processor.is_valid_name(teacher['name'])]
                    if len(valid_data) < len(data):
                        logging.warning(f"Filtered out {len(data) - len(valid_data)} invalid entries in {filename}")
                    all_data.append((os.path.splitext(filename)[0], valid_data))
            except json.JSONDecodeError as e:
                logging.error(f"Error decoding JSON in file {filename}: {str(e)}")
            except Exception as e:
                logging.error(f"Error reading file {filename}: {str(e)}")
    return all_data

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def process_json_files(json_folder, output_folder, use_selenium=False):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    os.makedirs(output_folder, exist_ok=True)

    json_files_data = read_json_files(json_folder)
    
    if not json_files_data:
        logging.error("No valid JSON data found. Exiting.")
        print("错误：未找到有效的JSON数据")
        return False

    total_teachers = sum(len(teachers) for _, teachers in json_files_data)
    
    with tqdm(total=total_teachers, desc="总体进度", unit="位", position=0, leave=True) as pbar:
        for json_filename, teachers_data in json_files_data:
            logging.info(f"Processing data from {json_filename}.json")
            
            results = process_teachers(teachers_data, use_selenium=use_selenium, pbar=pbar)
            
            output_excel = os.path.join(output_folder, f"{json_filename}.xlsx")
            save_to_excel(results, output_excel)
            logging.info(f"Results for {json_filename} saved to {output_excel}")

    print("\n处理完成！")
    return True

def process_json_files_with_progress(json_folder, output_folder, use_selenium=False):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    os.makedirs(output_folder, exist_ok=True)

    json_files_data = read_json_files(json_folder)
    
    if not json_files_data:
        logging.error("No valid JSON data found. Exiting.")
        yield json.dumps({"status": "error", "message": "未找到有效的JSON数据"})
        return

    total_files = len(json_files_data)
    total_teachers = sum(len(teachers) for _, teachers in json_files_data)
    
    with tqdm(total=total_teachers, desc="总体进度", unit="位", position=0, leave=True) as pbar:
        for file_index, (json_filename, teachers_data) in enumerate(json_files_data, 1):
            logging.info(f"Processing data from {json_filename}.json")
            yield json.dumps({
                "status": "processing",
                "file": json_filename,
                "progress": f"{file_index}/{total_files}",
                "total_teachers": total_teachers,
                "current_teacher": pbar.n
            })
            
            results = process_teachers(teachers_data, use_selenium=use_selenium, pbar=pbar)
            
            output_excel = os.path.join(output_folder, f"{json_filename}.xlsx")
            save_to_excel(results, output_excel)
            logging.info(f"Results for {json_filename} saved to {output_excel}")
            
            yield json.dumps({
                "status": "file_completed",
                "file": json_filename,
                "progress": f"{file_index}/{total_files}",
                "total_teachers": total_teachers,
                "current_teacher": pbar.n
            })

    yield json.dumps({"status": "finished", "total_teachers": total_teachers})


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_folder = os.path.join(script_dir, 'urls')
    output_folder = os.path.join(script_dir, '人员信息结果')
    use_selenium = False  # 是否使用 Selenium

    # 如果直接运行这个脚本，使用原有的函数
    process_json_files(json_folder, output_folder, use_selenium)