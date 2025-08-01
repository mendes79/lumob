# app.py
# rev01 - integração do campo email da tabela usuarios no app.py
# rev02 - Correção do erro 'now is undefined' no template welcome.html
# rev03 - Suporte a requisições AJAX e respostas JSON na rota /login para o novo layout de login
# rev04 - Implantação do CSRFProtect nas requisições tipo POST/DELETE dos templates HTML contra CSRF (Cross-Site Request Forgery)

#################################################################
# 0. CONFIGURAÇÕES INICIAIS
#################################################################

# ===============================================================
# 0.1 IMPORTAÇÕES E BIBLIOTECAS
# ===============================================================

# Necessária para carregar credenciais e senhas do .env
import os
from dotenv import load_dotenv # Idem

from flask import Flask, render_template, redirect, url_for, request, flash, session, get_flashed_messages, jsonify # Adicionado jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import mysql.connector              # Para a classe Error do MySQL
from datetime import datetime, date # Garante que datetime e date estejam disponíveis
from flask_wtf.csrf import CSRFProtect

# Para a adição da opção exportar para Excel no módulo Pessoal
from flask import send_file # Adicione este import no topo do seu app.py
import pandas as pd         # Adicione este import no topo do seu app.py
from io import BytesIO      # Adicione este import no topo do seu app.py

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_user_manager import UserManager
# from database.db_hr_manager import HrManager # Para o módulo de RH/DP (mantido para estrutura) <<< ver se ainda precisa! Pode apagar!!!
from database.db_obras_manager import ObrasManager # Para o módulo Obras
from database.db_seguranca_manager import SegurancaManager # Para o módulo Segurança
from database.db_pessoal_manager import PessoalManager

# Imaportações para Blueprint
from modulos.users_bp import users_bp
from modulos.pessoal_bp import pessoal_bp
from modulos.obras_bp import obras_bp
from modulos.seguranca_bp import seguranca_bp

# ===============================================================
# 0.2 CONFIGURAÇÃO DA APLICAÇÃO
# ===============================================================
app = Flask(__name__)
csrf = CSRFProtect(app)

# **IMPORTANTE: A CHAVE SECRETA É LIDA DE VARIÁVEL DE AMBIENTE**
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback_secret_key_dev_only')

# Configurações do Banco de Dados - Definidas GLOBALMENTE E em app.config
db_config = { # <-- RESTAURADA AQUI COMO VARIÁVEL GLOBAL
    "host": os.getenv('DB_HOST'),
    "database": os.getenv('DB_DATABASE'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD')
}
app.config['DB_CONFIG'] = db_config # Atribui a variável global a app.config


# Disponibilizar date.today() como 'today' no ambiente Jinja2 para aniversariantes do mês
# Isso permitirá usar 'today()' no HTML
# Alternativamente, para usar 'now()', você precisaria importar 'datetime' e usar 'datetime.now'
# REMOVIDO: app.jinja_env.globals.update(today=date.today)
# Justificativa: Vamos passar datetime.now() diretamente para o template welcome.html,
# o que é mais explícito para o uso no rodapé. A função 'today' para aniversariantes
# (se utilizada) pode ser passada da mesma forma ou de forma mais específica no seu blueprint.

# Inicialização do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
# Se o usuário tentar acessar uma página protegida sem estar logado, será redirecionado para 'login'

# Classe User para Flask-Login
class User(UserMixin):
    # ALTERAÇÃO: Adicionado 'email' ao construtor
    def __init__(self, id, username, role, email=None, permissions=None):
        self.id = id
        self.username = username
        self.role = role
        self.email = email # NOVO: Atributo email
        # permissions será uma lista de nomes de módulos (strings), ex: ['Pessoal', 'Obras']
        # MANTIDO: Você já tem 'permissions' e 'can_access_module'
        self.permissions = permissions if permissions is not None else []

    def get_id(self):
        return str(self.id)

    # Método auxiliar para verificar se o usuário tem permissão para um módulo
    def can_access_module(self, module_name):
        if self.role == 'admin':            # Admin sempre tem acesso total, ignora permissões de módulo
            return True
        return module_name in self.permissions  # Verifica se o módulo está na lista de permissões do usuário

# Carregador de usuário para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            # ALTERAÇÃO: user_data agora deve incluir 'email'
            user_data = user_manager.find_user_by_id(user_id)
            if user_data:
                # Carregar as permissões do usuário e anexar ao objeto User
                user_permissions = user_manager.get_user_permissions(user_id)
                # ALTERAÇÃO: Passando user_data['email'] para o construtor do User
                return User(user_data['id'], user_data['username'], user_data['role'], user_data.get('email'), user_permissions)
        return None
    except mysql.connector.Error as e:
        print(f"Erro ao carregar usuário: {e}")
        return None

#################################################################
# 1. ROTAS GERAIS DO SISTEMA
#################################################################

# ===============================================================
# 1.1 AUTENTICAÇÃO E ACESSO
# ===============================================================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('welcome'))

    if request.method == 'POST':
        # Verifica se a requisição é AJAX (enviada pelo JavaScript)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

        username = None
        password = None

        # Tenta obter os dados do JSON se for uma requisição JSON
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
        else: # Se não for JSON, tenta pegar dos dados de formulário padrão
            username = request.form.get('username')
            password = request.form.get('password')

        try:
            with DatabaseManager(**db_config) as db_base:
                user_manager = UserManager(db_base)
                user_record = user_manager.authenticate_user(username, password) # Passa a senha em texto puro para autenticação

                if user_record:
                    user_permissions = user_manager.get_user_permissions(user_record['id'])
                    # Certifique-se de que 'email' existe no user_record, use .get() para segurança
                    user = User(user_record['id'], user_record['username'], user_record['role'], user_record.get('email'), user_permissions)
                    login_user(user)
                    if is_ajax: # Se for AJAX, retorna JSON de sucesso
                        return jsonify(success=True, redirect_url=url_for('welcome'))
                    else: # Se não for AJAX (submissão de formulário normal), redireciona e flash
                        flash('Login bem-sucedido!', 'success')
                        return redirect(url_for('welcome'))
                else:
                    message = 'Usuário ou senha inválidos.'
                    if is_ajax: # Se for AJAX, retorna JSON de falha
                        return jsonify(success=False, message=message), 401 # Retorna 401 Unauthorized para credenciais inválidas
                    else: # Se não for AJAX, flash e renderiza o template de login
                        flash(message, 'danger')
        except mysql.connector.Error as e:
            message = f"Erro de banco de dados: {e}"
            print(f"Erro de banco de dados: {e}")
            if is_ajax: # Em caso de erro de banco de dados, retorna JSON de erro
                return jsonify(success=False, message=message), 500
            else: # Caso contrário, flash e renderiza
                flash(message, 'danger')
        except Exception as e:
            message = f"Ocorreu um erro inesperado: {e}"
            print(f"Erro inesperado durante o login: {e}")
            if is_ajax: # Em caso de erro inesperado, retorna JSON de erro
                return jsonify(success=False, message=message), 500
            else: # Caso contrário, flash e renderiza
                flash(message, 'danger')

    # Para requisições GET ou submissões POST não-AJAX que falham
    # Este return será alcançado se o método não for POST, ou se o POST não for AJAX e falhar no try/except.
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    # --- NOVO: Limpar mensagens flash da sessão antes de redirecionar ---
    session.pop('_flashes', None) # Remove todas as mensagens flash da sessão
    # --- FIM NOVO ---
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

# ===============================================================
# 1.2 BOAS VINDAS (WELCOME) APÓS LOGIN: APRESENTA OS MÓDULOS
# ===============================================================
@app.route('/welcome')
@login_required
def welcome():
    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            # Garante que as permissões e email do usuário atual estejam atualizadas
            current_user.permissions = user_manager.get_user_permissions(current_user.id)
            updated_user_data = user_manager.find_user_by_id(current_user.id)
            if updated_user_data:
                current_user.email = updated_user_data.get('email')
    except Exception as e:
        print(f"Erro ao carregar permissões e/ou email para current_user em welcome: {e}")
        current_user.permissions = []
        current_user.email = None

    # --- REMOVIDO: flash(f"Bem-vindo(a) ao sistema LUMOB, {current_user.username}!", "info") para evitar redundância ---

    all_modules_db = []
    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            all_modules_db = user_manager.get_all_modules()
    except Exception as e:
        print(f"Erro ao obter todos os módulos para welcome.html: {e}")

    # CORREÇÃO: Passar o objeto datetime.now() explicitamente para o template
    return render_template(
        'welcome.html',
        user=current_user,
        all_modules_db=all_modules_db,
        now=datetime.now() # AGORA SIM: 'now' será definido no template!
    )

#################################################################
# 99. REGISTRO DOS BLUEPRINTS (NOVO)
#################################################################
app.register_blueprint(users_bp) # Registra o Blueprint do Módulo Usuários
app.register_blueprint(pessoal_bp)
app.register_blueprint(obras_bp) # Registra o Blueprint do Módulo Obras
app.register_blueprint(seguranca_bp)

if __name__ == '__main__':
    # Carrega variáveis de ambiente do arquivo .env
    load_dotenv() # É boa prática carregar as variáveis de ambiente antes de usar osenv()
    #app.run(debug=True)
    app.run(host='0.0.0.0', port=5000, debug=True)