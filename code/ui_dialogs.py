import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime
from code.models import bank, Question, SingleChoiceQuestion, MultiChoiceQuestion, FillInBlankQuestion, QuestionBank
from code.utils import center_window

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
                      text="题目中用 {1}、{2}... 表示填空位置",
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
# 题库切换/管理窗口
# ============================================================================

class BankSwitchWindow:
    """题库管理窗口 —— 切换、创建、删除、重命名题库。"""

    def __init__(self, parent, callback=None):
        self.parent = parent
        self.callback = callback
        self.window = tk.Toplevel(parent)
        self.window.title("题库管理")
        self.window.resizable(False, False)
        center_window(self.window, 450, 530)
        self.window.focus_force()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=15)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="📁 题库管理",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 10))

        # 题库列表
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="both", expand=True, pady=5)

        self._listbox = tk.Listbox(list_frame, font=("Microsoft YaHei", 10),
                                   selectmode="single", height=8)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                   command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._refresh_list()

        # 操作按钮
        btn_row1 = ttk.Frame(frame)
        btn_row1.pack(fill="x", pady=(10, 3))
        ttk.Button(btn_row1, text="✅ 切换到选中题库",
                   command=self._switch_to).pack(side="left", padx=2)
        ttk.Button(btn_row1, text="📝 重命名",
                   command=self._rename).pack(side="left", padx=2)

        btn_row2 = ttk.Frame(frame)
        btn_row2.pack(fill="x", pady=3)
        ttk.Button(btn_row2, text="➕ 创建新题库",
                   command=self._create).pack(side="left", padx=2)
        ttk.Button(btn_row2, text="� 复制题库",
                   command=self._copy_bank).pack(side="left", padx=2)
        ttk.Button(btn_row2, text="🗑 删除选中题库",
                   command=self._delete).pack(side="left", padx=2)

        btn_row2b = ttk.Frame(frame)
        btn_row2b.pack(fill="x", pady=3)
        ttk.Button(btn_row2b, text="💾 导出题库JSON...",
                   command=self._export_bank).pack(side="left", padx=2)

        # 外部题库导入按钮
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=(8, 5))
        ttk.Label(frame, text="从外部导入题库文件:",
                  font=("Microsoft YaHei", 9),
                  foreground="gray").pack(anchor="w", pady=(0, 3))
        btn_row3 = ttk.Frame(frame)
        btn_row3.pack(fill="x", pady=2)
        ttk.Button(btn_row3, text="📄 添加题库文件...",
                   command=self._add_file).pack(side="left", padx=2)
        ttk.Button(btn_row3, text="📂 扫描文件夹...",
                   command=self._scan_dir).pack(side="left", padx=2)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)
        ttk.Button(frame, text="返回主菜单", command=self._on_close).pack()

    def _refresh_list(self):
        self._listbox.delete(0, "end")
        for name in bank.list_banks():
            marker = " ★" if name == bank.active_name else ""
            self._listbox.insert("end", f"{name}{marker}")
            if name == bank.active_name:
                self._listbox.selection_set(self._listbox.size() - 1)

    def _get_selected_name(self) -> str:
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个题库。")
            return ""
        text = self._listbox.get(sel[0])
        return text.rstrip(" ★")

    def _switch_to(self):
        name = self._get_selected_name()
        if not name:
            return
        bank.switch_bank(name)
        self._refresh_list()
        messagebox.showinfo("切换成功", f"已切换到题库「{name}」。")

    def _create(self):
        dialog = tk.Toplevel(self.window)
        dialog.title("创建新题库")
        dialog.resizable(False, False)
        center_window(dialog, 300, 130)
        dialog.focus_force()

        ttk.Label(dialog, text="请输入新题库名称:",
                  font=("Microsoft YaHei", 10)).pack(pady=(15, 5))
        name_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=name_var, width=25)
        entry.pack(pady=5)
        entry.focus()

        def do_create():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("警告", "名称不能为空！")
                return
            if not bank.create_bank(name):
                messagebox.showwarning("警告", f"题库「{name}」已存在！")
                return
            dialog.destroy()
            bank.switch_bank(name)
            self._refresh_list()
            messagebox.showinfo("创建成功", f"题库「{name}」已创建并切换。")

        ttk.Button(dialog, text="创建", command=do_create).pack(pady=(5, 10))
        entry.bind("<Return>", lambda e: do_create())

    def _rename(self):
        name = self._get_selected_name()
        if not name:
            return

        dialog = tk.Toplevel(self.window)
        dialog.title("重命名题库")
        dialog.resizable(False, False)
        center_window(dialog, 300, 130)
        dialog.focus_force()

        ttk.Label(dialog, text=f"将「{name}」重命名为:",
                  font=("Microsoft YaHei", 10)).pack(pady=(15, 5))
        name_var = tk.StringVar(value=name)
        entry = ttk.Entry(dialog, textvariable=name_var, width=25)
        entry.pack(pady=5)
        entry.focus()
        entry.select_range(0, "end")

        def do_rename():
            new_name = name_var.get().strip()
            if not new_name:
                return
            if bank.rename_bank(name, new_name):
                dialog.destroy()
                self._refresh_list()
            else:
                messagebox.showwarning("警告", f"重命名失败，名称「{new_name}」可能已存在。")

        ttk.Button(dialog, text="确认", command=do_rename).pack(pady=(5, 10))
        entry.bind("<Return>", lambda e: do_rename())

    def _delete(self):
        name = self._get_selected_name()
        if not name:
            return
        if name == bank.active_name:
            messagebox.showwarning("警告", "不能删除当前正在使用的题库，请先切换到其他题库。")
            return
        if len(bank.list_banks()) <= 1:
            messagebox.showwarning("警告", "至少保留一个题库。")
            return
        if messagebox.askyesno("确认删除",
                               f"确定要删除题库「{name}」吗？\n此操作不可撤销！"):
            if bank.delete_bank(name):
                self._refresh_list()
                messagebox.showinfo("删除成功", f"题库「{name}」已删除。")

    def _copy_bank(self):
        """复制选中的题库。"""
        name = self._get_selected_name()
        if not name:
            return
        new_name = f"{name}_副本"
        n = 1
        while new_name in bank.list_banks():
            n += 1
            new_name = f"{name}_副本{n}"
        if not bank.create_bank(new_name):
            messagebox.showwarning("失败", "创建副本失败。")
            return
        # 复制所有题目
        src = bank._banks[name]
        dst = bank._banks[new_name]
        dst.questions = [q for q in src.questions]  # 浅拷贝（题目对象不可变）
        # 复制错题本
        dst.wrong_book = dict(src.wrong_book)
        dst.save()
        dst.save_wrong_book()
        self._refresh_list()
        messagebox.showinfo("复制成功", f"题库「{name}」已复制为「{new_name}」。")

    def _export_bank(self):
        """导出选中题库为独立 JSON 文件。"""
        name = self._get_selected_name()
        if not name:
            return
        filepath = filedialog.asksaveasfilename(
            title=f"导出题库「{name}」",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if not filepath:
            return
        try:
            qb = bank._banks[name]
            data = [q.to_dict() for q in qb.questions]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("导出成功", f"题库「{name}」已导出到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _add_file(self):
        """添加外部题库 JSON 文件。"""
        filepath = filedialog.askopenfilename(
            title="选择题库 JSON 文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if not filepath:
            return
        if bank.add_bank_from_file(filepath):
            self._refresh_list()
            name = os.path.splitext(os.path.basename(filepath))[0]
            messagebox.showinfo("添加成功", f"已添加题库「{name}」。")
        else:
            messagebox.showwarning("失败", "无法添加该题库文件，请检查文件是否有效。")

    def _scan_dir(self):
        """扫描文件夹中的所有题库 JSON 文件。"""
        dirpath = filedialog.askdirectory(title="选择题库文件夹")
        if not dirpath:
            return
        count = bank.scan_directory(dirpath)
        if count > 0:
            self._refresh_list()
            messagebox.showinfo("扫描完成", f"从文件夹中发现并添加了 {count} 个题库。")
        else:
            messagebox.showinfo("扫描完成", "未在文件夹中发现有效题库文件。")

    def _on_close(self):
        bank.save()
        self.window.destroy()
        if self.callback:
            self.callback()


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
        center_window(self.window, 580, 520)
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

        # 目标题库选择
        target_frame = ttk.LabelFrame(frame, text="导入目标", padding=8)
        target_frame.pack(fill="x", pady=(0, 10))

        self._import_mode = tk.StringVar(value="current")
        ttk.Radiobutton(target_frame, text=f"添加到当前题库「{bank.active_name}」",
                        variable=self._import_mode, value="current").pack(anchor="w")
        ttk.Radiobutton(target_frame, text="创建新题库并导入",
                        variable=self._import_mode, value="new").pack(anchor="w")
        # 已有题库下拉
        exist_frame = ttk.Frame(target_frame)
        exist_frame.pack(fill="x", pady=(5, 0))
        ttk.Radiobutton(exist_frame, text="添加到已有题库:",
                        variable=self._import_mode, value="existing").pack(side="left")
        other_names = [n for n in bank.list_banks() if n != bank.active_name]
        self._target_combo = ttk.Combobox(exist_frame, values=other_names,
                                           state="readonly", width=18)
        self._target_combo.pack(side="left", padx=5)
        if other_names:
            self._target_combo.current(0)

        ttk.Button(frame, text="从 TXT 文件导入...",
                   command=self._from_file).pack(fill="x", pady=5)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(frame, text="或直接在下方粘贴题目文本：",
                  font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(0, 5))

        self.text_area = scrolledtext.ScrolledText(frame, height=10, width=60)
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
  • 答案行使用中文「答案:」，不区分中英文冒号

──────────────────────────────────────────────
  1. 单选题
──────────────────────────────────────────────
  1.(单选题)中国的首都是？
  A. 上海
  B. 北京
  C. 广州
  D. 深圳
  答案: B

  说明:
  - 选项以 A. B. C. D. 开头（支持任意数量选项）
  - 答案: 后填正确选项字母（大小写均可）

──────────────────────────────────────────────
  2. 多选题
──────────────────────────────────────────────
  2.(多选题)以下哪些是编程语言？
  A. Python
  B. Java
  C. 中文
  D. C++
  答案: ABD

  说明:
  - 答案以连续字母形式书写（如 ABD），不加逗号
  - 所有正确选项必须全选对才得分

──────────────────────────────────────────────
  3. 填空题
──────────────────────────────────────────────
  3.(填空题)世界上最高的山峰是 {1}，海拔 {2} 米。
  空1: 珠穆朗玛峰,珠峰
  空2: 8848.86,8848

  说明:
  - 题目中用 {1}、{2}... 标记填空位置
  - 空1 对应 {1}，空2 对应 {2}，从 1 开始编号
  - 多个可接受答案用逗号分隔，匹配任一即可

══════════════════════════════════════════════════
  完整示例（3 道题，注意题间空行）
══════════════════════════════════════════════════
  1.(单选题)Python 的作者是？
  A. Guido van Rossum
  B. Dennis Ritchie
  C. James Gosling
  D. Bjarne Stroustrup
  答案: A

  2.(多选题)以下哪些是Python标准库？
  A. os
  B. json
  C. numpy
  D. random
  答案: ABD

  3.(填空题)Python 中表示空值的常量是 {1}。
  空1: None,none
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

        # 确定目标题库
        mode = self._import_mode.get()
        if mode == "new":
            # 创建新题库
            new_name = f"导入题库_{datetime.now().strftime('%m%d_%H%M')}"
            while new_name in bank.list_banks():
                new_name = f"导入题库_{datetime.now().strftime('%m%d_%H%M%S')}"
            bank.create_bank(new_name)
            bank.switch_bank(new_name)
            bank.questions.extend(parsed)
            bank.save()
            messagebox.showinfo("导入成功",
                                f"已创建题库「{new_name}」并导入 {len(parsed)} 道题目！")
        elif mode == "existing":
            target = self._target_combo.get()
            if not target:
                messagebox.showwarning("警告", "请选择一个已有题库。")
                return
            # 临时切换以添加题目
            prev = bank.active_name
            bank.switch_bank(target)
            bank.questions.extend(parsed)
            bank.save()
            if target != prev:
                bank.switch_bank(prev)
            messagebox.showinfo("导入成功",
                                f"已向题库「{target}」导入 {len(parsed)} 道题目！")
        else:
            # 添加到当前题库
            bank.questions.extend(parsed)
            bank.save()
            messagebox.showinfo("导入成功",
                                f"已向当前题库导入 {len(parsed)} 道题目！")
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
    """查看统计窗口 —— 含条形图和趋势图。"""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("统计信息")
        self.window.resizable(False, False)
        center_window(self.window, 500, 600)
        self.window.focus_force()

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.window, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="📊 统计信息",
                  font=("Microsoft YaHei", 14, "bold")).pack(pady=(0, 10))

        stats = bank.get_statistics()

        # 题库统计
        ttk.Label(frame, text="── 题库分布 ──",
                  font=("Microsoft YaHei", 10, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"总题数: {stats['total']}（单选 {stats['single']} | 多选 {stats['multi']} | 填空 {stats['fill']}）",
                  font=("Microsoft YaHei", 10)).pack(anchor="w", pady=(0, 5))

        # 条形图
        self._draw_bar_chart(frame, stats)

        # 历史成绩
        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(frame, text="── 历史考试成绩 ──",
                  font=("Microsoft YaHei", 10, "bold")).pack(anchor="w")

        if not bank.history:
            ttk.Label(frame, text="暂无考试记录。",
                      font=("Microsoft YaHei", 10),
                      foreground="gray").pack(anchor="w", pady=5)
        else:
            self._draw_trend_chart(frame)

            avg_rate = sum(
                r["correct"] / r["total"] * 100 if r["total"] > 0 else 0
                for r in bank.history
            ) / len(bank.history)
            ttk.Label(frame,
                      text=f"平均正确率: {avg_rate:.1f}%（{len(bank.history)} 次）",
                      font=("Microsoft YaHei", 10, "bold")
                      ).pack(anchor="w", pady=(5, 0))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_frame, text="📤 导出统计报告",
                   command=self._export_report).pack(side="left")
        ttk.Button(btn_frame, text="关闭",
                   command=self.window.destroy).pack(side="right")

    def _draw_bar_chart(self, parent, stats):
        """绘制题型分布条形图。"""
        canvas = tk.Canvas(parent, width=440, height=150, bg="white",
                           highlightthickness=1, highlightbackground="#ddd")
        canvas.pack(pady=5)

        labels = ["单选题", "多选题", "填空题"]
        values = [stats["single"], stats["multi"], stats["fill"]]
        colors = ["#4CAF50", "#2196F3", "#FF9800"]
        max_val = max(values) if max(values) > 0 else 1
        bar_w, start_x, base_y = 100, 50, 130

        for i, (label, val, color) in enumerate(zip(labels, values, colors)):
            x = start_x + i * (bar_w + 30)
            h = val / max_val * 100
            canvas.create_rectangle(x, base_y - h, x + bar_w, base_y,
                                    fill=color, outline="")
            canvas.create_text(x + bar_w / 2, base_y - h - 10,
                               text=str(val), font=("Microsoft YaHei", 9, "bold"))
            canvas.create_text(x + bar_w / 2, base_y + 10,
                               text=label, font=("Microsoft YaHei", 9))

    def _draw_trend_chart(self, parent):
        """绘制历史正确率趋势折线图。"""
        canvas = tk.Canvas(parent, width=440, height=130, bg="white",
                           highlightthickness=1, highlightbackground="#ddd")
        canvas.pack(pady=5)

        rates = [r["correct"] / r["total"] * 100 if r["total"] > 0 else 0
                 for r in bank.history[-10:]]  # 最近 10 次
        if not rates:
            return

        base_y, chart_h = 110, 80
        max_r, min_r = max(rates), min(rates)
        if max_r == min_r:
            max_r = min_r + 10

        n = len(rates)
        if n < 2:
            canvas.create_text(220, 65, text=f"正确率: {rates[0]:.1f}%",
                               font=("Microsoft YaHei", 11, "bold"))
            return

        step_x = 400 / (n - 1)
        points = []
        for i, r in enumerate(rates):
            x = 20 + i * step_x
            y = base_y - (r - min_r) / (max_r - min_r) * chart_h
            points.append((x, y))
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#E91E63", outline="")
            canvas.create_text(x, base_y + 10, text=f"{r:.0f}%",
                               font=("Microsoft YaHei", 7))

        for i in range(len(points) - 1):
            canvas.create_line(points[i][0], points[i][1],
                               points[i+1][0], points[i+1][1],
                               fill="#E91E63", width=2)

    def _export_report(self):
        """导出统计报告为 TXT。"""
        filepath = filedialog.asksaveasfilename(
            title="导出统计报告",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not filepath:
            return
        try:
            stats = bank.get_statistics()
            lines = ["统计报告", "=" * 40, "",
                     f"题库: {bank.active_name}",
                     f"总题数: {stats['total']}",
                     f"单选题: {stats['single']}",
                     f"多选题: {stats['multi']}",
                     f"填空题: {stats['fill']}",
                     "", "历史考试成绩:", "-" * 30]
            for r in bank.history:
                rate = r["correct"] / r["total"] * 100 if r["total"] > 0 else 0
                lines.append(f"  {r.get('date', '?')} | {r['total']}题 | "
                             f"{r['correct']}对 | {rate:.1f}%")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("导出成功", f"报告已导出到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))


# ============================================================================

