# database/db_user_manager.py
# rev01 - alterações para tratar a adição do campo email na tabela usuarios
import bcrypt
from passlib.context import CryptContext

# Configuração do contexto para hashing de senhas com scrypt
# Certifique-se de que 'scrypt' esteja instalado (pip install passlib[scrypt])
pwd_context = CryptContext(schemes=["scrypt"], deprecated="auto")

class UserManager:
    def __init__(self, db_manager):
        self.db = db_manager

    def find_user_by_id(self, user_id):
        """
        Retorna um registro de usuário pelo ID, incluindo o email.
        """
        query = "SELECT id, username, password, role, email FROM usuarios WHERE id = %s"
        result = self.db.execute_query(query, (user_id,), fetch_results=True)
        return result[0] if result else None

    def find_user_by_username(self, username):
        """
        Retorna um registro de usuário pelo nome de usuário, incluindo o email.
        """
        query = "SELECT id, username, password, role, email FROM usuarios WHERE username = %s"
        result = self.db.execute_query(query, (username,), fetch_results=True)
        return result[0] if result else None

    def find_user_by_email(self, email):
        """
        NOVO MÉTODO: Retorna um registro de usuário pelo email.
        """
        query = "SELECT id, username, password, role, email FROM usuarios WHERE email = %s"
        result = self.db.execute_query(query, (email,), fetch_results=True)
        return result[0] if result else None

    def authenticate_user(self, username, plain_password):
        user_record = self.find_user_by_username(username)
        if user_record:
            try:
                # Usa pwd_context para verificar a senha
                if pwd_context.verify(plain_password, user_record['password']):
                    return user_record
            except ValueError as e:
                # Erro ao verificar senha (formato inválido?): {e}
                return None
        return None

    def get_user_permissions(self, user_id):
        """
        Retorna uma lista de nomes de módulos que o usuário tem permissão.
        Admins têm acesso a todos os módulos existentes na tabela 'modulos'.
        """
        user = self.find_user_by_id(user_id)
        if not user:
            return []

        # Se o usuário é admin, retorna todos os módulos
        if user.get('role') == 'admin':
            all_modules_query = "SELECT Nome_Modulo FROM modulos"
            all_modules_result = self.db.execute_query(all_modules_query, fetch_results=True)
            return [row['Nome_Modulo'] for row in all_modules_result] if all_modules_result else []

        # Para outros roles, retorna as permissões explícitas
        query = """
            SELECT m.Nome_Modulo
            FROM permissoes_usuarios pu
            JOIN modulos m ON pu.ID_Modulo = m.ID_Modulo
            WHERE pu.ID_Usuario = %s
        """
        result = self.db.execute_query(query, (user_id,), fetch_results=True)
        return [row['Nome_Modulo'] for row in result] if result else []

    # --- MÉTODOS PARA O MÓDULO DE USUÁRIOS ---

    def get_all_users(self):
        """
        Retorna todos os usuários com seus IDs, usernames, emails e roles.
        """
        query = "SELECT id, username, email, role FROM usuarios ORDER BY username"
        return self.db.execute_query(query, fetch_results=True)

    def add_user(self, username, plain_password, role, email):
        """
        Adiciona um novo usuário ao banco de dados, incluindo o email.
        """
        hashed_password = pwd_context.hash(plain_password)
        query = "INSERT INTO usuarios (username, password, role, email) VALUES (%s, %s, %s, %s)"
        success = self.db.execute_query(query, (username, hashed_password, role, email), fetch_results=False)
        if success:
            # Tenta retornar o ID do usuário recém-criado, buscando-o
            user_data = self.find_user_by_username(username) # Ou find_user_by_email(email)
            return user_data['id'] if user_data else None
        return None

    def update_user(self, user_id, new_username=None, new_password=None, new_role=None, new_email=None):
        """
        Atualiza o username, senha, role e/ou email de um usuário.
        """
        updates = []
        params = []

        if new_username is not None: # Verifica se foi fornecido, pode ser uma string vazia
            updates.append("username = %s")
            params.append(new_username)
        
        if new_password is not None:
            hashed_password = pwd_context.hash(new_password)
            updates.append("password = %s")
            params.append(hashed_password)
        
        if new_role is not None:
            updates.append("role = %s")
            params.append(new_role)

        if new_email is not None: # Adiciona o campo email
            updates.append("email = %s")
            params.append(new_email)

        if not updates: # Se não há nada para atualizar
            return False

        query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s"
        params.append(user_id) # O ID do usuário sempre vai no final

        return self.db.execute_query(query, tuple(params), fetch_results=False)

    def reset_password(self, user_id, default_password="lumob@123"):
        """Reseta a senha de um usuário para uma senha padrão."""
        hashed_password = pwd_context.hash(default_password)
        query = "UPDATE usuarios SET password = %s WHERE id = %s"
        return self.db.execute_query(query, (hashed_password, user_id), fetch_results=False)

    def delete_user(self, user_id):
        """Deleta um usuário e todas as suas permissões associadas."""
        # Primeiro, deleta as permissões para evitar erros de chave estrangeira
        query_delete_permissions = "DELETE FROM permissoes_usuarios WHERE ID_Usuario = %s"
        self.db.execute_query(query_delete_permissions, (user_id,), fetch_results=False)

        # Depois, deleta o usuário
        query_delete_user = "DELETE FROM usuarios WHERE id = %s"
        return self.db.execute_query(query_delete_user, (user_id,), fetch_results=False)

    def get_all_modules(self):
        """Retorna todos os módulos disponíveis (ID_Modulo, Nome_Modulo)."""
        query = "SELECT ID_Modulo, Nome_Modulo FROM modulos ORDER BY Nome_Modulo"
        return self.db.execute_query(query, fetch_results=True)

    def get_user_module_permissions(self, user_id):
        """Retorna os IDs dos módulos que um usuário tem permissão explícita."""
        query = "SELECT ID_Modulo FROM permissoes_usuarios WHERE ID_Usuario = %s"
        result = self.db.execute_query(query, (user_id,), fetch_results=True)
        return [row['ID_Modulo'] for row in result] if result else []

    def update_user_module_permissions(self, user_id, module_ids):
        """Atualiza as permissões de módulo de um usuário, substituindo as existentes."""
        # 1. Deleta todas as permissões existentes para o usuário
        query_delete = "DELETE FROM permissoes_usuarios WHERE ID_Usuario = %s"
        self.db.execute_query(query_delete, (user_id,), fetch_results=False)

        # 2. Insere as novas permissões (apenas se houver module_ids para inserir)
        if module_ids:
            # Cria uma lista de tuplas (ID_Usuario, ID_Modulo) para a inserção
            values_to_insert = [(user_id, mod_id) for mod_id in module_ids]
            
            # Executa inserção para cada par, pois db.execute_query não suporta executemany diretamente
            all_success = True
            for val_tuple in values_to_insert:
                if not self.db.execute_query(
                    "INSERT INTO permissoes_usuarios (ID_Usuario, ID_Modulo) VALUES (%s, %s)", 
                    val_tuple, 
                    fetch_results=False
                ):
                    all_success = False
            return all_success
        return True # Se module_ids está vazio, apenas removeu as permissões existentes, o que é um sucesso.