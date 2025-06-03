# database/db_base.py

import mysql.connector
from mysql.connector import Error

# 1. Definição da classe DatabaseManager
class DatabaseManager:
    """
    Gerencia a conexão com o banco de dados MySQL e operações CRUD.
    Utiliza context manager para garantir que a conexão seja fechada automaticamente.
    """
    def __init__(self, host, database, user, password):
        """Inicializa o gerenciador com as credenciais do banco de dados."""
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.connection = None

    def __enter__(self):
        """Estabelece a conexão com a conexão com o banco de dados ao entrar no bloco 'with'."""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )
            if self.connection.is_connected():
                print(f"Conexão bem-sucedida ao banco de dados '{self.database}'!")
            return self # Retorna a instância da classe para ser usada no 'as db_manager'
        except Error as e:
            print(f"Erro ao conectar ao MySQL: {e}")
            self.connection = None # Garante que a conexão seja None se falhar
            raise # Re-lança a exceção para que o problema seja visível

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Fecha a conexão com o banco de dados ao sair do bloco 'with'."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("Conexão MySQL fechada.")

    def execute_query(self, query, params=None, fetch_results=True):
        """
        Executa uma consulta SQL (INSERT, UPDATE, DELETE, SELECT).
        :param query: A string da consulta SQL.
        :param params: Uma tupla ou lista de parâmetros para a consulta (para segurança e evitar SQL Injection).
        :param fetch_results: Se True (para SELECT), retorna os resultados. Se False (para INSERT/UPDATE/DELETE), commita as mudanças.
        :return: Uma lista de dicionários (para SELECT) ou True/False (para outras operações).
        """
        if not self.connection or not self.connection.is_connected():
            print("Erro: Nenhuma conexão ativa com o banco de dados.")
            return None

        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params or ())

            if fetch_results:
                results = cursor.fetchall()
                return results
            else:
                self.connection.commit()
                return True
        except Error as e:
            print(f"Erro ao executar a consulta '{query}': {e}")
            self.connection.rollback()
            return False
        finally:
            cursor.close()

    def get_id_by_name(self, table_name, name_column, name_value, id_column=None):
        """
        Busca o ID de uma tabela de domínio (cargos, niveis) dado o nome.
        :param table_name: Nome da tabela (ex: 'cargos', 'niveis').
        :param name_column: Nome da coluna que contém o nome (ex: 'Nome_Cargo', 'Nome_Nivel').
        :param name_value: O nome a ser buscado (ex: 'Engenheiro Civil', 'Junior').
        :param id_column: Nome da coluna ID. Se None, assume ID_TableName (ex: ID_Cargos).
        :return: O ID correspondente ou None se não encontrado.
        """
        if id_column is None:
            id_column = f"ID_{table_name.capitalize()}"
        
        query = f"SELECT {id_column} FROM {table_name} WHERE {name_column} = %s;"
        result = self.execute_query(query, (name_value,), fetch_results=True)
        if result and result[0]:
            return result[0][id_column]
        return None