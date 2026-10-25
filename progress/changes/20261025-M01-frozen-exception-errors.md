# 变更申请：取消异常类的冻结 dataclass

- 状态：已验证；待合并批准。
- 范围：M01、M02、M05、M06、M07 的共享错误类。
- 依据：SPEC 附录 B.1 错误包络。

## 背景

CI #216 两次尝试均红。失败组为 M11-pipeline。首个失败为登录统一错误用例。根因为 AuthError 是冻结 dataclass。新版 FastAPI 与 Starlette 把 ExitStack 放入请求作用域。异常经 ExitStack 时，标准库修正异常上下文。修正为属性写。冻结类拒绝属性写。于是抛 FrozenInstanceError。统一包络未返回。

本地旧环境无此路径，测试通过。旧环境为 fastapi 0.159.1、starlette 1.9.0。全新解析环境复现失败。环境为 fastapi 0.162.0、starlette 1.10.0。PR #48 仅含 2 个文档文件，与失败无关。

## 决定

取消 6 个异常类的冻结。文件为 6 个 errors.py。分属 audit、auth、documents。分属 exports、parsing、runs。字段、相等性、包络均不变。无代码依赖哈希与集合。无 ADR，因为包络与权限语义均不变。

## 验证

全新解析环境复现失败后，修后单测通过。pipeline 组 337 通过、20 跳过。M01-auth 组 82 通过。M02-documents 组 34 通过。M06-export-audit 组 37 通过。ruff 全过。

## 未采纳方案

钉死 starlette 与 fastapi 版本。钉死只治一时。冻结异常遇标准异常机制即崩。取消冻结治本。
