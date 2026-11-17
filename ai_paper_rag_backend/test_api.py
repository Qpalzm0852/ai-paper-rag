import requests
import json

# 你的 Django 接口地址
url = "http://127.0.0.1:8000/api/ask/"

# 模拟 Vue 前端发给后端的数据
payload = {
    "question": "这篇论文介绍的核心模型叫什么名字？它有什么突破？"
}

headers = {
    "Content-Type": "application/json"
}

print("🚀 正在向 Django 后端发送问题...")

# 发送 POST 请求
response = requests.post(url, data=json.dumps(payload), headers=headers)

# 打印后端返回的 JSON 结果
print("\n✅ 后端返回结果：")
print(json.dumps(response.json(), indent=4, ensure_ascii=False))