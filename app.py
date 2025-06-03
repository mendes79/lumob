# app.py

# Importações necessárias
from flask import Flask, render_template, redirect, url_for, request, flash, session, get_flashed_messages
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import mysql.connector # Para a classe Error do MySQL

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_user_manager import UserManager
from database.db_hr_manager import HrManager # Para o módulo de RH/DP (mantido para estrutura)

# --- Inicialização do Flask ---
app = Flask(__name__)

# --- Configurações do Flask ---
# **IMPORTANTE: TROQUE ESTA CHAVE POR UMA STRING LONGA E ALEATÓRIA PARA PRODUÇÃO**
app.config['SECRET_KEY'] = '0ca1a44e0ae3dbb65bd073ccdc37d90d285064c4abec94e9'
# Exemplo de como gerar uma: import os; os.urandom(24).hex()

# Configurações do Banco de Dados
db_config = {
    "host": "localhost",
    "database": "lumob",
    "user": "mendes",
    "password": "Galo13BH79&*" # Sua senha real
}

# --- Inicialização do Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Se o usuário tentar acessar uma página protegida sem estar logado, será redirecionado para 'login'

# Classe User para Flask-Login
class User(UserMixin):
    def __init__(self, id, username, role, permissions=None): # Adicionar 'permissions'
        self.id = id
        self.username = username
        self.role = role
        # permissions será uma lista de nomes de módulos (strings), ex: ['Pessoal', 'Obras']
        self.permissions = permissions if permissions is not None else [] 

    def get_id(self):
        return str(self.id)

    # Método auxiliar para verificar se o usuário tem permissão para um módulo
    def can_access_module(self, module_name):
        if self.role == 'admin': # Admin sempre tem acesso total, ignora permissões de módulo
            return True
        return module_name in self.permissions # Verifica se o módulo está na lista de permissões do usuário

# Carregador de usuário para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            user_data = user_manager.find_user_by_id(user_id)
            if user_data:
                # Carregar as permissões do usuário e anexar ao objeto User
                user_permissions = user_manager.get_user_permissions(user_id)
                # Passamos o user_permissions como uma lista de nomes de módulos
                return User(user_data['id'], user_data['username'], user_data['role'], user_permissions)
        return None
    except mysql.connector.Error as e:
        print(f"Erro ao carregar usuário: {e}")
        return None

# --- Rotas da Aplicação ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('welcome'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'] # A senha vinda do formulário

        try:
            with DatabaseManager(**db_config) as db_base:
                user_manager = UserManager(db_base)
                user_record = user_manager.authenticate_user(username, password) # Passa a senha em texto puro para autenticação
                
                if user_record:
                    # Ao logar, carregamos o user_permissions para o objeto User
                    user_permissions = user_manager.get_user_permissions(user_record['id'])
                    user = User(user_record['id'], user_record['username'], user_record['role'], user_permissions)
                    login_user(user)
                    flash('Login bem-sucedido!', 'success')
                    return redirect(url_for('welcome'))
                else:
                    flash('Usuário ou senha inválidos.', 'danger')
        except mysql.connector.Error as e:
            flash(f"Erro de banco de dados: {e}", 'danger')
            print(f"Erro de banco de dados: {e}")
        except Exception as e:
            flash(f"Ocorreu um erro inesperado: {e}", 'danger')
            print(f"Erro inesperado durante o login: {e}")

    return render_template('login.html')

@app.route('/welcome')
@login_required
def welcome():
    # Isso garante que as permissões do usuário logado estejam atualizadas
    # no objeto current_user antes de renderizar welcome.html
    # É importante após o gerenciamento de permissões.
    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            current_user.permissions = user_manager.get_user_permissions(current_user.id)
    except Exception as e:
        print(f"Erro ao carregar permissões para current_user em welcome: {e}")
        current_user.permissions = [] # Garante que seja uma lista vazia em caso de erro

    flash(f"Bem-vindo(a) ao sistema LUMOB, {current_user.username}!", "info")
    
    # Obter todos os módulos para enviar ao template e renderizar a lista
    all_modules_db = []
    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            all_modules_db = user_manager.get_all_modules() # Retorna Nome_Modulo e ID_Modulo
    except Exception as e:
        print(f"Erro ao obter todos os módulos para welcome.html: {e}")
        # all_modules_db permanece vazio

    return render_template('welcome.html', user=current_user, all_modules_db=all_modules_db)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

# --- Rotas para os Módulos Principais (com permissões verificadas agora) ---

@app.route('/pessoal')
@login_required
def pessoal_module():
    # A verificação de permissão usa o método do objeto User
    if not current_user.can_access_module('Pessoal'): # Verifica se 'Pessoal' está na lista de permissões
        flash('Acesso negado. Você não tem permissão para acessar o módulo Pessoal.', 'warning')
        return redirect(url_for('welcome'))
    
    flash("Bem-vindo ao módulo de Pessoal! (RH/DP)", "info")
    return "<h1>Página do Módulo de Pessoal</h1><p><a href='/welcome'>Voltar</a></p>"

@app.route('/obras')
@login_required
def obras_module():
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para acessar o módulo Obras.', 'warning')
        return redirect(url_for('welcome'))

    flash("Bem-vindo ao módulo de Obras!", "info")
    return "<h1>Página do Módulo de Obras</h1><p><a href='/welcome'>Voltar</a></p>"

@app.route('/seguranca')
@login_required
def seguranca_module():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para acessar o módulo Segurança.', 'warning')
        return redirect(url_for('welcome'))

    flash("Bem-vindo ao módulo de Segurança!", "info")
    return "<h1>Página do Módulo de Segurança</h1><p><a href='/welcome'>Voltar</a></p>"

# --- Rotas para o Módulo de Usuários ---
@app.route('/users')
@login_required
def users_module():
    # O módulo de usuários (users_module) deve ter acesso restrito apenas a 'admin'
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar o módulo Usuários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            users = user_manager.get_all_users() # Obter todos os usuários
            return render_template('users.html', users=users, user=current_user)
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar usuários: {e}", 'danger')
        return redirect(url_for('welcome'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        return redirect(url_for('welcome'))

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem adicionar usuários.', 'warning')
        return redirect(url_for('users_module'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        try:
            with DatabaseManager(**db_config) as db_base:
                user_manager = UserManager(db_base)
                if user_manager.find_user_by_username(username):
                    flash(f"Usuário '{username}' já existe.", 'danger')
                else:
                    new_user_id = user_manager.add_user(username, password, role)
                    if new_user_id:
                        flash(f"Usuário '{username}' adicionado com sucesso!", 'success')
                        return redirect(url_for('users_module'))
                    else:
                        flash("Erro ao adicionar usuário.", 'danger')
        except mysql.connector.Error as e:
            flash(f"Erro de banco de dados: {e}", 'danger')
        except Exception as e:
            flash(f"Ocorreu um erro inesperado: {e}", 'danger')

    # Para a página GET, ou em caso de erro no POST
    # Pode-se passar a lista de roles disponíveis para o template
    available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
    return render_template('add_user.html', user=current_user, available_roles=available_roles)

@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem editar usuários.', 'warning')
        return redirect(url_for('users_module'))

    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            user_to_edit = user_manager.find_user_by_id(user_id)

            if not user_to_edit:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('users_module'))

            if request.method == 'POST':
                new_username = request.form.get('username')
                new_password = request.form.get('password') # Pode ser vazio se não for alterada
                new_role = request.form.get('role')

                # Validação básica
                if not new_username or not new_role:
                    flash("Nome de usuário e Papel (Role) são obrigatórios.", 'danger')
                    return render_template('edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])
                
                # Se o username for alterado, verificar se o novo username já existe para outro usuário
                if new_username != user_to_edit['username']:
                    existing_user_with_new_name = user_manager.find_user_by_username(new_username)
                    if existing_user_with_new_name and existing_user_with_new_name['id'] != user_id:
                        flash(f"O nome de usuário '{new_username}' já está em uso por outro usuário.", 'danger')
                        return render_template('edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])

                success = user_manager.update_user(user_id, new_username, new_password if new_password else None, new_role)
                if success:
                    flash(f"Usuário '{user_to_edit['username']}' atualizado com sucesso!", 'success')
                    return redirect(url_for('users_module'))
                else:
                    flash("Erro ao atualizar usuário.", 'danger')
            
            # GET request
            available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
            return render_template('edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=available_roles)

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        return redirect(url_for('users_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        return redirect(url_for('users_module'))

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem deletar usuários.', 'warning')
        return redirect(url_for('users_module'))

    if current_user.id == user_id:
        flash('Você não pode deletar sua própria conta.', 'danger')
        return redirect(url_for('users_module'))

    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            # Opcional: buscar o nome do usuário antes de deletar para mensagem de feedback
            user_to_delete = user_manager.find_user_by_id(user_id)
            if user_to_delete:
                if user_manager.delete_user(user_id):
                    flash(f"Usuário '{user_to_delete['username']}' deletado com sucesso!", 'success')
                else:
                    flash("Erro ao deletar usuário.", 'danger')
            else:
                flash("Usuário não encontrado para deletar.", 'danger')
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
    
    return redirect(url_for('users_module'))

@app.route('/users/reset_password/<int:user_id>', methods=['POST'])
@login_required
def reset_password(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem resetar senhas.', 'warning')
        return redirect(url_for('users_module'))
    
    if current_user.id == user_id:
        flash('Você não pode resetar a sua própria senha padrão por aqui. Altere-a pela edição.', 'danger')
        return redirect(url_for('users_module'))

    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            user_to_reset = user_manager.find_user_by_id(user_id)
            if user_to_reset:
                # A senha padrão está definida no db_user_manager.py como "lumob@123"
                if user_manager.reset_password(user_id):
                    flash(f"Senha do usuário '{user_to_reset['username']}' resetada para a padrão!", 'info')
                else:
                    flash("Erro ao resetar senha.", 'danger')
            else:
                flash("Usuário não encontrado para resetar senha.", 'danger')
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
    
    return redirect(url_for('users_module'))

@app.route('/users/permissions/<int:user_id>', methods=['GET', 'POST'])
@login_required
def manage_user_permissions(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem gerenciar permissões.', 'warning')
        return redirect(url_for('users_module'))

    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            user_to_manage = user_manager.find_user_by_id(user_id)

            if not user_to_manage:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('users_module'))

            # Admins sempre têm acesso total, suas permissões não devem ser editáveis aqui
            if user_to_manage['role'] == 'admin':
                flash('As permissões de um administrador são totais por padrão e não podem ser gerenciadas individualmente.', 'info')
                # Renderiza a página, mas com a mensagem informativa e desabilitada
                return render_template('manage_permissions.html', 
                                   user_to_manage=user_to_manage,
                                   all_modules=[], # Nenhum módulo para selecionar
                                   current_permissions_ids=[], # Nenhuma permissão individual
                                   user=current_user)

            all_modules = user_manager.get_all_modules()
            current_permissions_ids = user_manager.get_user_module_permissions(user_id)
            
            if request.method == 'POST':
                # Obter os IDs dos módulos selecionados no formulário
                # request.form.getlist('module_ids') retorna uma lista de strings
                selected_module_ids_str = request.form.getlist('module_ids')
                selected_module_ids = [int(mod_id) for mod_id in selected_module_ids_str]

                if user_manager.update_user_module_permissions(user_id, selected_module_ids):
                    flash(f"Permissões do usuário '{user_to_manage['username']}' atualizadas com sucesso!", 'success')
                    # Se o usuário que teve as permissões alteradas for o current_user,
                    # precisamos forçar a atualização das permissões em current_user.permissions
                    if current_user.id == user_id:
                        current_user.permissions = user_manager.get_user_permissions(current_user.id)
                    
                    return redirect(url_for('users_module'))
                else:
                    flash("Erro ao atualizar permissões.", 'danger')

            # GET request
            return render_template('manage_permissions.html', 
                                   user_to_manage=user_to_manage,
                                   all_modules=all_modules,
                                   current_permissions_ids=current_permissions_ids,
                                   user=current_user)

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        return redirect(url_for('users_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        return redirect(url_for('users_module'))


if __name__ == '__main__':
    app.run(debug=True)