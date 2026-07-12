# 主动识图插件

## 仓库结构

- `plugin.py` — 入口，`create_plugin()` 工厂函数
- `_manifest.json` — 插件元信息（host/sdk 版本范围、capabilities）
- `config.toml` — 配置项
- `docs/superpowers/` — 本地开发文档（不提交 Git）

## 设计要点

### 配置

- `[recognition]` 段控制模式：`mode`（"text"/"multimodal"）、`dual_recognition`（纯文本下开启框架被动识图）、`prompt`（自定义提示词）

### Hook 流程

- `@HookHandler("chat.receive.before_process", BLOCKING, EARLY)` — 所有模式缓存图片
  - **默认**（text + dual=false）：设 `[图片 #N]` + 清除 binary，阻止框架被动识图
  - **双识图**（text + dual=true）：仅缓存，不改 content/binary，让框架正常运行
  - **多模态**（multimodal）：同默认行为
- `@HookHandler("chat.receive.after_process", BLOCKING, NORMAL)` — 仅在双识图模式生效
  - 框架 `process()` 后，在每个 ImageComponent 后插入 TextComponent `[图片 #N]`
  - 不修改 ImageComponent.content，确保框架 `chat_history_refresher` 自动刷新机制不被阻断

### 工具

- `@Tool("recognize_image", core_tool=True)` — 纯文本模式返回 VLM 文本描述，多模态模式返回原始图片 base64
- 参数：`image_number`（必填）、`question`（可选）

### 提示词

- 优先级：`{data_dir}/custom_prompts/{locale}/image_description.prompt` → `config.toml prompt` → 内置默认
- `{question}` 占位，未含变量则自动拼接 `"用户的问题是：{question}\n\n{template}"`
- 实例级 `_prompt_cache` 缓存，`on_config_update` 时清空

### 缓存

- `deque` + LRU 淘汰（默认上限 200），存 key `(session_id, counter)` → `{hash, bytes, format}`
- 会话计数器 `_session_counters: dict[str, int]` 跨消息单调递增
- `_pending_message_image_range: dict[str, tuple[int, int]]` 记录单消息图片编号范围

## 运行

不独立运行，需放入 MaiBot `plugins/` 目录，在 WebUI 插件管理中启用。

## 验证

```bash
ruff check plugin.py
python -c "import ast; ast.parse(open('plugin.py', encoding='utf-8').read())"
python -c "import json; json.load(open('_manifest.json'))"
```

## 依赖

- 运行时：MaiBot 提供 `maibot-plugin-sdk>=2.5.1`
- 无需额外包依赖

## Git

仓库独立于 MaiBot 主仓库，主分支为 `master`。
