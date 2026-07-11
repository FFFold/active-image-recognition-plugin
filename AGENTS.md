# 主动识图插件

## 仓库结构

- `plugin.py` — 入口，`create_plugin()` 工厂函数
- `_manifest.json` — 插件元信息（host/sdk 版本范围、capabilities）
- `config.toml` — 配置项

## 设计要点

- `@HookHandler("chat.receive.before_process", BLOCKING, EARLY)` 在消息处理前拦截所有图片，替换为 `[图片 #N]` 占位符，清除二进制数据 → 阻止 MaiBot 默认 VLM 被动识别
- `@Tool("recognize_image", core_tool=True)` LLM 在 planner 阶段始终可见，通过 `image_number` 参数指定要识别的图片
- 转发合集消息递归处理，扁平编号
- 缓存用 `deque` + LRU 淘汰（默认上限 200），存 key `(session_id, counter)` → `{hash, bytes, format}`
- 缓存为实例变量（`__init__` 初始化），非类变量，重启清空

## 运行

不独立运行，需放入 MaiBot `plugins/` 目录，在 WebUI 插件管理中启用。

## 验证

```bash
ruff check plugin.py
python -c "import ast; ast.parse(open('plugin.py').read())"
python -c "import json; json.load(open('_manifest.json'))"
```

## 依赖

- 运行时：MaiBot 提供 `maibot-plugin-sdk>=2.5.1`
- 无需额外包依赖

## Git

仓库独立于 MaiBot 主仓库，主分支为 `master`。
