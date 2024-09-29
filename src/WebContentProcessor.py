from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import logging
from content_preprocessor import preprocess_content, clean_content, extract_resume_content

class WebContentProcessor:
    def __init__(self, use_selenium=False, headless=True, window_size=(800, 600)):
        """
        初始化 WebContentProcessor 类
        
        :param use_selenium: 是否使用 Selenium 来获取网页内容
        :param headless: 是否使用无头模式（不显示浏览器界面）
        :param window_size: 设置浏览器窗口大小
        """
        self.use_selenium = use_selenium
        self.logger = logging.getLogger(__name__)  # 创建日志记录器
        
        # 设置 Chrome 浏览器选项
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument("--headless")  # 启用无头模式
        self.chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")  # 设置窗口大小
        
        self.driver = None  # 初始化 WebDriver 为 None

    def initialize_driver(self):
        """
        初始化 Selenium WebDriver
        只有在使用 Selenium 且驱动尚未初始化时才会创建新的驱动
        """
        if self.use_selenium and not self.driver:
            self.driver = webdriver.Chrome(options=self.chrome_options)

    def close_driver(self):
        """
        关闭 Selenium WebDriver
        在处理完所有任务后调用此方法以释放资源
        """
        if self.driver:
            self.driver.quit()
            self.driver = None

    def fetch_webpage(self, url):
        """
        获取网页内容
        
        :param url: 要获取的网页 URL
        :return: 网页的 HTML 内容，如果获取失败则返回 None
        """
        if self.use_selenium:
            # 使用 Selenium 获取网页内容
            self.initialize_driver()
            try:
                self.driver.get(url)
                # 等待页面主体加载完成
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                return self.driver.page_source
            except Exception as e:
                self.logger.error(f"Error fetching webpage with Selenium: {e}")
                return None
        else:
            # 使用 requests 库获取网页内容
            try:
                response = requests.get(url)
                response.raise_for_status()  # 如果请求失败，抛出异常
                return response.text
            except requests.RequestException as e:
                self.logger.error(f"Error fetching webpage with requests: {e}")
                return None

    def process(self, url):
        self.logger.debug(f"Processing URL: {url}")
        html = self.fetch_webpage(url)
        if html:
            try:
                self.logger.debug("Preprocessing content")
                preprocessed_content = preprocess_content(html)
                self.logger.debug("Cleaning content")
                cleaned_content = clean_content(preprocessed_content)
                self.logger.debug("Extracting resume content")
                resume_content = extract_resume_content(cleaned_content)
                
                # 将结果转换为适合表格的格式
                if isinstance(resume_content, list):
                    return "\n\n".join(resume_content)
                elif isinstance(resume_content, str):
                    return resume_content
                else:
                    self.logger.warning(f"Unexpected resume_content type: {type(resume_content)}")
                    return "无法提取有效内容"
            except Exception as e:
                self.logger.error(f"Error processing content: {e}", exc_info=True)
                return f"处理内容时发生错误: {str(e)}"
        else:
            self.logger.error("Failed to fetch webpage content")
            return "无法获取网页内容"