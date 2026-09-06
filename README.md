# 长篇小说写作助手

基于GLM5.2/5.3的超长小说（100万字+）写作系统。

## 核心问题

AI模型上下文窗口有限，无法一次性处理整部小说（120万字/960章）。本系统通过**分层记忆**、**智能上下文装配**和**三级约束体系**解决这一问题。

## 系统架构

```
novel-writer/
├── main.py              # CLI入口
├── config.example.yaml  # 配置模板
├── core/                # 核心模块
│   ├── storage.py       # 每章一个文件夹的存储系统
│   ├── memory.py        # 富结构记忆（事件/时间线/人物/事实）
│   ├── context.py       # Token预算+滑动窗口上下文引擎
│   ├── llm.py           # GLM API封装+记忆提取
│   ├── constraints.py   # 三级约束体系（基础性/可演变/可偏离）
│   ├── foreshadowing.py # 伏笔管理（fsXXX编号+自动关联）
│   ├── chapter_connection.py  # 章节连接词
│   └── checker.py       # 一致性检查
├── templates/           # 模板文件
│   ├── 角色档案格式规范.txt
│   ├── 角色关系图模板.txt
│   ├── 说话风格卡模板.txt
│   ├── 能力体系模板.txt
│   ├── 物品系统设定模板.txt
│   ├── 地点档案模板.txt
│   ├── 时间线模板.txt
│   └── 细纲模板.txt
├── prompts/             # 提示词模板
└── data/{项目名}/       # 项目数据
```

## 核心功能

### 1. Token预算上下文引擎

- 默认128K上下文，支持扩展到1M
- Token分配：背景50% + 约束3% + 章节35% + 输出预留12%
- 滑动窗口：最近5章全文 + 前20章摘要
- 智能截断：硬切→软切→AI压缩，三级降级

### 2. 富结构记忆系统

- 每章提取：摘要/事件/时间线/人物变化/关系变化/事实/伏笔
- 全局索引：`event_log.jsonl` + `timeline.jsonl` + `character_graph.json` + `facts.jsonl`
- 去重机制：重新保存时先清除旧条目再重新提取

### 3. 三级约束体系

| 档 | 对应 | 说明 |
|---|------|------|
| Tier1 基础性 | 绝对不可偏离 | name/personality/constraints等 |
| Tier2 可演变 | 随剧情自然变化 | age/境界/关系/status等 |
| Tier3 可偏离 | 每章可调整 | 外貌描写/说话风格细节等 |

### 4. 伏笔管理系统

- 自动编号：`fs001`, `fs002`...
- 关联章节：引入章→推进章→回收章
- 支持待定状态（`?`）自动推进
- 超时预警：60章未推进自动提醒

### 5. 一致性检查

- 角色状态追踪（位置/能力/关系）
- 伏笔回收检查
- 时间线冲突检测
- 约束违规预警

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置API密钥
cp config.example.yaml config.yaml
# 编辑 config.yaml 填入 GLM API密钥

# 初始化项目
python main.py init --name "我的小说"

# 写第1章
python main.py write --chapter 1

# 审查第1章
python main.py review --chapter 1

# 编辑第1章
python main.py edit --chapter 1

# 查看项目状态
python main.py status
```

## 完整命令列表

| 命令 | 说明 |
|------|------|
| `init` | 初始化新项目 |
| `write` | 写章节（自动加载上下文+提取记忆） |
| `edit` | 编辑章节（终端或系统编辑器） |
| `save` | 重新提取记忆（去重后覆盖） |
| `review` | 审查章节（格式+风格+伏笔） |
| `status` | 项目状态+Token预算报告 |
| `chapters` | 列出所有章节 |
| `characters` | 列出角色 |
| `events` | 列出事件 |
| `timeline` | 列出时间线 |
| `query` | 全文检索 |
| `constraints` | 查看/管理约束 |
| `constraints-sync` | 从章节同步约束 |
| `constraints-add` | 手动添加约束 |
| `constraints-check` | 检查约束违规 |

## 项目数据结构

```
data/{项目名}/
├── outline/               # 大纲
│   ├── 全书大纲.txt       # 十卷结构
│   └── 卷01_细纲.txt      # 卷级细纲
├── characters/            # 角色
│   └── 角色档案.txt       # 全部角色（按格式规范填写）
├── world/                 # 世界观
│   ├── 故事圣经.txt       # 世界规则
│   ├── 伏笔.txt           # 伏笔登记
│   ├── 人物关系图.txt
│   ├── 说话风格卡.txt
│   ├── 能力体系.txt
│   ├── 物品系统设定.txt
│   ├── 地点档案.txt
│   └── 时间线.txt
├── chapters/              # 章节（每章一个文件夹）
│   ├── ch0001_水上乐园/
│   │   ├── draft.txt
│   │   ├── final.txt
│   │   ├── metadata.json
│   │   ├── memory.json
│   │   └── backups/
│   └── ...
├── memory/                # 记忆数据
│   ├── event_log.jsonl    # 全局事件索引
│   ├── timeline.jsonl     # 全局时间线
│   ├── character_graph.json  # 人物关系图
│   ├── facts/facts.jsonl  # 事实表
│   └── summaries/chNNNN.txt  # 章节摘要
├── foreshadowing.json     # 伏笔状态
└── project_stats.json     # 项目统计
```

## 使用流程

1. **初始化**：`python main.py init --name "小说名"`
2. **填写设定**：按模板格式填写角色/世界观/大纲
3. **写章节**：`python main.py write --chapter N`（系统自动加载上下文）
4. **审查**：`python main.py review --chapter N`
5. **编辑**：`python main.py edit --chapter N`（修改后自动备份）
6. **保存**：`python main.py save --chapter N`（重新提取记忆，去重）
7. **继续写**：系统自动加载最近5章全文+前20章摘要+约束+伏笔

## 设计原则

1. **Token预算优先**：所有上下文都经过Token计算，绝不超窗
2. **三级约束**：基础性不可变 / 可演变随剧情更新 / 可偏离每章覆盖
3. **富结构记忆**：不只是摘要，还有事件/时间线/人物/关系/事实
4. **每章独立文件夹**：draft/final/metadata/memory/backups
5. **去重机制**：重新保存时先清除旧条目再重新提取

## License

MIT
