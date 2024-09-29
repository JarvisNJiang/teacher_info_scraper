import re

def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))