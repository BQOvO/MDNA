---
name: "focus-writer"
description: "为 Pipeline JSON 节点编写 focus 字段。当用户要求给节点加 focus、写 focus 文案、或提到 UI 面板显示文字时调用。"
---

# Focus Writer

为 MaaFramework Pipeline JSON 节点编写 `focus` 字段，用于在 MFAA/MXU 客户端 UI 面板上显示任务执行状态。

## 核心原则

### 1. 大白话，不说文言文
用户看不懂古风表达，必须用现代汉语。对比：
- ❌ `振臂挥竿，一掷乾坤`
- ✅ `准备开始钓鱼啦！`

### 2. 不用太精炼，UI 面板空间够大
可以写完整句子，不需要缩成四字成语。对比：
- ❌ `渔获丰收`
- ✅ `钓到鱼啦！`

### 3. 颜文字表达情绪，文字说大白话
颜文字负责视觉情绪，文案负责讲清楚在干什么。几种典型情绪：

| 场景 | 颜文字 | 情绪 |
|------|--------|------|
| 开始行动 | `(๑•̀ㅂ•́)و✧` | 干劲满满 |
| 等待中 | `(´-ω-`)` | 佛系静候 |
| 激动事件 | `٩(ˊᗜˋ*)و` | 惊喜欢呼 |
| 紧张博弈 | `(ง •̀_•́)ง` | 专注战斗 |
| 成功结果 | `(๑˃̵ᴗ˂̵)و` | 开心满足 |
| 失败结果 | `(╥﹏╥)` | 遗憾惋惜 |
| 稀有事件 | `✧` | 特殊高亮 |

### 4. 只给关键节点配 focus，跳过/动画节点不需要
- ✅ 配 focus：开始节点、等待节点、结果节点、特殊事件节点
- ❌ 不配 focus：跳过动画节点、纯过渡节点

### 5. 调试信息不进 focus，进终端
- ✅ focus 显示：`正在和鱼拉扯中！`
- ❌ focus 显示：`icon_y=117 offset=+23 bar=[38,151]`（这些是给开发者看的，留终端）

### 6. focus 会自动带上任务名前缀
FocusPrefix sink 会自动在 focus 前加 `[任务名] `，所以文案里不需要重复任务名。

### 7. 要有对话感，像在和用户聊天
文案应该有"程序在跟你说话"的感觉，而不是冷冰冰的状态报告。多用"你"、"啦"、"~"等口语化表达。对比：
- ❌ `选择等级 100`（冷冰冰的声明）
- ✅ `你选择了level.100`（像在跟你对话）
- ❌ `进入副本成功`（机器报告）
- ✅ `进入副本成功！`（有语气，有人味）

## focus 事件类型

根据节点行为选择合适的 key：

| Key | 触发时机 | 适用场景 |
|-----|----------|----------|
| `Node.Action.Starting` | 动作开始执行 | 点击、滑动、自定义动作 |
| `Node.Recognition.Starting` | 识别开始执行 | 等待 OCR/模板匹配 |
| `Node.Recognition.Succeeded` | 识别成功 | 检测到目标时的提示 |

## 格式模板

```json
"focus": {
  "Node.Action.Starting": "(๑•̀ㅂ•́)و✧ 准备开始XXX啦！",
  "Node.Recognition.Succeeded": "(๑˃̵ᴗ˂̵)و XXX成功啦！"
}
```

## 实战示例（钓鱼任务）

```json
"钓鱼-开始钓鱼": {
  "focus": { "Node.Action.Starting": "(๑•̀ㅂ•́)و✧ 准备开始钓鱼啦！" }
}
"钓鱼-抛竿": {
  "focus": { "Node.Action.Starting": "抛竿中，等待鱼儿上钩~" }
}
"钓鱼-等鱼": {
  "focus": { "Node.Recognition.Starting": "(´-ω-`) 等待鱼儿咬钩中..." }
}
"钓鱼-鱼上钩了": {
  "focus": { "Node.Recognition.Succeeded": "٩(ˊᗜˋ*)و 鱼上钩了！快收线！" }
}
"钓鱼-钓鱼博弈": {
  "focus": { "Node.Action.Starting": "(ง •̀_•́)ง 正在和鱼拉扯中！" }
}
"钓鱼-钓鱼成功": {
  "focus": { "Node.Recognition.Succeeded": "(๑˃̵ᴗ˂̵)و 钓到鱼啦！" }
}
"钓鱼-钓鱼失败": {
  "focus": { "Node.Recognition.Succeeded": "(╥﹏╥) 鱼跑掉了..." }
}
"钓鱼-授渔以鱼": {
  "focus": { "Node.Recognition.Succeeded": "✧ 触发授渔以鱼！额外奖励！" }
}
```

## 工作流程

1. 阅读目标 Pipeline JSON，理解节点流程
2. 找出关键节点（开始、等待、结果、特殊事件）
3. 为每个关键节点确定合适的 `focus` key（Action.Starting / Recognition.Starting / Recognition.Succeeded）
4. 根据节点所处的阶段和情绪，选配合适的颜文字
5. 用大白话写一句描述性文案
6. 跳过动画节点和纯过渡节点，不给它们配 focus
7. 验证 JSON 语法正确