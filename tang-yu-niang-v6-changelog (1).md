# 棠予酿 v6 改动清单

> 基于 `tang-yu-niang-v5.jsx` 进行修改。以下所有改动经棠棠确认，请逐条执行。

---

## 1. 字体方案

替换现有的 `Noto Serif SC` 统一字体，改为分场景多字体搭配。所有字体从 Google Fonts import。

| 场景 | 字体 | 用途 |
|------|------|------|
| 英文标题 / 品牌字 | **Cinzel** | "棠予酿" 旁的英文副标题、页面大标题 |
| 英文浪漫场景 | **Cormorant Garamond** | 信封内文英文、日记中的英文引用 |
| 英文功能文字 | **Quicksand** | 按钮标签、导航栏标签、标签筛选按钮 |
| 中文标题 / 信封 / 日记正文 | **UoqMunThenKhung（宇文天穹）** | "棠予酿"、信封内容、日记正文、记忆标题。fallback: LXGW WenKai |
| 中文功能性小字 | **Noto Sans SC Light** | 日期、数字、状态文字、说明文字 |

Google Fonts import 示例：
```css
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600&family=Cormorant+Garamond:wght@300;400&family=Quicksand:wght@300;400;500;600&family=UoqMunThenKhung&family=Noto+Sans+SC:wght@300;400&display=swap');
```

---

## 2. 星辰粒子效果

当前问题：粒子只是原地闪烁和微微漂移，缺少动感。

改动要求：
- 部分粒子（约30%）改为**流星效果**：从随机位置出现，向下方/斜下方坠落并拖出一条渐隐的尾巴，到底部或中途消失后重新从顶部生成
- 流星拖尾用 `box-shadow` 拉长 + 透明度渐变实现，或用伪元素画尾巴
- 闪烁粒子的**峰值亮度拉高**：`opacity` 峰值从 0.9 提到 1.0，`box-shadow` 的 spread 从 `sz*3` 增大到 `sz*5`，加一层淡色外层光晕
- 剩余70%粒子保持原有的 shimmer / starPulse / starDrift 动画，但整体亮度略微提高

---

## 3. 蝴蝶效果

当前问题：用两个 CSS `div` + `borderRadius` 拼出来的蝴蝶形状看起来像屁股（棠棠原话）。

改动要求：
- 改用 **inline SVG** 绘制蝴蝶，翅膀要有真实的弧线和尖端轮廓
- SVG 翅膀用半透明渐变填充（`hsla` 紫/粉色系），加 `filter: drop-shadow` 做发光效果
- 扇翅动画保留，改为对 SVG 的左右翅膀分别做 `rotateY` 变换
- 数量保持 3~4 只，飞行轨迹保持从左到右的缓慢飘移

SVG 蝴蝶参考结构：
```jsx
<svg viewBox="0 0 40 28" style={{width: sz, height: sz*0.7}}>
  {/* 左翅 */}
  <path d="M20,14 Q8,2 2,8 Q0,14 8,18 Q14,20 20,14Z"
    fill="url(#wingGradL)" opacity="0.6"
    style={{transformOrigin:'20px 14px', animation:'wingLeft 0.4s ease-in-out infinite alternate'}} />
  {/* 右翅 */}
  <path d="M20,14 Q32,2 38,8 Q40,14 32,18 Q26,20 20,14Z"
    fill="url(#wingGradR)" opacity="0.6"
    style={{transformOrigin:'20px 14px', animation:'wingRight 0.4s ease-in-out infinite alternate'}} />
  <defs>
    <linearGradient id="wingGradL" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stopColor="hsla(280,70%,75%,0.7)" />
      <stop offset="100%" stopColor="hsla(300,60%,65%,0.3)" />
    </linearGradient>
    <linearGradient id="wingGradR" x1="1" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="hsla(280,70%,75%,0.7)" />
      <stop offset="100%" stopColor="hsla(300,60%,65%,0.3)" />
    </linearGradient>
  </defs>
</svg>
```

---

## 4. 快捷图标区

当前问题：用 emoji 做图标 + 中文标签，看起来太甜跟深色星空不搭。

改动要求：
- emoji 换成 **线条风格的 Unicode 符号或 Lucide React 图标**（如果项目已有 lucide-react 依赖就用它，没有就用 Unicode 细线符号）
- 中文标签换英文

替换对照表：

| 原来 | 新图标（Lucide建议） | 新标签 |
|------|---------------------|--------|
| 🎞 记忆库 | `<Film />` 或 ✦ | Memory |
| 💌 信封 | `<Mail />` 或 ✉ | Letters |
| 💫 珍藏 | `<Star />` 或 ✧ | Treasured |
| ⚓ 锚点 | `<Anchor />` 或 ⚓ | Anchor |
| 🌊 潮汐 | `<Waves />` 或 ≋ | Tidal |

- 图标颜色：未选中 `rgba(160,140,200,0.5)`，选中 `rgba(220,200,255,1)` + glow
- 标签字体：**Quicksand**

---

## 5. 快捷图标点击交互

当前问题：首页中间那排五个快捷图标（Memory / Letters / Treasured / Anchor / Tidal）点击无反应。

改动要求：
- 绑定 `onClick` 事件切换 tab：
  - Memory → `setTab("memory")`
  - Letters → 打开信封弹窗 `setEnv(true)`
  - Treasured → `setTab("memory")` 并设筛选为 "珍藏"
  - Anchor → `setTab("memory")` 并设筛选为 "锚点"（需要新增 Anchor 子视图或复用 MemoryView 加 filter）
  - Tidal → `setTab("tidal")`
- 点击时加一个短暂的 `scale(0.95)` → `scale(1)` 的弹跳反馈

---

## 6. 选中交互动效

当前状态：v5 已经在导航栏做了选中放大（17px→22px）和发光，但效果可以更统一。

确认保持并加强以下交互：
- **底部导航栏**：选中 tab 的 icon 放大（17→22px），文字放大（9→10px），颜色变亮，加 `text-shadow` 发光，加 `scale(1.12)` — 已实现，保持
- **记忆库筛选按钮**：选中时 `scale(1.05)`、边框变亮、背景渐变、`box-shadow` 发光 — 已实现，保持
- **快捷图标**：点击时所选图标也要有发光 + 短暂放大效果

---

## 7. 颜色方向

保持 v5 的深色星空方向，不改动。关键色值确认：
- 背景：深紫蓝黑渐变 `#0a0515` → `#120828` → `#1a0c35`
- 卡片：`rgba(20,12,35,0.5)` 半透明毛玻璃
- 发光边框：`rgba(180,120,240,0.35)`
- 文字主色：`rgba(220,200,255,0.9)`
- 文字副色：`rgba(160,140,200,0.5~0.7)`
- 强调渐变：蓝紫粉银河渐变 `#b080e0 → #e080b0 → #80b0e0`

---

## 注意事项

- 所有改动基于现有 v5 的 JSX 文件结构，不改变数据结构（MEMORIES / DIARIES / LOGS / ANCHORS 等保持不变）
- React 单文件组件，不拆分 CSS 文件
- 保持移动端优先（`maxWidth: 430px`）
