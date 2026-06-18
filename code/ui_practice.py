import json
import os
import random
import tkinter as tk
from tkinter import ttk, messagebox
from code.models import bank, config, BANKS_DIR, Question, SingleChoiceQuestion, MultiChoiceQuestion, FillInBlankQuestion
from code.utils import center_window
from code.ui_exam import ResultWindow

class PracticeWindow:
    """刷题练习窗口 —— 随机出题，可查看答案，支持错题本模式。"""

    def __init__(self, parent, questions: list, indices_map=None,
                 mode_name: str = "刷题模式"):
        self.parent = parent
        self.questions = questions
        self.indices_map = indices_map
        self.mode_name = mode_name
        self.is_random = (config.get("practice_mode") == "random")
        self._progress_file = os.path.join(
            BANKS_DIR, f"{bank.active_name}_progress.json")

        # 保存原始主题名，以便窗口关闭后恢复
        self._orig_theme = ttk.Style().theme_use()

        # 初始化题目顺序
        self.shuffled = list(range(len(questions)))
        if self.is_random:
            random.shuffle(self.shuffled)

        self.current_idx = 0
        self.records: dict[int, bool] = {}
        self.show_answer_flag = tk.BooleanVar(
            value=config.get("practice_show_answer"))

        # 尝试恢复上次进度
        restored = False
        if indices_map is None and self._try_restore_progress():
            restored = True

        self.window = tk.Toplevel(parent)
        self.window.title(self.mode_name)
        self.window.resizable(True, True)
        try:
            self.window.state("zoomed")
        except Exception:
            center_window(self.window, 700, 580)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

        if restored:
            msg = (f"已恢复上次进度（第 {self.current_idx + 1}/{len(self.shuffled)} 题，"
                   f"已答 {len(self.records)} 题）")
            self._mode_label.config(text=f"模式: {'随机' if self.is_random else '顺序'} | {msg}")

        self._display_question()
        self._bind_keys()

    def _build_ui(self):
        # 使用 clam 主题使选择框随字体缩放（设置在 build_ui 开头，仅一次）
        self._opt_style = ttk.Style()
        self._opt_style.theme_use('clam')
        self._opt_style.configure("Option.TRadiobutton", font=("Microsoft YaHei", 22),
                                  indicatorsize=28)
        self._opt_style.configure("Option.TCheckbutton", font=("Microsoft YaHei", 22),
                                  indicatorsize=28)

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

        hint = "← → 切换 | A~H/1~8 选择 | 空格/回车 提交"
        ttk.Label(top_frame, text=hint, font=("Microsoft YaHei", 8),
                  foreground="gray").pack(side="left", padx=15)

        self._mode_label = ttk.Label(top_frame, text="", font=("Microsoft YaHei", 8),
                                     foreground="blue")
        self._mode_label.pack(side="left", padx=10)

        ttk.Button(top_frame, text="切换随机/顺序",
                   command=self._toggle_mode).pack(side="right", padx=5)

        ttk.Button(top_frame, text="显示/隐藏答案",
                   command=self._toggle_answer).pack(side="right", padx=5)
        ttk.Button(top_frame, text="返回主菜单",
                   command=self._on_close).pack(side="right", padx=5)

        ttk.Separator(self.window, orient="horizontal").pack(fill="x", padx=10)

        # 题目显示区
        self.question_frame = ttk.Frame(self.window, padding=15)
        self.question_frame.pack(fill="both", expand=True)

        self.type_label = ttk.Label(self.question_frame, text="",
                                    font=("Microsoft YaHei", 12, "bold"))
        self.type_label.pack(anchor="w", pady=(0, 5))

        self.question_label = ttk.Label(self.question_frame, text="",
                                        font=("Microsoft YaHei", 24),
                                        wraplength=650, justify="left")
        self.question_label.pack(anchor="w", pady=(0, 10))

        # 选项/填空区域
        self.answer_frame = ttk.Frame(self.question_frame)
        self.answer_frame.pack(fill="both", expand=True)

        # 正确答案显示
        self.correct_answer_label = ttk.Label(self.question_frame, text="",
                                              font=("Microsoft YaHei", 11),
                                              foreground="green")
        self.correct_answer_label.pack(anchor="w", pady=(10, 0))

        # 答题结果提示
        self.result_label = ttk.Label(self.question_frame, text="",
                                      font=("Microsoft YaHei", 11, "bold"))
        self.result_label.pack(anchor="w", pady=(5, 0))

        # 错题次数
        self.wrong_count_label = ttk.Label(self.question_frame, text="",
                                           font=("Microsoft YaHei", 9),
                                           foreground="orange")
        self.wrong_count_label.pack(anchor="w", pady=(3, 0))

        # 底部导航
        bottom_frame = ttk.Frame(self.window, padding=10)
        bottom_frame.pack(fill="x", side="bottom")

        ttk.Button(bottom_frame, text="◀ 上一题",
                   command=self._prev).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="下一题 ▶",
                   command=self._next).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="提交答案",
                   command=self._submit).pack(side="right", padx=5)

    def _bind_keys(self):
        """绑定键盘快捷键。"""
        self.window.bind("<Left>", lambda e: self._prev())
        self.window.bind("<Right>", lambda e: self._next())
        self.window.bind("<Return>", lambda e: self._submit())
        # 字母键选择选项
        for letter in "ABCDEFGH":
            self.window.bind(f"<KeyPress-{letter}>",
                             lambda e, l=letter: self._key_select(l))
            self.window.bind(f"<KeyPress-{letter.lower()}>",
                             lambda e, l=letter: self._key_select(l))
        # 数字键选择: 1→A, 2→B, 3→C ...
        num_map = "ABCDEFGH"
        for i, letter in enumerate(num_map):
            self.window.bind(str(i + 1), lambda e, l=letter: self._key_select(l))
        # 空格键提交（窗口级兜底）；选项控件上有独立绑定阻断默认切换行为
        self.window.bind("<space>", lambda e: self._submit())

    def _key_select(self, letter: str):
        """键盘按字母选择对应选项。"""
        q = self._current_question()
        if isinstance(q, SingleChoiceQuestion):
            valid = [o.split(".")[0].strip().upper() for o in q.options]
            if letter in valid and hasattr(self, '_var'):
                self._var.set(letter)
        elif isinstance(q, MultiChoiceQuestion):
            if hasattr(self, '_check_vars') and letter in self._check_vars:
                var = self._check_vars[letter]
                var.set(not var.get())

    def _display_question(self):
        """渲染当前题目。"""
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

        # 渲染选项/填空（题目字号-2 = 22pt，选择框随 clam 主题自动缩放）
        if isinstance(q, SingleChoiceQuestion):
            self._var = tk.StringVar(value="")
            for opt in q.options:
                key = opt.split(".")[0].strip().upper()
                rb = ttk.Radiobutton(self.answer_frame, text=opt,
                                     variable=self._var, value=key,
                                     style="Option.TRadiobutton",
                                     takefocus=0)
                rb.pack(anchor="w", pady=4)
                # 空格键提交，阻断默认选中/取消行为
                rb.bind("<space>", lambda e: (self._submit(), "break")[1])
        elif isinstance(q, MultiChoiceQuestion):
            self._check_vars = {}
            for opt in q.options:
                key = opt.split(".")[0].strip().upper()
                var = tk.BooleanVar(value=False)
                self._check_vars[key] = var
                cb = ttk.Checkbutton(self.answer_frame, text=opt,
                                     variable=var,
                                     style="Option.TCheckbutton",
                                     takefocus=0)
                cb.pack(anchor="w", pady=4)
                # 空格键提交，阻断默认勾选/取消行为
                cb.bind("<space>", lambda e: (self._submit(), "break")[1])
        elif isinstance(q, FillInBlankQuestion):
            self._entry_vars = []
            for i in range(len(q.blanks)):
                lbl = ttk.Label(self.answer_frame, text=f"空{i+1}：",
                                font=("Microsoft YaHei", 11))
                lbl.pack(anchor="w", pady=(5, 0))
                var = tk.StringVar()
                ttk.Entry(self.answer_frame, textvariable=var, width=40,
                          font=("Microsoft YaHei", 12)).pack(anchor="w", pady=(0, 5))
                self._entry_vars.append(var)

        # 正确答案
        if self.show_answer_flag.get():
            self.correct_answer_label.config(
                text=f"★ 正确答案: {q.get_answer_display()}")
        else:
            self.correct_answer_label.config(text="")

        # 答题结果
        real_idx = self._real_question_index()
        if real_idx in self.records:
            status = "✓ 回答正确" if self.records[real_idx] else "✗ 回答错误"
            color = "green" if self.records[real_idx] else "red"
            self.result_label.config(text=status, foreground=color)
        else:
            self.result_label.config(text="")

        # 错题次数
        wc = bank.get_wrong_count(real_idx)
        if wc > 0:
            self.wrong_count_label.config(text=f"⚠ 已错 {wc} 次")
        else:
            self.wrong_count_label.config(text="")

    def _current_question(self) -> Question:
        return self.questions[self.shuffled[self.current_idx]]

    def _real_question_index(self) -> int:
        """获取当前题目在题库中的真实索引。"""
        if self.indices_map is not None:
            return self.indices_map[self.shuffled[self.current_idx]]
        return self.shuffled[self.current_idx]

    def _get_user_answer(self):
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
        real_idx = self._real_question_index()
        user_ans = self._get_user_answer()
        is_correct = q.check_answer(user_ans)
        self.records[real_idx] = is_correct

        if is_correct:
            self.result_label.config(text="✓ 回答正确！", foreground="green")
            # 正确自动跳下一题
            self.window.after(500, self._auto_next)
        else:
            self.result_label.config(
                text=f"✗ 回答错误！正确答案: {q.get_answer_display()}",
                foreground="red")
            # 记录到错题本
            bank.add_wrong(real_idx)
            wc = bank.get_wrong_count(real_idx)
            self.wrong_count_label.config(text=f"⚠ 已错 {wc} 次")

    def _auto_next(self):
        """正确后自动跳转下一题。"""
        if self.current_idx < len(self.shuffled) - 1:
            self.current_idx += 1
            self._display_question()
        else:
            self._check_all_done()

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
        # 完成时清除进度
        if os.path.exists(self._progress_file):
            os.remove(self._progress_file)
        ResultWindow(self.window, "练习成绩", total, answered, correct,
                     self.questions, self.shuffled, self.records)

    # ---------- 进度持久化 ----------

    def _try_restore_progress(self) -> bool:
        """尝试恢复上次进度，返回是否成功。"""
        if not os.path.exists(self._progress_file):
            return False
        try:
            with open(self._progress_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            saved_shuffled = data.get("shuffled", [])
            # 验证题库未变（题目数量一致）
            if len(saved_shuffled) != len(self.shuffled):
                return False
            self.shuffled = saved_shuffled
            self.current_idx = data.get("current_idx", 0)
            self.records = {int(k): v for k, v in data.get("records", {}).items()}
            return True
        except (json.JSONDecodeError, ValueError, KeyError):
            return False

    def _save_progress(self):
        """保存当前刷题进度。"""
        if self.indices_map is not None:
            return  # 错题本模式不保存进度
        data = {
            "shuffled": self.shuffled,
            "current_idx": self.current_idx,
            "records": {str(k): v for k, v in self.records.items()}
        }
        try:
            with open(self._progress_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    def _toggle_mode(self):
        """切换随机/顺序模式。"""
        if messagebox.askyesno("切换模式", "切换刷题模式将重置当前进度，确定继续？"):
            self.is_random = not self.is_random
            config.set("practice_mode", "random" if self.is_random else "sequential")
            self.shuffled = list(range(len(self.questions)))
            if self.is_random:
                random.shuffle(self.shuffled)
            self.current_idx = 0
            self.records = {}
            self._display_question()
            self._mode_label.config(
                text=f"模式: {'随机' if self.is_random else '顺序'} | 进度已重置")
            if os.path.exists(self._progress_file):
                os.remove(self._progress_file)

    def _on_close(self):
        self.window.unbind("<Left>")
        self.window.unbind("<Right>")
        self.window.unbind("<Return>")
        self.window.unbind("<space>")
        for letter in "ABCDEFGH":
            self.window.unbind(f"<KeyPress-{letter}>")
            self.window.unbind(f"<KeyPress-{letter.lower()}>")
            self.window.unbind(str(ord(letter) - ord('A') + 1))
        self._save_progress()
        # 恢复原始 ttk 主题
        try:
            ttk.Style().theme_use(self._orig_theme)
        except Exception:
            pass
        self.window.destroy()
        self.parent.deiconify()


# ============================================================================

