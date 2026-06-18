# 发行日志 (Changelog)

本文档记录「GUI 刷题与考试程序」的所有版本变更与开发记录。

---

## [v2.0.4] - 2026-06-18

### 🐛 修复
- **按钮不随窗口缩放**：将 `place()` 布局改为纯 `pack()` 布局
  - 移除 `_btn_anchor.place(relx=0.5, rely=0.5)` 居中锚定（该方式不响应父容器尺寸变化）
  - 改用 `_btn_frame.pack(expand=True)` + `pack_configure(fill="x"/"none")` 动态切换
  - 紧凑模式：`fill="none"` 按钮保持固定宽度居中
  - 大型模式：`fill="x"` + `padx=30` 按钮撑满窗口宽度
- **清理残留代码**：移除旧 `_apply_large` 方法残留片段，消除重复方法定义

---

## [v2.0.3] - 2026-06-18

### ✨ 改进
- **主窗口自适应双布局**：
  - **紧凑布局**（窗口面积 < 屏幕 1/3）：小字体(14pt)、窄间距(pady=2)、固定按钮宽度(22字符)，适合小窗使用
  - **大型布局**（窗口面积 ≥ 屏幕 1/3）：大字体(20pt)、宽间距(pady=5)、按钮自动撑满宽度，适合最大化/大屏使用
  - 窗口缩放时自动切换，无需手动操作
- **去除底部多余留白**：按钮组居中锚定，不再有大量空白区域
- **降低最小窗口尺寸**：480×400 更紧凑

---

## [v2.0.2] - 2026-06-18

### 🐛 修复
- **类型检查报错**（Pylance/Pyright）：共修复 78 个类型错误
  - 移除 `**btn_config` 字典解包模式，改为显式 `width=25` 参数传递，解决 `int` 类型无法匹配 `ttk.Button` 各参数的问题
  - 修复 `dict[int, any]` 中未导入的 `any` 类型 → 改为 `dict[int, object]`
  - 添加 `assert self.question is not None` 守卫，消除 `Question | None` 类型访问属性报错
  - 添加 `assert self.index is not None` 守卫，消除 `int | None` 作为索引的报错
  - 添加 `else: raise ValueError` 分支，消除 `q` 可能未绑定的报错

---

## [v2.0.1] - 2026-06-18

### 🐛 修复
- **主窗口显示不全**：增大主窗口默认高度（420 → 520），设置最小窗口尺寸（450×480），压缩标题区和按钮区间距，确保"查看统计"和"退出程序"按钮不被遮挡

---

## [v2.0.0] - 2026-06-18

### 🎨 重大重构：命令行 → GUI（Tkinter）

#### 新增功能
- **GUI 界面**：使用 Tkinter 构建完整的图形界面，替代原命令行交互
  - 主窗口菜单，通过按钮进入各功能模块
  - 所有交互通过窗口控件完成（按钮、标签、文本框、Treeview 等）
- **考试模式**：
  - 考试设置窗口：选择题量、考试时长
  - 限时倒计时显示（分钟:秒），时间到自动提交试卷
  - 禁看答案，隐藏"显示答案"功能
  - 底部题号快捷跳转按钮，已答/未答状态区分
  - 支持提前提交试卷
- **成绩历史记录**：
  - 每次考试自动保存记录到 `history.json`
  - 统计窗口显示历史考试列表（日期、题量、正确数、正确率、用时）
  - 计算历史平均正确率
- **题库管理 GUI**：
  - Treeview 列表展示所有题目（序号、题型、预览）
  - 实时搜索过滤
  - 双击编辑题目
  - 弹出式添加/编辑窗口，支持动态切换题型输入框
- **刷题模式**：
  - 单选用 Radiobutton，多选用 Checkbutton，填空用 Entry
  - 提交答案按钮 + 显示/隐藏答案按钮
  - 上一题/下一题导航

#### 变更
- **移除依赖**：不再依赖 `keyboard` 第三方库，全部使用 Python 标准库
- **架构重构**：
  - 新增 `MainApp` 类（主窗口）
  - 新增 `PracticeWindow` 类（刷题窗口）
  - 新增 `ExamSetupWindow` 类（考试设置）
  - 新增 `ExamWindow` 类（考试窗口）
  - 新增 `ResultWindow` 类（成绩窗口）
  - 新增 `BankManagementWindow` 类（题库管理窗口）
  - 新增 `QuestionEditWindow` 类（题目编辑弹窗）
  - 新增 `ImportWindow` / `ExportWindow` 类（导入导出）
  - 新增 `StatisticsWindow` 类（统计窗口）
  - 保留 `Question`(ABC) / `SingleChoiceQuestion` / `MultiChoiceQuestion` / `FillInBlankQuestion` 数据模型
  - `QuestionBank` 类增加 `history` 历史记录支持
- **文件变更**：
  - `questions.json` — 题库数据（格式不变）
  - `history.json` — 新增，考试历史记录
  - `requirements.txt` — 清空（零依赖）

---

## [v1.0.0] - 2026-06-18

### 🎉 首次发布

#### 新增功能
- **三种题型支持**：单选题、多选题、填空题（含多空、多答案匹配）
- **题库管理**：支持题目的显示、添加、删除、修改、关键词搜索
- **JSON 持久化**：题库以 JSON 格式自动保存/加载（`questions.json`）
- **TXT 导入**：支持从 TXT 文件导入或直接粘贴文本，按规范格式解析
- **TXT 导出**：将当前题库按规范格式导出为 TXT 文件
- **交互式刷题**：
  - 随机打乱题目顺序，每次显示一道
  - 支持键盘 ← → 切换题目（需 `keyboard` 库）
  - 无 `keyboard` 库时自动降级为输入指令模式（n/p 切换）
  - H 键显示/隐藏正确答案
  - Q 键退出刷题并查看统计报告
- **统计功能**：题库总览统计 + 刷题成绩报告（正确率、各题型正确率）
- **依赖检查**：启动时检测 `keyboard` 库可用性，缺失时给出安装提示

#### 技术架构
- 面向对象设计：`Question`(ABC) / `SingleChoiceQuestion` / `MultiChoiceQuestion` / `FillInBlankQuestion`
- 题库管理：`QuestionBank` 类
- 刷题引擎：`ExamEngine` 类
- 纯 Python 标准库 + 可选 `keyboard` 第三方库

#### 文件清单
| 文件 | 说明 |
|------|------|
| `main.py` | 主程序（GUI 版，约 700 行） |
| `requirements.txt` | Python 依赖声明（零依赖，仅标准库） |
| `CHANGELOG.md` | 发行日志（本文件） |
| `questions.json` | 题库数据（自动生成） |
| `history.json` | 考试历史记录（自动生成） |

---

> 格式参考：[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)
