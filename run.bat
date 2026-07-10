@echo off
set PYTHONIOENCODING=utf-8
echo Starting AI Interview Coach on http://localhost:8503 ...
cd /d %~dp0
streamlit run app.py --server.port 8503
pause
