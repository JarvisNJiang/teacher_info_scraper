import os
import json
import re
import pandas as pd
import argparse
import logging
import time
import hashlib
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from tqdm import tqdm



# 设置日志
def setup_logger(log_level):
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)

# 设置目录结构
def setup_directories(base_dir, university_name):
    output_dir = os.path.join(base_dir, "output", university_name)
    personnel_dir = os.path.join(output_dir, "人员信息")
    other_dir = os.path.join(output_dir, "其他")
    
    os.makedirs(personnel_dir, exist_ok=True)
    os.makedirs(other_dir, exist_ok=True)
    
    return output_dir, personnel_dir, other_dir

# 初始化浏览器
def initialize_browser():
    browser = webdriver.Firefox()
    try:
        browser.switch_to.alert.dismiss()
    except:
        pass
    return browser

# 创建浏览器池
def create_browser_pool(num_browsers):
    return [initialize_browser() for _ in range(num_browsers)]

# 关闭浏览器池
def close_browser_pool(browser_pool):
    for browser in browser_pool:
        browser.quit()

# 等待元素加载
def wait_for_elements(browser, by, value, timeout):
    return WebDriverWait(browser, timeout).until(
        EC.presence_of_all_elements_located((by, value))
    )

# 获取链接列表
def get_links(browser, url, xpath, timeout, max_retries, logger):
    for attempt in range(max_retries):
        try:
            browser.get(url)
            links = [link.get_attribute('href') for link in wait_for_elements(browser, By.XPATH, xpath, timeout)]
            return list(set(filter(lambda x: x and "@" not in x, links)))
        except TimeoutException:
            logger.warning(f"Timeout occurred. Retrying... ({attempt + 1}/{max_retries})")
    logger.error(f"Failed to get links from {url} after {max_retries} attempts")
    return []

# 获取教师详细信息
def get_detail(browser, url, name_xpath, info_xpath, timeout, max_retries, logger):
    for attempt in range(max_retries):
        try:
            browser.get(url)
            name = wait_for_elements(browser, By.XPATH, name_xpath, timeout)[0].text.strip()
            info = wait_for_elements(browser, By.XPATH, info_xpath, timeout)[0].text.strip()
            return name, info, None
        except TimeoutException:
            logger.warning(f"Timeout occurred. Retrying... ({attempt + 1}/{max_retries})")
        except WebDriverException as e:
            logger.error(f"WebDriver error: {str(e)}")
            return None, None, str(e)
    logger.error(f"Failed to get details from {url} after {max_retries} attempts")
    return None, None, "Max retries reached"

# 保存到Excel文件
def save_to_excel(data, filename, logger):
    df = pd.DataFrame(data, columns=['Name', 'Information', 'Link'])
    
    max_retries = 3
    for i in range(max_retries):
        try:
            df.to_excel(filename, index=False)
            logger.info(f"Data saved to {filename}")
            return
        except PermissionError:
            if i < max_retries - 1:  # 如果不是最后一次尝试
                logger.warning(f"Permission denied when trying to save to {filename}. Retrying...")
                time.sleep(2)  # 等待2秒后重试
            else:  # 如果是最后一次尝试
                new_filename = f"{os.path.splitext(filename)[0]}_{int(time.time())}.xlsx"
                logger.warning(f"Unable to save to {filename} after {max_retries} attempts. Trying to save as {new_filename}")
                try:
                    df.to_excel(new_filename, index=False)
                    logger.info(f"Data saved to {new_filename}")
                except Exception as e:
                    logger.error(f"Failed to save data: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to save data: {str(e)}")
            return

# 保存错误记录
def save_error_log(errors, filename, logger):
    df = pd.DataFrame(errors, columns=['姓名', '链接', '错误原因'])
    df.to_excel(filename, index=False)
    logger.info(f"Error log saved to {filename}")

# 验证配置文件
def validate_config(config):
    required_fields = ['institute_name', 'teacher_page_urls', 'teacher_list_xpath', 'teacher_name_xpath', 'teacher_information_xpath']
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field in config: {field}")

def validate_json_configs(base_dir, university_name, logger):
    """
    验证指定大学的所有JSON配置文件。
    
    Args:
        base_dir (str): 项目的基础目录。
        university_name (str): 大学名称。
        logger (logging.Logger): 日志记录器。
    
    Returns:
        list: 包含无效配置文件名的列表。
    """
    # 构建配置文件目录路径
    config_dir = os.path.join(base_dir, "configs", university_name)
    # 获取所有JSON配置文件
    config_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
    
    invalid_configs = []

    # 使用tqdm创建进度条
    with tqdm(total=len(config_files), desc="Validating JSON configs", position=0, leave=True) as pbar:
        for config_file in config_files:
            config_path = os.path.join(config_dir, config_file)
            try:
                with open(config_path, 'r', encoding='utf-8') as file:
                    file_content = file.read()
                    if not file_content.strip():
                        # 文件为空
                        logger.error(f"Config file is empty: {config_path}")
                        invalid_configs.append(config_file)
                    else:
                        try:
                            # 尝试解析JSON
                            json.loads(file_content)
                        except json.JSONDecodeError as e:
                            # JSON解析失败
                            logger.error(f"Invalid JSON in {config_path}: {str(e)}")
                            logger.error(f"File content: {file_content}")
                            invalid_configs.append(config_file)
            except IOError as e:
                # 文件读取失败
                logger.error(f"Error reading config file {config_path}: {str(e)}")
                invalid_configs.append(config_file)
            
            # 更新进度条
            pbar.update(1)
    
    return invalid_configs

# 计算数据哈希值
def calculate_hash(data):
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

# 爬取单个教师信息
def scrape_teacher(args):
    browser, link, name_xpath, info_xpath, timeout, max_retries, logger = args
    name, info, error = get_detail(browser, link, name_xpath, info_xpath, timeout, max_retries, logger)
    if name and info:
        return name, info, link, None
    else:
        return None, None, link, error

# 爬取单个大学的信息
def scrape_university(base_dir, university_name, global_timeout, global_max_retries, num_threads, logger, browser_pool):
    config_dir = os.path.join(base_dir, "configs", university_name)
    output_dir, personnel_dir, other_dir = setup_directories(base_dir, university_name)
    
    config_files = [f for f in os.listdir(config_dir) if f.endswith('.json')]
    total_progress = len(config_files)
    
    with tqdm(total=total_progress, desc="Overall Progress", position=0, leave=True) as pbar:
        for config_file in config_files:
            with open(os.path.join(config_dir, config_file), 'r', encoding='utf-8') as file:
                data = json.load(file)

            try:
                validate_config(data)
            except ValueError as e:
                logger.error(f"Invalid config in {config_file}: {str(e)}")
                pbar.update(1)
                continue

            timeout = data.get("timeout", global_timeout)
            max_retries = data.get("max_retries", global_max_retries)

            all_links = []
            for url in data["teacher_page_urls"]:
                all_links.extend(get_links(browser_pool[0], url, data["teacher_list_xpath"], timeout, max_retries, logger))

            # 读取之前的数据和上次更新时间
            prev_data_file = os.path.join(other_dir, f"{data['institute_name']}_prev.json")
            last_update_file = os.path.join(other_dir, f"{data['institute_name']}_last_update.json")
            if os.path.exists(prev_data_file):
                with open(prev_data_file, 'r', encoding='utf-8') as f:
                    prev_data = json.load(f)
            else:
                prev_data = {}
            
            if os.path.exists(last_update_file):
                with open(last_update_file, 'r', encoding='utf-8') as f:
                    last_update = json.load(f)
            else:
                last_update = {}

            teacher_info = []
            errors = []
            current_time = datetime.now().isoformat()

            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = []
                for i, link in enumerate(all_links):
                    # 检查上次更新时间，如果在24小时内更新过，则跳过
                    if link in last_update and datetime.fromisoformat(last_update[link]) > datetime.now() - timedelta(hours=24):
                        continue
                    
                    browser = browser_pool[i % num_threads]
                    future = executor.submit(scrape_teacher, (browser, link, data["teacher_name_xpath"], data["teacher_information_xpath"], timeout, max_retries, logger))
                    futures.append(future)

                with tqdm(total=len(futures), desc=f"Processing {data['institute_name']}", position=1, leave=False) as inner_pbar:
                    for future in as_completed(futures):
                        name, info, link, error = future.result()
                        if name and info:
                            current_hash = calculate_hash((name, info))
                            if link not in prev_data or prev_data[link] != current_hash:
                                teacher_info.append((name, info, link))
                                prev_data[link] = current_hash
                            last_update[link] = current_time
                        else:
                            errors.append((name if name else "Unknown", link, error))
                        time.sleep(1)  # 简单的限速机制
                        inner_pbar.update(1)

            # 保存当前数据的哈希值和更新时间
            with open(prev_data_file, 'w', encoding='utf-8') as f:
                json.dump(prev_data, f)
            with open(last_update_file, 'w', encoding='utf-8') as f:
                json.dump(last_update, f)

            save_to_excel(teacher_info, os.path.join(personnel_dir, f"{data['institute_name']}.xlsx"), logger)
            save_error_log(errors, os.path.join(other_dir, f"{data['institute_name']}_errors.xlsx"), logger)

            pbar.update(1)

# 主函数
def main(base_dir, university_name, timeout, max_retries, num_threads, log_level):
    logger = setup_logger(log_level)
    
    logger.info("Validating JSON config files...")
    invalid_configs = validate_json_configs(base_dir, university_name, logger)
    
    if invalid_configs:
        logger.error(f"Found {len(invalid_configs)} invalid config files:")
        for config in invalid_configs:
            logger.error(f"  - {config}")
        logger.error("Please fix these config files before proceeding.")
        return

    logger.info("All config files are valid. Starting scraping process...")
    
    # 创建浏览器池
    browser_pool = create_browser_pool(num_threads)
    
    try:
        scrape_university(base_dir, university_name, timeout, max_retries, num_threads, logger, browser_pool)
    finally:
        # 在所有任务完成后关闭浏览器池
        close_browser_pool(browser_pool)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape university website")
    parser.add_argument("base_dir", help="Base directory of the project")
    parser.add_argument("university_name", help="Name of the university to scrape")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout for requests in seconds")
    parser.add_argument("--max_retries", type=int, default=3, help="Maximum number of retries for failed requests")
    parser.add_argument("--num_threads", type=int, default=5, help="Number of threads to use")
    parser.add_argument("--log_level", default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    main(args.base_dir, args.university_name, args.timeout, args.max_retries, args.num_threads, args.log_level)