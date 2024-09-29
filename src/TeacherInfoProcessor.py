import json
import os
from WebContentProcessor import WebContentProcessor
import pandas as pd
from tqdm import tqdm

class TeacherInfoProcessor:
    def __init__(self, use_selenium=False, headless=True, window_size=(800, 600)):
        self.web_processor = WebContentProcessor(use_selenium, headless, window_size)

    def process_teachers(self, json_folder='urls', output_folder='人员信息结果'):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_folder_path = os.path.join(current_dir, json_folder)
        output_folder_path = os.path.join(current_dir, output_folder)
        
        os.makedirs(output_folder_path, exist_ok=True)
        
        json_files = [f for f in os.listdir(json_folder_path) if f.endswith('.json')]
        
        with tqdm(total=len(json_files), desc="总进度", position=0) as pbar:
            for filename in json_files:
                file_path = os.path.join(json_folder_path, filename)
                results = []
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        teacher_data = json.load(file)
                    
                    with tqdm(total=len(teacher_data), desc=f"处理 {filename}", position=1, leave=False) as sub_pbar:
                        for teacher in teacher_data:
                            if teacher is None:
                                print(f"\n警告：在 {filename} 中发现无效的教师数据")
                                continue
                            
                            name = teacher.get('name', '')
                            url = teacher.get('url', '')
                            
                            if not url or url.strip() == "":
                                personal_info = '未提供个人主页链接'
                            else:
                                try:
                                    processed_result = self.web_processor.process(url)
                                    if processed_result is None:
                                        personal_info = '无法提取内容'
                                    elif isinstance(processed_result, str):
                                        personal_info = processed_result
                                    elif isinstance(processed_result, dict):
                                        personal_info = processed_result.get('content', '无法提取内容')
                                    else:
                                        personal_info = '处理结果格式错误'
                                except Exception as e:
                                    print(f"\n处理教师 {name} 的URL时发生错误：{e}")
                                    personal_info = '处理错误'
                            
                            results.append({'姓名': name, '个人简介': personal_info, 'URL': url})
                            sub_pbar.update(1)
                    
                    excel_filename = os.path.splitext(filename)[0] + '.xlsx'
                    output_path = os.path.join(output_folder_path, excel_filename)
                    self.save_results(pd.DataFrame(results), output_path)
                
                except Exception as e:
                    print(f"\n处理文件 {filename} 时发生错误：{e}")
                
                pbar.update(1)

        self.web_processor.close_driver()

    def save_results(self, results, output_file):
        if results is not None and not results.empty:
            results.to_excel(output_file, index=False)
            print(f"\n结果已保存到 {output_file}")
        else:
            print(f"\n没有结果可以保存到 {output_file}")

if __name__ == "__main__":
    processor = TeacherInfoProcessor(use_selenium=True, headless=True, window_size=(800, 600))
    processor.process_teachers()