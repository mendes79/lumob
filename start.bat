@echo off
setlocal

:: Define o nome da pasta do ambiente virtual
set VENV_DIR=venv

:: Verifica se a pasta do ambiente virtual existe
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo.
    echo A pasta '%VENV_DIR%' (ambiente virtual) ou o script de ativacao nao foi encontrada.
    echo Certifique-se de ter criado um ambiente virtual (ex: python -m venv %VENV_DIR%) e execute este script na raiz do projeto.
    echo.
    goto :eof
)

:: --- ATIVA O AMBIENTE VIRTUAL ---
:: A forma de ativar depende do shell. Este script funciona para CMD e Git Bash.
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo Erro ao ativar o ambiente virtual. Verifique o caminho ou a integridade do venv.
    goto :eof
)
echo.
echo Ambiente virtual '%VENV_DIR%' ativado!
echo.

:: --- GERENCIAMENTO DE BRANCHES GIT ---
echo.
echo --- Branches do Projeto ---
git branch --all

:escolha_branch
echo.
set /p escolha="Digite o nome da branch para ativar ou criar (ou 'exit' para sair): "

if /i "%escolha%"=="exit" (
    goto :eof
)

:: Tenta fazer o checkout da branch
git checkout "%escolha%"
if %errorlevel% equ 0 (
    echo.
    echo Branch '%escolha%' ativada com sucesso!
) else (
    :: Se falhou, tenta criar e fazer o checkout
    echo Branch '%escolha%' nao encontrada. Tentando criar e ativar...
    git checkout -b "%escolha%"
    if %errorlevel% equ 0 (
        echo.
        echo Branch '%escolha%' criada e ativada com sucesso!
    ) else (
        echo.
        echo Erro: Nao foi possivel ativar ou criar a branch '%escolha%'.
        goto escolha_branch
    )
)

echo.
echo --- Configuracao Concluida ---
echo Voce ja esta na branch escolhida e o ambiente virtual esta ativo.
echo.

endlocal