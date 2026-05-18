<!-- GSD:docs-update -->
# 贡献指南

欢迎参与 Slide Skill 项目！Slide Skill 是一个 SVG 优先的 PowerPoint 技能包和 Python 工具集，旨在让 AI 智能体能够可靠地生成、修改和验证原生可编辑的 PPTX 演示文稿。项目采用 MIT 许可证，所有贡献均按相同许可证发布。

## 净室政策

**关键要求：禁止复制、引入或改写上游专有源码。**

本项目参考了 Anthropic 公开的 `skills/pptx` 包结构及其工作流，但绝不可将其专有源码复制到本仓库中。所有功能必须从需求出发、基于可观测的工作流独立重建。如果你在实现中对某段代码的来源有疑虑，请停止并先在 Issue 中讨论。

## 开发环境搭建

```bash
git clone https://github.com/<your-org>/slide-skill.git
cd slide-skill
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

确保所有测试通过后再开始开发。

## 代码风格

- Python 3.10+，使用现代语法（`match`、`|` 类型联合等）
- 优先使用类型注解，函数签名必须标注参数和返回类型
- 函数单一职责，缩进不超过 3 层
- 仅在意图不明显时添加简短注释，不加冗余注释
- 遵循项目现有模式和目录结构，不自创风格

## 贡献流程

1. Fork 本仓库
2. 从 `main` 创建功能分支：`git checkout -b feature/your-feature`
3. 编写代码和对应测试
4. 提交变更：使用简洁的提交信息，说明"为什么"而非"做了什么"
5. 推送分支并向 `main` 发起 Pull Request

## 测试要求

- 仓库现有 **144+** 项测试，全部必须通过
- 新增功能必须附带测试覆盖：正常路径、边界条件、错误处理
- 运行：`pytest`（或 `pytest tests/ -v` 查看详情）
- 不允许以"写了测试"作为完成标准——必须确保所有需求场景均有测试且通过

## Pull Request 规范

- 标题和正文清晰描述变更内容与动机
- 关联相关 Issue（如 `Closes #12`）
- 确保 CI 全部通过
- 如涉及净室合规审查，请在 PR 中说明实现依据
- 保持 PR 粒度适中，避免巨型合并

## 报告 Bug

通过 GitHub Issues 提交，请包含：

- 复现步骤
- 期望行为与实际行为
- Python 版本和操作系统
- 相关日志或截图

## 功能建议

通过 GitHub Issues 提交，请描述：

- 具体使用场景
- 期望的行为和输出
- 与现有功能的关联或区别

## 许可证

本项目采用 MIT 许可证。提交贡献即表示你同意该贡献以 MIT 许可证发布。
