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
from database.db_hr_manager import HrManager # Para o módulo de RH/DP (mantido para estrutura) <<< ver se ainda precisa! Pode apagar!!!
from database.db_obras_manager import ObrasManager # Para o módulo Obras
from database.db_seguranca_manager import SegurancaManager # Para o módulo Segurança
from database.db_pessoal_manager import PessoalManager

# Imaportações para Blueprint
from modulos.users_bp import users_bp # NOVO: Importa o Blueprint de Usuários
from modulos.pessoal_bp import pessoal_bp


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
# 3. MÓDULO OBRAS
#################################################################

@app.route('/obras')
@login_required
def obras_module():
    """
    Rota principal do módulo Obras.
    Serve como hub de navegação para os submódulos.
    """
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para acessar o Módulo Obras.', 'warning')
        return redirect(url_for('welcome'))
    
    return render_template('obras/obras_welcome.html', user=current_user)

# ===============================================================
# 3.1 ROTAS DE OBRAS
# ===============================================================
@app.route('/obras/add', methods=['GET', 'POST'])
@login_required
def add_obra():
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para adicionar obras.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                id_contratos = int(request.form['id_contratos'])
                numero_obra = request.form['numero_obra'].strip()
                nome_obra = request.form['nome_obra'].strip()
                endereco_obra = request.form['endereco_obra'].strip()
                escopo_obra = request.form['escopo_obra'].strip()
                valor_obra = float(request.form['valor_obra'].replace(',', '.')) 
                valor_aditivo_total = float(request.form.get('valor_aditivo_total', '0').replace(',', '.'))
                status_obra = request.form['status_obra'].strip()
                data_inicio_prevista_str = request.form['data_inicio_prevista'].strip()
                data_fim_prevista_str = request.form['data_fim_prevista'].strip()

                if not all([id_contratos, numero_obra, nome_obra, status_obra, data_inicio_prevista_str, data_fim_prevista_str]):
                    flash('Campos obrigatórios (Contrato, Número, Nome, Status, Datas de Início/Fim) não podem ser vazios.', 'danger')
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/add_obra.html',
                        user=current_user,
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form 
                    )

                try:
                    data_inicio_prevista = datetime.strptime(data_inicio_prevista_str, '%Y-%m-%d').date()
                    data_fim_prevista = datetime.strptime(data_fim_prevista_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/add_obra.html',
                        user=current_user,
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                if obras_manager.get_obra_by_numero(numero_obra):
                    flash('Número da obra já existe. Por favor, use um número único.', 'danger')
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/add_obra.html',
                        user=current_user,
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.add_obra(
                    id_contratos, numero_obra, nome_obra, endereco_obra, escopo_obra, valor_obra, valor_aditivo_total, status_obra, data_inicio_prevista, data_fim_prevista
                )
                if success:
                    flash('Obra adicionada com sucesso!', 'success')
                    return redirect(url_for('gerenciar_obras_lista'))
                else:
                    flash('Erro ao adicionar obra. Verifique os dados.', 'danger')
            
            # GET request: Carregar dados para o formulário
            all_contratos = obras_manager.get_all_contratos_for_dropdown()
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada'] 
                
            return render_template(
                'obras/add_obra.html',
                user=current_user,
                all_contratos=all_contratos,
                status_options=status_options,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_obra: {e}")
        return redirect(url_for('gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_obra: {e}")
        return redirect(url_for('gerenciar_obras_lista'))

# ---------------------------------------------------------------
# 3.1.2 ROTAS DO CRUD - EDITAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/edit/<int:obra_id>', methods=['GET', 'POST'])
@login_required
def edit_obra(obra_id):
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para editar obras.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            obra = obras_manager.get_obra_by_id(obra_id)

            if not obra:
                flash('Obra não encontrada.', 'danger')
                return redirect(url_for('gerenciar_obras_lista'))

            if request.method == 'POST':
                id_contratos = int(request.form['id_contratos'])
                numero_obra = request.form['numero_obra'].strip()
                nome_obra = request.form['nome_obra'].strip()
                endereco_obra = request.form['endereco_obra'].strip()
                escopo_obra = request.form['escopo_obra'].strip()
                valor_obra = float(request.form['valor_obra'].replace(',', '.'))
                valor_aditivo_total = float(request.form.get('valor_aditivo_total', '0').replace(',', '.'))
                status_obra = request.form['status_obra'].strip()
                data_inicio_prevista_str = request.form['data_inicio_prevista'].strip()
                data_fim_prevista_str = request.form['data_fim_prevista'].strip()

                if not all([id_contratos, numero_obra, nome_obra, status_obra, data_inicio_prevista_str, data_fim_prevista_str]):
                    flash('Campos obrigatórios (Contrato, Número, Nome, Status, Datas de Início/Fim) não podem ser vazios.', 'danger')
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/edit_obra.html',
                        user=current_user,
                        obra=obra, 
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form 
                    )

                try:
                    data_inicio_prevista = datetime.strptime(data_inicio_prevista_str, '%Y-%m-%d').date()
                    data_fim_prevista = datetime.strptime(data_fim_prevista_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/edit_obra.html',
                        user=current_user,
                        obra=obra, 
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                existing_obra = obras_manager.get_obra_by_numero(numero_obra)
                if existing_obra and existing_obra['ID_Obras'] != obra_id:
                    flash('Número da obra já existe. Por favor, use um número único.', 'danger')
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/edit_obra.html',
                        user=current_user,
                        obra=obra, 
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.update_obra(
                    obra_id, id_contratos, numero_obra, nome_obra, endereco_obra, escopo_obra, valor_obra, valor_aditivo_total, status_obra, data_inicio_prevista, data_fim_prevista
                )
                if success:
                    flash('Obra atualizada com sucesso!', 'success')
                    return redirect(url_for('gerenciar_obras_lista'))
                else:
                    flash('Erro ao atualizar obra.', 'danger')
            
            else: # GET request
                all_contratos = obras_manager.get_all_contratos_for_dropdown()
                status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                
                obra['Data_Inicio_Prevista'] = obra['Data_Inicio_Prevista'].strftime('%Y-%m-%d') if obra['Data_Inicio_Prevista'] else ''
                obra['Data_Fim_Prevista'] = obra['Data_Fim_Prevista'].strftime('%Y-%m-%d') if obra['Data_Fim_Prevista'] else ''

                return render_template(
                    'obras/edit_obra.html',
                    user=current_user,
                    obra=obra,
                    all_contratos=all_contratos,
                    status_options=status_options
                )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_obra: {e}")
        return redirect(url_for('gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_obra: {e}")
        return redirect(url_for('gerenciar_obras_lista'))

# ---------------------------------------------------------------
# 3.1.3 ROTAS DO CRUD - DELETAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/delete/<int:obra_id>', methods=['POST'])
@login_required
def delete_obra(obra_id):
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para excluir obras.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_obra(obra_id)
            if success:
                flash('Obra excluída com sucesso!', 'success')
            else:
                flash('Erro ao excluir obra. Verifique se ela existe e não possui dependências (ARTs, Medições, etc.).', 'danger')
        return redirect(url_for('gerenciar_obras_lista'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_obra: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir a obra pois existem registros relacionados (ARTs, Medições, etc.). Remova-os primeiro.", 'danger')
        return redirect(url_for('gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_obra: {e}")
        return redirect(url_for('gerenciar_obras_lista'))
    
# ---------------------------------------------------------------
# 3.1.4 ROTAS DO CRUD - DETALHES - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/details/<int:obra_id>')
@login_required
def obra_details(obra_id):
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de obras.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            obra = obras_manager.get_obra_by_id(obra_id)

            if not obra:
                flash('Obra não encontrada.', 'danger')
                return redirect(url_for('gerenciar_obras_lista'))

        return render_template(
            'obras/obra_details.html',
            user=current_user,
            obra=obra
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em obra_details: {e}")
        return redirect(url_for('gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em obra_details: {e}")
        return redirect(url_for('gerenciar_obras_lista'))

# ---------------------------------------------------------------
# 3.1.5 ROTA - EXPORTAR P/ EXCEL - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/export/excel')
@login_required
def export_obras_excel():
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para exportar dados de obras.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            search_numero = request.args.get('numero_obra')
            search_nome = request.args.get('nome_obra')
            search_status = request.args.get('status_obra')
            search_cliente_id = request.args.get('cliente_id')

            obras_data = obras_manager.get_all_obras(
                search_numero=search_numero,
                search_nome=search_nome,
                search_status=search_status,
                search_cliente_id=search_cliente_id
            )

            if not obras_data:
                flash('Nenhuma obra encontrada para exportar.', 'info')
                return redirect(url_for('gerenciar_obras_lista'))

            df = pd.DataFrame(obras_data)

            df = df.rename(columns={
                'ID_Obras': 'ID Obra',
                'Numero_Obra': 'Número da Obra',
                'Nome_Obra': 'Nome da Obra',
                'Endereco_Obra': 'Endereço',
                'Escopo_Obra': 'Escopo',
                'Valor_Obra': 'Valor (R$)',
                'Valor_Aditivo_Total': 'Aditivos (R$)',
                'Status_Obra': 'Status',
                'Data_Inicio_Prevista': 'Início Previsto',
                'Data_Fim_Prevista': 'Fim Previsto',
                'Numero_Contrato': 'Número do Contrato',
                'Nome_Cliente': 'Cliente',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            ordered_columns = [
                'ID Obra', 'Número da Obra', 'Nome da Obra', 'Cliente', 'Número do Contrato',
                'Endereço', 'Status', 'Início Previsto', 'Fim Previsto',
                'Valor (R$)', 'Aditivos (R$)', 'Escopo', 'Data de Criação', 'Última Modificação'
            ]
            df = df[[col for col in ordered_columns if col in df.columns]]


            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_obras.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar obras para Excel: {e}", 'danger')
        print(f"Erro ao exportar obras Excel: {e}")
        return redirect(url_for('gerenciar_obras_lista'))

# ---------------------------------------------------------------
# 3.1.6 ROTA DASBOARD - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/dashboard')
@login_required
def obras_dashboard():
    """
    Rota para o Dashboard de Obras, exibindo KPIs e resumos.
    """
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para acessar o Dashboard de Obras.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base) 

            status_counts_list = obras_manager.get_obra_status_counts()
            # Converte a lista de dicionários para um único dicionário para fácil acesso no template
            status_counts = {item['Status_Obra']: item['Count'] for item in status_counts_list}

            total_contratos_ativos = obras_manager.get_total_contratos_ativos_valor()
            total_medicoes_realizadas = obras_manager.get_total_medicoes_realizadas_valor()
            avg_avanco_fisico = obras_manager.get_avg_avanco_fisico_obras_ativas()
            
            # Formatar valores monetários e percentuais para exibição
            total_contratos_ativos_formatado = f"R$ {total_contratos_ativos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_contratos_ativos is not None else "R$ 0,00"
            total_medicoes_realizadas_formatado = f"R$ {total_medicoes_realizadas:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_medicoes_realizadas is not None else "R$ 0,00"
            avg_avanco_fisico_formatado = f"{avg_avanco_fisico:.2f}%" if avg_avanco_fisico is not None else "0.00%"


            return render_template(
                'obras/obras_dashboard.html', # Template para o dashboard
                user=current_user,
                status_counts=status_counts,
                total_contratos_ativos=total_contratos_ativos_formatado,
                total_medicoes_realizadas=total_medicoes_realizadas_formatado,
                avg_avanco_fisico=avg_avanco_fisico_formatado
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar dashboard de obras: {e}", 'danger')
        print(f"Erro de banco de dados em obras_dashboard: {e}")
        return redirect(url_for('obras_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar dashboard de obras: {e}", 'danger')
        print(f"Erro inesperado em obras_dashboard: {e}")
        return redirect(url_for('obras_module'))

# ---------------------------------------------------------------
# 3.1.7 ROTA LISTAGEM/GERENCIAMENTO DE OBRAS ESPECÍFICA - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/gerenciar')
@login_required
def gerenciar_obras_lista():
    """
    Rota para a listagem e filtragem de obras.
    Anteriormente parte da 'obras_module', agora separada para clareza.
    """
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para acessar a gestão de Obras.', 'warning')
        return redirect(url_for('welcome'))

    search_numero = request.args.get('numero_obra')
    search_nome = request.args.get('nome_obra')
    search_status = request.args.get('status_obra')
    search_cliente_id = request.args.get('cliente_id') 

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            obras = obras_manager.get_all_obras(
                search_numero=search_numero,
                search_nome=search_nome,
                search_status=search_status,
                search_cliente_id=search_cliente_id
            )
            
            # Assumindo que get_all_clientes está em ObrasManager e retorna todos os clientes
            clientes = obras_manager.get_all_clientes() 
            
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']

        return render_template(
            'obras/obras_module.html', # Template para a lista de obras
            user=current_user,
            obras=obras,
            clientes=clientes,
            status_options=status_options,
            selected_numero=search_numero,
            selected_nome=search_nome,
            selected_status=search_status,
            selected_cliente_id=int(search_cliente_id) if search_cliente_id else None
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar obras: {e}", 'danger')
        print(f"Erro de banco de dados em gerenciar_obras_lista: {e}")
        return redirect(url_for('obras_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar obras: {e}", 'danger')
        print(f"Erro inesperado em gerenciar_obras_lista: {e}")
        return redirect(url_for('obras_module'))

# ---------------------------------------------------------------
# 3.1.7 ROTA PARA O RELATÓRIO DE ANDAMENTO DE OBRAS - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/relatorio_andamento')
@login_required
def obras_relatorio_andamento():
    """
    Rota para o relatório de andamento de obras, com filtros.
    """
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para acessar o Relatório de Andamento de Obras.', 'warning')
        return redirect(url_for('welcome'))

    # Coletar parâmetros de filtro
    search_numero = request.args.get('numero_obra')
    search_nome = request.args.get('nome_obra')
    search_status = request.args.get('status_obra')
    search_cliente_id = request.args.get('cliente_id')

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            # Chama o novo método para obter os dados do relatório de andamento
            obras_andamento = obras_manager.get_obras_andamento_para_relatorio(
                search_numero=search_numero,
                search_nome=search_nome,
                search_status=search_status,
                search_cliente_id=search_cliente_id
            )
            
            # Obter listas para dropdowns de filtro (se aplicável ao template)
            # Assumimos que get_all_clientes existe e retorna todos os clientes
            all_clientes = obras_manager.get_all_clientes() 
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada'] # Opções de status

            return render_template(
                'obras/obras_relatorio_andamento.html', # Este template ainda não existe, será criado.
                user=current_user,
                obras_andamento=obras_andamento,
                all_clientes=all_clientes,
                status_options=status_options,
                selected_numero=search_numero,
                selected_nome=search_nome,
                selected_status=search_status,
                selected_cliente_id=int(search_cliente_id) if search_cliente_id else None
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar relatório de andamento de obras: {e}", 'danger')
        print(f"Erro de banco de dados em obras_relatorio_andamento: {e}")
        return redirect(url_for('obras_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar relatório de andamento de obras: {e}", 'danger')
        print(f"Erro inesperado em obras_relatorio_andamento: {e}")
        return redirect(url_for('obras_module'))

# ===============================================================
# 3.2 ROTAS DE CLIENTES - OBRAS
# ===============================================================
@app.route('/obras/clientes')
@login_required
def clientes_module(): 
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Clientes.', 'warning')
        return redirect(url_for('welcome'))

    search_nome = request.args.get('nome_cliente')
    search_cnpj = request.args.get('cnpj_cliente')

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base) 
            clientes = obras_manager.get_all_clientes(
                search_nome=search_nome,
                search_cnpj=search_cnpj
            )

        return render_template(
            'obras/clientes/clientes_module.html',
            user=current_user,
            clientes=clientes,
            selected_nome=search_nome,
            selected_cnpj=search_cnpj
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar clientes: {e}", 'danger')
        print(f"Erro de banco de dados em clientes_module: {e}")
        return redirect(url_for('obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar clientes: {e}", 'danger')
        print(f"Erro inesperado em clientes_module: {e}")
        return redirect(url_for('obras_module')) 

# ---------------------------------------------------------------
# 3.2.1 ROTAS DO CRUD DE CLIENTES - CRIAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/clientes/add', methods=['GET', 'POST'])
@login_required
def add_cliente():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para adicionar clientes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                nome_cliente = request.form['nome_cliente'].strip()
                cnpj_cliente = request.form['cnpj_cliente'].strip()
                razao_social_cliente = request.form['razao_social_cliente'].strip()
                endereco_cliente = request.form['endereco_cliente'].strip()
                telefone_cliente = request.form['telefone_cliente'].strip()
                email_cliente = request.form['email_cliente'].strip()
                contato_principal_nome = request.form['contato_principal_nome'].strip()

                if not all([nome_cliente, cnpj_cliente]):
                    flash('Nome e CNPJ do cliente são obrigatórios.', 'danger')
                    return render_template(
                        'obras/clientes/add_cliente.html',
                        user=current_user,
                        form_data=request.form 
                    )
                
                if obras_manager.get_cliente_by_cnpj(cnpj_cliente):
                    flash('CNPJ já existe. Por favor, use um CNPJ único.', 'danger')
                    return render_template(
                        'obras/clientes/add_cliente.html',
                        user=current_user,
                        form_data=request.form
                    )

                success = obras_manager.add_cliente(
                    nome_cliente, cnpj_cliente, razao_social_cliente, endereco_cliente, telefone_cliente, email_cliente, contato_principal_nome
                )
                if success:
                    flash('Cliente adicionado com sucesso!', 'success')
                    return redirect(url_for('clientes_module'))
                else:
                    flash('Erro ao adicionar cliente. Verifique os dados e tente novamente.', 'danger')
            
            return render_template(
                'obras/clientes/add_cliente.html',
                user=current_user,
                form_data={} 
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_cliente: {e}")
        return redirect(url_for('clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_cliente: {e}")
        return redirect(url_for('clientes_module'))

# ---------------------------------------------------------------
# 3.2.2 ROTAS DO CRUD DE CLIENTES - EDITAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/clientes/edit/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def edit_cliente(cliente_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para editar clientes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            cliente = obras_manager.get_cliente_by_id(cliente_id)

            if not cliente:
                flash('Cliente não encontrado.', 'danger')
                return redirect(url_for('clientes_module'))

            if request.method == 'POST':
                nome_cliente = request.form['nome_cliente'].strip()
                cnpj_cliente = request.form['cnpj_cliente'].strip()
                razao_social_cliente = request.form['razao_social_cliente'].strip()
                endereco_cliente = request.form['endereco_cliente'].strip()
                telefone_cliente = request.form['telefone_cliente'].strip()
                email_cliente = request.form['email_cliente'].strip()
                contato_principal_nome = request.form['contato_principal_nome'].strip()

                if not all([nome_cliente, cnpj_cliente]):
                    flash('Nome e CNPJ do cliente são obrigatórios.', 'danger')
                    return render_template(
                        'obras/clientes/edit_cliente.html',
                        user=current_user,
                        cliente=cliente, 
                        form_data=request.form 
                    )
                
                existing_cliente = obras_manager.get_cliente_by_cnpj(cnpj_cliente)
                if existing_cliente and existing_cliente['ID_Clientes'] != cliente_id:
                    flash('CNPJ já existe. Por favor, use um CNPJ único.', 'danger')
                    return render_template(
                        'obras/clientes/edit_cliente.html',
                        user=current_user,
                        cliente=cliente, 
                        form_data=request.form
                    )

                success = obras_manager.update_cliente(
                    cliente_id, nome_cliente, cnpj_cliente, razao_social_cliente, endereco_cliente, telefone_cliente, email_cliente, contato_principal_nome
                )
                if success:
                    flash('Cliente atualizado com sucesso!', 'success')
                    return redirect(url_for('clientes_module'))
                else:
                    flash('Erro ao atualizar cliente.', 'danger')
            
            return render_template(
                'obras/clientes/edit_cliente.html',
                user=current_user,
                cliente=cliente
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_cliente: {e}")
        return redirect(url_for('clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_cliente: {e}")
        return redirect(url_for('clientes_module'))

# ---------------------------------------------------------------
# 3.2.3 ROTAS DO CRUD DE CLIENTES - DELETAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/clientes/delete/<int:cliente_id>', methods=['POST'])
@login_required
def delete_cliente(cliente_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para excluir clientes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_cliente(cliente_id)
            if success:
                flash('Cliente excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir cliente. Verifique se ele existe e não possui contratos associados.', 'danger')
        return redirect(url_for('clientes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_cliente: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir o cliente pois existem contratos ou obras associados a ele. Remova-os primeiro.", 'danger')
        return redirect(url_for('clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_cliente: {e}")
        return redirect(url_for('clientes_module'))

# ---------------------------------------------------------------
# 3.2.4 ROTAS DO CRUD DE CLIENTES - DETALHES - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/clientes/details/<int:cliente_id>')
@login_required
def cliente_details(cliente_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para ver detalhes de clientes.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            cliente = obras_manager.get_cliente_by_id(cliente_id)

            if not cliente:
                flash('Cliente não encontrado.', 'danger')
                return redirect(url_for('clientes_module'))

        return render_template(
            'obras/clientes/cliente_details.html',
            user=current_user,
            cliente=cliente
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em cliente_details: {e}")
        return redirect(url_for('clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em cliente_details: {e}")
        return redirect(url_for('clientes_module'))

# ---------------------------------------------------------------
# 3.2.5 ROTA DE CLIENTES - EXPORTAR P/ EXCEL - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/clientes/export/excel')
@login_required
def export_clientes_excel():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para exportar dados de clientes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            search_nome = request.args.get('nome_cliente')
            search_cnpj = request.args.get('cnpj_cliente')

            clientes_data = obras_manager.get_all_clientes(
                search_nome=search_nome,
                search_cnpj=search_cnpj
            )

            if not clientes_data:
                flash('Nenhum cliente encontrado para exportar.', 'info')
                return redirect(url_for('clientes_module'))

            df = pd.DataFrame(clientes_data)

            df = df.rename(columns={
                'ID_Clientes': 'ID Cliente',
                'Nome_Cliente': 'Nome do Cliente',
                'CNPJ_Cliente': 'CNPJ',
                'Razao_Social_Cliente': 'Razão Social',
                'Endereco_Cliente': 'Endereço',
                'Telefone_Cliente': 'Telefone',
                'Email_Cliente': 'Email',
                'Contato_Principal_Nome': 'Contato Principal',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            ordered_columns = [
                'ID Cliente', 'Nome do Cliente', 'CNPJ', 'Razão Social', 'Endereço',
                'Telefone', 'Email', 'Contato Principal', 'Data de Criação', 'Última Modificação'
            ]
            df = df[[col for col in ordered_columns if col in df.columns]]

            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_clientes.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar clientes para Excel: {e}", 'danger')
        print(f"Erro ao exportar clientes Excel: {e}")
        return redirect(url_for('clientes_module'))


# ===============================================================
# 3.3 ROTAS DE CONTRATOS - OBRAS
# ===============================================================
@app.route('/obras/contratos')
@login_required
def contratos_module(): 
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Contratos.', 'warning')
        return redirect(url_for('welcome'))

    search_numero = request.args.get('numero_contrato')
    search_cliente_id = request.args.get('cliente_id')
    search_status = request.args.get('status_contrato')

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            contratos = obras_manager.get_all_contratos(
                search_numero=search_numero,
                search_cliente_id=search_cliente_id,
                search_status=search_status
            )
            
            clientes = obras_manager.get_all_clientes() 
            
            status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']

        return render_template(
            'obras/contratos/contratos_module.html',
            user=current_user,
            contratos=contratos,
            clientes=clientes,
            status_options=status_options,
            selected_numero=search_numero,
            selected_cliente_id=int(search_cliente_id) if search_cliente_id else None,
            selected_status=search_status
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar contratos: {e}", 'danger')
        print(f"Erro de banco de dados em contratos_module: {e}")
        return redirect(url_for('obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar contratos: {e}", 'danger')
        print(f"Erro inesperado em contratos_module: {e}")
        return redirect(url_for('obras_module')) 

# ---------------------------------------------------------------
# 3.3.1 ROTAS DO CRUD DE CONTRATOS - CRIAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/contratos/add', methods=['GET', 'POST'])
@login_required
def add_contrato():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para adicionar contratos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                id_clientes = int(request.form['id_clientes'])
                numero_contrato = request.form['numero_contrato'].strip()
                valor_contrato = float(request.form['valor_contrato'].replace(',', '.'))
                data_assinatura_str = request.form['data_assinatura'].strip()
                data_ordem_inicio_str = request.form.get('data_ordem_inicio', '').strip()
                prazo_contrato_dias = int(request.form.get('prazo_contrato_dias', 0))
                data_termino_previsto_str = request.form.get('data_termino_previsto', '').strip()
                status_contrato = request.form['status_contrato'].strip()
                observacoes = request.form.get('observacoes', '').strip()

                if not all([id_clientes, numero_contrato, valor_contrato, data_assinatura_str, status_contrato]):
                    flash('Campos obrigatórios (Cliente, Número, Valor, Data Assinatura, Status) não podem ser vazios.', 'danger')
                    all_clientes = obras_manager.get_all_clientes() 
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/add_contrato.html',
                        user=current_user,
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                try:
                    data_assinatura = datetime.strptime(data_assinatura_str, '%Y-%m-%d').date()
                    data_ordem_inicio = datetime.strptime(data_ordem_inicio_str, '%Y-%m-%d').date() if data_ordem_inicio_str else None
                    data_termino_previsto = datetime.strptime(data_termino_previsto_str, '%Y-%m-%d').date() if data_termino_previsto_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_clientes = obras_manager.get_all_clientes() 
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/add_contrato.html',
                        user=current_user,
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                if obras_manager.get_contrato_by_numero(numero_contrato):
                    flash('Número do contrato já existe. Por favor, use um número único.', 'danger')
                    all_clientes = obras_manager.get_all_clientes() 
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/add_contrato.html',
                        user=current_user,
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.add_contrato(
                    id_clientes, numero_contrato, valor_contrato, data_assinatura, data_ordem_inicio, prazo_contrato_dias, data_termino_previsto, status_contrato, observacoes
                )
                if success:
                    flash('Contrato adicionado com sucesso!', 'success')
                    return redirect(url_for('contratos_module'))
                else:
                    flash('Erro ao adicionar contrato. Verifique os dados e tente novamente.', 'danger')
            
            all_clientes = obras_manager.get_all_clientes() 
            status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                
            return render_template(
                'obras/contratos/add_contrato.html',
                user=current_user,
                all_clientes=all_clientes,
                status_options=status_options,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_contrato: {e}")
        return redirect(url_for('contratos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_contrato: {e}")
        return redirect(url_for('contratos_module'))

# ---------------------------------------------------------------
# 3.3.2 ROTAS DO CRUD DE CONTRATOS - EDITAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/contratos/edit/<int:contrato_id>', methods=['GET', 'POST'])
@login_required
def edit_contrato(contrato_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para editar contratos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            contrato = obras_manager.get_contrato_by_id(contrato_id)

            if not contrato:
                flash('Contrato não encontrado.', 'danger')
                return redirect(url_for('contratos_module'))

            if request.method == 'POST':
                id_clientes = int(request.form['id_clientes'])
                numero_contrato = request.form['numero_contrato'].strip()
                valor_contrato = float(request.form['valor_contrato'].replace(',', '.'))
                data_assinatura_str = request.form['data_assinatura'].strip()
                data_ordem_inicio_str = request.form.get('data_ordem_inicio', '').strip()
                prazo_contrato_dias = int(request.form.get('prazo_contrato_dias', 0))
                data_termino_previsto_str = request.form.get('data_termino_previsto', '').strip()
                status_contrato = request.form['status_contrato'].strip()
                observacoes = request.form.get('observacoes', '').strip()

                if not all([id_clientes, numero_contrato, valor_contrato, data_assinatura_str, status_contrato]):
                    flash('Campos obrigatórios (Cliente, Número, Valor, Data Assinatura, Status) não podem ser vazios.', 'danger')
                    all_clientes = obras_manager.get_all_clientes() 
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/edit_contrato.html',
                        user=current_user,
                        contrato=contrato, 
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                try:
                    data_assinatura = datetime.strptime(data_assinatura_str, '%Y-%m-%d').date()
                    data_ordem_inicio = datetime.strptime(data_ordem_inicio_str, '%Y-%m-%d').date() if data_ordem_inicio_str else None
                    data_termino_previsto = datetime.strptime(data_termino_previsto_str, '%Y-%m-%d').date() if data_termino_previsto_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_clientes = obras_manager.get_all_clientes() 
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/edit_contrato.html',
                        user=current_user,
                        contrato=contrato, 
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )

                existing_contrato = obras_manager.get_contrato_by_numero(numero_contrato)
                if existing_contrato and existing_contrato['ID_Contratos'] != contrato_id:
                    flash('Número do contrato já existe. Por favor, use um número único.', 'danger')
                    all_clientes = obras_manager.get_all_clientes() 
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/edit_contrato.html',
                        user=current_user,
                        contrato=contrato, 
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.update_contrato(
                    contrato_id, id_clientes, numero_contrato, valor_contrato, data_assinatura, data_ordem_inicio, prazo_contrato_dias, data_termino_previsto, status_contrato, observacoes
                )
                if success:
                    flash('Contrato atualizado com sucesso!', 'success')
                    return redirect(url_for('contratos_module'))
                else:
                    flash('Erro ao atualizar contrato.', 'danger')
            
            else: # GET request
                all_clientes = obras_manager.get_all_clientes() 
                status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                
                contrato['Data_Assinatura'] = contrato['Data_Assinatura'].strftime('%Y-%m-%d') if contrato['Data_Assinatura'] else ''
                contrato['Data_Ordem_Inicio'] = contrato['Data_Ordem_Inicio'].strftime('%Y-%m-%d') if contrato['Data_Ordem_Inicio'] else ''
                contrato['Data_Termino_Previsto'] = contrato['Data_Termino_Previsto'].strftime('%Y-%m-%d') if contrato['Data_Termino_Previsto'] else ''

            return render_template(
                'obras/contratos/edit_contrato.html',
                user=current_user,
                contrato=contrato,
                all_clientes=all_clientes,
                status_options=status_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_contrato: {e}")
        return redirect(url_for('contratos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_contrato: {e}")
        return redirect(url_for('contratos_module'))

# ---------------------------------------------------------------
# 3.3.3 ROTAS DO CRUD DE CONTRATOS - DELETAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/contratos/delete/<int:contrato_id>', methods=['POST'])
@login_required
def delete_contrato(contrato_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para excluir contratos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_contrato(contrato_id)
            if success:
                flash('Contrato excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir contrato. Verifique se ele existe e não possui obras ou outros registros associados.', 'danger')
        return redirect(url_for('contratos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_contrato: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir o contrato pois existem obras ou outros registros associados a ele. Remova-os primeiro.", 'danger')
        return redirect(url_for('contratos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_contrato: {e}")
        return redirect(url_for('contratos_module'))

# ---------------------------------------------------------------
# 3.3.4 ROTAS DO CRUD DE CONTRATOS - DETALHES - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/contratos/details/<int:contrato_id>')
@login_required
def contrato_details(contrato_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para ver detalhes de contratos.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            contrato = obras_manager.get_contrato_by_id(contrato_id)

            if not contrato:
                flash('Contrato não encontrado.', 'danger')
                return redirect(url_for('contratos_module'))

        return render_template(
            'obras/contratos/contrato_details.html',
            user=current_user,
            contrato=contrato
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em contrato_details: {e}")
        return redirect(url_for('contratos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em contrato_details: {e}")
        return redirect(url_for('contratos_module'))

# ---------------------------------------------------------------
# 3.3.5 ROTA DE CONTRATOS - EXPORTAR P/ EXCEL - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/contratos/export/excel')
@login_required
def export_contratos_excel():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para exportar dados de contratos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            search_numero = request.args.get('numero_contrato')
            search_cliente_id = request.args.get('cliente_id')
            search_status = request.args.get('status_contrato')

            contratos_data = obras_manager.get_all_contratos(
                search_numero=search_numero,
                search_cliente_id=search_cliente_id,
                search_status=search_status
            )

            if not contratos_data:
                flash('Nenhum contrato encontrado para exportar.', 'info')
                return redirect(url_for('contratos_module'))

            df = pd.DataFrame(contratos_data)

            df = df.rename(columns={
                'ID_Contratos': 'ID Contrato',
                'Numero_Contrato': 'Número do Contrato',
                'Valor_Contrato': 'Valor (R$)',
                'Data_Assinatura': 'Data Assinatura',
                'Data_Ordem_Inicio': 'Ordem de Início',
                'Prazo_Contrato_Dias': 'Prazo (Dias)',
                'Data_Termino_Previsto': 'Término Previsto',
                'Status_Contrato': 'Status',
                'Observacoes': 'Observações',
                'Nome_Cliente': 'Cliente',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            ordered_columns = [
                'ID Contrato', 'Número do Contrato', 'Cliente', 'Valor (R$)',
                'Data Assinatura', 'Ordem de Início', 'Prazo (Dias)', 'Término Previsto',
                'Status', 'Observações', 'Data de Criação', 'Última Modificação'
            ]
            df = df[[col for col in ordered_columns if col in df.columns]]

            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_contratos.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar contratos para Excel: {e}", 'danger')
        print(f"Erro ao exportar contratos Excel: {e}")
        return redirect(url_for('contratos_module'))


# ===============================================================
# 3.4 ROTAS DE ARTS - OBRAS
# ===============================================================
@app.route('/obras/arts')
@login_required
def arts_module(): 
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para acessar o módulo de ARTs.', 'warning')
        return redirect(url_for('welcome'))

    search_numero = request.args.get('numero_art')
    search_obra_id = request.args.get('obra_id')
    search_status = request.args.get('status_art')

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            arts = obras_manager.get_all_arts(
                search_numero=search_numero,
                search_obra_id=search_obra_id,
                search_status=search_status
            )
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']

        return render_template(
            'obras/arts/arts_module.html',
            user=current_user,
            arts=arts,
            all_obras=all_obras,
            status_options=status_options,
            selected_numero=search_numero,
            selected_obra_id=int(search_obra_id) if search_obra_id else None,
            selected_status=search_status
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar ARTs: {e}", 'danger')
        print(f"Erro de banco de dados em arts_module: {e}")
        return redirect(url_for('obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar ARTs: {e}", 'danger')
        print(f"Erro inesperado em arts_module: {e}")
        return redirect(url_for('obras_module')) 

# ---------------------------------------------------------------
# 3.4.1 ROTAS DO CRUD DE ARTS - CRIAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/arts/add', methods=['GET', 'POST'])
@login_required
def add_art():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para adicionar ARTs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_art = request.form['numero_art'].strip()
                data_pagamento_str = request.form.get('data_pagamento', '').strip()
                valor_pagamento = float(request.form.get('valor_pagamento', '0').replace(',', '.'))
                status_art = request.form['status_art'].strip()

                if not all([id_obras, numero_art, status_art]):
                    flash('Campos obrigatórios (Obra, Número da ART, Status) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
                    return render_template(
                        'obras/arts/add_art.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                try:
                    data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date() if data_pagamento_str else None
                except ValueError:
                    flash('Formato de Data de Pagamento inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
                    return render_template(
                        'obras/arts/add_art.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                if obras_manager.get_art_by_numero(numero_art):
                    flash('Número da ART já existe. Por favor, use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
                    return render_template(
                        'obras/arts/add_art.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.add_art(
                    id_obras, numero_art, data_pagamento, valor_pagamento, status_art
                )
                if success:
                    flash('ART adicionada com sucesso!', 'success')
                    return redirect(url_for('arts_module'))
                else:
                    flash('Erro ao adicionar ART. Verifique os dados e tente novamente.', 'danger')
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
                
            return render_template(
                'obras/arts/add_art.html',
                user=current_user,
                all_obras=all_obras,
                status_options=status_options,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_art: {e}")
        return redirect(url_for('arts_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_art: {e}")
        return redirect(url_for('arts_module'))

# ---------------------------------------------------------------
# 3.4.2 ROTAS DO CRUD DE ARTS - EDITAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/arts/edit/<int:art_id>', methods=['GET', 'POST'])
@login_required
def edit_art(art_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para editar ARTs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            art = obras_manager.get_art_by_id(art_id)

            if not art:
                flash('ART não encontrada.', 'danger')
                return redirect(url_for('arts_module'))

            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_art = request.form['numero_art'].strip()
                data_pagamento_str = request.form.get('data_pagamento', '').strip()
                valor_pagamento = float(request.form.get('valor_pagamento', '0').replace(',', '.'))
                status_art = request.form['status_art'].strip()

                if not all([id_obras, numero_art, status_art]):
                    flash('Campos obrigatórios (Obra, Número da ART, Status) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
                    return render_template(
                        'obras/arts/edit_art.html',
                        user=current_user,
                        art=art,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                try:
                    data_pagamento = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date() if data_pagamento_str else None
                except ValueError:
                    flash('Formato de Data de Pagamento inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
                    return render_template(
                        'obras/arts/edit_art.html',
                        user=current_user,
                        art=art,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                existing_art = obras_manager.get_art_by_numero(numero_art)
                if existing_art and existing_art['ID_Arts'] != art_id:
                    flash('Número da ART já existe. Por favor, use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
                    return render_template(
                        'obras/arts/edit_art.html',
                        user=current_user,
                        art=art,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.update_art(
                    art_id, id_obras, numero_art, data_pagamento, valor_pagamento, status_art
                )
                if success:
                    flash('ART atualizada com sucesso!', 'success')
                    return redirect(url_for('arts_module'))
                else:
                    flash('Erro ao atualizar ART.', 'danger')
            
            else: # GET request
                all_obras = obras_manager.get_all_obras_for_dropdown()
                status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
                
                art['Data_Pagamento'] = art['Data_Pagamento'].strftime('%Y-%m-%d') if art['Data_Pagamento'] else ''

            return render_template(
                'obras/arts/edit_art.html',
                user=current_user,
                art=art,
                all_obras=all_obras,
                status_options=status_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_art: {e}")
        return redirect(url_for('arts_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_art: {e}")
        return redirect(url_for('arts_module'))

# ---------------------------------------------------------------
# 3.4.3 ROTAS DO CRUD DE ARTS - DELETAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/arts/delete/<int:art_id>', methods=['POST'])
@login_required
def delete_art(art_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para excluir ARTs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_art(art_id)
            if success:
                flash('ART excluída com sucesso!', 'success')
            else:
                flash('Erro ao excluir ART. Verifique se ela existe.', 'danger')
        return redirect(url_for('arts_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_art: {e}")
        return redirect(url_for('arts_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_art: {e}")
        return redirect(url_for('arts_module'))

# ---------------------------------------------------------------
# 3.4.4 ROTAS DO CRUD DE ARTS - DETALHES - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/arts/details/<int:art_id>')
@login_required
def art_details(art_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para ver detalhes de ARTs.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            art = obras_manager.get_art_by_id(art_id)

            if not art:
                flash('ART não encontrada.', 'danger')
                return redirect(url_for('arts_module'))

        return render_template(
            'obras/arts/art_details.html',
            user=current_user,
            art=art
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em art_details: {e}")
        return redirect(url_for('arts_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em art_details: {e}")
        return redirect(url_for('arts_module'))

# ---------------------------------------------------------------
# 3.4.5 ROTA DE ARTS - EXPORTAR P/ EXCEL - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/arts/export/excel')
@login_required
def export_arts_excel():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para exportar dados de ARTs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            search_numero = request.args.get('numero_art')
            search_obra_id = request.args.get('obra_id')
            search_status = request.args.get('status_art')

            arts_data = obras_manager.get_all_arts(
                search_numero=search_numero,
                search_obra_id=search_obra_id,
                search_status=search_status
            )

            if not arts_data:
                flash('Nenhuma ART encontrada para exportar.', 'info')
                return redirect(url_for('arts_module'))

            df = pd.DataFrame(arts_data)

            df = df.rename(columns={
                'ID_Arts': 'ID ART',
                'ID_Obras': 'ID Obra',
                'Numero_Art': 'Número da ART',
                'Data_Pagamento': 'Data de Pagamento',
                'Valor_Pagamento': 'Valor de Pagamento (R$)',
                'Status_Art': 'Status',
                'Numero_Obra': 'Número da Obra',
                'Nome_Obra': 'Nome da Obra',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            ordered_columns = [
                'ID ART', 'Número da ART', 'Número da Obra', 'Nome da Obra',
                'Data de Pagamento', 'Valor de Pagamento (R$)', 'Status',
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
                download_name='relatorio_arts.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar ARTs para Excel: {e}", 'danger')
        print(f"Erro ao exportar ARTs Excel: {e}")
        return redirect(url_for('arts_module'))


# ===============================================================
# 3.5 ROTAS DE MEDICOES - OBRAS
# ===============================================================
@app.route('/obras/medicoes')
@login_required
def medicoes_module(): 
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Medições.', 'warning')
        return redirect(url_for('welcome'))

    search_numero_medicao = request.args.get('numero_medicao')
    search_obra_id = request.args.get('obra_id')
    search_status = request.args.get('status_medicao')

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            medicoes = obras_manager.get_all_medicoes(
                search_numero_medicao=search_numero_medicao,
                search_obra_id=search_obra_id,
                search_status=search_status
            )
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']

        return render_template(
            'obras/medicoes/medicoes_module.html',
            user=current_user,
            medicoes=medicoes,
            all_obras=all_obras,
            status_options=status_options,
            selected_numero_medicao=search_numero_medicao,
            selected_obra_id=int(search_obra_id) if search_obra_id else None,
            selected_status=search_status
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Medições: {e}", 'danger')
        print(f"Erro de banco de dados em medicoes_module: {e}")
        return redirect(url_for('obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Medições: {e}", 'danger')
        print(f"Erro inesperado em medicoes_module: {e}")
        return redirect(url_for('obras_module')) 

# ---------------------------------------------------------------
# 3.5.1 ROTAS DO CRUD DE MEDICOES - CRIAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/medicoes/add', methods=['GET', 'POST'])
@login_required
def add_medicao():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para adicionar Medições.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_medicao = int(request.form['numero_medicao'])
                valor_medicao = float(request.form['valor_medicao'].replace(',', '.'))
                data_medicao_str = request.form['data_medicao'].strip()
                mes_referencia = request.form.get('mes_referencia', '').strip()
                data_aprovacao_str = request.form.get('data_aprovacao', '').strip()
                status_medicao = request.form['status_medicao'].strip()
                observacao_medicao = request.form.get('observacao_medicao', '').strip()

                if not all([id_obras, numero_medicao, valor_medicao, data_medicao_str, status_medicao]):
                    flash('Campos obrigatórios (Obra, Número, Valor, Data, Status) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
                    return render_template(
                        'obras/medicoes/add_medicao.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                try:
                    data_medicao = datetime.strptime(data_medicao_str, '%Y-%m-%d').date()
                    data_aprovacao = datetime.strptime(data_aprovacao_str, '%Y-%m-%d').date() if data_aprovacao_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
                    return render_template(
                        'obras/medicoes/add_medicao.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                if obras_manager.get_medicao_by_obra_numero(id_obras, numero_medicao):
                    flash('Já existe uma medição com este número para a obra selecionada. Use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
                    return render_template(
                        'obras/medicoes/add_medicao.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.add_medicao(
                    id_obras, numero_medicao, valor_medicao, data_medicao, mes_referencia, data_aprovacao, status_medicao, observacao_medicao
                )
                if success:
                    flash('Medição adicionada com sucesso!', 'success')
                    return redirect(url_for('medicoes_module'))
                else:
                    flash('Erro ao adicionar medição. Verifique os dados e tente novamente.', 'danger')
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
                
            return render_template(
                'obras/medicoes/add_medicao.html',
                user=current_user,
                all_obras=all_obras,
                status_options=status_options,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_medicao: {e}")
        return redirect(url_for('medicoes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_medicao: {e}")
        return redirect(url_for('medicoes_module'))

# ---------------------------------------------------------------
# 3.5.2 ROTAS DO CRUD DE MEDICOES - EDITAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/medicoes/edit/<int:medicao_id>', methods=['GET', 'POST'])
@login_required
def edit_medicao(medicao_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para editar Medições.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            medicao = obras_manager.get_medicao_by_id(medicao_id)

            if not medicao:
                flash('Medição não encontrada.', 'danger')
                return redirect(url_for('medicoes_module'))

            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_medicao = int(request.form['numero_medicao'])
                valor_medicao = float(request.form['valor_medicao'].replace(',', '.'))
                data_medicao_str = request.form['data_medicao'].strip()
                mes_referencia = request.form.get('mes_referencia', '').strip()
                data_aprovacao_str = request.form.get('data_aprovacao', '').strip()
                status_medicao = request.form['status_medicao'].strip()
                observacao_medicao = request.form.get('observacao_medicao', '').strip()

                if not all([id_obras, numero_medicao, valor_medicao, data_medicao_str, status_medicao]):
                    flash('Campos obrigatórios (Obra, Número, Valor, Data, Status) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
                    return render_template(
                        'obras/medicoes/edit_medicao.html',
                        user=current_user,
                        medicao=medicao,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                try:
                    data_medicao = datetime.strptime(data_medicao_str, '%Y-%m-%d').date()
                    data_aprovacao = datetime.strptime(data_aprovacao_str, '%Y-%m-%d').date() if data_aprovacao_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
                    return render_template(
                        'obras/medicoes/edit_medicao.html',
                        user=current_user,
                        medicao=medicao,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )

                if obras_manager.get_medicao_by_obra_numero(id_obras, numero_medicao):
                    flash('Já existe uma medição com este número para a obra selecionada. Use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
                    return render_template(
                        'obras/medicoes/edit_medicao.html',
                        user=current_user,
                        medicao=medicao,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.update_medicao(
                    medicao_id, id_obras, numero_medicao, valor_medicao, data_medicao, mes_referencia, data_aprovacao, status_medicao, observacao_medicao
                )
                if success:
                    flash('Medição atualizada com sucesso!', 'success')
                    return redirect(url_for('medicoes_module'))
                else:
                    flash('Erro ao atualizar medição.', 'danger')
            
            else: # GET request
                all_obras = obras_manager.get_all_obras_for_dropdown()
                status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
                
                medicao['Data_Medicao'] = medicao['Data_Medicao'].strftime('%Y-%m-%d') if medicao['Data_Medicao'] else ''
                medicao['Data_Aprovacao'] = medicao['Data_Aprovacao'].strftime('%Y-%m-%d') if medicao['Data_Aprovacao'] else ''

            return render_template(
                'obras/medicoes/edit_medicao.html',
                user=current_user,
                medicao=medicao,
                all_obras=all_obras,
                status_options=status_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_medicao: {e}")
        return redirect(url_for('medicoes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_medicao: {e}")
        return redirect(url_for('medicoes_module'))

# ---------------------------------------------------------------
# 3.5.3 ROTAS DO CRUD DE MEDICOES - DELETAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/medicoes/delete/<int:medicao_id>', methods=['POST'])
@login_required
def delete_medicao(medicao_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para excluir Medições.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_medicao(medicao_id)
            if success:
                flash('Medição excluída com sucesso!', 'success')
            else:
                flash('Erro ao excluir medição. Verifique se ela existe.', 'danger')
        return redirect(url_for('medicoes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_medicao: {e}")
        return redirect(url_for('medicoes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_medicao: {e}")
        return redirect(url_for('medicoes_module'))

# ---------------------------------------------------------------
# 3.5.4 ROTAS DO CRUD DE MEDICOES - DETALHES - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/medicoes/details/<int:medicao_id>')
@login_required
def medicao_details(medicao_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para ver detalhes de Medições.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            medicao = obras_manager.get_medicao_by_id(medicao_id)

            if not medicao:
                flash('Medição não encontrada.', 'danger')
                return redirect(url_for('medicoes_module'))

        return render_template(
            'obras/medicoes/medicao_details.html',
            user=current_user,
            medicao=medicao
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em medicao_details: {e}")
        return redirect(url_for('medicoes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em medicao_details: {e}")
        return redirect(url_for('medicoes_module'))

# ---------------------------------------------------------------
# 3.5.5 ROTA DE MEDICOES - EXPORTAR P/ EXCEL - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/medicoes/export/excel')
@login_required
def export_medicoes_excel():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para exportar dados de Medições.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            search_numero_medicao = request.args.get('numero_medicao')
            search_obra_id = request.args.get('obra_id')
            search_status = request.args.get('status_medicao')

            medicoes_data = obras_manager.get_all_medicoes(
                search_numero_medicao=search_numero_medicao,
                search_obra_id=search_obra_id,
                search_status=search_status
            )

            if not medicoes_data:
                flash('Nenhuma Medição encontrada para exportar.', 'info')
                return redirect(url_for('medicoes_module'))

            df = pd.DataFrame(medicoes_data)

            df = df.rename(columns={
                'ID_Medicoes': 'ID Medição',
                'ID_Obras': 'ID Obra',
                'Numero_Medicao': 'Número da Medição',
                'Valor_Medicao': 'Valor da Medição (R$)',
                'Data_Medicao': 'Data da Medição',
                'Mes_Referencia': 'Mês de Referência',
                'Data_Aprovacao': 'Data de Aprovação',
                'Status_Medicao': 'Status',
                'Observacao_Medicao': 'Observações',
                'Numero_Obra': 'Número da Obra',
                'Nome_Obra': 'Nome da Obra',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            ordered_columns = [
                'ID Medição', 'Número da Medição', 'Número da Obra', 'Nome da Obra',
                'Valor da Medição (R$)', 'Data da Medição', 'Mês de Referência',
                'Data de Aprovação', 'Status', 'Observações', 'Data de Criação', 'Última Modificação'
            ]
            df = df[[col for col in ordered_columns if col in df.columns]]

            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_medicoes.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Medições para Excel: {e}", 'danger')
        print(f"Erro ao exportar Medições Excel: {e}")
        return redirect(url_for('medicoes_module'))


# ===============================================================
# 3.6 ROTAS DE AVANCO FISICO - OBRAS
# ===============================================================
@app.route('/obras/avancos_fisicos')
@login_required
def avancos_fisicos_module(): 
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Avanços Físicos.', 'warning')
        return redirect(url_for('welcome'))

    search_obra_id = request.args.get('obra_id')
    search_data_inicio_str = request.args.get('data_inicio')
    search_data_fim_str = request.args.get('data_fim')

    search_data_inicio = None
    search_data_fim = None

    try:
        if search_data_inicio_str:
            search_data_inicio = datetime.strptime(search_data_inicio_str, '%Y-%m-%d').date()
        if search_data_fim_str:
            search_data_fim = datetime.strptime(search_data_fim_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Formato de data inválido nos filtros. Use AAAA-MM-DD.', 'danger')
        return redirect(url_for('avancos_fisicos_module')) 

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            avancos = obras_manager.get_all_avancos_fisicos(
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_data_inicio=search_data_inicio,
                search_data_fim=search_data_fim
            )
            
            all_obras = obras_manager.get_all_obras_for_dropdown()

        return render_template(
            'obras/avancos_fisicos/avancos_fisicos_module.html',
            user=current_user,
            avancos=avancos,
            all_obras=all_obras,
            selected_obra_id=int(search_obra_id) if search_obra_id else None,
            selected_data_inicio=search_data_inicio_str,
            selected_data_fim=search_data_fim_str
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Avanços Físicos: {e}", 'danger')
        print(f"Erro de banco de dados em avancos_fisicos_module: {e}")
        return redirect(url_for('obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Avanços Físicos: {e}", 'danger')
        print(f"Erro inesperado em avancos_fisicos_module: {e}")
        return redirect(url_for('obras_module')) 

# ---------------------------------------------------------------
# 3.6.1 ROTAS DO CRUD DE AVANCO FISICO - CRIAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/avancos_fisicos/add', methods=['GET', 'POST'])
@login_required
def add_avanco_fisico():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para adicionar Avanços Físicos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                percentual_avanco_fisico = float(request.form['percentual_avanco_fisico'].replace(',', '.'))
                data_avanco_str = request.form['data_avanco'].strip()

                if not all([id_obras, percentual_avanco_fisico, data_avanco_str]):
                    flash('Campos obrigatórios (Obra, Percentual de Avanço, Data) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    return render_template(
                        'obras/avancos_fisicos/add_avanco_fisico.html',
                        user=current_user,
                        all_obras=all_obras,
                        form_data=request.form
                    )
                
                try:
                    data_avanco = datetime.strptime(data_avanco_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Avanço inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    return render_template(
                        'obras/avancos_fisicos/add_avanco_fisico.html',
                        user=current_user,
                        all_obras=all_obras,
                        form_data=request.form
                    )
                
                if not (0 <= percentual_avanco_fisico <= 100):
                    flash('Percentual de Avanço Físico deve ser entre 0 e 100.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    return render_template(
                        'obras/avancos_fisicos/add_avanco_fisico.html',
                        user=current_user,
                        all_obras=all_obras,
                        form_data=request.form
                    )


                success = obras_manager.add_avanco_fisico(
                    id_obras, percentual_avanco_fisico, data_avanco
                )
                if success:
                    flash('Avanço Físico adicionado com sucesso!', 'success')
                    return redirect(url_for('avancos_fisicos_module'))
                else:
                    flash('Erro ao adicionar avanço físico. Verifique os dados e tente novamente.', 'danger')
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
                
            return render_template(
                'obras/avancos_fisicos/add_avanco_fisico.html',
                user=current_user,
                all_obras=all_obras,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_avanco_fisico: {e}")
        return redirect(url_for('avancos_fisicos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_avanco_fisico: {e}")
        return redirect(url_for('avancos_fisicos_module'))

# ---------------------------------------------------------------
# 3.6.2 ROTAS DO CRUD DE AVANCO FISICO - EDITAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/avancos_fisicos/edit/<int:avanco_id>', methods=['GET', 'POST'])
@login_required
def edit_avanco_fisico(avanco_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para editar Avanços Físicos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            avanco = obras_manager.get_avanco_fisico_by_id(avanco_id)

            if not avanco:
                flash('Avanço Físico não encontrado.', 'danger')
                return redirect(url_for('avancos_fisicos_module'))

            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                percentual_avanco_fisico = float(request.form['percentual_avanco_fisico'].replace(',', '.'))
                data_avanco_str = request.form['data_avanco'].strip()

                if not all([id_obras, percentual_avanco_fisico, data_avanco_str]):
                    flash('Campos obrigatórios (Obra, Percentual de Avanço, Data) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    return render_template(
                        'obras/avancos_fisicos/edit_avanco_fisico.html',
                        user=current_user,
                        avanco=avanco,
                        all_obras=all_obras,
                        form_data=request.form
                    )
                
                try:
                    data_avanco = datetime.strptime(data_avanco_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Avanço inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    return render_template(
                        'obras/avancos_fisicos/edit_avanco_fisico.html',
                        user=current_user,
                        avanco=avanco,
                        all_obras=all_obras,
                        form_data=request.form
                    )

                if not (0 <= percentual_avanco_fisico <= 100):
                    flash('Percentual de Avanço Físico deve ser entre 0 e 100.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    return render_template(
                        'obras/avancos_fisicos/edit_avanco_fisico.html',
                        user=current_user,
                        avanco=avanco,
                        all_obras=all_obras,
                        form_data=request.form
                    )


                success = obras_manager.update_avanco_fisico(
                    avanco_id, id_obras, percentual_avanco_fisico, data_avanco
                )
                if success:
                    flash('Avanço Físico atualizado com sucesso!', 'success')
                    return redirect(url_for('avancos_fisicos_module'))
                else:
                    flash('Erro ao atualizar avanço físico.', 'danger')
            
            else: # GET request
                all_obras = obras_manager.get_all_obras_for_dropdown()
                
                avanco['Data_Avanco'] = avanco['Data_Avanco'].strftime('%Y-%m-%d') if avanco['Data_Avanco'] else ''

            return render_template(
                'obras/avancos_fisicos/edit_avanco_fisico.html',
                user=current_user,
                avanco=avanco,
                all_obras=all_obras
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_avanco_fisico: {e}")
        return redirect(url_for('avancos_fisicos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_avanco_fisico: {e}")
        return redirect(url_for('avancos_fisicos_module'))

# ---------------------------------------------------------------
# 3.6.3 ROTAS DO CRUD DE AVANCO FISICO - DELETAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/avancos_fisicos/delete/<int:avanco_id>', methods=['POST'])
@login_required
def delete_avanco_fisico(avanco_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para excluir Avanços Físicos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_avanco_fisico(avanco_id)
            if success:
                flash('Avanço Físico excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir avanço físico. Verifique se ele existe.', 'danger')
        return redirect(url_for('avancos_fisicos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_avanco_fisico: {e}")
        return redirect(url_for('avancos_fisicos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_avanco_fisico: {e}")
        return redirect(url_for('avancos_fisicos_module'))

# ---------------------------------------------------------------
# 3.6.4 ROTAS DO CRUD DE AVANCO FISICO - DETALHES - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/avancos_fisicos/details/<int:avanco_id>')
@login_required
def avanco_fisico_details(avanco_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para ver detalhes de Avanços Físicos.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            avanco = obras_manager.get_avanco_fisico_by_id(avanco_id)

            if not avanco:
                flash('Avanço Físico não encontrado.', 'danger')
                return redirect(url_for('avancos_fisicos_module'))

        return render_template(
            'obras/avancos_fisicos/avanco_fisico_details.html',
            user=current_user,
            avanco=avanco
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em avanco_fisico_details: {e}")
        return redirect(url_for('avancos_fisicos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em avanco_fisico_details: {e}")
        return redirect(url_for('avancos_fisicos_module'))

# ---------------------------------------------------------------
# 3.6.5 ROTA DE AVANCO FISICO - EXPORTAR P/ EXCEL - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/avancos_fisicos/export/excel')
@login_required
def export_avancos_fisicos_excel():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para exportar dados de Avanços Físicos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            search_obra_id = request.args.get('obra_id')
            search_data_inicio_str = request.args.get('data_inicio')
            search_data_fim_str = request.args.get('data_fim')

            search_data_inicio = None
            search_data_fim = None
            try:
                if search_data_inicio_str:
                    search_data_inicio = datetime.strptime(search_data_inicio_str, '%Y-%m-%d').date()
                if search_data_fim_str:
                    search_data_fim = datetime.strptime(search_data_fim_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de data inválido nos filtros de exportação. Use AAAA-MM-DD.', 'danger')
                return redirect(url_for('avancos_fisicos_module')) 

            avancos_data = obras_manager.get_all_avancos_fisicos(
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_data_inicio=search_data_inicio,
                search_data_fim=search_data_fim
            )

            if not avancos_data:
                flash('Nenhum Avanço Físico encontrado para exportar.', 'info')
                return redirect(url_for('avancos_fisicos_module'))

            df = pd.DataFrame(avancos_data)

            df = df.rename(columns={
                'ID_Avancos_Fisicos': 'ID Avanço',
                'ID_Obras': 'ID Obra',
                'Percentual_Avanco_Fisico': 'Percentual de Avanço (%)',
                'Data_Avanco': 'Data do Avanço',
                'Numero_Obra': 'Número da Obra',
                'Nome_Obra': 'Nome da Obra',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            ordered_columns = [
                'ID Avanço', 'Número da Obra', 'Nome da Obra',
                'Percentual de Avanço (%)', 'Data do Avanço',
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
                download_name='relatorio_avancos_fisicos.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Avanços Físicos para Excel: {e}", 'danger')
        print(f"Erro ao exportar Avanços Físicos Excel: {e}")
        return redirect(url_for('avancos_fisicos_module'))


# ===============================================================
# 3.7 ROTAS DE REIDI - OBRAS
# ===============================================================
@app.route('/obras/reidis')
@login_required
def reidis_module():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para acessar o módulo de REIDIs.', 'warning')
        return redirect(url_for('welcome'))

    search_numero_portaria = request.args.get('numero_portaria')
    search_numero_ato = request.args.get('numero_ato')
    search_obra_id = request.args.get('obra_id')
    search_status = request.args.get('status_reidi')

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            reidis = obras_manager.get_all_reidis(
                search_numero_portaria=search_numero_portaria,
                search_numero_ato=search_numero_ato,
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_status=search_status
            )
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise'] 

        return render_template(
            'obras/reidis/reidis_module.html',
            user=current_user,
            reidis=reidis,
            all_obras=all_obras,
            status_options=status_options,
            selected_numero_portaria=search_numero_portaria,
            selected_numero_ato=search_numero_ato,
            selected_obra_id=int(search_obra_id) if search_obra_id else None,
            selected_status=search_status
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar REIDIs: {e}", 'danger')
        print(f"Erro de banco de dados em reidis_module: {e}")
        return redirect(url_for('obras_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar REIDIs: {e}", 'danger')
        print(f"Erro inesperado em reidis_module: {e}")
        return redirect(url_for('obras_module'))

# ---------------------------------------------------------------
# 3.7.1 ROTAS DO CRUD DE REIDI - CRIAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/reidis/add', methods=['GET', 'POST'])
@login_required
def add_reidi():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para adicionar REIDIs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_portaria = request.form['numero_portaria'].strip()
                numero_ato_declaratorio = request.form['numero_ato_declaratorio'].strip()
                data_aprovacao_reidi_str = request.form.get('data_aprovacao_reidi', '').strip()
                data_validade_reidi_str = request.form.get('data_validade_reidi', '').strip()
                status_reidi = request.form.get('status_reidi', '').strip() 
                observacoes_reidi = request.form.get('observacoes_reidi', '').strip()

                if not all([id_obras, numero_portaria, numero_ato_declaratorio]): 
                    flash('Campos obrigatórios (Obra, Número da Portaria, Número do Ato Declaratório) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                    return render_template(
                        'obras/reidis/add_reidi.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                data_aprovacao_reidi = None
                data_validade_reidi = None
                try:
                    data_aprovacao_reidi = datetime.strptime(data_aprovacao_reidi_str, '%Y-%m-%d').date() if data_aprovacao_reidi_str else None
                    data_validade_reidi = datetime.strptime(data_validade_reidi_str, '%Y-%m-%d').date() if data_validade_reidi_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                    return render_template(
                        'obras/reidis/add_reidi.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                if obras_manager.get_reidi_by_numero_portaria(numero_portaria):
                    flash('Número da Portaria já existe. Por favor, use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                    return render_template(
                        'obras/reidis/add_reidi.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                if obras_manager.get_reidi_by_numero_ato_declaratorio(numero_ato_declaratorio):
                    flash('Número do Ato Declaratório já existe. Por favor, use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                    return render_template(
                        'obras/reidis/add_reidi.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )

                success = obras_manager.add_reidi(
                    id_obras, numero_portaria, numero_ato_declaratorio, data_aprovacao_reidi, data_validade_reidi, status_reidi, observacoes_reidi
                )
                if success:
                    flash('REIDI adicionado com sucesso!', 'success')
                    return redirect(url_for('reidis_module'))
                else:
                    flash('Erro ao adicionar REIDI. Verifique os dados e tente novamente.', 'danger')
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                
            return render_template(
                'obras/reidis/add_reidi.html',
                user=current_user,
                all_obras=all_obras,
                status_options=status_options,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_reidi: {e}")
        return redirect(url_for('reidis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_reidi: {e}")
        return redirect(url_for('reidis_module'))

# ---------------------------------------------------------------
# 3.7.2 ROTAS DO CRUD DE REIDI - EDITAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/reidis/edit/<int:reidi_id>', methods=['GET', 'POST'])
@login_required
def edit_reidi(reidi_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para editar REIDIs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            reidi = obras_manager.get_reidi_by_id(reidi_id)

            if not reidi:
                flash('REIDI não encontrado.', 'danger')
                return redirect(url_for('reidis_module'))

            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_portaria = request.form['numero_portaria'].strip()
                numero_ato_declaratorio = request.form['numero_ato_declaratorio'].strip()
                data_aprovacao_reidi_str = request.form.get('data_aprovacao_reidi', '').strip()
                data_validade_reidi_str = request.form.get('data_validade_reidi', '').strip()
                status_reidi = request.form.get('status_reidi', '').strip() 
                observacoes_reidi = request.form.get('observacoes_reidi', '').strip()

                if not all([id_obras, numero_portaria, numero_ato_declaratorio]):
                    flash('Campos obrigatórios (Obra, Número da Portaria, Número do Ato Declaratório) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                    return render_template(
                        'obras/reidis/edit_reidi.html',
                        user=current_user,
                        reidi=reidi,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                data_aprovacao_reidi = None
                data_validade_reidi = None
                try:
                    data_aprovacao_reidi = datetime.strptime(data_aprovacao_reidi_str, '%Y-%m-%d').date() if data_aprovacao_reidi_str else None
                    data_validade_reidi = datetime.strptime(data_validade_reidi_str, '%Y-%m-%d').date() if data_validade_reidi_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                    return render_template(
                        'obras/reidis/edit_reidi.html',
                        user=current_user,
                        reidi=reidi,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )

                if obras_manager.get_reidi_by_numero_portaria(numero_portaria):
                    flash('Número da Portaria já existe. Por favor, use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                    return render_template(
                        'obras/reidis/edit_reidi.html',
                        user=current_user,
                        reidi=reidi,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )

                if obras_manager.get_reidi_by_numero_ato_declaratorio(numero_ato_declaratorio):
                    flash('Número do Ato Declaratório já existe. Por favor, use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                    return render_template(
                        'obras/reidis/edit_reidi.html',
                        user=current_user,
                        reidi=reidi,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=request.form
                    )


                success = obras_manager.update_reidi(
                    reidi_id, id_obras, numero_portaria, numero_ato_declaratorio, data_aprovacao_reidi, data_validade_reidi, status_reidi, observacoes_reidi
                )
                if success:
                    flash('REIDI atualizado com sucesso!', 'success')
                    return redirect(url_for('reidis_module'))
                else:
                    flash('Erro ao atualizar REIDI.', 'danger')
            
            else: # GET request
                all_obras = obras_manager.get_all_obras_for_dropdown()
                status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                
                reidi['Data_Aprovacao_Reidi'] = reidi['Data_Aprovacao_Reidi'].strftime('%Y-%m-%d') if reidi['Data_Aprovacao_Reidi'] else ''
                reidi['Data_Validade_Reidi'] = reidi['Data_Validade_Reidi'].strftime('%Y-%m-%d') if reidi['Data_Validade_Reidi'] else ''

            return render_template(
                'obras/reidis/edit_reidi.html',
                user=current_user,
                reidi=reidi,
                all_obras=all_obras,
                status_options=status_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_reidi: {e}")
        return redirect(url_for('reidis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_reidi: {e}")
        return redirect(url_for('reidis_module'))

# ---------------------------------------------------------------
# 3.7.3 ROTAS DO CRUD DE REIDI - DELETAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/reidis/delete/<int:reidi_id>', methods=['POST'])
@login_required
def delete_reidi(reidi_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para excluir REIDIs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_reidi(reidi_id)
            if success:
                flash('REIDI excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir REIDI. Verifique se ele existe.', 'danger')
        return redirect(url_for('reidis_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_reidi: {e}")
        return redirect(url_for('reidis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_reidi: {e}")
        return redirect(url_for('reidis_module'))

# ---------------------------------------------------------------
# 3.7.4 ROTAS DO CRUD DE REIDI - DETALHES - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/reidis/details/<int:reidi_id>')
@login_required
def reidi_details(reidi_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para ver detalhes de REIDIs.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            reidi = obras_manager.get_reidi_by_id(reidi_id)

            if not reidi:
                flash('REIDI não encontrado.', 'danger')
                return redirect(url_for('reidis_module'))

        return render_template(
            'obras/reidis/reidi_details.html',
            user=current_user,
            reidi=reidi
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em reidi_details: {e}")
        return redirect(url_for('reidis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em reidi_details: {e}")
        return redirect(url_for('reidis_module'))

# ---------------------------------------------------------------
# 3.7.5 ROTA DE REIDI - EXPORTAR P/ EXCEL - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/reidis/export/excel')
@login_required
def export_reidis_excel():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para exportar dados de REIDIs.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            search_numero_portaria = request.args.get('numero_portaria')
            search_numero_ato = request.args.get('numero_ato')
            search_obra_id = request.args.get('obra_id')
            search_status = request.args.get('status_reidi')

            reidis_data = obras_manager.get_all_reidis(
                search_numero_portaria=search_numero_portaria,
                search_numero_ato=search_numero_ato,
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_status=search_status
            )

            if not reidis_data:
                flash('Nenhum REIDI encontrado para exportar.', 'info')
                return redirect(url_for('reidis_module'))

            df = pd.DataFrame(reidis_data)

            df = df.rename(columns={
                'ID_Reidis': 'ID REIDI',
                'ID_Obras': 'ID Obra',
                'Numero_Portaria': 'Número da Portaria',
                'Numero_Ato_Declaratorio': 'Número do Ato Declaratório',
                'Data_Aprovacao_Reidi': 'Data de Aprovação',
                'Data_Validade_Reidi': 'Data de Validade',
                'Status_Reidi': 'Status',
                'Observacoes_Reidi': 'Observações',
                'Numero_Obra': 'Número da Obra',
                'Nome_Obra': 'Nome da Obra',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            ordered_columns = [
                'ID REIDI', 'Número da Portaria', 'Número do Ato Declaratório',
                'Número da Obra', 'Nome da Obra', 'Data de Aprovação', 'Data de Validade',
                'Status', 'Observações', 'Data de Criação', 'Última Modificação'
            ]
            df = df[[col for col in ordered_columns if col in df.columns]]

            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)

            return send_file(
                excel_buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='relatorio_reidis.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar REIDIs para Excel: {e}", 'danger')
        print(f"Erro ao exportar REIDIs Excel: {e}")
        return redirect(url_for('reidis_module'))


# ===============================================================
# 3.8 ROTAS DE SEGUROS - OBRAS
# ===============================================================
@app.route('/obras/seguros')
@login_required
def seguros_module(): 
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Seguros.', 'warning')
        return redirect(url_for('welcome'))

    search_numero_apolice = request.args.get('numero_apolice')
    search_obra_id = request.args.get('obra_id')
    search_status = request.args.get('status_seguro')
    search_tipo = request.args.get('tipo_seguro')

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            seguros = obras_manager.get_all_seguros(
                search_numero_apolice=search_numero_apolice,
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_status=search_status,
                search_tipo=search_tipo
            )
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
            tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']

        return render_template(
            'obras/seguros/seguros_module.html',
            user=current_user,
            seguros=seguros,
            all_obras=all_obras,
            status_options=status_options,
            tipo_seguro_options=tipo_seguro_options,
            selected_numero_apolice=search_numero_apolice,
            selected_obra_id=int(search_obra_id) if search_obra_id else None,
            selected_status=search_status,
            selected_tipo=search_tipo
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em seguros_module: {e}")
        return redirect(url_for('obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em seguros_module: {e}")
        return redirect(url_for('obras_module')) 

# ---------------------------------------------------------------
# 3.8.1 ROTAS DO CRUD DE SEGUROS - CRIAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/seguros/add', methods=['GET', 'POST'])
@login_required
def add_seguro():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para adicionar Seguros.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_apolice = request.form['numero_apolice'].strip()
                seguradora = request.form['seguradora'].strip()
                tipo_seguro = request.form['tipo_seguro'].strip()
                valor_segurado = float(request.form.get('valor_segurado', '0').replace(',', '.'))
                data_inicio_vigencia_str = request.form.get('data_inicio_vigencia', '').strip()
                data_fim_vigencia_str = request.form.get('data_fim_vigencia', '').strip()
                status_seguro = request.form.get('status_seguro', '').strip()
                observacoes_seguro = request.form.get('observacoes_seguro', '').strip()

                if not all([id_obras, numero_apolice, seguradora, tipo_seguro, data_inicio_vigencia_str]):
                    flash('Campos obrigatórios (Obra, Número da Apólice, Seguradora, Tipo, Data Início Vigência) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
                    tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
                    return render_template(
                        'obras/seguros/add_seguro.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        tipo_seguro_options=tipo_seguro_options,
                        form_data=request.form
                    )
                
                data_inicio_vigencia = None
                data_fim_vigencia = None
                try:
                    data_inicio_vigencia = datetime.strptime(data_inicio_vigencia_str, '%Y-%m-%d').date() if data_inicio_vigencia_str else None
                    data_fim_vigencia = datetime.strptime(data_fim_vigencia_str, '%Y-%m-%d').date() if data_fim_vigencia_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
                    tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
                    return render_template(
                        'obras/seguros/add_seguro.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        tipo_seguro_options=tipo_seguro_options,
                        form_data=request.form
                    )
                
                if obras_manager.get_seguro_by_numero_apolice(numero_apolice):
                    flash('Número da Apólice já existe. Por favor, use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
                    tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
                    return render_template(
                        'obras/seguros/add_seguro.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        tipo_seguro_options=tipo_seguro_options,
                        form_data=request.form
                    )

                success = obras_manager.add_seguro(
                    id_obras, numero_apolice, seguradora, tipo_seguro, valor_segurado, data_inicio_vigencia, data_fim_vigencia, status_seguro, observacoes_seguro
                )
                if success:
                    flash('Seguro adicionado com sucesso!', 'success')
                    return redirect(url_for('seguros_module'))
                else:
                    flash('Erro ao adicionar seguro. Verifique os dados e tente novamente.', 'danger')
            
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
            tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
                
            return render_template(
                'obras/seguros/add_seguro.html',
                user=current_user,
                all_obras=all_obras,
                status_options=status_options,
                tipo_seguro_options=tipo_seguro_options,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_seguro: {e}")
        return redirect(url_for('seguros_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_seguro: {e}")
        return redirect(url_for('seguros_module'))

# ---------------------------------------------------------------
# 3.8.2 ROTAS DO CRUD DE SEGUROS - EDITAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/seguros/edit/<int:seguro_id>', methods=['GET', 'POST'])
@login_required
def edit_seguro(seguro_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para editar Seguros.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            seguro = obras_manager.get_seguro_by_id(seguro_id)

            if not seguro:
                flash('Seguro não encontrado.', 'danger')
                return redirect(url_for('seguros_module'))
            
            # --- ADICIONE ESTES PRINTS DE DEBUG AQUI ---
            print(f"DEBUG (Seguro ID {seguro_id}) - Objeto seguro recebido de db_obras_manager: {seguro}")
            print(f"DEBUG (Seguro ID {seguro_id}) - Tipo Data_Inicio_Vigencia antes: {type(seguro.get('Data_Inicio_Vigencia'))}, Valor: {seguro.get('Data_Inicio_Vigencia')}")
            print(f"DEBUG (Seguro ID {seguro_id}) - Tipo Data_Fim_Vigencia antes: {type(seguro.get('Data_Fim_Vigencia'))}, Valor: {seguro.get('Data_Fim_Vigencia')}")
            # --- FIM DOS PRINTS DE DEBUG ---

            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_apolice = request.form['numero_apolice'].strip()
                seguradora = request.form['seguradora'].strip()
                tipo_seguro = request.form['tipo_seguro'].strip()
                valor_segurado = float(request.form.get('valor_segurado', '0').replace(',', '.'))
                data_inicio_vigencia_str = request.form.get('data_inicio_vigencia', '').strip()
                data_fim_vigencia_str = request.form.get('data_fim_vigencia', '').strip()
                status_seguro = request.form.get('status_seguro', '').strip()
                observacoes_seguro = request.form.get('observacoes_seguro', '').strip()

                if not all([id_obras, numero_apolice, seguradora, tipo_seguro, data_inicio_vigencia_str]):
                    flash('Campos obrigatórios (Obra, Número da Apólice, Seguradora, Tipo, Data Início Vigência) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
                    tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
                    return render_template(
                        'obras/seguros/edit_seguro.html',
                        user=current_user,
                        seguro=seguro,
                        all_obras=all_obras,
                        status_options=status_options,
                        tipo_seguro_options=tipo_seguro_options,
                        form_data=request.form
                    )
                
                data_inicio_vigencia = None
                data_fim_vigencia = None
                try:
                    data_inicio_vigencia = datetime.strptime(data_inicio_vigencia_str, '%Y-%m-%d').date() if data_inicio_vigencia_str else None
                    data_fim_vigencia = datetime.strptime(data_fim_vigencia_str, '%Y-%m-%d').date() if data_fim_vigencia_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
                    tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
                    return render_template(
                        'obras/seguros/edit_seguro.html',
                        user=current_user,
                        seguro=seguro,
                        all_obras=all_obras,
                        status_options=status_options,
                        tipo_seguro_options=tipo_seguro_options,
                        form_data=request.form
                    )
                
                if obras_manager.get_seguro_by_numero_apolice(numero_apolice):
                    flash('Número da Apólice já existe. Por favor, use um número único.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
                    tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
                    return render_template(
                        'obras/seguros/edit_seguro.html',
                        user=current_user,
                        seguro=seguro,
                        all_obras=all_obras,
                        status_options=status_options,
                        tipo_seguro_options=tipo_seguro_options,
                        form_data=request.form
                    )

                success = obras_manager.update_seguro(
                    seguro_id, id_obras, numero_apolice, seguradora, tipo_seguro, valor_segurado, data_inicio_vigencia, data_fim_vigencia, status_seguro, observacoes_seguro
                )
                if success:
                    flash('Seguro atualizado com sucesso!', 'success')
                    return redirect(url_for('seguros_module'))
                else:
                    flash('Erro ao atualizar seguro.', 'danger')
            
            else: # GET request
                all_obras = obras_manager.get_all_obras_for_dropdown()
                status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
                tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
                
                seguro['Data_Inicio_Vigencia'] = seguro['Data_Inicio_Vigencia'].strftime('%Y-%m-%d') if seguro['Data_Inicio_Vigencia'] else ''
                seguro['Data_Fim_Vigencia'] = seguro['Data_Fim_Vigencia'].strftime('%Y-%m-%d') if seguro['Data_Fim_Vigencia'] else ''

                # --- ADICIONE ESTES PRINTS DE DEBUG AQUI TAMBÉM ---
                print(f"DEBUG (Seguro ID {seguro_id}) - Tipo Data_Inicio_Vigencia depois: {type(seguro.get('Data_Inicio_Vigencia'))}, Valor: {seguro.get('Data_Inicio_Vigencia')}")
                print(f"DEBUG (Seguro ID {seguro_id}) - Tipo Data_Fim_Vigencia depois: {type(seguro.get('Data_Fim_Vigencia'))}, Valor: {seguro.get('Data_Fim_Vigencia')}")
                # --- FIM DOS PRINTS DE DEBUG ---

            return render_template(
                'obras/seguros/edit_seguro.html',
                user=current_user,
                seguro=seguro,
                all_obras=all_obras,
                status_options=status_options,
                tipo_seguro_options=tipo_seguro_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_seguro: {e}")
        return redirect(url_for('seguros_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_seguro: {e}")
        return redirect(url_for('seguros_module'))

# ---------------------------------------------------------------
# 3.8.3 ROTAS DO CRUD DE SEGUROS - DELETAR - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/seguros/delete/<int:seguro_id>', methods=['POST'])
@login_required
def delete_seguro(seguro_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para excluir Seguros.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_seguro(seguro_id)
            if success:
                flash('Seguro excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir seguro. Verifique se ele existe.', 'danger')
        return redirect(url_for('seguros_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_seguro: {e}")
        return redirect(url_for('seguros_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_seguro: {e}")
        return redirect(url_for('seguros_module'))

# ---------------------------------------------------------------
# 3.8.4 ROTAS DO CRUD DE SEGUROS - DETALHES - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/seguros/details/<int:seguro_id>')
@login_required
def seguro_details(seguro_id):
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para ver detalhes de Seguros.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            seguro = obras_manager.get_seguro_by_id(seguro_id)

            if not seguro:
                flash('Seguro não encontrado.', 'danger')
                return redirect(url_for('seguros_module'))

        return render_template(
            'obras/seguros/seguro_details.html',
            user=current_user,
            seguro=seguro
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em seguro_details: {e}")
        return redirect(url_for('seguros_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em seguro_details: {e}")
        return redirect(url_for('seguros_module'))

# ---------------------------------------------------------------
# 3.8.5 ROTA DE SEGUROS - EXPORTAR P/ EXCEL - OBRAS
# ---------------------------------------------------------------
@app.route('/obras/seguros/export/excel')
@login_required
def export_seguros_excel():
    if not current_user.can_access_module('Obras'): 
        flash('Acesso negado. Você não tem permissão para exportar dados de Seguros.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            search_numero_apolice = request.args.get('numero_apolice')
            search_obra_id = request.args.get('obra_id')
            search_status = request.args.get('status_seguro')
            search_tipo = request.args.get('tipo_seguro')

            seguros_data = obras_manager.get_all_seguros(
                search_numero_apolice=search_numero_apolice,
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_status=search_status,
                search_tipo=search_tipo
            )

            if not seguros_data:
                flash('Nenhum Seguro encontrado para exportar.', 'info')
                return redirect(url_for('seguros_module'))

            df = pd.DataFrame(seguros_data)

            df = df.rename(columns={
                'ID_Seguros': 'ID Seguro',
                'ID_Obras': 'ID Obra',
                'Numero_Apolice': 'Número da Apólice',
                'Seguradora': 'Seguradora',
                'Tipo_Seguro': 'Tipo de Seguro',
                'Valor_Segurado': 'Valor Segurado (R$)',
                'Data_Inicio_Vigencia': 'Início Vigência',
                'Data_Fim_Vigencia': 'Fim Vigência',
                'Status_Seguro': 'Status',
                'Observacoes_Seguro': 'Observações',
                'Numero_Obra': 'Número da Obra',
                'Nome_Obra': 'Nome da Obra',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            ordered_columns = [
                'ID Seguro', 'Número da Apólice', 'Seguradora', 'Tipo de Seguro',
                'Número da Obra', 'Nome da Obra', 'Valor Segurado (R$)',
                'Início Vigência', 'Fim Vigência', 'Status', 'Observações',
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
                download_name='relatorio_seguros.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Seguros para Excel: {e}", 'danger')
        print(f"Erro ao exportar Seguros Excel: {e}")
        return redirect(url_for('seguros_module'))


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


if __name__ == '__main__':
    app.run(debug=True)