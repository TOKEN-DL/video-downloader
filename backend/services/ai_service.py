import json
import logging
from openai import OpenAI
import config
from services.ai_prompts import SUMMARIZE_SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, MINDMAP_PROMPT

logger = logging.getLogger("ai_service")

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )
    return _client


def summarize(transcript: str, title: str) -> dict:
    """调用 DeepSeek 生成结构化总结。返回 {summary, highlights, terms, qa}。"""
    client = _get_client()
    user_content = f"视频标题：{title}\n\n字幕内容：\n{transcript}"

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    raw = response.choices[0].message.content.strip()
    return _parse_json_response(raw)


def chat(transcript: str, messages: list[dict]) -> str:
    """带视频上下文的 AI 对话。"""
    client = _get_client()
    system_msg = CHAT_SYSTEM_PROMPT + f"\n\n视频字幕内容：\n{transcript[:8000]}"

    api_messages = [{"role": "system", "content": system_msg}]
    for m in messages:
        if m.get("role") in ("user", "assistant"):
            api_messages.append({"role": m["role"], "content": m["content"]})

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=api_messages,
        temperature=0.5,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()


def generate_mindmap_markdown(summary: dict, title: str) -> str:
    """根据总结结果生成 markmap 兼容的 Markdown 大纲。"""
    client = _get_client()
    summary_text = json.dumps(summary, ensure_ascii=False, indent=2)
    user_content = f"视频标题：{title}\n\n总结内容：\n{summary_text}"

    response = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": MINDMAP_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()


def _parse_json_response(raw: str) -> dict:
    """解析 AI 返回的 JSON，处理 markdown 代码块包裹的情况。"""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError(f"AI 返回非 JSON 内容: {text[:200]}")
