# 主动识图插件

为 Bot 提供主动识图工具 `recognize_image`，支持纯文本 / 多模态两种识别模式，让 LLM 自己决定何时查看图片。

## 功能

- **主动识图工具**：为 LLM 暴露 `recognize_image` 核心工具，Bot 可主动调用查看图片内容
- **双模式支持**：纯文本模式（VLM 转述）和多模态模式（直接返回图片 base64）
- **双识图并存**：纯文本模式下可同时保留框架被动识图 + 插件主动识图，LLM 既可看到自动描述也能深究特定图片
- **带问题识图**：LLM 可传入 `question` 参数让 VLM 带着具体问题回答
- **独立 VLM 配置**：可指定不同于框架默认的 VLM 模型名称
- **自定义提示词**：`{question}` 占位符，支持独立配置识图 prompt
- **转发消息支持**：自动处理转发合集消息中的图片
- **缓存管理**：LRU 缓存近期图片，支持容量上限

## 安装

将插件目录放入 MaiBot 的 `plugins/` 目录下，在 WebUI 插件管理页面中启用即可。

## 配置

```toml
[plugin]
enabled = false
config_version = "2.0.0"

[recognition]
mode = "text"                    # "text" | "multimodal"
dual_recognition = false         # 纯文本模式下同时开启框架被动识图
prompt = ""                      # 自定义提示词，{question} 占位
use_custom_vlm_model = false     # 是否使用独立 VLM 模型
vlm_model = ""                   # VLM 模型名称（如 OpenCodeGo/kimi-k2.7-code）

[cache]
max_images = 200
```

### 模式说明

| 模式 | `mode` | `dual_recognition` | 行为 |
|------|--------|-------------------|------|
| 纯文本（默认） | `text` | `false` | 拦截图片 → `[图片 #N]`，LLM 通过工具查看 |
| 纯文本 + 双识图 | `text` | `true` | 框架自动描述 + 插件编号，LLM 可深究 |
| 多模态 | `multimodal` | — | 拦截图片 → `[图片 #N]`，工具返回原始图片 |

## 使用

### 纯文本模式（默认）

启用后 Bot 收到的图片被替换为 `[图片 #N]` 占位符，LLM 需调用 `recognize_image` 查看内容。

### 双识图模式

框架自动生成基础描述 `[图片：描述内容]`，同时附编号 `[图片 #N]`。LLM 看到描述后如有疑问可调用 `recognize_image(image_number=N)` 深究。

### 多模态模式

图片同样替换为 `[图片 #N]`，但调用 `recognize_image` 时工具直接返回图片数据，让具有多模态能力的 LLM 直接"看"图。

### 识图提示词

优先级：
1. 插件数据目录 `custom_prompts/{locale}/image_description.prompt`
2. `config.toml` 中 `recognition.prompt`
3. 内置默认文本

`{question}` 作为用户问题占位符，未在模板中包含则自动拼接到模板前。

## 工具

### `recognize_image`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image_number` | int | 是 | 图片编号，对应 `[图片 #N]` 中的 N |
| `question` | str | 否 | 对图片的具体问题，如「这是什么品牌？」 |

**纯文本模式返回**：VLM 生成的文字描述 + 图片数据
**多模态模式返回**：图片 base64 数据（不经过 VLM 转述）

## 注意事项

1. 插件仅缓存启用后收到的图片，历史图片无法通过此工具识别
2. 图片数据存储在内存中，重启后清空
3. 同一图片多次发送会占用多个缓存槽位
4. 双识图模式下编号通过独立 TextComponent 注入，不干扰框架 `chat_history_refresher` 自动刷新
