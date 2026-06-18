import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from code.models import bank, config, SingleChoiceQuestion, MultiChoiceQuestion, FillInBlankQuestion, Question
from code.utils import center_window

# 考试设置窗口
# ============================================================================

class ExamSetupWindow:
    """考试设置窗口 —— 按题型选择题量、时长。"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("考试设置")
        self.window.resizable(False, False)
        center_window(self.window, 420, 340)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="⏱ 考试设置",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 10))

        stats = bank.get_statistics()
        ttk.Label(frame,
                  text=f"题库: 单选 {stats['single']} | 多选 {stats['multi']} | 填空 {stats['fill']}",
                  font=("Microsoft YaHei", 9)).pack(anchor="w", pady=(0, 10))

        # 各题型题量
        types = [("单选题", "single"), ("多选题", "multi"), ("填空题", "fill")]
        self._type_vars = {}
        for label, key in types:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=f"{label}:", width=10).pack(side="left")
            available = stats[key]
            default = min(available, 5) if available > 0 else 0
            var = tk.IntVar(value=default)
            self._type_vars[key] = var
            ttk.Spinbox(row, from_=0, to=available, textvariable=var,
                         width=8).pack(side="left", padx=5)
            ttk.Label(row, text=f"/ {available} 题",
                      font=("Microsoft YaHei", 9)).pack(side="left")

        # 时长
        row_t = ttk.Frame(frame)
        row_t.pack(fill="x", pady=(10, 5))
        ttk.Label(row_t, text="考试时长:", width=10).pack(side="left")
        self.time_var = tk.IntVar(value=30)
        ttk.Spinbox(row_t, from_=1, to=180, textvariable=self.time_var,
                     width=8).pack(side="left", padx=5)
        ttk.Label(row_t, text="分钟", font=("Microsoft YaHei", 9)).pack(side="left")

        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_frame, text="开始考试",
                   command=self._start_exam,
                   takefocus=0).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="返回",
                   command=self._on_close,
                   takefocus=0).pack(side="right", padx=5)

    def _start_exam(self):
        selected = []
        for key in ("single", "multi", "fill"):
            count = self._type_vars[key].get()
            # 获取该题型在题库中的所有索引
            indices = [i for i, q in enumerate(bank.questions) if q.qtype == key]
            if count > len(indices):
                type_cn = {"single": "单选题", "multi": "多选题", "fill": "填空题"}
                messagebox.showwarning("警告",
                    f"{type_cn[key]}仅 {len(indices)} 题，无法抽取 {count} 题！")
                return
            if count > 0:
                selected.extend(random.sample(indices, count))

        if not selected:
            messagebox.showwarning("警告", "请至少选择一种题型！")
            return

        random.shuffle(selected)
        exam_time = self.time_var.get()
        self.window.destroy()
        ExamWindow(self.parent, selected, exam_time)

    def _on_close(self):
        self.window.destroy()
        self.parent.deiconify()


# ============================================================================
# 考试窗口
# ============================================================================

class ExamWindow:
    """考试窗口 —— 限时、禁看答案，支持键盘操作。"""

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
        self.window.focus_force()

        self.window.protocol("WM_DELETE_WINDOW", self._on_force_close)
        # 防作弊：窗口失焦时警告
        self.window.bind("<FocusOut>", self._on_focus_out)
        self._focus_warnings = 0

        self._build_ui()
        self._display_question()
        self._start_timer()
        self._bind_keys()

    def _on_focus_out(self, event=None):
        """窗口失去焦点时警告，累计 3 次自动提交。"""
        if self._submitted:
            return
        self._focus_warnings += 1
        if self._focus_warnings >= 3:
            messagebox.showwarning("防作弊",
                                   "检测到多次切换窗口，试卷将自动提交！")
            self._submitted = True
            self._do_submit()
        else:
            self.window.lift()
            self.window.focus_force()
            messagebox.showwarning(
                "警告",
                f"考试期间请勿切换窗口！\n（第 {self._focus_warnings}/3 次警告）")

    def _bind_keys(self):
        """绑定键盘快捷键。"""
        self.window.bind("<Left>", lambda e: self._prev())
        self.window.bind("<Right>", lambda e: self._next())
        for letter in "ABCDEFGH":
            self.window.bind(f"<KeyPress-{letter}>",
                             lambda e, l=letter: self._key_select(l))
            self.window.bind(f"<KeyPress-{letter.lower()}>",
                             lambda e, l=letter: self._key_select(l))

    def _key_select(self, letter: str):
        q = self._current_question()
        if isinstance(q, SingleChoiceQuestion):
            valid = [o.split(".")[0].strip().upper() for o in q.options]
            if letter in valid and hasattr(self, '_var'):
                self._var.set(letter)
                self._save_current_answer()
        elif isinstance(q, MultiChoiceQuestion):
            if hasattr(self, '_check_vars') and letter in self._check_vars:
                var = self._check_vars[letter]
                var.set(not var.get())
                self._save_current_answer()

    def _build_ui(self):
        top_frame = ttk.Frame(self.window, padding=10)
        top_frame.pack(fill="x")

        self.timer_label = ttk.Label(top_frame, text="",
                                     font=("Microsoft YaHei", 16, "bold"),
                                     foreground="red")
        self.timer_label.pack(side="left", padx=10)

        self.progress_label = ttk.Label(top_frame, text="",
                                        font=("Microsoft YaHei", 11))
        self.progress_label.pack(side="left", padx=20)

        ttk.Label(top_frame, text="← → 切换 | A/B/C/D 选择",
                  font=("Microsoft YaHei", 8),
                  foreground="gray").pack(side="left", padx=15)

        ttk.Button(top_frame, text="提交试卷",
                   command=self._submit_exam,
                   takefocus=0).pack(side="right", padx=10)

        ttk.Separator(self.window, orient="horizontal").pack(fill="x", padx=10)

        # 题目显示区
        self.question_frame = ttk.Frame(self.window, padding=15)
        self.question_frame.pack(fill="both", expand=True)

        self.type_label = ttk.Label(self.question_frame, text="",
                                    font=("Microsoft YaHei", 12, "bold"))
        self.type_label.pack(anchor="w", pady=(0, 5))

        self.question_label = ttk.Label(self.question_frame, text="",
                                        font=("Microsoft YaHei", 24),
                                        wraplength=700, justify="left")
        self.question_label.pack(anchor="w", pady=(0, 10))

        self.answer_frame = ttk.Frame(self.question_frame)
        self.answer_frame.pack(fill="both", expand=True)

        # 底部导航
        bottom_frame = ttk.Frame(self.window, padding=10)
        bottom_frame.pack(fill="x", side="bottom")
        ttk.Button(bottom_frame, text="◀ 上一题",
                   command=self._prev,
                   takefocus=0).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="下一题 ▶",
                   command=self._next,
                   takefocus=0).pack(side="left", padx=5)

        self.jump_frame = ttk.Frame(bottom_frame)
        self.jump_frame.pack(side="right", padx=10)
        self._build_jump_buttons()

    def _build_jump_buttons(self):
        """构建题号跳转按钮。"""
        self.jump_buttons = []
        for i in range(len(self.question_indices)):
            btn = ttk.Button(self.jump_frame, text=str(i + 1), width=3,
                             command=lambda idx=i: self._jump_to(idx),
                             takefocus=0)
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
            is_correct = q.check_answer(user_ans) if user_ans is not None else None
            records[real_idx] = is_correct
            if is_correct is True:
                correct += 1
            else:
                # 错题记入错题本
                bank.add_wrong(real_idx)

        total = len(self.question_indices)
        used_seconds = self.total_seconds - max(self.remaining_seconds, 0)

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
    """成绩显示窗口 —— 含成绩概览和逐题详情。"""

    def __init__(self, parent, title, total, answered, correct,
                 questions, indices, records):
        self.parent = parent
        self.questions = questions
        self.indices = indices
        self.records = records
        self.total = total
        self.answered = answered
        self.correct = correct

        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.resizable(False, False)
        center_window(self.window, 440, 420)
        self.window.focus_force()

        self._build_main()

    def _build_main(self):
        """主成绩页面。"""
        for w in self.window.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.window, padding=25)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="📊 成绩报告",
                  font=("Microsoft YaHei", 16, "bold")).pack(pady=(0, 15))

        correct_rate = (self.correct / self.total * 100) if self.total > 0 else 0

        info_text = (
            f"总题数：{self.total}\n"
            f"已答题数：{self.answered}\n"
            f"正确数：{self.correct}\n"
            f"正确率：{correct_rate:.1f}%\n"
        )
        ttk.Label(frame, text=info_text, font=("Microsoft YaHei", 12),
                  justify="left").pack(anchor="w", pady=(0, 10))

        # 各题型统计
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=5)
        ttk.Label(frame, text="各题型正确率：",
                  font=("Microsoft YaHei", 10, "bold")).pack(anchor="w")

        type_stats = {"single": [0, 0], "multi": [0, 0], "fill": [0, 0]}
        for idx in self.indices:
            q = self.questions[idx]
            if q.qtype in type_stats:
                type_stats[q.qtype][0] += 1
                if self.records.get(idx, False):
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

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(20, 0))
        ttk.Button(btn_frame, text="📋 查看逐题详情",
                   command=self._show_details).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="关闭",
                   command=self.window.destroy).pack(side="right", padx=5)

    def _show_details(self):
        """显示逐题作答详情。"""
        for w in self.window.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.window, padding=15)
        frame.pack(fill="both", expand=True)

        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text="📋 逐题详情",
                  font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        ttk.Button(header, text="↩ 返回概览",
                   command=self._build_main).pack(side="right")
        ttk.Button(header, text="📤 导出TXT",
                   command=self._export_details).pack(side="right", padx=5)

        # 可滚动列表
        canvas = tk.Canvas(frame, height=350)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        detail_frame = ttk.Frame(canvas)
        detail_frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=detail_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        type_cn = {"single": "单选", "multi": "多选", "fill": "填空"}
        for i, idx in enumerate(self.indices):
            q = self.questions[idx]
            is_correct = self.records.get(idx, None)
            if is_correct is None:
                status = "⚪ 未作答"
            elif is_correct:
                status = "✅ 正确"
            else:
                status = "❌ 错误"

            row = ttk.Frame(detail_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{i+1}.", width=4,
                      font=("Consolas", 10)).pack(side="left")
            ttk.Label(row, text=f"[{type_cn.get(q.qtype, '?')}]",
                      width=8, font=("Microsoft YaHei", 9)).pack(side="left")
            preview = q.question[:40] + ("..." if len(q.question) > 40 else "")
            ttk.Label(row, text=preview, width=25,
                      font=("Microsoft YaHei", 9)).pack(side="left")
            ttk.Label(row, text=status, width=10,
                      font=("Microsoft YaHei", 9, "bold")).pack(side="left")
            correct_ans = q.get_answer_display()
            ttk.Label(row, text=f"答案: {correct_ans}",
                      font=("Microsoft YaHei", 8),
                      foreground="green").pack(side="left", padx=(5, 0))

    def _export_details(self):
        """导出逐题详情为 TXT。"""
        filepath = filedialog.asksaveasfilename(
            title="导出作答详情",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not filepath:
            return
        try:
            type_cn = {"single": "单选", "multi": "多选", "fill": "填空"}
            lines = ["逐题作答详情", "=" * 40, ""]
            for i, idx in enumerate(self.indices):
                q = self.questions[idx]
                is_correct = self.records.get(idx, None)
                if is_correct is None:
                    status = "未作答"
                elif is_correct:
                    status = "正确"
                else:
                    status = "错误"
                lines.append(
                    f"{i+1}. [{type_cn.get(q.qtype, '?')}] {q.question}")
                lines.append(f"   正确答案: {q.get_answer_display()}")
                lines.append(f"   结果: {status}")
                lines.append("")
            lines.append(f"总计: {self.correct}/{self.total} 正确")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("导出成功", f"详情已导出到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))


# ============================================================================

