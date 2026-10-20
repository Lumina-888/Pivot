# Agent 实施路线图

> **创建日期**：2026-10-11  
> **状态**：执行中  
> **Owner**：lumina888  
> **目标**：完成 Pivot Agent 从基础框架到可演示系统的完整实施

---

**口径说明**：本节是 2026-10-11 的状态快照。现行状态以 [PROGRESS.md](../../PROGRESS.md) 为准。本节的完成标记表示开发实现已经提交，不构成运行批准，也不构成验收结论。

## 0. 当前状态

### ✅ 已完成（Phase 0: 基础设施）

- **Owner 决策**（commit 0a309b0）
  - 批准 02-A/B/C、03-A、04-A 提案
  - 允许 LangGraph 安装和真实 API 联调
  - 预算：单次 100 元，累计 500 元

- **ND-AGENT-02-D**（commit c06978c + ab167c8）
  - SearchKnowledgeTool / ReadEvidenceTool
  - EvidenceRegistry + ToolExecutor
  - 15/15 测试通过

- **ND-AGENT-02-F**（commit aa0eb4e）
  - BudgetPolicy / BudgetState / BudgetGuard
  - 18/18 测试通过

- **ND-AGENT-02-C**（commit a07e61f）
  - langgraph==0.2.45
  - langchain-core==0.3.21

- **ND-AGENT-02-G**（commit 8a309c3）
  - AgentState + AgentNodes
  - 条件路由（tools/finalize/end）

- **ND-AGENT-02-H**（commit c558d56 + 2ee808a）
  - StructuredFinalizer
  - 8/8 测试通过

**统计**：26 commits, 4,114 行代码, 41/41 测试通过

### ✅ 已完成（Phase 1-3: 完整闭环）

- **Phase 1: LlamaIndex 检索集成**（commit 37b6f1e）
  - LlamaIndexRetriever 实现
  - 测试文档集与索引构建脚本
  - 集成测试通过

- **Phase 2: 真实模型集成**（commit 1f12406）
  - AgentModel 适配器（ChatOpenAI）
  - 工具 schema 定义
  - decide 节点真实模型调用
  - 模型集成测试通过

- **Phase 3: 端到端闭环**（commit eef40df）
  - agent_graph 路由支持 LangGraph AIMessage
  - finalize 节点接入 StructuredFinalizer
  - run_agent 接收 model/finalizer 参数
  - 预算耗尽优雅停止
  - 4/4 端到端测试通过（Fake 模型）

**统计**：Phase 0-3 完成，基础框架 → 真实集成 → 端到端闭环

### ⚠️ 剩余工作（可选/待定）

- 真实 API 端到端测试（需要 API key）
- 答案质量人工评估
- 性能测试
- Demo 文档

---

## 1. Phase 1: LlamaIndex 检索集成（1-2 天）

### 1.1 目标

让 Agent 能够检索真实文档并返回证据。

### 1.2 任务清单

#### 1.2.1 依赖安装

```bash
# 核心库
pip install llama-index-core==0.11.x

# Embedding 模型（选其一）
pip install llama-index-embeddings-openai      # 使用 OpenAI embedding
# 或
pip install llama-index-embeddings-huggingface # 使用本地模型

# 向量存储（选其一）
pip install llama-index-vector-stores-qdrant   # Qdrant（推荐）
# 或
pip install llama-index-vector-stores-chroma   # Chroma（简单）
```

**验收标准**：
- [ ] 依赖安装成功
- [ ] `from llama_index.core import VectorStoreIndex` 导入成功
- [ ] compileall 通过

#### 1.2.2 实现 LlamaIndexRetriever

**文件**：`api/src/pivot/retrieval/llama_index_retriever.py`

```python
from llama_index.core import VectorStoreIndex, ServiceContext
from llama_index.embeddings.openai import OpenAIEmbedding
from pivot.qa.ports import Retriever, RetrievalResult, EvidenceHit

class LlamaIndexRetriever:
    """使用 LlamaIndex 实现的检索器"""
    
    def __init__(self, index: VectorStoreIndex):
        self.index = index
        self.query_engine = index.as_query_engine(
            similarity_top_k=5,
            response_mode="no_text"  # 只返回节点，不生成摘要
        )
    
    def retrieve(
        self,
        question: str,
        *,
        scope_type: str,
        scope_document_id: str | None,
        principal_id: str,
    ) -> RetrievalResult:
        """检索相关证据"""
        
        # 构建过滤器（如果需要按文档范围过滤）
        filters = None
        if scope_type == "document" and scope_document_id:
            filters = {"document_id": scope_document_id}
        
        # 执行检索
        response = self.query_engine.query(question)
        
        # 转换为 EvidenceHit 格式
        hits = []
        for node in response.source_nodes:
            hits.append(EvidenceHit(
                chunk_id=node.node_id,
                document_id=node.metadata.get("document_id", "unknown"),
                version_id=node.metadata.get("version_id", "v1"),
                text=node.text,
                locator=f"score={node.score:.4f}",
                external_llm_allowed=True,  # 根据文档权限设置
            ))
        
        status = "found" if hits else "empty"
        return RetrievalResult(status=status, evidence=tuple(hits))
```

**验收标准**：
- [ ] 实现 Retriever 协议
- [ ] 支持 scope_type 过滤
- [ ] 转换 LlamaIndex 格式到 EvidenceHit
- [ ] compileall/ruff 通过

#### 1.2.3 准备测试文档集

**文件**：`tests/fixtures/documents/sample_policies.txt`

示例内容（考勤制度）：
```
考勤管理制度

第一条 迟到早退规定
员工应按时上下班。迟到或早退超过30分钟按旷工半天处理。
一个月内累计迟到三次以上，视为旷工一天。

第二条 请假流程
员工请假需提前一天申请，经部门主管批准后生效。
病假需提供医院证明。事假扣除当日工资。

第三条 加班规定
加班需提前申请，经主管批准。
工作日加班按1.5倍工资计算，周末加班按2倍计算。
```

**验收标准**：
- [ ] 准备 3-5 个测试文档
- [ ] 涵盖不同主题（考勤、薪资、福利等）
- [ ] 每个文档 500-1000 字

#### 1.2.4 构建索引脚本

**文件**：`scripts/build_test_index.py`

```python
"""构建测试用的向量索引"""

from pathlib import Path
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Document
from llama_index.embeddings.openai import OpenAIEmbedding

def build_test_index():
    # 读取测试文档
    docs_path = Path("tests/fixtures/documents")
    documents = SimpleDirectoryReader(docs_path).load_data()
    
    # 添加元数据
    for i, doc in enumerate(documents):
        doc.metadata["document_id"] = f"doc_{i+1}"
        doc.metadata["version_id"] = "v1"
    
    # 构建索引
    index = VectorStoreIndex.from_documents(
        documents,
        embed_model=OpenAIEmbedding(model="text-embedding-3-small"),
    )
    
    # 持久化
    index.storage_context.persist("tests/fixtures/index")
    print(f"✅ 索引已构建：{len(documents)} 个文档")

if __name__ == "__main__":
    build_test_index()
```

**验收标准**：
- [ ] 脚本能成功运行
- [ ] 生成索引文件到 `tests/fixtures/index/`
- [ ] 能加载索引并执行查询

#### 1.2.5 集成测试

**文件**：`tests/integration/test_llama_index_retrieval.py`

```python
"""LlamaIndex 检索集成测试"""

import pytest
from llama_index.core import StorageContext, load_index_from_storage
from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever

@pytest.fixture
def retriever():
    storage_context = StorageContext.from_defaults(
        persist_dir="tests/fixtures/index"
    )
    index = load_index_from_storage(storage_context)
    return LlamaIndexRetriever(index)

def test_retrieval_returns_relevant_evidence(retriever):
    """测试：检索返回相关证据"""
    result = retriever.retrieve(
        "迟到三次怎么处理？",
        scope_type="all",
        scope_document_id=None,
        principal_id="user_1",
    )
    
    assert result.status == "found"
    assert len(result.evidence) > 0
    assert any("迟到" in hit.text for hit in result.evidence)

def test_retrieval_empty_when_no_match(retriever):
    """测试：无匹配时返回空"""
    result = retriever.retrieve(
        "火星移民政策",
        scope_type="all",
        scope_document_id=None,
        principal_id="user_1",
    )
    
    assert result.status in ("empty", "found")
    if result.status == "found":
        assert len(result.evidence) == 0
```

**验收标准**：
- [ ] 集成测试通过（至少 2 个）
- [ ] 检索质量可接受（人工评估）
- [ ] 端到端流程顺畅

#### 1.2.6 Agent 集成

修改 `api/src/pivot/qa/agent_graph.py` 中的 `create_agent_graph` 函数：

```python
def create_agent_graph(
    retriever: Retriever,  # 传入真实的 LlamaIndexRetriever
    budget_policy: BudgetPolicy,
    draft_writer: DraftWriter | None = None,
    verifier: Verifier | None = None,
) -> StateGraph:
    # ... 现有代码
```

**验收标准**：
- [ ] Agent 能使用真实检索器
- [ ] SearchKnowledgeTool 返回真实证据
- [ ] 所有现有单元测试仍然通过（使用 Fake）

### 1.3 Phase 1 DoD（Definition of Done）

- [ ] LlamaIndex 依赖安装完成
- [ ] LlamaIndexRetriever 实现并通过单元测试
- [ ] 测试文档集准备完成（3-5 个文档）
- [ ] 索引构建脚本可用
- [ ] 集成测试通过（2/2）
- [ ] Agent 能执行真实检索
- [ ] 检索质量达到可演示标准
- [ ] 提交代码并更新 PROGRESS.md

---

## 2. Phase 2: 真实模型集成（1-2 天）

### 2.1 目标

让 Agent 的 `decide` 节点能调用真实的 LLM 做决策。

### 2.2 任务清单

#### 2.2.1 依赖安装

```bash
# OpenAI Adapter
pip install langchain-openai==0.2.x

# 或其他模型（根据实际选择）
# pip install langchain-anthropic
# pip install langchain-community
```

**验收标准**：
- [ ] 依赖安装成功
- [ ] `from langchain_openai import ChatOpenAI` 导入成功

#### 2.2.2 实现 AgentModel Adapter

**文件**：`api/src/pivot/qa/agent_model.py`

```python
"""Agent 模型适配器"""

from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

class AgentModel:
    """Agent 决策模型"""
    
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.0,
        api_key: str | None = None,
    ):
        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
        )
    
    def decide(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AIMessage:
        """
        执行决策
        
        Args:
            messages: 历史消息
            tools: 可用工具定义
        
        Returns:
            AIMessage（可能包含 tool_calls）
        """
        # 绑定工具
        model_with_tools = self.model.bind_tools(tools)
        
        # 调用模型
        response = model_with_tools.invoke(messages)
        
        return response
```

**验收标准**：
- [ ] 支持工具绑定
- [ ] 返回 AIMessage 格式
- [ ] 支持 tool_calls 解析
- [ ] compileall/ruff 通过

#### 2.2.3 定义工具 Schema

**文件**：`api/src/pivot/qa/agent_tools.py`（扩展现有文件）

添加工具 schema：

```python
def get_tool_schemas() -> list[dict[str, Any]]:
    """返回工具的 JSON Schema 定义"""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": "搜索知识库中的相关信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询词",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_evidence",
                "description": "读取已找到的证据详细内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "evidence_id": {
                            "type": "string",
                            "description": "证据 ID",
                        }
                    },
                    "required": ["evidence_id"],
                },
            },
        },
    ]
```

**验收标准**：
- [ ] 工具 schema 符合 OpenAI 函数调用格式
- [ ] 描述清晰准确
- [ ] 参数定义完整

#### 2.2.4 修改 decide 节点

**文件**：`api/src/pivot/qa/agent_graph.py`

```python
def decide(self, state: AgentState) -> AgentState:
    """Agent 决策节点（使用真实模型）"""
    
    # 预算检查
    if not self.budget_guard.check_before_action(
        state["budget_state"], action_type="model_call"
    ):
        # 预算耗尽，直接 finalize
        return {
            **state,
            "messages": state["messages"]
            + [{"role": "assistant", "content": "", "control_intent": "finalize"}],
        }
    
    # 构建消息历史
    messages = state["messages"]
    
    # 调用模型
    response = self.model.decide(
        messages=messages,
        tools=get_tool_schemas(),
    )
    
    # 更新预算
    new_budget = self.budget_guard.update_after_action(
        state["budget_state"], action_type="model_call"
    )
    
    # 转换为 dict 格式
    response_dict = {
        "role": "assistant",
        "content": response.content,
    }
    
    # 处理 tool_calls
    if response.tool_calls:
        response_dict["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments,
                },
            }
            for tc in response.tool_calls
        ]
    
    return {
        **state,
        "messages": state["messages"] + [response_dict],
        "budget_state": new_budget,
    }
```

**验收标准**：
- [ ] 使用真实模型替换占位符
- [ ] 正确处理 tool_calls
- [ ] 预算追踪正常
- [ ] 消息格式正确

#### 2.2.5 模型调用测试

**文件**：`tests/integration/test_agent_model.py`

```python
"""Agent 模型集成测试"""

import pytest
from pivot.qa.agent_model import AgentModel
from pivot.qa.agent_tools import get_tool_schemas

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="需要 OPENAI_API_KEY"
)
def test_model_decides_to_search():
    """测试：模型决定搜索"""
    model = AgentModel()
    
    messages = [
        {"role": "user", "content": "请问迟到三次怎么处理？"}
    ]
    
    response = model.decide(
        messages=messages,
        tools=get_tool_schemas(),
    )
    
    assert response.tool_calls is not None
    assert len(response.tool_calls) > 0
    assert response.tool_calls[0].name == "search_knowledge"

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="需要 OPENAI_API_KEY"
)
def test_model_decides_to_finalize():
    """测试：模型决定结束"""
    model = AgentModel()
    
    messages = [
        {"role": "user", "content": "你好"},
    ]
    
    response = model.decide(
        messages=messages,
        tools=get_tool_schemas(),
    )
    
    # 简单问候应该直接回答，不调用工具
    assert response.tool_calls is None or len(response.tool_calls) == 0
```

**验收标准**：
- [ ] 真实 API 调用成功
- [ ] 模型能正确选择工具
- [ ] tool_calls 格式正确
- [ ] 预算消耗正确追踪

#### 2.2.6 预算追踪验证

**文件**：`tests/integration/test_budget_tracking.py`

```python
"""预算追踪集成测试"""

def test_budget_tracks_real_model_calls():
    """测试：预算正确追踪真实模型调用"""
    
    policy = BudgetPolicy(
        max_model_calls=2,
        max_tool_calls=5,
        max_rewrite_count=1,
        timeout_seconds=60,
    )
    
    # ... 创建 agent graph
    
    # 执行多次调用
    # 验证预算递减
    # 验证达到上限时停止
```

**验收标准**：
- [ ] 预算正确递减
- [ ] 达到上限时 fail closed
- [ ] 不同维度独立追踪

### 2.3 Phase 2 DoD

- [ ] langchain-openai 依赖安装完成
- [ ] AgentModel 实现并通过测试
- [ ] 工具 schema 定义完整
- [ ] decide 节点使用真实模型
- [ ] 模型集成测试通过（2/2）
- [ ] 预算追踪验证通过
- [ ] 提交代码并更新 PROGRESS.md

---

## 3. Phase 3: 端到端测试与优化 ✅

### 3.1 目标

验证完整的 Agent 流程，从用户问题到最终答案。

**状态**：✅ 已完成（commit eef40df）

### 3.2 任务清单

#### 3.2.1 端到端测试

**文件**：`tests/e2e/test_agent_complete_flow.py`

```python
"""Agent 端到端测试"""

@pytest.mark.e2e
def test_complete_question_answering_flow():
    """
    测试：完整的问答流程
    
    Given: 用户问"迟到三次怎么处理？"
    When: Agent 执行完整流程
    Then: 返回正确答案并引用证据
    """
    # 1. 创建所有依赖
    retriever = create_test_retriever()
    model = AgentModel()
    finalizer = create_test_finalizer()
    
    # 2. 创建 graph
    graph = create_agent_graph(
        retriever=retriever,
        budget_policy=BudgetPolicy(...),
        model=model,
        finalizer=finalizer,
    )
    
    # 3. 执行
    result = run_agent(
        graph,
        question="迟到三次怎么处理？",
        run_id="run_1",
        principal_id="user_1",
    )
    
    # 4. 验证
    assert result["final_answer"] is not None
    assert "旷工" in result["final_answer"]["answer"]
    assert len(result["final_answer"]["claims"]) > 0
    assert result["budget_state"]["remaining"] > 0

@pytest.mark.e2e
def test_multi_turn_conversation():
    """测试：多轮对话"""
    # ...

@pytest.mark.e2e
def test_budget_exhaustion_stops_gracefully():
    """测试：预算耗尽时优雅停止"""
    # ...
```

**验收标准**：
- [ ] 端到端测试通过（至少 3 个场景）
- [ ] 覆盖正常流程、多轮对话、预算耗尽
- [ ] 答案质量可接受

#### 3.2.2 性能测试

**文件**：`tests/performance/test_agent_performance.py`

```python
"""Agent 性能测试"""

def test_response_time_under_10_seconds():
    """测试：响应时间 < 10 秒"""
    
    start = time.time()
    result = run_agent(graph, question="简单问题")
    elapsed = time.time() - start
    
    assert elapsed < 10.0

def test_handles_concurrent_requests():
    """测试：并发请求处理"""
    # ...
```

**验收标准**：
- [ ] 单个请求 < 10 秒
- [ ] 支持并发（如果需要）
- [ ] 内存使用合理

#### 3.2.3 答案质量评估

手动测试 10 个问题：

| 问题 | 答案正确性 | 证据引用 | 备注 |
|------|-----------|---------|------|
| 迟到三次怎么处理？ | ✅ | ✅ | |
| 请假需要提前多久？ | ✅ | ✅ | |
| ... | | | |

**验收标准**：
- [ ] 10 个问题中至少 8 个正确
- [ ] 所有答案都有证据引用
- [ ] 无幻觉或错误信息

#### 3.2.4 文档更新

更新以下文档：
- `README.md`：添加使用说明
- `PROGRESS.md`：更新进度
- `docs/AGENT_USAGE.md`：编写使用指南

**验收标准**：
- [ ] 文档完整清晰
- [ ] 包含示例代码
- [ ] 包含配置说明

#### 3.2.5 Demo 准备

准备答辩演示：
- [ ] 准备 3-5 个演示问题
- [ ] 录制演示视频（可选）
- [ ] 准备 PPT 讲解材料

### 3.3 Phase 3 DoD

- [x] 端到端测试通过（4/4）✅
  - `test_complete_question_answering_flow`
  - `test_multi_turn_tool_sequence_keeps_question_context`
  - `test_budget_exhaustion_stops_before_another_model_call`
  - `test_run_agent_rejects_non_positive_budget`
- [ ] 性能测试达标（可选）
- [ ] 答案质量评估通过（可选，需要真实 API）
- [x] 文档更新完成 ✅
- [ ] Demo 准备就绪（可选）
- [x] 提交最终代码 ✅

---

## 4. 风险与应对

### 4.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| LlamaIndex 版本不兼容 | 高 | 中 | 固定版本号，充分测试 |
| API 配额耗尽 | 中 | 中 | 设置预算上限，使用便宜模型 |
| 检索质量不达标 | 高 | 低 | 调整 top_k、重排序 |
| 响应时间过长 | 中 | 中 | 使用更快的模型、缓存 |

### 4.2 时间风险

总预计时间：**4-5 天**

- Phase 1: 1-2 天
- Phase 2: 1-2 天
- Phase 3: 1 天
- 缓冲时间: 1 天

如果时间紧张，可以：
- 简化 Phase 3 的性能测试
- 减少测试用例数量
- 使用更快的模型（如 gpt-4o-mini）

---

## 5. 验收标准（总体）

### 5.1 功能完整性

- [ ] Agent 能检索真实文档
- [ ] Agent 能调用真实模型
- [ ] Agent 能生成结构化答案
- [ ] 预算管理正常工作
- [ ] 证据追踪完整

### 5.2 质量标准

- [ ] 所有单元测试通过（50+ tests）
- [ ] 集成测试通过（5+ tests）
- [ ] 端到端测试通过（3+ tests）
- [ ] 答案质量达标（80%+ 正确率）
- [ ] 代码质量：compileall/ruff/LSP 通过

### 5.3 可演示性

- [ ] 能现场演示完整问答
- [ ] 响应时间可接受（< 10 秒）
- [ ] 有真实文档和数据
- [ ] 有清晰的讲解材料

---

## 6. 下一步行动

**立即开始**：Phase 1 - LlamaIndex 集成

第一个任务：
```bash
# 1. 安装依赖
pip install llama-index-core llama-index-embeddings-openai

# 2. 验证安装
python -c "from llama_index.core import VectorStoreIndex; print('OK')"

# 3. 创建 LlamaIndexRetriever
touch api/src/pivot/retrieval/__init__.py
touch api/src/pivot/retrieval/llama_index_retriever.py
```

准备好了吗？让我们开始！
