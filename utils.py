# utils.py

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

# Você pode adicionar outras funções úteis e globais aqui no futuro.