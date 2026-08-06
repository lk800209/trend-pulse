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

    # 2. 准备 Gemini API 请求参数
    api_key = os.environ.get('AI_KEY') or os.environ.get('AI_API_KEY')
    
    if not api_key:
        print("❌ 未检测到 AI 密钥！请检查 GitHub Workflows 中的环境变量配置。")
        return

    base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    ai_url = f"{base_url}?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }

    # 重构 Prompt：严格要求 3个国家 * 4个板块 * 3条选题 = 36条选题
    # 精简了大纲格式，确保这 36 条能在一轮请求里全部吐出来，绝不截断
    prompt = f"""
You are a top-tier social media content strategist who is expert at creating viral videos on Chinese platforms like Xiaohongshu and Douyin.
Please analyze the following multi-regional real-time trending raw data:
{raw_content}

Your Core Tasks:
You must extract and transform exactly 36 high-potential viral video topics customized for the Chinese audience.
The topics must follow a strict matrix of 3 regions (US, JP, KR) x 4 categories (Tech, AI, Lifestyle, Entertainment).
For EACH region (US, JP, KR) and EACH category (Tech, AI, Lifestyle, Entertainment), you must generate exactly 3 topics (3 * 4 * 3 = 36 topics in total).

Strict Output Requirements:
1. You must output ONLY a valid JSON array.
2. Do NOT wrap your response in markdown blocks (strictly no ```json and no trailing ```).
3. Do NOT include any conversational preface, introduction, or explanation.
4. All values for "title", "origin", and "outline" MUST be written in natural, engaging Simplified Chinese.
5. The "region" value MUST be: "美国", "日本", or "韩国".
6. The "category" value MUST be: "科技", "AI", "生活", or "娱乐".

The JSON array structure must strictly match this template (ensure all 36 objects are generated):
[
  {{
    "region": "美国",
    "category": "科技",
    "title": "爆款中文标题",
    "original_title": "海外原标题的中文直译",
    "origin": "海外原帖简短热度来源",
    "url": "从原始数据中提取的原文URL链接（若无则留空\"\"）",
    "outline": "视频结构：1.钩子痛点 2.核心干货 3.转化结语。包含2句引发情绪共鸣的金句。"
  }}
]
"""

    # 适配 Gemini 官方的 JSON 请求格式
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.4, 
            "responseMimeType": "application/json"
        }
    }

    print("1. 正在调遣 Gemini (36 选大阵) 脑暴并分类筛选中...")
    
    res = requests.post(ai_url, json=data, headers=headers)
    
    if res.status_code != 200:
        print(f"❌ Gemini 服务器返回错误！状态码: {res.status_code}")
        print(f"返回的内容为:\n{res.text}")
        return

    try:
        response = res.json()
    except Exception:
        print("❌ 无法解析 Gemini 返回的数据为 JSON 格式！")
        print(f"返回的原始文本是:\n{res.text}")
        return
    
    try:
        ai_raw_text = response['candidates'][0]['content']['parts'][0]['text'].strip()
    except KeyError:
        print("❌ Gemini 返回的结构异常，可能是触发了内容安全安全审查：", response)
        return

    # 防御性清洗
    if ai_raw_text.startswith("```"):
        ai_raw_text = ai_raw_text.split("```")[1]
        if ai_raw_text.startswith("json"):
            ai_raw_text = ai_raw_text[4:]
    ai_raw_text = ai_raw_text.strip()

    try:
        topics = json.loads(ai_raw_text)
    except Exception as e:
        print(f"❌ 解析 Gemini 传回的 JSON 失败。原始文本为：\n{ai_raw_text}")
        print(f"错误信息: {e}")
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
    print(f"3. 正在将 {len(topics)} 条选题批量运往你的飞书多维表格...")
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
                "国家/地区": topic.get("region", "未知"),
                "选题分类": topic.get("category", "未分类"),
                "选题标题": topic.get("title", ""),
                "原题直译": topic.get("original_title", ""),
                "海外原帖": topic.get("origin", ""),
                "原文URL": topic.get("url", ""),
                "爆款脚本大纲": topic.get("outline", "")
            }
        })

    write_res = requests.post(add_record_url, json={"records": records}, headers=feishu_headers).json()
    if write_res.get("code") == 0:
        print(f"🎉 恭喜你！每日共 {len(topics)} 条矩阵选题（中英双语优化版）已成功输送到飞书多维表格！")
    else:
        print("⚠️ 飞书写入出错，请检查多维表格字段名是否完全一致：", write_res)

if __name__ == "__main__":
    main()
