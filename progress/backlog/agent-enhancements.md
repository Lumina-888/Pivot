# Agent 后续增强任务清单

> **创建日期**：2026-10-06  
> **状态**：backlog（待规划）  
> **性质**：增强功能、优化改进、技术债务

本文档记录 Agent 基础功能完成后的后续优化和增强任务。

## 1. LlamaIndex 集成（P1 / M）

### 背景
当前使用简单的 Retriever 接口，LlamaIndex 提供更强大的检索能力（多种索引、查询引擎、重排序）。
建议架构：**LlamaIndex 管检索 + LangGraph 管流程**。

### 目标
- 用 LlamaIndex 替换当前的检索实现
- 保持 `pivot.qa.ports.Retriever` 接口不变
- 支持多种索引类型（Vector、Tree、Keyword）
- 支持高级查询引擎（SubQuestion、RouterQuery）

### 实施方案

#### 1.1 依赖安装
```bash
pip install llama-index-core==0.10.x
pip install llama-index-embeddings-openai  # 或其他 embedding 模型
pip install llama-index-vector-stores-qdrant  # 如果使用 Qdrant
```

#### 1.2 实现适配器
创建 `api/src/pivot/retrieval/llama_index_retriever.py`：

```python
from llama_index.core import VectorStoreIndex, ServiceContext
from pivot.qa.ports import Retriever, RetrievalResult, EvidenceHit

class LlamaIndexRetriever:
    """使用 LlamaIndex 实现的检索器"""
    
    def __init__(self, index: VectorStoreIndex):
        self.index = index
        self.query_engine = index.as_query_engine(similarity_top_k=5)
    
    def retrieve(self, question, *, scope_type, scope_document_id, principal_id):
        # 使用 LlamaIndex 检索
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

#### 1.3 集成到 StateGraph
```python
from pivot.retrieval.llama_index_retriever import LlamaIndexRetriever
from pivot.qa.agent_graph import create_agent_graph

# 创建索引（生产环境从持久化加载）
index = VectorStoreIndex.from_documents(documents)

# 创建检索器
retriever = LlamaIndexRetriever(index)

# 创建 Agent 图（无需修改）
graph = create_agent_graph(
    retriever=retriever,
    budget_policy=budget_policy,
)
```

#### 1.4 测试兼容性
- 所有现有单元测试应该继续通过（使用 Fake Retriever）
- 新增 LlamaIndex 集成测试
- 对比检索质量（召回率、精确度）

### 依赖
- ✅ ND-AGENT-02-D 完成（Retriever 接口已定义）
- ✅ ND-AGENT-02-G 完成（StateGraph 已实现）
- ⏸️ 等待基础 Agent 功能验证通过

### 验收标准
- [ ] LlamaIndexRetriever 实现 Retriever 接口
- [ ] 所有现有测试通过
- [ ] 新增 3 个 LlamaIndex 集成测试
- [ ] 检索质量 benchmark（对比旧实现）
- [ ] 文档更新：如何切换检索后端

### 优先级
P1 - 在 Agent 基础功能稳定后实施

---

## 2. 其他待规划任务

### 2.1 查询改写（Query Rewriting）
- 实现 PR-01：用户输入 Prompt 重写
- 支持多轮改写（max_rewrite_count=2）
- 保留原始意图追踪

### 2.2 多模型支持
- 支持主备模型切换
- 模型能力探测
- 成本优化（使用便宜模型做简单任务）

### 2.3 流式响应
- 支持 SSE 流式输出
- 增量答案生成
- 工具调用进度反馈

### 2.4 高级检索策略
- 混合检索（向量 + 关键词）
- 重排序（rerank）
- 上下文压缩

### 2.5 性能优化
- 并发工具调用
- 缓存检索结果
- 预算优化（避免重复检索）

### 2.6 可观测性
- 结构化日志
- Metrics 导出
- Trace 追踪（LangSmith/OpenTelemetry）

---

## 更新记录

- 2026-10-06：创建文档，记录 LlamaIndex 集成任务
