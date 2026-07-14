import os
import json
import requests

def main():
    # 1. 检测并读取抓取到的原始热点数据
    if not os.path.exists("raw_data.txt"):
        print("❌ 未找到 raw_data.txt，请检查上一步是否成功抓取。")
        return
        
    with open("raw_data.txt", "r", encoding="utf-8") as f:
        raw_content = f.read()

    # 2. 准备 AI 请求参数
    ai_url = "https://ark.cn-beijing.volces.com/api/plan/v3"  # 或者是硅基流动、OpenAI 的 API 地址
    headers = {
        "Authorization": f"Bearer {os.environ['AI_KEY']}", 
        "Content-Type": "application/json"
    }

    # 严格指令：命令 AI 过滤分类并仅输出标准的 JSON 数组，不带任何废话
    prompt = f"""
你是一个熟悉国内自媒体、抖音和小红书流量密码的【自媒体爆款导师】。
请阅读以下我为你抓取到的今日日本（JP）地区实时热点原始数据：
{raw_content}

核心任务：
1. 请从上述所有热点中，**严格筛选并只保留【科技/数码、日常生活/生活方式、娱乐/影视八卦】这三个领域**的内容。直接过滤掉政治、社会新闻、体育等不相干的内容。
2. 从过滤后的内容里，转化出 3 个最具备爆款潜力的“信息差”选题。

要求：你必须严格并且只输出一个合法的 JSON 数组，不要包含任何 Markdown 格式包装（比如不要加上 ```json 和结尾的 ```），不要有任何解释性前言或多余的话。

JSON 数组中的每个对象格式必须如下：
[
  {{
    "title": "爆款中文标题",
    "origin": "海外原帖视频简介/搜索热度解释（注明属于科技/生活/娱乐哪一类）",
    "outline": "详细说明国内切入角度，分步骤写下爆款脚本框架，并写3个情绪共鸣金句"
  }}
]
"""

    data = {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    print("1. 正在调遣大模型脑暴并筛选分类中...")
    response = requests.post(ai_url, json=data, headers=headers).json()
    
    if "choices" not in response:
        print("❌ AI 响应异常，请检查 API Key 或网络：", response)
        return
        
    ai_raw_text = response['choices'][0]['message']['content'].strip()

    # 清洗 AI 偶发产生的 Markdown 格式包装
    if ai_raw_text.startswith("```"):
        ai_raw_text = ai_raw_text.split("```")[1]
        if ai_raw_text.startswith("json"):
            ai_raw_text = ai_raw_text[4:]
    ai_raw_text = ai_raw_text.strip()

    try:
        topics = json.loads(ai_raw_text)
    except Exception as e:
        print(f"❌ 解析 AI 传回的 JSON 失败。AI 的原始内容为：\n{ai_raw_text}")
        print("错误信息：", e)
        return

    # 3. 申请飞书 Tenant Access Token
    print("2. 正在向飞书总部申请临时通行证 (Tenant Access Token)...")
    auth_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    auth_res = requests.post(auth_url, json={
        "app_id": os.environ["FEISHU_APP_ID"],
        "app_secret": os.environ["FEISHU_APP_SECRET"]
    }).json()
    
    if "tenant_access_token" not in auth_res:
        print("❌ 获取飞书 Token 失败，请检查 App ID 和 App Secret：", auth_res)
        return
        
    tenant_token = auth_res["tenant_access_token"]

    # 4. 批量写入飞书多维表格
    print("3. 正在将选题批量运往你的飞书多维表格...")
    feishu_headers = {
        "Authorization": f"Bearer {tenant_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    app_token = os.environ['FEISHU_APP_TOKEN']
    table_id = os.environ['FEISHU_TABLE_ID']
    add_record_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"

    records = []
    for topic in topics:
        records.append({
            "fields": {
                "选题标题": topic["title"],
                "海外原帖": topic["origin"],
                "爆款脚本大纲": topic["outline"]
            }
        })

    write_res = requests.post(add_record_url, json={"records": records}, headers=feishu_headers).json()
    if write_res.get("code") == 0:
        print("🎉 恭喜你！每日选题已成功输送到飞书多维表格！")
    else:
        print("⚠️ 飞书写入出错，请检查多维表格字段名是否完全一致：", write_res)

if __name__ == "__main__":
    main()
