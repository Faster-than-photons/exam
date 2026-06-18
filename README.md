# 刷题与考试系统

基于 Python Tkinter 的 GUI 刷题与考试程序，支持单选/多选/填空、多题库管理、错题本、考试模式、统计图表。

## 快速开始

```bash
python main.py
```

> 零外部依赖，Python 3.7+ 自带 Tkinter。

---

## 工程架构 (v3.0.0)

```
exam/
├── main.py                  # 程序入口（仅 40 行）
├── code/                    # 核心代码模块
│   ├── __init__.py
│   ├── models.py            # 数据模型 (~800 行)
│   │   ├── Question (ABC)   # 题目基类
│   │   ├── SingleChoiceQuestion
│   │   ├── MultiChoiceQuestion
│   │   ├── FillInBlankQuestion
│   │   ├── QuestionBank     # 题库逻辑（加载/保存/增删改查/错题本）
│   │   ├── BankManager      # 多题库管理器
│   │   └── AppConfig        # 全局配置 (config.json)
│   ├── utils.py             # 工具函数
│   │   └── center_window()
│   ├── ui_main.py           # 主窗口 MainApp (~350 行)
│   │   └── 侧边栏 + 内容区面板切换
│   ├── ui_panels.py         # 嵌入式面板 (~800 行)
│   │   ├── PracticeChoicePanel  # 刷题选择 + 设置
│   │   ├── BankHubPanel         # 题库管理中心
│   │   ├── StatisticsPanel      # 统计图表
│   │   ├── SettingsPanel        # 偏好设置
│   │   └── WrongBookPanel       # 错题本
│   ├── ui_practice.py       # 刷题窗口 (~450 行)
│   │   └── PracticeWindow   # 全屏刷题 + 键盘快捷键
│   ├── ui_exam.py           # 考试模块 (~650 行)
│   │   ├── ExamSetupWindow  # 考试设置
│   │   ├── ExamWindow       # 限时考试 + 防作弊
│   │   └── ResultWindow     # 成绩报告 + 逐题详情
│   └── ui_dialogs.py        # 对话框集合 (~1100 行)
│       ├── BankManagementWindow  # 题库管理
│       ├── BankSwitchWindow      # 题库切换
│       ├── ImportWindow          # TXT 导入
│       ├── ExportWindow          # TXT 导出
│       ├── QuestionEditWindow    # 题目编辑
│       └── StatisticsWindow      # 统计（Toplevel 版）
├── banks/                   # 题库数据目录
│   ├── index.json           # 题库注册表
│   ├── <题库名>.json        # 题库数据
│   ├── <题库名>_history.json # 考试历史
│   └── <题库名>_wrong.json  # 错题本
├── config.json              # 用户偏好
├── CHANGELOG.md             # 版本日志
└── README.md                # 本文件
```

---

## 核心类关系

```
Question (ABC)
├── SingleChoiceQuestion
├── MultiChoiceQuestion
└── FillInBlankQuestion

QuestionBank              ← 题库 CRUD + 错题本 + TXT 解析
BankManager               ← 多题库管理（代理模式）
AppConfig                 ← config.json 读写

MainApp                   ← 主窗口（侧边栏 + 内容面板切换）
├── PracticeChoicePanel   ← 刷题入口 + 设置
├── BankHubPanel          ← 题库管理（合并面板）
├── StatisticsPanel       ← 统计图表
├── WrongBookPanel        ← 错题本面板
├── PracticeWindow        ← 全屏刷题（Toplevel）
├── ExamWindow            ← 考试窗口（Toplevel）
└── (dialogs)             ← 其余弹窗类
```

---

## 数据流

```
用户操作 → UI 面板 → BankManager → QuestionBank → JSON 文件
                                          ↓
                                    错题本 (_wrong.json)
                                    历史记录 (_history.json)
                                    刷题进度 (_progress.json)
```

---

## 快捷键总览

### 主窗口
| 快捷键 | 功能 |
|--------|------|
| `Ctrl+1` | 刷题模式 |
| `Ctrl+2` | 考试模式 |
| `Ctrl+3` | 错题本 |
| `Ctrl+4` | 题库管理 |
| `Ctrl+5` | 统计 |
| `Ctrl+6` | 退出 |
| `Ctrl+W` | 返回默认面板 |

### 刷题窗口
| 快捷键 | 功能 |
|--------|------|
| `←` `→` | 切换题目 |
| `A`~`H` / `1`~`8` | 选择选项 |
| `空格` / `回车` | 提交答案 |
| 答对自动跳下一题 | 答错停留，显示正确答案 |

---

## TXT 题库格式

```
1.(单选题)题目内容
A. 选项1
B. 选项2
答案: B

2.(多选题)题目内容
A. 选项1
B. 选项2
C. 选项3
答案: AB

3.(填空题)题目内容包含 {1} 和 {2}
空1: 答案1,答案2
空2: 答案1
```

- 题与题之间用空行分隔
- 空格宽容（`1 . ( 单选题 ) 题目` 也能解析）
- 答案行使用中文 `答案:`（中英文冒号均可）

---

## 版本

当前: **v3.0.0** — 代码模块化重构

详见 [CHANGELOG.md](CHANGELOG.md)
