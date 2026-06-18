import tkinter as tk
from tkinter import ttk, messagebox
from code.models import bank, config, SingleChoiceQuestion, MultiChoiceQuestion, Question
from code.utils import center_window
from code.ui_panels import PracticeChoicePanel, BankHubPanel, StatisticsPanel, WrongBookPanel
from code.ui_practice import PracticeWindow
from code.ui_exam import ExamSetupWindow

class MainApp:
    """程序主窗口 —— 左侧竖向菜单栏 + 右侧内容区，支持紧凑/大型双布局。"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("刷题与考试系统")
        self.root.resizable(True, True)
        center_window(self.root, 900, 600)
        self.root.minsize(600, 450)
        self._layout_mode = None
        self._current_panel = None
        self._sidebar_collapsed = False  # 紧凑模式：仅图标

        self._build_ui()
        self.root.update_idletasks()
        self._update_layout()
        self.root.bind("<Configure>", self._on_resize)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # 默认显示刷题面板
        self._show_default()

    # ---------- 界面构建 ----------

    def _build_ui(self):
        """构建侧边栏 + 内容区布局。"""
        # === 左侧侧边栏 ===
        self._sidebar = tk.Frame(self.root, bg="#2c3e50", width=160)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # 统计图标（顶部）
        stats_btn = tk.Button(self._sidebar, text="📊", font=("Microsoft YaHei", 16),
                              bg="#2c3e50", fg="white", bd=0, activebackground="#34495e",
                              command=self._open_statistics, cursor="hand2")
        stats_btn.pack(pady=(10, 5))

        # 分隔线
        sep1 = tk.Frame(self._sidebar, height=1, bg="#4a6785")
        sep1.pack(fill="x", padx=15, pady=5)

        # 主功能按钮（大字）
        self._sidebar_btns = []
        menu_items = [
            ("📝\n刷题模式", self._open_practice),
            ("⏱\n考试模式", self._open_exam_setup),
            ("📕\n错题本", self._open_wrong_book),
            ("📋\n题库管理", self._open_bank_hub),
        ]
        for text, cmd in menu_items:
            btn = tk.Button(self._sidebar, text=text, font=("Microsoft YaHei", 11, "bold"),
                            bg="#2c3e50", fg="white", bd=0, activebackground="#34495e",
                            compound="top", padx=10, pady=10,
                            command=cmd, cursor="hand2")
            btn.pack(fill="x", padx=8, pady=3)
            self._sidebar_btns.append(btn)

        # 弹性空间
        spacer = tk.Frame(self._sidebar, bg="#2c3e50")
        spacer.pack(fill="both", expand=True)

        # 退出图标（底部）
        exit_btn = tk.Button(self._sidebar, text="🚪", font=("Microsoft YaHei", 16),
                             bg="#2c3e50", fg="#e74c3c", bd=0, activebackground="#34495e",
                             command=self._on_close, cursor="hand2")
        exit_btn.pack(pady=(5, 15))

        # === 右侧内容区 ===
        self._content_area = ttk.Frame(self.root)
        self._content_area.pack(side="left", fill="both", expand=True)

        # 题库信息条（顶部）
        self._info_bar = ttk.Frame(self._content_area)
        self._info_bar.pack(fill="x")
        self._bank_label = ttk.Label(self._info_bar, text="", font=("Microsoft YaHei", 9),
                                     padding=(10, 5))
        self._bank_label.pack(side="left")
        self._stats_label = ttk.Label(self._info_bar, text="", font=("Microsoft YaHei", 9),
                                      foreground="gray")
        self._stats_label.pack(side="left", padx=(5, 0))
        ttk.Separator(self._content_area, orient="horizontal").pack(fill="x")
        self._refresh_bank_info()

        # 键盘快捷键
        self.root.bind("<Control-Key-1>", lambda e: self._open_practice())
        self.root.bind("<Control-Key-2>", lambda e: self._open_exam_setup())
        self.root.bind("<Control-Key-3>", lambda e: self._open_wrong_book())
        self.root.bind("<Control-Key-4>", lambda e: self._open_bank_hub())
        self.root.bind("<Control-Key-5>", lambda e: self._open_statistics())
        self.root.bind("<Control-Key-6>", lambda e: self._on_close())
        self.root.bind("<Control-Key-w>", lambda e: self._show_default())

    # ---------- 面板切换 ----------

    def _show_panel(self, panel_frame):
        if self._current_panel:
            self._current_panel.pack_forget()
        panel_frame.pack(fill="both", expand=True)
        self._current_panel = panel_frame

    def _show_default(self):
        """返回默认视图（刷题选择面板）。"""
        if self._current_panel:
            self._current_panel.pack_forget()
            self._current_panel = None
        self._open_practice()

    def _refresh_bank_info(self):
        stats = bank.get_statistics()
        self._bank_label.config(text=f"📁 {bank.active_name}")
        self._stats_label.config(
            text=f"共 {stats['total']} 题（单选 {stats['single']} | 多选 {stats['multi']} | 填空 {stats['fill']}）")

    # ---------- 自适应布局 ----------

    def _on_resize(self, event=None):
        if event and event.widget is not self.root:
            return
        self._update_layout()

    def _update_layout(self):
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        if w < 50 or h < 50:
            return
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        threshold = screen_w * screen_h / 3
        new_mode = "large" if w * h >= threshold else "compact"

        if new_mode != self._layout_mode:
            self._layout_mode = new_mode
            if new_mode == "compact":
                self._apply_compact()
            else:
                self._apply_large()

    def _apply_compact(self):
        """紧凑模式：侧边栏仅图标（60px 宽），文字隐藏。"""
        self._sidebar.configure(width=60)
        for btn in self._sidebar_btns:
            # 只保留第一行（图标）
            icon = btn.cget("text").split("\n")[0]
            btn.configure(text=icon, font=("Microsoft YaHei", 14, "bold"),
                          padx=5, pady=8)
        self._bank_label.configure(font=("Microsoft YaHei", 8))

    def _apply_large(self):
        """大型模式：侧边栏展开（图标+文字，160px 宽）。"""
        self._sidebar.configure(width=160)
        texts = ["📝\n刷题模式", "⏱\n考试模式", "📕\n错题本", "📋\n题库管理"]
        for btn, text in zip(self._sidebar_btns, texts):
            btn.configure(text=text, font=("Microsoft YaHei", 11, "bold"),
                          padx=10, pady=10)
        self._bank_label.configure(font=("Microsoft YaHei", 9))

    # ---------- 各功能入口 ----------

    def _open_practice(self):
        if not bank.questions:
            messagebox.showinfo("提示", "题库为空，请先导入或添加题目！")
            return

        panel = PracticeChoicePanel(self._content_area,
                                     on_practice=self._start_practice,
                                     on_wrong=self._start_practice_wrong)
        self._show_panel(panel.frame)

    def _start_practice(self):
        self.root.withdraw()
        PracticeWindow(self.root, bank.questions)

    def _start_practice_wrong(self):
        wrong_indices = bank.get_wrong_indices()
        if not wrong_indices:
            messagebox.showinfo("提示", "错题本为空。")
            return
        wrong_questions = [bank.questions[i] for i in wrong_indices if i < len(bank.questions)]
        self.root.withdraw()
        PracticeWindow(self.root, wrong_questions, indices_map=wrong_indices, mode_name="错题本刷题")

    def _open_exam_setup(self):
        if not bank.questions:
            messagebox.showinfo("提示", "题库为空，请先导入或添加题目！")
            return
        self.root.withdraw()
        ExamSetupWindow(self.root)

    def _open_wrong_book(self):
        panel = WrongBookPanel(self._content_area, on_back=lambda: self._show_default())
        self._show_panel(panel.frame)

    def _open_bank_hub(self):
        """打开题库管理中心（合并面板）。"""
        panel = BankHubPanel(self._content_area, on_back=lambda: self._show_default(),
                             on_refresh=self._refresh_bank_info)
        self._show_panel(panel.frame)

    def _open_statistics(self):
        panel = StatisticsPanel(self._content_area)
        self._show_panel(panel.frame)

    def _on_close(self):
        bank.save()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ============================================================================
# 刷题选择面板
# ============================================================================


