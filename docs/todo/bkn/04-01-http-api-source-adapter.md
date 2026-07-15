# Feature 4.1：HTTP/API 数据源适配器

## 目标

支持从平台 HTTP/API 动态读取节点属性。

## 需要干什么

- 支持 manifest 中声明 `data_source_kind=api_endpoint`。
- 实现 HTTP 只读 adapter，支持 base_url、endpoint template、timeout、retries。
- auth 只支持安全引用，不把 token 写进 graph 或 schema。

## 为什么

- minimax 设计里的最终形态是“平台 API 是权威数据源”。
- HTTP/API 涉及网络、认证和安全，需要在本阶段单独收敛。

## 需要改什么文件

- `bamboo/bkn/attrs_store.py`
  - 增加 `HttpApiAdapter`。
- `bamboo/security/url_safety.py`
  - 如需限制 URL，复用或扩展 URL 安全校验。
- `pyproject.toml`
  - 已有 `httpx[socks]`，无需新增依赖。

## 需要增加什么文件

- `tests/test_bkn_http_attrs.py`

## 测试

- mock HTTP 成功读取。
- 超时返回 attrs_unavailable。
- 非 allowlist URL 被拒绝。
- token 不出现在 tool result 和 audit log。

## 验收标准

- BKN 可以从测试 HTTP 服务读取属性，并在 snapshot 中标明 source/fetched_at。
