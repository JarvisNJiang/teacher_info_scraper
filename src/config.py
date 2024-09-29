import os

# 获取当前文件(config.py)所在的目录路径
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 定义 urls 文件夹的路径,它在项目根目录下
URLS_FOLDER = os.path.join(BASE_DIR, '..', 'urls')

# 定义输出文件夹的路径,它也在项目根目录下
OUTPUT_FOLDER = os.path.join(BASE_DIR, '..', '人员信息结果')

class Config:
    DEBUG = True
    # 在这里可以添加其他配置项,比如数据库URL,密钥等