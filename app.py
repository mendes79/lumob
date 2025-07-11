# app.py
# rev01 - integração do campo email da tabela usuarios no app.py

#################################################################
# 0. CONFIGURAÇÕES INICIAIS
#################################################################

# ===============================================================
# 0.1 IMPORTAÇÕES E BIBLIOTECAS
# ===============================================================

# Necessária para carregar credenciais e senhas do .env
import os 
from dotenv import load_dotenv # Idem

from flask import Flask, render_template, redirect, url_for, request, flash, session, get_flashed_messages, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import mysql.connector              # Para a classe Error do MySQL
from datetime import datetime, date # Garante que datetime e date estejam disponíveis

# Para a adição da opção exportar para Excel no módulo Pessoal
from flask import send_file # Adicione este import no topo do seu app.py
import pandas as pd         # Adicione este import no topo do seu app.py
from io import BytesIO      # Adicione este import no topo do seu app.py

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_user_manager import UserManager
# from database.db_hr_manager import HrManager # Para o módulo de RH/DP (mantido para estrutura) <<< ver se ainda precisa! Pode apagar!!!
# from database.db_obras_manager import ObrasManager # Para o módulo Obras
from database.db_seguranca_manager import SegurancaManager # Para o módulo Segurança
# from database.db_pessoal_manager import PessoalManager

# Imaportações para Blueprint
from modulos.users_bp import users_bp # NOVO: Importa o Blueprint de Usuários
from modulos.pessoal_bp import pessoal_bp
from modulos.obras_bp import obras_bp

# ===============================================================
# 0.2 CONFIGURAÇÃO DA APLICAÇÃO
# ===============================================================
app = Flask(__name__)

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
app.jinja_env.globals.update(today=date.today) 

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
        if self.role == 'admin':                # Admin sempre tem acesso total, ignora permissões de módulo
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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

# ===============================================================
# 1.2 BOAS VINDAS (WELCOME) APÓS LOGIN: APRESENTA OS MÓDULOS
# ===============================================================
@app.route('/welcome')
@login_required
def welcome():
    # Isso garante que as permissões do usuário logado estejam atualizadas
    # no objeto current_user antes de renderizar welcome.html
    # É importante após o gerenciamento de permissões.
    try:
        with DatabaseManager(**db_config) as db_base:
            user_manager = UserManager(db_base)
            # Atualiza o atributo permissions do objeto current_user
            current_user.permissions = user_manager.get_user_permissions(current_user.id)
            # Recarrega o email para garantir que current_user esteja atualizado
            updated_user_data = user_manager.find_user_by_id(current_user.id)
            if updated_user_data:
                current_user.email = updated_user_data.get('email')
    except Exception as e:
        print(f"Erro ao carregar permissões e/ou email para current_user em welcome: {e}")
        current_user.permissions = []   # Garante que seja uma lista vazia em caso de erro
        current_user.email = None       # Garante que seja None em caso de erro

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

#################################################################
# 4. MÓDULO SEGURANCA
#################################################################

@app.route('/seguranca')
@login_required
def seguranca_module():
    # Esta função será o endpoint 'seguranca_module'
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Segurança.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            # Futuramente, você pode buscar dados relacionados à segurança aqui
            pass
            
        return render_template(
            'seguranca/seguranca_module.html',
            user=current_user
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar módulo Segurança: {e}", 'danger')
        print(f"Erro de banco de dados em seguranca_module: {e}")
        return redirect(url_for('welcome'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar módulo Segurança: {e}", 'danger')
        print(f"Erro inesperado em seguranca_module: {e}")
        return redirect(url_for('welcome'))

# ===============================================================
# 4.1 ROTAS DE INCIDENTES_ACIDENTES - SEGURANCA
# ===============================================================
@app.route('/seguranca/incidentes_acidentes')
@login_required
def incidentes_acidentes_module():
    if not current_user.can_access_module('Segurança'): # Ou permissão específica para SSMA
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Incidentes e Acidentes.', 'warning')
        return redirect(url_for('welcome'))

    search_tipo = request.args.get('tipo_registro')
    search_status = request.args.get('status_registro')
    search_obra_id = request.args.get('obra_id')
    search_responsavel_matricula = request.args.get('responsavel_matricula')

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            incidentes = seguranca_manager.get_all_incidentes_acidentes(
                search_tipo=search_tipo,
                search_status=search_status,
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_responsavel_matricula=search_responsavel_matricula
            )
            
            # Obter listas para dropdowns de filtro
            # Assumindo que ObrasManager ou PessoalManager podem fornecer essas listas
            obras_manager = ObrasManager(db_base) # Precisa instanciar para pegar obras
            pessoal_manager = PessoalManager(db_base) # Precisa instanciar para pegar funcionários

            all_obras = obras_manager.get_all_obras_for_dropdown()
            all_funcionarios = pessoal_manager.get_all_funcionarios() # Retorna todos os funcionários
            
            tipo_registro_options = ['Incidente', 'Acidente']
            status_registro_options = ['Aberto', 'Em Investigação', 'Concluído', 'Fechado']

        return render_template(
            'seguranca/incidentes_acidentes/incidentes_acidentes_module.html',
            user=current_user,
            incidentes=incidentes,
            all_obras=all_obras,
            all_funcionarios=all_funcionarios,
            tipo_registro_options=tipo_registro_options,
            status_registro_options=status_registro_options,
            selected_tipo=search_tipo,
            selected_status=search_status,
            selected_obra_id=int(search_obra_id) if search_obra_id else None,
            selected_responsavel_matricula=search_responsavel_matricula
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Incidentes/Acidentes: {e}", 'danger')
        print(f"Erro de banco de dados em incidentes_acidentes_module: {e}")
        return redirect(url_for('seguranca_module')) # Volta para o hub de segurança
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Incidentes/Acidentes: {e}", 'danger')
        print(f"Erro inesperado em incidentes_acidentes_module: {e}")
        return redirect(url_for('seguranca_module')) # Volta para o hub de segurança

# ---------------------------------------------------------------
# 4.1.1 ROTAS DO CRUD DE INCIDENTES_ACIDENTES - CRIAR - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/incidentes_acidentes/add', methods=['GET', 'POST'])
@login_required
def add_incidente_acidente():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para adicionar Incidentes/Acidentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            obras_manager = ObrasManager(db_base)
            pessoal_manager = PessoalManager(db_base)
            
            # Carrega opções para os dropdowns
            all_obras = obras_manager.get_all_obras_for_dropdown()
            all_funcionarios = pessoal_manager.get_all_funcionarios() # Para responsável
            tipo_registro_options = ['Incidente', 'Acidente']
            status_registro_options = ['Aberto', 'Em Investigação', 'Concluído', 'Fechado']

            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                tipo_registro = form_data_received.get('tipo_registro', '').strip()
                data_hora_ocorrencia_str = form_data_received.get('data_hora_ocorrencia', '').strip()
                local_ocorrencia = form_data_received.get('local_ocorrencia', '').strip()
                id_obras = form_data_received.get('id_obras')
                descricao_resumida = form_data_received.get('descricao_resumida', '').strip()
                causas_identificadas = form_data_received.get('causas_identificadas', '').strip()
                acoes_corretivas_tomadas = form_data_received.get('acoes_corretivas_tomadas', '').strip()
                acoes_preventivas_recomendadas = form_data_received.get('acoes_preventivas_recomendadas', '').strip()
                status_registro = form_data_received.get('status_registro', '').strip()
                responsavel_matricula = form_data_received.get('responsavel_matricula', '').strip()
                data_fechamento_str = form_data_received.get('data_fechamento', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                data_hora_ocorrencia = None
                data_fechamento = None
                is_valid = True

                if not all([tipo_registro, data_hora_ocorrencia_str, descricao_resumida, status_registro]):
                    flash('Campos obrigatórios (Tipo, Data/Hora, Descrição, Status) não podem ser vazios.', 'danger')
                    is_valid = False
                
                try:
                    data_hora_ocorrencia = datetime.strptime(data_hora_ocorrencia_str, '%Y-%m-%dT%H:%M') # Para input type="datetime-local"
                except ValueError:
                    flash('Formato de Data/Hora de Ocorrência inválido. Use AAAA-MM-DDTHH:MM.', 'danger')
                    is_valid = False
                
                if data_fechamento_str:
                    try:
                        data_fechamento = datetime.strptime(data_fechamento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Fechamento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False

                # Recarrega os dados do formulário para o dicionário que será passado para o template em caso de falha
                form_data_to_template = form_data_received
                form_data_to_template['data_hora_ocorrencia'] = data_hora_ocorrencia_str # Mantém string para input
                form_data_to_template['data_fechamento'] = data_fechamento_str # Mantém string para input

                if is_valid:
                    success = seguranca_manager.add_incidente_acidente(
                        tipo_registro, data_hora_ocorrencia, local_ocorrencia, 
                        int(id_obras) if id_obras else None, descricao_resumida, 
                        causas_identificadas, acoes_corretivas_tomadas, acoes_preventivas_recomendadas, 
                        status_registro, responsavel_matricula if responsavel_matricula else None, 
                        data_fechamento, observacoes
                    )
                    if success:
                        flash('Registro de Incidente/Acidente adicionado com sucesso!', 'success')
                        return redirect(url_for('incidentes_acidentes_module'))
                    else:
                        flash('Erro ao adicionar registro de Incidente/Acidente. Verifique os dados e tente novamente.', 'danger')
            
            # GET request ou POST com falha de validação
            return render_template(
                'seguranca/incidentes_acidentes/add_incidente_acidente.html',
                user=current_user,
                all_obras=all_obras,
                all_funcionarios=all_funcionarios,
                tipo_registro_options=tipo_registro_options,
                status_registro_options=status_registro_options,
                form_data=form_data_to_template
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_incidente_acidente: {e}")
        return redirect(url_for('incidentes_acidentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_incidente_acidente: {e}")
        return redirect(url_for('incidentes_acidentes_module'))

# ---------------------------------------------------------------
# 4.1.2 ROTAS DO CRUD DE INCIDENTES_ACIDENTES- EDITAR - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/incidentes_acidentes/edit/<int:incidente_id>', methods=['GET', 'POST'])
@login_required
def edit_incidente_acidente(incidente_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para editar Incidentes/Acidentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            obras_manager = ObrasManager(db_base)
            pessoal_manager = PessoalManager(db_base)

            # Sempre busca o registro para o GET inicial ou para re-exibir em caso de POST com erro
            incidente_from_db = seguranca_manager.get_incidente_acidente_by_id(incidente_id)
            if not incidente_from_db:
                flash('Registro de Incidente/Acidente não encontrado.', 'danger')
                return redirect(url_for('incidentes_acidentes_module'))

            # Carrega opções para os dropdowns
            all_obras = obras_manager.get_all_obras_for_dropdown()
            all_funcionarios = pessoal_manager.get_all_funcionarios()
            tipo_registro_options = ['Incidente', 'Acidente']
            status_registro_options = ['Aberto', 'Em Investigação', 'Concluído', 'Fechado']

            form_data_to_template = {} # Inicializa para o GET ou falha do POST

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                tipo_registro = form_data_received.get('tipo_registro', '').strip()
                data_hora_ocorrencia_str = form_data_received.get('data_hora_ocorrencia', '').strip()
                local_ocorrencia = form_data_received.get('local_ocorrencia', '').strip()
                id_obras = form_data_received.get('id_obras')
                descricao_resumida = form_data_received.get('descricao_resumida', '').strip()
                causas_identificadas = form_data_received.get('causas_identificadas', '').strip()
                acoes_corretivas_tomadas = form_data_received.get('acoes_corretivas_tomadas', '').strip()
                acoes_preventivas_recomendadas = form_data_received.get('acoes_preventivas_recomendadas', '').strip()
                status_registro = form_data_received.get('status_registro', '').strip()
                responsavel_matricula = form_data_received.get('responsavel_matricula', '').strip()
                data_fechamento_str = form_data_received.get('data_fechamento', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                data_hora_ocorrencia = None
                data_fechamento = None
                is_valid = True

                if not all([tipo_registro, data_hora_ocorrencia_str, descricao_resumida, status_registro]):
                    flash('Campos obrigatórios (Tipo, Data/Hora, Descrição, Status) não podem ser vazios.', 'danger')
                    is_valid = False
                
                try:
                    data_hora_ocorrencia = datetime.strptime(data_hora_ocorrencia_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash('Formato de Data/Hora de Ocorrência inválido. Use AAAA-MM-DDTHH:MM.', 'danger')
                    is_valid = False
                
                if data_fechamento_str:
                    try:
                        data_fechamento = datetime.strptime(data_fechamento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Fechamento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False

                # Recarrega os dados do formulário para o dicionário que será passado para o template em caso de falha
                form_data_to_template = form_data_received
                form_data_to_template['data_hora_ocorrencia'] = data_hora_ocorrencia_str # Mantém string para input
                form_data_to_template['data_fechamento'] = data_fechamento_str # Mantém string para input

                if is_valid:
                    success = seguranca_manager.update_incidente_acidente(
                        incidente_id, tipo_registro, data_hora_ocorrencia, local_ocorrencia,
                        int(id_obras) if id_obras else None, descricao_resumida,
                        causas_identificadas, acoes_corretivas_tomadas,
                        acoes_preventivas_recomendadas, # <--- CORRIGIDO AQUI: 'recomenadas' para 'recomendadas'
                        status_registro, responsavel_matricula if responsavel_matricula else None,
                        data_fechamento, observacoes
                    )
                    if success:
                        flash('Registro de Incidente/Acidente atualizado com sucesso!', 'success')
                        return redirect(url_for('incidentes_acidentes_module'))
                    else:
                        flash('Erro ao atualizar registro de Incidente/Acidente. Verifique os dados e tente novamente.', 'danger')
            
            else: # GET request
                # Prepara os dados do DB para exibição inicial no formulário GET
                form_data_to_template = incidente_from_db.copy()
                # Formatar datetime para o input type="datetime-local"
                form_data_to_template['Data_Hora_Ocorrencia'] = form_data_to_template['Data_Hora_Ocorrencia'].strftime('%Y-%m-%dT%H:%M') if form_data_to_template['Data_Hora_Ocorrencia'] else ''
                # Formatar data para o input type="date"
                form_data_to_template['Data_Fechamento'] = form_data_to_template['Data_Fechamento'].strftime('%Y-%m-%d') if form_data_to_template['Data_Fechamento'] else ''
                # Converter ID_Obras para string para o select
                form_data_to_template['ID_Obras'] = str(form_data_to_template['ID_Obras']) if form_data_to_template['ID_Obras'] else ''


            return render_template(
                'seguranca/incidentes_acidentes/edit_incidente_acidente.html',
                user=current_user,
                incidente=form_data_to_template,
                all_obras=all_obras,
                all_funcionarios=all_funcionarios,
                tipo_registro_options=tipo_registro_options,
                status_registro_options=status_registro_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_incidente_acidente: {e}")
        return redirect(url_for('incidentes_acidentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_incidente_acidente: {e}")
        return redirect(url_for('incidentes_acidentes_module'))

# ---------------------------------------------------------------
# 4.1.3 ROTAS DO CRUD DE INCIDENTES_ACIDENTES- DELETAR- SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/incidentes_acidentes/delete/<int:incidente_id>', methods=['POST'])
@login_required
def delete_incidente_acidente(incidente_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para excluir Incidentes/Acidentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_incidente_acidente(incidente_id)
            if success:
                flash('Registro de Incidente/Acidente excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir registro de Incidente/Acidente. Verifique se ele existe.', 'danger')
        return redirect(url_for('incidentes_acidentes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_incidente_acidente: {e}")
        return redirect(url_for('incidentes_acidentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_incidente_acidente: {e}")
        return redirect(url_for('incidentes_acidentes_module'))

# ---------------------------------------------------------------
# 4.1.4 ROTAS DO CRUD DE INCIDENTES_ACIDENTES -DETALHES SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/incidentes_acidentes/details/<int:incidente_id>')
@login_required
def incidente_acidente_details(incidente_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Incidentes/Acidentes.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            incidente = seguranca_manager.get_incidente_acidente_by_id(incidente_id)

            if not incidente:
                flash('Registro de Incidente/Acidente não encontrado.', 'danger')
                return redirect(url_for('incidentes_acidentes_module'))

        return render_template(
            'seguranca/incidentes_acidentes/incidente_acidente_details.html',
            user=current_user,
            incidente=incidente
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em incidente_acidente_details: {e}")
        return redirect(url_for('incidentes_acidentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em incidente_acidente_details: {e}")
        return redirect(url_for('incidentes_acidentes_module'))

# ---------------------------------------------------------------
# 4.1.5 ROTA INCIDENTES_ACIDENTES - EXPORTAR P/ EXCEL - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/incidentes_acidentes/export/excel')
@login_required
def export_incidentes_acidentes_excel():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Incidentes/Acidentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            search_tipo = request.args.get('tipo_registro')
            search_status = request.args.get('status_registro')
            search_obra_id = request.args.get('obra_id')
            search_responsavel_matricula = request.args.get('responsavel_matricula')

            incidentes_data = seguranca_manager.get_all_incidentes_acidentes(
                search_tipo=search_tipo,
                search_status=search_status,
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_responsavel_matricula=search_responsavel_matricula
            )

            if not incidentes_data:
                flash('Nenhum registro de Incidente/Acidente encontrado para exportar.', 'info')
                return redirect(url_for('incidentes_acidentes_module'))

            df = pd.DataFrame(incidentes_data)

            # Renomeie colunas para serem mais amigáveis no Excel
            df = df.rename(columns={
                'ID_Incidente_Acidente': 'ID Registro',
                'Tipo_Registro': 'Tipo de Registro',
                'Data_Hora_Ocorrencia': 'Data/Hora Ocorrência',
                'Local_Ocorrencia': 'Local',
                'ID_Obras': 'ID Obra',
                'Descricao_Resumida': 'Descrição Resumida',
                'Causas_Identificadas': 'Causas',
                'Acoes_Corretivas_Tomadas': 'Ações Corretivas',
                'Acoes_Preventivas_Recomendadas': 'Ações Preventivas',
                'Status_Registro': 'Status',
                'Responsavel_Investigacao_Funcionario_Matricula': 'Matrícula Responsável',
                'Nome_Responsavel_Investigacao': 'Nome Responsável',
                'Data_Fechamento': 'Data de Fechamento',
                'Observacoes': 'Observações',
                'Numero_Obra': 'Número da Obra',
                'Nome_Obra': 'Nome da Obra',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
            ordered_columns = [
                'ID Registro', 'Tipo de Registro', 'Data/Hora Ocorrência', 'Local',
                'Número da Obra', 'Nome da Obra', 'Descrição Resumida', 'Status',
                'Matrícula Responsável', 'Nome Responsável', 'Data de Fechamento',
                'Causas', 'Ações Corretivas', 'Ações Preventivas', 'Observações',
                'Data de Criação', 'Última Modificação'
            ]
            df = df[[col for col in ordered_columns if col in df.columns]]

            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_incidentes_acidentes.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Incidentes/Acidentes para Excel: {e}", 'danger')
        print(f"Erro ao exportar Incidentes/Acidentes Excel: {e}")
        return redirect(url_for('incidentes_acidentes_module'))

# ===============================================================
# 4.2 ROTAS DE ASOS - SEGURANCA
# ===============================================================
@app.route('/seguranca/asos')
@login_required
def asos_module():
    if not current_user.can_access_module('Segurança'): # Ou permissão específica para ASOs
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de ASOs.', 'warning')
        return redirect(url_for('welcome'))

    search_matricula = request.args.get('matricula')
    search_tipo = request.args.get('tipo_aso')
    search_resultado = request.args.get('resultado')
    search_data_emissao_inicio = request.args.get('data_emissao_inicio')
    search_data_emissao_fim = request.args.get('data_emissao_fim')

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            pessoal_manager = PessoalManager(db_base) # Para obter lista de funcionários

            asos = seguranca_manager.get_all_asos(
                search_matricula=search_matricula,
                search_tipo=search_tipo,
                search_resultado=search_resultado,
                search_data_emissao_inicio=datetime.strptime(search_data_emissao_inicio, '%Y-%m-%d').date() if search_data_emissao_inicio else None,
                search_data_emissao_fim=datetime.strptime(search_data_emissao_fim, '%Y-%m-%d').date() if search_data_emissao_fim else None
            )
            
            all_funcionarios = pessoal_manager.get_all_funcionarios() # Para dropdown de funcionário
            tipo_aso_options = ['Admissional', 'Periódico', 'Mudança de Função', 'Retorno ao Trabalho', 'Demissional', 'Outro']
            resultado_options = ['Apto', 'Inapto', 'Apto com Restrições']

        return render_template(
            'seguranca/asos/asos_module.html',
            user=current_user,
            asos=asos,
            all_funcionarios=all_funcionarios,
            tipo_aso_options=tipo_aso_options,
            resultado_options=resultado_options,
            selected_matricula=search_matricula,
            selected_tipo=search_tipo,
            selected_resultado=search_resultado,
            selected_data_emissao_inicio=search_data_emissao_inicio,
            selected_data_emissao_fim=search_data_emissao_fim
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar ASOs: {e}", 'danger')
        print(f"Erro de banco de dados em asos_module: {e}")
        return redirect(url_for('seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar ASOs: {e}", 'danger')
        print(f"Erro inesperado em asos_module: {e}")
        return redirect(url_for('seguranca_module'))

# ---------------------------------------------------------------
# 4.2.1 ROTAS DO CRUD DE ASOS - CRIAR - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/asos/add', methods=['GET', 'POST'])
@login_required
def add_aso():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para adicionar ASOs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            pessoal_manager = PessoalManager(db_base)
            
            all_funcionarios = pessoal_manager.get_all_funcionarios()
            tipo_aso_options = ['Admissional', 'Periódico', 'Mudança de Função', 'Retorno ao Trabalho', 'Demissional', 'Outro']
            resultado_options = ['Apto', 'Inapto', 'Apto com Restrições']

            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                tipo_aso = form_data_received.get('tipo_aso', '').strip()
                data_emissao_str = form_data_received.get('data_emissao', '').strip()
                data_vencimento_str = form_data_received.get('data_vencimento', '').strip()
                resultado = form_data_received.get('resultado', '').strip()
                medico_responsavel = form_data_received.get('medico_responsavel', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                data_emissao = None
                data_vencimento = None
                is_valid = True

                if not all([matricula_funcionario, tipo_aso, data_emissao_str, resultado]):
                    flash('Campos obrigatórios (Funcionário, Tipo, Data Emissão, Resultado) não podem ser vazios.', 'danger')
                    is_valid = False
                
                try:
                    data_emissao = datetime.strptime(data_emissao_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Emissão inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False
                
                if data_vencimento_str:
                    try:
                        data_vencimento = datetime.strptime(data_vencimento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Vencimento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False

                form_data_to_template = form_data_received
                form_data_to_template['data_emissao'] = data_emissao_str
                form_data_to_template['data_vencimento'] = data_vencimento_str

                if is_valid:
                    success = seguranca_manager.add_aso(
                        matricula_funcionario, tipo_aso, data_emissao, data_vencimento,
                        resultado, medico_responsavel, observacoes
                    )
                    if success:
                        flash('ASO adicionado com sucesso!', 'success')
                        return redirect(url_for('asos_module'))
                    else:
                        flash('Erro ao adicionar ASO. Verifique os dados e tente novamente.', 'danger')
            
            return render_template(
                'seguranca/asos/add_aso.html',
                user=current_user,
                all_funcionarios=all_funcionarios,
                tipo_aso_options=tipo_aso_options,
                resultado_options=resultado_options,
                form_data=form_data_to_template
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_aso: {e}")
        return redirect(url_for('asos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_aso: {e}")
        return redirect(url_for('asos_module'))

# ---------------------------------------------------------------
# 4.2.2 ROTAS DO CRUD DE ASOS - EDITAR - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/asos/edit/<int:aso_id>', methods=['GET', 'POST'])
@login_required
def edit_aso(aso_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para editar ASOs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            pessoal_manager = PessoalManager(db_base)

            aso_from_db = seguranca_manager.get_aso_by_id(aso_id)
            if not aso_from_db:
                flash('ASO não encontrado.', 'danger')
                return redirect(url_for('asos_module'))

            all_funcionarios = pessoal_manager.get_all_funcionarios()
            tipo_aso_options = ['Admissional', 'Periódico', 'Mudança de Função', 'Retorno ao Trabalho', 'Demissional', 'Outro']
            resultado_options = ['Apto', 'Inapto', 'Apto com Restrições']

            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                tipo_aso = form_data_received.get('tipo_aso', '').strip()
                data_emissao_str = form_data_received.get('data_emissao', '').strip()
                data_vencimento_str = form_data_received.get('data_vencimento', '').strip()
                resultado = form_data_received.get('resultado', '').strip()
                medico_responsavel = form_data_received.get('medico_responsavel', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                data_emissao = None
                data_vencimento = None
                is_valid = True

                if not all([matricula_funcionario, tipo_aso, data_emissao_str, resultado]):
                    flash('Campos obrigatórios (Funcionário, Tipo, Data Emissão, Resultado) não podem ser vazios.', 'danger')
                    is_valid = False
                
                try:
                    data_emissao = datetime.strptime(data_emissao_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Emissão inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False
                
                if data_vencimento_str:
                    try:
                        data_vencimento = datetime.strptime(data_vencimento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Vencimento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False

                form_data_to_template = form_data_received
                form_data_to_template['data_emissao'] = data_emissao_str
                form_data_to_template['data_vencimento'] = data_vencimento_str

                if is_valid:
                    success = seguranca_manager.update_aso(
                        aso_id, matricula_funcionario, tipo_aso, data_emissao, data_vencimento,
                        resultado, medico_responsavel, observacoes
                    )
                    if success:
                        flash('ASO atualizado com sucesso!', 'success')
                        return redirect(url_for('asos_module'))
                    else:
                        flash('Erro ao atualizar ASO. Verifique os dados e tente novamente.', 'danger')
            
            else: # GET request
                form_data_to_template = aso_from_db.copy()
                form_data_to_template['Data_Emissao'] = form_data_to_template['Data_Emissao'].strftime('%Y-%m-%d') if form_data_to_template['Data_Emissao'] else ''
                form_data_to_template['Data_Vencimento'] = form_data_to_template['Data_Vencimento'].strftime('%Y-%m-%d') if form_data_to_template['Data_Vencimento'] else ''
                
            return render_template(
                'seguranca/asos/edit_aso.html',
                user=current_user,
                aso=form_data_to_template,
                all_funcionarios=all_funcionarios,
                tipo_aso_options=tipo_aso_options,
                resultado_options=resultado_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_aso: {e}")
        return redirect(url_for('asos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_aso: {e}")
        return redirect(url_for('asos_module'))

# ---------------------------------------------------------------
# 4.2.3 ROTAS DO CRUD DE ASOS - DELETAR - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/asos/delete/<int:aso_id>', methods=['POST'])
@login_required
def delete_aso(aso_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para excluir ASOs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_aso(aso_id)
            if success:
                flash('ASO excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir ASO. Verifique se ele existe.', 'danger')
        return redirect(url_for('asos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_aso: {e}")
        return redirect(url_for('asos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_aso: {e}")
        return redirect(url_for('asos_module'))

# ---------------------------------------------------------------
# 4.2.4 ROTAS DO CRUD DE ASOS - DETALHES SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/asos/details/<int:aso_id>')
@login_required
def aso_details(aso_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de ASOs.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            aso = seguranca_manager.get_aso_by_id(aso_id)

            if not aso:
                flash('ASO não encontrado.', 'danger')
                return redirect(url_for('asos_module'))

        return render_template(
            'seguranca/asos/aso_details.html',
            user=current_user,
            aso=aso
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em aso_details: {e}")
        return redirect(url_for('asos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em aso_details: {e}")
        return redirect(url_for('asos_module'))

# ---------------------------------------------------------------
# 4.2.5 ROTA ASOS - EXPORTAR P/ EXCEL - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/asos/export/excel')
@login_required
def export_asos_excel():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para exportar dados de ASOs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            pessoal_manager = PessoalManager(db_base)
            
            search_matricula = request.args.get('matricula')
            search_tipo = request.args.get('tipo_aso')
            search_resultado = request.args.get('resultado')
            search_data_emissao_inicio = request.args.get('data_emissao_inicio')
            search_data_emissao_fim = request.args.get('data_emissao_fim')

            asos_data = seguranca_manager.get_all_asos(
                search_matricula=search_matricula,
                search_tipo=search_tipo,
                search_resultado=search_resultado,
                search_data_emissao_inicio=datetime.strptime(search_data_emissao_inicio, '%Y-%m-%d').date() if search_data_emissao_inicio else None,
                search_data_emissao_fim=datetime.strptime(search_data_emissao_fim, '%Y-%m-%d').date() if search_data_emissao_fim else None
            )

            if not asos_data:
                flash('Nenhum ASO encontrado para exportar.', 'info')
                return redirect(url_for('asos_module'))

            df = pd.DataFrame(asos_data)

            # Renomeie colunas para serem mais amigáveis no Excel
            df = df.rename(columns={
                'ID_ASO': 'ID ASO',
                'Matricula_Funcionario': 'Matrícula Funcionário',
                'Nome_Funcionario': 'Nome do Funcionário',
                'Tipo_ASO': 'Tipo de ASO',
                'Data_Emissao': 'Data de Emissão',
                'Data_Vencimento': 'Data de Vencimento',
                'Resultado': 'Resultado',
                'Medico_Responsavel': 'Médico Responsável',
                'Observacoes': 'Observações',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
            ordered_columns = [
                'ID ASO', 'Matrícula Funcionário', 'Nome do Funcionário', 'Tipo de ASO',
                'Data de Emissão', 'Data de Vencimento', 'Resultado', 'Médico Responsável',
                'Observações', 'Data de Criação', 'Última Modificação'
            ]
            df = df[[col for col in ordered_columns if col in df.columns]]

            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_asos.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar ASOs para Excel: {e}", 'danger')
        print(f"Erro ao exportar ASOs Excel: {e}")
        return redirect(url_for('asos_module'))


# ===============================================================
# 4.3 ROTAS DE TREINAMENTOS - SEGURANCA
# ===============================================================
@app.route('/seguranca/treinamentos')
@login_required
def treinamentos_module():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para acessar o Catálogo de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    search_nome = request.args.get('nome_treinamento')
    search_tipo = request.args.get('tipo_treinamento')

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            treinamentos = seguranca_manager.get_all_treinamentos(
                search_nome=search_nome,
                search_tipo=search_tipo
            )
            
            tipo_treinamento_options = ['Obrigatório', 'Reciclagem', 'Voluntário', 'Outro']

        return render_template(
            'seguranca/treinamentos/treinamentos_module.html',
            user=current_user,
            treinamentos=treinamentos,
            tipo_treinamento_options=tipo_treinamento_options,
            selected_nome=search_nome,
            selected_tipo=search_tipo
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Treinamentos: {e}", 'danger')
        print(f"Erro de banco de dados em treinamentos_module: {e}")
        return redirect(url_for('seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Treinamentos: {e}", 'danger')
        print(f"Erro inesperado em treinamentos_module: {e}")
        return redirect(url_for('seguranca_module'))

# ---------------------------------------------------------------
# 4.3.1 ROTAS DO CRUD DE TREINAMENTOS - CRIAR - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/treinamentos/add', methods=['GET', 'POST'])
@login_required
def add_treinamento():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para adicionar Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            tipo_treinamento_options = ['Obrigatório', 'Reciclagem', 'Voluntário', 'Outro']
            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                nome_treinamento = form_data_received.get('nome_treinamento', '').strip()
                descricao = form_data_received.get('descricao', '').strip()
                carga_horaria_horas = float(form_data_received.get('carga_horaria_horas', '0').replace(',', '.'))
                tipo_treinamento = form_data_received.get('tipo_treinamento', '').strip()
                validade_dias = int(form_data_received.get('validade_dias', 0)) if form_data_received.get('validade_dias', '').strip() else None
                instrutor_responsavel = form_data_received.get('instrutor_responsavel', '').strip()

                is_valid = True

                if not all([nome_treinamento, carga_horaria_horas, tipo_treinamento]):
                    flash('Campos obrigatórios (Nome, Carga Horária, Tipo) não podem ser vazios.', 'danger')
                    is_valid = False
                
                if seguranca_manager.get_treinamento_by_nome(nome_treinamento):
                    flash('Já existe um treinamento com este nome.', 'danger')
                    is_valid = False

                form_data_to_template = form_data_received # Para preencher o formulário em caso de erro

                if is_valid:
                    success = seguranca_manager.add_treinamento(
                        nome_treinamento, descricao, carga_horaria_horas, tipo_treinamento,
                        validade_dias, instrutor_responsavel
                    )
                    if success:
                        flash('Treinamento adicionado com sucesso!', 'success')
                        return redirect(url_for('treinamentos_module'))
                    else:
                        flash('Erro ao adicionar treinamento. Verifique os dados e tente novamente.', 'danger')
            
            return render_template(
                'seguranca/treinamentos/add_treinamento.html',
                user=current_user,
                tipo_treinamento_options=tipo_treinamento_options,
                form_data=form_data_to_template
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_treinamento: {e}")
        return redirect(url_for('treinamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_treinamento: {e}")
        return redirect(url_for('treinamentos_module'))

# ---------------------------------------------------------------
# 4.3.2 ROTAS DO CRUD DE TREINAMENTOS - EDITAR - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/treinamentos/edit/<int:treinamento_id>', methods=['GET', 'POST'])
@login_required
def edit_treinamento(treinamento_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para editar Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            treinamento_from_db = seguranca_manager.get_treinamento_by_id(treinamento_id)
            if not treinamento_from_db:
                flash('Treinamento não encontrado.', 'danger')
                return redirect(url_for('treinamentos_module'))

            tipo_treinamento_options = ['Obrigatório', 'Reciclagem', 'Voluntário', 'Outro']
            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                nome_treinamento = form_data_received.get('nome_treinamento', '').strip()
                descricao = form_data_received.get('descricao', '').strip()
                carga_horaria_horas = float(form_data_received.get('carga_horaria_horas', '0').replace(',', '.'))
                tipo_treinamento = form_data_received.get('tipo_treinamento', '').strip()
                validade_dias = int(form_data_received.get('validade_dias', 0)) if form_data_received.get('validade_dias', '').strip() else None
                instrutor_responsavel = form_data_received.get('instrutor_responsavel', '').strip()

                is_valid = True

                if not all([nome_treinamento, carga_horaria_horas, tipo_treinamento]):
                    flash('Campos obrigatórios (Nome, Carga Horária, Tipo) não podem ser vazios.', 'danger')
                    is_valid = False
                
                existing_treinamento = seguranca_manager.get_treinamento_by_nome(nome_treinamento)
                if existing_treinamento and existing_treinamento['ID_Treinamento'] != treinamento_id:
                    flash('Já existe um treinamento com este nome.', 'danger')
                    is_valid = False

                form_data_to_template = form_data_received # Para preencher o formulário em caso de erro

                if is_valid:
                    success = seguranca_manager.update_treinamento(
                        treinamento_id, nome_treinamento, descricao, carga_horaria_horas, tipo_treinamento,
                        validade_dias, instrutor_responsavel
                    )
                    if success:
                        flash('Treinamento atualizado com sucesso!', 'success')
                        return redirect(url_for('treinamentos_module'))
                    else:
                        flash('Erro ao atualizar treinamento. Verifique os dados e tente novamente.', 'danger')
            
            else: # GET request
                form_data_to_template = treinamento_from_db.copy()

            return render_template(
                'seguranca/treinamentos/edit_treinamento.html',
                user=current_user,
                treinamento=form_data_to_template,
                tipo_treinamento_options=tipo_treinamento_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_treinamento: {e}")
        return redirect(url_for('treinamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_treinamento: {e}")
        return redirect(url_for('treinamentos_module'))

# ---------------------------------------------------------------
# 4.3.3 ROTAS DO CRUD DE TREINAMENTOS - DELETAR - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/treinamentos/delete/<int:treinamento_id>', methods=['POST'])
@login_required
def delete_treinamento(treinamento_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para excluir Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_treinamento(treinamento_id)
            if success:
                flash('Treinamento excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir treinamento. Verifique se não há agendamentos associados.', 'danger')
        return redirect(url_for('treinamentos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_treinamento: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir o treinamento pois existem agendamentos associados a ele. Remova-os primeiro.", 'danger')
        return redirect(url_for('treinamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_treinamento: {e}")
        return redirect(url_for('treinamentos_module'))

# ---------------------------------------------------------------
# 4.3.4 ROTAS DO CRUD DE TREINAMENTOS - DETALHES SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/treinamentos/details/<int:treinamento_id>')
@login_required
def treinamento_details(treinamento_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            treinamento = seguranca_manager.get_treinamento_by_id(treinamento_id)

            if not treinamento:
                flash('Treinamento não encontrado.', 'danger')
                return redirect(url_for('treinamentos_module'))

        return render_template(
            'seguranca/treinamentos/treinamento_details.html',
            user=current_user,
            treinamento=treinamento
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em treinamento_details: {e}")
        return redirect(url_for('treinamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em treinamento_details: {e}")
        return redirect(url_for('treinamentos_module'))

# ---------------------------------------------------------------
# 4.3.5 ROTA TREINAMENTOS - EXPORTAR P/ EXCEL - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/treinamentos/export/excel')
@login_required
def export_treinamentos_excel():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            search_nome = request.args.get('nome_treinamento')
            search_tipo = request.args.get('tipo_treinamento')

            treinamentos_data = seguranca_manager.get_all_treinamentos(
                search_nome=search_nome,
                search_tipo=search_tipo
            )

            if not treinamentos_data:
                flash('Nenhum treinamento encontrado para exportar.', 'info')
                return redirect(url_for('treinamentos_module'))

            df = pd.DataFrame(treinamentos_data)

            df = df.rename(columns={
                'ID_Treinamento': 'ID Treinamento',
                'Nome_Treinamento': 'Nome do Treinamento',
                'Descricao': 'Descrição',
                'Carga_Horaria_Horas': 'Carga Horária (h)',
                'Tipo_Treinamento': 'Tipo de Treinamento',
                'Validade_Dias': 'Validade (dias)',
                'Instrutor_Responsavel': 'Instrutor Responsável',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_treinamentos.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Treinamentos para Excel: {e}", 'danger')
        print(f"Erro ao exportar Treinamentos Excel: {e}")
        return redirect(url_for('treinamentos_module'))


# ---------------------------------------------------------------
# 4.3.6 ROTAS RELATORIO DE TREINAMENTOS - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/relatorio_treinamentos')
@login_required
def seguranca_relatorio_treinamentos():
    """
    Rota para o relatório de treinamentos de segurança, com filtros.
    """
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para acessar o Relatório de Treinamentos de Segurança.', 'warning')
        return redirect(url_for('welcome'))

    # Coletar parâmetros de filtro
    search_nome_treinamento = request.args.get('nome_treinamento')
    search_tipo_treinamento = request.args.get('tipo_treinamento')
    search_status_agendamento = request.args.get('status_agendamento')
    search_matricula_participante = request.args.get('matricula_participante')

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            pessoal_manager = PessoalManager(db_base) # Necessário para o dropdown de funcionários

            # Chama o novo método para obter os dados do relatório
            treinamentos_relatorio_data = seguranca_manager.get_treinamentos_para_relatorio(
                search_nome_treinamento=search_nome_treinamento,
                search_tipo_treinamento=search_tipo_treinamento,
                search_status_agendamento=search_status_agendamento,
                search_matricula_participante=search_matricula_participante
            )
            
            # Obter listas para dropdowns de filtro
            all_treinamentos_for_filter = seguranca_manager.get_all_treinamentos_for_dropdown()
            all_funcionarios_for_filter = pessoal_manager.get_all_funcionarios() # Para o filtro de participante
            
            tipo_treinamento_options = ['Obrigatório', 'Reciclagem', 'Voluntário', 'Outro']
            status_agendamento_options = ['Programado', 'Realizado', 'Cancelado', 'Adiado']

            return render_template(
                'seguranca/treinamentos/treinamentos_relatorio.html', # Novo template que criaremos
                user=current_user,
                treinamentos_relatorio_data=treinamentos_relatorio_data,
                all_treinamentos_for_filter=all_treinamentos_for_filter,
                all_funcionarios_for_filter=all_funcionarios_for_filter,
                tipo_treinamento_options=tipo_treinamento_options,
                status_agendamento_options=status_agendamento_options,
                selected_nome_treinamento=search_nome_treinamento,
                selected_tipo_treinamento=search_tipo_treinamento,
                selected_status_agendamento=search_status_agendamento,
                selected_matricula_participante=search_matricula_participante
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar relatório de treinamentos de segurança: {e}", 'danger')
        print(f"Erro de banco de dados em seguranca_relatorio_treinamentos: {e}")
        return redirect(url_for('seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar relatório de treinamentos de segurança: {e}", 'danger')
        print(f"Erro inesperado em seguranca_relatorio_treinamentos: {e}")
        return redirect(url_for('seguranca_module'))

# ---------------------------------------------------------------
# 4.3.7 ROTAS TREINAMENTOS AGENDAMENTOS - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/treinamentos/agendamentos')
@login_required
def treinamentos_agendamentos_module():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Agendamentos de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    search_treinamento_id = request.args.get('treinamento_id')
    search_status = request.args.get('status_agendamento')
    search_data_inicio_str = request.args.get('data_inicio')
    search_data_fim_str = request.args.get('data_fim')

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            data_inicio = None
            data_fim = None
            if search_data_inicio_str:
                data_inicio = datetime.strptime(search_data_inicio_str, '%Y-%m-%d').date()
            if search_data_fim_str:
                data_fim = datetime.strptime(search_data_fim_str, '%Y-%m-%d').date()

            agendamentos = seguranca_manager.get_all_treinamentos_agendamentos(
                search_treinamento_id=int(search_treinamento_id) if search_treinamento_id else None,
                search_status=search_status,
                search_data_inicio=data_inicio,
                search_data_fim=data_fim
            )
            
            all_treinamentos = seguranca_manager.get_all_treinamentos_for_dropdown()
            status_agendamento_options = ['Programado', 'Realizado', 'Cancelado', 'Adiado']

        return render_template(
            'seguranca/treinamentos/agendamentos/agendamentos_module.html',
            user=current_user,
            agendamentos=agendamentos,
            all_treinamentos=all_treinamentos,
            status_agendamento_options=status_agendamento_options,
            selected_treinamento_id=int(search_treinamento_id) if search_treinamento_id else None,
            selected_status=search_status,
            selected_data_inicio=search_data_inicio_str,
            selected_data_fim=search_data_fim_str
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Agendamentos: {e}", 'danger')
        print(f"Erro de banco de dados em treinamentos_agendamentos_module: {e}")
        return redirect(url_for('seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Agendamentos: {e}", 'danger')
        print(f"Erro inesperado em treinamentos_agendamentos_module: {e}")
        return redirect(url_for('seguranca_module'))

# ·······························································
# 4.3.7.1 TREINAMENTOS AGENDAMENTOS CRUD CRIAR - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/agendamentos/add', methods=['GET', 'POST'])
@login_required
def add_treinamento_agendamento():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para adicionar Agendamentos de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            all_treinamentos = seguranca_manager.get_all_treinamentos_for_dropdown()
            status_agendamento_options = ['Programado', 'Realizado', 'Cancelado', 'Adiado']
            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                id_treinamento = int(form_data_received.get('id_treinamento'))
                data_hora_inicio_str = form_data_received.get('data_hora_inicio', '').strip()
                data_hora_fim_str = form_data_received.get('data_hora_fim', '').strip()
                local_treinamento = form_data_received.get('local_treinamento', '').strip()
                status_agendamento = form_data_received.get('status_agendamento', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                data_hora_inicio = None
                data_hora_fim = None
                is_valid = True

                if not all([id_treinamento, data_hora_inicio_str, status_agendamento]):
                    flash('Campos obrigatórios (Treinamento, Data/Hora Início, Status) não podem ser vazios.', 'danger')
                    is_valid = False
                
                try:
                    data_hora_inicio = datetime.strptime(data_hora_inicio_str, '%Y-%m-%dT%H:%M')
                    if data_hora_fim_str:
                        data_hora_fim = datetime.strptime(data_hora_fim_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash('Formato de data/hora inválido. Use AAAA-MM-DDTHH:MM.', 'danger')
                    is_valid = False
                
                form_data_to_template = form_data_received
                form_data_to_template['data_hora_inicio'] = data_hora_inicio_str
                form_data_to_template['data_hora_fim'] = data_hora_fim_str

                if is_valid:
                    success = seguranca_manager.add_treinamento_agendamento(
                        id_treinamento, data_hora_inicio, data_hora_fim, local_treinamento,
                        status_agendamento, observacoes
                    )
                    if success:
                        flash('Agendamento de Treinamento adicionado com sucesso!', 'success')
                        return redirect(url_for('treinamentos_agendamentos_module'))
                    else:
                        flash('Erro ao adicionar agendamento. Verifique os dados e tente novamente.', 'danger')
            
            return render_template(
                'seguranca/treinamentos/agendamentos/add_agendamento.html',
                user=current_user,
                all_treinamentos=all_treinamentos,
                status_agendamento_options=status_agendamento_options,
                form_data=form_data_to_template
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_treinamento_agendamento: {e}")
        return redirect(url_for('treinamentos_agendamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_treinamento_agendamento: {e}")
        return redirect(url_for('treinamentos_agendamentos_module'))

# ·······························································
# 4.3.7.2 TREINAMENTOS AGENDAMENTOS CRUD EDITAR - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/agendamentos/edit/<int:agendamento_id>', methods=['GET', 'POST'])
@login_required
def edit_treinamento_agendamento(agendamento_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para editar Agendamentos de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            agendamento_from_db = seguranca_manager.get_treinamento_agendamento_by_id(agendamento_id)
            if not agendamento_from_db:
                flash('Agendamento não encontrado.', 'danger')
                return redirect(url_for('treinamentos_agendamentos_module'))

            all_treinamentos = seguranca_manager.get_all_treinamentos_for_dropdown()
            status_agendamento_options = ['Programado', 'Realizado', 'Cancelado', 'Adiado']
            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                id_treinamento = int(form_data_received.get('id_treinamento'))
                data_hora_inicio_str = form_data_received.get('data_hora_inicio', '').strip()
                data_hora_fim_str = form_data_received.get('data_hora_fim', '').strip()
                local_treinamento = form_data_received.get('local_treinamento', '').strip()
                status_agendamento = form_data_received.get('status_agendamento', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                data_hora_inicio = None
                data_hora_fim = None
                is_valid = True

                if not all([id_treinamento, data_hora_inicio_str, status_agendamento]):
                    flash('Campos obrigatórios (Treinamento, Data/Hora Início, Status) não podem ser vazios.', 'danger')
                    is_valid = False
                
                try:
                    data_hora_inicio = datetime.strptime(data_hora_inicio_str, '%Y-%m-%dT%H:%M')
                    if data_hora_fim_str:
                        data_hora_fim = datetime.strptime(data_hora_fim_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    flash('Formato de data/hora inválido. Use AAAA-MM-DDTHH:MM.', 'danger')
                    is_valid = False

                form_data_to_template = form_data_received
                form_data_to_template['data_hora_inicio'] = data_hora_inicio_str
                form_data_to_template['data_hora_fim'] = data_hora_fim_str

                if is_valid:
                    success = seguranca_manager.update_treinamento_agendamento(
                        agendamento_id, id_treinamento, data_hora_inicio, data_hora_fim, local_treinamento,
                        status_agendamento, observacoes
                    )
                    if success:
                        flash('Agendamento atualizado com sucesso!', 'success')
                        return redirect(url_for('treinamentos_agendamentos_module'))
                    else:
                        flash('Erro ao atualizar agendamento. Verifique os dados e tente novamente.', 'danger')
            
            else: # GET request
                form_data_to_template = agendamento_from_db.copy()
                form_data_to_template['Data_Hora_Inicio'] = form_data_to_template['Data_Hora_Inicio'].strftime('%Y-%m-%dT%H:%M') if form_data_to_template['Data_Hora_Inicio'] else ''
                form_data_to_template['Data_Hora_Fim'] = form_data_to_template['Data_Hora_Fim'].strftime('%Y-%m-%dT%H:%M') if form_data_to_template['Data_Hora_Fim'] else ''
                
            return render_template(
                'seguranca/treinamentos/agendamentos/edit_agendamento.html',
                user=current_user,
                agendamento=form_data_to_template,
                all_treinamentos=all_treinamentos,
                status_agendamento_options=status_agendamento_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_treinamento_agendamento: {e}")
        return redirect(url_for('treinamentos_agendamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_treinamento_agendamento: {e}")
        return redirect(url_for('treinamentos_agendamentos_module'))

# ·······························································
# 4.3.7.3 TREINAMENTOS AGENDAMENTOS CRUD DELETAR - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/agendamentos/delete/<int:agendamento_id>', methods=['POST'])
@login_required
def delete_treinamento_agendamento(agendamento_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para excluir Agendamentos de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_treinamento_agendamento(agendamento_id)
            if success:
                flash('Agendamento de Treinamento excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir agendamento. Verifique se não há participantes associados.', 'danger')
        return redirect(url_for('treinamentos_agendamentos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_treinamento_agendamento: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir o agendamento pois existem participantes associados a ele. Remova-os primeiro.", 'danger')
        return redirect(url_for('treinamentos_agendamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_treinamento_agendamento: {e}")
        return redirect(url_for('treinamentos_agendamentos_module'))

# ·······························································
# 4.3.7.4 TREINAMENTOS AGENDAMENTOS CRUD DETALHES - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/agendamentos/details/<int:agendamento_id>')
@login_required
def treinamento_agendamento_details(agendamento_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Agendamentos de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            agendamento = seguranca_manager.get_treinamento_agendamento_by_id(agendamento_id)
            participantes = seguranca_manager.get_all_treinamentos_participantes(search_agendamento_id=agendamento_id)

            if not agendamento:
                flash('Agendamento não encontrado.', 'danger')
                return redirect(url_for('treinamentos_agendamentos_module'))

        return render_template(
            'seguranca/treinamentos/agendamentos/agendamento_details.html',
            user=current_user,
            agendamento=agendamento,
            participantes=participantes
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em treinamento_agendamento_details: {e}")
        return redirect(url_for('treinamentos_agendamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em treinamento_agendamento_details: {e}")
        return redirect(url_for('treinamentos_agendamentos_module'))

# ·······························································
# 4.3.7.5 TREINAMENTOS AGENDAMENTOS EXPORTAR P/ EXCEL - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/agendamentos/export/excel')
@login_required
def export_treinamentos_agendamentos_excel():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Agendamentos de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            search_treinamento_id = request.args.get('treinamento_id')
            search_status = request.args.get('status_agendamento')
            search_data_inicio_str = request.args.get('data_inicio')
            search_data_fim_str = request.args.get('data_fim')

            data_inicio = None
            data_fim = None
            try:
                if search_data_inicio_str:
                    data_inicio = datetime.strptime(search_data_inicio_str, '%Y-%m-%d').date()
                if search_data_fim_str:
                    data_fim = datetime.strptime(search_data_fim_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de data inválido nos filtros de exportação. Use AAAA-MM-DD.', 'danger')
                return redirect(url_for('treinamentos_agendamentos_module'))

            agendamentos_data = seguranca_manager.get_all_treinamentos_agendamentos(
                search_treinamento_id=int(search_treinamento_id) if search_treinamento_id else None,
                search_status=search_status,
                search_data_inicio=data_inicio,
                search_data_fim=data_fim
            )

            if not agendamentos_data:
                flash('Nenhum agendamento de treinamento encontrado para exportar.', 'info')
                return redirect(url_for('treinamentos_agendamentos_module'))

            df = pd.DataFrame(agendamentos_data)

            df = df.rename(columns={
                'ID_Agendamento': 'ID Agendamento',
                'ID_Treinamento': 'ID Treinamento',
                'Nome_Treinamento': 'Nome do Treinamento',
                'Tipo_Treinamento': 'Tipo de Treinamento',
                'Data_Hora_Inicio': 'Início',
                'Data_Hora_Fim': 'Fim',
                'Local_Treinamento': 'Local',
                'Status_Agendamento': 'Status',
                'Observacoes': 'Observações',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_agendamentos_treinamentos.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Agendamentos para Excel: {e}", 'danger')
        print(f"Erro ao exportar Agendamentos Excel: {e}")
        return redirect(url_for('treinamentos_agendamentos_module'))

# ---------------------------------------------------------------
# 4.3.8 ROTAS TREINAMENTOS PARTICIPANTES - SEGURANCA
# ---------------------------------------------------------------
@app.route('/seguranca/treinamentos/participantes')
@login_required
def treinamentos_participantes_module():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Participantes de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    search_agendamento_id = request.args.get('agendamento_id')
    search_matricula = request.args.get('matricula')
    search_presenca = request.args.get('presenca') # String 'True', 'False' ou None

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            # Converte search_presenca para booleano/None
            presenca_filter = None
            if search_presenca == 'True':
                presenca_filter = True
            elif search_presenca == 'False':
                presenca_filter = False

            participantes = seguranca_manager.get_all_treinamentos_participantes(
                search_agendamento_id=int(search_agendamento_id) if search_agendamento_id else None,
                search_matricula=search_matricula,
                search_presenca=presenca_filter
            )
            
            all_agendamentos = seguranca_manager.get_all_agendamentos_for_dropdown()
            all_funcionarios = seguranca_manager.get_all_funcionarios_for_dropdown() # PessoalManager.get_all_funcionarios()
            
            presenca_options = [('True', 'Presente'), ('False', 'Ausente')] # Para o filtro

        return render_template(
            'seguranca/treinamentos/participantes/participantes_module.html',
            user=current_user,
            participantes=participantes,
            all_agendamentos=all_agendamentos,
            all_funcionarios=all_funcionarios,
            presenca_options=presenca_options,
            selected_agendamento_id=int(search_agendamento_id) if search_agendamento_id else None,
            selected_matricula=search_matricula,
            selected_presenca=search_presenca
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Participantes: {e}", 'danger')
        print(f"Erro de banco de dados em treinamentos_participantes_module: {e}")
        return redirect(url_for('seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Participantes: {e}", 'danger')
        print(f"Erro inesperado em treinamentos_participantes_module: {e}")
        return redirect(url_for('seguranca_module'))

# ·······························································
# 4.3.8.1 TREINAMENTOS AGENDAMENTOS CRUD CRIAR - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/participantes/add', methods=['GET', 'POST'])
@login_required
def add_treinamento_participante():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para adicionar Participantes de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            all_agendamentos = seguranca_manager.get_all_agendamentos_for_dropdown()
            all_funcionarios = seguranca_manager.get_all_funcionarios_for_dropdown()
            
            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                id_agendamento = int(form_data_received.get('id_agendamento'))
                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                presenca = 'presenca' in request.form
                nota_avaliacao = float(form_data_received.get('nota_avaliacao', '0').replace(',', '.')) if form_data_received.get('nota_avaliacao', '').strip() else None
                data_conclusao_str = form_data_received.get('data_conclusao', '').strip()
                certificado_emitido = 'certificado_emitido' in request.form

                data_conclusao = None
                is_valid = True

                if not all([id_agendamento, matricula_funcionario]):
                    flash('Campos obrigatórios (Agendamento, Funcionário) não podem ser vazios.', 'danger')
                    is_valid = False
                
                if data_conclusao_str:
                    try:
                        data_conclusao = datetime.strptime(data_conclusao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Conclusão inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                if nota_avaliacao is not None and not (0 <= nota_avaliacao <= 10):
                    flash('Nota de Avaliação deve ser entre 0 e 10.', 'danger')
                    is_valid = False

                # Verificar unicidade (ID_Agendamento, Matricula_Funcionario)
                if seguranca_manager.get_participante_by_agendamento_funcionario(id_agendamento, matricula_funcionario):
                    flash('Este funcionário já está registrado para este agendamento.', 'danger')
                    is_valid = False

                form_data_to_template = form_data_received
                form_data_to_template['data_conclusao'] = data_conclusao_str
                form_data_to_template['presenca'] = presenca
                form_data_to_template['certificado_emitido'] = certificado_emitido

                if is_valid:
                    success = seguranca_manager.add_treinamento_participante(
                        id_agendamento, matricula_funcionario, presenca, nota_avaliacao,
                        data_conclusao, certificado_emitido
                    )
                    if success:
                        flash('Participante adicionado com sucesso!', 'success')
                        return redirect(url_for('treinamentos_participantes_module'))
                    else:
                        flash('Erro ao adicionar participante. Verifique os dados e tente novamente.', 'danger')
            
            return render_template(
                'seguranca/treinamentos/participantes/add_participante.html',
                user=current_user,
                all_agendamentos=all_agendamentos,
                all_funcionarios=all_funcionarios,
                form_data=form_data_to_template
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_treinamento_participante: {e}")
        return redirect(url_for('treinamentos_participantes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_treinamento_participante: {e}")
        return redirect(url_for('treinamentos_participantes_module'))

# ·······························································
# 4.3.8.2 TREINAMENTOS AGENDAMENTOS CRUD EDITAR - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/participantes/edit/<int:participante_id>', methods=['GET', 'POST'])
@login_required
def edit_treinamento_participante(participante_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para editar Participantes de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            participante_from_db = seguranca_manager.get_treinamento_participante_by_id(participante_id)
            if not participante_from_db:
                flash('Participante não encontrado.', 'danger')
                return redirect(url_for('treinamentos_participantes_module'))

            all_agendamentos = seguranca_manager.get_all_agendamentos_for_dropdown()
            all_funcionarios = seguranca_manager.get_all_funcionarios_for_dropdown()
            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                id_agendamento = int(form_data_received.get('id_agendamento'))
                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                presenca = 'presenca' in request.form
                nota_avaliacao = float(form_data_received.get('nota_avaliacao', '0').replace(',', '.')) if form_data_received.get('nota_avaliacao', '').strip() else None
                data_conclusao_str = form_data_received.get('data_conclusao', '').strip()
                certificado_emitido = 'certificado_emitido' in request.form

                data_conclusao = None
                is_valid = True

                if not all([id_agendamento, matricula_funcionario]):
                    flash('Campos obrigatórios (Agendamento, Funcionário) não podem ser vazios.', 'danger')
                    is_valid = False
                
                if data_conclusao_str:
                    try:
                        data_conclusao = datetime.strptime(data_conclusao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Conclusão inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                if nota_avaliacao is not None and not (0 <= nota_avaliacao <= 10):
                    flash('Nota de Avaliação deve ser entre 0 e 10.', 'danger')
                    is_valid = False

                # Verificar unicidade (ID_Agendamento, Matricula_Funcionario)
                existing_participante = seguranca_manager.get_participante_by_agendamento_funcionario(id_agendamento, matricula_funcionario, exclude_id=participante_id)
                if existing_participante:
                    flash('Este funcionário já está registrado para este agendamento.', 'danger')
                    is_valid = False

                form_data_to_template = form_data_received
                form_data_to_template['data_conclusao'] = data_conclusao_str
                form_data_to_template['presenca'] = presenca
                form_data_to_template['certificado_emitido'] = certificado_emitido

                if is_valid:
                    success = seguranca_manager.update_treinamento_participante(
                        participante_id, id_agendamento, matricula_funcionario, presenca, nota_avaliacao,
                        data_conclusao, certificado_emitido
                    )
                    if success:
                        flash('Participante atualizado com sucesso!', 'success')
                        return redirect(url_for('treinamentos_participantes_module'))
                    else:
                        flash('Erro ao atualizar participante. Verifique os dados e tente novamente.', 'danger')
            
            else: # GET request
                form_data_to_template = participante_from_db.copy()
                form_data_to_template['Data_Conclusao'] = form_data_to_template['Data_Conclusao'].strftime('%Y-%m-%d') if form_data_to_template['Data_Conclusao'] else ''
                form_data_to_template['Presenca'] = bool(form_data_to_template.get('Presenca'))
                form_data_to_template['Certificado_Emitido'] = bool(form_data_to_template.get('Certificado_Emitido'))
                
            return render_template(
                'seguranca/treinamentos/participantes/edit_participante.html',
                user=current_user,
                participante=form_data_to_template,
                all_agendamentos=all_agendamentos,
                all_funcionarios=all_funcionarios
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_treinamento_participante: {e}")
        return redirect(url_for('treinamentos_participantes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_treinamento_participante: {e}")
        return redirect(url_for('treinamentos_participantes_module'))

# ·······························································
# 4.3.8.3 TREINAMENTOS AGENDAMENTOS CRUD DELETAR - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/participantes/delete/<int:participante_id>', methods=['POST'])
@login_required
def delete_treinamento_participante(participante_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para excluir Participantes de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_treinamento_participante(participante_id)
            if success:
                flash('Participante excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir participante. Verifique se ele existe.', 'danger')
        return redirect(url_for('treinamentos_participantes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_treinamento_participante: {e}")
        return redirect(url_for('treinamentos_participantes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_treinamento_participante: {e}")
        return redirect(url_for('treinamentos_participantes_module'))

# ·······························································
# 4.3.8.4 TREINAMENTOS AGENDAMENTOS CRUD DETALHES - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/participantes/details/<int:participante_id>')
@login_required
def treinamento_participante_details(participante_id):
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Participantes de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            participante = seguranca_manager.get_treinamento_participante_by_id(participante_id)

            if not participante:
                flash('Participante não encontrado.', 'danger')
                return redirect(url_for('treinamentos_participantes_module'))

        return render_template(
            'seguranca/treinamentos/participantes/participante_details.html',
            user=current_user,
            participante=participante
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em treinamento_participante_details: {e}")
        return redirect(url_for('treinamentos_participantes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em treinamento_participante_details: {e}")
        return redirect(url_for('treinamentos_participantes_module'))

# ·······························································
# 4.3.8.5 TREINAMENTOS AGENDAMENTOS EXPORTAR P/ EXCEL - SEGURANCA
# ·······························································
@app.route('/seguranca/treinamentos/participantes/export/excel')
@login_required
def export_treinamentos_participantes_excel():
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Participantes de Treinamentos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            search_agendamento_id = request.args.get('agendamento_id')
            search_matricula = request.args.get('matricula')
            search_presenca = request.args.get('presenca')

            presenca_filter = None
            if search_presenca == 'True':
                presenca_filter = True
            elif search_presenca == 'False':
                presenca_filter = False

            participantes_data = seguranca_manager.get_all_treinamentos_participantes(
                search_agendamento_id=int(search_agendamento_id) if search_agendamento_id else None,
                search_matricula=search_matricula,
                search_presenca=presenca_filter
            )

            if not participantes_data:
                flash('Nenhum participante encontrado para exportar.', 'info')
                return redirect(url_for('treinamentos_participantes_module'))

            df = pd.DataFrame(participantes_data)

            df = df.rename(columns={
                'ID_Participante': 'ID Participante',
                'ID_Agendamento': 'ID Agendamento',
                'Matricula_Funcionario': 'Matrícula Funcionário',
                'Nome_Funcionario': 'Nome do Funcionário',
                'Presenca': 'Presença',
                'Nota_Avaliacao': 'Nota de Avaliação',
                'Data_Conclusao': 'Data de Conclusão',
                'Certificado_Emitido': 'Certificado Emitido',
                'Nome_Treinamento': 'Nome do Treinamento',
                'Data_Hora_Inicio': 'Data/Hora Agendamento',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            df['Presença'] = df['Presenca'].apply(lambda x: 'Sim' if x else 'Não')
            df['Certificado Emitido'] = df['Certificado Emitido'].apply(lambda x: 'Sim' if x else 'Não')

            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_participantes_treinamentos.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Participantes para Excel: {e}", 'danger')
        print(f"Erro ao exportar Participantes Excel: {e}")
        return redirect(url_for('treinamentos_participantes_module'))

# ===============================================================
# 4.4 ROTAS PARA DASHBOARD - SEGURANCA
# ===============================================================
@app.route('/seguranca/dashboard')
@login_required
def seguranca_dashboard():
    """
    Rota para o Dashboard de Segurança, exibindo KPIs e resumos.
    """
    if not current_user.can_access_module('Segurança'):
        flash('Acesso negado. Você não tem permissão para acessar o Dashboard de Segurança.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            
            # --- CORRIGIDO AQUI: GARANTIR NOMES E FORMATOS CONSISTENTES ---
            total_incidentes_acidentes = seguranca_manager.get_total_incidentes_acidentes()

            type_counts_list = seguranca_manager.get_incidentes_acidentes_counts_by_type()
            # Converte a lista de dicionários para um único dicionário para fácil acesso no template
            type_counts_dict = {item['Tipo_Registro']: item['Count'] for item in type_counts_list}

            status_counts_list_from_db = seguranca_manager.get_incidentes_acidentes_counts_by_status()
            # Converte a lista de dicionários para um único dicionário para fácil acesso no template para KPIs específicos
            status_counts_dict = {item['Status_Registro']: item['Count'] for item in status_counts_list_from_db}

            monthly_counts = seguranca_manager.get_incidentes_acidentes_counts_by_month_year()

            return render_template(
                'seguranca/seguranca_dashboard.html',
                user=current_user,
                total_incidentes_acidentes=total_incidentes_acidentes, # Valor total
                type_counts=type_counts_list,       # Lista para iteração por tipo
                status_counts=status_counts_dict,   # Dicionário para KPIs abertos/concluídos (ex: .get('Aberto'))
                status_counts_list=status_counts_list_from_db, # Lista para iteração por status geral
                monthly_counts=monthly_counts       # Lista para iteração mensal
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar dashboard de segurança: {e}", 'danger')
        print(f"Erro de banco de dados em seguranca_dashboard: {e}")
        return redirect(url_for('seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar dashboard de segurança: {e}", 'danger')
        print(f"Erro inesperado em seguranca_dashboard: {e}")
        return redirect(url_for('seguranca_module'))

#################################################################
# 99. REGISTRO DOS BLUEPRINTS (NOVO)
#################################################################
app.register_blueprint(users_bp) # Registra o Blueprint do Módulo Usuários
app.register_blueprint(pessoal_bp)
app.register_blueprint(obras_bp) # Registra o Blueprint do Módulo Obras

if __name__ == '__main__':
    app.run(debug=True)