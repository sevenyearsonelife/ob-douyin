#!/usr/bin/env python3
"""抖音视频文案提取脚本
读取 抖音视频链接.md，对比 提取记录.md，对新链接调用 transcribe.py 提取文案，
以视频标题命名写入新 md 文件。
用法: python3 extract.py
"""

import re
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
LINKS_FILE = SCRIPT_DIR / "00抖音视频链接.md"
RECORD_FILE = SCRIPT_DIR / "01提取记录.md"
TRANSCRIBE_SCRIPT = Path.home() / ".claude/skills/douyin-transcript/scripts/transcribe.py"

DOUYIN_LINK_RE = re.compile(r'https://v\.douyin\.com/[\w\-/]+')


def extract_links(text: str) -> list[str]:
    """从文本中提取抖音视频链接（去重，保持顺序）"""
    links = DOUYIN_LINK_RE.findall(text)
    seen = set()
    return [l for l in links if not (l in seen or seen.add(l))]


def read_processed_links() -> set[str]:
    """读取已提取记录，返回已处理的链接集合"""
    if not RECORD_FILE.exists():
        return set()
    text = RECORD_FILE.read_text(encoding='utf-8')
    return set(DOUYIN_LINK_RE.findall(text))


def sanitize_filename(title: str, max_len: int = 60) -> str:
    """将视频标题清理为合法文件名"""
    title = re.sub(r'[\\/:*?"<>|#\n\r\t]', '', title)
    title = title.strip().strip('.')
    if len(title) > max_len:
        title = title[:max_len].rstrip('。，,. ')
    return title if title else "未命名视频"


# 分段由大模型（Claude）基于语义完成，脚本不做关键词规则分段

def transcribe(url: str) -> dict:
    """调用 transcribe.py --json 获取转写结果"""
    result = subprocess.run(
        [sys.executable, str(TRANSCRIBE_SCRIPT), url, '--json'],
        capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"转写失败 (exit {result.returncode}): {result.stderr.strip()}")

    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        raise RuntimeError(f"无法解析 JSON 输出: {result.stdout[:500]}")


def append_record(url: str, filename: str):
    """追加一条提取记录，文件名用 markdown 超链接"""
    from urllib.parse import quote
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    encoded = quote(filename, safe='')
    with open(RECORD_FILE, 'a', encoding='utf-8') as f:
        f.write(f"| {url} | [{filename}]({encoded}) | {timestamp} |\n")


def ensure_record_header():
    """确保记录文件有表头"""
    if not RECORD_FILE.exists():
        with open(RECORD_FILE, 'w', encoding='utf-8') as f:
            f.write("| 视频链接 | 文件名 | 提取时间 |\n")
            f.write("|---|---|---|\n")


def main():
    if not LINKS_FILE.exists():
        print(f"链接文件不存在: {LINKS_FILE}")
        return 1

    text = LINKS_FILE.read_text(encoding='utf-8')
    all_links = extract_links(text)

    if not all_links:
        print("未找到任何抖音视频链接")
        return 0

    print(f"链接文件中共 {len(all_links)} 条链接")

    processed = read_processed_links()
    new_links = [l for l in all_links if l not in processed]

    if not new_links:
        print("所有链接均已提取，无须处理")
        return 0

    print(f"其中 {len(new_links)} 条未提取，开始处理...\n")

    ensure_record_header()

    success = 0
    for i, url in enumerate(new_links, 1):
        print(f"[{i}/{len(new_links)}] {url}")
        try:
            data = transcribe(url)
            title = data.get('title', '未命名视频')
            text_content = data.get('text', '')

            filename = sanitize_filename(title) + '.md'
            filepath = SCRIPT_DIR / filename
            filepath.write_text(f"视频链接：{url}\n\n{text_content}", encoding='utf-8')

            append_record(url, filename)
            print(f"  ✅ {filename}")
            success += 1
        except Exception as e:
            print(f"  ❌ 失败: {e}")

    print(f"\n完成: {success}/{len(new_links)} 条提取成功")
    return 0 if success == len(new_links) else 1


if __name__ == '__main__':
    sys.exit(main())
