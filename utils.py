# utils.py

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def formatar_moeda_brl(valor):
    """Formata um número para o padrão de moeda brasileiro (R$ 1.234,56) de forma manual."""
    if valor is None:
        valor = 0.0
    # Formata o número com 2 casas decimais para separar o inteiro do decimal
    valor_str = f"{valor:.2f}"
    inteiro, decimal = valor_str.split('.')
    
    # Adiciona os pontos como separadores de milhar
    inteiro_rev = inteiro[::-1] # Inverte a string do inteiro
    partes = [inteiro_rev[i:i+3] for i in range(0, len(inteiro_rev), 3)]
    inteiro_formatado = '.'.join(partes)[::-1] # Junta com pontos e inverte de volta
    
    return f"R$ {inteiro_formatado},{decimal}"

# --- NOVO DECORATOR DE PERMISSÃO ---
def module_required(module_name):
    """
    Decorator que verifica se o usuário atual tem permissão para acessar um módulo.
    Redireciona para a página de boas-vindas se não tiver permissão.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Garante que o usuário está logado e tem a permissão necessária
            if not current_user.is_authenticated or not current_user.can_access_module(module_name):
                flash(f'Acesso negado. Você não tem permissão para acessar o Módulo {module_name}.', 'warning')
                return redirect(url_for('welcome'))
            # Se tiver permissão, executa a rota original
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Você pode adicionar outras funções úteis e globais aqui no futuro.