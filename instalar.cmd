@echo off
rem ============================================================================
rem  Instala o ambiente da plataforma de prospecção (RIP Memorial).
rem  Rode UMA VEZ depois de clonar o projeto. Depois é só "Abrir plataforma.cmd".
rem ============================================================================
setlocal
cd /d "%~dp0"
echo.
echo === Plataforma de prospeccao - instalacao ===
echo Pasta: %CD%
echo.

rem ---- 1. Achar o Python (3.11 ou mais novo) --------------------------------
set "PY="
for %%V in (3.14 3.13 3.12 3.11) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [ERRO] Python 3.11 ou mais novo nao encontrado.
  echo.
  echo Instale em https://www.python.org/downloads/ marcando
  echo "Add python.exe to PATH" e rode este arquivo de novo.
  echo.
  pause
  exit /b 1
)
echo [1/4] Python encontrado: %PY%
%PY% --version

rem ---- 2. Criar o ambiente virtual ------------------------------------------
if exist ".venv\Scripts\python.exe" (
  echo [2/4] Ambiente .venv ja existe; reaproveitando.
) else (
  echo [2/4] Criando o ambiente .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERRO] Nao foi possivel criar o ambiente virtual.
    pause
    exit /b 1
  )
)
set "VPY=.venv\Scripts\python.exe"

rem ---- 3. Instalar os tres pacotes ------------------------------------------
rem  A ordem importa: pesquisa-empresas depende de prospeccao-instagram
rem  (os 13 segmentos A-M), e a plataforma depende dos dois.
echo [3/4] Instalando as dependencias (pode levar alguns minutos) ...
"%VPY%" -m pip install --upgrade pip --quiet
if errorlevel 1 goto :falha_pip
for %%P in (instagram pesquisa-empresas plataforma) do (
  echo       - %%P
  "%VPY%" -m pip install -e ".\%%P[dev]" --quiet
  if errorlevel 1 goto :falha_pip
)

rem ---- 4. Preparar o banco de consulta --------------------------------------
echo [4/4] Preparando o banco da plataforma ...
"%VPY%" -m plataforma sincronizar
if errorlevel 1 (
  echo [AVISO] A sincronizacao inicial falhou, mas a instalacao continua valida.
)

echo.
echo ============================================================
echo  Pronto.
echo.
echo  Para abrir:        clique duas vezes em "Abrir plataforma.cmd"
echo  Endereco:          http://127.0.0.1:8770
echo.
echo  Para usar o Instagram voce ainda precisa configurar a sessao
echo  (aba Sistema da plataforma, ou: .venv\Scripts\prospeccao.exe sessao firefox)
echo ============================================================
echo.
pause
exit /b 0

:falha_pip
echo.
echo [ERRO] Falha ao instalar as dependencias.
echo Verifique a conexao com a internet e rode este arquivo de novo.
echo.
pause
exit /b 1
