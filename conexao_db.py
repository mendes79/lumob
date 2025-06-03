import mysql.connector
from mysql.connector import Error

def criar_conexao():
    """Cria e retorna uma conexão com o banco de dados MySQL."""
    conexao = None
    try:
        conexao = mysql.connector.connect(
            host="localhost",      # Onde seu MySQL está rodando (geralmente localhost)
            database="lumob",      # Nome do seu banco de dados
            user="mendes",           # Seu usuário do MySQL (geralmente root para desenvolvimento)
            password="Galo13BH79&*" # !!! COLOQUE SUA SENHA DO MYSQL AQUI !!!
        )
        if conexao.is_connected():
            print("Conexão bem-sucedida ao banco de dados 'lumob'!")
            return conexao
        else:
            print("Não foi possível conectar ao banco de dados.")
            return None

    except Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None

def executar_consulta(conexao, query):
    """Executa uma consulta SQL e retorna os resultados."""
    cursor = conexao.cursor() # Um cursor permite executar comandos SQL
    try:
        cursor.execute(query)
        # Se for uma consulta SELECT, obtenha os resultados
        if query.strip().upper().startswith("SELECT"):
            resultados = cursor.fetchall() # fetchall() obtém todas as linhas do resultado
            return resultados
        else:
            # Se for um INSERT, UPDATE, DELETE, etc., confirme as mudanças
            conexao.commit()
            print(f"Comando executado com sucesso: {query[:50]}...")
            return True # Retorna True para indicar sucesso em operações que não retornam dados
            
    except Error as e:
        print(f"Erro ao executar a consulta '{query}': {e}")
        return None
    finally:
        cursor.close() # Sempre feche o cursor

def fechar_conexao(conexao):
    """Fecha a conexão com o banco de dados."""
    if conexao and conexao.is_connected():
        conexao.close()
        print("Conexão MySQL fechada.")

# --- Exemplo de Uso ---
if __name__ == "__main__":
    conexao_db = criar_conexao()

    if conexao_db:
        print("\n--- Testando consulta de Cargos ---")
        cargos = executar_consulta(conexao_db, "SELECT ID_Cargos, Nome_Cargo FROM cargos;")
        if cargos:
            print("Cargos encontrados:")
            for cargo in cargos:
                print(f"ID: {cargo[0]}, Nome: {cargo[1]}")
        else:
            print("Nenhum cargo encontrado ou erro na consulta.")

        print("\n--- Testando consulta de Funcionários e seus Cargos/Níveis ---")
        query_funcionarios = """
        SELECT 
            f.Nome_Completo,
            c.Nome_Cargo,
            n.Nome_Nivel
        FROM 
            funcionarios f
        JOIN 
            cargos c ON f.ID_Cargos = c.ID_Cargos
        JOIN 
            niveis n ON f.ID_Niveis = n.ID_Niveis;
        """
        funcionarios_info = executar_consulta(conexao_db, query_funcionarios)
        if funcionarios_info:
            print("Informações de Funcionários:")
            for info in funcionarios_info:
                print(f"Nome: {info[0]}, Cargo: {info[1]}, Nível: {info[2]}")
        else:
            print("Nenhuma informação de funcionário encontrada ou erro na consulta.")

        fechar_conexao(conexao_db)