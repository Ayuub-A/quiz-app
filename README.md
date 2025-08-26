Quiz App Python

A lightweight desktop quiz app built in **Python** with a **Tkinter** GUI.  
Choose a **category** and **difficulty**, answer multiple-choice questions against a **per-question timer**, and view your past scores stored in **SQLite**. Question content lives in a simple **JSON** file so it’s easy to extend.

---

## Features

- Multiple-choice questions with **shuffled options**
- **Category** and **difficulty** filters
- Set **number of questions** and **time per question**
- **Live score** and end-of-quiz **percentage summary**
- **History** view powered by SQLite (timestamp, category, score, duration)
- Clean, responsive **Tkinter GUI**
- Works cross-platform with Python; Windows **.exe** build available

---

## What I Learned / Skills Developed

**Technical**
- **Python fundamentals:** functions, lists/dicts, file I/O, error handling
- **GUI development (Tkinter):** layout, state management, events, timers
- **Data modelling:** clean `Question` structure (dataclass) and JSON schema
- **Persistence:** reading questions from **JSON**, saving attempts to **SQLite**
- **Architecture & refactoring:** separated **QuizEngine** (logic), **GUI**, and **DB** layers
- **Packaging & distribution:** handled resource paths and built a Windows **.exe** (PyInstaller)

**Professional**
- **Requirements to delivery:** iterated from CLI → GUI → features (timers, history)
- **Debugging & testing:** traced runtime errors, validated JSON, improved robustness
- **Documentation:** created a clear README and structured project for employers to review
- **Version control:** organised commits and repo for a portfolio-ready project

## How to Run

### Option 1 — Windows (recommended): Download the EXE
1. Go to **Releases**: [https://github.com/Ayuub-A/quiz-app/releases/tag/app](https://github.com/Ayuub-A/quiz-app/releases/tag/app)
2. Download `quiz.exe`
3. Double-click to run  
   *(The app includes questions and creates a `quiz.db` history file automatically.)*

> Note: The EXE is for **Windows**. No Python needed.

---

### Option 2 — Any OS: Run from Source (Python)
**Requires:** Python 3.9+

# 1) Clone or download the repo
git clone [https://github.com/<your-username>/flashcard-quiz-app.git](https://github.com/Ayuub-A/quiz-app/tree/main/quiz)


# 2) Run the app
python quiz.py
