import json
import os
import re
from abc import ABC, abstractmethod
from tkinter import messagebox
from datetime import datetime

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
    """题库管理 —— JSON 持久化、增删改查、导入导出、历史成绩、错题本。"""

    def __init__(self, filepath: str = "questions.json",
                 history_path: str = "history.json"):
        self.filepath = filepath
        self.history_path = history_path
        self.questions: list[Question] = []
        self.history: list[dict] = []  # 考试历史记录
        self.wrong_book: dict[int, int] = {}  # 错题本: 题目索引 → 错误次数
        self.load()
        self.load_history()
        self.load_wrong_book()

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

    # ---------- 错题本 ----------

    def _wrong_book_path(self) -> str:
        """错题本文件路径（基于题库文件名派生）。"""
        base = os.path.splitext(self.filepath)[0]
        return f"{base}_wrong.json"

    def load_wrong_book(self):
        wp = self._wrong_book_path()
        if os.path.exists(wp):
            try:
                with open(wp, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # 键在 JSON 中是字符串，转为 int
                self.wrong_book = {int(k): v for k, v in raw.items()}
            except (json.JSONDecodeError, ValueError):
                self.wrong_book = {}
        else:
            self.wrong_book = {}

    def save_wrong_book(self):
        wp = self._wrong_book_path()
        with open(wp, "w", encoding="utf-8") as f:
            json.dump(self.wrong_book, f, ensure_ascii=False, indent=2)

    def add_wrong(self, question_index: int):
        """记录一次错题（题目在题库中的原始索引）。"""
        self.wrong_book[question_index] = self.wrong_book.get(question_index, 0) + 1
        self.save_wrong_book()

    def get_wrong_indices(self) -> list[int]:
        """返回所有错题的原始索引列表（按错误次数降序）。"""
        return sorted(self.wrong_book.keys(), key=lambda i: self.wrong_book[i], reverse=True)

    def get_wrong_count(self, question_index: int) -> int:
        return self.wrong_book.get(question_index, 0)

    # ---------- TXT 解析与生成 ----------

    @staticmethod
    def parse_txt(text: str) -> list:
        """解析 TXT 格式题目文本，返回 Question 列表。（对空白字符高度容错）"""
        questions = []
        # 以空行分隔题目块（允许空行中有空格）
        blocks = re.split(r"\n\s*\n", text.strip())
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            # 每行去除首尾空白，跳过纯空白行
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue

            first_line = lines[0]
            # 容忍序号前后空格: " 1 . ( 单选题 ) 题目..."
            # 也兼容无空格写法: "1.(单选题)题目..."
            type_match = re.match(
                r"^\s*\d+\s*\.\s*\(\s*(单选题|多选题|填空题)\s*\)\s*(.+)$",
                first_line)
            if not type_match:
                continue

            qtype_cn = type_match.group(1)
            question_text = type_match.group(2).strip()

            if qtype_cn == "单选题":
                options, answer = [], ""
                for line in lines[1:]:
                    if re.match(r"^\s*答案\s*[:：]", line):
                        # 容忍 "答案 : B" / "答案：B" / "答案:  B" 等
                        answer = re.split(r"[:：]", line, 1)[1].strip().upper()
                    elif re.match(r"^\s*[A-Z]\s*\.", line):
                        options.append(line)
                if question_text and options and answer:
                    questions.append(SingleChoiceQuestion(question_text, options, answer))

            elif qtype_cn == "多选题":
                options, answer = [], []
                for line in lines[1:]:
                    if re.match(r"^\s*答案\s*[:：]", line):
                        raw = re.split(r"[:：]", line, 1)[1].strip()
                        # 直接识别连续字母，如 ABD（忽略空格和逗号）
                        answer = [ch.upper() for ch in raw if ch.isalpha()]
                    elif re.match(r"^\s*[A-Z]\s*\.", line):
                        options.append(line)
                if question_text and options and answer:
                    questions.append(MultiChoiceQuestion(question_text, options, answer))

            elif qtype_cn == "填空题":
                blank_dict = {}
                for line in lines[1:]:
                    # 空 1 : 答案  →  idx=0（容忍空格）
                    m = re.match(r"^\s*空\s*(\d+)\s*[:：]\s*(.+)$", line)
                    if m:
                        idx = int(m.group(1)) - 1  # 从1开始计数 → 内部从0
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
                lines.append(f"答案: {q.answer}")
            elif isinstance(q, MultiChoiceQuestion):
                lines.append(f"{i+1}.(多选题){q.question}")
                for opt in q.options:
                    lines.append(opt)
                lines.append(f"答案: {''.join(q.answer)}")
            elif isinstance(q, FillInBlankQuestion):
                lines.append(f"{i+1}.(填空题){q.question}")
                for j, blank in enumerate(q.blanks):
                    lines.append(f"空{j+1}: {','.join(blank['answers'])}")
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
# 多题库管理器
# ============================================================================

BANKS_DIR = "banks"


class BankManager:
    """多题库管理器 —— 管理多个题库，支持从任意目录加载题库文件。"""

    def __init__(self):
        os.makedirs(BANKS_DIR, exist_ok=True)
        self._banks: dict[str, QuestionBank] = {}       # name → QuestionBank
        self._bank_paths: dict[str, str] = {}            # name → json file path
        self._history_paths: dict[str, str] = {}          # name → history file path
        self._active_name: str = ""
        self._load_registry()

    # ---------- 注册表 ----------

    def _registry_path(self) -> str:
        return os.path.join(BANKS_DIR, "index.json")

    def _make_bank_path(self, name: str) -> str:
        """为新题库生成默认路径（在 BANKS_DIR 下）。"""
        safe = name.replace("/", "_").replace("\\", "_")
        return os.path.join(BANKS_DIR, f"{safe}.json")

    def _make_history_path(self, json_path: str) -> str:
        base = os.path.splitext(json_path)[0]
        return f"{base}_history.json"

    def _load_registry(self):
        """加载题库注册表。"""
        reg_path = self._registry_path()
        if os.path.exists(reg_path):
            try:
                with open(reg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                data = {}

            saved_paths = data.get("paths", {})  # {name: json_path}
            self._active_name = data.get("active", "")
        else:
            saved_paths = {}
            self._active_name = ""

        # 加载持久化的题库
        for name, bp in saved_paths.items():
            if os.path.exists(bp):
                self._bank_paths[name] = bp
                self._history_paths[name] = self._make_history_path(bp)
                self._banks[name] = QuestionBank(bp, self._history_paths[name])

        # 确保有活跃题库
        if not self._banks:
            self._create_default()

    def _save_registry(self):
        """保存题库注册表。"""
        data = {
            "paths": dict(self._bank_paths),
            "active": self._active_name
        }
        with open(self._registry_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _create_default(self):
        """创建默认题库。"""
        name = "默认题库"
        bp = self._make_bank_path(name)
        hp = self._make_history_path(bp)
        self._banks[name] = QuestionBank(bp, hp)
        self._bank_paths[name] = bp
        self._history_paths[name] = hp
        self._active_name = name
        self._save_registry()

    # ---------- 外部题库导入 ----------

    def add_bank_from_file(self, filepath: str) -> bool:
        """从外部 JSON 文件添加题库。返回是否成功。"""
        if not os.path.exists(filepath):
            return False
        # 用文件名（不含扩展名）作为题库名
        name = os.path.splitext(os.path.basename(filepath))[0]
        # 重名处理
        orig = name
        n = 1
        while name in self._banks:
            name = f"{orig}_{n}"
            n += 1
        hp = self._make_history_path(filepath)
        self._banks[name] = QuestionBank(filepath, hp)
        self._bank_paths[name] = filepath
        self._history_paths[name] = hp
        self._save_registry()
        return True

    def scan_directory(self, dirpath: str) -> int:
        """扫描目录中所有 .json 题库文件并添加。返回添加的数量。"""
        if not os.path.isdir(dirpath):
            return 0
        added = 0
        for fname in os.listdir(dirpath):
            if fname.endswith(".json") and not fname.startswith("index"):
                fpath = os.path.join(dirpath, fname)
                # 快速验证是否是题库格式
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and len(data) > 0 and "type" in data[0]:
                        if self.add_bank_from_file(fpath):
                            added += 1
                except (json.JSONDecodeError, ValueError, KeyError):
                    pass
        return added

    # ---------- 题库操作 ----------

    def create_bank(self, name: str) -> bool:
        """在 BANKS_DIR 下创建新题库。"""
        name = name.strip()
        if not name or name in self._banks:
            return False
        bp = self._make_bank_path(name)
        hp = self._make_history_path(bp)
        self._banks[name] = QuestionBank(bp, hp)
        self._bank_paths[name] = bp
        self._history_paths[name] = hp
        self._save_registry()
        return True

    def switch_bank(self, name: str):
        if name in self._banks:
            self._active_bank.save()
            self._active_name = name
            self._save_registry()

    def delete_bank(self, name: str) -> bool:
        if name not in self._banks or len(self._banks) <= 1:
            return False
        # 仅删除 BANKS_DIR 内的文件（外部文件保留）
        bp = self._bank_paths.get(name, "")
        if bp.startswith(os.path.abspath(BANKS_DIR)):
            hp = self._history_paths.get(name, "")
            for p in (bp, hp):
                if p and os.path.exists(p):
                    os.remove(p)
            # 也删除错题本
            wp = os.path.splitext(bp)[0] + "_wrong.json"
            if os.path.exists(wp):
                os.remove(wp)
        del self._banks[name]
        self._bank_paths.pop(name, None)
        self._history_paths.pop(name, None)
        if self._active_name == name:
            self._active_name = next(iter(self._banks.keys()))
        self._save_registry()
        return True

    def rename_bank(self, old_name: str, new_name: str) -> bool:
        new_name = new_name.strip()
        if not new_name or new_name in self._banks or old_name not in self._banks:
            return False
        bank_obj = self._banks.pop(old_name)
        old_bp = self._bank_paths.pop(old_name)
        old_hp = self._history_paths.pop(old_name)

        # 仅对 BANKS_DIR 内的文件重命名物理文件
        if old_bp.startswith(os.path.abspath(BANKS_DIR)):
            new_bp = self._make_bank_path(new_name)
            new_hp = self._make_history_path(new_bp)
            bank_obj.filepath = new_bp
            bank_obj.history_path = new_hp
            if os.path.exists(old_bp):
                os.rename(old_bp, new_bp)
            if os.path.exists(old_hp):
                os.rename(old_hp, new_hp)
            # 错题本也改名
            old_wp = os.path.splitext(old_bp)[0] + "_wrong.json"
            new_wp = os.path.splitext(new_bp)[0] + "_wrong.json"
            if os.path.exists(old_wp):
                os.rename(old_wp, new_wp)
            self._bank_paths[new_name] = new_bp
            self._history_paths[new_name] = new_hp
        else:
            self._bank_paths[new_name] = old_bp
            self._history_paths[new_name] = old_hp

        self._banks[new_name] = bank_obj
        if self._active_name == old_name:
            self._active_name = new_name
        self._save_registry()
        return True

    def list_banks(self) -> list[str]:
        return list(self._banks.keys())

    def bank_file_path(self, name: str) -> str:
        return self._bank_paths.get(name, "")

    # ---------- 代理属性 ----------

    @property
    def _active_bank(self) -> QuestionBank:
        return self._banks[self._active_name]

    @property
    def questions(self) -> list:
        return self._active_bank.questions

    @questions.setter
    def questions(self, value):
        self._active_bank.questions = value

    @property
    def history(self) -> list:
        return self._active_bank.history

    @property
    def active_name(self) -> str:
        return self._active_name

    def save(self):
        self._active_bank.save()

    def get_statistics(self) -> dict:
        return self._active_bank.get_statistics()

    def add_history(self, record: dict):
        self._active_bank.add_history(record)

    def add_wrong(self, question_index: int):
        self._active_bank.add_wrong(question_index)

    def get_wrong_indices(self) -> list[int]:
        return self._active_bank.get_wrong_indices()

    def get_wrong_count(self, question_index: int) -> int:
        return self._active_bank.get_wrong_count(question_index)


# ============================================================================
# 全局配置
# ============================================================================




class BankManager:
    """多题库管理器 —— 管理多个题库，支持从任意目录加载题库文件。"""

    def __init__(self):
        os.makedirs(BANKS_DIR, exist_ok=True)
        self._banks: dict[str, QuestionBank] = {}       # name → QuestionBank
        self._bank_paths: dict[str, str] = {}            # name → json file path
        self._history_paths: dict[str, str] = {}          # name → history file path
        self._active_name: str = ""
        self._load_registry()

    # ---------- 注册表 ----------

    def _registry_path(self) -> str:
        return os.path.join(BANKS_DIR, "index.json")

    def _make_bank_path(self, name: str) -> str:
        """为新题库生成默认路径（在 BANKS_DIR 下）。"""
        safe = name.replace("/", "_").replace("\\", "_")
        return os.path.join(BANKS_DIR, f"{safe}.json")

    def _make_history_path(self, json_path: str) -> str:
        base = os.path.splitext(json_path)[0]
        return f"{base}_history.json"

    def _load_registry(self):
        """加载题库注册表。"""
        reg_path = self._registry_path()
        if os.path.exists(reg_path):
            try:
                with open(reg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                data = {}

            saved_paths = data.get("paths", {})  # {name: json_path}
            self._active_name = data.get("active", "")
        else:
            saved_paths = {}
            self._active_name = ""

        # 加载持久化的题库
        for name, bp in saved_paths.items():
            if os.path.exists(bp):
                self._bank_paths[name] = bp
                self._history_paths[name] = self._make_history_path(bp)
                self._banks[name] = QuestionBank(bp, self._history_paths[name])

        # 确保有活跃题库
        if not self._banks:
            self._create_default()

    def _save_registry(self):
        """保存题库注册表。"""
        data = {
            "paths": dict(self._bank_paths),
            "active": self._active_name
        }
        with open(self._registry_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _create_default(self):
        """创建默认题库。"""
        name = "默认题库"
        bp = self._make_bank_path(name)
        hp = self._make_history_path(bp)
        self._banks[name] = QuestionBank(bp, hp)
        self._bank_paths[name] = bp
        self._history_paths[name] = hp
        self._active_name = name
        self._save_registry()

    # ---------- 外部题库导入 ----------

    def add_bank_from_file(self, filepath: str) -> bool:
        """从外部 JSON 文件添加题库。返回是否成功。"""
        if not os.path.exists(filepath):
            return False
        # 用文件名（不含扩展名）作为题库名
        name = os.path.splitext(os.path.basename(filepath))[0]
        # 重名处理
        orig = name
        n = 1
        while name in self._banks:
            name = f"{orig}_{n}"
            n += 1
        hp = self._make_history_path(filepath)
        self._banks[name] = QuestionBank(filepath, hp)
        self._bank_paths[name] = filepath
        self._history_paths[name] = hp
        self._save_registry()
        return True

    def scan_directory(self, dirpath: str) -> int:
        """扫描目录中所有 .json 题库文件并添加。返回添加的数量。"""
        if not os.path.isdir(dirpath):
            return 0
        added = 0
        for fname in os.listdir(dirpath):
            if fname.endswith(".json") and not fname.startswith("index"):
                fpath = os.path.join(dirpath, fname)
                # 快速验证是否是题库格式
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and len(data) > 0 and "type" in data[0]:
                        if self.add_bank_from_file(fpath):
                            added += 1
                except (json.JSONDecodeError, ValueError, KeyError):
                    pass
        return added

    # ---------- 题库操作 ----------

    def create_bank(self, name: str) -> bool:
        """在 BANKS_DIR 下创建新题库。"""
        name = name.strip()
        if not name or name in self._banks:
            return False
        bp = self._make_bank_path(name)
        hp = self._make_history_path(bp)
        self._banks[name] = QuestionBank(bp, hp)
        self._bank_paths[name] = bp
        self._history_paths[name] = hp
        self._save_registry()
        return True

    def switch_bank(self, name: str):
        if name in self._banks:
            self._active_bank.save()
            self._active_name = name
            self._save_registry()

    def delete_bank(self, name: str) -> bool:
        if name not in self._banks or len(self._banks) <= 1:
            return False
        # 仅删除 BANKS_DIR 内的文件（外部文件保留）
        bp = self._bank_paths.get(name, "")
        if bp.startswith(os.path.abspath(BANKS_DIR)):
            hp = self._history_paths.get(name, "")
            for p in (bp, hp):
                if p and os.path.exists(p):
                    os.remove(p)
            # 也删除错题本
            wp = os.path.splitext(bp)[0] + "_wrong.json"
            if os.path.exists(wp):
                os.remove(wp)
        del self._banks[name]
        self._bank_paths.pop(name, None)
        self._history_paths.pop(name, None)
        if self._active_name == name:
            self._active_name = next(iter(self._banks.keys()))
        self._save_registry()
        return True

    def rename_bank(self, old_name: str, new_name: str) -> bool:
        new_name = new_name.strip()
        if not new_name or new_name in self._banks or old_name not in self._banks:
            return False
        bank_obj = self._banks.pop(old_name)
        old_bp = self._bank_paths.pop(old_name)
        old_hp = self._history_paths.pop(old_name)

        # 仅对 BANKS_DIR 内的文件重命名物理文件
        if old_bp.startswith(os.path.abspath(BANKS_DIR)):
            new_bp = self._make_bank_path(new_name)
            new_hp = self._make_history_path(new_bp)
            bank_obj.filepath = new_bp
            bank_obj.history_path = new_hp
            if os.path.exists(old_bp):
                os.rename(old_bp, new_bp)
            if os.path.exists(old_hp):
                os.rename(old_hp, new_hp)
            # 错题本也改名
            old_wp = os.path.splitext(old_bp)[0] + "_wrong.json"
            new_wp = os.path.splitext(new_bp)[0] + "_wrong.json"
            if os.path.exists(old_wp):
                os.rename(old_wp, new_wp)
            self._bank_paths[new_name] = new_bp
            self._history_paths[new_name] = new_hp
        else:
            self._bank_paths[new_name] = old_bp
            self._history_paths[new_name] = old_hp

        self._banks[new_name] = bank_obj
        if self._active_name == old_name:
            self._active_name = new_name
        self._save_registry()
        return True

    def list_banks(self) -> list[str]:
        return list(self._banks.keys())

    def bank_file_path(self, name: str) -> str:
        return self._bank_paths.get(name, "")

    # ---------- 代理属性 ----------

    @property
    def _active_bank(self) -> QuestionBank:
        return self._banks[self._active_name]

    @property
    def questions(self) -> list:
        return self._active_bank.questions

    @questions.setter
    def questions(self, value):
        self._active_bank.questions = value

    @property
    def history(self) -> list:
        return self._active_bank.history

    @property
    def active_name(self) -> str:
        return self._active_name

    def save(self):
        self._active_bank.save()

    def get_statistics(self) -> dict:
        return self._active_bank.get_statistics()

    def add_history(self, record: dict):
        self._active_bank.add_history(record)

    def add_wrong(self, question_index: int):
        self._active_bank.add_wrong(question_index)

    def get_wrong_indices(self) -> list[int]:
        return self._active_bank.get_wrong_indices()

    def get_wrong_count(self, question_index: int) -> int:
        return self._active_bank.get_wrong_count(question_index)


# ============================================================================


class AppConfig:
    """应用全局配置，存储用户偏好设置。"""

    CONFIG_PATH = "config.json"
    DEFAULTS = {
        "practice_mode": "random",        # random / sequential
        "practice_show_answer": False,
        "exam_default_duration": 30,       # 分钟
    }

    def __init__(self):
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                for k in self.DEFAULTS:
                    if k in loaded:
                        self.data[k] = loaded[k]
            except (json.JSONDecodeError, ValueError):
                pass

    def save(self):
        with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, key: str):
        return self.data.get(key, self.DEFAULTS.get(key))

    def set(self, key: str, value):
        self.data[key] = value
        self.save()


config = AppConfig()


# ============================================================================




BANKS_DIR = 'banks'

config = AppConfig()
bank = BankManager()

