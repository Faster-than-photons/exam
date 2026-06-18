import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from code.models import bank, config, BANKS_DIR, SingleChoiceQuestion, MultiChoiceQuestion, Question
from code.utils import center_window
from code.ui_practice import PracticeWindow
from code.ui_dialogs import ImportWindow, ExportWindow, QuestionEditWindow

class PracticeChoicePanel:
    """刷题选择面板 —— 选择正常刷题或错题本刷题，含设置入口。"""

    def __init__(self, parent, on_practice=None, on_wrong=None):
        self.parent = parent
        self.on_practice = on_practice
        self.on_wrong = on_wrong
        self.frame = ttk.Frame(parent)

        self._build_ui()

    def _build_ui(self):
        inner = ttk.Frame(self.frame)
        inner.pack(expand=True)

        ttk.Label(inner, text="📝 刷题模式",
                  font=("Microsoft YaHei", 18, "bold")).pack(pady=(0, 5))

        wrong_count = len(bank.get_wrong_indices())
        ttk.Label(inner, text=f"题库: {bank.active_name} | 错题: {wrong_count} 题",
                  font=("Microsoft YaHei", 10), foreground="gray").pack(pady=(0, 20))

        ttk.Button(inner, text="📝 正常刷题（全部题目）",
                   command=self._start_normal, width=30).pack(pady=5)
        ttk.Button(inner, text=f"📕 错题本刷题（{wrong_count} 题）",
                   command=self._start_wrong, width=30).pack(pady=5)

        # 设置区
        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=15)
        ttk.Label(inner, text="⚙ 刷题设置", font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", pady=(0, 5))

        set_frame = ttk.Frame(inner)
        set_frame.pack(fill="x", pady=5)
        ttk.Label(set_frame, text="刷题模式:").pack(side="left")
        self._mode_var = tk.StringVar(value=config.get("practice_mode"))
        ttk.Radiobutton(set_frame, text="随机", variable=self._mode_var,
                        value="random", command=self._save_settings).pack(side="left", padx=10)
        ttk.Radiobutton(set_frame, text="顺序", variable=self._mode_var,
                        value="sequential", command=self._save_settings).pack(side="left", padx=10)

        set_frame2 = ttk.Frame(inner)
        set_frame2.pack(fill="x", pady=5)
        self._answer_var = tk.BooleanVar(value=config.get("practice_show_answer"))
        ttk.Checkbutton(set_frame2, text="默认显示正确答案",
                        variable=self._answer_var,
                        command=self._save_settings).pack(side="left")

    def _save_settings(self):
        config.set("practice_mode", self._mode_var.get())
        config.set("practice_show_answer", self._answer_var.get())

    def _start_normal(self):
        if self.on_practice:
            self.on_practice()

    def _start_wrong(self):
        if self.on_wrong:
            self.on_wrong()


# ============================================================================
# 题库管理中心面板
# ============================================================================

class BankHubPanel:
    """题库管理中心 —— 整合题库切换、题目管理、导入导出。"""

    def __init__(self, parent, on_back=None, on_refresh=None):
        self.parent = parent
        self.on_back = on_back
        self.on_refresh = on_refresh
        self.frame = ttk.Frame(parent)

        self._build_ui()

    def _build_ui(self):
        # 顶部栏
        header = ttk.Frame(self.frame, padding=(10, 8))
        header.pack(fill="x")
        ttk.Label(header, text="📋 题库管理",
                  font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        ttk.Button(header, text="↩ 返回", command=self._go_back).pack(side="right", padx=3)
        ttk.Button(header, text="📥 导入TXT", command=self._import_txt).pack(side="right", padx=3)
        ttk.Button(header, text="📤 导出TXT", command=self._export_txt).pack(side="right", padx=3)
        ttk.Button(header, text="🔄 切换题库", command=self._switch_bank).pack(side="right", padx=3)

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x")

        # 内容区：左右分栏
        panes = ttk.Frame(self.frame)
        panes.pack(fill="both", expand=True)

        # 左栏：题目列表
        left = ttk.Frame(panes)
        left.pack(side="left", fill="both", expand=True)

        # 搜索栏
        search_frame = ttk.Frame(left, padding=5)
        search_frame.pack(fill="x")
        ttk.Label(search_frame, text="搜索:").pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._refresh_questions())
        ttk.Entry(search_frame, textvariable=self._search_var, width=25).pack(side="left", padx=5)
        ttk.Button(search_frame, text="+ 添加", command=self._add_question).pack(side="right", padx=2)
        ttk.Button(search_frame, text="✎ 编辑", command=self._edit_question).pack(side="right", padx=2)
        ttk.Button(search_frame, text="✕ 删除", command=self._delete_question).pack(side="right", padx=2)

        # 题目 Treeview
        tree_frame = ttk.Frame(left, padding=5)
        tree_frame.pack(fill="both", expand=True)
        columns = ("#", "type", "preview")
        self._qtree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self._qtree.heading("#", text="序号")
        self._qtree.heading("type", text="题型")
        self._qtree.heading("preview", text="题目预览")
        self._qtree.column("#", width=40, anchor="center", stretch=False)
        self._qtree.column("type", width=50, anchor="center", stretch=False)
        self._qtree.column("preview", width=350, stretch=True)
        qscroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._qtree.yview)
        self._qtree.configure(yscrollcommand=qscroll.set)
        self._qtree.pack(side="left", fill="both", expand=True)
        qscroll.pack(side="right", fill="y")
        self._qtree.bind("<Double-1>", lambda e: self._edit_question())

        # 右栏：题库列表
        right = ttk.Frame(panes, width=260)
        right.pack(side="right", fill="y", padx=(5, 0))
        right.pack_propagate(False)

        ttk.Label(right, text="题库列表", font=("Microsoft YaHei", 10, "bold")).pack(pady=(5, 3))
        self._blist = tk.Listbox(right, font=("Microsoft YaHei", 9), height=12)
        bscroll = ttk.Scrollbar(right, orient="vertical", command=self._blist.yview)
        self._blist.configure(yscrollcommand=bscroll.set)
        self._blist.pack(side="left", fill="both", expand=True)
        bscroll.pack(side="right", fill="y")

        btn_col = ttk.Frame(right)
        btn_col.pack(fill="x", pady=3)
        ttk.Button(btn_col, text="➕ 新建", command=self._create_bank).pack(fill="x", pady=1)
        ttk.Button(btn_col, text="📋 复制", command=self._copy_bank).pack(fill="x", pady=1)
        ttk.Button(btn_col, text="💾 导出JSON", command=self._export_bank).pack(fill="x", pady=1)
        ttk.Button(btn_col, text="📄 添加文件", command=self._add_file).pack(fill="x", pady=1)
        ttk.Button(btn_col, text="📂 扫描文件夹", command=self._scan_dir).pack(fill="x", pady=1)

        self._refresh_all()

    def _refresh_all(self):
        self._refresh_bank_list()
        self._refresh_questions()

    def _refresh_bank_list(self):
        self._blist.delete(0, "end")
        for name in bank.list_banks():
            marker = " ★" if name == bank.active_name else ""
            self._blist.insert("end", f"{name}{marker}")
            if name == bank.active_name:
                self._blist.selection_set(self._blist.size() - 1)

    def _refresh_questions(self):
        for item in self._qtree.get_children():
            self._qtree.delete(item)
        keyword = self._search_var.get().strip().lower()
        type_cn = {"single": "单选", "multi": "多选", "fill": "填空"}
        for i, q in enumerate(bank.questions):
            if keyword:
                st = q.question.lower()
                if isinstance(q, (SingleChoiceQuestion, MultiChoiceQuestion)):
                    st += " " + " ".join(o.lower() for o in q.options)
                if keyword not in st:
                    continue
            preview = q.question[:45] + ("..." if len(q.question) > 45 else "")
            self._qtree.insert("", "end", iid=str(i),
                               values=(i + 1, type_cn.get(q.qtype, q.qtype), preview))

    def _get_selected_q(self) -> int:
        sel = self._qtree.selection()
        return int(sel[0]) if sel else -1

    def _add_question(self):
        QuestionEditWindow(self.frame, on_save=self._refresh_questions)

    def _edit_question(self):
        idx = self._get_selected_q()
        if idx < 0:
            messagebox.showinfo("提示", "请先选择题目。")
            return
        QuestionEditWindow(self.frame, question=bank.questions[idx], index=idx, on_save=self._refresh_questions)

    def _delete_question(self):
        idx = self._get_selected_q()
        if idx < 0:
            return
        q = bank.questions[idx]
        if messagebox.askyesno("确认删除", f"删除: {q.get_short_info()}？"):
            del bank.questions[idx]
            bank.save()
            self._refresh_questions()

    def _switch_bank(self):
        sel = self._blist.curselection()
        if not sel:
            return
        name = self._blist.get(sel[0]).rstrip(" ★")
        bank.switch_bank(name)
        self._refresh_all()
        if self.on_refresh:
            self.on_refresh()

    def _create_bank(self):
        dialog = tk.Toplevel(self.frame)
        dialog.title("新建题库")
        dialog.resizable(False, False)
        center_window(dialog, 280, 120)
        ttk.Label(dialog, text="题库名称:", font=("Microsoft YaHei", 10)).pack(pady=(15, 5))
        name_var = tk.StringVar()
        e = ttk.Entry(dialog, textvariable=name_var, width=25)
        e.pack(pady=5)
        e.focus()
        def do():
            n = name_var.get().strip()
            if n and bank.create_bank(n):
                bank.switch_bank(n)
                dialog.destroy()
                self._refresh_all()
                if self.on_refresh:
                    self.on_refresh()
            else:
                messagebox.showwarning("警告", "名称无效或已存在。")
        ttk.Button(dialog, text="创建", command=do).pack(pady=(5, 10))
        e.bind("<Return>", lambda ev: do())

    def _copy_bank(self):
        from shutil import copyfile
        sel = self._blist.curselection()
        if not sel:
            return
        name = self._blist.get(sel[0]).rstrip(" ★")
        new_name = f"{name}_副本"
        n = 1
        while new_name in bank.list_banks():
            n += 1
            new_name = f"{name}_副本{n}"
        if bank.create_bank(new_name):
            src = bank._banks[name]
            dst = bank._banks[new_name]
            dst.questions = [q for q in src.questions]
            dst.wrong_book = dict(src.wrong_book)
            dst.save()
            dst.save_wrong_book()
            self._refresh_all()

    def _export_bank(self):
        sel = self._blist.curselection()
        if not sel:
            return
        name = self._blist.get(sel[0]).rstrip(" ★")
        fp = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not fp:
            return
        try:
            data = [q.to_dict() for q in bank._banks[name].questions]
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("导出成功", f"已导出到:\n{fp}")
        except Exception as e:
            messagebox.showerror("失败", str(e))

    def _add_file(self):
        fp = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if fp and bank.add_bank_from_file(fp):
            self._refresh_all()

    def _scan_dir(self):
        d = filedialog.askdirectory()
        if d:
            n = bank.scan_directory(d)
            if n > 0:
                self._refresh_all()
            messagebox.showinfo("扫描完成", f"添加了 {n} 个题库。")

    def _import_txt(self):
        ImportWindow(self.frame)

    def _export_txt(self):
        if not bank.questions:
            messagebox.showinfo("提示", "题库为空。")
            return
        ExportWindow(self.frame)

    def _go_back(self):
        if self.on_back:
            self.on_back()


# ============================================================================
# 统计面板
# ============================================================================

class StatisticsPanel:
    """统计面板 —— 嵌入内容区，含图表和导出。"""

    def __init__(self, parent):
        self.parent = parent
        self.frame = ttk.Frame(parent)
        self._build_ui()

    def _build_ui(self):
        header = ttk.Frame(self.frame, padding=(10, 8))
        header.pack(fill="x")
        ttk.Label(header, text="📊 统计信息",
                  font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        ttk.Button(header, text="📤 导出报告", command=self._export).pack(side="right")

        canvas = tk.Canvas(self.frame, height=340)
        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        stats = bank.get_statistics()
        ttk.Label(inner, text=f"题库: {bank.active_name} | 总题数: {stats['total']}",
                  font=("Microsoft YaHei", 10), padding=10).pack(anchor="w")
        ttk.Label(inner, text=f"单选: {stats['single']} | 多选: {stats['multi']} | 填空: {stats['fill']}",
                  font=("Microsoft YaHei", 9), padding=(0, 10)).pack(anchor="w")

        self._draw_bar(inner, stats)

        ttk.Separator(inner, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(inner, text="历史考试正确率趋势",
                  font=("Microsoft YaHei", 10, "bold"), padding=10).pack(anchor="w")

        if bank.history:
            self._draw_trend(inner)
            rates = [r["correct"] / r["total"] * 100 if r["total"] > 0 else 0 for r in bank.history]
            avg = sum(rates) / len(rates)
            ttk.Label(inner, text=f"平均正确率: {avg:.1f}%（{len(bank.history)} 次）",
                      font=("Microsoft YaHei", 10), padding=10).pack(anchor="w")
        else:
            ttk.Label(inner, text="暂无考试记录。", foreground="gray", padding=10).pack(anchor="w")

    def _draw_bar(self, parent, stats):
        c = tk.Canvas(parent, width=380, height=130, bg="white", highlightthickness=1, highlightbackground="#ddd")
        c.pack(pady=5)
        labels = ["单选题", "多选题", "填空题"]
        values = [stats["single"], stats["multi"], stats["fill"]]
        colors = ["#4CAF50", "#2196F3", "#FF9800"]
        mv = max(values) if max(values) > 0 else 1
        bw, sx, by = 80, 45, 110
        for i, (lb, vl, cl) in enumerate(zip(labels, values, colors)):
            x = sx + i * (bw + 35)
            h = vl / mv * 90
            c.create_rectangle(x, by - h, x + bw, by, fill=cl, outline="")
            c.create_text(x + bw / 2, by - h - 10, text=str(vl), font=("Microsoft YaHei", 9, "bold"))
            c.create_text(x + bw / 2, by + 12, text=lb, font=("Microsoft YaHei", 9))

    def _draw_trend(self, parent):
        c = tk.Canvas(parent, width=380, height=120, bg="white", highlightthickness=1, highlightbackground="#ddd")
        c.pack(pady=5)
        rates = [r["correct"] / r["total"] * 100 if r["total"] > 0 else 0 for r in bank.history[-10:]]
        if not rates:
            return
        by, ch = 100, 70
        mr, mn = max(rates), min(rates)
        if mr == mn:
            mr = mn + 10
        n = len(rates)
        if n < 2:
            c.create_text(190, 60, text=f"正确率: {rates[0]:.1f}%", font=("Microsoft YaHei", 11, "bold"))
            return
        step = 340 / (n - 1)
        pts = []
        for i, r in enumerate(rates):
            x, y = 20 + i * step, by - (r - mn) / (mr - mn) * ch
            pts.append((x, y))
            c.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#E91E63", outline="")
            c.create_text(x, by + 10, text=f"{r:.0f}%", font=("Microsoft YaHei", 7))
        for i in range(len(pts) - 1):
            c.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], fill="#E91E63", width=2)

    def _export(self):
        fp = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("文本", "*.txt")])
        if not fp:
            return
        try:
            stats = bank.get_statistics()
            lines = ["统计报告", f"题库: {bank.active_name}", f"总题数: {stats['total']}",
                     f"单选: {stats['single']} 多选: {stats['multi']} 填空: {stats['fill']}", ""]
            for r in bank.history:
                rate = r["correct"] / r["total"] * 100 if r["total"] > 0 else 0
                lines.append(f"{r.get('date', '?')} | {r['total']}题 | {r['correct']}对 | {rate:.1f}%")
            with open(fp, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("导出成功", f"已导出到:\n{fp}")
        except Exception as e:
            messagebox.showerror("失败", str(e))


# ============================================================================
# 设置面板（嵌入主窗口）
# ============================================================================

class SettingsPanel:
    """设置面板 —— 修改用户偏好配置。"""

    def __init__(self, parent, on_back=None):
        self.parent = parent
        self.on_back = on_back
        self.frame = ttk.Frame(parent)

        self._build_ui()

    def _build_ui(self):
        header = ttk.Frame(self.frame, padding=(15, 10))
        header.pack(fill="x")
        ttk.Label(header, text="⚙ 设置",
                  font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        ttk.Button(header, text="↩ 返回主菜单",
                   command=self._go_back).pack(side="right")

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=10)

        form = ttk.Frame(self.frame, padding=20)
        form.pack(fill="both", expand=True)

        row1 = ttk.Frame(form)
        row1.pack(fill="x", pady=8)
        ttk.Label(row1, text="默认刷题模式:", width=18).pack(side="left")
        self._mode_var = tk.StringVar(value=config.get("practice_mode"))
        ttk.Radiobutton(row1, text="随机", variable=self._mode_var,
                        value="random").pack(side="left", padx=10)
        ttk.Radiobutton(row1, text="顺序", variable=self._mode_var,
                        value="sequential").pack(side="left", padx=10)

        row2 = ttk.Frame(form)
        row2.pack(fill="x", pady=8)
        ttk.Label(row2, text="默认显示答案:", width=18).pack(side="left")
        self._answer_var = tk.BooleanVar(value=config.get("practice_show_answer"))
        ttk.Checkbutton(row2, text="刷题时默认显示正确答案",
                        variable=self._answer_var).pack(side="left", padx=10)

        row3 = ttk.Frame(form)
        row3.pack(fill="x", pady=8)
        ttk.Label(row3, text="默认考试时长(分):", width=18).pack(side="left")
        self._duration_var = tk.IntVar(value=config.get("exam_default_duration"))
        ttk.Spinbox(row3, from_=1, to=180, textvariable=self._duration_var,
                     width=6).pack(side="left", padx=10)

        ttk.Separator(form, orient="horizontal").pack(fill="x", pady=15)
        ttk.Label(form, text="快捷键: Ctrl+1~8 切换功能 | Ctrl+W 返回主菜单",
                  font=("Microsoft YaHei", 9),
                  foreground="gray").pack(anchor="w")

        ttk.Button(form, text="💾 保存设置",
                   command=self._save).pack(pady=(20, 0))

    def _save(self):
        config.set("practice_mode", self._mode_var.get())
        config.set("practice_show_answer", self._answer_var.get())
        config.set("exam_default_duration", self._duration_var.get())
        messagebox.showinfo("保存成功", "设置已保存，下次启动生效。")

    def _go_back(self):
        if self.on_back:
            self.on_back()


# ============================================================================
# 错题本面板（嵌入主窗口）
# ============================================================================

class WrongBookPanel:
    """错题本面板 —— 显示错题统计、支持删除错题、启动错题刷题。"""

    def __init__(self, parent, on_back=None):
        self.parent = parent
        self.on_back = on_back
        self.frame = ttk.Frame(parent)

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        # 顶部标题栏
        header = ttk.Frame(self.frame, padding=(15, 10))
        header.pack(fill="x")
        ttk.Label(header, text="📕 错题本",
                  font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        ttk.Button(header, text="↩ 返回主菜单",
                   command=self._go_back).pack(side="right")
        ttk.Button(header, text="🧹 清空错题本",
                   command=self._clear_all).pack(side="right", padx=5)

        # 统计信息
        self._stats_label = ttk.Label(self.frame, text="", font=("Microsoft YaHei", 10),
                                      padding=(15, 5))
        self._stats_label.pack(anchor="w")

        ttk.Separator(self.frame, orient="horizontal").pack(fill="x", padx=10)

        # Treeview 错题列表
        tree_frame = ttk.Frame(self.frame, padding=10)
        tree_frame.pack(fill="both", expand=True)

        columns = ("question", "type", "wrong_count")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                   selectmode="extended")
        self._tree.heading("question", text="题目")
        self._tree.heading("type", text="题型")
        self._tree.heading("wrong_count", text="错误次数")
        self._tree.column("question", width=400, stretch=True)
        self._tree.column("type", width=60, anchor="center", stretch=False)
        self._tree.column("wrong_count", width=70, anchor="center", stretch=False)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical",
                                   command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 底部操作栏
        bottom = ttk.Frame(self.frame, padding=(15, 10))
        bottom.pack(fill="x", side="bottom")

        self._selection_label = ttk.Label(bottom, text="", font=("Microsoft YaHei", 9),
                                          foreground="gray")
        self._selection_label.pack(side="left")

        ttk.Button(bottom, text="🗑 从错题本移除",
                   command=self._remove_selected).pack(side="right", padx=5)
        ttk.Button(bottom, text="📝 刷错题",
                   command=self._practice_wrong).pack(side="right", padx=5)

        # 绑定选择事件
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

    def _refresh(self):
        """刷新错题列表。"""
        for item in self._tree.get_children():
            self._tree.delete(item)

        wrong_indices = bank.get_wrong_indices()
        type_cn = {"single": "单选", "multi": "多选", "fill": "填空"}

        for idx in wrong_indices:
            if idx >= len(bank.questions):
                continue
            q = bank.questions[idx]
            wc = bank.get_wrong_count(idx)
            preview = q.question[:55] + ("..." if len(q.question) > 55 else "")
            self._tree.insert("", "end", iid=str(idx),
                              values=(preview, type_cn.get(q.qtype, q.qtype), wc))

        total = len(wrong_indices)
        self._stats_label.config(
            text=f"错题总数: {total}   |   题库: {bank.active_name}")
        self._selection_label.config(text=f"共 {total} 道错题")

    def _on_select(self, event=None):
        sel = self._tree.selection()
        self._selection_label.config(text=f"已选中 {len(sel)} 道题")

    def _remove_selected(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中要移除的错题。")
            return
        for iid in sel:
            idx = int(iid)
            bank._active_bank.wrong_book.pop(idx, None)
        bank._active_bank.save_wrong_book()
        self._refresh()

    def _clear_all(self):
        if not bank.get_wrong_indices():
            messagebox.showinfo("提示", "错题本已为空。")
            return
        if messagebox.askyesno("确认清空", "确定要清空整个错题本吗？此操作不可撤销。"):
            bank._active_bank.wrong_book.clear()
            bank._active_bank.save_wrong_book()
            self._refresh()

    def _practice_wrong(self):
        wrong_indices = bank.get_wrong_indices()
        if not wrong_indices:
            messagebox.showinfo("提示", "错题本为空，没有错题可刷。")
            return
        wrong_questions = [bank.questions[i] for i in wrong_indices if i < len(bank.questions)]
        if not wrong_questions:
            messagebox.showinfo("提示", "错题对应的题目已不存在。")
            return
        # 获取顶层窗口
        top = self.frame.winfo_toplevel()
        top.withdraw()
        PracticeWindow(top, wrong_questions,
                       indices_map=wrong_indices, mode_name="错题本刷题")

    def _go_back(self):
        if self.on_back:
            self.on_back()


# ============================================================================

