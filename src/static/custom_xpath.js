document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('customXpathForm');
    const progressDiv = document.getElementById('progress');
    const resultTable = document.getElementById('resultTable');

    function displayTeachersInfo(teachersInfo) {
        // 清空现有的表格内容，保留表头
        const tbody = resultTable.querySelector('tbody');
        tbody.innerHTML = '';

        // 添加新的教师信息
        teachersInfo.forEach(teacher => {
            const row = tbody.insertRow();
            const nameCell = row.insertCell(0);
            const urlCell = row.insertCell(1);
            
            nameCell.textContent = teacher.name;
            
            if (teacher.url) {
                const link = document.createElement('a');
                link.href = teacher.url;
                link.textContent = teacher.url;
                link.target = '_blank';
                urlCell.appendChild(link);
            } else {
                urlCell.textContent = '无链接';
            }
        });

        // 显示表格
        resultTable.style.display = 'table';
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault(); // 阻止表单的默认提交行为

        const url = document.getElementById('url').value;
        const instituteName = document.getElementById('instituteName').value;
        const xpath = document.getElementById('xpath').value;
        const enablePagination = document.getElementById('enablePagination').checked;

        // 添加一些基本的验证
        if (!url || !instituteName || !xpath) {
            alert('请填写所有字段');
            return;
        }

        // 重置进度和结果显示
        progressDiv.textContent = '正在提取...';
        resultTable.style.display = 'none';

        fetch('/extract_custom', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                instituteName: instituteName,
                xpath: xpath,
                enablePagination: enablePagination
            }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
    
            function readStream() {
                return reader.read().then(({ done, value }) => {
                    if (done) {
                        console.log("Stream complete");
                        return;
                    }
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');
                    lines.forEach(line => {
                        if (line.startsWith('data:')) {
                            try {
                                const data = JSON.parse(line.slice(5));
                                if (data.progress) {
                                    progressDiv.textContent = data.progress;
                                    if (data.teachers_count) {
                                        progressDiv.textContent += ` - 已提取 ${data.teachers_count} 位教师信息`;
                                    }
                                } else if (data.teachers_info) {
                                    displayTeachersInfo(data.teachers_info);
                                    progressDiv.textContent = '提取完成';
                                    if (data.json_file) {
                                        progressDiv.textContent += ` - JSON文件已生成: ${data.json_file}`;
                                    }
                                } else if (data.error) {
                                    progressDiv.textContent = `错误: ${data.error}`;
                                }
                            } catch (e) {
                                console.error("Error parsing JSON:", e);
                                progressDiv.textContent = `解析错误: ${e.message}`;
                            }
                        }
                    });
                    return readStream();
                });
            }
    
            return readStream();
        })
        .catch(error => {
            console.error('Error:', error);
            progressDiv.textContent = '发生错误: ' + error.message;
        });
    });
});