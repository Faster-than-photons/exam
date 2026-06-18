#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 GUI 刷题与考试程序 (Tkinter-based Quiz & Exam Program)
===============================================================================

 功能概述:
   - 支持单选题、多选题、填空题（含多空、多答案匹配）
   - 题库管理：增、删、改、查（GUI 界面）
   - 导入/导出 TXT 格式题库
   - 刷题模式（练习，可查看答案）
   - 考试模式（限时、禁看答案、自动提交）
   - 成绩历史记录与统计

 使用方法:
   直接运行: python main.py
   （无需安装第三方库，Tkinter 为 Python 标准库）

 环境依赖:
   - Python 3.7+（自带 Tkinter）
   - 无需第三方包

 作者: AI Assistant
 日期: 2026-06-18
===============================================================================
"""

import json
import os
import random
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from abc import ABC, abstractmethod
from datetime import datetime


# ============================================================================
# 题型类定义（与 JSON 数据格式对应）
# ============================================================================

class Question(ABC):
    """题目基类 —— 所有题型的抽象父类。预留接口，便于扩展新题型。"""

    def __init__(self, qtype: str, question: str):
        self.qtype = qtype
        self.question = question

    @abstractmethod
    def get_answer_display(self) -> str:
        """返回答案的字符串表示。"""
        pass

    @abstractmethod
    def check_answer(self, user_input) -> bool:
        """判断用户输入是否正确。"""
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        """序列化为字典。"""
        pass

    @staticmethod
    def from_dict(data: dict) -> "Question":
        """工厂方法：从字典反序列化。"""
        qtype = data.get("type", "")
        if qtype == "single":
            return SingleChoiceQuestion(
                data["question"], data.get("options", []), data.get("answer", ""))
        elif qtype == "multi":
            return MultiChoiceQuestion(
                data["question"], data.get("options", []), data.get("answer", []))
        elif qtype == "fill":
            return FillInBlankQuestion(
                data["question"], data.get("blanks", []))
        else:
            raise ValueError(f"未知题型: {qtype}")

    @abstractmethod
    def get_short_info(self) -> str:
        """简短摘要（用于列表显示）。"""
        pass


class SingleChoiceQuestion(Question):
    """单选题"""

    def __init__(self, question: str, options: list, answer: str):
        super().__init__("single", question)
        self.options = options
        self.answer = answer.strip().upper()

    def get_answer_display(self) -> str:
        return self.answer

    def check_answer(self, user_input) -> bool:
        if isinstance(user_input, str):
            return user_input.strip().upper() == self.answer
        return False

    def to_dict(self) -> dict:
        return {"type": "single", "question": self.question,
                "options": self.options, "answer": self.answer}

    def get_short_info(self) -> str:
        preview = self.question[:25] + ("..." if len(self.question) > 25 else "")
        return f"[单选] {preview}"


class MultiChoiceQuestion(Question):
    """多选题 —— 全部选对才得分。"""

    def __init__(self, question: str, options: list, answer: list):
        super().__init__("multi", question)
        self.options = options
        self.answer = sorted([a.strip().upper() for a in answer])

    def get_answer_display(self) -> str:
        return ",".join(self.answer)

    def check_answer(self, user_input) -> bool:
        """user_input 为排序后的大写字母列表，如 ['A','B','D']"""
        if isinstance(user_input, list):
            return sorted([str(x).strip().upper() for x in user_input]) == self.answer
        if isinstance(user_input, str):
            raw = user_input.strip().upper()
            if "," in raw:
                parts = sorted([a.strip() for a in raw.split(",") if a.strip()])
            else:
                parts = sorted([ch for ch in raw if ch.isalpha()])
            return parts == self.answer
        return False

    def to_dict(self) -> dict:
        return {"type": "multi", "question": self.question,
                "options": self.options, "answer": self.answer}

    def get_short_info(self) -> str:
        preview = self.question[:25] + ("..." if len(self.question) > 25 else "")
        return f"[多选] {preview}"


class FillInBlankQuestion(Question):
    """填空题 —— 支持多空，每空多答案匹配。"""

    def __init__(self, question: str, blanks: list):
        super().__init__("fill", question)
        self.blanks = blanks  # [{"answers": [...]}, ...]

    def get_answer_display(self) -> str:
        parts = []
        for i, b in enumerate(self.blanks):
            parts.append(f"空{i}: {'/'.join(b['answers'])}")
        return " | ".join(parts)

    def check_answer(self, user_input) -> bool:
        """user_input 为字符串列表，每个元素对应一个空的答案。"""
        if isinstance(user_input, list):
            answers = [str(a).strip() for a in user_input]
        elif isinstance(user_input, str):
            answers = [a.strip() for a in user_input.split(",")]
        else:
            return False
        if len(answers) != len(self.blanks):
            return False
        for i, blank in enumerate(self.blanks):
            if answers[i] not in blank["answers"]:
                return False
        return True

    def to_dict(self) -> dict:
        return {"type": "fill", "question": self.question, "blanks": self.blanks}

    def get_short_info(self) -> str:
        preview = self.question[:25] + ("..." if len(self.question) > 25 else "")
        return f"[填空] {preview}"


# ============================================================================
# 题库管理类（含历史记录）
# ============================================================================

class QuestionBank:
    """题库管理 —— JSON 持久化、增删改查、导入导出、历史成绩。"""

    def __init__(self, filepath: str = "questions.json",
                 history_path: str = "history.json"):
        self.filepath = filepath
        self.history_path = history_path
        self.questions: list[Question] = []
        self.history: list[dict] = []  # 考试历史记录
        self.load()
        self.load_history()

    # ---------- JSON 持久化 ----------

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.questions = [Question.from_dict(item) for item in data]
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                messagebox.showwarning("题库加载", f"题库文件解析失败: {e}\n将使用空题库。")
                self.questions = []
        else:
            self.questions = []

    def save(self):
        data = [q.to_dict() for q in self.questions]
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---------- 历史记录 ----------

    def load_history(self):
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except (json.JSONDecodeError, ValueError):
                self.history = []

    def save_history(self):
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def add_history(self, record: dict):
        """添加一条考试记录。"""
        self.history.append(record)
        self.save_history()

    # ---------- TXT 解析与生成 ----------

    @staticmethod
    def parse_txt(text: str) -> list:
        """解析 TXT 格式题目文本，返回 Question 列表。"""
        questions = []
        blocks = re.split(r"\n\s*\n", text.strip())
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            first_line = lines[0]
            type_match = re.match(r"^\d+\.\((单选题|多选题|填空题)\)(.+)$", first_line)
            if not type_match:
                continue

            qtype_cn = type_match.group(1)
            question_text = type_match.group(2).strip()

            if qtype_cn == "单选题":
                options, answer = [], ""
                for line in lines[1:]:
                    if line.lower().startswith("answer:"):
                        answer = line.split(":", 1)[1].strip().upper()
                    elif re.match(r"^[A-Z]\.", line):
                        options.append(line)
                if question_text and options and answer:
                    questions.append(SingleChoiceQuestion(question_text, options, answer))

            elif qtype_cn == "多选题":
                options, answer = [], []
                for line in lines[1:]:
                    if line.lower().startswith("answer:"):
                        raw = line.split(":", 1)[1].strip()
                        answer = [a.strip().upper() for a in raw.split(",") if a.strip()]
                    elif re.match(r"^[A-Z]\.", line):
                        options.append(line)
                if question_text and options and answer:
                    questions.append(MultiChoiceQuestion(question_text, options, answer))

            elif qtype_cn == "填空题":
                blank_dict = {}
                for line in lines[1:]:
                    m = re.match(r"^blank(\d+):\s*(.+)$", line, re.IGNORECASE)
                    if m:
                        idx = int(m.group(1))
                        raw = m.group(2).strip()
                        blank_dict[idx] = [a.strip() for a in raw.split(",") if a.strip()]
                blanks = [{"answers": blank_dict[k]} for k in sorted(blank_dict.keys())]
                if question_text and blanks:
                    questions.append(FillInBlankQuestion(question_text, blanks))

        return questions

    @staticmethod
    def export_txt_str(questions: list) -> str:
        """将题目列表导出为 TXT 格式字符串。"""
        lines = []
        for i, q in enumerate(questions):
            if isinstance(q, SingleChoiceQuestion):
                lines.append(f"{i+1}.(单选题){q.question}")
                for opt in q.options:
                    lines.append(opt)
                lines.append(f"answer: {q.answer}")
            elif isinstance(q, MultiChoiceQuestion):
                lines.append(f"{i+1}.(多选题){q.question}")
                for opt in q.options:
                    lines.append(opt)
                lines.append(f"answer: {','.join(q.answer)}")
            elif isinstance(q, FillInBlankQuestion):
                lines.append(f"{i+1}.(填空题){q.question}")
                for j, blank in enumerate(q.blanks):
                    lines.append(f"blank{j}: {','.join(blank['answers'])}")
            lines.append("")
        return "\n".join(lines)

    # ---------- 统计 ----------

    def get_statistics(self) -> dict:
        stats = {"total": len(self.questions), "single": 0, "multi": 0, "fill": 0}
        for q in self.questions:
            if q.qtype in stats:
                stats[q.qtype] += 1
        return stats


# ============================================================================
# 全局题库实例
# ============================================================================

bank = QuestionBank()


# ============================================================================
# 通用工具函数
# ============================================================================

def center_window(window, width, height):
    """将窗口居中显示。"""
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")


# ============================================================================
# 主窗口
# ============================================================================

class MainApp:
    """程序主窗口 —— 显示功能菜单，支持紧凑/大型双布局自适应。"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("刷题与考试系统")
        self.root.resizable(True, True)
        center_window(self.root, 520, 460)
        self.root.minsize(400, 380)
        self._layout_mode = None  # 当前布局模式: 'compact' / 'large'

        self._build_ui()
        self.root.update_idletasks()  # 确保初始尺寸就绪
        self._update_layout()
        self.root.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 界面构建 ----------

    def _build_ui(self):
        """构建主界面骨架。"""
        # 标题区
        self._title_frame = ttk.Frame(self.root)
        self._title_frame.pack(fill="x")

        self._title_label = ttk.Label(self._title_frame, text="📚 刷题与考试系统",
                                      font=("Microsoft YaHei", 18, "bold"))
        self._title_label.pack()

        stats = bank.get_statistics()
        self._stats_label = ttk.Label(
            self._title_frame,
            text=f"题库共 {stats['total']} 题（单选 {stats['single']} | 多选 {stats['multi']} | 填空 {stats['fill']}）",
            font=("Microsoft YaHei", 9))
        self._stats_label.pack(pady=(5, 0))

        # 分隔线
        self._sep = ttk.Separator(self.root, orient="horizontal")
        self._sep.pack(fill="x", padx=15, pady=(8, 0))

        # 按钮外层容器（占满剩余空间）
        self._outer_frame = ttk.Frame(self.root)
        self._outer_frame.pack(fill="both", expand=True)

        # 按钮内层框架（默认居中，large 时 fill="x"）
        self._btn_frame = ttk.Frame(self._outer_frame)
        self._btn_frame.pack(expand=True)

        # 创建所有按钮并保存引用
        self._buttons: list[ttk.Button] = []
        btn_defs = [
            ("📝 刷题模式（练习）", self._open_practice),
            ("⏱ 考试模式", self._open_exam_setup),
            ("📋 题库管理（增删改查）", self._open_bank_management),
            ("📥 导入题库（TXT）", self._open_import),
            ("📤 导出题库（TXT）", self._open_export),
            ("📊 查看统计", self._open_statistics),
            ("🚪 退出程序", self._on_close),
        ]
        for text, cmd in btn_defs:
            btn = ttk.Button(self._btn_frame, text=text, command=cmd)
            btn.pack(pady=2)
            self._buttons.append(btn)

    # ---------- 自适应布局 ----------

    def _on_resize(self, event=None):
        """窗口大小变化时检查并切换布局模式。"""
        if event and event.widget is not self.root:
            return
        self._update_layout()

    def _update_layout(self):
        """根据当前窗口尺寸选择并应用布局。"""
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        if w < 50 or h < 50:
            return

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        screen_area = screen_w * screen_h
        window_area = w * h
        threshold = screen_area / 3

        new_mode = "large" if window_area >= threshold else "compact"

        if new_mode != self._layout_mode:
            # 模式切换
            self._layout_mode = new_mode
            if new_mode == "compact":
                self._apply_compact()
            else:
                self._apply_large()
        elif new_mode == "large":
            # 大型模式内连续缩放：实时更新间距
            self._apply_large()

    def _apply_compact(self):
        """紧凑布局：小字体、间距=半按钮高、上下边距=一按钮高、无左右限制。"""
        btn_font = ("Microsoft YaHei", 9)
        btn_h = 24  # 紧凑模式按钮近似高度(px)
        pady_gap = max(1, btn_h // 4)
        margin_v = btn_h

        self._title_frame.configure(padding=(12, 8, 12, 2))
        self._title_label.configure(font=("Microsoft YaHei", 14, "bold"))
        self._stats_label.configure(font=("Microsoft YaHei", 8))

        self._btn_frame.pack_configure(fill="none", expand=True, padx=0, pady=margin_v)

        for btn in self._buttons:
            btn.configure(width=22)
            btn.pack_configure(pady=pady_gap, fill="none")

        self._apply_button_font(btn_font)

    def _apply_large(self):
        """大型布局：间距=半按钮高（动态计算）、左右边距=按钮宽/10。"""
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()

        # 可用垂直空间 ≈ 窗口高度 - 标题区(约60px) - 分隔线(约10px)
        avail_h = max(200, win_h - 70)

        # 7 按钮 + 6 间隙，间隙 = btn_h/2
        # avail_h = 7*btn_h + 6*(btn_h/2) = 10*btn_h → btn_h = avail_h / 10
        n_btns = len(self._buttons)
        n_gaps = n_btns - 1
        btn_h = avail_h / (n_btns + n_gaps * 0.5)
        gap = btn_h / 2
        pady_gap = max(1, int(gap / 2))  # pack pady 上下各一半
        margin_v = max(4, int(btn_h))     # 上下边距 = 一个按钮高

        # 左右边距 = 按钮宽度 / 10 → padx = win_w / 12
        padx_h = max(10, win_w // 12)

        btn_font = ("Microsoft YaHei", 11)
        self._title_frame.configure(padding=(padx_h, 15, padx_h, 8))
        self._title_label.configure(font=("Microsoft YaHei", 20, "bold"))
        self._stats_label.configure(font=("Microsoft YaHei", 10))

        self._btn_frame.pack_configure(fill="both", expand=True,
                                       padx=padx_h, pady=margin_v)

        for btn in self._buttons:
            btn.configure(width=0)
            btn.pack_configure(pady=pady_gap, fill="both", expand=True)

        self._apply_button_font(btn_font)

    def _apply_button_font(self, font):
        """通过 ttk.Style 设置按钮字体。"""
        style = ttk.Style()
        style.configure("Main.TButton", font=font)
        for btn in self._buttons:
            btn.configure(style="Main.TButton")

    # ---------- 各功能入口 ----------

    def _open_practice(self):
        if not bank.questions:
            messagebox.showinfo("提示", "题库为空，请先导入或添加题目！")
            return
        self.root.withdraw()
        PracticeWindow(self.root, bank.questions)

    def _open_exam_setup(self):
        if not bank.questions:
            messagebox.showinfo("提示", "题库为空，请先导入或添加题目！")
            return
        self.root.withdraw()
        ExamSetupWindow(self.root)

    def _open_bank_management(self):
        self.root.withdraw()
        BankManagementWindow(self.root)

    def _open_import(self):
        ImportWindow(self.root)

    def _open_export(self):
        if not bank.questions:
            messagebox.showinfo("提示", "题库为空，无法导出！")
            return
        ExportWindow(self.root)

    def _open_statistics(self):
        StatisticsWindow(self.root)

    def _on_close(self):
        bank.save()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ============================================================================
# 刷题模式（练习）窗口
# ============================================================================

class PracticeWindow:
    """刷题练习窗口 —— 随机出题，可查看答案。"""

    def __init__(self, parent, questions: list):
        self.parent = parent
        self.questions = questions
        self.shuffled = list(range(len(questions)))
        random.shuffle(self.shuffled)
        self.current_idx = 0
        self.records: dict[int, bool] = {}  # shuffled_pos -> is_correct
        self.show_answer_flag = tk.BooleanVar(value=False)

        self.window = tk.Toplevel(parent)
        self.window.title("刷题模式（练习）")
        self.window.resizable(True, True)
        center_window(self.window, 650, 550)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._display_question()

    def _build_ui(self):
        # 顶部：进度与按钮
        top_frame = ttk.Frame(self.window, padding=10)
        top_frame.pack(fill="x")

        self.progress_label = ttk.Label(top_frame, text="",
                                        font=("Microsoft YaHei", 10))
        self.progress_label.pack(side="left", padx=5)

        self.answered_label = ttk.Label(top_frame, text="",
                                        font=("Microsoft YaHei", 9),
                                        foreground="gray")
        self.answered_label.pack(side="left", padx=15)

        ttk.Button(top_frame, text="显示/隐藏答案",
                   command=self._toggle_answer).pack(side="right", padx=5)
        ttk.Button(top_frame, text="返回主菜单",
                   command=self._on_close).pack(side="right", padx=5)

        # 分隔线
        ttk.Separator(self.window, orient="horizontal").pack(fill="x", padx=10)

        # 题目显示区
        self.question_frame = ttk.Frame(self.window, padding=15)
        self.question_frame.pack(fill="both", expand=True)

        self.type_label = ttk.Label(self.question_frame, text="",
                                    font=("Microsoft YaHei", 11, "bold"))
        self.type_label.pack(anchor="w", pady=(0, 5))

        self.question_label = ttk.Label(self.question_frame, text="",
                                        font=("Microsoft YaHei", 12),
                                        wraplength=580, justify="left")
        self.question_label.pack(anchor="w", pady=(0, 10))

        # 选项/填空区域（动态变化）
        self.answer_frame = ttk.Frame(self.question_frame)
        self.answer_frame.pack(fill="both", expand=True)

        # 正确答案显示
        self.correct_answer_label = ttk.Label(self.question_frame, text="",
                                              font=("Microsoft YaHei", 10),
                                              foreground="green")
        self.correct_answer_label.pack(anchor="w", pady=(10, 0))

        # 答题结果提示
        self.result_label = ttk.Label(self.question_frame, text="",
                                      font=("Microsoft YaHei", 10, "bold"))
        self.result_label.pack(anchor="w", pady=(5, 0))

        # 底部：导航与提交
        bottom_frame = ttk.Frame(self.window, padding=10)
        bottom_frame.pack(fill="x", side="bottom")

        ttk.Button(bottom_frame, text="◀ 上一题",
                   command=self._prev).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="下一题 ▶",
                   command=self._next).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="提交答案",
                   command=self._submit).pack(side="right", padx=5)

    def _display_question(self):
        """渲染当前题目。"""
        # 清除旧控件
        for w in self.answer_frame.winfo_children():
            w.destroy()

        total = len(self.shuffled)
        current_display = self.current_idx + 1
        answered = len(self.records)
        self.progress_label.config(text=f"第 {current_display}/{total} 题")
        self.answered_label.config(text=f"已答: {answered} 题")

        q = self._current_question()
        type_cn = {"single": "单选题", "multi": "多选题", "fill": "填空题"}
        self.type_label.config(text=f"【{type_cn.get(q.qtype, q.qtype)}】")
        self.question_label.config(text=q.question)

        # 渲染选项/填空控件
        if isinstance(q, SingleChoiceQuestion):
            self._var = tk.StringVar(value="")
            for opt in q.options:
                ttk.Radiobutton(self.answer_frame, text=opt,
                                variable=self._var,
                                value=opt.split(".")[0].strip().upper()
                                ).pack(anchor="w", pady=3)

        elif isinstance(q, MultiChoiceQuestion):
            self._check_vars = {}
            for opt in q.options:
                key = opt.split(".")[0].strip().upper()
                var = tk.BooleanVar(value=False)
                self._check_vars[key] = var
                ttk.Checkbutton(self.answer_frame, text=opt,
                                variable=var).pack(anchor="w", pady=3)

        elif isinstance(q, FillInBlankQuestion):
            self._entry_vars = []
            for i in range(len(q.blanks)):
                lbl = ttk.Label(self.answer_frame, text=f"空{i}：")
                lbl.pack(anchor="w", pady=(5, 0))
                var = tk.StringVar()
                ttk.Entry(self.answer_frame, textvariable=var,
                          width=40).pack(anchor="w", pady=(0, 5))
                self._entry_vars.append(var)

        # 正确答案
        if self.show_answer_flag.get():
            self.correct_answer_label.config(
                text=f"★ 正确答案: {q.get_answer_display()}")
        else:
            self.correct_answer_label.config(text="")

        # 答题结果
        real_idx = self.shuffled[self.current_idx]
        if real_idx in self.records:
            status = "✓ 回答正确" if self.records[real_idx] else "✗ 回答错误"
            color = "green" if self.records[real_idx] else "red"
            self.result_label.config(text=status, foreground=color)
        else:
            self.result_label.config(text="")

    def _current_question(self) -> Question:
        return self.questions[self.shuffled[self.current_idx]]

    def _get_user_answer(self):
        """从控件中提取用户答案。"""
        q = self._current_question()
        if isinstance(q, SingleChoiceQuestion):
            return self._var.get()
        elif isinstance(q, MultiChoiceQuestion):
            return sorted([k for k, v in self._check_vars.items() if v.get()])
        elif isinstance(q, FillInBlankQuestion):
            return [v.get() for v in self._entry_vars]
        return None

    def _submit(self):
        q = self._current_question()
        real_idx = self.shuffled[self.current_idx]
        user_ans = self._get_user_answer()
        is_correct = q.check_answer(user_ans)
        self.records[real_idx] = is_correct

        if is_correct:
            self.result_label.config(text="✓ 回答正确！", foreground="green")
        else:
            self.result_label.config(
                text=f"✗ 回答错误！正确答案: {q.get_answer_display()}",
                foreground="red")

    def _next(self):
        if self.current_idx < len(self.shuffled) - 1:
            self.current_idx += 1
            self._display_question()
        else:
            messagebox.showinfo("提示", "已是最后一题。")
        self._check_all_done()

    def _prev(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._display_question()
        else:
            messagebox.showinfo("提示", "已是第一题。")

    def _toggle_answer(self):
        self.show_answer_flag.set(not self.show_answer_flag.get())
        self._display_question()

    def _check_all_done(self):
        if len(self.records) >= len(self.shuffled):
            self._show_result()

    def _show_result(self):
        total = len(self.shuffled)
        answered = len(self.records)
        correct = sum(1 for v in self.records.values() if v)
        ResultWindow(self.window, "练习成绩", total, answered, correct,
                     self.questions, self.shuffled, self.records)

    def _on_close(self):
        self.window.destroy()
        self.parent.deiconify()


# ============================================================================
# 考试设置窗口
# ============================================================================

class ExamSetupWindow:
    """考试设置窗口 —— 选择题量、时长。"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("考试设置")
        self.window.resizable(False, False)
        center_window(self.window, 400, 280)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="⏱ 考试设置",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 15))

        total = len(bank.questions)
        ttk.Label(frame, text=f"题库总题数: {total}",
                  font=("Microsoft YaHei", 10)).pack(anchor="w")

        # 题量设置
        row1 = ttk.Frame(frame)
        row1.pack(fill="x", pady=(10, 5))
        ttk.Label(row1, text="试卷题量:", width=12).pack(side="left")
        self.count_var = tk.IntVar(value=min(total, 10))
        ttk.Spinbox(row1, from_=1, to=total, textvariable=self.count_var,
                     width=10).pack(side="left", padx=5)
        ttk.Label(row1, text="题", font=("Microsoft YaHei", 9)).pack(side="left")

        # 时长设置
        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(5, 15))
        ttk.Label(row2, text="考试时长:", width=12).pack(side="left")
        self.time_var = tk.IntVar(value=30)
        ttk.Spinbox(row2, from_=1, to=180, textvariable=self.time_var,
                     width=10).pack(side="left", padx=5)
        ttk.Label(row2, text="分钟", font=("Microsoft YaHei", 9)).pack(side="left")

        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_frame, text="开始考试",
                   command=self._start_exam).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="返回",
                   command=self._on_close).pack(side="right", padx=5)

    def _start_exam(self):
        count = self.count_var.get()
        total = len(bank.questions)
        if count > total:
            messagebox.showwarning("警告", f"题库仅 {total} 题，无法抽取 {count} 题！")
            return
        exam_time = self.time_var.get()
        selected = random.sample(list(range(total)), count)
        self.window.destroy()
        ExamWindow(self.parent, selected, exam_time)

    def _on_close(self):
        self.window.destroy()
        self.parent.deiconify()


# ============================================================================
# 考试窗口
# ============================================================================

class ExamWindow:
    """考试窗口 —— 限时、禁看答案。"""

    def __init__(self, parent, question_indices: list, total_minutes: int):
        self.parent = parent
        self.question_indices = question_indices
        self.total_seconds = total_minutes * 60
        self.remaining_seconds = self.total_seconds
        self.current_idx = 0
        self.answers: dict[int, object] = {}  # index_in_indices -> user answer
        self._timer_id = None
        self._submitted = False

        self.window = tk.Toplevel(parent)
        self.window.title("考试模式")
        self.window.resizable(True, True)
        try:
            self.window.state("zoomed")
        except Exception:
            center_window(self.window, 750, 600)
        self.window.protocol("WM_DELETE_WINDOW", lambda: messagebox.showinfo(
            "提示", "考试进行中，请提交试卷后再退出。"))
        self.window.focus_force()

        # 绑定窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self._on_force_close)

        self._build_ui()
        self._display_question()
        self._start_timer()

    def _build_ui(self):
        # 顶部：倒计时 + 题号
        top_frame = ttk.Frame(self.window, padding=10)
        top_frame.pack(fill="x")

        self.timer_label = ttk.Label(top_frame, text="",
                                     font=("Microsoft YaHei", 16, "bold"),
                                     foreground="red")
        self.timer_label.pack(side="left", padx=10)

        self.progress_label = ttk.Label(top_frame, text="",
                                        font=("Microsoft YaHei", 11))
        self.progress_label.pack(side="left", padx=20)

        ttk.Button(top_frame, text="提交试卷",
                   command=self._submit_exam).pack(side="right", padx=10)

        ttk.Separator(self.window, orient="horizontal").pack(fill="x", padx=10)

        # 题目显示区
        self.question_frame = ttk.Frame(self.window, padding=15)
        self.question_frame.pack(fill="both", expand=True)

        self.type_label = ttk.Label(self.question_frame, text="",
                                    font=("Microsoft YaHei", 11, "bold"))
        self.type_label.pack(anchor="w", pady=(0, 5))

        self.question_label = ttk.Label(self.question_frame, text="",
                                        font=("Microsoft YaHei", 12),
                                        wraplength=700, justify="left")
        self.question_label.pack(anchor="w", pady=(0, 10))

        self.answer_frame = ttk.Frame(self.question_frame)
        self.answer_frame.pack(fill="both", expand=True)

        # 底部导航
        bottom_frame = ttk.Frame(self.window, padding=10)
        bottom_frame.pack(fill="x", side="bottom")
        ttk.Button(bottom_frame, text="◀ 上一题",
                   command=self._prev).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="下一题 ▶",
                   command=self._next).pack(side="left", padx=5)

        # 题号快捷跳转按钮
        self.jump_frame = ttk.Frame(bottom_frame)
        self.jump_frame.pack(side="right", padx=10)
        self._build_jump_buttons()

    def _build_jump_buttons(self):
        """构建题号跳转按钮。"""
        self.jump_buttons = []
        for i in range(len(self.question_indices)):
            btn = ttk.Button(self.jump_frame, text=str(i + 1), width=3,
                             command=lambda idx=i: self._jump_to(idx))
            btn.pack(side="left", padx=1)
            self.jump_buttons.append(btn)

    def _start_timer(self):
        self._update_timer()
        self._timer_id = self.window.after(1000, self._tick)

    def _tick(self):
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self._time_up()
        else:
            self._update_timer()
            self._timer_id = self.window.after(1000, self._tick)

    def _update_timer(self):
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        self.timer_label.config(text=f"⏱ {mins:02d}:{secs:02d}")

    def _time_up(self):
        if not self._submitted:
            self._submitted = True
            messagebox.showinfo("时间到", "考试时间已到，系统将自动提交试卷！")
            self._do_submit()

    def _on_force_close(self):
        """防止用户在考试中直接关闭窗口。"""
        if not self._submitted:
            messagebox.showinfo("提示", "考试进行中，请提交试卷后再退出。")
        else:
            self.window.destroy()
            self.parent.deiconify()

    def _display_question(self):
        for w in self.answer_frame.winfo_children():
            w.destroy()

        total = len(self.question_indices)
        self.progress_label.config(
            text=f"第 {self.current_idx + 1}/{total} 题")

        q = self._current_question()
        type_cn = {"single": "单选题", "multi": "多选题", "fill": "填空题"}
        self.type_label.config(text=f"【{type_cn.get(q.qtype, q.qtype)}】")
        self.question_label.config(text=q.question)

        # 恢复之前保存的答案
        prev_ans = self.answers.get(self.current_idx)

        if isinstance(q, SingleChoiceQuestion):
            default_val = prev_ans if isinstance(prev_ans, str) else ""
            self._var = tk.StringVar(value=default_val)
            for opt in q.options:
                ttk.Radiobutton(self.answer_frame, text=opt,
                                variable=self._var,
                                value=opt.split(".")[0].strip().upper()
                                ).pack(anchor="w", pady=3)

        elif isinstance(q, MultiChoiceQuestion):
            self._check_vars = {}
            prev_set = set(prev_ans) if isinstance(prev_ans, list) else set()
            for opt in q.options:
                key = opt.split(".")[0].strip().upper()
                var = tk.BooleanVar(value=(key in prev_set))
                self._check_vars[key] = var
                ttk.Checkbutton(self.answer_frame, text=opt,
                                variable=var).pack(anchor="w", pady=3)

        elif isinstance(q, FillInBlankQuestion):
            self._entry_vars = []
            if isinstance(prev_ans, list) and len(prev_ans) == len(q.blanks):
                defaults = prev_ans
            else:
                defaults = [""] * len(q.blanks)
            for i in range(len(q.blanks)):
                lbl = ttk.Label(self.answer_frame, text=f"空{i}：")
                lbl.pack(anchor="w", pady=(5, 0))
                var = tk.StringVar(value=defaults[i])
                ttk.Entry(self.answer_frame, textvariable=var,
                          width=40).pack(anchor="w", pady=(0, 5))
                self._entry_vars.append(var)

        self._update_jump_buttons()

    def _current_question(self) -> Question:
        return bank.questions[self.question_indices[self.current_idx]]

    def _save_current_answer(self):
        """保存当前题目的答案到 answers 字典。"""
        q = self._current_question()
        if isinstance(q, SingleChoiceQuestion):
            ans = self._var.get()
            if ans:
                self.answers[self.current_idx] = ans
        elif isinstance(q, MultiChoiceQuestion):
            selected = sorted(
                [k for k, v in self._check_vars.items() if v.get()])
            if selected:
                self.answers[self.current_idx] = selected
        elif isinstance(q, FillInBlankQuestion):
            vals = [v.get() for v in self._entry_vars]
            if any(vals):
                self.answers[self.current_idx] = vals

    def _next(self):
        self._save_current_answer()
        if self.current_idx < len(self.question_indices) - 1:
            self.current_idx += 1
            self._display_question()

    def _prev(self):
        self._save_current_answer()
        if self.current_idx > 0:
            self.current_idx -= 1
            self._display_question()

    def _jump_to(self, idx):
        self._save_current_answer()
        self.current_idx = idx
        self._display_question()

    def _update_jump_buttons(self):
        """更新底部题号按钮状态（已答/未答/当前）。"""
        for i, btn in enumerate(self.jump_buttons):
            is_answered = i in self.answers
            is_current = (i == self.current_idx)

            if is_answered:
                btn.configure(style="Answered.TButton")
            else:
                btn.configure(style="TButton")

            if is_current:
                btn.state(["pressed"])
            else:
                btn.state(["!pressed"])

    def _submit_exam(self):
        self._save_current_answer()
        unanswered = len(self.question_indices) - len(self.answers)
        if unanswered > 0:
            if not messagebox.askyesno("确认提交",
                                       f"还有 {unanswered} 题未作答，确定提交吗？"):
                return
        self._submitted = True
        self._do_submit()

    def _do_submit(self):
        if self._timer_id:
            self.window.after_cancel(self._timer_id)
            self._timer_id = None

        # 计算成绩
        correct = 0
        records = {}
        for i, real_idx in enumerate(self.question_indices):
            q = bank.questions[real_idx]
            user_ans = self.answers.get(i)
            is_correct = q.check_answer(user_ans) if user_ans is not None else False
            records[real_idx] = is_correct
            if is_correct:
                correct += 1

        total = len(self.question_indices)
        used_seconds = self.total_seconds - max(self.remaining_seconds, 0)

        # 保存历史记录
        bank.add_history({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "correct": correct,
            "time_limit_minutes": self.total_seconds // 60,
            "used_seconds": used_seconds
        })

        self.window.destroy()
        ResultWindow(self.parent, "考试成绩", total, len(self.answers),
                     correct, bank.questions, self.question_indices, records)
        self.parent.deiconify()


# ============================================================================
# 成绩窗口
# ============================================================================

class ResultWindow:
    """成绩显示窗口。"""

    def __init__(self, parent, title, total, answered, correct,
                 questions, indices, records):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.resizable(False, False)
        center_window(self.window, 420, 380)
        self.window.focus_force()

        frame = ttk.Frame(self.window, padding=25)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=f"📊 {title}",
                  font=("Microsoft YaHei", 16, "bold")).pack(pady=(0, 15))

        correct_rate = (correct / total * 100) if total > 0 else 0

        info_text = (
            f"总题数：{total}\n"
            f"已答题数：{answered}\n"
            f"正确数：{correct}\n"
            f"正确率：{correct_rate:.1f}%\n"
        )
        ttk.Label(frame, text=info_text, font=("Microsoft YaHei", 12),
                  justify="left").pack(anchor="w", pady=(0, 10))

        # 各题型统计
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(frame, text="各题型正确率：",
                  font=("Microsoft YaHei", 10, "bold")).pack(anchor="w")

        type_stats = {"single": [0, 0], "multi": [0, 0], "fill": [0, 0]}
        for idx in indices:
            q = questions[idx]
            if q.qtype in type_stats:
                type_stats[q.qtype][0] += 1
                if records.get(idx, False):
                    type_stats[q.qtype][1] += 1

        type_cn = {"single": "单选题", "multi": "多选题", "fill": "填空题"}
        for ttype, cn_name in type_cn.items():
            ttl, crt = type_stats[ttype]
            if ttl > 0:
                rate = crt / ttl * 100
                ttk.Label(frame, text=f"  {cn_name}: {crt}/{ttl} ({rate:.1f}%)",
                          font=("Microsoft YaHei", 10)).pack(anchor="w")
            else:
                ttk.Label(frame, text=f"  {cn_name}: 无题目",
                          font=("Microsoft YaHei", 10)).pack(anchor="w")

        ttk.Button(frame, text="关闭",
                   command=self.window.destroy).pack(pady=(20, 0))


# ============================================================================
# 题库管理窗口
# ============================================================================

class BankManagementWindow:
    """题库管理窗口 —— Treeview 列表 + 增删改查。"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("题库管理")
        self.window.resizable(True, True)
        center_window(self.window, 750, 550)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        # 顶部搜索栏
        top_frame = ttk.Frame(self.window, padding=10)
        top_frame.pack(fill="x")

        ttk.Label(top_frame, text="搜索:").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._refresh_list())
        ttk.Entry(top_frame, textvariable=self.search_var,
                  width=30).pack(side="left", padx=5)

        ttk.Button(top_frame, text="添加题目",
                   command=self._add_question).pack(side="right", padx=3)
        ttk.Button(top_frame, text="修改题目",
                   command=self._edit_question).pack(side="right", padx=3)
        ttk.Button(top_frame, text="删除题目",
                   command=self._delete_question).pack(side="right", padx=3)
        ttk.Button(top_frame, text="返回主菜单",
                   command=self._on_close).pack(side="right", padx=10)

        # Treeview 列表
        tree_frame = ttk.Frame(self.window, padding=10)
        tree_frame.pack(fill="both", expand=True)

        columns = ("#", "type", "preview")
        self.tree = ttk.Treeview(tree_frame, columns=columns,
                                  show="headings", selectmode="browse")
        self.tree.heading("#", text="序号")
        self.tree.heading("type", text="题型")
        self.tree.heading("preview", text="题目预览")
        self.tree.column("#", width=50, anchor="center")
        self.tree.column("type", width=60, anchor="center")
        self.tree.column("preview", width=600)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical",
                                   command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 双击查看/编辑
        self.tree.bind("<Double-1>", lambda e: self._edit_question())

    def _refresh_list(self):
        """刷新题目列表，支持搜索过滤。"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        keyword = self.search_var.get().strip().lower()
        type_cn = {"single": "单选", "multi": "多选", "fill": "填空"}

        for i, q in enumerate(bank.questions):
            if keyword:
                search_text = q.question.lower()
                if isinstance(q, (SingleChoiceQuestion, MultiChoiceQuestion)):
                    search_text += " " + " ".join(
                        o.lower() for o in q.options)
                if keyword not in search_text:
                    continue

            preview = q.question[:50] + ("..." if len(q.question) > 50 else "")
            self.tree.insert("", "end", iid=str(i),
                             values=(i + 1, type_cn.get(q.qtype, q.qtype),
                                     preview))

    def _get_selected_index(self) -> int:
        """获取当前选中题目的索引，未选中返回 -1。"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选择一道题目。")
            return -1
        return int(sel[0])

    def _add_question(self):
        QuestionEditWindow(self.window, on_save=self._refresh_list)

    def _edit_question(self):
        idx = self._get_selected_index()
        if idx < 0:
            return
        QuestionEditWindow(self.window, question=bank.questions[idx],
                           index=idx, on_save=self._refresh_list)

    def _delete_question(self):
        idx = self._get_selected_index()
        if idx < 0:
            return
        q = bank.questions[idx]
        if messagebox.askyesno("确认删除",
                               f"确定要删除题目：\n{q.get_short_info()}？"):
            del bank.questions[idx]
            bank.save()
            self._refresh_list()

    def _on_close(self):
        bank.save()
        self.window.destroy()
        self.parent.deiconify()


# ============================================================================
# 题目编辑窗口（添加/修改共用）
# ============================================================================

class QuestionEditWindow:
    """题目编辑弹窗 —— 支持添加和修改模式。"""

    def __init__(self, parent, question=None, index=None, on_save=None):
        self.parent = parent
        self.question = question
        self.index = index
        self.on_save = on_save
        self.is_edit = question is not None

        self.window = tk.Toplevel(parent)
        self.window.title("修改题目" if self.is_edit else "添加题目")
        self.window.resizable(False, False)
        center_window(self.window, 500, 520)
        self.window.focus_force()

        self._build_ui()

        if self.is_edit:
            self._load_question()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=15)
        frame.pack(fill="both", expand=True)

        # 题型选择
        row0 = ttk.Frame(frame)
        row0.pack(fill="x", pady=(0, 10))
        ttk.Label(row0, text="题型:", width=8).pack(side="left")
        self.type_var = tk.StringVar(value="single")
        if self.is_edit:
            assert self.question is not None
            type_names = {"single": "单选题", "multi": "多选题",
                          "fill": "填空题"}
            ttk.Label(row0, text=type_names.get(
                self.question.qtype, "")).pack(side="left")
            self.type_var.set(self.question.qtype)
        else:
            ttk.Radiobutton(row0, text="单选题", variable=self.type_var,
                            value="single",
                            command=self._render_dynamic_fields
                            ).pack(side="left", padx=5)
            ttk.Radiobutton(row0, text="多选题", variable=self.type_var,
                            value="multi",
                            command=self._render_dynamic_fields
                            ).pack(side="left", padx=5)
            ttk.Radiobutton(row0, text="填空题", variable=self.type_var,
                            value="fill",
                            command=self._render_dynamic_fields
                            ).pack(side="left", padx=5)

        # 题目内容
        row1 = ttk.Frame(frame)
        row1.pack(fill="x", pady=5)
        ttk.Label(row1, text="题目内容:", width=8).pack(side="left", anchor="n")
        self.question_text = scrolledtext.ScrolledText(
            row1, height=3, width=50)
        self.question_text.pack(side="left", fill="x", expand=True)

        # 选项/填空区域（动态）
        self.dynamic_frame = ttk.Frame(frame)
        self.dynamic_frame.pack(fill="both", expand=True, pady=10)

        self._render_dynamic_fields()

        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_frame, text="保存",
                   command=self._save).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="取消",
                   command=self.window.destroy).pack(side="right", padx=5)

    def _render_dynamic_fields(self):
        """根据题型渲染选项/填空输入区。"""
        for w in self.dynamic_frame.winfo_children():
            w.destroy()

        qtype = self.type_var.get()

        if qtype in ("single", "multi"):
            ttk.Label(self.dynamic_frame,
                      text="选项（每行一个，如 A. 北京）:",
                      font=("Microsoft YaHei", 9)).pack(anchor="w")
            self.options_text = scrolledtext.ScrolledText(
                self.dynamic_frame, height=5, width=50)
            self.options_text.pack(fill="x", expand=True)

            if qtype == "single":
                ttk.Label(self.dynamic_frame, text="正确答案（如 B）:",
                          font=("Microsoft YaHei", 9)
                          ).pack(anchor="w", pady=(5, 0))
            else:
                ttk.Label(self.dynamic_frame,
                          text="正确答案（多选用逗号分隔，如 A,B,D）:",
                          font=("Microsoft YaHei", 9)
                          ).pack(anchor="w", pady=(5, 0))
            self.answer_var = tk.StringVar()
            ttk.Entry(self.dynamic_frame, textvariable=self.answer_var,
                      width=20).pack(anchor="w")

        elif qtype == "fill":
            ttk.Label(self.dynamic_frame,
                      text="填空答案设置（每空一行，格式: 答案1,答案2,答案3）:",
                      font=("Microsoft YaHei", 9)).pack(anchor="w")
            ttk.Label(self.dynamic_frame,
                      text="题目中用 {0}、{1}... 表示填空位置",
                      font=("Microsoft YaHei", 8),
                      foreground="gray").pack(anchor="w")
            self.blanks_text = scrolledtext.ScrolledText(
                self.dynamic_frame, height=5, width=50)
            self.blanks_text.pack(fill="x", expand=True)

    def _load_question(self):
        """编辑模式：加载题目数据到控件。"""
        q = self.question
        assert q is not None
        self.question_text.insert("1.0", q.question)

        if isinstance(q, SingleChoiceQuestion):
            self.options_text.insert("1.0", "\n".join(q.options))
            self.answer_var.set(q.answer)
        elif isinstance(q, MultiChoiceQuestion):
            self.options_text.insert("1.0", "\n".join(q.options))
            self.answer_var.set(",".join(q.answer))
        elif isinstance(q, FillInBlankQuestion):
            lines = [",".join(b["answers"]) for b in q.blanks]
            self.blanks_text.insert("1.0", "\n".join(lines))

    def _save(self):
        """保存题目到题库。"""
        qtype = self.type_var.get()
        text = self.question_text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("警告", "题目内容不能为空！")
            return

        try:
            if qtype == "single":
                options = [o.strip() for o in
                           self.options_text.get("1.0", "end-1c").strip()
                           .split("\n") if o.strip()]
                answer = self.answer_var.get().strip().upper()
                if len(options) < 2:
                    raise ValueError("单选题至少需要 2 个选项")
                if not answer:
                    raise ValueError("答案不能为空")
                q = SingleChoiceQuestion(text, options, answer)

            elif qtype == "multi":
                options = [o.strip() for o in
                           self.options_text.get("1.0", "end-1c").strip()
                           .split("\n") if o.strip()]
                raw_ans = self.answer_var.get().strip()
                answer = [a.strip().upper() for a in raw_ans.split(",")
                          if a.strip()]
                if len(options) < 2:
                    raise ValueError("多选题至少需要 2 个选项")
                if not answer:
                    raise ValueError("答案不能为空")
                q = MultiChoiceQuestion(text, options, answer)

            elif qtype == "fill":
                raw_blanks = [b.strip() for b in
                              self.blanks_text.get("1.0", "end-1c").strip()
                              .split("\n") if b.strip()]
                blanks = []
                for line in raw_blanks:
                    answers = [a.strip() for a in line.split(",")
                               if a.strip()]
                    if not answers:
                        raise ValueError("每个填空至少需要一个答案")
                    blanks.append({"answers": answers})
                if not blanks:
                    raise ValueError("填空答案不能为空")
                q = FillInBlankQuestion(text, blanks)

            else:
                raise ValueError(f"未知题型: {qtype}")

            # 保存到题库
            if self.is_edit:
                assert self.index is not None
                bank.questions[self.index] = q
            else:
                bank.questions.append(q)
            bank.save()

            if self.on_save:
                self.on_save()
            self.window.destroy()

        except ValueError as e:
            messagebox.showwarning("输入错误", str(e))


# ============================================================================
# 导入窗口
# ============================================================================

class ImportWindow:
    """导入题库窗口。"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("导入题库")
        self.window.resizable(False, False)
        center_window(self.window, 580, 440)
        self.window.focus_force()

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=15)
        frame.pack(fill="both", expand=True)

        # 标题行
        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="📥 导入题库",
                  font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        ttk.Button(header, text="📋 查看格式说明",
                   command=self._show_format_help).pack(side="right")

        ttk.Button(frame, text="从 TXT 文件导入...",
                   command=self._from_file).pack(fill="x", pady=5)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(frame, text="或直接在下方粘贴题目文本：",
                  font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(0, 5))

        self.text_area = scrolledtext.ScrolledText(frame, height=12, width=60)
        self.text_area.pack(fill="both", expand=True, pady=(0, 10))

        ttk.Label(frame,
                  text="题与题之间用空行分隔，点击右上角「查看格式说明」了解详细格式。",
                  font=("Microsoft YaHei", 8),
                  foreground="gray").pack(anchor="w")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="解析并导入",
                   command=self._import_text).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="关闭",
                   command=self.window.destroy).pack(side="right", padx=5)

    def _show_format_help(self):
        """弹出 TXT 题库格式说明窗口。"""
        help_win = tk.Toplevel(self.window)
        help_win.title("TXT 题库格式说明")
        help_win.resizable(False, False)
        center_window(help_win, 600, 480)
        help_win.focus_force()

        frame = ttk.Frame(help_win, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="📋 TXT 题库格式说明",
                  font=("Microsoft YaHei", 13, "bold")).pack(pady=(0, 10))

        text = scrolledtext.ScrolledText(frame, width=68, height=22,
                                         font=("Consolas", 10))
        text.pack(fill="both", expand=True)

        # 格式说明内容
        help_content = """\
══════════════════════════════════════════════════
  TXT 题库文件格式规范
══════════════════════════════════════════════════

【基本规则】
  • 每道题占多行，题与题之间用空行分隔
  • 第一行格式: 序号.(题型)题目内容
  • 题型: 单选题 / 多选题 / 填空题

──────────────────────────────────────────────
  1. 单选题
──────────────────────────────────────────────
  1.(单选题)中国的首都是？
  A. 上海
  B. 北京
  C. 广州
  D. 深圳
  answer: B

  说明:
  - 选项以 A. B. C. D. 开头（支持任意数量选项）
  - answer: 后填正确选项字母

──────────────────────────────────────────────
  2. 多选题
──────────────────────────────────────────────
  2.(多选题)以下哪些是编程语言？
  A. Python
  B. Java
  C. 中文
  D. C++
  answer: A,B,D

  说明:
  - 多个答案用逗号分隔（如 A,B,D）
  - 所有选项必须全选对才得分

──────────────────────────────────────────────
  3. 填空题
──────────────────────────────────────────────
  3.(填空题)世界上最高的山峰是 {0}，海拔 {1} 米。
  blank0: 珠穆朗玛峰,珠峰
  blank1: 8848.86,8848

  说明:
  - 题目中用 {0}、{1}... 标记填空位置
  - blank0: 对应 {0} 的答案，多个可接受答案用逗号分隔
  - 每个空的答案匹配任一即可得分

══════════════════════════════════════════════════
  完整示例（3 道题，注意题间空行）
══════════════════════════════════════════════════
  1.(单选题)Python 的作者是？
  A. Guido van Rossum
  B. Dennis Ritchie
  C. James Gosling
  D. Bjarne Stroustrup
  answer: A

  2.(多选题)以下哪些是Python标准库？
  A. os
  B. json
  C. numpy
  D. random
  answer: A,B,D

  3.(填空题)Python 中表示空值的常量是 {0}。
  blank0: None,none
"""
        text.insert("1.0", help_content)
        text.configure(state="disabled")  # 只读

        ttk.Button(frame, text="关闭",
                   command=help_win.destroy).pack(pady=(10, 0))

    def _from_file(self):
        filepath = filedialog.askopenfilename(
            title="选择 TXT 题库文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            self._do_import(text)
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {e}")

    def _import_text(self):
        text = self.text_area.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showinfo("提示", "请先粘贴题目文本或选择文件。")
            return
        self._do_import(text)

    def _do_import(self, text: str):
        parsed = QuestionBank.parse_txt(text)
        if not parsed:
            result = messagebox.askyesno(
                "导入失败",
                "未能解析到有效题目，请检查格式是否正确。\n\n"
                "是否查看 TXT 题库格式说明？")
            if result:
                self._show_format_help()
            return
        bank.questions.extend(parsed)
        bank.save()
        messagebox.showinfo("导入成功", f"成功导入 {len(parsed)} 道题目！")
        self.window.destroy()


# ============================================================================
# 导出窗口
# ============================================================================

class ExportWindow:
    """导出题库窗口。"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("导出题库")
        self.window.resizable(False, False)
        center_window(self.window, 450, 200)
        self.window.focus_force()

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="📤 导出题库",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 15))

        ttk.Label(frame,
                  text=f"当前题库共 {len(bank.questions)} 道题目，"
                       "将导出为 TXT 格式。",
                  font=("Microsoft YaHei", 10)).pack(pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="选择保存路径...",
                   command=self._export).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="取消",
                   command=self.window.destroy).pack(side="right", padx=5)

    def _export(self):
        filepath = filedialog.asksaveasfilename(
            title="导出题库",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not filepath:
            return
        try:
            content = QuestionBank.export_txt_str(bank.questions)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("导出成功", f"题库已导出到:\n{filepath}")
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("导出失败", str(e))


# ============================================================================
# 统计窗口
# ============================================================================

class StatisticsWindow:
    """查看统计窗口。"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("统计信息")
        self.window.resizable(False, False)
        center_window(self.window, 480, 500)
        self.window.focus_force()

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="📊 统计信息",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 15))

        # 题库统计
        ttk.Label(frame, text="── 题库统计 ──",
                  font=("Microsoft YaHei", 11, "bold")
                  ).pack(anchor="w", pady=(0, 5))

        stats = bank.get_statistics()
        ttk.Label(frame, text=f"总题数: {stats['total']}",
                  font=("Microsoft YaHei", 10)).pack(anchor="w")
        ttk.Label(frame, text=f"单选题: {stats['single']}",
                  font=("Microsoft YaHei", 10)).pack(anchor="w")
        ttk.Label(frame, text=f"多选题: {stats['multi']}",
                  font=("Microsoft YaHei", 10)).pack(anchor="w")
        ttk.Label(frame, text=f"填空题: {stats['fill']}",
                  font=("Microsoft YaHei", 10)).pack(anchor="w")

        # 历史成绩
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(frame, text="── 历史考试成绩 ──",
                  font=("Microsoft YaHei", 11, "bold")
                  ).pack(anchor="w", pady=(0, 5))

        if not bank.history:
            ttk.Label(frame, text="暂无考试记录。",
                      font=("Microsoft YaHei", 10),
                      foreground="gray").pack(anchor="w", pady=5)
        else:
            list_frame = ttk.Frame(frame)
            list_frame.pack(fill="both", expand=True, pady=5)

            columns = ("date", "total", "correct", "rate", "time")
            tree = ttk.Treeview(list_frame, columns=columns,
                                 show="headings", height=8)
            tree.heading("date", text="日期")
            tree.heading("total", text="题量")
            tree.heading("correct", text="正确")
            tree.heading("rate", text="正确率")
            tree.heading("time", text="用时")
            tree.column("date", width=140)
            tree.column("total", width=50, anchor="center")
            tree.column("correct", width=50, anchor="center")
            tree.column("rate", width=60, anchor="center")
            tree.column("time", width=80, anchor="center")

            scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                       command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            for rec in bank.history:
                rate = (rec["correct"] / rec["total"] * 100
                        if rec["total"] > 0 else 0)
                used_min = rec.get("used_seconds", 0) // 60
                used_sec = rec.get("used_seconds", 0) % 60
                tree.insert("", "end", values=(
                    rec.get("date", "未知"),
                    rec["total"],
                    rec["correct"],
                    f"{rate:.1f}%",
                    f"{used_min}分{used_sec}秒"
                ))

            if bank.history:
                avg_rate = sum(
                    r["correct"] / r["total"] * 100 if r["total"] > 0 else 0
                    for r in bank.history
                ) / len(bank.history)
                ttk.Label(frame,
                          text=f"平均正确率: {avg_rate:.1f}%"
                               f"（共 {len(bank.history)} 次考试）",
                          font=("Microsoft YaHei", 10, "bold")
                          ).pack(anchor="w", pady=(10, 0))

        ttk.Button(frame, text="关闭",
                   command=self.window.destroy).pack(pady=(15, 0))


# ============================================================================
# 程序入口
# ============================================================================

def main():
    """启动 GUI 程序。"""
    # 预初始化样式
    root_temp = tk.Tk()
    root_temp.withdraw()
    style = ttk.Style()
    style.configure("Answered.TButton", background="#90EE90")
    root_temp.destroy()

    app = MainApp()
    app.run()


if __name__ == "__main__":
    main()
