# lumob/database/db_modulos_permissoes_manager.py

# Importa DatabaseManager para o bloco de teste e para a tipagem (se necessário)
from database.db_base import DatabaseManager 
import mysql.connector # Para poder pegar erros específicos do MySQL

class DBModulosPermissoesManager:
    """
    Gerencia as operações de banco de dados relacionadas a módulos e permissões
    de usuário em relação a esses módulos.

    Recebe uma instância de DatabaseManager no construtor, que deve ter
    um atributo 'connection' para a conexão MySQL ativa.
    """
    def __init__(self, database_manager_instance):
        # A instância de DatabaseManager é passada e armazenada.
        # A conexão MySQL real é acessada via database_manager_instance.connection
        self.db_manager = database_manager_instance

    def get_todos_modulos(self):
        """
        Retorna uma lista de todos os módulos disponíveis no sistema.
        Cada módulo é um dicionário, contendo ID_Modulo e Nome_Modulo.
        """
        # Verifica se a conexão está disponível antes de tentar usar
        if not self.db_manager.connection:
            print("Erro: Conexão com o banco de dados não estabelecida.")
            return []

        cursor = self.db_manager.connection.cursor(dictionary=True) 
        try:
            cursor.execute("SELECT ID_Modulo, Nome_Modulo FROM modulos ORDER BY Nome_Modulo")
            modulos = cursor.fetchall()
            return modulos
        except mysql.connector.Error as e:
            print(f"Erro de banco de dados ao buscar todos os módulos: {e}")
            return []
        except Exception as e:
            print(f"Erro inesperado ao buscar todos os módulos: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            # A conexão (self.db_manager.connection) é gerenciada pelo DatabaseManager (context manager),
            # então não a fechamos aqui.

    def get_permissoes_usuario_modulos(self, id_usuario):
        """
        Retorna uma lista dos IDs dos módulos aos quais o usuário tem permissão.
        """
        if not self.db_manager.connection:
            print("Erro: Conexão com o banco de dados não estabelecida.")
            return []

        cursor = self.db_manager.connection.cursor()
        try:
            query = """
            SELECT ID_Modulo
            FROM permissoes_usuarios
            WHERE ID_Usuario = %s
            """
            cursor.execute(query, (id_usuario,))
            return [row[0] for row in cursor.fetchall()]
        except mysql.connector.Error as e:
            print(f"Erro de banco de dados ao buscar permissões do usuário {id_usuario}: {e}")
            return []
        except Exception as e:
            print(f"Erro inesperado ao buscar permissões do usuário {id_usuario}: {e}")
            return []
        finally:
            if cursor:
                cursor.close()

    def adicionar_modulo(self, nome_modulo):
        """Adiciona um novo módulo ao sistema (apenas nome)."""
        if not self.db_manager.connection:
            print("Erro: Conexão com o banco de dados não estabelecida.")
            return False

        cursor = self.db_manager.connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO modulos (Nome_Modulo) VALUES (%s)",
                (nome_modulo,)
            )
            self.db_manager.connection.commit() 
            print(f"Módulo '{nome_modulo}' adicionado com sucesso.")
            return True
        except mysql.connector.Error as e:
            if e.errno == 1062: # MySQL error code for duplicate entry
                print(f"Módulo '{nome_modulo}' já existe. (Erro MySQL: {e})")
            else:
                print(f"Erro de banco de dados ao adicionar módulo: {e}")
            self.db_manager.connection.rollback()
            return False
        except Exception as e:
            print(f"Erro inesperado ao adicionar módulo: {e}")
            self.db_manager.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def adicionar_permissao_usuario(self, id_usuario, id_modulo):
        """Concede permissão a um usuário para um módulo específico."""
        if not self.db_manager.connection:
            print("Erro: Conexão com o banco de dados não estabelecida.")
            return False

        cursor = self.db_manager.connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO permissoes_usuarios (ID_Usuario, ID_Modulo) VALUES (%s, %s)",
                (id_usuario, id_modulo)
            )
            self.db_manager.connection.commit()
            print(f"Permissão concedida: Usuário {id_usuario} para Módulo {id_modulo}.")
            return True
        except mysql.connector.Error as e:
            if e.errno == 1062: # MySQL error code for duplicate entry
                print(f"Permissão para usuário {id_usuario} e módulo {id_modulo} já existe.")
                return True # Consideramos que já existir é um sucesso para a operação
            else:
                print(f"Erro de banco de dados ao adicionar permissão: {e}")
            self.db_manager.connection.rollback()
            return False
        except Exception as e:
            print(f"Erro inesperado ao adicionar permissão: {e}")
            self.db_manager.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def remover_permissao_usuario(self, id_usuario, id_modulo):
        """Remove permissão de um usuário para um módulo específico."""
        if not self.db_manager.connection:
            print("Erro: Conexão com o banco de dados não estabelecida.")
            return False

        cursor = self.db_manager.connection.cursor()
        try:
            cursor.execute(
                "DELETE FROM permissoes_usuarios WHERE ID_Usuario = %s AND ID_Modulo = %s",
                (id_usuario, id_modulo)
            )
            self.db_manager.connection.commit()
            if cursor.rowcount > 0:
                print(f"Permissão removida: Usuário {id_usuario} do Módulo {id_modulo}.")
            else:
                print(f"Permissão não encontrada para remover: Usuário {id_usuario} do Módulo {id_modulo}.")
            return cursor.rowcount > 0
        except mysql.connector.Error as e:
            print(f"Erro de banco de dados ao remover permissão: {e}")
            self.db_manager.connection.rollback()
            return False
        except Exception as e:
            print(f"Erro inesperado ao remover permissão: {e}")
            self.db_manager.connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()


# --- SCRIPT DE TESTE INTEGRADO ---
if __name__ == "__main__":
    # Configurações do Banco de Dados para o teste
    # ESTAS CONFIGURAÇÕES DEVEM CORRESPONDER EXATAMENTE ÀS SUAS CREDENCIAIS REAIS DO MySQL!
    db_config_test = {
        "host": "localhost",
        "database": "lumob",
        "user": "mendes",
        "password": "Galo13BH79&*" # <--- CONFIRME SUA SENHA AQUI!
    }

    print("--- Iniciando testes de DBModulosPermissoesManager ---")

    # Teste 1: Listar todos os módulos
    print("\n--- Teste 1: Listar todos os módulos ---")
    try:
        with DatabaseManager(**db_config_test) as db_manager_instance:
            manager = DBModulosPermissoesManager(db_manager_instance)
            modulos = manager.get_todos_modulos()
            if modulos:
                print("Módulos encontrados:")
                for m in modulos:
                    print(f"  ID: {m['ID_Modulo']}, Nome: {m['Nome_Modulo']}")
            else:
                print("Nenhum módulo encontrado. Verifique se a tabela 'modulos' está populada.")
    except Exception as e:
        print(f"Falha no Teste 1: {e}")

    # Teste 2: Obter permissões para um usuário específico (ID_Usuario 3 - admin_test)
    # Assumindo que o usuário com ID 3 (admin_test) existe e tem permissões para todos os módulos
    print("\n--- Teste 2: Obter permissões para o Usuário 3 (admin_test) ---")
    user_id_test_admin = 3 
    try:
        with DatabaseManager(**db_config_test) as db_manager_instance:
            manager = DBModulosPermissoesManager(db_manager_instance)
            permissoes = manager.get_permissoes_usuario_modulos(user_id_test_admin)
            if permissoes:
                print(f"Permissões para Usuário {user_id_test_admin}: {permissoes}")
                expected_modules = [1, 2, 3, 4] # Exemplo: Pessoal, Obras, Usuários, Segurança
                if set(permissoes) == set(expected_modules):
                    print(f"  --> OK: Permissões para Usuário {user_id_test_admin} correspondem ao esperado (todos os módulos).")
                else:
                    print(f"  --> ATENÇÃO: Permissões para Usuário {user_id_test_admin} NÃO correspondem ao esperado. Esperado: {expected_modules}")
            else:
                print(f"Nenhuma permissão encontrada para Usuário {user_id_test_admin}. Verifique se a tabela 'permissoes_usuarios' está populada ou se o ID do usuário está correto.")
    except Exception as e:
        print(f"Falha no Teste 2: {e}")

    # Teste 3: Obter permissões para outro usuário (ID_Usuario 2 - testeusers)
    # Assumindo que o usuário com ID 2 (testeusers) existe e tem permissões para Pessoal (1) e Usuários (3)
    print("\n--- Teste 3: Obter permissões para o Usuário 2 (testeusers) ---")
    user_id_test_editor = 2 
    try:
        with DatabaseManager(**db_config_test) as db_manager_instance:
            manager = DBModulosPermissoesManager(db_manager_instance)
            permissoes_editor = manager.get_permissoes_usuario_modulos(user_id_test_editor)
            if permissoes_editor:
                print(f"Permissões para Usuário {user_id_test_editor}: {permissoes_editor}")
                expected_modules_editor = [1, 3] # Exemplo: Pessoal, Usuários
                if set(permissoes_editor) == set(expected_modules_editor):
                    print(f"  --> OK: Permissões para Usuário {user_id_test_editor} correspondem ao esperado.")
                else:
                    print(f"  --> ATENÇÃO: Permissões para Usuário {user_id_test_editor} NÃO correspondem ao esperado. Esperado: {expected_modules_editor}")
            else:
                print(f"Nenhuma permissão encontrada para Usuário {user_id_test_editor}.")
    except Exception as e:
        print(f"Falha no Teste 3: {e}")

    # Teste 4: Tentar adicionar um módulo duplicado (deve imprimir "Módulo já existe")
    print("\n--- Teste 4: Tentar adicionar módulo duplicado ('Pessoal') ---")
    try:
        with DatabaseManager(**db_config_test) as db_manager_instance:
            manager = DBModulosPermissoesManager(db_manager_instance)
            manager.adicionar_modulo("Pessoal") # Deve retornar True mas imprimir que já existe
    except Exception as e:
        print(f"Falha no Teste 4: {e}")

    # Teste 5: Tentar adicionar uma permissão duplicada
    print("\n--- Teste 5: Tentar adicionar permissão duplicada (Usuário 3, Módulo 1) ---")
    try:
        with DatabaseManager(**db_config_test) as db_manager_instance:
            manager = DBModulosPermissoesManager(db_manager_instance)
            manager.adicionar_permissao_usuario(3, 1) # Usuário 3 (admin) já tem permissão para Módulo 1 (Pessoal)
    except Exception as e:
        print(f"Falha no Teste 5: {e}")

    # Teste 6: Remover uma permissão (e tentar adicioná-la novamente para ver se funciona)
    # ATENÇÃO: Este teste altera o DB. Ele remove uma permissão e a adiciona de volta.
    print("\n--- Teste 6: Remover e adicionar permissão (Usuário 2, Módulo 1) ---")
    user_id_remove_test = 2
    module_id_remove_test = 1 # Módulo 'Pessoal'
    try:
        with DatabaseManager(**db_config_test) as db_manager_instance:
            manager = DBModulosPermissoesManager(db_manager_instance)
            print(f"Removendo permissão de Usuário {user_id_remove_test} para Módulo {module_id_remove_test}...")
            success = manager.remover_permissao_usuario(user_id_remove_test, module_id_remove_test)
            print(f"Remoção bem-sucedida? {success}")

            print(f"Verificando permissões para Usuário {user_id_remove_test} após remoção...")
            permissoes_after_remove = manager.get_permissoes_usuario_modulos(user_id_remove_test)
            print(f"Permissões restantes para Usuário {user_id_remove_test}: {permissoes_after_remove}")
            if module_id_remove_test not in permissoes_after_remove:
                print(f"  --> OK: Módulo {module_id_remove_test} removido da lista de permissões.")
            else:
                print(f"  --> ERRO: Módulo {module_id_remove_test} AINDA está na lista de permissões.")

            print(f"Adicionando permissão de volta para Usuário {user_id_remove_test} para Módulo {module_id_remove_test}...")
            success_add_back = manager.adicionar_permissao_usuario(user_id_remove_test, module_id_remove_test)
            print(f"Adição de volta bem-sucedida? {success_add_back}")

            print(f"Verificando permissões para Usuário {user_id_remove_test} após adição de volta...")
            permissoes_after_add_back = manager.get_permissoes_usuario_modulos(user_id_remove_test)
            print(f"Permissões após adição de volta para Usuário {user_id_remove_test}: {permissoes_after_add_back}")
            if module_id_remove_test in permissoes_after_add_back:
                print(f"  --> OK: Módulo {module_id_remove_test} readicionado à lista de permissões.")
            else:
                print(f"  --> ERRO: Módulo {module_id_remove_test} NÃO foi readicionado à lista de permissões.")
    except Exception as e:
        print(f"Falha no Teste 6: {e}")

    print("\n--- Testes de DBModulosPermissoesManager Concluídos ---")