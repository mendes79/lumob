import os

def list_tree_pretty(startpath, max_depth=2, ignore_dirs=None, ignore_files=None, current_depth=0, prefix=''):
    """
    Lista diretórios e arquivos em formato de árvore de forma agradável e compacta.

    Args:
        startpath (str): O caminho do diretório para iniciar a listagem.
        max_depth (int): A profundidade máxima para listar (0 = apenas o diretório inicial).
        ignore_dirs (list): Lista de nomes de diretórios a serem ignorados.
        ignore_files (list): Lista de nomes de arquivos a serem ignorados.
        current_depth (int): A profundidade atual na recursão (não alterar ao chamar).
        prefix (str): O prefixo de indentação para a árvore (não alterar ao chamar).
    """
    if ignore_dirs is None:
        ignore_dirs = [
            '__pycache__', '.git', '.vscode', 'node_modules',
            'venv', '.env', '.idea', 'dist', 'build'
        ]
    if ignore_files is None:
        ignore_files = ['.DS_Store', 'Thumbs.db', 'pyc'] # Adicione extensões ou nomes completos
    
    # Obter todos os itens no diretório atual
    entries = sorted(os.listdir(startpath))
    
    # Separar diretórios e arquivos
    dirs = [d for d in entries if os.path.isdir(os.path.join(startpath, d)) and d not in ignore_dirs]
    files = [f for f in entries if os.path.isfile(os.path.join(startpath, f)) and not any(ign in f for ign in ignore_files)]

    for i, entry in enumerate(dirs + files):
        is_last = (i == len(dirs) + len(files) - 1)
        
        # Determine o conector e o novo prefixo
        connector = '└── ' if is_last else '├── '
        new_prefix = prefix + ('    ' if is_last else '│   ')

        print(f"{prefix}{connector}{entry}{'/' if os.path.isdir(os.path.join(startpath, entry)) else ''}")

        # Se for um diretório e não atingimos a profundidade máxima, chame recursivamente
        if os.path.isdir(os.path.join(startpath, entry)) and current_depth < max_depth:
            list_tree_pretty(os.path.join(startpath, entry), max_depth, ignore_dirs, ignore_files, current_depth + 1, new_prefix)

if __name__ == "__main__":
    current_directory = os.getcwd() # Obtém o diretório atual

    # --- Configurações que você pode ajustar ---
    # max_depth: 0 = apenas o diretório inicial, 1 = diretórios e seus conteúdos diretos, etc.
    # ignore_dirs: Adicione mais nomes de diretórios para ignorar
    # ignore_files: Adicione mais nomes ou extensões de arquivos para ignorar
    
    print(f"Estrutura do Projeto (em {os.path.basename(current_directory)}/):\n")
    list_tree_pretty(current_directory, max_depth=2, 
                     ignore_dirs=['__pycache__', '.git', '.vscode', 'venv', '.env', 'node_modules'],
                     ignore_files=['.DS_Store', 'Thumbs.db', '.pyc', '.log'])
    print("\n-------------------------------------------")
    print("Para expandir/colapsar diretórios específicos, você pode ajustar 'max_depth' ou a lista 'ignore_dirs'.")