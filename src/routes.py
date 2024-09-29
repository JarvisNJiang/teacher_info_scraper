from flask import Blueprint, render_template, request, Response, stream_with_context, jsonify, current_app
from .utils import contains_chinese
from src.config import Config, URLS_FOLDER, OUTPUT_FOLDER
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from src.teacher_info_processor import process_json_files_with_progress
from lxml import etree
import json
import os
import logging
from functools import wraps
from urllib.parse import urljoin
import time


main = Blueprint('main', __name__)

def init_webdriver():
    options = Options()
    options.add_argument("--headless")
    return webdriver.Firefox(options=options)

def error_handler(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.exception(f"Error in {f.__name__}: {str(e)}")
            return jsonify({"error": str(e)}), 500
    return decorated_function

@main.route('/')
def index():
    return render_template('index.html')

def get_best_column_xpath(driver):
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    xpaths = [
        "//table//tr/td[1]",
        "//tr/td[1]",
        "//*[contains(@class, 'table')]//tr/td[1]",
        "//div[contains(@class, 'table')]//tr/td[1]"
    ]

    best_xpath = max(xpaths, key=lambda xpath: len([e for e in driver.find_elements(By.XPATH, xpath) 
                                                    if e.find_elements(By.XPATH, './/a') and contains_chinese(e.text.strip())]), 
                     default=None)

    if best_xpath:
        best_xpath += "[.//a and string-length(normalize-space(.)) > 0]"
        if not best_xpath.startswith("/html/body/"):
            best_xpath = "/html/body" + best_xpath

    return best_xpath

@main.route('/extract')
@error_handler
def extract_xpath():
    url = request.args.get('url')
    institute_name = request.args.get('instituteName')
    
    if not url or not institute_name:
            return jsonify({"error": "URL and institute name are required"}), 400

    def generate(url, institute_name):
        with init_webdriver() as driver:
            driver.get(url)
            best_xpath = get_best_column_xpath(driver)
            
            if not best_xpath:
                yield f"data: {json.dumps({'error': '未找到符合条件的XPath'})}\n\n"
                return

            elements = driver.find_elements(By.XPATH, best_xpath.replace("[.//a and string-length(normalize-space(.)) > 0]", ""))
            total_elements = len(elements)
            
            is_bold = driver.execute_script("""
                var style = window.getComputedStyle(arguments[0]);
                return style.getPropertyValue('font-weight') >= 700 || style.getPropertyValue('font-weight') === 'bold';
            """, elements[0])
            
            start_index = 1 if is_bold else 0
            teachers_info = []

            for index, element in enumerate(elements[start_index:], start=start_index):
                name = element.text.strip()
                if name:
                    link_element = element.find_elements(By.XPATH, './/a')
                    url = link_element[0].get_attribute('href') if link_element else ''
                    teachers_info.append({"name": name, "url": url})
                
                progress = (index - start_index + 1) / (total_elements - start_index) * 100
                yield f"data: {json.dumps({'progress': progress})}\n\n"
            
            json_filename = save_to_json(institute_name, teachers_info)
            
            yield f"data: {json.dumps({'xpath': best_xpath, 'teachers_info': teachers_info, 'json_file': json_filename})}\n\n"

    return Response(stream_with_context(generate(url, institute_name)), content_type='text/event-stream')

def save_to_json(institute_name, teachers_info):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    urls_folder = os.path.join(current_dir, 'urls')
    os.makedirs(urls_folder, exist_ok=True)
    
    filename = os.path.join(urls_folder, f"{institute_name}.json")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(teachers_info, f, ensure_ascii=False, indent=2)
    
    return filename

@main.route('/process_all', methods=['GET', 'POST'])
@error_handler
def process_all():
    current_app.logger.info("开始处理所有数据")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_folder = os.path.join(current_dir, 'urls')
    output_folder = os.path.join(current_dir, '人员信息结果')
    use_selenium = False

    def generate():
        for progress_data in process_json_files_with_progress(json_folder, output_folder, use_selenium):
            yield f"data: {progress_data}\n\n"
        yield "event: done\ndata: Processing completed\n\n"

    return Response(stream_with_context(generate()), content_type='text/event-stream')

@main.route('/extract_custom', methods=['POST'])
def extract_custom_xpath():
    current_app.logger.info("Starting extract_custom_xpath function")
    data = request.json
    current_app.logger.info(f"Received data: {data}")
    
    url = data.get('url')
    institute_name = data.get('instituteName')
    custom_xpath = data.get('xpath')
    
    current_app.logger.info(f"Parsed request: URL={url}, Institute={institute_name}, XPath={custom_xpath}")
    
    if not url or not institute_name or not custom_xpath:
        current_app.logger.error("Missing required parameters")
        return jsonify({"error": "All parameters (URL, institute name, and XPath) are required"}), 400

    def generate():
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            current_app.logger.info(f"Sending GET request to {url}")
            driver.get(url)
            
            # 等待 XPath 元素加载
            elements = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, custom_xpath))
            )
            
            current_app.logger.info(f"Found {len(elements)} elements matching the XPath")
            
            if not elements:
                current_app.logger.warning("No elements found matching the XPath")
                yield f"data: {json.dumps({'error': 'No elements found matching the XPath'})}\n\n"
                return

            teachers_info = []
            for i, element in enumerate(elements):
                try:
                    # 使用 JavaScript 获取元素的文本内容
                    name = driver.execute_script("return arguments[0].innerText;", element).strip()
                    href = element.get_attribute('href')
                    if href:
                        href = urljoin(url, href)
                    teachers_info.append({'name': name, 'url': href})
                    yield f"data: {json.dumps({'progress': (i + 1) / len(elements) * 100})}\n\n"
                except Exception as e:
                    current_app.logger.error(f"Error processing element {i+1}: {str(e)}", exc_info=True)
                    yield f"data: {json.dumps({'error': f'Error processing element {i+1}: {str(e)}'})}\n\n"

            # 保存为 JSON 文件
            json_filename = save_to_json(institute_name, teachers_info)
            
            yield f"data: {json.dumps({'teachers_info': teachers_info, 'json_file': json_filename})}\n\n"
            current_app.logger.info(f"Extraction completed successfully. JSON saved as {json_filename}")
        except Exception as e:
            current_app.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'error': f'Unexpected error: {str(e)}'})}\n\n"
        finally:
            driver.quit()

    current_app.logger.info("Finished extract_custom_xpath function")
    return Response(stream_with_context(generate()), content_type='text/event-stream')



def save_to_json(institute_name, teachers_info):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    urls_folder = os.path.join(current_dir, 'urls')
    os.makedirs(urls_folder, exist_ok=True)
    
    # 使用机构名称作为文件名，移除可能的非法字符
    safe_name = "".join([c for c in institute_name if c.isalnum() or c in (' ', '_')]).rstrip()
    filename = os.path.join(urls_folder, f"{safe_name}.json")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(teachers_info, f, ensure_ascii=False, indent=2)
    
    return filename

@main.route('/custom_xpath')
@error_handler
def custom_xpath():
    return render_template('custom_xpath.html')


