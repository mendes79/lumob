# app.py
# rev01 - integração do campo email da tabela usuarios no app.py

# Importações necessárias
from flask import Flask, render_template, redirect, url_for, request, flash, session, get_flashed_messages
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import mysql.connector # Para a classe Error do MySQL
from datetime import datetime, date # Garante que datetime e date estejam disponíveis

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_user_manager import UserManager
from database.db_hr_manager import HrManager # Para o módulo de RH/DP (mantido para estrutura) <<< ver se ainda precisa!

# Importação para o CRUD do módulo Pessoal
from database.db_personal_manager import PersonalManager

# Para a adição da opção exportar para Excel no módulo Pessoal
from flask import send_file # Adicione este import no topo do seu app.py
import pandas as pd # Adicione este import no topo do seu app.py
from io import BytesIO # Adicione este import no topo do seu app.py


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
    # MANTIDO: Este é o método que você já usa e é correto.
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
                    # Ao logar, carregamos o user_permissions e o email para o objeto User
                    user_permissions = user_manager.get_user_permissions(user_record['id'])
                    # ALTERAÇÃO: Passando user_record['email'] para o construtor do User
                    user = User(user_record['id'], user_record['username'], user_record['role'], user_record.get('email'), user_permissions)
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
            # REVISÃO: Atualiza o atributo permissions do objeto current_user
            current_user.permissions = user_manager.get_user_permissions(current_user.id)
            # NOVO: Recarrega o email para garantir que current_user esteja atualizado
            updated_user_data = user_manager.find_user_by_id(current_user.id)
            if updated_user_data:
                current_user.email = updated_user_data.get('email')
    except Exception as e:
        print(f"Erro ao carregar permissões e/ou email para current_user em welcome: {e}")
        current_user.permissions = [] # Garante que seja uma lista vazia em caso de erro
        current_user.email = None # Garante que seja None em caso de erro

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

# Rota para o Módulo Pessoal
@app.route('/personal') # ALTERADO: Rota para '/personal' conforme definido anteriormente
@login_required
def personal_module():
    # A verificação de permissão usa o método do objeto User
    # CORREÇÃO: Usando current_user.can_access_module('Pessoal')
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o módulo Pessoal.', 'warning')
        return redirect(url_for('welcome'))

    # Parâmetros de filtro da requisição
    search_matricula = request.args.get('matricula', '').strip()
    search_name = request.args.get('nome', '').strip()
    # Usamos type=int para converter diretamente para int, se não for, será None
    search_cargo_id = request.args.get('cargo_id', type=int)
    search_type_contratacao = request.args.get('tipo_contratacao', '').strip()

    try:
        with DatabaseManager(**db_config) as db_base:
            personal_manager = PersonalManager(db_base)

            # Obter a lista de funcionários com filtros
            employees = personal_manager.get_all_employees(
                search_matricula=search_matricula if search_matricula else None,
                search_name=search_name if search_name else None,
                search_cargo_id=search_cargo_id,
                search_type_contratacao=search_type_contratacao if search_type_contratacao else None
            )

            # Obter dados para os filtros (cargos e tipos de contratação)
            all_cargos = personal_manager.get_all_cargos()
            # Os tipos de contratação são fixos do ENUM, podem ser definidos aqui
            all_tipos_contratacao = ['CLT', 'PJ', 'Temporario']

            return render_template(
                'personal/personal_module.html',
                employees=employees,
                user=current_user,
                all_cargos=all_cargos,
                all_tipos_contratacao=all_tipos_contratacao,
                # Repassar os valores dos filtros para o template manter o estado
                selected_matricula=search_matricula,
                selected_name=search_name,
                selected_cargo_id=search_cargo_id,
                selected_type_contratacao=search_type_contratacao
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar dados do módulo Pessoal: {e}", 'danger')
        print(f"Erro de banco de dados em personal_module: {e}") # Para depuração no terminal
        return redirect(url_for('welcome'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado no módulo Pessoal: {e}", 'danger')
        print(f"Erro inesperado em personal_module: {e}") # Para depuração no terminal
        return redirect(url_for('welcome'))

# --- Continuação:
# --- ROTAS DO MÓDULO PESSOAL (CRUD COMPLETO) ---
# -----------------------------------------------
@app.route('/personal/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    if not current_user.can_access_module('Pessoal'): # Você pode criar uma permissão mais específica aqui, e.g., 'Pessoal_Add'
        flash('Acesso negado. Você não tem permissão para adicionar funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            personal_manager = PersonalManager(db_base)
            
            if request.method == 'POST':
                matricula = request.form['matricula'].strip()
                nome_completo = request.form['nome_completo'].strip()
                data_admissao_str = request.form['data_admissao'].strip()
                id_cargo = int(request.form['id_cargo']) # Usando id_cargo, conforme PersonalManager
                id_nivel = int(request.form['id_nivel']) # Usando id_nivel, conforme PersonalManager
                status = request.form['status'].strip()
                tipo_contratacao = request.form['tipo_contratacao'].strip()

                # Validação básica
                if not all([matricula, nome_completo, data_admissao_str, id_cargo, id_nivel, status, tipo_contratacao]):
                    flash('Todos os campos são obrigatórios.', 'danger')
                    return redirect(url_for('add_employee'))

                # Converter data
                try:
                    # Assumindo formato YYYY-MM-DD do input type="date"
                    data_admissao = datetime.strptime(data_admissao_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    return redirect(url_for('add_employee'))
                
                # Opcional: Verificar unicidade da matrícula antes de adicionar
                # if personal_manager.get_employee_by_matricula(matricula):
                #     flash('Matrícula já existe. Por favor, use uma matrícula única.', 'danger')
                #     return redirect(url_for('add_employee'))

                success = personal_manager.add_employee(
                    matricula, nome_completo, data_admissao, id_cargo, id_nivel, status, tipo_contratacao
                )
                if success:
                    flash('Funcionário adicionado com sucesso!', 'success')
                    return redirect(url_for('personal_module'))
                else:
                    flash('Erro ao adicionar funcionário. Matrícula pode já existir ou dados inválidos.', 'danger')
            
            # GET request: Carregar dados para o formulário
            all_cargos = personal_manager.get_all_cargos()
            all_niveis = personal_manager.get_all_niveis() # Adicione get_all_niveis ao PersonalManager se não tiver
            last_matricula = personal_manager.get_last_matricula()
            next_matricula = ""
            if last_matricula and last_matricula.isdigit():
                next_matricula = str(int(last_matricula) + 1).zfill(len(last_matricula)) # Mantém o zero padding
            else:
                next_matricula = "0001" # Matrícula inicial sugestiva
                
            return render_template(
                'personal/add_employee.html',
                user=current_user,
                all_cargos=all_cargos,
                all_niveis=all_niveis,
                next_matricula=next_matricula
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_employee: {e}")
        return redirect(url_for('personal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_employee: {e}")
        return redirect(url_for('personal_module'))

@app.route('/personal/edit/<string:matricula>', methods=['GET', 'POST'])
@login_required
def edit_employee(matricula):
    if not current_user.can_access_module('Pessoal'): # e.g., 'Pessoal_Edit'
        flash('Acesso negado. Você não tem permissão para editar funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            personal_manager = PersonalManager(db_base)
            employee = personal_manager.get_employee_by_matricula(matricula)

            if not employee:
                flash('Funcionário não encontrado.', 'danger')
                return redirect(url_for('personal_module'))

            if request.method == 'POST':
                nome_completo = request.form['nome_completo'].strip()
                data_admissao_str = request.form['data_admissao'].strip()
                id_cargo = int(request.form['id_cargo'])
                id_nivel = int(request.form['id_nivel'])
                status = request.form['status'].strip()
                tipo_contratacao = request.form['tipo_contratacao'].strip()

                try:
                    data_admissao = datetime.strptime(data_admissao_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    return redirect(url_for('edit_employee', matricula=matricula))

                success = personal_manager.update_employee(
                    matricula, nome_completo, data_admissao, id_cargo, id_nivel, status, tipo_contratacao
                )
                if success:
                    flash('Funcionário atualizado com sucesso!', 'success')
                    return redirect(url_for('personal_module'))
                else:
                    flash('Erro ao atualizar funcionário.', 'danger')
            
            # GET request: Carregar dados para o formulário
            all_cargos = personal_manager.get_all_cargos()
            all_niveis = personal_manager.get_all_niveis()

            return render_template(
                'personal/edit_employee.html',
                user=current_user,
                employee=employee,
                all_cargos=all_cargos,
                all_niveis=all_niveis
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_employee: {e}")
        return redirect(url_for('personal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_employee: {e}")
        return redirect(url_for('personal_module'))

@app.route('/personal/delete/<string:matricula>', methods=['POST'])
@login_required
def delete_employee(matricula):
    if not current_user.can_access_module('Pessoal'): # e.g., 'Pessoal_Delete'
        flash('Acesso negado. Você não tem permissão para excluir funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            personal_manager = PersonalManager(db_base)
            success = personal_manager.delete_employee(matricula)
            if success:
                flash('Funcionário excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir funcionário. Verifique se ele existe.', 'danger')
        return redirect(url_for('personal_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_employee: {e}")
        return redirect(url_for('personal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_employee: {e}")
        return redirect(url_for('personal_module'))

@app.route('/personal/details/<string:matricula>')
@login_required
def employee_details(matricula):
    if not current_user.can_access_module('Pessoal'): # e.g., 'Pessoal_View'
        flash('Acesso negado. Você não tem permissão para ver detalhes de funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            personal_manager = PersonalManager(db_base)
            employee = personal_manager.get_employee_by_matricula(matricula)

            if not employee:
                flash('Funcionário não encontrado.', 'danger')
                return redirect(url_for('personal_module'))
            
            # Se você tiver métodos para buscar contatos, documentos, endereços, chame-os aqui:
            # contacts = personal_manager.get_employee_contacts(matricula)
            # documents = personal_manager.get_employee_documents(matricula)
            # address = personal_manager.get_employee_address(matricula)

            return render_template(
                'personal/employee_details.html',
                user=current_user,
                employee=employee
                # contacts=contacts,
                # documents=documents,
                # address=address
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em employee_details: {e}")
        return redirect(url_for('personal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em employee_details: {e}")
        return redirect(url_for('personal_module'))

@app.route('/personal/export/excel')
@login_required
def export_employees_excel():
    if not current_user.can_access_module('Pessoal'): # Você pode criar uma permissão específica para exportação
        flash('Acesso negado. Você não tem permissão para exportar dados.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            personal_manager = PersonalManager(db_base)
            # Opcional: Você pode querer aplicar os mesmos filtros que na tabela
            # employees_data = personal_manager.get_all_employees(
            #    search_matricula=request.args.get('matricula'),
            #    search_name=request.args.get('nome'),
            #    # ... e outros filtros
            # )
            # Ou exportar todos os funcionários
            employees_data = personal_manager.get_all_employees()

            if not employees_data:
                flash('Nenhum funcionário encontrado para exportar.', 'info')
                return redirect(url_for('personal_module'))

            # Crie um DataFrame do Pandas
            df = pd.DataFrame(employees_data)

            # Renomeie colunas para serem mais amigáveis no Excel (opcional)
            df = df.rename(columns={
                'Matricula': 'Matrícula',
                'Nome_Completo': 'Nome Completo',
                'Data_Admissao': 'Data de Admissão',
                'Status': 'Status',
                'Tipo_Contratacao': 'Tipo Contratação',
                'Nome_Cargo': 'Cargo',
                'Nome_Nivel': 'Nível'
            })

            # Mova as colunas para uma ordem específica se desejar (opcional)
            ordered_columns = [
                'Matrícula', 'Nome Completo', 'Data de Admissão', 'Cargo',
                'Nível', 'Status', 'Tipo Contratação'
            ]
            # Garante que apenas as colunas desejadas e existentes sejam incluídas
            df = df[[col for col in ordered_columns if col in df.columns]]


            # Crie um buffer em memória para o arquivo Excel
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0) # Retorna ao início do buffer

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_funcionarios.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar para Excel: {e}", 'danger')
        print(f"Erro ao exportar Excel: {e}") # Para depuração no terminal
        return redirect(url_for('personal_module'))

#---------------------------------------------------------------------------------------------------
#--- Rotas para o Módulo Obras
#---------------------------------------------------------------------------------------------------
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
            users = user_manager.get_all_users() # Obter todos os usuários (agora com email)
            # CORREÇÃO: Nome do template de 'users.html' para 'users/users_module.html'
            return render_template('users/users_module.html', users=users, user=current_user)
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
        email = request.form['email'] # NOVO: Captura o campo email
        password = request.form['password']
        role = request.form['role']

        try:
            with DatabaseManager(**db_config) as db_base:
                user_manager = UserManager(db_base)

                # NOVO: Validação de unicidade para username
                if user_manager.find_user_by_username(username):
                    flash(f"Usuário '{username}' já existe. Por favor, escolha outro.", 'danger')
                    # Preserva os dados digitados para o usuário não ter que digitar tudo de novo
                    available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
                    return render_template('users/add_user.html', user=current_user, available_roles=available_roles,
                                            old_username=username, old_email=email, old_role=role)

                # NOVO: Validação de unicidade para email
                if user_manager.find_user_by_email(email):
                    flash(f"Este e-mail '{email}' já está em uso. Por favor, escolha outro.", 'danger')
                    # Preserva os dados digitados
                    available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
                    return render_template('users/add_user.html', user=current_user, available_roles=available_roles,
                                            old_username=username, old_email=email, old_role=role)

                # ALTERAÇÃO: Passa o email para o método add_user
                new_user_id = user_manager.add_user(username, password, role, email)
                if new_user_id:
                    flash(f"Usuário '{username}' adicionado com sucesso!", 'success')
                    return redirect(url_for('users_module'))
                else:
                    flash("Erro ao adicionar usuário.", 'danger')
        except mysql.connector.Error as e:
            flash(f"Erro de banco de dados: {e}", 'danger')
            print(f"Erro de banco de dados: {e}")
        except Exception as e:
            flash(f"Ocorreu um erro inesperado: {e}", 'danger')
            print(f"Erro inesperado durante a adição de usuário: {e}")

    # Para a página GET, ou em caso de erro no POST
    # Pode-se passar a lista de roles disponíveis para o template
    available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
    # CORREÇÃO: Nome do template de 'add_user.html' para 'users/add_user.html'
    return render_template('users/add_user.html', user=current_user, available_roles=available_roles)

@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem editar usuários.', 'warning')
        return redirect(url_for('users_module'))

    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            # ALTERAÇÃO: user_to_edit agora inclui o campo 'email'
            user_to_edit = user_manager.find_user_by_id(user_id)

            if not user_to_edit:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('users_module'))

            if request.method == 'POST':
                new_username = request.form.get('username')
                new_email = request.form.get('email') # NOVO: Captura o campo email
                new_password = request.form.get('password') # Pode ser vazio se não for alterada
                new_role = request.form.get('role')

                # Validação básica
                if not new_username or not new_role or not new_email: # NOVO: Email é obrigatório
                    flash("Nome de usuário, Email e Papel (Role) são obrigatórios.", 'danger')
                    # CORREÇÃO: Nome do template de 'edit_user.html' para 'users/edit_user.html'
                    return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])

                # Validação de unicidade do username (se for alterado e já existir)
                if new_username != user_to_edit['username']:
                    existing_user_with_new_name = user_manager.find_user_by_username(new_username)
                    if existing_user_with_new_name and existing_user_with_new_name['id'] != user_id:
                        flash(f"O nome de usuário '{new_username}' já está em uso por outro usuário.", 'danger')
                        # CORREÇÃO: Nome do template de 'edit_user.html' para 'users/edit_user.html'
                        return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])

                # NOVO: Validação de unicidade do email (se for alterado e já existir)
                if new_email != user_to_edit['email']:
                    existing_user_with_new_email = user_manager.find_user_by_email(new_email)
                    if existing_user_with_new_email and existing_user_with_new_email['id'] != user_id:
                        flash(f"O e-mail '{new_email}' já está em uso por outro usuário.", 'danger')
                        # CORREÇÃO: Nome do template de 'edit_user.html' para 'users/edit_user.html'
                        return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])

                # ALTERAÇÃO: Passa o new_email para o método update_user
                success = user_manager.update_user(user_id, new_username, new_password if new_password else None, new_role, new_email)
                if success:
                    flash(f"Usuário '{user_to_edit['username']}' atualizado com sucesso!", 'success')
                    return redirect(url_for('users_module'))
                else:
                    flash("Erro ao atualizar usuário.", 'danger')

            # GET request
            available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
            # CORREÇÃO: Nome do template de 'edit_user.html' para 'users/edit_user.html'
            return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=available_roles)

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
            # user_to_manage agora inclui o campo 'email'
            user_to_manage = user_manager.find_user_by_id(user_id)

            if not user_to_manage:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('users_module'))

            # Admins sempre têm acesso total, suas permissões não devem ser editáveis aqui
            if user_to_manage['role'] == 'admin':
                flash('As permissões de um administrador são totais por padrão e não podem ser gerenciadas individualmente.', 'info')
                # CORREÇÃO: Nome do template de 'manage_permissions.html' para 'users/manage_permissions.html'
                return render_template('users/manage_permissions.html',
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
            # CORREÇÃO: Nome do template de 'manage_permissions.html' para 'users/manage_permissions.html'
            return render_template('users/manage_permissions.html',
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