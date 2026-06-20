@echo off
:: Domain Research Training — Rob rotation domains (business, sales, growth, frontier, ...)
cd /d "%~dp0..\.."
backend\.venv\Scripts\python.exe oss\cli\domain_research_train.py %*