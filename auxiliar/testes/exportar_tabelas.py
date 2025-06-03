import pandas as pd
import mysql.connector
import os

# Conecte-se ao banco de dados 'lumob'
conn = mysql.connector.connect(
    host='localhost',
    user='mendes',       # Substitua por seu nome de usuário do MySQL
    password='Galo13BH79&*',     # Substitua pela sua senha
    database='lumob'
)

# Lista das tabelas que serão exportadas
tabelas = [
    'cargos',
    'funcionarios',
    'funcionarios_contatos',
    'funcionarios_documentos',
    'funcionarios_enderecos',
    'modulos',
    'niveis',
    'permissoes_usuarios',
    'salarios',
    'usuarios'
]

# Caminho onde os arquivos CSV serão salvos
caminho = r'C:\Users\mende\Projetos\lumob\Testes\versao_01\tabelas_lumob'

# Cria o diretório se ele não existir
os.makedirs(caminho, exist_ok=True)

# Loop para extrair os dados de cada tabela e salvá-los em arquivos CSV
for tabela in tabelas:
    try:
        query = f"SELECT * FROM {tabela}"
        df = pd.read_sql(query, conn)
        arquivo_csv = os.path.join(caminho, f"{tabela}.csv")
        df.to_csv(arquivo_csv, index=False)
        print(f"Tabela '{tabela}' exportada com sucesso para {arquivo_csv}.")
    except Exception as e:
        print(f"Erro ao exportar a tabela '{tabela}': {e}")

conn.close()
