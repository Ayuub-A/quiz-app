import os
import sys
import json
import time
import random
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import List, Optional

# --- paths/util ---

def resource_path(rel_path: str) -> str:
    """Return absolute path to a bundled/resource file (PyInstaller-friendly)."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)

def app_data_dir() -> Path:
    base = Path.home() / ".flashcard_quiz"
    base.mkdir(exist_ok=True)
    return base

# --- data model ---

@dataclass(frozen=True)
class Question:
    category: str
    question: str
    options: List[str]
    answer: str
    difficulty: str = "Easy"

def load_questions(path: str = "questions.json") -> List[Question]:
    """Load Question objects from JSON."""
    candidate = resource_path(path)
    if not os.path.isfile(candidate):
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
        alt = os.path.join(base_dir, path)
        if os.path.isfile(alt):
            candidate = alt
        else:
            raise FileNotFoundError(f"{path} not found")

    with open(candidate, "r", encoding="utf-8") as f:
        raw = json.load(f)

    out: List[Question] = []
    for category, items in raw.items():
        for q in items:
            out.append(Question(
                category=category,
                question=q["question"],
                options=list(q["options"]),
                answer=q["answer"],
                difficulty=q.get("difficulty", "Easy"),
            ))
    return out

# --- persistence ---

class DB:
    def __init__(self, db_file: str | None = None):
        if db_file is None:
            db_file = str(app_data_dir() / "quiz.db")
        self.conn = sqlite3.connect(db_file)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                duration_seconds INTEGER NOT NULL
            )
        """)
        self.conn.commit()

    def save_attempt(self, category: str, difficulty: str, score: int, total: int, duration_seconds: int) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO attempts (timestamp, category, difficulty, score, total, duration_seconds) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, category, difficulty, score, total, duration_seconds),
        )
        self.conn.commit()

    def recent_attempts(self, limit: int = 20):
        cur = self.conn.execute(
            "SELECT timestamp, category, difficulty, score, total, duration_seconds "
            "FROM attempts ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

# --- quiz logic ---

class QuizEngine:
    def __init__(self, questions: List[Question], rng: Optional[random.Random] = None):
        self.questions_all = questions
        self.rng = rng or random.Random()
        self.reset_state()

    def reset_state(self):
        self.pool: List[Question] = []
        self.order: List[int] = []
        self.index: int = 0
        self.score: int = 0
        self.started_at: float = 0.0
        self.category: str = "Any"
        self.difficulty: str = "Any"

    def start(self, category: str = "Any", difficulty: str = "Any", count: int = 5):
        self.category = category
        self.difficulty = difficulty

        pool = (q for q in self.questions_all if (category == "Any" or q.category == category))
        if difficulty != "Any":
            pool = (q for q in pool if q.difficulty == difficulty)
        self.pool = list(pool)
        if not self.pool:
            raise ValueError("No questions match your filters.")

        count = min(max(1, int(count)), len(self.pool))
        indices = list(range(len(self.pool)))
        self.rng.shuffle(indices)
        self.order = indices[:count]

        self.index = 0
        self.score = 0
        self.started_at = time.time()

    @property
    def total(self) -> int:
        return len(self.order)

    def current(self) -> Question:
        return self.pool[self.order[self.index]]

    def is_finished(self) -> bool:
        return self.index >= self.total

    def submit(self, selected: Optional[str]) -> bool:
        q = self.current()
        correct = (selected == q.answer)
        if correct:
            self.score += 1
        self.index += 1
        return correct

    def duration_seconds(self) -> int:
        return int(max(0, time.time() - self.started_at))

# --- GUI ---

DEFAULT_TIME_LIMIT = 20  # seconds

class FlashcardApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Flashcard Quiz App")
        self.root.geometry("720x520")
        self.root.configure(bg="#f0f0f0")

        self.db = DB()
        try:
            self.engine = QuizEngine(load_questions())
        except Exception as e:
            messagebox.showerror("Startup error", str(e))
            self.on_close()
            return

        self.time_limit = DEFAULT_TIME_LIMIT
        self.time_left = self.time_limit
        self.timer_id: Optional[str] = None

        self.home_frame: Optional[tk.Frame] = None
        self.quiz_frame: Optional[tk.Frame] = None

        self.meta_label: Optional[tk.Label] = None
        self.score_label: Optional[tk.Label] = None
        self.question_label: Optional[tk.Label] = None
        self.timer_label: Optional[tk.Label] = None
        self.progress: Optional[ttk.Progressbar] = None
        self.option_buttons: List[tk.Button] = []

        self.create_home()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # home

    def create_home(self):
        self.destroy_quiz()
        if self.home_frame:
            self.home_frame.destroy()

        self.home_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.home_frame.pack(expand=True, fill="both", padx=20, pady=20)

        title = tk.Label(self.home_frame, text="Flashcard Quiz App", font=("Helvetica", 20, "bold"), bg="#f0f0f0")
        title.pack(pady=(10, 16))

        selectors = tk.Frame(self.home_frame, bg="#f0f0f0")
        selectors.pack(pady=6)

        categories = ["Any"] + sorted({q.category for q in self.engine.questions_all})
        difficulties = ["Any", "Easy", "Medium", "Hard"]

        tk.Label(selectors, text="Category:", font=("Helvetica", 12), bg="#f0f0f0").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        self.category_var = tk.StringVar(value=categories[0])
        ttk.Combobox(selectors, textvariable=self.category_var, values=categories, state="readonly", width=28)\
            .grid(row=0, column=1, padx=8, pady=6)

        tk.Label(selectors, text="Difficulty:", font=("Helvetica", 12), bg="#f0f0f0").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        self.diff_var = tk.StringVar(value=difficulties[0])
        ttk.Combobox(selectors, textvariable=self.diff_var, values=difficulties, state="readonly", width=28)\
            .grid(row=1, column=1, padx=8, pady=6)

        tk.Label(selectors, text="Number of questions:", font=("Helvetica", 12), bg="#f0f0f0").grid(row=2, column=0, padx=8, pady=6, sticky="e")
        self.count_var = tk.IntVar(value=5)
        tk.Spinbox(selectors, from_=1, to=50, textvariable=self.count_var, width=10)\
            .grid(row=2, column=1, padx=8, pady=6, sticky="w")

        tk.Label(selectors, text="Time per question (s):", font=("Helvetica", 12), bg="#f0f0f0").grid(row=3, column=0, padx=8, pady=6, sticky="e")
        self.time_var = tk.IntVar(value=DEFAULT_TIME_LIMIT)
        tk.Spinbox(selectors, from_=5, to=120, textvariable=self.time_var, width=10)\
            .grid(row=3, column=1, padx=8, pady=6, sticky="w")

        btns = tk.Frame(self.home_frame, bg="#f0f0f0")
        btns.pack(pady=16)

        tk.Button(btns, text="Start Quiz", width=20, height=2, font=("Helvetica", 12),
                  bg="#4CAF50", fg="white", activebackground="#45a049",
                  command=self.on_start).grid(row=0, column=0, padx=10)

        tk.Button(btns, text="View History", width=20, height=2, font=("Helvetica", 12),
                  bg="#2196F3", fg="white", activebackground="#1976D2",
                  command=self.open_history).grid(row=0, column=1, padx=10)

    # quiz

    def on_start(self):
        try:
            self.engine.start(
                category=self.category_var.get(),
                difficulty=self.diff_var.get(),
                count=int(self.count_var.get()),
            )
        except ValueError as e:
            messagebox.showwarning("No Questions", str(e))
            return

        self.time_limit = max(5, int(self.time_var.get()))
        self.show_quiz()

    def show_quiz(self):
        if self.home_frame:
            self.home_frame.destroy()
            self.home_frame = None
        if self.quiz_frame:
            self.quiz_frame.destroy()

        self.quiz_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.quiz_frame.pack(expand=True, fill="both", padx=20, pady=20)

        header = tk.Frame(self.quiz_frame, bg="#f0f0f0")
        header.pack(fill="x")

        self.meta_label = tk.Label(header, text="", font=("Helvetica", 12, "italic"), bg="#f0f0f0")
        self.meta_label.pack(side="left")

        self.score_label = tk.Label(header, text="Score: 0", font=("Helvetica", 12, "bold"), bg="#f0f0f0")
        self.score_label.pack(side="right")

        self.question_label = tk.Label(self.quiz_frame, text="", font=("Helvetica", 16, "bold"),
                                       wraplength=660, justify="left", bg="#f0f0f0")
        self.question_label.pack(pady=(20, 10))

        row = tk.Frame(self.quiz_frame, bg="#f0f0f0")
        row.pack(pady=(0, 10), fill="x")
        self.timer_label = tk.Label(row, text="", font=("Helvetica", 12), bg="#f0f0f0")
        self.timer_label.pack(side="left")
        self.progress = ttk.Progressbar(row, length=320, mode="determinate", maximum=self.time_limit)
        self.progress.pack(side="right")

        self.option_buttons = []
        for _ in range(4):
            b = tk.Button(self.quiz_frame, text="", width=62, height=2,
                          font=("Helvetica", 11), bg="#2196F3", fg="white",
                          activebackground="#1976D2")
            b.pack(pady=6)
            self.option_buttons.append(b)

        self.display_question()

    def display_question(self):
        if self.engine.is_finished():
            self.finish()
            return

        self.cancel_timer()

        q = self.engine.current()
        self.meta_label.config(text=f"Category: {self.engine.category} | Difficulty: {self.engine.difficulty}")
        self.question_label.config(text=f"Q{self.engine.index + 1}/{self.engine.total}: {q.question}")
        self.score_label.config(text=f"Score: {self.engine.score} / {self.engine.total}")

        options = q.options[:]
        random.shuffle(options)

        for btn, opt in zip(self.option_buttons, options):
            btn.config(text=opt, state="normal", command=lambda o=opt: self.on_answer(o))

        self.time_left = self.time_limit
        self.progress.configure(maximum=self.time_limit, value=self.time_limit)
        self.timer_label.config(text=f"Time left: {self.time_left}s")
        self.timer_id = self.root.after(1000, self.tick)

    def on_answer(self, choice: Optional[str]):
        for b in self.option_buttons:
            b.config(state="disabled")
        self.cancel_timer()
        self.engine.submit(choice)
        self.display_question()

    def tick(self):
        self.time_left -= 1
        self.timer_label.config(text=f"Time left: {self.time_left}s")
        self.progress.configure(value=self.time_left)
        if self.time_left <= 0:
            self.on_answer(None)
        else:
            self.timer_id = self.root.after(1000, self.tick)

    def cancel_timer(self):
        if self.timer_id is not None:
            try:
                self.root.after_cancel(self.timer_id)
            except Exception:
                pass
            finally:
                self.timer_id = None

    def finish(self):
        self.cancel_timer()
        duration = self.engine.duration_seconds()
        self.db.save_attempt(
            category=self.engine.category,
            difficulty=self.engine.difficulty,
            score=self.engine.score,
            total=self.engine.total,
            duration_seconds=duration,
        )

        if self.quiz_frame:
            self.quiz_frame.destroy()

        result = tk.Frame(self.root, bg="#f0f0f0")
        result.pack(expand=True, fill="both", padx=20, pady=20)

        pct = round(100 * self.engine.score / max(1, self.engine.total))
        tk.Label(result, text="Quiz Complete!", font=("Helvetica", 20, "bold"), bg="#f0f0f0").pack(pady=(30, 10))
        tk.Label(result, text=f"Score: {self.engine.score}/{self.engine.total}  ({pct}%)\nTime: {duration}s",
                 font=("Helvetica", 14), bg="#f0f0f0").pack(pady=(0, 20))

        row = tk.Frame(result, bg="#f0f0f0")
        row.pack()

        tk.Button(row, text="Play Again", width=18, height=2, font=("Helvetica", 12),
                  bg="#4CAF50", fg="white",
                  command=lambda: self._restart(result)).grid(row=0, column=0, padx=8)

        tk.Button(row, text="Home", width=18, height=2, font=("Helvetica", 12),
                  bg="#607D8B", fg="white",
                  command=lambda: self._home(result)).grid(row=0, column=1, padx=8)

        tk.Button(row, text="Exit", width=18, height=2, font=("Helvetica", 12),
                  bg="#f44336", fg="white",
                  command=self.on_close).grid(row=0, column=2, padx=8)

    def _restart(self, frame: tk.Frame):
        frame.destroy()
        try:
            self.engine.start(self.engine.category, self.engine.difficulty, self.engine.total)
        except ValueError as e:
            messagebox.showwarning("No Questions", str(e))
            return
        self.show_quiz()

    def _home(self, frame: tk.Frame):
        frame.destroy()
        self.engine.reset_state()
        self.create_home()

    # history

    def open_history(self):
        rows = self.db.recent_attempts(limit=20)

        w = tk.Toplevel(self.root)
        w.title("Attempt History")
        w.geometry("680x360")

        columns = ("timestamp", "category", "difficulty", "score", "total", "duration (s)")
        tree = ttk.Treeview(w, columns=columns, show="headings", height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=110, stretch=True)
        tree.pack(expand=True, fill="both", padx=10, pady=10)

        for ts, cat, diff, sc, tot, dur in rows:
            tree.insert("", "end", values=(ts, cat, diff, sc, tot, dur))

    # cleanup

    def destroy_quiz(self):
        self.cancel_timer()
        if self.quiz_frame:
            self.quiz_frame.destroy()
            self.quiz_frame = None

    def on_close(self):
        self.destroy_quiz()
        self.db.close()
        try:
            self.root.quit()
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = FlashcardApp(root)
    root.mainloop()
