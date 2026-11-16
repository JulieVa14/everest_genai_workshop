# Course Companion: Student Guide

Everything happens in one notebook: [notebooks/course_companion.ipynb](../notebooks/course_companion.ipynb).
You read the idea, fill in a few blanks, run a test, and at the end open your own web app.
This page only explains how to get ready.

## Before class (once)

You need Python 3.12, Node.js and your own OpenAI API key (a ChatGPT subscription does
not include API credit; no Azure account is needed). In PowerShell, from the workshop folder:

```powershell
py -3.12 -m venv backend/.venv
./backend/.venv/Scripts/python.exe -m pip install -r requirements.txt
npm --prefix frontend ci
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

Then open `backend/.env` and put your key after `OPENAI_API_KEY=`. Never paste the key into
the notebook, a chat or a screenshot.

## In class

1. Open [notebooks/course_companion.ipynb](../notebooks/course_companion.ipynb) in VS Code.
2. Top right, choose the kernel **Course Companion (Python 3.12)**, or the Python in
   `backend/.venv`. Do not create a new environment.
3. Run the cells from top to bottom. In the ✏️ cells, replace every `____` blank, then run
   the cell. Run the ▶️ test cell below it. ✅ means it works.
4. At the end, `lab.open_app()` starts the web app that runs on your code.

Stuck? Read the message under the test cell first: it says which exercise and which blank
needs work. Then ask your instructor for a hint.

## Good to know

- Use only public lecture material: the text you search and ask about is sent to OpenAI.
- Only edit the ✏️ cells. Running one saves your code to `backend/app/student_code/`, where
  the app picks it up automatically.
- Clear all outputs before you share your notebook.