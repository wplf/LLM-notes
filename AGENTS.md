# AGENTS.md

本仓库用于记录 LLM 与计算机相关的知识笔记。Agent 在此仓库工作时遵循以下约定。

## 添加新知识笔记的流程

当用户要求“将结论写到 LLM-notes”时：

1. **新建主题文件夹**：在仓库根目录下为该主题新建一个文件夹（英文小写、短横线分隔，如 `chip-interconnect/`）。
2. **写 Markdown 笔记**：在文件夹中创建 `.md` 文件（如 `chip-interconnect/chip-interconnect-overview.md`），内容使用中文，结构清晰：
   - 分类小节 + 优缺点列表
   - 汇总对比表（如适用）
   - 结论 / 趋势
   - 对估算数值加注说明
3. **更新 README 索引**：在 `README.md` 的 `## Index` 下，按领域分类（如 `### 硬件 / Hardware`）添加一条相对链接，并附一句话简介：
   ```markdown
   - [笔记标题](folder/file.md) — 一句话简介
   ```
   若无合适分类则新建一个分类小节。
4. **提交并推送**：
   ```bash
   git add -A
   git commit -m "Add <topic> note and README index"
   git push
   ```

## 现有笔记

- [芯片间互联技术概览](chip-interconnect/chip-interconnect-overview.md) — 3D 堆叠、2.5D/Chiplet、铜 SerDes、无线耦合、晶圆级集成与光互连的优缺点对比；结论：封装内用 2.5D/3D，机柜内用铜，机柜间及更远用光。
