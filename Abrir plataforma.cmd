@echo off
rem Abre a plataforma de prospecção (http://127.0.0.1:8770). Feche esta janela para encerrar a interface;
rem análises e pesquisas em andamento continuam rodando e aparecem de novo ao reabrir.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente nao encontrado. Veja plataforma\README.md, secao "Instalar".
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m plataforma painel
pause
