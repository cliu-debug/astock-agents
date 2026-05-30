# 贡献指南

感谢你对 AStockAgents 项目的兴趣！我们欢迎任何形式的贡献，包括但不限于：

- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 完善文档
- 💻 提交代码改进
- 🌍 翻译文档
- ⭐ Star 支持

请花几分钟阅读本指南，以确保你的贡献过程顺利高效。

---

## 目录

1. [行为准则](#行为准则)
2. [如何贡献](#如何贡献)
3. [开发环境设置](#开发环境设置)
4. [代码规范](#代码规范)
5. [提交 Pull Request](#提交-pull-request)
6. [项目结构](#项目结构)
7. [问题反馈](#问题反馈)

---

## 行为准则

我们希望所有参与者都能保持友好和尊重。请阅读并遵守以下准则：

- 使用包容性语言
- 尊重不同的观点和经验
- 优雅地接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表现出同理心

任何违反行为准则的行为都将被严肃处理。

---

## 如何贡献

### 报告 Bug

如果你发现了 Bug，请使用 GitHub Issues 报告：

1. 搜索是否已经存在相同的 Bug 报告
2. 如果没有，请创建新的 Issue
3. 使用 `bug_report.md` 模板，提供以下信息：
   - 清晰的 Bug 描述
   - 复现步骤
   - 预期行为 vs 实际行为
   - 环境信息（操作系统、Python 版本等）
   - 可能的解决方案

### 提出新功能

我们欢迎新功能的建议！请：

1. 搜索是否已有类似的功能请求
2. 如果没有，使用 `feature_request.md` 模板创建 Issue
3. 详细描述功能需求和使用场景

### 提交代码

#### 1. Fork 项目

点击页面右上角的 "Fork" 按钮，创建你的个人分支。

#### 2. 克隆项目

```bash
git clone https://github.com/astock-agents/astock-agents.git
cd astock-agents
```

#### 3. 创建分支

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/bug-description
```

#### 4. 进行开发

确保你的代码：
- 遵循本项目的代码规范
- 包含适当的测试
- 更新相关文档（如果需要）

#### 5. 提交更改

```bash
git add .
git commit -m 'feat: Add new feature'
# 或
git commit -m 'fix: Fix bug description'
```

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

类型 (type)：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `perf`: 性能优化
- `test`: 测试相关
- `chore`: 构建或辅助工具变动

#### 6. 推送更改

```bash
git push origin feature/your-feature-name
```

#### 7. 创建 Pull Request

1. 访问原始仓库
2. 点击 "New Pull Request"
3. 选择你的分支并填写 PR 模板
4. 提交 PR

---

## 开发环境设置

### 前置要求

- Python 3.10+
- Node.js 18+
- Git

### Python 环境

```bash
# 克隆项目
git clone https://github.com/yourusername/astock-agents.git
cd astock-agents

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 安装项目
pip install -e .
```

### 前端开发环境

```bash
cd frontend
npm install
npm run dev
```

### 运行测试

```bash
# Python 测试
pytest

# 前端测试
cd frontend
npm test
```

---

## 代码规范

### Python

- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/) 规范
- 使用 [Black](https://github.com/psf/black) 格式化代码
- 使用 [isort](https://github.com/PyCQA/isort) 排序导入
- 使用 [Pylint](https://www.pylint.org/) 检查代码
- 类型提示：使用类型注解，避免使用 `Any`
- 命名：
  - 变量/函数：`snake_case`
  - 类名：`PascalCase`
  - 常量：`UPPER_SNAKE_CASE`

### JavaScript/TypeScript

- 遵循 ESLint 规则
- 使用 Prettier 格式化
- 使用有意义的变量名
- 组件采用 Vue 3 Composition API

### Git 提交信息

- 使用英文或中文编写提交信息
- 保持简洁明了
- 第一行不超过 50 个字符
- 详细说明放在正文

---

## 提交 Pull Request

### PR 标题格式

```
<type>(<scope>): <description>
```

示例：
- `feat(agents): Add new technical indicator`
- `fix(data): Fix data fetching timeout issue`
- `docs: Update README with new installation steps`

### PR 描述模板

请包含以下内容：

1. **关联 Issue**：使用 `Closes #123` 或 `Fixes #456`
2. **变更内容**：描述你做了什么
3. **测试结果**：说明测试情况
4. **截图**：如果是 UI 变更，请提供截图

### 代码审查清单

在提交 PR 前，请确保：

- [ ] 代码遵循项目规范
- [ ] 新功能包含测试
- [ ] Bug 修复包含回归测试
- [ ] 文档已更新（如需要）
- [ ] 所有测试通过

---

## 项目结构

```
astock-agents/
├── astock_agents/          # 主包
│   ├── agents/             # 智能体模块
│   ├── data/               # 数据模块
│   ├── models/             # 数据模型
│   ├── services/           # 服务层
│   ├── workflow/           # 工作流
│   ├── web/                # Web界面
│   └── utils/              # 工具函数
├── frontend/               # Vue 3 前端
├── tests/                  # 测试文件
├── docs/                   # 详细文档
├── examples/               # 示例代码
├── CHANGELOG.md           # 版本更新日志
└── README.md               # 项目说明
```

---

## 问题反馈

如果你有任何问题，可以通过以下方式获取帮助：

1. **GitHub Issues**：用于报告 Bug 和功能请求
2. **讨论区**：用于一般性讨论和问答

请注意：此项目仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。

---

## 致谢

感谢所有为 AStockAgents 做出贡献的开发者！

[![Contributors](https://contrib.rocks/image?repo=astock-agents/astock-agents)](https://github.com/astock-agents/astock-agents/graphs/contributors)
