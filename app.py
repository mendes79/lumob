# app.py
# rev01 - integração do campo email da tabela usuarios no app.py

# Importações necessárias
from flask import Flask, render_template, redirect, url_for, request, flash, session, get_flashed_messages, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import mysql.connector # Para a classe Error do MySQL
from datetime import datetime, date # Garante que datetime e date estejam disponíveis

# Para a adição da opção exportar para Excel no módulo Pessoal
from flask import send_file # Adicione este import no topo do seu app.py
import pandas as pd # Adicione este import no topo do seu app.py
from io import BytesIO # Adicione este import no topo do seu app.py

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_user_manager import UserManager
from database.db_hr_manager import HrManager # Para o módulo de RH/DP (mantido para estrutura) <<< ver se ainda precisa! Pode apagar!!!
from database.db_obras_manager import ObrasManager # Para o módulo Obras
from database.db_seguranca_manager import SegurancaManager # Para o módulo Segurança
from database.db_pessoal_manager import PessoalManager

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

# NOVO: Disponibilizar date.today() como 'today' no ambiente Jinja2 para aniversariantes do mês
app.jinja_env.globals.update(today=date.today) # Isso permitirá usar 'today()' no HTML
# Alternativamente, para usar 'now()', você precisaria importar 'datetime' e usar 'datetime.now'

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

#---------------------------------------------------------------------------------------------------
# ROTAS PARA O MÓDULO PESSOAL                                                                      |
#---------------------------------------------------------------------------------------------------

# ROTA PARA O DASHBOARD MÓDULO PESSOAL -------------------------------------------------------------

@app.route('/pessoal/dashboard')
@login_required
def pessoal_dashboard():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o Dashboard de Pessoal.', 'warning')
        return redirect(url_for('welcome'))

    try:
        # Instanciar DatabaseManager e PessoalManager dentro do bloco, como nas outras rotas
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base) # <<< ADICIONE ESTA LINHA AQUI!

            # Obter dados para o dashboard usando os métodos do PessoalManager
            status_counts = pessoal_manager.get_funcionario_status_counts()
            funcionarios_por_cargo = pessoal_manager.get_funcionarios_by_cargo()
            funcionarios_por_nivel = pessoal_manager.get_funcionarios_by_nivel()
            proximas_ferias = pessoal_manager.get_proximas_ferias(dias_antecedencia=60)

            # Renderizar o template do dashboard, passando os dados
            return render_template(
                'pessoal/pessoal_dashboard.html',
                user=current_user, # Sempre bom passar o user para o template
                status_counts=status_counts,
                funcionarios_por_cargo=funcionarios_por_cargo,
                funcionarios_por_nivel=funcionarios_por_nivel,
                proximas_ferias=proximas_ferias
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar dashboard de pessoal: {e}", 'danger')
        print(f"Erro de banco de dados em pessoal_dashboard: {e}")
        return redirect(url_for('pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar dashboard de pessoal: {e}", 'danger')
        print(f"Erro inesperado em pessoal_dashboard: {e}")
        return redirect(url_for('pessoal_module'))

# |-------------------------------------------- ANIVERSARIANTES DO MÊS ------------------------------------------------------|
@app.route('/pessoal/aniversariantes')
@login_required
def pessoal_aniversariantes():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o Relatório de Aniversariantes.', 'warning')
        return redirect(url_for('welcome'))

    # Definir o mês atual (ou um mês específico, se houver filtro futuro)
    mes_atual = date.today().month
    nome_mes = date(1900, mes_atual, 1).strftime('%B') # Retorna o nome completo do mês (ex: July)
    
    # Mapear nome do mês em inglês para português
    meses_pt = {
        'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março', 'April': 'Abril',
        'May': 'Maio', 'June': 'Junho', 'July': 'Julho', 'August': 'Agosto',
        'September': 'Setembro', 'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
    }
    nome_mes_pt = meses_pt.get(nome_mes, nome_mes) # Usa o nome em português ou o original se não mapeado

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base) # Instancia o manager
            
            aniversariantes = pessoal_manager.get_aniversariantes_do_mes(mes=mes_atual)

            return render_template(
                'pessoal/aniversariantes_module.html', # Novo template que criaremos
                user=current_user,
                aniversariantes=aniversariantes,
                mes_referencia=nome_mes_pt # Passa o nome do mês em português para o template
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar aniversariantes: {e}", 'danger')
        print(f"Erro de banco de dados em pessoal_aniversariantes: {e}")
        return redirect(url_for('pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar aniversariantes: {e}", 'danger')
        print(f"Erro inesperado em pessoal_aniversariantes: {e}")
        return redirect(url_for('pessoal_module'))

# $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
# $  MÓDULO PESSOAL - WELCOME  $
# $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

# --- ROTAS DO MÓDULO PESSOAL (HUB) ---
@app.route('/pessoal')
@login_required
def pessoal_module(): # Este é o ENDPOINT 'pessoal_module'
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o Módulo Pessoal.', 'warning')
        return redirect(url_for('welcome'))
    
    return render_template('pessoal/pessoal_welcome.html', user=current_user)


# --- ROTAS DO SUBMÓDULO PESSOAL: FUNCIONÁRIOS ---
@app.route('/pessoal/funcionarios')
@login_required
def funcionarios_module(): # Este é o ENDPOINT 'funcionarios_module'
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Funcionários.', 'warning')
        return redirect(url_for('welcome'))

    search_matricula = request.args.get('matricula')
    search_nome = request.args.get('nome')
    search_status = request.args.get('status')
    search_cargo_id = request.args.get('cargo_id')

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base) # NOVO MANAGER
            
            funcionarios = pessoal_manager.get_all_funcionarios(
                search_matricula=search_matricula,
                search_nome=search_nome,
                search_status=search_status,
                search_cargo_id=search_cargo_id
            )
            
            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']

        return render_template(
            'pessoal/funcionarios/funcionarios_module.html',
            user=current_user,
            funcionarios=funcionarios,
            all_cargos=all_cargos,
            status_options=status_options,
            selected_matricula=search_matricula,
            selected_nome=search_nome,
            selected_status=search_status,
            selected_cargo_id=int(search_cargo_id) if search_cargo_id else None
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar funcionários: {e}", 'danger')
        print(f"Erro de banco de dados em funcionarios_module: {e}")
        return redirect(url_for('pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar funcionários: {e}", 'danger')
        print(f"Erro inesperado em funcionarios_module: {e}")
        return redirect(url_for('pessoal_module'))

@app.route('/pessoal/funcionarios/add', methods=['GET', 'POST'])
@login_required
def add_funcionario():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar funcionários.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)

            if request.method == 'POST':
                # --- Dados de Funcionário Principal (Tabela 'funcionarios') ---
                matricula = request.form['matricula'].strip()
                nome_completo = request.form['nome_completo'].strip()
                data_admissao_str = request.form['data_admissao'].strip()
                id_cargos = int(request.form['id_cargos'])
                id_niveis = int(request.form['id_niveis'])
                status = request.form['status'].strip()

                # --- Dados Pessoais e Documentos (Nova Tabela 'funcionarios_documentos') ---
                data_nascimento_str = request.form.get('data_nascimento', '').strip()
                estado_civil = request.form.get('estado_civil', '').strip()
                nacionalidade = request.form.get('nacionalidade', '').strip()
                naturalidade = request.form.get('naturalidade', '').strip() # NOVO: Naturalidade
                genero = request.form.get('genero', '').strip()

                rg_numero = request.form.get('rg_numero', '').strip()
                rg_orgao_emissor = request.form.get('rg_orgao_emissor', '').strip()
                rg_uf_emissor = request.form.get('rg_uf_emissor', '').strip()
                rg_data_emissao_str = request.form.get('rg_data_emissao', '').strip()

                cpf_numero = request.form.get('cpf_numero', '').strip()

                ctps_numero = request.form.get('ctps_numero', '').strip()
                ctps_serie = request.form.get('ctps_serie', '').strip()

                pispasep = request.form.get('pispasep', '').strip()

                cnh_numero = request.form.get('cnh_numero', '').strip()
                cnh_categoria = request.form.get('cnh_categoria', '').strip()
                cnh_data_validade_str = request.form.get('cnh_data_validade', '').strip()
                cnh_orgao_emissor = request.form.get('cnh_orgao_emissor', '').strip()

                titeleitor_numero = request.form.get('titeleitor_numero', '').strip()
                titeleitor_zona = request.form.get('titeleitor_zona', '').strip()
                titeleitor_secao = request.form.get('titeleitor_secao', '').strip()
                
                observacoes_doc = request.form.get('observacoes_doc', '').strip() # NOVO: Observacoes gerais dos documentos
                link_foto = request.form.get('link_foto', '').strip() # NOVO: Link para Foto

                # --- Endereços e Contatos (Mantidos como estão, mas revisar os parâmetros) ---
                logradouro = request.form.get('logradouro', '').strip()
                numero_end = request.form.get('numero_end', '').strip()
                complemento = request.form.get('complemento', '').strip()
                bairro = request.form.get('bairro', '').strip()
                cidade = request.form.get('cidade', '').strip()
                estado_end = request.form.get('estado_end', '').strip()
                cep = request.form.get('cep', '').strip()

                tel_principal = request.form.get('tel_principal', '').strip()
                email_pessoal = request.form.get('email_pessoal', '').strip()

                # --- Validação e Conversão de Datas ---
                # A função _format_date_fields agora lida com strings para objetos date.
                # No entanto, para validação antes de chamar o manager, é bom converter
                # e tratar erros de formato aqui.
                data_admissao = None
                if data_admissao_str:
                    try:
                        data_admissao = datetime.strptime(data_admissao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Admissão inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template( # Retorna para o formulário com dados preenchidos
                            'pessoal/funcionarios/add_funcionario.html',
                            user=current_user,
                            all_cargos=pessoal_manager.get_all_cargos_for_dropdown(),
                            all_niveis=pessoal_manager.get_all_niveis_for_dropdown(),
                            status_options=['Ativo', 'Inativo', 'Ferias', 'Afastado'],
                            estado_civil_options=['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel'],
                            genero_options=['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar'],
                            form_data=request.form.to_dict() # Passa todos os dados do formulário de volta
                        )
                
                data_nascimento = None
                if data_nascimento_str:
                    try:
                        data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Nascimento inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template(
                            'pessoal/funcionarios/add_funcionario.html',
                            user=current_user, all_cargos=pessoal_manager.get_all_cargos_for_dropdown(),
                            all_niveis=pessoal_manager.get_all_niveis_for_dropdown(), status_options=['Ativo', 'Inativo', 'Ferias', 'Afastado'],
                            estado_civil_options=['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel'],
                            genero_options=['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar'],
                            form_data=request.form.to_dict()
                        )

                rg_data_emissao = None
                if rg_data_emissao_str:
                    try:
                        rg_data_emissao = datetime.strptime(rg_data_emissao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Emissão do RG inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template(
                            'pessoal/funcionarios/add_funcionario.html',
                            user=current_user, all_cargos=pessoal_manager.get_all_cargos_for_dropdown(),
                            all_niveis=pessoal_manager.get_all_niveis_for_dropdown(), status_options=['Ativo', 'Inativo', 'Ferias', 'Afastado'],
                            estado_civil_options=['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel'],
                            genero_options=['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar'],
                            form_data=request.form.to_dict()
                        )
                
                cnh_data_validade = None
                if cnh_data_validade_str:
                    try:
                        cnh_data_validade = datetime.strptime(cnh_data_validade_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Validade da CNH inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template(
                            'pessoal/funcionarios/add_funcionario.html',
                            user=current_user, all_cargos=pessoal_manager.get_all_cargos_for_dropdown(),
                            all_niveis=pessoal_manager.get_all_niveis_for_dropdown(), status_options=['Ativo', 'Inativo', 'Ferias', 'Afastado'],
                            estado_civil_options=['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel'],
                            genero_options=['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar'],
                            form_data=request.form.to_dict()
                        )

                # --- Validações Adicionais ---
                if not all([matricula, nome_completo, data_admissao, id_cargos, id_niveis, status]):
                    flash('Campos principais (Matrícula, Nome, Data de Admissão, Cargo, Nível, Status) são obrigatórios.', 'danger')
                    # Prepara e retorna o template com os dados do form para não perder
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
                    estado_civil_options = ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel']
                    genero_options = ['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar']
                    return render_template(
                        'pessoal/funcionarios/add_funcionario.html',
                        user=current_user, all_cargos=all_cargos, all_niveis=all_niveis,
                        status_options=status_options, estado_civil_options=estado_civil_options,
                        genero_options=genero_options, form_data=request.form.to_dict()
                    )
                
                # NOVO: Validação para CPF
                if not cpf_numero:
                    flash('O campo CPF é obrigatório e deve ser preenchido.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
                    estado_civil_options = ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel']
                    genero_options = ['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar']
                    return render_template(
                        'pessoal/funcionarios/add_funcionario.html',
                        user=current_user, all_cargos=all_cargos, all_niveis=all_niveis,
                        status_options=status_options, estado_civil_options=estado_civil_options,
                        genero_options=genero_options, form_data=request.form.to_dict()
                    )
                
                # Verificar unicidade da matrícula
                if pessoal_manager.get_funcionario_by_matricula(matricula): # Este método agora traz todos os dados, mas ainda serve para verificar existência
                    flash('Matrícula já existe. Por favor, use uma matrícula única.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
                    estado_civil_options = ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel']
                    genero_options = ['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar']
                    return render_template(
                        'pessoal/funcionarios/add_funcionario.html',
                        user=current_user, all_cargos=all_cargos, all_niveis=all_niveis,
                        status_options=status_options, estado_civil_options=estado_civil_options,
                        genero_options=genero_options, form_data=request.form.to_dict()
                    )

                # --- SALVAR NO BANCO DE DADOS ---
                # 1. Salvar dados principais do funcionário
                success_func = pessoal_manager.add_funcionario(
                    matricula, nome_completo, data_admissao, id_cargos, id_niveis, status
                )
                
                if success_func:
                    # 2. Salvar dados pessoais e de documentos (nova estrutura)
                    success_docs = pessoal_manager.save_funcionario_dados_pessoais_documentos(
                        matricula, data_nascimento, estado_civil, nacionalidade, naturalidade, genero,
                        rg_numero, rg_orgao_emissor, rg_uf_emissor, rg_data_emissao,
                        cpf_numero,
                        ctps_numero, ctps_serie,
                        pispasep,
                        cnh_numero, cnh_categoria, cnh_data_validade, cnh_orgao_emissor,
                        titeleitor_numero, titeleitor_zona, titeleitor_secao,
                        observacoes_doc, link_foto
                    )

                    # 3. Adicionar dados de endereço (apenas residencial por enquanto)
                    if any([logradouro, numero_end, bairro, cidade, estado_end, cep]):
                        pessoal_manager.add_funcionario_endereco(
                            matricula, 'Residencial', logradouro, numero_end, complemento, bairro, cidade, estado_end, cep
                        )

                    # 4. Adicionar dados de contato
                    if tel_principal:
                        pessoal_manager.add_funcionario_contato(matricula, 'Telefone Principal', tel_principal)
                    if email_pessoal:
                        pessoal_manager.add_funcionario_contato(matricula, 'Email Pessoal', email_pessoal)

                    flash('Funcionário adicionado com sucesso!', 'success')
                    return redirect(url_for('funcionarios_module'))
                else:
                    flash('Erro ao adicionar funcionário. Verifique os dados e tente novamente.', 'danger')
            
            # --- GET request (carregar dropdowns e sugerir matrícula) ---
            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
            estado_civil_options = ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel']
            genero_options = ['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar']
            
            next_matricula = pessoal_manager.generate_next_matricula()

            return render_template(
                'pessoal/funcionarios/add_funcionario.html',
                user=current_user,
                all_cargos=all_cargos,
                all_niveis=all_niveis,
                status_options=status_options,
                estado_civil_options=estado_civil_options,
                genero_options=genero_options,
                next_matricula=next_matricula,
                form_data={} # Garante que form_data está vazio para o GET inicial
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_funcionario: {e}")
        return redirect(url_for('funcionarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_funcionario: {e}")
        return redirect(url_for('funcionarios_module'))

@app.route('/pessoal/funcionarios/edit/<string:matricula>', methods=['GET', 'POST'])
@login_required
def edit_funcionario(matricula):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            # Sempre obtenha os dados do funcionário principal e seus relacionamentos consolidados
            # Este método agora já traz os dados da nova tabela 'funcionarios_documentos'
            funcionario = pessoal_manager.get_funcionario_by_matricula(matricula)
            
            if not funcionario:
                flash('Funcionário não encontrado.', 'danger')
                return redirect(url_for('funcionarios_module'))

            # Carrega as opções para os dropdowns, independentemente do método (GET/POST)
            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
            estado_civil_options = ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel']
            genero_options = ['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar']

            if request.method == 'POST':
                # No POST, os dados vêm do formulário (request.form)
                form_data_received = request.form.to_dict() # Coleta todos os dados do formulário

                # --- Validações e Coleta de Dados para Update ---
                new_matricula = form_data_received.get('matricula', '').strip()
                nome_completo = form_data_received.get('nome_completo', '').strip()
                data_admissao_str = form_data_received.get('data_admissao', '').strip()
                
                # Conversão de Data de Admissão
                data_admissao = None
                if data_admissao_str:
                    try:
                        data_admissao = datetime.strptime(data_admissao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Admissão inválido. Use AAAA-MM-DD.', 'danger')
                        # Retorna ao formulário com os dados preenchidos para correção
                        return render_template(
                            'pessoal/funcionarios/edit_funcionario.html',
                            user=current_user, funcionario=form_data_received, # Passa o form_data para pré-preencher
                            all_cargos=all_cargos, all_niveis=all_niveis,
                            status_options=status_options, estado_civil_options=estado_civil_options,
                            genero_options=genero_options
                        )

                # Tratamento para ID_Cargos e ID_Niveis
                try:
                    id_cargos = int(form_data_received.get('id_cargos', 0))
                except ValueError:
                    id_cargos = 0
                try:
                    id_niveis = int(form_data_received.get('id_niveis', 0))
                except ValueError:
                    id_niveis = 0

                status = form_data_received.get('status', '').strip()

                # NOVO: Coleta de Dados Pessoais e Documentos (da nova estrutura)
                data_nascimento_str = form_data_received.get('data_nascimento', '').strip()
                estado_civil = form_data_received.get('estado_civil', '').strip()
                nacionalidade = form_data_received.get('nacionalidade', '').strip()
                naturalidade = form_data_received.get('naturalidade', '').strip()
                genero = form_data_received.get('genero', '').strip()

                rg_numero = form_data_received.get('rg_numero', '').strip()
                rg_orgao_emissor = form_data_received.get('rg_orgao_emissor', '').strip()
                rg_uf_emissor = form_data_received.get('rg_uf_emissor', '').strip()
                rg_data_emissao_str = form_data_received.get('rg_data_emissao', '').strip()

                cpf_numero = form_data_received.get('cpf_numero', '').strip()

                ctps_numero = form_data_received.get('ctps_numero', '').strip()
                ctps_serie = form_data_received.get('ctps_serie', '').strip()

                pispasep = form_data_received.get('pispasep', '').strip()

                cnh_numero = form_data_received.get('cnh_numero', '').strip()
                cnh_categoria = form_data_received.get('cnh_categoria', '').strip()
                cnh_data_validade_str = form_data_received.get('cnh_data_validade', '').strip()
                cnh_orgao_emissor = form_data_received.get('cnh_orgao_emissor', '').strip()

                titeleitor_numero = form_data_received.get('titeleitor_numero', '').strip()
                titeleitor_zona = form_data_received.get('titeleitor_zona', '').strip()
                titeleitor_secao = form_data_received.get('titeleitor_secao', '').strip()
                
                observacoes_doc = form_data_received.get('observacoes_doc', '').strip()
                link_foto = form_data_received.get('link_foto', '').strip()

                # Conversão de Datas para Dados Pessoais/Documentos
                data_nascimento = None
                if data_nascimento_str:
                    try:
                        data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Nascimento inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template(
                            'pessoal/funcionarios/edit_funcionario.html',
                            user=current_user, funcionario=form_data_received, 
                            all_cargos=all_cargos, all_niveis=all_niveis,
                            status_options=status_options, estado_civil_options=estado_civil_options,
                            genero_options=genero_options
                        )

                rg_data_emissao = None
                if rg_data_emissao_str:
                    try:
                        rg_data_emissao = datetime.strptime(rg_data_emissao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Emissão do RG inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template(
                            'pessoal/funcionarios/edit_funcionario.html',
                            user=current_user, funcionario=form_data_received, 
                            all_cargos=all_cargos, all_niveis=all_niveis,
                            status_options=status_options, estado_civil_options=estado_civil_options,
                            genero_options=genero_options
                        )
                
                cnh_data_validade = None
                if cnh_data_validade_str:
                    try:
                        cnh_data_validade = datetime.strptime(cnh_data_validade_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Validade da CNH inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template(
                            'pessoal/funcionarios/edit_funcionario.html',
                            user=current_user, funcionario=form_data_received, 
                            all_cargos=all_cargos, all_niveis=all_niveis,
                            status_options=status_options, estado_civil_options=estado_civil_options,
                            genero_options=genero_options
                        )

                # --- Validação de Campos Obrigatórios ---
                is_valid = True
                if not all([new_matricula, nome_completo, data_admissao, id_cargos, id_niveis, status]):
                    flash('Campos principais (Matrícula, Nome, Data de Admissão, Cargo, Nível, Status) são obrigatórios.', 'danger')
                    is_valid = False
                
                # Validação para CPF (como fizemos no add)
                if not cpf_numero:
                    flash('O campo CPF é obrigatório e deve ser preenchido.', 'danger')
                    is_valid = False

                # Verificar unicidade da matrícula (se a matrícula foi alterada)
                if new_matricula != matricula: # Se a matrícula foi alterada
                    existing_funcionario_by_new_matricula = pessoal_manager.get_funcionario_by_matricula(new_matricula)
                    if existing_funcionario_by_new_matricula:
                        flash('Nova matrícula já existe. Por favor, use uma matrícula única.', 'danger')
                        is_valid = False

                if not is_valid:
                    # Se houver erros de validação, re-renderiza o formulário com as mensagens e dados
                    return render_template(
                        'pessoal/funcionarios/edit_funcionario.html',
                        user=current_user, funcionario=form_data_received, 
                        all_cargos=all_cargos, all_niveis=all_niveis,
                        status_options=status_options, estado_civil_options=estado_civil_options,
                        genero_options=genero_options
                    )

                # --- SALVAR NO BANCO DE DADOS ---
                # 1. Atualizar dados principais do funcionário
                success_func = pessoal_manager.update_funcionario(
                    matricula, new_matricula, nome_completo, data_admissao, id_cargos, id_niveis, status
                )
                
                if success_func:
                    # 2. Salvar/Atualizar dados pessoais e de documentos (nova estrutura)
                    success_docs = pessoal_manager.save_funcionario_dados_pessoais_documentos(
                        new_matricula, # Usa a nova matrícula para salvar/atualizar
                        data_nascimento, estado_civil, nacionalidade, naturalidade, genero,
                        rg_numero, rg_orgao_emissor, rg_uf_emissor, rg_data_emissao,
                        cpf_numero,
                        ctps_numero, ctps_serie,
                        pispasep,
                        cnh_numero, cnh_categoria, cnh_data_validade, cnh_orgao_emissor,
                        titeleitor_numero, titeleitor_zona, titeleitor_secao,
                        observacoes_doc, link_foto
                    )

                    # 3. Atualizar dados de endereço (se eles forem modificados ou inseridos)
                    logradouro = form_data_received.get('logradouro', '').strip()
                    numero_end = form_data_received.get('numero_end', '').strip()
                    complemento = form_data_received.get('complemento', '').strip()
                    bairro = form_data_received.get('bairro', '').strip()
                    cidade = form_data_received.get('cidade', '').strip()
                    estado_end = form_data_received.get('estado_end', '').strip()
                    cep = form_data_received.get('cep', '').strip()
                    pessoal_manager.update_or_add_funcionario_endereco(
                        new_matricula, 'Residencial', logradouro, numero_end, complemento, bairro, cidade, estado_end, cep
                    )

                    # 4. Atualizar dados de contato
                    tel_principal = form_data_received.get('tel_principal', '').strip()
                    email_pessoal = form_data_received.get('email_pessoal', '').strip()
                    pessoal_manager.update_or_add_funcionario_contato(
                        new_matricula, 'Telefone Principal', tel_principal
                    )
                    pessoal_manager.update_or_add_funcionario_contato(
                        new_matricula, 'Email Pessoal', email_pessoal
                    )

                    flash('Funcionário atualizado com sucesso!', 'success')
                    return redirect(url_for('funcionarios_module'))
                else:
                    flash('Erro ao atualizar funcionário. Verifique os dados e tente novamente.', 'danger')
            
            else: # GET request
                # Prepara os dados para exibição inicial no formulário GET
                # O objeto 'funcionario' já contém todos os dados de funcionarios_documentos
                data_to_pass_to_template = funcionario.copy() 

                # Buscar endereços e contatos separadamente para pré-preenchimento
                funcionario_enderecos = pessoal_manager.get_funcionario_enderecos_by_matricula(matricula)
                funcionario_contatos = pessoal_manager.get_funcionario_contatos_by_matricula(matricula)

                # Mapear e formatar dados de Endereços para o template
                if funcionario_enderecos:
                    res_endereco = next((end for end in funcionario_enderecos if end.get('Tipo_Endereco') == 'Residencial'), None)
                    if not res_endereco and funcionario_enderecos:
                        res_endereco = funcionario_enderecos[0]
                    if res_endereco:
                        data_to_pass_to_template['logradouro'] = res_endereco.get('Logradouro', '')
                        data_to_pass_to_template['numero_end'] = res_endereco.get('Numero', '')
                        data_to_pass_to_template['complemento'] = res_endereco.get('Complemento', '')
                        data_to_pass_to_template['bairro'] = res_endereco.get('Bairro', '')
                        data_to_pass_to_template['cidade'] = res_endereco.get('Cidade', '')
                        data_to_pass_to_template['estado_end'] = res_endereco.get('Estado', '')
                        data_to_pass_to_template['cep'] = res_endereco.get('Cep', '')

                # Mapear e formatar dados de Contatos para o template
                if funcionario_contatos:
                    tel_principal = next((cont for cont in funcionario_contatos if cont.get('Tipo_Contato') == 'Telefone Principal'), None)
                    if tel_principal:
                        data_to_pass_to_template['tel_principal'] = tel_principal.get('Valor_Contato', '')
                    email_pessoal = next((cont for cont in funcionario_contatos if cont.get('Tipo_Contato') == 'Email Pessoal'), None)
                    if email_pessoal:
                        data_to_pass_to_template['email_pessoal'] = email_pessoal.get('Valor_Contato', '')
                
                # Formatar datas para o input type="date" para o GET request
                data_to_pass_to_template['Data_Admissao'] = data_to_pass_to_template['Data_Admissao'].strftime('%Y-%m-%d') if isinstance(data_to_pass_to_template.get('Data_Admissao'), date) else ''
                data_to_pass_to_template['Data_Nascimento'] = data_to_pass_to_template['Data_Nascimento'].strftime('%Y-%m-%d') if isinstance(data_to_pass_to_template.get('Data_Nascimento'), date) else ''
                data_to_pass_to_template['Rg_DataEmissao'] = data_to_pass_to_template['Rg_DataEmissao'].strftime('%Y-%m-%d') if isinstance(data_to_pass_to_template.get('Rg_DataEmissao'), date) else ''
                data_to_pass_to_template['Cnh_DataValidade'] = data_to_pass_to_template['Cnh_DataValidade'].strftime('%Y-%m-%d') if isinstance(data_to_pass_to_template.get('Cnh_DataValidade'), date) else ''
                
                # Renderizar o template de edição com os dados
                return render_template(
                    'pessoal/funcionarios/edit_funcionario.html',
                    user=current_user,
                    funcionario=data_to_pass_to_template, # Passa todos os dados para o template
                    all_cargos=all_cargos,
                    all_niveis=all_niveis,
                    status_options=status_options,
                    estado_civil_options=estado_civil_options,
                    genero_options=genero_options
                )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_funcionario: {e}")
        return redirect(url_for('funcionarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_funcionario: {e}")
        return redirect(url_for('funcionarios_module'))

@app.route('/pessoal/funcionarios/delete/<string:matricula>', methods=['POST'])
@login_required
def delete_funcionario(matricula):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base) # NOVO MANAGER
            success = pessoal_manager.delete_funcionario(matricula)
            if success:
                flash('Funcionário excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir funcionário. Verifique se ele existe.', 'danger')
        return redirect(url_for('funcionarios_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_funcionario: {e}")
        return redirect(url_for('funcionarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_funcionario: {e}")
        return redirect(url_for('funcionarios_module'))


@app.route('/pessoal/funcionarios/details/<string:matricula>')
@login_required
def funcionario_details(matricula):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de funcionários.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            # get_funcionario_by_matricula agora traz TUDO (incluindo dados de 'funcionarios_documentos')
            funcionario = pessoal_manager.get_funcionario_by_matricula(matricula)
            
            if not funcionario:
                flash('Funcionário não encontrado.', 'danger')
                return redirect(url_for('funcionarios_module'))

            # Endereços e Contatos ainda são tabelas separadas, então mantemos a busca individual
            funcionario_enderecos = pessoal_manager.get_funcionario_enderecos_by_matricula(matricula)
            funcionario_contatos = pessoal_manager.get_funcionario_contatos_by_matricula(matricula)

        return render_template(
            'pessoal/funcionarios/funcionario_details.html',
            user=current_user,
            funcionario=funcionario, # Este objeto 'funcionario' agora contém todos os dados
            funcionario_enderecos=funcionario_enderecos,
            funcionario_contatos=funcionario_contatos
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em funcionario_details: {e}")
        return redirect(url_for('funcionarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em funcionario_details: {e}")
        return redirect(url_for('funcionarios_module'))


@app.route('/pessoal/funcionarios/export/excel')
@login_required
def export_funcionarios_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base) # NOVO MANAGER
            
            search_matricula = request.args.get('matricula')
            search_nome = request.args.get('nome')
            search_status = request.args.get('status')
            search_cargo_id = request.args.get('cargo_id')

            funcionarios_data = pessoal_manager.get_all_funcionarios_completo( # NOVO MÉTODO PARA EXPORTAÇÃO COMPLETA
                search_matricula=search_matricula,
                search_nome=search_nome,
                search_status=search_status,
                search_cargo_id=search_cargo_id
            )

            if not funcionarios_data:
                flash('Nenhum funcionário encontrado para exportar.', 'info')
                return redirect(url_for('funcionarios_module'))

            df = pd.DataFrame(funcionarios_data)

            # Renomeie colunas para serem mais amigáveis no Excel
            df = df.rename(columns={
                'Matricula': 'Matrícula',
                'Nome_Completo': 'Nome Completo',
                'Data_Admissao': 'Data de Admissão',
                'Nome_Cargo': 'Cargo',
                'Nome_Nivel': 'Nível',
                'Status': 'Status',
                # Novas colunas de documentos, endereços e contatos
                'Rg': 'RG', 'Cpf': 'CPF', 'Data_Nascimento': 'Data de Nascimento',
                'Ctps_Numero': 'CTPS Nº', 'Ctps_Serie': 'CTPS Série',
                'Pis_Pasep': 'PIS/PASEP', 'Cnh_Numero': 'CNH Nº',
                'Cnh_Categoria': 'CNH Categoria', 'Titulo_Eleitor_Numero': 'Título Eleitor Nº',
                'Titulo_Eleitor_Zona': 'Título Eleitor Zona', 'Titulo_Eleitor_Secao': 'Título Eleitor Seção',
                'Estado_Civil': 'Estado Civil', 'Nacionalidade': 'Nacionalidade', 'Genero': 'Gênero',
                'Endereco_Residencial': 'Endereço Residencial', 'Numero_Endereco': 'Número Endereço',
                'Complemento_Endereco': 'Complemento Endereço', 'Bairro_Endereco': 'Bairro Endereço',
                'Cidade_Endereco': 'Cidade Endereço', 'Estado_Endereco': 'Estado Endereço',
                'Cep_Endereco': 'CEP Endereço',
                'Telefone_Principal': 'Telefone Principal', 'Email_Pessoal': 'Email Pessoal',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
            ordered_columns = [
                'Matrícula', 'Nome Completo', 'Status', 'Cargo', 'Nível',
                'Data de Admissão', 'RG', 'CPF', 'Data de Nascimento',
                'Endereço Residencial', 'Número Endereço', 'Complemento Endereço', 'Bairro Endereço',
                'Cidade Endereço', 'Estado Endereço', 'CEP Endereço',
                'Telefone Principal', 'Email Pessoal',
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
                download_name='relatorio_funcionarios.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar funcionários para Excel: {e}", 'danger')
        print(f"Erro ao exportar funcionários Excel: {e}")
        return redirect(url_for('funcionarios_module'))

# --- ROTAS DO SUBMÓDULO PESSOAL: CARGOS ---

@app.route('/pessoal/cargos')
@login_required
def cargos_module():
    if not current_user.can_access_module('Pessoal'): # Ou uma permissão mais específica para cargos
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Cargos.', 'warning')
        return redirect(url_for('welcome'))

    search_nome = request.args.get('nome_cargo')

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            cargos = pessoal_manager.get_all_cargos(search_nome=search_nome)

        return render_template(
            'pessoal/cargos/cargos_module.html',
            user=current_user,
            cargos=cargos,
            selected_nome=search_nome
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar cargos: {e}", 'danger')
        print(f"Erro de banco de dados em cargos_module: {e}")
        return redirect(url_for('pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar cargos: {e}", 'danger')
        print(f"Erro inesperado em cargos_module: {e}")
        return redirect(url_for('pessoal_module'))


@app.route('/pessoal/cargos/add', methods=['GET', 'POST'])
@login_required
def add_cargo():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            if request.method == 'POST':
                nome_cargo = request.form['nome_cargo'].strip()
                descricao_cargo = request.form.get('descricao_cargo', '').strip()
                cbo = request.form.get('cbo', '').strip()

                if not nome_cargo:
                    flash('O nome do cargo é obrigatório.', 'danger')
                    return render_template(
                        'pessoal/cargos/add_cargo.html',
                        user=current_user,
                        form_data=request.form
                    )
                
                if pessoal_manager.get_cargo_by_nome(nome_cargo):
                    flash('Já existe um cargo com este nome.', 'danger')
                    return render_template(
                        'pessoal/cargos/add_cargo.html',
                        user=current_user,
                        form_data=request.form
                    )

                success = pessoal_manager.add_cargo(nome_cargo, descricao_cargo, cbo)
                if success:
                    flash('Cargo adicionado com sucesso!', 'success')
                    return redirect(url_for('cargos_module'))
                else:
                    flash('Erro ao adicionar cargo. Verifique os dados e tente novamente.', 'danger')
            
            # GET request
            return render_template(
                'pessoal/cargos/add_cargo.html',
                user=current_user,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_cargo: {e}")
        return redirect(url_for('cargos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_cargo: {e}")
        return redirect(url_for('cargos_module'))


@app.route('/pessoal/cargos/edit/<int:cargo_id>', methods=['GET', 'POST'])
@login_required
def edit_cargo(cargo_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            cargo = pessoal_manager.get_cargo_by_id(cargo_id)

            if not cargo:
                flash('Cargo não encontrado.', 'danger')
                return redirect(url_for('cargos_module'))

            if request.method == 'POST':
                nome_cargo = request.form['nome_cargo'].strip()
                descricao_cargo = request.form.get('descricao_cargo', '').strip()
                cbo = request.form.get('cbo', '').strip()

                if not nome_cargo:
                    flash('O nome do cargo é obrigatório.', 'danger')
                    return render_template(
                        'pessoal/cargos/edit_cargo.html',
                        user=current_user,
                        cargo=cargo,
                        form_data=request.form
                    )
                
                existing_cargo = pessoal_manager.get_cargo_by_nome(nome_cargo)
                if existing_cargo and existing_cargo['ID_Cargos'] != cargo_id:
                    flash('Já existe um cargo com este nome.', 'danger')
                    return render_template(
                        'pessoal/cargos/edit_cargo.html',
                        user=current_user,
                        cargo=cargo,
                        form_data=request.form
                    )

                success = pessoal_manager.update_cargo(cargo_id, nome_cargo, descricao_cargo, cbo)
                if success:
                    flash('Cargo atualizado com sucesso!', 'success')
                    return redirect(url_for('cargos_module'))
                else:
                    flash('Erro ao atualizar cargo.', 'danger')
            
            # GET request
            return render_template(
                'pessoal/cargos/edit_cargo.html',
                user=current_user,
                cargo=cargo
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_cargo: {e}")
        return redirect(url_for('cargos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_cargo: {e}")
        return redirect(url_for('cargos_module'))


@app.route('/pessoal/cargos/delete/<int:cargo_id>', methods=['POST'])
@login_required
def delete_cargo(cargo_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_cargo(cargo_id)
            if success:
                flash('Cargo excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir cargo. Certifique-se de que não há funcionários associados a ele.', 'danger')
        return redirect(url_for('cargos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_cargo: {e}")
        return redirect(url_for('cargos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_cargo: {e}")
        return redirect(url_for('cargos_module'))


@app.route('/pessoal/cargos/details/<int:cargo_id>')
@login_required
def cargo_details(cargo_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de cargos.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            cargo = pessoal_manager.get_cargo_by_id(cargo_id)

            if not cargo:
                flash('Cargo não encontrado.', 'danger')
                return redirect(url_for('cargos_module'))

        return render_template(
            'pessoal/cargos/cargo_details.html',
            user=current_user,
            cargo=cargo
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em cargo_details: {e}")
        return redirect(url_for('cargos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em cargo_details: {e}")
        return redirect(url_for('cargos_module'))


@app.route('/pessoal/cargos/export/excel')
@login_required
def export_cargos_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            search_nome = request.args.get('nome_cargo')
            cargos_data = pessoal_manager.get_all_cargos(search_nome=search_nome)

            if not cargos_data:
                flash('Nenhum cargo encontrado para exportar.', 'info')
                return redirect(url_for('cargos_module'))

            df = pd.DataFrame(cargos_data)
            df = df.rename(columns={
                'ID_Cargos': 'ID Cargo',
                'Nome_Cargo': 'Nome do Cargo',
                'Descricao_Cargo': 'Descrição do Cargo',
                'Cbo': 'CBO',
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
                download_name='relatorio_cargos.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar cargos para Excel: {e}", 'danger')
        print(f"Erro ao exportar cargos Excel: {e}")
        return redirect(url_for('cargos_module'))


# --- ROTAS DO SUBMÓDULO PESSOAL: NÍVEIS ---

@app.route('/pessoal/niveis')
@login_required
def niveis_module():
    if not current_user.can_access_module('Pessoal'): # Ou uma permissão mais específica para níveis
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Níveis.', 'warning')
        return redirect(url_for('welcome'))

    search_nome = request.args.get('nome_nivel')

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            niveis = pessoal_manager.get_all_niveis(search_nome=search_nome)

        return render_template(
            'pessoal/niveis/niveis_module.html',
            user=current_user,
            niveis=niveis,
            selected_nome=search_nome
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar níveis: {e}", 'danger')
        print(f"Erro de banco de dados em niveis_module: {e}")
        return redirect(url_for('pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar níveis: {e}", 'danger')
        print(f"Erro inesperado em niveis_module: {e}")
        return redirect(url_for('pessoal_module'))


@app.route('/pessoal/niveis/add', methods=['GET', 'POST'])
@login_required
def add_nivel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            if request.method == 'POST':
                nome_nivel = request.form['nome_nivel'].strip()
                descricao = request.form.get('descricao', '').strip()

                if not nome_nivel:
                    flash('O nome do nível é obrigatório.', 'danger')
                    return render_template(
                        'pessoal/niveis/add_nivel.html',
                        user=current_user,
                        form_data=request.form
                    )
                
                if pessoal_manager.get_nivel_by_nome(nome_nivel):
                    flash('Já existe um nível com este nome.', 'danger')
                    return render_template(
                        'pessoal/niveis/add_nivel.html',
                        user=current_user,
                        form_data=request.form
                    )

                success = pessoal_manager.add_nivel(nome_nivel, descricao)
                if success:
                    flash('Nível adicionado com sucesso!', 'success')
                    return redirect(url_for('niveis_module'))
                else:
                    flash('Erro ao adicionar nível. Verifique os dados e tente novamente.', 'danger')
            
            # GET request
            return render_template(
                'pessoal/niveis/add_nivel.html',
                user=current_user,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_nivel: {e}")
        return redirect(url_for('niveis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_nivel: {e}")
        return redirect(url_for('niveis_module'))


@app.route('/pessoal/niveis/edit/<int:nivel_id>', methods=['GET', 'POST'])
@login_required
def edit_nivel(nivel_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            nivel = pessoal_manager.get_nivel_by_id(nivel_id)

            if not nivel:
                flash('Nível não encontrado.', 'danger')
                return redirect(url_for('niveis_module'))

            if request.method == 'POST':
                nome_nivel = request.form['nome_nivel'].strip()
                descricao = request.form.get('descricao', '').strip()

                if not nome_nivel:
                    flash('O nome do nível é obrigatório.', 'danger')
                    return render_template(
                        'pessoal/niveis/edit_nivel.html',
                        user=current_user,
                        nivel=nivel,
                        form_data=request.form
                    )
                
                existing_nivel = pessoal_manager.get_nivel_by_nome(nome_nivel)
                if existing_nivel and existing_nivel['ID_Niveis'] != nivel_id:
                    flash('Já existe um nível com este nome.', 'danger')
                    return render_template(
                        'pessoal/niveis/edit_nivel.html',
                        user=current_user,
                        nivel=nivel,
                        form_data=request.form
                    )

                success = pessoal_manager.update_nivel(nivel_id, nome_nivel, descricao)
                if success:
                    flash('Nível atualizado com sucesso!', 'success')
                    return redirect(url_for('niveis_module'))
                else:
                    flash('Erro ao atualizar nível.', 'danger')
            
            # GET request
            return render_template(
                'pessoal/niveis/edit_nivel.html',
                user=current_user,
                nivel=nivel
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_nivel: {e}")
        return redirect(url_for('niveis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_nivel: {e}")
        return redirect(url_for('niveis_module'))


@app.route('/pessoal/niveis/delete/<int:nivel_id>', methods=['POST'])
@login_required
def delete_nivel(nivel_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_nivel(nivel_id)
            if success:
                flash('Nível excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir nível. Certifique-se de que não há funcionários associados a ele.', 'danger')
        return redirect(url_for('niveis_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_nivel: {e}")
        return redirect(url_for('niveis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_nivel: {e}")
        return redirect(url_for('niveis_module'))

@app.route('/pessoal/niveis/details/<int:nivel_id>')
@login_required
def nivel_details(nivel_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de níveis.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            nivel = pessoal_manager.get_nivel_by_id(nivel_id)

            if not nivel:
                flash('Nível não encontrado.', 'danger')
                return redirect(url_for('niveis_module'))

        return render_template(
            'pessoal/niveis/nivel_details.html',
            user=current_user,
            nivel=nivel
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em nivel_details: {e}")
        return redirect(url_for('niveis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em nivel_details: {e}")
        return redirect(url_for('niveis_module'))

@app.route('/pessoal/niveis/export/excel')
@login_required
def export_niveis_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            search_nome = request.args.get('nome_nivel')
            niveis_data = pessoal_manager.get_all_niveis(search_nome=search_nome)

            if not niveis_data:
                flash('Nenhum nível encontrado para exportar.', 'info')
                return redirect(url_for('niveis_module'))

            df = pd.DataFrame(niveis_data)
            df = df.rename(columns={
                'ID_Niveis': 'ID Nível',
                'Nome_Nivel': 'Nome do Nível',
                'Descricao': 'Descrição',
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
                download_name='relatorio_niveis.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar níveis para Excel: {e}", 'danger')
        print(f"Erro ao exportar níveis Excel: {e}")
        return redirect(url_for('niveis_module'))

# --- ROTAS DO SUBMÓDULO PESSOAL: SALÁRIOS E BENEFÍCIOS ---

@app.route('/pessoal/salarios')
@login_required
def salarios_module():
    if not current_user.can_access_module('Pessoal'): # Ou permissão específica para salários
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Salários.', 'warning')
        return redirect(url_for('welcome'))

    search_cargo_id = request.args.get('cargo_id')
    search_nivel_id = request.args.get('nivel_id')

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            salarios = pessoal_manager.get_all_salarios(
                search_cargo_id=int(search_cargo_id) if search_cargo_id else None,
                search_nivel_id=int(search_nivel_id) if search_nivel_id else None
            )
            
            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()

        return render_template(
            'pessoal/salarios/salarios_module.html',
            user=current_user,
            salarios=salarios,
            all_cargos=all_cargos,
            all_niveis=all_niveis,
            selected_cargo_id=int(search_cargo_id) if search_cargo_id else None,
            selected_nivel_id=int(search_nivel_id) if search_nivel_id else None
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Salários: {e}", 'danger')
        print(f"Erro de banco de dados em salarios_module: {e}")
        return redirect(url_for('pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Salários: {e}", 'danger')
        print(f"Erro inesperado em salarios_module: {e}")
        return redirect(url_for('pessoal_module'))


@app.route('/pessoal/salarios/add', methods=['GET', 'POST'])
@login_required
def add_salario():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            if request.method == 'POST':
                id_cargos = int(request.form['id_cargos'])
                id_niveis = int(request.form['id_niveis'])
                salario_base = float(request.form.get('salario_base', '0').replace(',', '.'))
                periculosidade = 'periculosidade' in request.form
                insalubridade = 'insalubridade' in request.form
                ajuda_de_custo = float(request.form.get('ajuda_de_custo', '0').replace(',', '.'))
                vale_refeicao = float(request.form.get('vale_refeicao', '0').replace(',', '.'))
                gratificacao = float(request.form.get('gratificacao', '0').replace(',', '.'))
                cesta_basica = 'cesta_basica' in request.form
                outros_beneficios = request.form.get('outros_beneficios', '').strip()
                data_vigencia_str = request.form.get('data_vigencia', '').strip()

                if not all([id_cargos, id_niveis, salario_base, data_vigencia_str]):
                    flash('Campos obrigatórios (Cargo, Nível, Salário Base, Data Vigência) não podem ser vazios.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    return render_template(
                        'pessoal/salarios/add_salario.html',
                        user=current_user,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=request.form
                    )
                
                try:
                    data_vigencia = datetime.strptime(data_vigencia_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Vigência inválido. Use AAAA-MM-DD.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    return render_template(
                        'pessoal/salarios/add_salario.html',
                        user=current_user,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=request.form
                    )
                
                if pessoal_manager.get_salario_by_cargo_nivel_vigencia(id_cargos, id_niveis, data_vigencia):
                    flash('Já existe um pacote salarial para esta combinação de Cargo, Nível e Data de Vigência.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    return render_template(
                        'pessoal/salarios/add_salario.html',
                        user=current_user,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=request.form
                    )

                success = pessoal_manager.add_salario(
                    id_cargos, id_niveis, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia
                )
                if success:
                    flash('Pacote salarial adicionado com sucesso!', 'success')
                    return redirect(url_for('salarios_module'))
                else:
                    flash('Erro ao adicionar pacote salarial. Verifique os dados e tente novamente.', 'danger')
            
            # GET request
            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                
            return render_template(
                'pessoal/salarios/add_salario.html',
                user=current_user,
                all_cargos=all_cargos,
                all_niveis=all_niveis,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_salario: {e}")
        return redirect(url_for('salarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_salario: {e}")
        return redirect(url_for('salarios_module'))


@app.route('/pessoal/salarios/edit/<int:salario_id>', methods=['GET', 'POST'])
@login_required
def edit_salario(salario_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            salario = pessoal_manager.get_salario_by_id(salario_id)

            if not salario:
                flash('Pacote salarial não encontrado.', 'danger')
                return redirect(url_for('salarios_module'))

            if request.method == 'POST':
                id_cargos = int(request.form['id_cargos'])
                id_niveis = int(request.form['id_niveis'])
                salario_base = float(request.form.get('salario_base', '0').replace(',', '.'))
                periculosidade = 'periculosidade' in request.form
                insalubridade = 'insalubridade' in request.form
                ajuda_de_custo = float(request.form.get('ajuda_de_custo', '0').replace(',', '.'))
                vale_refeicao = float(request.form.get('vale_refeicao', '0').replace(',', '.'))
                gratificacao = float(request.form.get('gratificacao', '0').replace(',', '.'))
                cesta_basica = 'cesta_basica' in request.form
                outros_beneficios = request.form.get('outros_beneficios', '').strip()
                data_vigencia_str = request.form.get('data_vigencia', '').strip()

                if not all([id_cargos, id_niveis, salario_base, data_vigencia_str]):
                    flash('Campos obrigatórios (Cargo, Nível, Salário Base, Data Vigência) não podem ser vazios.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    return render_template(
                        'pessoal/salarios/edit_salario.html',
                        user=current_user,
                        salario=salario,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=request.form
                    )
                
                try:
                    data_vigencia = datetime.strptime(data_vigencia_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Vigência inválido. Use AAAA-MM-DD.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    return render_template(
                        'pessoal/salarios/edit_salario.html',
                        user=current_user,
                        salario=salario,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=request.form
                    )
                
                existing_salario = pessoal_manager.get_salario_by_cargo_nivel_vigencia(id_cargos, id_niveis, data_vigencia)
                if existing_salario and existing_salario['ID_Salarios'] != salario_id:
                    flash('Já existe um pacote salarial para esta combinação de Cargo, Nível e Data de Vigência.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    return render_template(
                        'pessoal/salarios/edit_salario.html',
                        user=current_user,
                        salario=salario,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=request.form
                    )

                success = pessoal_manager.update_salario(
                    salario_id, id_cargos, id_niveis, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia
                )
                if success:
                    flash('Pacote salarial atualizado com sucesso!', 'success')
                    return redirect(url_for('salarios_module'))
                else:
                    flash('Erro ao atualizar pacote salarial.', 'danger')
            
            # GET request
            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
            
            # Formatar data de vigência para o input type="date"
            salario['Data_Vigencia'] = salario['Data_Vigencia'].strftime('%Y-%m-%d') if salario['Data_Vigencia'] else ''

            return render_template(
                'pessoal/salarios/edit_salario.html',
                user=current_user,
                salario=salario,
                all_cargos=all_cargos,
                all_niveis=all_niveis
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_salario: {e}")
        return redirect(url_for('salarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_salario: {e}")
        return redirect(url_for('salarios_module'))


@app.route('/pessoal/salarios/delete/<int:salario_id>', methods=['POST'])
@login_required
def delete_salario(salario_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_salario(salario_id)
            if success:
                flash('Pacote salarial excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir pacote salarial. Verifique se ele existe.', 'danger')
        return redirect(url_for('salarios_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_salario: {e}")
        return redirect(url_for('salarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_salario: {e}")
        return redirect(url_for('salarios_module'))


@app.route('/pessoal/salarios/details/<int:salario_id>')
@login_required
def salario_details(salario_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Salários.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            salario = pessoal_manager.get_salario_by_id(salario_id)

            if not salario:
                flash('Pacote salarial não encontrado.', 'danger')
                return redirect(url_for('salarios_module'))

        return render_template(
            'pessoal/salarios/salario_details.html',
            user=current_user,
            salario=salario
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em salario_details: {e}")
        return redirect(url_for('salarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em salario_details: {e}")
        return redirect(url_for('salarios_module'))


@app.route('/pessoal/salarios/export/excel')
@login_required
def export_salarios_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            search_cargo_id = request.args.get('cargo_id')
            search_nivel_id = request.args.get('nivel_id')

            salarios_data = pessoal_manager.get_all_salarios(
                search_cargo_id=int(search_cargo_id) if search_cargo_id else None,
                search_nivel_id=int(search_nivel_id) if search_nivel_id else None
            )

            if not salarios_data:
                flash('Nenhum pacote salarial encontrado para exportar.', 'info')
                return redirect(url_for('salarios_module'))

            df = pd.DataFrame(salarios_data)

            # Renomeie colunas para serem mais amigáveis no Excel
            df = df.rename(columns={
                'ID_Salarios': 'ID Salário',
                'ID_Cargos': 'ID Cargo',
                'ID_Niveis': 'ID Nível',
                'Salario_Base': 'Salário Base (R$)',
                'Periculosidade': 'Periculosidade',
                'Insalubridade': 'Insalubridade',
                'Ajuda_De_Custo': 'Ajuda de Custo (R$)',
                'Vale_Refeicao': 'Vale Refeição (R$)',
                'Gratificacao': 'Gratificação (R$)',
                'Cesta_Basica': 'Cesta Básica',
                'Outros_Beneficios': 'Outros Benefícios',
                'Data_Vigencia': 'Data de Vigência',
                'Nome_Cargo': 'Cargo',
                'Nome_Nivel': 'Nível',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            # Converter booleanos para 'Sim'/'Não' para melhor leitura no Excel
            df['Periculosidade'] = df['Periculosidade'].apply(lambda x: 'Sim' if x else 'Não')
            df['Insalubridade'] = df['Insalubridade'].apply(lambda x: 'Sim' if x else 'Não')
            df['Cesta_Basica'] = df['Cesta_Basica'].apply(lambda x: 'Sim' if x else 'Não')

            # Ordenar colunas para melhor visualização no Excel (opcional)
            ordered_columns = [
                'ID Salário', 'Cargo', 'Nível', 'Salário Base (R$)', 'Data de Vigência',
                'Periculosidade', 'Insalubridade', 'Ajuda de Custo (R$)',
                'Vale Refeição (R$)', 'Gratificação (R$)', 'Cesta Básica', 'Outros Benefícios',
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
                download_name='relatorio_salarios.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Salários para Excel: {e}", 'danger')
        print(f"Erro ao exportar Salários Excel: {e}")
        return redirect(url_for('salarios_module'))

# --- ROTAS DO SUBMÓDULO PESSOAL: FÉRIAS ---

@app.route('/pessoal/ferias')
@login_required
def ferias_module():
    if not current_user.can_access_module('Pessoal'): # Ou permissão específica para férias
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Férias.', 'warning')
        return redirect(url_for('welcome'))

    search_matricula = request.args.get('matricula')
    search_status = request.args.get('status')
    search_periodo_inicio = request.args.get('periodo_inicio')
    search_periodo_fim = request.args.get('periodo_fim')

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            ferias = pessoal_manager.get_all_ferias(
                search_matricula=search_matricula,
                search_status=search_status,
                search_periodo_inicio=datetime.strptime(search_periodo_inicio, '%Y-%m-%d').date() if search_periodo_inicio else None,
                search_periodo_fim=datetime.strptime(search_periodo_fim, '%Y-%m-%d').date() if search_periodo_fim else None
            )
            
            # Obter lista de funcionários para o dropdown de filtro e adição/edição
            all_funcionarios = pessoal_manager.get_all_funcionarios() # Você já tem este método

            status_options = ['Programada', 'Aprovada', 'Gozo', 'Concluída', 'Cancelada']

        return render_template(
            'pessoal/ferias/ferias_module.html',
            user=current_user,
            ferias=ferias,
            all_funcionarios=all_funcionarios,
            status_options=status_options,
            selected_matricula=search_matricula,
            selected_status=search_status,
            selected_periodo_inicio=search_periodo_inicio,
            selected_periodo_fim=search_periodo_fim
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Férias: {e}", 'danger')
        print(f"Erro de banco de dados em ferias_module: {e}")
        return redirect(url_for('pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Férias: {e}", 'danger')
        print(f"Erro inesperado em ferias_module: {e}")
        return redirect(url_for('pessoal_module'))


@app.route('/pessoal/ferias/add', methods=['GET', 'POST'])
@login_required
def add_ferias():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            # Carrega opções para os dropdowns, independentemente do método (GET/POST)
            all_funcionarios = pessoal_manager.get_all_funcionarios()
            status_options = ['Programada', 'Aprovada', 'Gozo', 'Concluída', 'Cancelada']

            # Inicializa form_data_to_template para preencher o formulário em caso de erro ou GET
            form_data_to_template = {}

            if request.method == 'POST':
                # Copia os dados do formulário para um dicionário mutável
                form_data_received = request.form.to_dict()

                # Tenta converter as datas primeiro
                periodo_aquisitivo_inicio = None
                periodo_aquisitivo_fim = None
                data_inicio_gozo = None
                data_fim_gozo = None

                is_valid = True

                try:
                    periodo_aquisitivo_inicio = datetime.strptime(form_data_received.get('periodo_aquisitivo_inicio', '').strip(), '%Y-%m-%d').date()
                    periodo_aquisitivo_fim = datetime.strptime(form_data_received.get('periodo_aquisitivo_fim', '').strip(), '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Período Aquisitivo inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False
                
                try:
                    if form_data_received.get('data_inicio_gozo', '').strip():
                        data_inicio_gozo = datetime.strptime(form_data_received.get('data_inicio_gozo').strip(), '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Início de Gozo inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False

                try:
                    if form_data_received.get('data_fim_gozo', '').strip():
                        data_fim_gozo = datetime.strptime(form_data_received.get('data_fim_gozo').strip(), '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data Final de Gozo inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False
                
                # Recarrega os dados do formulário para o dicionário que será passado para o template em caso de falha
                form_data_to_template = form_data_received
                # Formata as datas de volta para string para o input type="date"
                form_data_to_template['periodo_aquisitivo_inicio'] = periodo_aquisitivo_inicio.strftime('%Y-%m-%d') if periodo_aquisitivo_inicio else ''
                form_data_to_template['periodo_aquisitivo_fim'] = periodo_aquisitivo_fim.strftime('%Y-%m-%d') if periodo_aquisitivo_fim else ''
                form_data_to_template['data_inicio_gozo'] = data_inicio_gozo.strftime('%Y-%m-%d') if data_inicio_gozo else ''
                form_data_to_template['data_fim_gozo'] = data_fim_gozo.strftime('%Y-%m-%d') if data_fim_gozo else ''


                # Validação de campos obrigatórios e conversões numéricas
                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                dias_gozo = int(form_data_received.get('dias_gozo', 0))
                status_ferias = form_data_received.get('status_ferias', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                if not all([matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim, status_ferias]):
                    flash('Campos obrigatórios (Funcionário, Período Aquisitivo, Status) não podem ser vazios.', 'danger')
                    is_valid = False
                
                # --- DEBUG PRINTS ---
                # print(f"DEBUG_ADD_FERIAS: Periodo Aquisitivo Inicio (Tipo): {type(periodo_aquisitivo_inicio)}, Valor: {periodo_aquisitivo_inicio}")
                # print(f"DEBUG_ADD_FERIAS: Periodo Aquisitivo Fim (Tipo): {type(periodo_aquisitivo_fim)}, Valor: {periodo_aquisitivo_fim}")
                # print(f"DEBUG_ADD_FERIAS: Comparacao: {periodo_aquisitivo_fim} < {periodo_aquisitivo_inicio} = {periodo_aquisitivo_fim < periodo_aquisitivo_inicio}")
                # --- FIM DEBUG PRINTS ---

                # Regra de Negócio: Periodo_Aquisitivo_Fim deve ser posterior à Periodo_Aquisitivo_Inicio
                if is_valid and periodo_aquisitivo_fim < periodo_aquisitivo_inicio:
                    flash('Data final do período aquisitivo deve ser posterior à data inicial.', 'danger')
                    is_valid = False
                
                # Regra de Negócio: Data_Fim_Gozo deve ser posterior à Data_Inicio_Gozo (se ambos existirem)
                if is_valid and data_inicio_gozo and data_fim_gozo and data_fim_gozo < data_inicio_gozo:
                    flash('Data final de gozo deve ser posterior à data inicial de gozo.', 'danger')
                    is_valid = False

                if is_valid:
                    success = pessoal_manager.add_ferias(
                        matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim,
                        data_inicio_gozo, data_fim_gozo, dias_gozo, status_ferias, observacoes
                    )
                    if success:
                        flash('Registro de férias adicionado com sucesso!', 'success')
                        return redirect(url_for('ferias_module'))
                    else:
                        flash('Erro ao adicionar registro de férias. Verifique os dados e tente novamente.', 'danger')
            
            # GET request ou POST com falha de validação: Renderiza o formulário com dados existentes/submetidos
            return render_template(
                'pessoal/ferias/add_ferias.html',
                user=current_user,
                all_funcionarios=all_funcionarios,
                status_options=status_options,
                form_data=form_data_to_template # Passa os dados para preencher o formulário
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_ferias: {e}")
        return redirect(url_for('ferias_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_ferias: {e}")
        return redirect(url_for('ferias_module'))


@app.route('/pessoal/ferias/edit/<int:ferias_id>', methods=['GET', 'POST'])
@login_required
def edit_ferias(ferias_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            # Carrega opções para os dropdowns
            all_funcionarios = pessoal_manager.get_all_funcionarios()
            status_options = ['Programada', 'Aprovada', 'Gozo', 'Concluída', 'Cancelada']

            # Sempre busca o registro de férias para o GET inicial ou para re-exibir em caso de POST com erro
            ferias_from_db = pessoal_manager.get_ferias_by_id(ferias_id)
            if not ferias_from_db:
                flash('Registro de férias não encontrado.', 'danger')
                return redirect(url_for('ferias_module'))

            # Inicializa form_data_to_template para preencher o formulário
            form_data_to_template = {}


            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                # Tenta converter as datas primeiro
                periodo_aquisitivo_inicio = None
                periodo_aquisitivo_fim = None
                data_inicio_gozo = None
                data_fim_gozo = None

                is_valid = True

                try:
                    periodo_aquisitivo_inicio = datetime.strptime(form_data_received.get('periodo_aquisitivo_inicio', '').strip(), '%Y-%m-%d').date()
                    periodo_aquisitivo_fim = datetime.strptime(form_data_received.get('periodo_aquisitivo_fim', '').strip(), '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Período Aquisitivo inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False
                
                try:
                    if form_data_received.get('data_inicio_gozo', '').strip():
                        data_inicio_gozo = datetime.strptime(form_data_received.get('data_inicio_gozo').strip(), '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Início de Gozo inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False

                try:
                    if form_data_received.get('data_fim_gozo', '').strip():
                        data_fim_gozo = datetime.strptime(form_data_received.get('data_fim_gozo').strip(), '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data Final de Gozo inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False

                # Recarrega os dados do formulário para o dicionário que será passado para o template em caso de falha
                form_data_to_template = form_data_received
                # Formata as datas de volta para string para o input type="date"
                form_data_to_template['periodo_aquisitivo_inicio'] = periodo_aquisitivo_inicio.strftime('%Y-%m-%d') if periodo_aquisitivo_inicio else ''
                form_data_to_template['periodo_aquisitivo_fim'] = periodo_aquisitivo_fim.strftime('%Y-%m-%d') if periodo_aquisitivo_fim else ''
                form_data_to_template['data_inicio_gozo'] = data_inicio_gozo.strftime('%Y-%m-%d') if data_inicio_gozo else ''
                form_data_to_template['data_fim_gozo'] = data_fim_gozo.strftime('%Y-%m-%d') if data_fim_gozo else ''


                # Validação de campos obrigatórios e conversões numéricas
                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                dias_gozo = int(form_data_received.get('dias_gozo', 0))
                status_ferias = form_data_received.get('status_ferias', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                if not all([matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim, status_ferias]):
                    flash('Campos obrigatórios (Funcionário, Período Aquisitivo, Status) não podem ser vazios.', 'danger')
                    is_valid = False

                # --- DEBUG PRINTS ---
                # print(f"DEBUG_EDIT_FERIAS: Periodo Aquisitivo Inicio (Tipo): {type(periodo_aquisitivo_inicio)}, Valor: {periodo_aquisitivo_inicio}")
                # print(f"DEBUG_EDIT_FERIAS: Periodo Aquisitivo Fim (Tipo): {type(periodo_aquisitivo_fim)}, Valor: {periodo_aquisitivo_fim}")
                # print(f"DEBUG_EDIT_FERIAS: Comparacao: {periodo_aquisitivo_fim} < {periodo_aquisitivo_inicio} = {periodo_aquisitivo_fim < periodo_aquisitivo_inicio}")
                # --- FIM DEBUG PRINTS ---

                # Regra de Negócio: Periodo_Aquisitivo_Fim deve ser posterior à Periodo_Aquisitivo_Inicio
                if is_valid and periodo_aquisitivo_fim < periodo_aquisitivo_inicio:
                    flash('Data final do período aquisitivo deve ser posterior à data inicial.', 'danger')
                    is_valid = False
                
                # Regra de Negócio: Data_Fim_Gozo deve ser posterior à Data_Inicio_Gozo (se ambos existirem)
                if is_valid and data_inicio_gozo and data_fim_gozo and data_fim_gozo < data_inicio_gozo:
                    flash('Data final de gozo deve ser posterior à data inicial de gozo.', 'danger')
                    is_valid = False

                if is_valid:
                    success = pessoal_manager.update_ferias(
                        ferias_id, matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim,
                        data_inicio_gozo, data_fim_gozo, dias_gozo, status_ferias, observacoes
                    )
                    if success:
                        flash('Registro de férias atualizado com sucesso!', 'success')
                        return redirect(url_for('ferias_module'))
                    else:
                        flash('Erro ao atualizar registro de férias. Verifique os dados e tente novamente.', 'danger')
            
            else: # GET request
                # Prepara os dados do DB para exibição inicial no formulário GET
                form_data_to_template = ferias_from_db.copy()
                # Formatar datas para o input type="date"
                form_data_to_template['Periodo_Aquisitivo_Inicio'] = form_data_to_template['Periodo_Aquisitivo_Inicio'].strftime('%Y-%m-%d') if form_data_to_template['Periodo_Aquisitivo_Inicio'] else ''
                form_data_to_template['Periodo_Aquisitivo_Fim'] = form_data_to_template['Periodo_Aquisitivo_Fim'].strftime('%Y-%m-%d') if form_data_to_template['Periodo_Aquisitivo_Fim'] else ''
                form_data_to_template['Data_Inicio_Gozo'] = form_data_to_template['Data_Inicio_Gozo'].strftime('%Y-%m-%d') if form_data_to_template['Data_Inicio_Gozo'] else ''
                form_data_to_template['Data_Fim_Gozo'] = form_data_to_template['Data_Fim_Gozo'].strftime('%Y-%m-%d') if form_data_to_template['Data_Fim_Gozo'] else ''

            return render_template(
                'pessoal/ferias/edit_ferias.html',
                user=current_user,
                ferias=form_data_to_template, # Passa os dados preparados aqui
                all_funcionarios=all_funcionarios,
                status_options=status_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_ferias: {e}")
        return redirect(url_for('ferias_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_ferias: {e}")
        return redirect(url_for('ferias_module'))

@app.route('/pessoal/ferias/delete/<int:ferias_id>', methods=['POST'])
@login_required
def delete_ferias(ferias_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_ferias(ferias_id)
            if success:
                flash('Registro de férias excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir registro de férias. Verifique se ele existe.', 'danger')
        return redirect(url_for('ferias_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_ferias: {e}")
        return redirect(url_for('ferias_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_ferias: {e}")
        return redirect(url_for('ferias_module'))


@app.route('/pessoal/ferias/details/<int:ferias_id>')
@login_required
def ferias_details(ferias_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Férias.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            ferias = pessoal_manager.get_ferias_by_id(ferias_id)

            if not ferias:
                flash('Registro de férias não encontrado.', 'danger')
                return redirect(url_for('ferias_module'))

        return render_template(
            'pessoal/ferias/ferias_details.html',
            user=current_user,
            ferias=ferias
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em ferias_details: {e}")
        return redirect(url_for('ferias_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em ferias_details: {e}")
        return redirect(url_for('ferias_module'))


@app.route('/pessoal/ferias/export/excel')
@login_required
def export_ferias_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            search_matricula = request.args.get('matricula')
            search_status = request.args.get('status')
            search_periodo_inicio = request.args.get('periodo_inicio')
            search_periodo_fim = request.args.get('periodo_fim')

            ferias_data = pessoal_manager.get_all_ferias(
                search_matricula=search_matricula,
                search_status=search_status,
                search_periodo_inicio=datetime.strptime(search_periodo_inicio, '%Y-%m-%d').date() if search_periodo_inicio else None,
                search_periodo_fim=datetime.strptime(search_periodo_fim, '%Y-%m-%d').date() if search_periodo_fim else None
            )

            if not ferias_data:
                flash('Nenhum registro de férias encontrado para exportar.', 'info')
                return redirect(url_for('ferias_module'))

            df = pd.DataFrame(ferias_data)

            # Renomeie colunas para serem mais amigáveis no Excel
            df = df.rename(columns={
                'ID_Ferias': 'ID Férias',
                'Matricula_Funcionario': 'Matrícula',
                'Nome_Funcionario': 'Nome do Funcionário',
                'Periodo_Aquisitivo_Inicio': 'Início Período Aquisitivo',
                'Periodo_Aquisitivo_Fim': 'Fim Período Aquisitivo',
                'Data_Inicio_Gozo': 'Início Gozo',
                'Data_Fim_Gozo': 'Fim Gozo',
                'Dias_Gozo': 'Dias de Gozo',
                'Status_Ferias': 'Status',
                'Observacoes': 'Observações',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
            ordered_columns = [
                'ID Férias', 'Matrícula', 'Nome do Funcionário',
                'Início Período Aquisitivo', 'Fim Período Aquisitivo',
                'Início Gozo', 'Fim Gozo', 'Dias de Gozo', 'Status',
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
                download_name='relatorio_ferias.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Férias para Excel: {e}", 'danger')
        print(f"Erro ao exportar Férias Excel: {e}")
        return redirect(url_for('ferias_module'))

#
#  DEPENDENTES - MÓDULO PESSOAL
#  2026-06-26 - MENDES/GEMINI

# Função auxiliar para calcular idade (Certifique-se de que esta é a versão atualizada)
def calculate_age(born_date):
    """Calcula a idade em anos a partir de uma data de nascimento."""
    # Garante que born_date é um objeto date e não None
    if not isinstance(born_date, date):
        print(f"DEBUG_CALCULATE_AGE: Data de nascimento inválida ou não é objeto date: {born_date} (Tipo: {type(born_date)}). Retornando None.")
        return None
    
    today = date.today()
    age = today.year - born_date.year - ((today.month, today.day) < (born_date.month, born_date.day))
    print(f"DEBUG_CALCULATE_AGE: Data Nascimento: {born_date}, Hoje: {today}, Idade Calculada: {age}")
    return age


# --- ROTAS DO SUBMÓDULO PESSOAL: DEPENDENTES E CONTATOS DE EMERGÊNCIA ---

@app.route('/pessoal/dependentes')
@login_required
def dependentes_module():
    if not current_user.can_access_module('Pessoal'): # Ou permissão específica para dependentes
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    search_matricula = request.args.get('matricula')
    search_nome = request.args.get('nome')
    search_parentesco = request.args.get('parentesco')

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            # Obtém todos os dependentes com base nos filtros
            dependentes = pessoal_manager.get_all_dependentes(
                search_matricula=search_matricula,
                search_nome=search_nome,
                search_parentesco=search_parentesco
            )
            
            # Lista para armazenar os dependentes com a idade calculada
            processed_dependentes = []
            for dep in dependentes:
                # É importante criar uma cópia mutável do dicionário para adicionar a idade
                dep_copy = dep.copy() 
                
                # DEBUG: Verificar o tipo e valor de Data_Nascimento antes de calcular a idade
                print(f"DEBUG_DEPENDENTES_MODULE: Processando dependente: {dep_copy.get('Nome_Completo')}")
                print(f"DEBUG_DEPENDENTES_MODULE: Data_Nascimento original: {dep_copy.get('Data_Nascimento')} (Tipo: {type(dep_copy.get('Data_Nascimento'))})")
                
                # Calcula a idade e adiciona ao dicionário
                dep_copy['Idade'] = calculate_age(dep_copy.get('Data_Nascimento'))
                
                print(f"DEBUG_DEPENDENTES_MODULE: Idade calculada: {dep_copy['Idade']}")
                processed_dependentes.append(dep_copy)

            # DEBUG FINAL: Imprime a lista completa que será enviada para o template
            print(f"DEBUG_DEPENDENTES_MODULE: Dados finais para o template: {processed_dependentes}")


            # Obter lista de funcionários para o dropdown de filtro (e futuros formulários)
            all_funcionarios = pessoal_manager.get_all_funcionarios()
            
            # Opções de parentesco para o filtro
            parentesco_options = ['Filho(a)', 'Cônjuge', 'Pai', 'Mãe', 'Irmão(ã)', 'Outro']

        return render_template(
            'pessoal/dependentes/dependentes_module.html',
            user=current_user,
            dependentes=processed_dependentes, # Passa a lista com as idades calculadas
            all_funcionarios=all_funcionarios,
            parentesco_options=parentesco_options,
            selected_matricula=search_matricula,
            selected_nome=search_nome,
            selected_parentesco=search_parentesco
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Dependentes: {e}", 'danger')
        print(f"Erro de banco de dados em dependentes_module: {e}")
        return redirect(url_for('pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Dependentes: {e}", 'danger')
        print(f"Erro inesperado em dependentes_module: {e}")
        # Redireciona para a página principal do módulo Pessoal para evitar um loop de erro
        return redirect(url_for('pessoal_module'))

@app.route('/pessoal/dependentes/add', methods=['GET', 'POST'])
@login_required
def add_dependente():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            # Carrega opções para os dropdowns, independentemente do método (GET/POST)
            all_funcionarios = pessoal_manager.get_all_funcionarios()
            parentesco_options = ['Filho(a)', 'Cônjuge', 'Pai', 'Mãe', 'Irmão(ã)', 'Outro']

            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                nome_completo = form_data_received.get('nome_completo', '').strip()
                parentesco = form_data_received.get('parentesco', '').strip()
                data_nascimento_str = form_data_received.get('data_nascimento', '').strip()
                cpf = form_data_received.get('cpf', '').replace('.', '').replace('-', '').strip()
                contato_emergencia = 'contato_emergencia' in request.form
                telefone_emergencia = form_data_received.get('telefone_emergencia', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                data_nascimento = None
                is_valid = True

                if not all([matricula_funcionario, nome_completo, parentesco]):
                    flash('Campos obrigatórios (Funcionário, Nome Completo, Parentesco) não podem ser vazios.', 'danger')
                    is_valid = False
                
                if data_nascimento_str:
                    try:
                        data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Nascimento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                if cpf:
                    existing_dependente = pessoal_manager.get_dependente_by_cpf(cpf)
                    if existing_dependente:
                        flash('Já existe um dependente com este CPF.', 'danger')
                        is_valid = False

                # Recarrega os dados do formulário para o dicionário que será passado para o template em caso de falha
                form_data_to_template = form_data_received
                form_data_to_template['data_nascimento'] = data_nascimento_str # Mantém a string original para re-preencher o input date
                form_data_to_template['contato_emergencia'] = contato_emergencia # Para checagem do checkbox

                if is_valid:
                    success = pessoal_manager.add_dependente(
                        matricula_funcionario, nome_completo, parentesco, data_nascimento,
                        cpf if cpf else None, contato_emergencia, telefone_emergencia, observacoes
                    )
                    if success:
                        flash('Dependente adicionado com sucesso!', 'success')
                        return redirect(url_for('dependentes_module'))
                    else:
                        flash('Erro ao adicionar dependente. Verifique os dados e tente novamente.', 'danger')
            
            # GET request ou POST com falha de validação: Renderiza o formulário com dados existentes/submetidos
            return render_template(
                'pessoal/dependentes/add_dependente.html',
                user=current_user,
                all_funcionarios=all_funcionarios,
                parentesco_options=parentesco_options,
                form_data=form_data_to_template
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_dependente: {e}")
        return redirect(url_for('dependentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_dependente: {e}")
        return redirect(url_for('dependentes_module'))


@app.route('/pessoal/dependentes/edit/<int:dependente_id>', methods=['GET', 'POST'])
@login_required
def edit_dependente(dependente_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            # Carrega opções para os dropdowns
            all_funcionarios = pessoal_manager.get_all_funcionarios()
            parentesco_options = ['Filho(a)', 'Cônjuge', 'Pai', 'Mãe', 'Irmão(ã)', 'Outro']

            # Sempre busca o registro de dependente para o GET inicial ou para re-exibir em caso de POST com erro
            dependente_from_db = pessoal_manager.get_dependente_by_id(dependente_id)
            if not dependente_from_db:
                flash('Dependente não encontrado.', 'danger')
                return redirect(url_for('dependentes_module'))

            form_data_to_template = {} # Inicializa para o GET ou falha do POST

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                nome_completo = form_data_received.get('nome_completo', '').strip()
                parentesco = form_data_received.get('parentesco', '').strip()
                data_nascimento_str = form_data_received.get('data_nascimento', '').strip()
                cpf = form_data_received.get('cpf', '').replace('.', '').replace('-', '').strip()
                contato_emergencia = 'contato_emergencia' in request.form
                telefone_emergencia = form_data_received.get('telefone_emergencia', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                data_nascimento = None
                is_valid = True

                if not all([matricula_funcionario, nome_completo, parentesco]):
                    flash('Campos obrigatórios (Funcionário, Nome Completo, Parentesco) não podem ser vazios.', 'danger')
                    is_valid = False
                
                if data_nascimento_str:
                    try:
                        data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Nascimento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                if cpf:
                    existing_dependente = pessoal_manager.get_dependente_by_cpf(cpf, exclude_id=dependente_id)
                    if existing_dependente:
                        flash('Já existe um dependente com este CPF.', 'danger')
                        is_valid = False

                # Recarrega os dados do formulário para o dicionário que será passado para o template em caso de falha
                form_data_to_template = form_data_received
                form_data_to_template['data_nascimento'] = data_nascimento_str # Mantém a string original para re-preencher o input date
                form_data_to_template['contato_emergencia'] = contato_emergencia # Para checagem do checkbox

                if is_valid:
                    success = pessoal_manager.update_dependente(
                        dependente_id, matricula_funcionario, nome_completo, parentesco, data_nascimento,
                        cpf if cpf else None, contato_emergencia, telefone_emergencia, observacoes
                    )
                    if success:
                        flash('Dependente atualizado com sucesso!', 'success')
                        return redirect(url_for('dependentes_module'))
                    else:
                        flash('Erro ao atualizar dependente. Verifique os dados e tente novamente.', 'danger')
            
            else: # GET request
                # Prepara os dados do DB para exibição inicial no formulário GET
                form_data_to_template = dependente_from_db.copy()
                # Formatar data de nascimento para o input type="date"
                form_data_to_template['Data_Nascimento'] = form_data_to_template['Data_Nascimento'].strftime('%Y-%m-%d') if form_data_to_template['Data_Nascimento'] else ''
                # Assegurar que 'contato_emergencia' no template reflete o booleano do DB
                form_data_to_template['Contato_Emergencia'] = bool(form_data_to_template.get('Contato_Emergencia'))

            return render_template(
                'pessoal/dependentes/edit_dependente.html',
                user=current_user,
                dependente=form_data_to_template, # Passa os dados preparados aqui
                all_funcionarios=all_funcionarios,
                parentesco_options=parentesco_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_dependente: {e}")
        return redirect(url_for('dependentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_dependente: {e}")
        return redirect(url_for('dependentes_module'))


@app.route('/pessoal/dependentes/delete/<int:dependente_id>', methods=['POST'])
@login_required
def delete_dependente(dependente_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_dependente(dependente_id)
            if success:
                flash('Dependente excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir dependente. Verifique se ele existe.', 'danger')
        return redirect(url_for('dependentes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_dependente: {e}")
        return redirect(url_for('dependentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_dependente: {e}")
        return redirect(url_for('dependentes_module'))


@app.route('/pessoal/dependentes/details/<int:dependente_id>')
@login_required
def dependente_details(dependente_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Dependentes.', 'warning')
        return redirect(url_for('welcome'))
    
    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            dependente = pessoal_manager.get_dependente_by_id(dependente_id)

            if not dependente:
                flash('Dependente não encontrado.', 'danger')
                return redirect(url_for('dependentes_module'))

            # Calcular a idade para o dependente individual
            dependente['Idade'] = calculate_age(dependente.get('Data_Nascimento'))

        return render_template(
            'pessoal/dependentes/dependente_details.html',
            user=current_user,
            dependente=dependente
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em dependente_details: {e}")
        return redirect(url_for('dependentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em dependente_details: {e}")
        return redirect(url_for('dependentes_module'))


@app.route('/pessoal/dependentes/export/excel')
@login_required
def export_dependentes_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            search_matricula = request.args.get('matricula')
            search_nome = request.args.get('nome')
            search_parentesco = request.args.get('parentesco')

            dependentes_data = pessoal_manager.get_all_dependentes(
                search_matricula=search_matricula,
                search_nome=search_nome,
                search_parentesco=search_parentesco
            )

            if not dependentes_data:
                flash('Nenhum dependente encontrado para exportar.', 'info')
                return redirect(url_for('dependentes_module'))

            # Calcular a idade antes de criar o DataFrame
            for dep in dependentes_data:
                dep['Idade'] = calculate_age(dep.get('Data_Nascimento'))

            df = pd.DataFrame(dependentes_data)

            # Renomeie colunas para serem mais amigáveis no Excel
            df = df.rename(columns={
                'ID_Dependente': 'ID Dependente',
                'Matricula_Funcionario': 'Matrícula Funcionário',
                'Nome_Funcionario': 'Nome do Funcionário',
                'Nome_Completo': 'Nome do Dependente',
                'Parentesco': 'Parentesco',
                'Data_Nascimento': 'Data de Nascimento',
                'Idade': 'Idade (anos)', # Novo campo
                'Cpf': 'CPF',
                'Contato_Emergencia': 'Contato de Emergência',
                'Telefone_Emergencia': 'Telefone de Emergência',
                'Observacoes': 'Observações',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })
            
            # Converter booleanos para 'Sim'/'Não' para melhor leitura no Excel
            df['Contato de Emergência'] = df['Contato de Emergência'].apply(lambda x: 'Sim' if x else 'Não')

            # Ordenar colunas para melhor visualização no Excel (opcional)
            ordered_columns = [
                'ID Dependente', 'Matrícula Funcionário', 'Nome do Funcionário',
                'Nome do Dependente', 'Parentesco', 'Data de Nascimento', 'Idade (anos)', 'CPF',
                'Contato de Emergência', 'Telefone de Emergência', 'Observações',
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
                download_name='relatorio_dependentes.xlsx'
            )

    except Exception as e:
        flash(f"Ocorreu um erro ao exportar Dependentes para Excel: {e}", 'danger')
        print(f"Erro ao exportar Dependentes Excel: {e}")
        return redirect(url_for('dependentes_module'))

#---------------------------------------------------------------------------------------------------
# ROTAS PARA O MÓDULO SEGURANÇA                                                                    |
#---------------------------------------------------------------------------------------------------

# --- ROTAS DO MÓDULO SEGURANÇA, SAÚDE E MEIO AMBIENTE (SSMA): INCIDENTES E ACIDENTES ---

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

# ---------------------------------------------------------------------
# --- ROTAS DO MÓDULO SEGURANÇA, SAÚDE E MEIO AMBIENTE (SSMA): ASOs ---
# ---------------------------------------------------------------------

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

# --- ROTAS DO MÓDULO SEGURANÇA, SAÚDE E MEIO AMBIENTE (SSMA): TREINAMENTOS (Catálogo) ---

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


# --- ROTAS DO MÓDULO SEGURANÇA, SAÚDE E MEIO AMBIENTE (SSMA): AGENDAMENTOS DE TREINAMENTOS ---

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

# ----------------------------------------------------------------------------------------------
# --- ROTAS DO MÓDULO SEGURANÇA, SAÚDE E MEIO AMBIENTE (SSMA): PARTICIPANTES DE TREINAMENTOS ---
# ----------------------------------------------------------------------------------------------

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

#---------------------------------------------------------------------------------------------------
# ROTAS PARA O MÓDULO OBRAS                                                                        |
#---------------------------------------------------------------------------------------------------

# $$$$$$$$$$$$$$$$$$$$$$$$$$$$
# $  MÓDULO OBRAS - WELCOME  $
# $$$$$$$$$$$$$$$$$$$$$$$$$$$$

@app.route('/obras')
@login_required
def obras_module():
    # Verificação de permissão para o módulo Obras
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Obras.', 'warning')
        return redirect(url_for('welcome'))

    search_numero = request.args.get('numero_obra')
    search_nome = request.args.get('nome_obra')
    search_status = request.args.get('status_obra')
    search_cliente_id = request.args.get('cliente_id') # Adicione o ID do cliente se quiser filtrar por cliente

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            # Obter todas as obras com filtros (se houver)
            obras = obras_manager.get_all_obras(
                search_numero=search_numero,
                search_nome=search_nome,
                search_status=search_status,
                search_cliente_id=search_cliente_id
            )
            
            # Obter lista de clientes para o filtro (opcional)
            clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
            
            # Status de obra fixos para o filtro (pode vir do banco se tiver tabela de domínios)
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']

        return render_template(
            'obras/obras_welcome.html', # Novo Template ao invés do obras_module.html
            user=current_user,
            obras=obras,
            clientes=clientes,
            status_options=status_options,
            # Passar os filtros selecionados de volta para o template para manter o estado do formulário
            selected_numero=search_numero,
            selected_nome=search_nome,
            selected_status=search_status,
            selected_cliente_id=int(search_cliente_id) if search_cliente_id else None
        )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar obras: {e}", 'danger')
        print(f"Erro de banco de dados em obras_module: {e}")
        return redirect(url_for('welcome'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar obras: {e}", 'danger')
        print(f"Erro inesperado em obras_module: {e}")
        return redirect(url_for('welcome'))

# NOVA ROTA PARA A LISTAGEM/GERENCIAMENTO DE OBRAS ESPECÍFICAS
@app.route('/obras/gerenciar') # NOVO CAMINHO: /obras/gerenciar
@login_required
def gerenciar_obras_lista(): # NOVO ENDPOINT: 'gerenciar_obras_lista'
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Obras.', 'warning')
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
            
            clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']

        return render_template(
            'obras/obras_module.html', # CONTINUA USANDO ESTE TEMPLATE PARA A LISTA
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
        return redirect(url_for('welcome'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar obras: {e}", 'danger')
        print(f"Erro inesperado em gerenciar_obras_lista: {e}")
        return redirect(url_for('welcome'))

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
                valor_obra = float(request.form['valor_obra'].replace(',', '.')) # Converte para float, ajusta vírgula
                valor_aditivo_total = float(request.form.get('valor_aditivo_total', '0').replace(',', '.'))
                status_obra = request.form['status_obra'].strip()
                data_inicio_prevista_str = request.form['data_inicio_prevista'].strip()
                data_fim_prevista_str = request.form['data_fim_prevista'].strip()

                # Validação básica
                if not all([id_contratos, numero_obra, nome_obra, status_obra, data_inicio_prevista_str, data_fim_prevista_str]):
                    flash('Campos obrigatórios (Contrato, Número, Nome, Status, Datas de Início/Fim) não podem ser vazios.', 'danger')
                    # Recarregar contratos e status para o formulário
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/add_obra.html',
                        user=current_user,
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form # Passa os dados do form para manter os campos preenchidos
                    )

                # Converter datas
                try:
                    data_inicio_prevista = datetime.strptime(data_inicio_prevista_str, '%Y-%m-%d').date()
                    data_fim_prevista = datetime.strptime(data_fim_prevista_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    # Recarregar contratos e status para o formulário
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/add_obra.html',
                        user=current_user,
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                # Opcional: Verificar unicidade do número da obra
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
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada'] # Opções de status fixas
                
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

                # Validação básica
                if not all([id_contratos, numero_obra, nome_obra, status_obra, data_inicio_prevista_str, data_fim_prevista_str]):
                    flash('Campos obrigatórios (Contrato, Número, Nome, Status, Datas de Início/Fim) não podem ser vazios.', 'danger')
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/edit_obra.html',
                        user=current_user,
                        obra=obra, # Passa a obra original
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form # Tenta manter os dados digitados
                    )

                # Converter datas
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
                        obra=obra, # Passa a obra original
                        all_contratos=all_contratos,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                # Opcional: Verificar unicidade do número da obra, exceto para a obra atual
                existing_obra = obras_manager.get_obra_by_numero(numero_obra)
                if existing_obra and existing_obra['ID_Obras'] != obra_id:
                    flash('Número da obra já existe. Por favor, use um número único.', 'danger')
                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/edit_obra.html',
                        user=current_user,
                        obra=obra, # Passa a obra original
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
            
            # GET request: Carregar dados para o formulário
            all_contratos = obras_manager.get_all_contratos_for_dropdown()
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
            
            # Formata as datas para o formato 'YYYY-MM-DD' para o input type="date"
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
        # Se o erro for por causa de FOREIGN KEY constraint, dar uma mensagem mais específica
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir a obra pois existem registros relacionados (ARTs, Medições, etc.). Remova-os primeiro.", 'danger')
        return redirect(url_for('gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_obra: {e}")
        return redirect(url_for('gerenciar_obras_lista'))

# Opcional: Rota para detalhes da obra (se quiser uma página separada)
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
                return redirect(url_for('ogerenciar_obras_lista'))

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

@app.route('/obras/export/excel')
@login_required
def export_obras_excel():
    if not current_user.can_access_module('Obras'):
        flash('Acesso negado. Você não tem permissão para exportar dados de obras.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            # Use os mesmos filtros da página de listagem, se quiser exportar apenas o que está filtrado
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

            # Renomeie colunas para serem mais amigáveis no Excel
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
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
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

# *************************************
# *        submódulo clientes         *      
# *************************************

# --- ROTAS DO MÓDULO OBRAS: CLIENTES (DESCOMENTAR ESTE BLOCO) ---

@app.route('/obras/clientes')
@login_required
def clientes_module(): # ESTE É O ENDPOINT 'clientes_module' que estava faltando
    if not current_user.can_access_module('Obras'): # Ou uma permissão específica para Clientes
        flash('Acesso negado. Você não tem permissão para acessar o módulo de Clientes.', 'warning')
        return redirect(url_for('welcome'))

    search_nome = request.args.get('nome_cliente')
    search_cnpj = request.args.get('cnpj_cliente')

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base) # Reutilizamos o ObrasManager
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
        return redirect(url_for('obras_module')) # Volta para o hub de obras
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar clientes: {e}", 'danger')
        print(f"Erro inesperado em clientes_module: {e}")
        return redirect(url_for('obras_module')) # Volta para o hub de obras


@app.route('/obras/clientes/add', methods=['GET', 'POST'])
@login_required
def add_cliente():
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
                if not all([nome_cliente, cnpj_cliente]):
                    flash('Nome e CNPJ do cliente são obrigatórios.', 'danger')
                    return render_template(
                        'obras/clientes/add_cliente.html',
                        user=current_user,
                        form_data=request.form # Mantém dados preenchidos
                    )
                
                # Verificar unicidade do CNPJ
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
            
            # GET request
            return render_template(
                'obras/clientes/add_cliente.html',
                user=current_user,
                form_data={} # Garante que form_data esteja definido no GET
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_cliente: {e}")
        return redirect(url_for('clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_cliente: {e}")
        return redirect(url_for('clientes_module'))


@app.route('/obras/clientes/edit/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def edit_cliente(cliente_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
                if not all([nome_cliente, cnpj_cliente]):
                    flash('Nome e CNPJ do cliente são obrigatórios.', 'danger')
                    return render_template(
                        'obras/clientes/edit_cliente.html',
                        user=current_user,
                        cliente=cliente, # Passa o cliente original
                        form_data=request.form # Tenta manter os dados digitados
                    )
                
                # Verificar unicidade do CNPJ, exceto para o cliente atual
                existing_cliente = obras_manager.get_cliente_by_cnpj(cnpj_cliente)
                if existing_cliente and existing_cliente['ID_Clientes'] != cliente_id:
                    flash('CNPJ já existe. Por favor, use um CNPJ único.', 'danger')
                    return render_template(
                        'obras/clientes/edit_cliente.html',
                        user=current_user,
                        cliente=cliente, # Passa o cliente original
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
            
            # GET request
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


@app.route('/obras/clientes/delete/<int:cliente_id>', methods=['POST'])
@login_required
def delete_cliente(cliente_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/clientes/details/<int:cliente_id>')
@login_required
def cliente_details(cliente_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/clientes/export/excel')
@login_required
def export_clientes_excel():
    if not current_user.can_access_module('Obras'): # Você pode criar uma permissão específica para exportação
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

            # Renomeie colunas para serem mais amigáveis no Excel
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
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
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

# *******************************
# * submódulo CONTRATOS (OBRAS) *
# *******************************

# --- ROTAS DO MÓDULO OBRAS: CONTRATOS --- 2025-06-24 MENDES / GEMINI

@app.route('/obras/contratos')
@login_required
def contratos_module(): # Este é o ENDPOINT 'contratos_module'
    if not current_user.can_access_module('Obras'): # Ou uma permissão específica para Contratos
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
            
            # Obter lista de clientes para o filtro
            clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
            
            # Opções de status de contrato (pode vir do banco se tiver tabela de domínios)
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
        return redirect(url_for('obras_module')) # Volta para o hub de obras
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar contratos: {e}", 'danger')
        print(f"Erro inesperado em contratos_module: {e}")
        return redirect(url_for('obras_module')) # Volta para o hub de obras


@app.route('/obras/contratos/add', methods=['GET', 'POST'])
@login_required
def add_contrato():
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
                if not all([id_clientes, numero_contrato, valor_contrato, data_assinatura_str, status_contrato]):
                    flash('Campos obrigatórios (Cliente, Número, Valor, Data Assinatura, Status) não podem ser vazios.', 'danger')
                    all_clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/add_contrato.html',
                        user=current_user,
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                # Converter datas
                try:
                    data_assinatura = datetime.strptime(data_assinatura_str, '%Y-%m-%d').date()
                    data_ordem_inicio = datetime.strptime(data_ordem_inicio_str, '%Y-%m-%d').date() if data_ordem_inicio_str else None
                    data_termino_previsto = datetime.strptime(data_termino_previsto_str, '%Y-%m-%d').date() if data_termino_previsto_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/add_contrato.html',
                        user=current_user,
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                # Verificar unicidade do número do contrato
                if obras_manager.get_contrato_by_numero(numero_contrato):
                    flash('Número do contrato já existe. Por favor, use um número único.', 'danger')
                    all_clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
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
            
            # GET request
            all_clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
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


@app.route('/obras/contratos/edit/<int:contrato_id>', methods=['GET', 'POST'])
@login_required
def edit_contrato(contrato_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
                if not all([id_clientes, numero_contrato, valor_contrato, data_assinatura_str, status_contrato]):
                    flash('Campos obrigatórios (Cliente, Número, Valor, Data Assinatura, Status) não podem ser vazios.', 'danger')
                    all_clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/edit_contrato.html',
                        user=current_user,
                        contrato=contrato,
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )
                
                # Converter datas
                try:
                    data_assinatura = datetime.strptime(data_assinatura_str, '%Y-%m-%d').date()
                    data_ordem_inicio = datetime.strptime(data_ordem_inicio_str, '%Y-%m-%d').date() if data_ordem_inicio_str else None
                    data_termino_previsto = datetime.strptime(data_termino_previsto_str, '%Y-%m-%d').date() if data_termino_previsto_str else None
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    all_clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
                    status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
                    return render_template(
                        'obras/contratos/edit_contrato.html',
                        user=current_user,
                        contrato=contrato,
                        all_clientes=all_clientes,
                        status_options=status_options,
                        form_data=request.form
                    )

                # Verificar unicidade do número do contrato, exceto para o contrato atual
                existing_contrato = obras_manager.get_contrato_by_numero(numero_contrato)
                if existing_contrato and existing_contrato['ID_Contratos'] != contrato_id:
                    flash('Número do contrato já existe. Por favor, use um número único.', 'danger')
                    all_clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
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
            
            # GET request
            all_clientes = obras_manager.db.execute_query("SELECT ID_Clientes, Nome_Cliente FROM clientes ORDER BY Nome_Cliente", fetch_results=True)
            status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']
            
            # Formatar datas para o input type="date"
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


@app.route('/obras/contratos/delete/<int:contrato_id>', methods=['POST'])
@login_required
def delete_contrato(contrato_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/contratos/details/<int:contrato_id>')
@login_required
def contrato_details(contrato_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/contratos/export/excel')
@login_required
def export_contratos_excel():
    if not current_user.can_access_module('Obras'): # Você pode criar uma permissão específica para exportação
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

            # Renomeie colunas para serem mais amigáveis no Excel
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
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
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


# ***************************
# * submódulo ARTS (OBRAS)  *
# ***************************

# --- ROTAS DO MÓDULO OBRAS: ARTS --- 2025-06-24 MENDES / GEMINI

@app.route('/obras/arts')
@login_required
def arts_module(): # Este é o ENDPOINT 'arts_module'
    if not current_user.can_access_module('Obras'): # Ou uma permissão específica para ARTs
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
            
            # Obter lista de obras para o filtro
            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            # Opções de status de ART (pode vir do banco se tiver tabela de domínios)
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
        return redirect(url_for('obras_module')) # Volta para o hub de obras
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar ARTs: {e}", 'danger')
        print(f"Erro inesperado em arts_module: {e}")
        return redirect(url_for('obras_module')) # Volta para o hub de obras


@app.route('/obras/arts/add', methods=['GET', 'POST'])
@login_required
def add_art():
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
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
                
                # Converter data (se existir)
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
                
                # Verificar unicidade do número da ART
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
            
            # GET request
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


@app.route('/obras/arts/edit/<int:art_id>', methods=['GET', 'POST'])
@login_required
def edit_art(art_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
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
                
                # Converter data (se existir)
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

                # Verificar unicidade do número da ART, exceto para a ART atual
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
            
            # GET request
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']
            
            # Formatar datas para o input type="date"
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


@app.route('/obras/arts/delete/<int:art_id>', methods=['POST'])
@login_required
def delete_art(art_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/arts/details/<int:art_id>')
@login_required
def art_details(art_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/arts/export/excel')
@login_required
def export_arts_excel():
    if not current_user.can_access_module('Obras'): # Você pode criar uma permissão específica para exportação
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

            # Renomeie colunas para serem mais amigáveis no Excel
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
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
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

# *******************************
# * submódulo MEDICOES (OBRAS)  *
# *******************************
# --- ROTAS DO MÓDULO OBRAS: MEDIÇÕES --- 2025-06-24 MENDES/GEMINI

@app.route('/obras/medicoes')
@login_required
def medicoes_module(): # Este é o ENDPOINT 'medicoes_module'
    if not current_user.can_access_module('Obras'): # Ou uma permissão específica para Medições
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
            
            # Obter lista de obras para o filtro
            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            # Opções de status de Medição
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
        return redirect(url_for('obras_module')) # Volta para o hub de obras
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Medições: {e}", 'danger')
        print(f"Erro inesperado em medicoes_module: {e}")
        return redirect(url_for('obras_module')) # Volta para o hub de obras


@app.route('/obras/medicoes/add', methods=['GET', 'POST'])
@login_required
def add_medicao():
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
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
                
                # Converter datas
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
                
                # Verificar unicidade (ID_Obras, Numero_Medicao)
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
            
            # GET request
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


@app.route('/obras/medicoes/edit/<int:medicao_id>', methods=['GET', 'POST'])
@login_required
def edit_medicao(medicao_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
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
                
                # Converter datas
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

                # Verificar unicidade (ID_Obras, Numero_Medicao) para outras medições
                existing_medicao = obras_manager.get_medicao_by_obra_numero(id_obras, numero_medicao)
                if existing_medicao and existing_medicao['ID_Medicoes'] != medicao_id:
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
            
            # GET request
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']
            
            # Formatar datas para o input type="date"
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


@app.route('/obras/medicoes/delete/<int:medicao_id>', methods=['POST'])
@login_required
def delete_medicao(medicao_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/medicoes/details/<int:medicao_id>')
@login_required
def medicao_details(medicao_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/medicoes/export/excel')
@login_required
def export_medicoes_excel():
    if not current_user.can_access_module('Obras'): # Você pode criar uma permissão específica para exportação
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

            # Renomeie colunas para serem mais amigáveis no Excel
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
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
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

# ************************************
# * submódulo AVANÇO FÍSICO (OBRAS)  *
# ************************************
# --- ROTAS DO MÓDULO OBRAS: AVANÇO FÍSICO --- 2025-06-24 MENDES/GEMINI

@app.route('/obras/avancos_fisicos')
@login_required
def avancos_fisicos_module(): # Este é o ENDPOINT 'avancos_fisicos_module'
    if not current_user.can_access_module('Obras'): # Ou uma permissão específica
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
        # Continuar com as datas como None, ou redirecionar, dependendo da sua preferência
        # Por simplicidade, continuaremos e deixaremos o filtro de data falhar silenciosamente no DB Manager

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            avancos = obras_manager.get_all_avancos_fisicos(
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_data_inicio=search_data_inicio,
                search_data_fim=search_data_fim
            )
            
            # Obter lista de obras para o filtro
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
        return redirect(url_for('obras_module')) # Volta para o hub de obras
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Avanços Físicos: {e}", 'danger')
        print(f"Erro inesperado em avancos_fisicos_module: {e}")
        return redirect(url_for('obras_module')) # Volta para o hub de obras


@app.route('/obras/avancos_fisicos/add', methods=['GET', 'POST'])
@login_required
def add_avanco_fisico():
    if not current_user.can_access_module('Obras'): # Ou permissão específica
        flash('Acesso negado. Você não tem permissão para adicionar Avanços Físicos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**db_config) as db_base:
            obras_manager = ObrasManager(db_base)
            
            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                percentual_avanco_fisico = float(request.form['percentual_avanco_fisico'].replace(',', '.'))
                data_avanco_str = request.form['data_avanco'].strip()

                # Validação básica
                if not all([id_obras, percentual_avanco_fisico, data_avanco_str]):
                    flash('Campos obrigatórios (Obra, Percentual de Avanço, Data) não podem ser vazios.', 'danger')
                    all_obras = obras_manager.get_all_obras_for_dropdown()
                    return render_template(
                        'obras/avancos_fisicos/add_avanco_fisico.html',
                        user=current_user,
                        all_obras=all_obras,
                        form_data=request.form
                    )
                
                # Converter data
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
                
                # Opcional: Validar se percentual está entre 0 e 100
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
            
            # GET request
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


@app.route('/obras/avancos_fisicos/edit/<int:avanco_id>', methods=['GET', 'POST'])
@login_required
def edit_avanco_fisico(avanco_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
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
                
                # Converter data
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

                # Opcional: Validar se percentual está entre 0 e 100
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
            
            # GET request
            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            # Formatar data para o input type="date"
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


@app.route('/obras/avancos_fisicos/delete/<int:avanco_id>', methods=['POST'])
@login_required
def delete_avanco_fisico(avanco_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/avancos_fisicos/details/<int:avanco_id>')
@login_required
def avanco_fisico_details(avanco_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/avancos_fisicos/export/excel')
@login_required
def export_avancos_fisicos_excel():
    if not current_user.can_access_module('Obras'): # Você pode criar uma permissão específica para exportação
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
                return redirect(url_for('avancos_fisicos_module')) # Redireciona com erro se a data do filtro for inválida

            avancos_data = obras_manager.get_all_avancos_fisicos(
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_data_inicio=search_data_inicio,
                search_data_fim=search_data_fim
            )

            if not avancos_data:
                flash('Nenhum Avanço Físico encontrado para exportar.', 'info')
                return redirect(url_for('avancos_fisicos_module'))

            df = pd.DataFrame(avancos_data)

            # Renomeie colunas para serem mais amigáveis no Excel
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
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
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

# ************************************
# *     submódulo REIDI (OBRAS)      *
# ************************************
# --- ROTAS DO MÓDULO OBRAS: REIDIS ---

@app.route('/obras/reidis')
@login_required
def reidis_module():
    if not current_user.can_access_module('Obras'): # Ou uma permissão específica
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
            status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise'] # Pode ser buscado do DB em um futuro sistema de domínios

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


@app.route('/obras/reidis/add', methods=['GET', 'POST'])
@login_required
def add_reidi():
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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
                status_reidi = request.form.get('status_reidi', '').strip() # Agora pode ser vazio
                observacoes_reidi = request.form.get('observacoes_reidi', '').strip()

                # Validação básica
                if not all([id_obras, numero_portaria, numero_ato_declaratorio]): # Data_Aprovacao_Reidi e Status_Reidi não são mais NOT NULL
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
                
                # Converter datas (se existirem)
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
                
                # Verificar unicidade dos números
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
            
            # GET request
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


@app.route('/obras/reidis/edit/<int:reidi_id>', methods=['GET', 'POST'])
@login_required
def edit_reidi(reidi_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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
                status_reidi = request.form.get('status_reidi', '').strip() # Agora pode ser vazio
                observacoes_reidi = request.form.get('observacoes_reidi', '').strip()

                # Validação básica
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
                
                # Converter datas
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

                # Verificar unicidade dos números, exceto para o REIDI atual
                existing_reidi_portaria = obras_manager.get_reidi_by_numero_portaria(numero_portaria)
                if existing_reidi_portaria and existing_reidi_portaria['ID_Reidis'] != reidi_id:
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

                existing_reidi_ato = obras_manager.get_reidi_by_numero_ato_declaratorio(numero_ato_declaratorio)
                if existing_reidi_ato and existing_reidi_ato['ID_Reidis'] != reidi_id:
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
            
            # GET request
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
            
            # Formatar datas para o input type="date"
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


@app.route('/obras/reidis/delete/<int:reidi_id>', methods=['POST'])
@login_required
def delete_reidi(reidi_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/reidis/details/<int:reidi_id>')
@login_required
def reidi_details(reidi_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/reidis/export/excel')
@login_required
def export_reidis_excel():
    if not current_user.can_access_module('Obras'): # Você pode criar uma permissão específica para exportação
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

            # Renomeie colunas para serem mais amigáveis no Excel
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
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
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

# ************************************
# *   submódulo SEGUROS (OBRAS)      *
# ************************************
# --- ROTAS DO MÓDULO OBRAS: SEGUROS ---

@app.route('/obras/seguros')
@login_required
def seguros_module(): # Este é o ENDPOINT 'seguros_module'
    if not current_user.can_access_module('Obras'): # Ou uma permissão específica
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
            
            # Obter lista de obras para o filtro
            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            # Opções de status e tipo de seguro
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
        flash(f"Erro de banco de dados ao carregar Seguros: {e}", 'danger')
        print(f"Erro de banco de dados em seguros_module: {e}")
        return redirect(url_for('obras_module')) # Volta para o hub de obras
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Seguros: {e}", 'danger')
        print(f"Erro inesperado em seguros_module: {e}")
        return redirect(url_for('obras_module')) # Volta para o hub de obras


@app.route('/obras/seguros/add', methods=['GET', 'POST'])
@login_required
def add_seguro():
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
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
                
                # Converter datas
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
                
                # Verificar unicidade do número da apólice
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
            
            # GET request
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


@app.route('/obras/seguros/edit/<int:seguro_id>', methods=['GET', 'POST'])
@login_required
def edit_seguro(seguro_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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

                # Validação básica
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
                
                # Converter datas
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

                # Verificar unicidade do número da apólice, exceto para o seguro atual
                existing_seguro = obras_manager.get_seguro_by_numero_apolice(numero_apolice)
                if existing_seguro and existing_seguro['ID_Seguros'] != seguro_id:
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
            
            # GET request
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
            tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']
            
            # Formatar datas para o input type="date"
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


@app.route('/obras/seguros/delete/<int:seguro_id>', methods=['POST'])
@login_required
def delete_seguro(seguro_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/seguros/details/<int:seguro_id>')
@login_required
def seguro_details(seguro_id):
    if not current_user.can_access_module('Obras'): # Ou permissão específica
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


@app.route('/obras/seguros/export/excel')
@login_required
def export_seguros_excel():
    if not current_user.can_access_module('Obras'): # Você pode criar uma permissão específica para exportação
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

            # Renomeie colunas para serem mais amigáveis no Excel
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
            
            # Ordenar colunas para melhor visualização no Excel (opcional)
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


# |-----------------------------------------------------------------------|
# | FIM DO MÓDULO OBRAS                                                   |
# |-----------------------------------------------------------------------|

# |-----------------------------------------------------------------------|
# | *************   MÓDULO SEGURANÇA *****************************        |
# |-----------------------------------------------------------------------|

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

# |-----------------------------------------------------------------------|
# | FIM DO MÓDULO SEGURANÇA                                               |
# |-----------------------------------------------------------------------|

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