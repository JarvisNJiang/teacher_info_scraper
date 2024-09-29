import logging
from bs4 import BeautifulSoup, NavigableString
import re

logger = logging.getLogger(__name__)

def preprocess_content(html):
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # # 定义要删除的元素
        # elements_to_remove = ['script', 'style', 'iframe', 'noscript']
        
        # # 添加导航栏、侧边栏、页眉和页脚
        # elements_to_remove.extend(['nav', 'header', 'footer', 'aside'])
        
        # for element in soup(elements_to_remove):
        #     element.decompose()
        
        # # 定义可能包含无关内容的类名或ID
        # irrelevant_patterns = [
        #     re.compile(r'ad-?\w*', re.I),      # 广告相关
        #     re.compile(r'banner', re.I),       # 横幅广告
        #     re.compile(r'popup', re.I),        # 弹窗
        #     re.compile(r'cookie-?\w*', re.I),  # Cookie提示
        #     re.compile(r'nav(igation)?-?\w*', re.I),  # 导航
        #     re.compile(r'menu-?\w*', re.I),    # 菜单
        #     re.compile(r'sidebar-?\w*', re.I), # 侧边栏
        #     re.compile(r'header-?\w*', re.I),  # 页眉
        #     re.compile(r'footer-?\w*', re.I),  # 页脚
        # ]
        
        # def is_valid_element(element):
        #     return element is not None and not isinstance(element, NavigableString) and hasattr(element, 'name') and element.name is not None

        # elements_to_remove = []
        # for element in soup.find_all(True):
        #     if not is_valid_element(element):
        #         logger.warning(f"Encountered an invalid element while preprocessing: {element}")
        #         elements_to_remove.append(element)
        #         continue
            
        #     try:
        #         classes = element.get('class', [])
        #         if isinstance(classes, list):
        #             classes = ' '.join(classes)
        #         else:
        #             classes = str(classes)
        #         element_id = element.get('id', '')
        #         if any(pattern.search(classes) or pattern.search(element_id) for pattern in irrelevant_patterns):
        #             elements_to_remove.append(element)
        #     except AttributeError:
        #         logger.warning(f"Encountered an element without expected attributes: {element}")
        #         elements_to_remove.append(element)

        # for element in elements_to_remove:
        #     element.extract()

        return str(soup)
    except Exception as e:
        logger.error(f"Error in preprocess_content: {e}")
        return ""

def clean_content(content):
    # 移除HTML标签，但保留段落结构
    soup = BeautifulSoup(content, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    for p in soup.find_all('p'):
        p.append('\n\n')
    text = soup.get_text()
    
    # 清理文本
    text = re.sub(r'\s*\n\s*', '\n', text)  # 删除行首行尾的空白，但保留换行
    text = re.sub(r'\n{3,}', '\n\n', text)  # 将多个连续换行减少到最多两个
    
    # 保留更多的标点符号和特殊字符
    text = re.sub(r'[^\w\s.,;:!?()（）《》""''\-–—\u4e00-\u9fff]+', '', text)
    
    # 保护常见的简历格式
    text = re.sub(r'(^|\n)([^：\n]{2,10})(：|\:)', r'\1\2：', text)  # 确保冒号前后格式正确
    
    return text.strip()

def extract_resume_content(cleaned_content):
    if not cleaned_content:
        return "无有效内容"
    
    try:
        lines = cleaned_content.split('\n')
        content = []
        start_extracting = False

        # 定义可能标志简历开始的关键词
        start_keywords = ["姓名"]
        
        for line in lines:
            # 检查是否包含任何开始关键词
            if any(keyword in line for keyword in start_keywords):
                start_extracting = True
            
            if start_extracting:
                content.append(line)
                
        # 如果没有找到任何开始关键词，则返回所有内容
        if not start_extracting:
            return cleaned_content

        # 移除重复内容但保持原有的格式
        return remove_duplicates(content)
    except Exception as e:
        print(f"Error in extract_resume_content: {e}")
        return "提取内容时出错"

def remove_duplicates(elements):
    # 使用集合来去除重复元素，保持元素的原始顺序
    seen = set()
    return [x for x in elements if not (x in seen or seen.add(x))]