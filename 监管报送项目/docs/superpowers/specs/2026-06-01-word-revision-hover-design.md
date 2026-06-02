# Word Revision Hover Design

## Goal

画像页指标详情中的“原文依据”应接近 Word 修订视图：新增内容在原文位置以蓝色标注，删除内容在原文位置以红色删除线展示，鼠标悬浮显示操作、作者、时间和修订文本。

## Scope

本次只改文档画像页的指标详情，不改“查看原文”弹窗，不改业务信号归并、摘要生成和后续建单逻辑。

## Current Problem

当前链路在 `instruction_parser.py` 中能提取 Word 修订动作，但只保存为动作列表和压平的 `evidence_text`。这会丢失删除内容在段落中的原始顺序，前端只能展示动作清单，不能还原 Word 原位悬浮效果。

## Data Contract

在 `TableChangeSignal` 上增加 `revision_spans` 字段。该字段只用于前端展示，不参与业务归并。

每个 span 包含：

- `type`: `TEXT` / `INSERT` / `DELETE`
- `text`: 片段文本
- `author`: 修订作者，普通文本为空
- `date`: 修订日期，普通文本为空
- `action`: 中文操作名，`新增` / `删除` / 空

## Backend Design

`instruction_parser.py` 新增 Word XML 原位片段解析：

- 读取 `word/document.xml`。
- 按段落和 run 顺序遍历 `w:p` 内的文本节点。
- 普通 `w:t` 输出 `TEXT`。
- `w:ins` 内的 `w:t` 输出 `INSERT`。
- `w:del` 内的 `w:delText` 输出 `DELETE`。
- 段落之间追加换行，方便前端保留阅读结构。

修订年份处理：

- 找出文档中带年份的最新修订年份。
- 最新年份的 `INSERT` / `DELETE` 保持修订状态。
- 历史 `INSERT` 作为普通 `TEXT` 展示。
- 历史 `DELETE` 不展示。

画像阶段：

- 对每条指标定义段落，找到与该段落对应的原位 span。
- 写入 `TableChangeSignal.revision_spans`。
- 合并信号时合并并去重 `revision_spans`。
- API schema 和前端类型同步增加字段。

## Frontend Design

`PortraitView.vue` 的详情“原文依据”优先使用 `signal.revision_spans`：

- `TEXT` 渲染普通文本。
- `INSERT` 渲染蓝色、轻背景、下划线标记。
- `DELETE` 渲染红色、轻背景、删除线标记。
- `title` 或自定义 tooltip 显示 `新增/删除 · 作者 · 日期 · 文本`。

无 `revision_spans` 时降级为现有 `evidence_text` 清洗展示，不推断删除位置。

删除上一版平铺的“Word 修订动作”详情区，避免详情比直接看 doc 更冗长。

## Testing

后端：

- 单测 Word XML 原位 span 顺序。
- 单测最新年份过滤：历史新增转普通文本，历史删除不展示，最新删除保留删除线数据。
- 单测 G01 指标定义信号携带 `revision_spans`。

前端：

- 单测详情优先渲染 `revision_spans`。
- 断言新增、删除节点存在。
- 断言删除节点文本包含 `银行`、`开卡`、`远程`。
- 断言 tooltip/title 包含操作、作者和日期。
- 单测无 `revision_spans` 时继续降级展示正文。

## Acceptance Criteria

- 用户在画像详情中查看 `11.1 通过互联网吸收的个人存款` 时，能在原文位置看到新增和删除修订。
- 鼠标悬浮修订词可以看到操作、作者、时间。
- 删除内容默认以红色删除线显示。
- 不再依赖动作清单理解修订。
- 旧数据或无结构化 span 的信号仍可正常展示。
