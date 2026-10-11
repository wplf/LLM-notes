#!/usr/bin/env python3
"""把笔记复制到 _docs/，并根据 README 的 Index 生成中文侧边栏导航（mkdocs.gen.yml）。

侧边栏顺序、分组、以及「标题 -> 文件」的映射全部来自 README：
- 二级标题（###）作为分组名，只取 " / " 前的中文部分；
- 列表项 `- [标题](路径.md)` 作为该分组下的导航项，显示标题即列表项标题。
README 里未登记的笔记会归入「其他」，不会从网站上漏掉。
"""
import json
import re
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
docs = root / "_docs"
shutil.rmtree(docs, ignore_errors=True)
docs.mkdir()

readme = (root / "README.md").read_text(encoding="utf-8")
# 网站首页用中文标题，其余内容保持与 README 一致
(docs / "index.md").write_text(readme.replace("\n## Index\n", "\n## 目录\n"), encoding="utf-8")

for d in root.iterdir():
    if d.is_dir() and not d.name.startswith((".", "_")) and d.name not in ("site", "scripts"):
        shutil.copytree(d, docs / d.name)

nav = [{"首页": "index.md"}]
section = None
listed = set()
for line in readme.splitlines():
    m = re.match(r"###\s+(.+)", line)
    if m:
        section = {m.group(1).split(" / ")[0].strip(): []}
        nav.append(section)
        continue
    m = re.match(r"\s*-\s*\[(.+?)\]\((.+?\.md)\)", line)
    if m and section is not None:
        list(section.values())[0].append({m.group(1): m.group(2)})
        listed.add(m.group(2))

others = [str(p.relative_to(docs)) for p in sorted(docs.rglob("*.md"))
          if p.name != "index.md" and str(p.relative_to(docs)) not in listed]
if others:
    nav.append({"其他": others})

(root / "mkdocs.gen.yml").write_text(
    "INHERIT: mkdocs.yml\nnav: " + json.dumps(nav, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8")
print("生成 mkdocs.gen.yml：%d 个分组，%d 篇笔记" % (len(nav) - 1, len(listed) + len(others)))
