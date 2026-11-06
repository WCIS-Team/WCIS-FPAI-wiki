---
tags: [SOP]
---

# Discovery：目标驱动的现成 Agent skill / SOP 检索、复用与整理

## 1. 任务目标

用户提供一个具体目标。你需要先检索是否已有其他人实现了能够完成该目标的脚本、 SOP、Agent Skill、Runbook、Playbook、自动化工作流或工具、标准。

优先复用已有成果，不要一开始就自行设计。

同时利用固定的技能聚合库、SOP 框架和工作流目录发现候选方案。找到候选后，必须继续验证实际内容，不能仅凭目录中的介绍作出判断。

## 2. 固定检索入口

以下入口是每次检索时优先检查的候选来源。根据用户目标选择相关入口，不要求每个目标都逐一检查所有网站。

**检索原则：**

1. 优先搜索与目标直接相关的现成 Skill、SOP、脚本、工具和完整工作流，而不是只搜索介绍性文章。
    
2. 聚合库用于发现候选项目；具体项目的上游仓库、官方文档和实际实现才是判断可复用性的主要依据。
    
3. 区分通用 Skill、领域专用 SOP、自动化框架、评测基准和规范文档，不将它们视为同一种资源。
    
4. 固定入口不是搜索范围的边界。若现有入口不能找到合适实现，应主动搜索相关领域的专用工具、官方 Cookbook、插件市场、开源项目、论文及社区索引。
    
5. 记录候选项目的实际来源、适用范围、执行方式、依赖条件、许可证、维护状态及验证证据。不得仅凭项目名称、简介或 Star 数判定其适用性。
    

### 2.1 Agent Skills 与 SOP 聚合库

| 资源                             | 主要用途                          | 地址                                                                                                     |
| ------------------------------ | ----------------------------- | ------------------------------------------------------------------------------------------------------ |
| VoltAgent/awesome-agent-skills | 跨领域 Agent Skills 聚合，发现官方及社区技能 | [https://github.com/VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) |
| heilcheng/awesome-agent-skills | 查找 Agent Skills 目录、教程及相关指南    | [https://github.com/heilcheng/awesome-agent-skills](https://github.com/heilcheng/awesome-agent-skills) |

### 2.2 官方 Skill 规范与实际 Skill 实现

|资源|主要用途|地址|
|---|---|---|
|agentskills/agentskills|Agent Skills 开放规范、格式与使用文档|[https://github.com/agentskills/agentskills](https://github.com/agentskills/agentskills)|
|anthropics/skills|官方公开 Skills 示例及可复用技能实现|[https://github.com/anthropics/skills](https://github.com/anthropics/skills)|
|google-labs-code/stitch-skills|面向 Stitch MCP Server 的专用技能集合，参考其 Skill 组织方式及配套资源|[https://github.com/google-labs-code/stitch-skills](https://github.com/google-labs-code/stitch-skills)|
|mattpocock/skills|软件工程实践类 Skills，参考具体任务的执行方法与工程约束|[https://github.com/mattpocock/skills](https://github.com/mattpocock/skills)|
|obra/superpowers|Agent Skills 框架与软件开发方法论，参考分阶段执行、规划、测试及验证机制|[https://github.com/obra/superpowers](https://github.com/obra/superpowers)|

**使用说明：** 本节同时提供规范和实例。规范用于检查 Skill 的结构与兼容性；实际 Skill 仓库用于寻找可复用的任务实现。Stitch Skills 等专用技能集合仅在目标相关时重点检查。

### 2.3 SOP 编写、管理与工作流框架

|资源|主要用途|地址|
|---|---|---|
|Strands Agent SOP|自然语言工作流与多步骤 Agent 任务的组织|[https://github.com/strands-agents/agent-sop](https://github.com/strands-agents/agent-sop)|
|AgentPlaybooks|查找 Agent 配置、技能与工作流的组织管理方案|[https://agentplaybooks.ai/docs](https://agentplaybooks.ai/docs)|
|Microsoft AI Agent Runbooks|查找企业级 Agent 实施手册与技术模式|[https://github.com/microsoft/ai-agent-runbooks](https://github.com/microsoft/ai-agent-runbooks)|

**使用说明：** 本节侧重工作流如何组织、表达和执行，不意味着其中每个项目都包含可直接复用的目标领域 SOP。检索时应进入项目检查实际提供的文档、模板、代码和执行能力。

### 2.4 框架与自动化工作流

|资源|主要用途|地址|
|---|---|---|
|MLCommons Inference|标准化推理评测、基准测试与参考实现|[https://github.com/mlcommons/inference](https://github.com/mlcommons/inference)|
|MLCommons Collective Knowledge / Collective Mind|实验、Benchmark 与可复现工作流的自动化基础设施|[https://docs.mlcommons.org/ck/](https://docs.mlcommons.org/ck/)|

**使用说明：** 本节用于查找可执行框架、标准化实验流程和参考实现。它们不是通用 SOP 库；只有当用户目标涉及模型评测、实验自动化或相关工作流时，才需要优先深入检查。

### 2.5 按目标动态扩展检索源

以上固定入口不是搜索范围的边界。应根据用户的具体目标，主动补充以下来源：

- **官方文档与 Cookbook：** 目标涉及特定框架、模型、硬件或工具时，优先搜索其官方文档、示例和最佳实践。
    
- **领域专用开源项目：** 搜索能够直接完成目标的工具、脚本、工作流及其上游仓库。
    
- **其他技能市场与目录：** 搜索与目标相关的 Agent Skills、插件、工作流模板和自动化工具。
    
- **论文及其配套实现：** 当目标涉及专门算法、评测方法或研究流程时，检查论文是否公开了代码、配置、数据处理脚本和复现实验步骤。
    
- **社区实践：** 在 GitHub Discussions、Issues、技术社区及相关论坛中寻找已验证的解决方案，并将社区建议与实际可执行实现区分开。
    

### 2.6 候选资源的统一评估标准

对检索到的候选资源，统一检查：

1. **目标匹配度：** 是否解决用户提出的实际问题，而非仅涉及相同关键词。
    
2. **实现完整度：** 是否具有具体步骤、必要文件、脚本、工具调用或可运行工作流。
    
3. **执行可行性：** 运行环境、依赖、权限、硬件和外部服务是否满足要求。
    
4. **验证能力：** 是否有测试、验收标准、基准结果、示例输出或可复现证据。
    
5. **可迁移性：** 能否直接复用，还是需要修改参数、替换工具或补齐步骤。
    
6. **维护与可信度：** 检查上游来源、许可证、最近维护记录、已知问题及必要的安全风险。
    
7. **复用成本：** 比较直接使用、局部修改、组合多个方案和从零编写的成本。
    

最终优先推荐与目标匹配、能够验证且复用成本较低的方案。若没有足够证据证明某个候选项目可执行，应明确标记为待验证，不得将其描述为已经验证的解决方案。

## 3. 接收并解析用户目标

从用户的描述中提取：

- 目标：最终要完成什么。
    
- 输入：已有文件、代码、数据、硬件或其他资源。
    
- 约束：操作系统、工具链、权限、成本、性能等。
    
- 交付物：期望获得的文件、程序、配置或运行结果。
    
- 验收条件：如何判断完成。
    

信息足以开始时直接检索，不要要求用户填写冗长表单。只有缺少的关键信息会实质影响搜索结果时，才追问。

## 4. 将目标转化为检索方向

针对具体目标生成少量高相关搜索词，包括：

1. 目标的原始描述与专业术语。
    
2. 目标 + SOP / Skill / Runbook / Playbook。
    
3. 目标 + Workflow / Recipe / Automation / Pipeline。
    
4. 目标 + GitHub / Open Source / Implementation。
    
5. 目标 + 官方框架、关键工具或指定硬件。
    
6. 目标的同义词、替代实现和相关子任务。
    

例如，用户要从 Agent 执行记录中提炼并持续改进 SOP，可搜索：

- `agent SOP from execution traces`
    
- `agent workflow mining`
    
- `learn workflows from agent failures`
    
- `automated runbook generation`
    
- `agent skill evaluation and improvement`
    
- `execution trace analysis agent`
    

搜索结果必须围绕目标，而不是退化成无关的通用资源罗列。

## 5. 执行检索

### 第一步：检查固定入口

查看第 2 节中与目标相关的资源，利用仓库目录、标签