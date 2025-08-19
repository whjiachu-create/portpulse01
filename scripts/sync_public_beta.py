#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sync PUBLIC_BETA.md -> GitHub
- Digest: 统计总进度，给“Public Beta 里程碑总览（燃尽 & 跟踪）”追加周报评论
- Optional: 将文档中形如 `### Checklist — <Issue标题>` 的清单块，同步为对应 Issue 的正文
依赖：仅 Python 标准库 + GitHub CLI (gh)
"""

import os, re, json, subprocess, tempfile, datetime, sys

def sh(cmd, env=None, check=True, capture=True):
    r = subprocess.run(cmd, shell=True, check=check, text=True,
                       stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.STDOUT, env=env or os.environ)
    return r.stdout.strip() if capture else ""

def detect_repo():
    url = sh("git remote get-url origin")
    # 支持 git@ 和 https:// 两种
    m = re.search(r"(?:github\.com[:/])([^/]+/[^/.]+)(?:\.git)?$", url)
    if not m:
        print("❌ 无法识别 GitHub 仓库（请确认已设置 origin）")
        sys.exit(1)
    return m.group(1)

REPO = detect_repo()
MILESTONE_TITLE = "Public Beta"
OVERVIEW_ISSUE_TITLE = "Public Beta 里程碑总览（燃尽 & 跟踪）"
GH = "gh"

def ensure_milestone(repo):
    # 拿里程碑编号
    out = sh(f'{GH} api -R "{repo}" repos/{{owner}}/{{repo}}/milestones')
    arr = json.loads(out)
    for x in arr:
        if x["title"] == MILESTONE_TITLE and x["state"] == "open":
            return x["number"]
    # 若不存在则创建
    desc = "对外可收费、稳定可演示的发布标准（详见 PUBLIC_BETA.md）"
    sh(f'{GH} milestone create "{MILESTONE_TITLE}" -R "{repo}" -d "{desc}"')
    out = sh(f'{GH} api -R "{repo}" repos/{{owner}}/{{repo}}/milestones')
    arr = json.loads(out)
    for x in arr:
        if x["title"] == MILESTONE_TITLE and x["state"] == "open":
            return x["number"]
    print("❌ 里程碑创建失败")
    sys.exit(1)

def find_issue_by_title(repo, title, state="open"):
    q = f'repo:{repo} is:issue in:title "{title}"'
    out = sh(f'{GH} api /search/issues -f q="{q}" -H "Accept: application/vnd.github+json"')
    data = json.loads(out)
    for item in data.get("items", []):
        if item["title"] == title and item["state"] == state:
            return item["number"]
    return None

def ensure_issue(repo, milestone_num, title, labels):
    num = find_issue_by_title(repo, title)
    if num:
        return num
    # 创建
    tmp = tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md")
    tmp.write(f"此 Issue 由同步器自动创建，对应 `PUBLIC_BETA.md` 中的任务：**{title}**。\n\n> 请以 `PUBLIC_BETA.md` 为准，正文由同步器覆盖。\n")
    tmp.close()
    label_flags = " ".join([f'-l "{l}"' for l in labels])
    sh(f'{GH} issue create -R "{repo}" -t "{title}" -F "{tmp.name}" -m {milestone_num} {label_flags}')
    num = find_issue_by_title(repo, title)
    return num

def update_issue_body(repo, number, body_md):
    tmp = tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md")
    tmp.write(body_md)
    tmp.close()
    sh(f'{GH} issue edit {number} -R "{repo}" -F "{tmp.name}"')

def comment_issue(repo, number, body_md):
    tmp = tempfile.NamedTemporaryFile("w+", delete=False, suffix=".md")
    tmp.write(body_md)
    tmp.close()
    sh(f'{GH} issue comment {number} -R "{repo}" -F "{tmp.name}"')

def read_public_beta_md():
    if not os.path.exists("PUBLIC_BETA.md"):
        print("❌ 未找到 PUBLIC_BETA.md（请先添加到仓库根目录）")
        sys.exit(1)
    with open("PUBLIC_BETA.md", "r", encoding="utf-8") as f:
        return f.read()

CHECKBOX_RE = re.compile(r"^- \[( |x|X)\]\s+", re.M)

def count_checkboxes(md):
    total = 0
    checked = 0
    for m in CHECKBOX_RE.finditer(md):
        total += 1
        if m.group(1).lower() == "x":
            checked += 1
    return checked, total

# “Checklist — <Issue标题>”块解析
SECTION_RE = re.compile(r"^###\s+Checklist\s+—\s+(.+?)\s*$", re.M)

def extract_checklist_blocks(md):
    """
    返回 { issue_title: "原样清单Markdown" }
    规则：从行 `### Checklist — <Issue标题>` 开始，
         直到下一个以 `## ` 或 `### ` 开头的标题（不含）为止。
    """
    blocks = {}
    for m in SECTION_RE.finditer(md):
        title = m.group(1).strip()
        start = m.end()
        # 找终点
        tail = md[start:]
        end_rel = len(tail)
        m2 = re.search(r"^\#{2,3}\s+", tail, re.M)
        if m2:
            end_rel = m2.start()
        chunk = tail[:end_rel].strip("\n")
        # 仅保留复选框行与说明文本
        blocks[title] = chunk.strip()
    return blocks

def main():
    repo = REPO
    milestone_num = ensure_milestone(repo)
    md = read_public_beta_md()

    # 1) 进度汇总 -> 概览 Issue 评论
    checked, total = count_checkboxes(md)
    pct = (checked / total * 100) if total else 0.0
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    digest = (
        f"**自动周报（{ts}）**\n\n"
        f"- 进度：**{checked} / {total}**（{pct:.1f}%）\n"
        f"- 文件：`PUBLIC_BETA.md`\n"
        f"- 说明：本评论由同步器生成；请以文档为单一事实源（SSOT）。\n"
    )

    overview_num = ensure_issue(repo, milestone_num, OVERVIEW_ISSUE_TITLE, ["stage:public-beta","type:task"])
    comment_issue(repo, overview_num, digest)
    print(f"✅ 周报已追加到 #{overview_num}")

    # 2) 精细同步：把“Checklist — <Issue标题>”块同步到对应 Issue 正文
    blocks = extract_checklist_blocks(md)
    for issue_title, chunk in blocks.items():
        num = ensure_issue(repo, milestone_num, issue_title, ["stage:public-beta","type:task"])
        body = (
            f"> 本文由同步器从 `PUBLIC_BETA.md` 的 **Checklist — {issue_title}** 区块自动生成（单一事实源）。\n\n"
            f"{chunk.strip()}\n"
        )
        update_issue_body(repo, num, body)
        print(f"🔁 已同步正文至 Issue #{num}  《{issue_title}》")

    print("🎉 同步完成")

if __name__ == "__main__":
    main()
