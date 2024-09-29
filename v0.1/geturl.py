import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

def extract_links(html_content, base_url):
    """提取页面中的所有链接，包括按钮和下拉菜单中的链接"""
    soup = BeautifulSoup(html_content, 'html.parser')
    links = set()

    # 提取所有 <a> 标签的 href
    for a in soup.find_all('a', href=True):
        links.add(urljoin(base_url, a['href']))

    # 提取所有 <button> 标签的 onclick 属性中的 URL
    for button in soup.find_all('button'):
        onclick = button.get('onclick', '')
        if 'location.href' in onclick or 'window.location' in onclick:
            url = re.search(r"'(.*?)'", onclick)
            if url:
                links.add(urljoin(base_url, url.group(1)))

    # 提取所有 <select> 和 <option> 标签中的 URL
    for select in soup.find_all('select'):
        for option in select.find_all('option', value=True):
            if option['value'].startswith(('http', '/')):
                links.add(urljoin(base_url, option['value']))

    # 提取 JavaScript 中的 URL（简单情况）
    scripts = soup.find_all('script')
    for script in scripts:
        urls = re.findall(r'(https?://\S+)"', script.string if script.string else '')
        for url in urls:
            links.add(url)

    # 提取 data-href 属性
    for element in soup.find_all(attrs={"data-href": True}):
        links.add(urljoin(base_url, element['data-href']))

    return list(links)

def is_valid_url(url, base_url, depth, max_depth=3):
    base_domain = urlparse(base_url).netloc.split('.')[-2:]  # 获取主域名
    url_domain = urlparse(url).netloc.split('.')[-2:]
    
    # 检查深度
    if depth > max_depth:
        return False
    
    # 检查域名
    return base_domain == url_domain or (len(url_domain) > 2 and url_domain[-2:] == base_domain)

def is_teacher_list_page(html_content):
    """判断页面是否可能包含教师列表"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 定义与教师相关的关键词
    teacher_keywords = ['姓名', '电话', '师资', '教授', '副教授', '讲师', 'faculty', 'professor', 'teacher', 'instructor', 'staff']
    
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        if rows:
            columns = rows[0].find_all(['th', 'td'])
            if len(columns) > 3:
                # 检查表格内容是否包含教师相关关键词
                table_text = table.get_text().lower()
                if any(keyword.lower() in table_text for keyword in teacher_keywords):
                    return True
    
    return False

def crawl(start_url, max_pages=1000, max_depth=3):
    visited = set()
    queue = [(start_url, 0)]  # 元组 (URL, 深度)
    teacher_list_pages = []

    while queue and len(visited) < max_pages:
        url, depth = queue.pop(0)
        if url in visited:
            continue

        try:
            response = requests.get(url, timeout=10)
            visited.add(url)

            if is_teacher_list_page(response.text):
                teacher_list_pages.append(url)
                print(f"Found potential teacher list page: {url}")

            for link in extract_links(response.text, url):
                if link not in visited and is_valid_url(link, start_url, depth + 1, max_depth):
                    queue.append((link, depth + 1))

        except Exception as e:
            print(f"Error crawling {url}: {str(e)}")

    return teacher_list_pages

# 使用示例
if __name__ == "__main__":
    start_url = "https://scms.ustc.edu.cn/2390/list.htm"  # 替换为目标大学的网址
    teacher_pages = crawl(start_url, max_pages=500, max_depth=3)
    
    print("\nPotential teacher list pages found:")
    for page in teacher_pages:
        print(page)