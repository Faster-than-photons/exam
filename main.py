#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 GUI 刷题与考试程序 — 主入口 (v3.0.0)
===============================================================================

 功能模块: code/
   - models.py     题型数据模型 + 题库管理 + 配置
   - utils.py      通用工具函数
   - ui_main.py    主窗口
   - ui_panels.py  功能面板
   - ui_practice.py 刷题窗口
   - ui_exam.py    考试窗口 + 成绩窗口
   - ui_dialogs.py 对话框（题库管理、导入导出、编辑等）

 使用方法:
   python main.py

 环境: Python 3.7+, 零外部依赖
===============================================================================
"""

import tkinter as tk
from tkinter import ttk

from code.ui_main import MainApp


def main():
    """启动 GUI 程序。"""
    root_temp = tk.Tk()
    root_temp.withdraw()
    style = ttk.Style()
    style.configure("Answered.TButton", background="#90EE90")
    root_temp.destroy()

    app = MainApp()
    app.run()


if __name__ == "__main__":
    main()
