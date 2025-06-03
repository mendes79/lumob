# generate_password_hash.py
from passlib.context import CryptContext
import mysql.connector
from database.db_base import DatabaseManager # Importe seu DatabaseManager

# Configuração do contexto para hashing de senhas com scrypt
pwd_context = CryptContext(schemes=["scrypt"], deprecated="auto")

# Configurações do Banco de Dados (as mesmas do app.py)
db_config = {
    "host": "localhost",
    "database": "lumob",
    "user": "mendes",
    "password": "Galo13BH79&*" # Sua senha real
}

def generate_hash_and_update_user(username, plain_password):
    """
    Gera um hash scrypt para uma senha e atualiza a senha de um usuário existente no DB.
    Útil para corrigir senhas de usuários que não foram hashed corretamente.
    """
    try:
        # 1. Gerar o hash da senha
        hashed_password = pwd_context.hash(plain_password)
        print(f"Senha original: '{plain_password}'")
        print(f"Hash gerado: '{hashed_password}'")

        # 2. Conectar ao banco de dados e atualizar o usuário
        with DatabaseManager(**db_config) as db_base:
            query_select_user = "SELECT id FROM usuarios WHERE username = %s"
            user_data = db_base.execute_query(query_select_user, (username,), fetch_results=True)

            if user_data:
                user_id = user_data[0]['id']
                query_update = "UPDATE usuarios SET password = %s WHERE id = %s"
                success = db_base.execute_query(query_update, (hashed_password, user_id), fetch_results=False)
                if success:
                    print(f"Senha do usuário '{username}' atualizada com sucesso no banco de dados!")
                else:
                    print(f"Falha ao atualizar a senha do usuário '{username}'.")
            else:
                print(f"Usuário '{username}' não encontrado.")

    except mysql.connector.Error as e:
        print(f"Erro de banco de dados: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

def add_new_user_and_permissions(username, plain_password, role, module_names=None):
    """
    Adiciona um novo usuário ao banco de dados e, opcionalmente, configura suas permissões de módulo.
    :param username: Nome de usuário.
    :param plain_password: Senha em texto puro.
    :param role: Papel do usuário (ex: 'admin', 'rh', 'engenheiro', 'editor', 'seguranca').
    :param module_names: Lista de nomes de módulos aos quais o usuário terá acesso (ex: ['Pessoal']).
                         Se o role for 'admin', este parâmetro é ignorado, pois 'admin' tem acesso total.
                         Se não for 'admin' e module_names for None ou vazio, o usuário não terá permissões de módulo explícitas.
    """
    try:
        hashed_password = pwd_context.hash(plain_password)
        print(f"\n--- Adicionando novo usuário: {username} ---")
        print(f"Role: '{role}'")
        print(f"Senha gerada para '{plain_password}': '{hashed_password}'")

        with DatabaseManager(**db_config) as db_base:
            # 1. Verificar se o usuário já existe para evitar duplicatas
            existing_user = db_base.execute_query("SELECT id FROM usuarios WHERE username = %s", (username,), fetch_results=True)
            if existing_user:
                print(f"Usuário '{username}' já existe (ID: {existing_user[0]['id']}). Nenhuma ação de adição realizada.")
                print("Se deseja apenas atualizar a senha, use 'generate_hash_and_update_user'.")
                return

            # 2. Inserir o novo usuário
            query_insert_user = "INSERT INTO usuarios (username, password, role) VALUES (%s, %s, %s)"
            if not db_base.execute_query(query_insert_user, (username, hashed_password, role), fetch_results=False):
                print(f"Falha ao adicionar o usuário '{username}'.")
                return

            # Para obter o ID_Usuario recém-inserido
            # IMPORTANTE: Se o seu `db_base.execute_query` pudesse retornar o `cursor.lastrowid`,
            # seria mais eficiente. Como não retorna, fazemos uma nova busca.
            user_id_query = "SELECT id FROM usuarios WHERE username = %s"
            user_id_result = db_base.execute_query(user_id_query, (username,), fetch_results=True)
            if not user_id_result:
                print(f"Erro: Não foi possível recuperar o ID do usuário '{username}' após a inserção. Permissões não configuradas.")
                return
            new_user_id = user_id_result[0]['id']
            print(f"Usuário '{username}' (ID: {new_user_id}) adicionado com sucesso.")

            # 3. Configurar permissões de módulo (se aplicável e não for 'admin')
            if role != 'admin' and module_names:
                print(f"Configurando permissões para os módulos: {', '.join(module_names)}")
                for module_name in module_names:
                    # Obter ID_Modulo pelo Nome_Modulo
                    module_id_query = "SELECT ID_Modulo FROM modulos WHERE Nome_Modulo = %s"
                    module_id_result = db_base.execute_query(module_id_query, (module_name,), fetch_results=True)
                    
                    if module_id_result:
                        module_id = module_id_result[0]['ID_Modulo']
                        # Inserir permissão
                        # Evitar duplicatas em permissoes_usuarios (opcional, mas boa prática)
                        check_perm_query = "SELECT 1 FROM permissoes_usuarios WHERE ID_Usuario = %s AND ID_Modulo = %s"
                        existing_perm = db_base.execute_query(check_perm_query, (new_user_id, module_id), fetch_results=True)
                        if not existing_perm:
                            permission_query = "INSERT INTO permissoes_usuarios (ID_Usuario, ID_Modulo) VALUES (%s, %s)"
                            if db_base.execute_query(permission_query, (new_user_id, module_id), fetch_results=False):
                                print(f"  Permissão concedida para '{module_name}'.")
                            else:
                                print(f"  Falha ao conceder permissão para '{module_name}'.")
                        else:
                            print(f"  Permissão para '{module_name}' já existe para o usuário '{username}'.")
                    else:
                        print(f"  Aviso: Módulo '{module_name}' não encontrado na tabela 'modulos'. Permissão não adicionada.")
            elif role == 'admin':
                print("Usuário é 'admin', o acesso aos módulos é controlado pela 'role' no app.py.")
            else:
                print("Nenhum módulo específico para permissão fornecido (ou role 'admin').")

    except mysql.connector.Error as e:
        print(f"Erro de banco de dados: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")


if __name__ == "__main__":
    # --- IMPORTANTE: ANTES DE RODAR ---
    # Certifique-se de que a sua tabela `modulos` no banco de dados 'lumob'
    # contenha as entradas para 'Pessoal', 'Obras', 'Usuários', 'Segurança'.
    # Exemplo de SQL para inserir, se elas não existirem:
    # INSERT INTO modulos (Nome_Modulo, Descricao_Modulo) VALUES ('Pessoal', 'Gestão de Recursos Humanos e Departamento Pessoal');
    # INSERT INTO modulos (Nome_Modulo, Descricao_Modulo) VALUES ('Obras', 'Gestão de Projetos e Obras');
    # INSERT INTO modulos (Nome_Modulo, Descricao_Modulo) VALUES ('Usuários', 'Gestão de Usuários e Acessos');
    # INSERT INTO modulos (Nome_Modulo, Descricao_Modulo) VALUES ('Segurança', 'Gestão de Segurança e Acesso Físico');
    # Execute essas SQLs no seu cliente MySQL (Workbench, DBeaver, etc.) se necessário.

    # --- EXEMPLOS DE USO ---

    # 1. Atualizar senha de um usuário existente (ex: se 'admin_test' já existe mas a senha não está hashed corretamente)
    # generate_hash_and_update_user('admin_test', 'adminpass')

    # 2. Criar um novo usuário 'dp' com role 'rh' e acesso apenas ao módulo 'Pessoal'
    # O role 'rh' é o que permite acesso ao módulo 'Pessoal' no welcome.html, junto com 'admin' e 'editor'.
    add_new_user_and_permissions('dp', 'dp', 'rh', ['Pessoal'])

    # 3. Criar um novo usuário 'engenheiro_test' com role 'engenheiro' e acesso a 'Obras'
    # add_new_user_and_permissions('eng_test', 'engpass', 'engenheiro', ['Obras'])

    # 4. Criar um novo usuário 'seguranca_test' com role 'seguranca' e acesso a 'Segurança'
    # add_new_user_and_permissions('seg_test', 'segpass', 'seguranca', ['Segurança'])

    # 5. Criar um novo usuário 'editor_test' com role 'editor' e acesso a 'Pessoal'
    # add_new_user_and_permissions('editor_test', 'editorpass', 'editor', ['Pessoal'])

    # 6. Criar um novo usuário 'novo_admin' com role 'admin' (acesso total via role)
    # add_new_user_and_permissions('novo_admin', 'nova_admin_senha', 'admin')