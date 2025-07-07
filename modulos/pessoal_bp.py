# modulos/pessoal_bp.py

import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime, date

# Para a adição da opção exportar para Excel no módulo Pessoal
from flask import send_file # Adicione este import no topo do seu app.py
import pandas as pd         # Adicione este import no topo do seu app.py
from io import BytesIO      # Adicione este import no topo do seu app.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, Flask, session, get_flashed_messages, jsonify
from flask_login import login_required, current_user, LoginManager, UserMixin, login_user, logout_user 

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_pessoal_manager import PessoalManager

# Crie a instância do Blueprint para o Módulo Pessoal
pessoal_bp = Blueprint('pessoal_bp', __name__, url_prefix='/pessoal')

# Função auxiliar para calcular idade (se ainda estiver em app.py, mova para cá ou para um utils.py)
# Copiei a versão que você me enviou para o app.py.txt
def calculate_age(born_date):
    """Calcula a idade em anos a partir de uma data de nascimento."""
    if not isinstance(born_date, date):
        print(f"DEBUG_CALCULATE_AGE: Data de nascimento inválida ou não é objeto date: {born_date} (Tipo: {type(born_date)}). Retornando None.")
        return None

    today = date.today()
    age = today.year - born_date.year - ((today.month, today.day) < (born_date.month, born_date.day))
    print(f"DEBUG_CALCULATE_AGE: Data Nascimento: {born_date}, Hoje: {today}, Idade Calculada: {age}")
    return age

# ---------------------------------------------------------------
# 2. MÓDULO PESSOAL - HUB
# ---------------------------------------------------------------
@pessoal_bp.route('/')
@login_required
def pessoal_module():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o Módulo Pessoal.', 'warning')
        return redirect(url_for('welcome')) # Redireciona para uma rota geral no app.py

    return render_template('pessoal/pessoal_welcome.html', user=current_user)

# ===============================================================
# 2.1 ROTAS DE FUNCIONÁRIOS - PESSOAL
# ===============================================================
@pessoal_bp.route('/funcionarios')
@login_required
def funcionarios_module():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Funcionários.', 'warning')
        return redirect(url_for('welcome'))

    search_matricula = request.args.get('matricula')
    search_nome = request.args.get('nome')
    search_status = request.args.get('status')
    search_cargo_id = request.args.get('cargo_id')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

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
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar funcionários: {e}", 'danger')
        print(f"Erro inesperado em funcionarios_module: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.1.1 ROTAS DO CRUD DE FUNCIONÁRIOS - CRIAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/funcionarios/add', methods=['GET', 'POST'])
@login_required
def add_funcionario():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                naturalidade = request.form.get('naturalidade', '').strip()
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

                observacoes_doc = request.form.get('observacoes_doc', '').strip()
                link_foto = request.form.get('link_foto', '').strip()

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

                # --- NOVO: Padronização e Validação para campos ENUM (Estado Civil e Gênero) ---
                valid_estado_civil_options = ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel']
                valid_genero_options = ['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar']

                # Valida Estado Civil
                if estado_civil and estado_civil not in valid_estado_civil_options:
                    flash('Valor inválido para Estado Civil. Selecione uma opção válida.', 'danger')
                    return render_template(
                        'pessoal/funcionarios/add_funcionario.html',
                        user=current_user,
                        all_cargos=pessoal_manager.get_all_cargos_for_dropdown(),
                        all_niveis=pessoal_manager.get_all_niveis_for_dropdown(),
                        status_options=['Ativo', 'Inativo', 'Ferias', 'Afastado'],
                        estado_civil_options=valid_estado_civil_options, 
                        genero_options=valid_genero_options, 
                        form_data=request.form.to_dict()
                    )

                # Valida Gênero
                if genero and genero not in valid_genero_options:
                    flash('Valor inválido para Gênero. Selecione uma opção válida.', 'danger')
                    return render_template(
                        'pessoal/funcionarios/add_funcionario.html',
                        user=current_user, all_cargos=pessoal_manager.get_all_cargos_for_dropdown(),
                        all_niveis=pessoal_manager.get_all_niveis_for_dropdown(), status_options=['Ativo', 'Inativo', 'Ferias', 'Afastado'],
                        estado_civil_options=valid_estado_civil_options,
                        genero_options=valid_genero_options,
                        form_data=request.form.to_dict()
                    )

                # Converte strings vazias para None para campos ENUM (se a coluna no DB for NULLable)
                estado_civil = estado_civil if estado_civil else None
                genero = genero if genero else None

                # --- Validação e Conversão de Datas ---
                data_admissao = None
                if data_admissao_str:
                    try:
                        data_admissao = datetime.strptime(data_admissao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Admissão inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template( 
                            'pessoal/funcionarios/add_funcionario.html',
                            user=current_user,
                            all_cargos=pessoal_manager.get_all_cargos_for_dropdown(),
                            all_niveis=pessoal_manager.get_all_niveis_for_dropdown(),
                            status_options=['Ativo', 'Inativo', 'Ferias', 'Afastado'],
                            estado_civil_options=valid_estado_civil_options, 
                            genero_options=valid_genero_options, 
                            form_data=request.form.to_dict()
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
                            estado_civil_options=valid_estado_civil_options,
                            genero_options=valid_genero_options,
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
                            estado_civil_options=valid_estado_civil_options,
                            genero_options=valid_genero_options,
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
                            estado_civil_options=valid_estado_civil_options,
                            genero_options=valid_genero_options,
                            form_data=request.form.to_dict()
                        )

                # --- Validações Adicionais ---
                if not all([matricula, nome_completo, data_admissao, id_cargos, id_niveis, status]):
                    flash('Campos principais (Matrícula, Nome, Data de Admissão, Cargo, Nível, Status) são obrigatórios.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
                    return render_template(
                        'pessoal/funcionarios/add_funcionario.html',
                        user=current_user, all_cargos=all_cargos, all_niveis=all_niveis,
                        status_options=status_options, estado_civil_options=valid_estado_civil_options,
                        genero_options=valid_genero_options, form_data=request.form.to_dict()
                    )

                # Validação para CPF
                if not cpf_numero:
                    flash('O campo CPF é obrigatório e deve ser preenchido.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
                    return render_template(
                        'pessoal/funcionarios/add_funcionario.html',
                        user=current_user, all_cargos=all_cargos, all_niveis=all_niveis,
                        status_options=status_options, estado_civil_options=valid_estado_civil_options,
                        genero_options=valid_genero_options, form_data=request.form.to_dict()
                    )

                # Verificar unicidade da matrícula
                if pessoal_manager.get_funcionario_by_matricula(matricula):
                    flash('Matrícula já existe. Por favor, use uma matrícula única.', 'danger')
                    all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
                    all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
                    status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
                    return render_template(
                        'pessoal/funcionarios/add_funcionario.html',
                        user=current_user, all_cargos=all_cargos, all_niveis=all_niveis,
                        status_options=status_options, estado_civil_options=valid_estado_civil_options,
                        genero_options=valid_genero_options, form_data=request.form.to_dict()
                    )

                # --- SALVAR NO BANCO DE DADOS ---
                success_func = pessoal_manager.add_funcionario(
                    matricula, nome_completo, data_admissao, id_cargos, id_niveis, status
                )

                if success_func:
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

                    logradouro = request.form.get('logradouro', '').strip()
                    numero_end = request.form.get('numero_end', '').strip()
                    complemento = request.form.get('complemento', '').strip()
                    bairro = request.form.get('bairro', '').strip()
                    cidade = request.form.get('cidade', '').strip()
                    estado_end = request.form.get('estado_end', '').strip()
                    cep = request.form.get('cep', '').strip()
                    pessoal_manager.add_funcionario_endereco(
                        matricula, 'Residencial', logradouro, numero_end, complemento, bairro, cidade, estado_end, cep
                    )

                    tel_principal = request.form.get('tel_principal', '').strip()
                    email_pessoal = request.form.get('email_pessoal', '').strip()
                    pessoal_manager.add_funcionario_contato(matricula, 'Telefone Principal', tel_principal)
                    pessoal_manager.add_funcionario_contato(matricula, 'Email Pessoal', email_pessoal)

                    flash('Funcionário adicionado com sucesso!', 'success')
                    return redirect(url_for('pessoal_bp.funcionarios_module'))
                else:
                    flash('Erro ao adicionar funcionário. Verifique os dados e tente novamente.', 'danger')

            # GET request (carregar dropdowns e sugerir matrícula)
            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
            valid_estado_civil_options = ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel']
            valid_genero_options = ['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar']

            next_matricula = pessoal_manager.generate_next_matricula()

            return render_template(
                'pessoal/funcionarios/add_funcionario.html',
                user=current_user,
                all_cargos=all_cargos,
                all_niveis=all_niveis,
                status_options=status_options,
                estado_civil_options=valid_estado_civil_options,
                genero_options=valid_genero_options,
                next_matricula=next_matricula,
                form_data={} 
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_funcionario: {e}")
        return redirect(url_for('pessoal_bp.funcionarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_funcionario: {e}")
        return redirect(url_for('pessoal_bp.funcionarios_module'))

# ---------------------------------------------------------------
# 2.1.2 ROTAS DO CRUD DE FUNCIONÁRIOS - EDITAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/funcionarios/edit/<string:matricula>', methods=['GET', 'POST'])
@login_required
def edit_funcionario(matricula):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            
            funcionario = pessoal_manager.get_funcionario_by_matricula(matricula)
            
            if not funcionario:
                flash('Funcionário não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.funcionarios_module'))

            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Ferias', 'Afastado']
            
            estado_civil_options = ['Solteiro(a)', 'Casado(a)', 'Divorciado(a)', 'Viuvo(a)', 'Uniao Estavel']
            genero_options = ['Masculino', 'Feminino', 'Outro', 'Prefiro nao informar']

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                new_matricula = form_data_received.get('matricula', '').strip()
                nome_completo = form_data_received.get('nome_completo', '').strip()
                data_admissao_str = form_data_received.get('data_admissao', '').strip()
                
                data_admissao = None
                if data_admissao_str:
                    try:
                        data_admissao = datetime.strptime(data_admissao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Admissão inválido. Use AAAA-MM-DD.', 'danger')
                        return render_template( # <-- Adicionado ou garantido 'return' aqui
                            'pessoal/funcionarios/edit_funcionario.html',
                            user=current_user, funcionario=form_data_received, 
                            all_cargos=all_cargos, all_niveis=all_niveis,
                            status_options=status_options, estado_civil_options=estado_civil_options, 
                            genero_options=genero_options 
                        )

                # --- Novo Bloco TRY/EXCEPT para a lógica de POST, como fizemos em users_bp ---
                try:
                    # As variáveis new_matricula, nome_completo, data_admissao, id_cargos, id_niveis, status
                    # são usadas em várias validações a seguir.
                    # Assegure-se de que id_cargos e id_niveis sejam int ou 0 caso não venham do form
                    try:
                        id_cargos = int(request.form.get('id_cargos', 0))
                    except ValueError:
                        id_cargos = 0
                    try:
                        id_niveis = int(request.form.get('id_niveis', 0))
                    except ValueError:
                        id_niveis = 0

                    status = request.form.get('status', '').strip()

                    # Captura dos demais campos
                    data_nascimento_str = request.form.get('data_nascimento', '').strip()
                    estado_civil = request.form.get('estado_civil', '').strip()
                    nacionalidade = request.form.get('nacionalidade', '').strip()
                    naturalidade = request.form.get('naturalidade', '').strip() 
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
                    
                    observacoes_doc = request.form.get('observacoes_doc', '').strip()
                    link_foto = request.form.get('link_foto', '').strip()

                    # --- Validação para campos ENUM (Estado Civil e Gênero) ---
                    if estado_civil and estado_civil not in estado_civil_options: 
                        flash('Valor inválido para Estado Civil. Selecione uma opção válida.', 'danger')
                        return render_template( # <-- Adicionado ou garantido 'return' aqui
                            'pessoal/funcionarios/edit_funcionario.html',
                            user=current_user, funcionario=form_data_received, 
                            all_cargos=all_cargos, all_niveis=all_niveis,
                            status_options=status_options, estado_civil_options=estado_civil_options,
                            genero_options=genero_options
                        )
                    
                    if genero and genero not in genero_options: 
                        flash('Valor inválido para Gênero. Selecione uma opção válida.', 'danger')
                        return render_template( # <-- Adicionado ou garantido 'return' aqui
                            'pessoal/funcionarios/edit_funcionario.html',
                            user=current_user, funcionario=form_data_received, 
                            all_cargos=all_cargos, all_niveis=all_niveis,
                            status_options=status_options, estado_civil_options=estado_civil_options,
                            genero_options=genero_options
                        )

                    estado_civil = estado_civil if estado_civil else None
                    genero = genero if genero else None

                    data_nascimento = None
                    if data_nascimento_str:
                        try:
                            data_nascimento = datetime.strptime(data_nascimento_str, '%Y-%m-%d').date()
                        except ValueError:
                            flash('Formato de Data de Nascimento inválido. Use AAAA-MM-DD.', 'danger')
                            return render_template( # <-- Adicionado ou garantido 'return' aqui
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
                            return render_template( # <-- Adicionado ou garantido 'return' aqui
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
                            return render_template( # <-- Adicionado ou garantido 'return' aqui
                                'pessoal/funcionarios/edit_funcionario.html',
                                user=current_user, funcionario=form_data_received, 
                                all_cargos=all_cargos, all_niveis=all_niveis,
                                status_options=status_options, estado_civil_options=estado_civil_options,
                                genero_options=genero_options
                            )

                    is_valid = True
                    if not all([new_matricula, nome_completo, data_admissao, id_cargos, id_niveis, status]):
                        flash('Campos principais (Matrícula, Nome, Data de Admissão, Cargo, Nível, Status) são obrigatórios.', 'danger')
                        is_valid = False
                    
                    if not cpf_numero:
                        flash('O campo CPF é obrigatório e deve ser preenchido.', 'danger')
                        is_valid = False

                    if new_matricula != matricula:
                        existing_funcionario_by_new_matricula = pessoal_manager.get_funcionario_by_matricula(new_matricula)
                        if existing_funcionario_by_new_matricula:
                            flash('Nova matrícula já existe. Por favor, use uma matrícula única.', 'danger')
                            is_valid = False

                    # Se a validação final (is_valid) falhar, retorna o template com os dados do formulário
                    if not is_valid: # <-- ESTE É O RETURN PRINCIPAL QUE AGORA VAI CAPTURAR MAIS ERROS
                        return render_template(
                            'pessoal/funcionarios/edit_funcionario.html',
                            user=current_user, funcionario=form_data_received, 
                            all_cargos=all_cargos, all_niveis=all_niveis,
                            status_options=status_options, estado_civil_options=estado_civil_options,
                            genero_options=genero_options
                        )

                    success_func = pessoal_manager.update_funcionario(
                        matricula, new_matricula, nome_completo, data_admissao, id_cargos, id_niveis, status
                    )
                    
                    if success_func:
                        success_docs = pessoal_manager.save_funcionario_dados_pessoais_documentos(
                            new_matricula,
                            data_nascimento, estado_civil, nacionalidade, naturalidade, genero,
                            rg_numero, rg_orgao_emissor, rg_uf_emissor, rg_data_emissao,
                            cpf_numero,
                            ctps_numero, ctps_serie,
                            pispasep,
                            cnh_numero, cnh_categoria, cnh_data_validade, cnh_orgao_emissor,
                            titeleitor_numero, titeleitor_zona, titeleitor_secao,
                            observacoes_doc, link_foto
                        )

                        logradouro = request.form.get('logradouro', '').strip()
                        numero_end = request.form.get('numero_end', '').strip()
                        complemento = request.form.get('complemento', '').strip()
                        bairro = request.form.get('bairro', '').strip()
                        cidade = request.form.get('cidade', '').strip()
                        estado_end = request.form.get('estado_end', '').strip()
                        cep = request.form.get('cep', '').strip()
                        pessoal_manager.update_or_add_funcionario_endereco(
                            new_matricula, 'Residencial', logradouro, numero_end, complemento, bairro, cidade, estado_end, cep
                        )

                        tel_principal = request.form.get('tel_principal', '').strip()
                        email_pessoal = request.form.get('email_pessoal', '').strip()
                        pessoal_manager.update_or_add_funcionario_contato(
                            new_matricula, 'Telefone Principal', tel_principal
                        )
                        pessoal_manager.update_or_add_funcionario_contato(
                            new_matricula, 'Email Pessoal', email_pessoal
                        )

                        flash('Funcionário atualizado com sucesso!', 'success')
                        return redirect(url_for('pessoal_bp.funcionarios_module'))
                    else:
                        flash('Erro ao atualizar funcionário. Verifique os dados e tente novamente.', 'danger')
                except mysql.connector.Error as e: # Este except é para erros de DB do POST
                    flash(f"Erro de banco de dados: {e}", 'danger')
                    print(f"Erro de banco de dados no POST de edit_funcionario: {e}")
                except Exception as e: # Este except é para erros gerais do POST
                    flash(f"Ocorreu um erro inesperado: {e}", 'danger')
                    print(f"Erro inesperado no POST de edit_funcionario: {e}")
                
                # Este return render_template é para quando o POST não foi bem-sucedido
                # mas não deu um erro fatal ou de validação que já tivesse um return.
                # Ele deve estar alinhado com o if request.method == 'POST':
                return render_template(
                    'pessoal/funcionarios/edit_funcionario.html',
                    user=current_user, funcionario=form_data_received, # Use form_data_received para repopular
                    all_cargos=all_cargos, all_niveis=all_niveis,
                    status_options=status_options, estado_civil_options=estado_civil_options,
                    genero_options=genero_options
                )
            
            else: # GET request (alinhado com o if request.method == 'POST':)
                data_to_pass_to_template = funcionario.copy() 

                # Converte explicitamente None para string vazia para campos de texto/select
                text_fields_to_format = [
                    'Rg_Numero', 'Rg_OrgaoEmissor', 'Rg_UfEmissor', 'Cpf_Numero',
                    'Ctps_Numero', 'Ctps_Serie', 'Pispasep', 'Cnh_Numero',
                    'Cnh_Categoria', 'Cnh_OrgaoEmissor', 'TitEleitor_Numero',
                    'TitEleitor_Zona', 'TitEleitor_Secao', 'Observacoes', 'Link_Foto',
                    'Estado_Civil', 'Genero', 'Nacionalidade', 'Naturalidade'
                ]
                for key in text_fields_to_format:
                    if key in data_to_pass_to_template and data_to_pass_to_template[key] is None:
                        data_to_pass_to_template[key] = ''

                # Campos de Endereço:
                # Se o seu get_funcionario_by_matricula já traz esses dados consolidados no mesmo dicionário 'funcionario',
                # então os nomes abaixo devem ser as chaves que ele retorna para endereço.
                # No seu db_pessoal_manager.py.txt (get_all_funcionarios_completo), os nomes são prefixedos (End_Logradouro, etc.)
                # mas em get_funcionario_by_matricula (que é o que está sendo chamado aqui), pode ser diferente.
                # Vamos mapear aqui para os nomes que o template espera (sem prefixo).
                # Se get_funcionario_by_matricula já retorna direto Logradouro, Numero, etc., este mapeamento pode ser mais simples.

                # Para garantir que o GET pegue os dados corretos de endereço e contato do 'funcionario' e os mapeie corretamente
                # para os nomes que o template 'edit_funcionario.html' espera (logradouro, numero_end, etc.),
                # precisamos fazer este mapeamento explícito, pois a query get_funcionario_by_matricula
                # do seu db_pessoal_manager.py não inclui os JOINS para endereço/contato, mas sim para funcionarios_documentos.
                # A get_all_funcionarios_completo do db_pessoal_manager é que tem os JOINS completos.
                # Isso significa que get_funcionario_by_matricula PRECISA ser atualizada para trazer TUDO.

                # VOU ASSUMIR QUE O SEU get_funcionario_by_matricula EM db_pessoal_manager.py
                # JÁ ESTÁ CONSOLIDADO PARA TRAZER ENDEREÇOS E CONTATOS, OU FAZENDO ISSO SEPARADAMENTE.
                # No entanto, ao analisar db_pessoal_manager.py.txt (get_funcionario_by_matricula), ele SÓ FAZ JOIN COM funcionarios_documentos.
                # Isso explica por que "logradouro", "numero_end", etc. não seriam encontrados em 'funcionario' diretamente.

                # CORREÇÃO PARA GARANTIR QUE OS DADOS DE ENDEREÇO E CONTATO SEJAM MAPEADOS.
                # ONDE ESTÁ A BUSCA POR 'funcionario_enderecos' e 'funcionario_contatos' em seu pessoal_bp.py?
                # No seu código anterior, você já tinha estas linhas:
                # funcionario_enderecos = pessoal_manager.get_funcionario_enderecos_by_matricula(matricula)
                # funcionario_contatos = pessoal_manager.get_funcionario_contatos_by_matricula(matricula)
                # Elas devem estar no bloco 'else' do GET, ANTES do return render_template.
                
                # Vamos adicionar essas chamadas e o mapeamento DENTRO DO ELSE DO GET:
                funcionario_enderecos = pessoal_manager.get_funcionario_enderecos_by_matricula(matricula)
                funcionario_contatos = pessoal_manager.get_funcionario_contatos_by_matricula(matricula)

                if funcionario_enderecos:
                    res_endereco = next((end for end in funcionario_enderecos if end.get('Tipo_Endereco') == 'Residencial'), None)
                    if not res_endereco and funcionario_enderecos:
                        res_endereco = funcionario_enderecos[0] # Pega o primeiro se não for residencial
                    if res_endereco:
                        data_to_pass_to_template['logradouro'] = res_endereco.get('Logradouro', '')
                        data_to_pass_to_template['numero_end'] = res_endereco.get('Numero', '')
                        data_to_pass_to_template['complemento'] = res_endereco.get('Complemento', '')
                        data_to_pass_to_template['bairro'] = res_endereco.get('Bairro', '')
                        data_to_pass_to_template['cidade'] = res_endereco.get('Cidade', '')
                        data_to_pass_to_template['estado_end'] = res_endereco.get('Estado', '')
                        data_to_pass_to_template['cep'] = res_endereco.get('Cep', '')

                if funcionario_contatos:
                    tel_principal = next((cont for cont in funcionario_contatos if cont.get('Tipo_Contato') == 'Telefone Principal'), None)
                    if tel_principal:
                        data_to_pass_to_template['tel_principal'] = tel_principal.get('Valor_Contato', '')
                    email_pessoal = next((cont for cont in funcionario_contatos if cont.get('Tipo_Contato') == 'Email Pessoal'), None)
                    if email_pessoal:
                        data_to_pass_to_template['email_pessoal'] = email_pessoal.get('Valor_Contato', '')
                
                # Formatar datas para o input type="date"
                date_fields_for_template_format = [ # Renomeado para evitar conflito com date_fields_to_format geral
                    'Data_Admissao', 'Data_Nascimento', 'Rg_DataEmissao', 'Cnh_DataValidade'
                ]
                for key in date_fields_for_template_format:
                    if key in data_to_pass_to_template:
                        val = data_to_pass_to_template[key]
                        if isinstance(val, date):
                            data_to_pass_to_template[key] = val.strftime('%Y-%m-%d')
                        elif val is None:
                            data_to_pass_to_template[key] = ''

                return render_template(
                    'pessoal/funcionarios/edit_funcionario.html',
                    user=current_user,
                    funcionario=data_to_pass_to_template, 
                    all_cargos=all_cargos,
                    all_niveis=all_niveis,
                    status_options=status_options,
                    estado_civil_options=estado_civil_options, 
                    genero_options=genero_options 
                )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_funcionario: {e}")
        return redirect(url_for('pessoal_bp.funcionarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_funcionario: {e}")
        return redirect(url_for('pessoal_bp.funcionarios_module'))

# ---------------------------------------------------------------
# 2.1.3 ROTAS DO CRUD DE FUNCIONÁRIOS - DELETAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/funcionarios/delete/<string:matricula>', methods=['POST'])
@login_required
def delete_funcionario(matricula):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base) 
            success = pessoal_manager.delete_funcionario(matricula)
            if success:
                flash('Funcionário excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir funcionário. Verifique se ele existe.', 'danger')
        return redirect(url_for('pessoal_bp.funcionarios_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_funcionario: {e}")
        return redirect(url_for('pessoal_bp.funcionarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_funcionario: {e}")
        return redirect(url_for('pessoal_bp.funcionarios_module'))

# ---------------------------------------------------------------
# 2.1.4 ROTAS DO CRUD DE FUNCIONÁRIOS - DETALHES - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/funcionarios/details/<string:matricula>')
@login_required
def funcionario_details(matricula):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            funcionario = pessoal_manager.get_funcionario_by_matricula(matricula)

            if not funcionario:
                flash('Funcionário não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.funcionarios_module'))

            funcionario_enderecos = pessoal_manager.get_funcionario_enderecos_by_matricula(matricula)
            funcionario_contatos = pessoal_manager.get_funcionario_contatos_by_matricula(matricula)

        return render_template(
            'pessoal/funcionarios/funcionario_details.html',
            user=current_user,
            funcionario=funcionario, 
            funcionario_enderecos=funcionario_enderecos,
            funcionario_contatos=funcionario_contatos
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em funcionario_details: {e}")
        return redirect(url_for('pessoal_bp.funcionarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em funcionario_details: {e}")
        return redirect(url_for('pessoal_bp.funcionarios_module'))

# ---------------------------------------------------------------
# 2.1.5 ROTA DE FUNCIONÁRIOS - EXPORTAR P/ EXCEL - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/funcionarios/export/excel')
@login_required
def export_funcionarios_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de funcionários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base) 

            search_matricula = request.args.get('matricula')
            search_nome = request.args.get('nome')
            search_status = request.args.get('status')
            search_cargo_id = request.args.get('cargo_id')

            funcionarios_data = pessoal_manager.get_all_funcionarios_completo(
                search_matricula=search_matricula,
                search_nome=search_nome,
                search_status=search_status,
                search_cargo_id=search_cargo_id
            )

            if not funcionarios_data:
                flash('Nenhum funcionário encontrado para exportar.', 'info')
                return redirect(url_for('pessoal_bp.funcionarios_module'))

            df = pd.DataFrame(funcionarios_data)

            df = df.rename(columns={
                'Matricula': 'Matrícula',
                'Nome_Completo': 'Nome Completo',
                'Data_Admissao': 'Data de Admissão',
                'Nome_Cargo': 'Cargo',
                'Nome_Nivel': 'Nível',
                'Status': 'Status',
                'Data_Nascimento': 'Data de Nascimento',
                'Estado_Civil': 'Estado Civil',
                'Nacionalidade': 'Nacionalidade',
                'Naturalidade': 'Naturalidade',
                'Genero': 'Gênero',
                'Rg_Numero': 'RG Nº', 
                'Rg_OrgaoEmissor': 'RG Órgão Emissor', 
                'Rg_UfEmissor': 'RG UF Emissor', 
                'Rg_DataEmissao': 'RG Data Emissão', 
                'Cpf_Numero': 'CPF', 
                'Ctps_Numero': 'CTPS Nº', 
                'Ctps_Serie': 'CTPS Série', 
                'Pispasep': 'PIS/PASEP', 
                'Cnh_Numero': 'CNH Nº', 
                'Cnh_Categoria': 'CNH Categoria', 
                'Cnh_DataValidade': 'CNH Data Validade', 
                'Cnh_OrgaoEmissor': 'CNH Órgão Emissor', 
                'TitEleitor_Numero': 'Título Eleitor Nº', 
                'TitEleitor_Zona': 'Título Eleitor Zona', 
                'TitEleitor_Secao': 'Título Eleitor Seção', 
                'Doc_Observacoes': 'Observações Documentos', 
                'Link_Foto': 'Link da Foto', 
                'End_Logradouro': 'Endereço Logradouro', 
                'End_Numero': 'Endereço Número',
                'End_Complemento': 'Endereço Complemento',
                'End_Bairro': 'Endereço Bairro',
                'End_Cidade': 'Endereço Cidade',
                'End_Estado': 'Endereço Estado',
                'End_Cep': 'Endereço CEP',
                'Tel_Principal': 'Telefone Principal',
                'Email_Pessoal': 'Email Pessoal',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })

            ordered_columns = [
                'Matrícula', 'Nome Completo', 'Status', 'Cargo', 'Nível',
                'Data de Admissão', 'Data de Nascimento', 'Estado Civil', 'Nacionalidade', 'Naturalidade', 'Gênero',
                'CPF', 'RG Nº', 'Rg_OrgaoEmissor', 'Rg_UfEmissor', 'RG Data Emissão',
                'CTPS Nº', 'CTPS Série', 'PIS/PASEP',
                'CNH Nº', 'CNH Categoria', 'CNH Data Validade', 'CNH Órgão Emissor',
                'Título Eleitor Nº', 'Título Eleitor Zona', 'Título Eleitor Seção',
                'Observações Documentos', 'Link da Foto',
                'Endereço Logradouro', 'Endereço Número', 'Endereço Complemento', 'Endereço Bairro',
                'Endereço Cidade', 'Endereço Estado', 'Endereço CEP',
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
        return redirect(url_for('pessoal_bp.funcionarios_module'))

# ===============================================================
# 2.2 ROTAS DE CARGOS - PESSOAL
# ===============================================================
@pessoal_bp.route('/cargos')
@login_required
def cargos_module():
    if not current_user.can_access_module('Pessoal'): 
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Cargos.', 'warning')
        return redirect(url_for('welcome'))

    search_nome = request.args.get('nome_cargo')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar cargos: {e}", 'danger')
        print(f"Erro inesperado em cargos_module: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.2.1 ROTAS DO CRUD DE CARGOS - CRIAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/cargos/add', methods=['GET', 'POST'])
@login_required
def add_cargo():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                    return redirect(url_for('pessoal_bp.cargos_module'))
                else:
                    flash('Erro ao adicionar cargo. Verifique os dados e tente novamente.', 'danger')

            return render_template(
                'pessoal/cargos/add_cargo.html',
                user=current_user,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_cargo: {e}")
        return redirect(url_for('pessoal_bp.cargos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_cargo: {e}")
        return redirect(url_for('pessoal_bp.cargos_module'))

# ---------------------------------------------------------------
# 2.2.2 ROTAS DO CRUD DE CARGOS - EDITAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/cargos/edit/<int:cargo_id>', methods=['GET', 'POST'])
@login_required
def edit_cargo(cargo_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            cargo = pessoal_manager.get_cargo_by_id(cargo_id)

            if not cargo:
                flash('Cargo não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.cargos_module'))

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
                    return redirect(url_for('pessoal_bp.cargos_module'))
                else:
                    flash('Erro ao atualizar cargo.', 'danger')

            return render_template(
                'pessoal/cargos/edit_cargo.html',
                user=current_user,
                cargo=cargo
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_cargo: {e}")
        return redirect(url_for('pessoal_bp.cargos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_cargo: {e}")
        return redirect(url_for('pessoal_bp.cargos_module'))

# ---------------------------------------------------------------
# 2.2.3 ROTAS DO CRUD DE CARGOS - DELETAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/cargos/delete/<int:cargo_id>', methods=['POST'])
@login_required
def delete_cargo(cargo_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_cargo(cargo_id)
            if success:
                flash('Cargo excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir cargo. Certifique-se de que não há funcionários associados a ele.', 'danger')
        return redirect(url_for('pessoal_bp.cargos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_cargo: {e}")
        return redirect(url_for('pessoal_bp.cargos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_cargo: {e}")
        return redirect(url_for('pessoal_bp.cargos_module'))

# ---------------------------------------------------------------
# 2.2.4 ROTAS DO CRUD DE CARGOS - DETALHES - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/cargos/details/<int:cargo_id>')
@login_required
def cargo_details(cargo_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            cargo = pessoal_manager.get_cargo_by_id(cargo_id)

            if not cargo:
                flash('Cargo não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.cargos_module'))

        return render_template(
            'pessoal/cargos/cargo_details.html',
            user=current_user,
            cargo=cargo
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em cargo_details: {e}")
        return redirect(url_for('pessoal_bp.cargos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em cargo_details: {e}")
        return redirect(url_for('pessoal_bp.cargos_module'))

# ---------------------------------------------------------------
# 2.2.5 ROTA DE CARGOS - EXPORTAR P/ EXCEL - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/cargos/export/excel')
@login_required
def export_cargos_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de cargos.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            search_nome = request.args.get('nome_cargo')
            cargos_data = pessoal_manager.get_all_cargos(search_nome=search_nome)

            if not cargos_data:
                flash('Nenhum cargo encontrado para exportar.', 'info')
                return redirect(url_for('pessoal_bp.cargos_module'))

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
        return redirect(url_for('pessoal_bp.cargos_module'))

# ===============================================================
# 2.3 ROTAS DE NIVEIS - PESSOAL
# ===============================================================
@pessoal_bp.route('/niveis')
@login_required
def niveis_module():
    if not current_user.can_access_module('Pessoal'): 
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Níveis.', 'warning')
        return redirect(url_for('welcome'))

    search_nome = request.args.get('nome_nivel')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar níveis: {e}", 'danger')
        print(f"Erro inesperado em niveis_module: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.3.1 ROTAS DO CRUD DE NIVEIS - CRIAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/niveis/add', methods=['GET', 'POST'])
@login_required
def add_nivel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                    return redirect(url_for('pessoal_bp.niveis_module'))
                else:
                    flash('Erro ao adicionar nível. Verifique os dados e tente novamente.', 'danger')

            return render_template(
                'pessoal/niveis/add_nivel.html',
                user=current_user,
                form_data={}
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_nivel: {e}")
        return redirect(url_for('pessoal_bp.niveis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_nivel: {e}")
        return redirect(url_for('pessoal_bp.niveis_module'))

# ---------------------------------------------------------------
# 2.3.2 ROTAS DO CRUD DE NIVEIS - EDITAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/niveis/edit/<int:nivel_id>', methods=['GET', 'POST'])
@login_required
def edit_nivel(nivel_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            nivel = pessoal_manager.get_nivel_by_id(nivel_id)

            if not nivel:
                flash('Nível não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.niveis_module'))

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
                    return redirect(url_for('pessoal_bp.niveis_module'))
                else:
                    flash('Erro ao atualizar nível.', 'danger')

            return render_template(
                'pessoal/niveis/edit_nivel.html',
                user=current_user,
                nivel=nivel
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_nivel: {e}")
        return redirect(url_for('pessoal_bp.niveis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_nivel: {e}")
        return redirect(url_for('pessoal_bp.niveis_module'))

# ---------------------------------------------------------------
# 2.3.3 ROTAS DO CRUD DE NIVEIS - DELETAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/niveis/delete/<int:nivel_id>', methods=['POST'])
@login_required
def delete_nivel(nivel_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_nivel(nivel_id)
            if success:
                flash('Nível excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir nível. Certifique-se de que não há funcionários associados a ele.', 'danger')
        return redirect(url_for('pessoal_bp.niveis_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_nivel: {e}")
        return redirect(url_for('pessoal_bp.niveis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_nivel: {e}")
        return redirect(url_for('pessoal_bp.niveis_module'))

# ---------------------------------------------------------------
# 2.3.4 ROTAS DO CRUD DE NIVEIS - DETALHES - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/niveis/details/<int:nivel_id>')
@login_required
def nivel_details(nivel_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            nivel = pessoal_manager.get_nivel_by_id(nivel_id)

            if not nivel:
                flash('Nível não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.niveis_module'))

        return render_template(
            'pessoal/niveis/nivel_details.html',
            user=current_user,
            nivel=nivel
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em nivel_details: {e}")
        return redirect(url_for('pessoal_bp.niveis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em nivel_details: {e}")
        return redirect(url_for('pessoal_bp.niveis_module'))

# ---------------------------------------------------------------
# 2.3.5 ROTA DE NIVEIS - EXPORTAR P/ EXCEL - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/niveis/export/excel')
@login_required
def export_niveis_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de níveis.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            search_nome = request.args.get('nome_nivel')
            niveis_data = pessoal_manager.get_all_niveis(search_nome=search_nome)

            if not niveis_data:
                flash('Nenhum nível encontrado para exportar.', 'info')
                return redirect(url_for('pessoal_bp.niveis_module'))

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
        return redirect(url_for('pessoal_bp.niveis_module'))

# ===============================================================
# 2.4 ROTAS DE SALARIOS - PESSOAL
# ===============================================================
@pessoal_bp.route('/salarios')
@login_required
def salarios_module():
    if not current_user.can_access_module('Pessoal'): 
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Salários.', 'warning')
        return redirect(url_for('welcome'))

    search_cargo_id = request.args.get('cargo_id')
    search_nivel_id = request.args.get('nivel_id')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Salários: {e}", 'danger')
        print(f"Erro inesperado em salarios_module: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.4.1 ROTAS DO CRUD DE SALARIOS - CRIAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/salarios/add', methods=['GET', 'POST'])
@login_required
def add_salario():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()

            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

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
                    form_data_to_template = form_data_received
                    return render_template(
                        'pessoal/salarios/add_salario.html',
                        user=current_user,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=form_data_to_template
                    )

                try:
                    data_vigencia = datetime.strptime(data_vigencia_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Vigência inválido. Use AAAA-MM-DD.', 'danger')
                    form_data_to_template = form_data_received
                    return render_template(
                        'pessoal/salarios/add_salario.html',
                        user=current_user,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=form_data_to_template
                    )

                if pessoal_manager.get_salario_by_cargo_nivel_vigencia(id_cargos, id_niveis, data_vigencia):
                    flash('Já existe um pacote salarial para esta combinação de Cargo, Nível e Data de Vigência.', 'danger')
                    form_data_to_template = form_data_received
                    return render_template(
                        'pessoal/salarios/add_salario.html',
                        user=current_user,
                        all_cargos=all_cargos,
                        all_niveis=all_niveis,
                        form_data=form_data_to_template
                    )

                success = pessoal_manager.add_salario(
                    id_cargos, id_niveis, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia
                )
                if success:
                    flash('Pacote salarial adicionado com sucesso!', 'success')
                    return redirect(url_for('pessoal_bp.salarios_module'))
                else:
                    flash('Erro ao adicionar pacote salarial. Verifique os dados e tente novamente.', 'danger')

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
        return redirect(url_for('pessoal_bp.salarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_salario: {e}")
        return redirect(url_for('pessoal_bp.salarios_module'))

# ---------------------------------------------------------------
# 2.4.2 ROTAS DO CRUD DE SALARIOS - EDITAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/salarios/edit/<int:salario_id>', methods=['GET', 'POST'])
@login_required
def edit_salario(salario_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            salario = pessoal_manager.get_salario_by_id(salario_id)

            if not salario:
                flash('Pacote salarial não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.salarios_module'))

            all_cargos = pessoal_manager.get_all_cargos_for_dropdown()
            all_niveis = pessoal_manager.get_all_niveis_for_dropdown()

            form_data_to_template = {} 

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

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

                is_valid = True

                if not all([id_cargos, id_niveis, salario_base, data_vigencia_str]):
                    flash('Campos obrigatórios (Cargo, Nível, Salário Base, Data Vigência) não podem ser vazios.', 'danger')
                    is_valid = False

                data_vigencia = None
                try:
                    data_vigencia = datetime.strptime(data_vigencia_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de Data de Vigência inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False

                existing_salario = pessoal_manager.get_salario_by_cargo_nivel_vigencia(id_cargos, id_niveis, data_vigencia)
                if existing_salario and existing_salario['ID_Salarios'] != salario_id:
                    flash('Já existe um pacote salarial para esta combinação de Cargo, Nível e Data de Vigência.', 'danger')
                    is_valid = False

                form_data_to_template = form_data_received
                form_data_to_template['data_vigencia'] = data_vigencia_str
                form_data_to_template['periculosidade'] = periculosidade
                form_data_to_template['insalubridade'] = insalubridade
                form_data_to_template['cesta_basica'] = cesta_basica


                if is_valid:
                    success = pessoal_manager.update_salario(
                        salario_id, id_cargos, id_niveis, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia
                    )
                    if success:
                        flash('Pacote salarial atualizado com sucesso!', 'success')
                        return redirect(url_for('pessoal_bp.salarios_module'))
                    else:
                        flash('Erro ao atualizar pacote salarial. Verifique os dados e tente novamente.', 'danger')

            else: # GET request
                form_data_to_template = salario.copy()
                form_data_to_template['Data_Vigencia'] = form_data_to_template['Data_Vigencia'].strftime('%Y-%m-%d') if form_data_to_template['Data_Vigencia'] else ''
                form_data_to_template['Periculosidade'] = bool(form_data_to_template.get('Periculosidade'))
                form_data_to_template['Insalubridade'] = bool(form_data_to_template.get('Insalubridade'))
                form_data_to_template['Cesta_Basica'] = bool(form_data_to_template.get('Cesta_Basica'))

            return render_template(
                'pessoal/salarios/edit_salario.html',
                user=current_user,
                salario=form_data_to_template,
                all_cargos=all_cargos,
                all_niveis=all_niveis
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_salario: {e}")
        return redirect(url_for('pessoal_bp.salarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_salario: {e}")
        return redirect(url_for('pessoal_bp.salarios_module'))

# ---------------------------------------------------------------
# 2.4.3 ROTAS DO CRUD DE SALARIOS - DELETAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/salarios/delete/<int:salario_id>', methods=['POST'])
@login_required
def delete_salario(salario_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_salario(salario_id)
            if success:
                flash('Pacote salarial excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir pacote salarial. Verifique se ele existe.', 'danger')
        return redirect(url_for('pessoal_bp.salarios_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_salario: {e}")
        return redirect(url_for('pessoal_bp.salarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_salario: {e}")
        return redirect(url_for('pessoal_bp.salarios_module'))

# ---------------------------------------------------------------
# 2.4.4 ROTAS DO CRUD DE SALARIOS - DETALHES - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/salarios/details/<int:salario_id>')
@login_required
def salario_details(salario_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            salario = pessoal_manager.get_salario_by_id(salario_id)

            if not salario:
                flash('Pacote salarial não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.salarios_module'))

        return render_template(
            'pessoal/salarios/salario_details.html',
            user=current_user,
            salario=salario
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em salario_details: {e}")
        return redirect(url_for('pessoal_bp.salarios_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em salario_details: {e}")
        return redirect(url_for('pessoal_bp.salarios_module'))

# ---------------------------------------------------------------
# 2.4.5 ROTAS DE SALARIOS - EXPORTAR P/ EXCEL - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/salarios/export/excel')
@login_required
def export_salarios_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Salários.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            search_cargo_id = request.args.get('cargo_id')
            search_nivel_id = request.args.get('nivel_id')

            salarios_data = pessoal_manager.get_all_salarios(
                search_cargo_id=int(search_cargo_id) if search_cargo_id else None,
                search_nivel_id=int(search_nivel_id) if search_nivel_id else None
            )

            if not salarios_data:
                flash('Nenhum pacote salarial encontrado para exportar.', 'info')
                return redirect(url_for('pessoal_bp.salarios_module'))

            df = pd.DataFrame(salarios_data)

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

            df['Periculosidade'] = df['Periculosidade'].apply(lambda x: 'Sim' if x else 'Não')
            df['Insalubridade'] = df['Insalubridade'].apply(lambda x: 'Sim' if x else 'Não')
            df['Cesta_Basica'] = df['Cesta_Basica'].apply(lambda x: 'Sim' if x else 'Não')

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
        return redirect(url_for('pessoal_bp.salarios_module'))

# ===============================================================
# 2.5 ROTAS DE FERIAS - PESSOAL
# ===============================================================
@pessoal_bp.route('/ferias')
@login_required
def ferias_module():
    if not current_user.can_access_module('Pessoal'): 
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Férias.', 'warning')
        return redirect(url_for('welcome'))

    search_matricula = request.args.get('matricula')
    search_status = request.args.get('status')
    search_periodo_inicio = request.args.get('periodo_inicio')
    search_periodo_fim = request.args.get('periodo_fim')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            ferias = pessoal_manager.get_all_ferias(
                search_matricula=search_matricula,
                search_status=search_status,
                search_periodo_inicio=datetime.strptime(search_periodo_inicio, '%Y-%m-%d').date() if search_periodo_inicio else None,
                search_periodo_fim=datetime.strptime(search_periodo_fim, '%Y-%m-%d').date() if search_periodo_fim else None
            )

            all_funcionarios = pessoal_manager.get_all_funcionarios()

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
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Férias: {e}", 'danger')
        print(f"Erro inesperado em ferias_module: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.5.1 ROTAS DO CRUD DE FERIAS - CRIAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/ferias/add', methods=['GET', 'POST'])
@login_required
def add_ferias():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            all_funcionarios = pessoal_manager.get_all_funcionarios()
            status_options = ['Programada', 'Aprovada', 'Gozo', 'Concluída', 'Cancelada']

            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

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

                form_data_to_template = form_data_received
                form_data_to_template['periodo_aquisitivo_inicio'] = periodo_aquisitivo_inicio.strftime('%Y-%m-%d') if periodo_aquisitivo_inicio else ''
                form_data_to_template['periodo_aquisitivo_fim'] = periodo_aquisitivo_fim.strftime('%Y-%m-%d') if periodo_aquisitivo_fim else ''
                form_data_to_template['data_inicio_gozo'] = data_inicio_gozo.strftime('%Y-%m-%d') if data_inicio_gozo else ''
                form_data_to_template['data_fim_gozo'] = data_fim_gozo.strftime('%Y-%m-%d') if data_fim_gozo else ''

                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                dias_gozo = int(form_data_received.get('dias_gozo', 0))
                status_ferias = form_data_received.get('status_ferias', '').strip()
                observacoes = request.form.get('observacoes', '').strip()

                if not all([matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim, status_ferias]):
                    flash('Campos obrigatórios (Funcionário, Período Aquisitivo, Status) não podem ser vazios.', 'danger')
                    is_valid = False

                if is_valid and periodo_aquisitivo_fim < periodo_aquisitivo_inicio:
                    flash('Data final do período aquisitivo deve ser posterior à data inicial.', 'danger')
                    is_valid = False

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
                        return redirect(url_for('pessoal_bp.ferias_module'))
                    else:
                        flash('Erro ao adicionar registro de férias. Verifique os dados e tente novamente.', 'danger')

            else: # GET request ou POST com falha de validação: Renderiza o formulário com dados existentes/submetidos
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
        return redirect(url_for('pessoal_bp.ferias_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_ferias: {e}")
        return redirect(url_for('pessoal_bp.ferias_module'))

# ---------------------------------------------------------------
# 2.5.2 ROTAS DO CRUD DE FERIAS - EDITAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/ferias/edit/<int:ferias_id>', methods=['GET', 'POST'])
@login_required
def edit_ferias(ferias_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            all_funcionarios = pessoal_manager.get_all_funcionarios()
            status_options = ['Programada', 'Aprovada', 'Gozo', 'Concluída', 'Cancelada']

            ferias_from_db = pessoal_manager.get_ferias_by_id(ferias_id)
            if not ferias_from_db:
                flash('Registro de férias não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.ferias_module'))

            form_data_to_template = {} 


            if request.method == 'POST':
                form_data_received = request.form.to_dict()

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

                form_data_to_template = form_data_received
                form_data_to_template['periodo_aquisitivo_inicio'] = periodo_aquisitivo_inicio.strftime('%Y-%m-%d') if periodo_aquisitivo_inicio else ''
                form_data_to_template['periodo_aquisitivo_fim'] = periodo_aquisitivo_fim.strftime('%Y-%m-%d') if periodo_aquisitivo_fim else ''
                form_data_to_template['data_inicio_gozo'] = data_inicio_gozo.strftime('%Y-%m-%d') if data_inicio_gozo else ''
                form_data_to_template['data_fim_gozo'] = data_fim_gozo.strftime('%Y-%m-%d') if data_fim_gozo else ''

                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                dias_gozo = int(form_data_received.get('dias_gozo', 0))
                status_ferias = form_data_received.get('status_ferias', '').strip()
                observacoes = request.form.get('observacoes', '').strip()

                if not all([matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim, status_ferias]):
                    flash('Campos obrigatórios (Funcionário, Período Aquisitivo, Status) não podem ser vazios.', 'danger')
                    is_valid = False

                if is_valid and periodo_aquisitivo_fim < periodo_aquisitivo_inicio:
                    flash('Data final do período aquisitivo deve ser posterior à data inicial.', 'danger')
                    is_valid = False

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
                        return redirect(url_for('pessoal_bp.ferias_module'))
                    else:
                        flash('Erro ao atualizar registro de férias. Verifique os dados e tente novamente.', 'danger')

            else: # GET request
                form_data_to_template = ferias_from_db.copy()
                form_data_to_template['Periodo_Aquisitivo_Inicio'] = form_data_to_template['Periodo_Aquisitivo_Inicio'].strftime('%Y-%m-%d') if form_data_to_template['Periodo_Aquisitivo_Inicio'] else ''
                form_data_to_template['Periodo_Aquisitivo_Fim'] = form_data_to_template['Periodo_Aquisitivo_Fim'].strftime('%Y-%m-%d') if form_data_to_template['Periodo_Aquisitivo_Fim'] else ''
                form_data_to_template['Data_Inicio_Gozo'] = form_data_to_template['Data_Inicio_Gozo'].strftime('%Y-%m-%d') if form_data_to_template['Data_Inicio_Gozo'] else ''
                form_data_to_template['Data_Fim_Gozo'] = form_data_to_template['Data_Fim_Gozo'].strftime('%Y-%m-%d') if form_data_to_template['Data_Fim_Gozo'] else ''
                form_data_to_template['Dias_Gozo'] = str(form_data_to_template['Dias_Gozo']) 
                form_data_to_template['Contato_Emergencia'] = bool(form_data_to_template.get('Contato_Emergencia'))

            return render_template(
                'pessoal/ferias/edit_ferias.html',
                user=current_user,
                ferias=form_data_to_template,
                all_funcionarios=all_funcionarios,
                status_options=status_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_ferias: {e}")
        return redirect(url_for('pessoal_bp.ferias_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_ferias: {e}")
        return redirect(url_for('pessoal_bp.ferias_module'))

# ---------------------------------------------------------------
# 2.5.3 ROTAS DO CRUD DE FERIAS - DELETAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/ferias/delete/<int:ferias_id>', methods=['POST'])
@login_required
def delete_ferias(ferias_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_ferias(ferias_id)
            if success:
                flash('Registro de férias excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir registro de férias. Verifique se ele existe.', 'danger')
        return redirect(url_for('pessoal_bp.ferias_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_ferias: {e}")
        return redirect(url_for('pessoal_bp.ferias_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_ferias: {e}")
        return redirect(url_for('pessoal_bp.ferias_module'))

# ---------------------------------------------------------------
# 2.5.4 ROTAS DO CRUD DE FERIAS - DETALHES - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/ferias/details/<int:ferias_id>')
@login_required
def ferias_details(ferias_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            ferias = pessoal_manager.get_ferias_by_id(ferias_id)

            if not ferias:
                flash('Registro de férias não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.ferias_module'))

            ferias['Idade'] = calculate_age(ferias.get('Data_Nascimento'))

        return render_template(
            'pessoal/ferias/ferias_details.html',
            user=current_user,
            ferias=ferias
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em ferias_details: {e}")
        return redirect(url_for('pessoal_bp.ferias_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em ferias_details: {e}")
        return redirect(url_for('pessoal_bp.ferias_module'))

# ---------------------------------------------------------------
# 2.5.5 ROTAS DE FERIAS - EXPORTAR P/ EXCEL - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/ferias/export/excel')
@login_required
def export_ferias_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Férias.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('pessoal_bp.ferias_module'))

            df = pd.DataFrame(ferias_data)

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
        return redirect(url_for('pessoal_bp.ferias_module'))

# ===============================================================
# 2.6 ROTAS DE DEPENDENTES - PESSOAL
# ===============================================================

# Função auxiliar para calcular idade
# Se esta função já estiver em outro arquivo (ex: utils.py), remova-a daqui
# ou considere movê-la para o utils.py se for usada por múltiplos blueprints/módulos
def calculate_age(born_date):
    """Calcula a idade em anos a partir de uma data de nascimento."""
    if not isinstance(born_date, date):
        print(f"DEBUG_CALCULATE_AGE: Data de nascimento inválida ou não é objeto date: {born_date} (Tipo: {type(born_date)}). Retornando None.")
        return None

    today = date.today()
    age = today.year - born_date.year - ((today.month, today.day) < (born_date.month, born_date.day))
    print(f"DEBUG_CALCULATE_AGE: Data Nascimento: {born_date}, Hoje: {today}, Idade Calculada: {age}")
    return age

@pessoal_bp.route('/dependentes')
@login_required
def dependentes_module():
    if not current_user.can_access_module('Pessoal'): 
        flash('Acesso negado. Você não tem permissão para acessar a Gestão de Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    search_matricula = request.args.get('matricula')
    search_nome = request.args.get('nome')
    search_parentesco = request.args.get('parentesco')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            dependentes = pessoal_manager.get_all_dependentes(
                search_matricula=search_matricula,
                search_nome=search_nome,
                search_parentesco=search_parentesco
            )

            processed_dependentes = []
            for dep in dependentes:
                dep_copy = dep.copy() 
                dep_copy['Idade'] = calculate_age(dep_copy.get('Data_Nascimento'))
                processed_dependentes.append(dep_copy)

            all_funcionarios = pessoal_manager.get_all_funcionarios()

            parentesco_options = ['Filho(a)', 'Cônjuge', 'Pai', 'Mãe', 'Irmão(ã)', 'Outro']

        return render_template(
            'pessoal/dependentes/dependentes_module.html',
            user=current_user,
            dependentes=processed_dependentes,
            all_funcionarios=all_funcionarios,
            parentesco_options=parentesco_options,
            selected_matricula=search_matricula,
            selected_nome=search_nome,
            selected_parentesco=search_parentesco
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar Dependentes: {e}", 'danger')
        print(f"Erro de banco de dados em dependentes_module: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Dependentes: {e}", 'danger')
        print(f"Erro inesperado em dependentes_module: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.6.1 ROTAS DO CRUD DE DEPENDENTES - CRIAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/dependentes/add', methods=['GET', 'POST'])
@login_required
def add_dependente():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para adicionar Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

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
                telefone_emergencia = request.form.get('telefone_emergencia', '').strip()
                observacoes = request.form.get('observacoes', '').strip()

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

                form_data_to_template = form_data_received
                form_data_to_template['data_nascimento'] = data_nascimento_str
                form_data_to_template['contato_emergencia'] = contato_emergencia

                if is_valid:
                    success = pessoal_manager.add_dependente(
                        matricula_funcionario, nome_completo, parentesco, data_nascimento,
                        cpf if cpf else None, contato_emergencia, telefone_emergencia, observacoes
                    )
                    if success:
                        flash('Dependente adicionado com sucesso!', 'success')
                        return redirect(url_for('pessoal_bp.dependentes_module'))
                    else:
                        flash('Erro ao adicionar dependente. Verifique os dados e tente novamente.', 'danger')

            else: # GET request ou POST com falha de validação: Renderiza o formulário com dados existentes/submetidos
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
        return redirect(url_for('pessoal_bp.dependentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_dependente: {e}")
        return redirect(url_for('pessoal_bp.dependentes_module'))

# ---------------------------------------------------------------
# 2.6.2 ROTAS DO CRUD DE DEPENDENTES - EDITAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/dependentes/edit/<int:dependente_id>', methods=['GET', 'POST'])
@login_required
def edit_dependente(dependente_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para editar Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            all_funcionarios = pessoal_manager.get_all_funcionarios()
            parentesco_options = ['Filho(a)', 'Cônjuge', 'Pai', 'Mãe', 'Irmão(ã)', 'Outro']

            dependente_from_db = pessoal_manager.get_dependente_by_id(dependente_id)
            if not dependente_from_db:
                flash('Dependente não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.dependentes_module'))

            form_data_to_template = {} 


            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                matricula_funcionario = form_data_received.get('matricula_funcionario', '').strip()
                nome_completo = form_data_received.get('nome_completo', '').strip()
                parentesco = form_data_received.get('parentesco', '').strip()
                data_nascimento_str = form_data_received.get('data_nascimento', '').strip()
                cpf = request.form.get('cpf', '').replace('.', '').replace('-', '').strip()
                contato_emergencia = 'contato_emergencia' in request.form
                telefone_emergencia = request.form.get('telefone_emergencia', '').strip()
                observacoes = request.form.get('observacoes', '').strip()

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

                form_data_to_template = form_data_received
                form_data_to_template['data_nascimento'] = data_nascimento_str
                form_data_to_template['contato_emergencia'] = contato_emergencia

                if is_valid:
                    success = pessoal_manager.update_dependente(
                        dependente_id, matricula_funcionario, nome_completo, parentesco, data_nascimento,
                        cpf if cpf else None, contato_emergencia, telefone_emergencia, observacoes
                    )
                    if success:
                        flash('Dependente atualizado com sucesso!', 'success')
                        return redirect(url_for('pessoal_bp.dependentes_module'))
                    else:
                        flash('Erro ao atualizar dependente. Verifique os dados e tente novamente.', 'danger')

            else: # GET request
                form_data_to_template = dependente_from_db.copy()
                form_data_to_template['Data_Nascimento'] = form_data_to_template['Data_Nascimento'].strftime('%Y-%m-%d') if form_data_to_template['Data_Nascimento'] else ''
                form_data_to_template['Contato_Emergencia'] = bool(form_data_to_template.get('Contato_Emergencia'))

            return render_template(
                'pessoal/dependentes/edit_dependente.html',
                user=current_user,
                dependente=form_data_to_template,
                all_funcionarios=all_funcionarios,
                parentesco_options=parentesco_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_dependente: {e}")
        return redirect(url_for('pessoal_bp.dependentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_dependente: {e}")
        return redirect(url_for('pessoal_bp.dependentes_module'))

# ---------------------------------------------------------------
# 2.6.3 ROTAS DO CRUD DE DEPENDENTES - DELETAR - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/dependentes/delete/<int:dependente_id>', methods=['POST'])
@login_required
def delete_dependente(dependente_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para excluir Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            success = pessoal_manager.delete_dependente(dependente_id)
            if success:
                flash('Dependente excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir dependente. Verifique se ele existe.', 'danger')
        return redirect(url_for('pessoal_bp.dependentes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_dependente: {e}")
        return redirect(url_for('pessoal_bp.dependentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_dependente: {e}")
        return redirect(url_for('pessoal_bp.dependentes_module'))

# ---------------------------------------------------------------
# 2.6.4 ROTAS DO CRUD DE DEPENDENTES - DETALHES - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/dependentes/details/<int:dependente_id>')
@login_required
def dependente_details(dependente_id):
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para ver detalhes de Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)
            dependente = pessoal_manager.get_dependente_by_id(dependente_id)

            if not dependente:
                flash('Dependente não encontrado.', 'danger')
                return redirect(url_for('pessoal_bp.dependentes_module'))

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
        return redirect(url_for('pessoal_bp.dependentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em dependente_details: {e}")
        return redirect(url_for('pessoal_bp.dependentes_module'))

# ---------------------------------------------------------------
# 2.6.5 ROTA DE DEPENDENTES - EXPORTAR P/ EXCEL- PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/dependentes/export/excel')
@login_required
def export_dependentes_excel():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para exportar dados de Dependentes.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('pessoal_bp.dependentes_module'))

            for dep in dependentes_data:
                dep['Idade'] = calculate_age(dep.get('Data_Nascimento'))

            df = pd.DataFrame(dependentes_data)

            df = df.rename(columns={
                'ID_Dependente': 'ID Dependente',
                'Matricula_Funcionario': 'Matrícula Funcionário',
                'Nome_Funcionario': 'Nome do Funcionário',
                'Nome_Completo': 'Nome do Dependente',
                'Parentesco': 'Parentesco',
                'Data_Nascimento': 'Data de Nascimento',
                'Idade': 'Idade (anos)', 
                'Cpf': 'CPF',
                'Contato_Emergencia': 'Contato de Emergência',
                'Telefone_Emergencia': 'Telefone de Emergência',
                'Observacoes': 'Observações',
                'Data_Criacao': 'Data de Criação',
                'Data_Modificacao': 'Última Modificação'
            })

            df['Contato de Emergência'] = df['Contato de Emergência'].apply(lambda x: 'Sim' if x else 'Não')

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
        return redirect(url_for('pessoal_bp.dependentes_module'))

# ---------------------------------------------------------------
# 2.6.6 ROTA DE DEPENDENTES - DASHBOARD - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/dashboard')
@login_required
def pessoal_dashboard():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o Dashboard de Pessoal.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base) 
            status_counts = pessoal_manager.get_funcionario_status_counts()
            funcionarios_por_cargo = pessoal_manager.get_funcionarios_by_cargo()
            funcionarios_por_nivel = pessoal_manager.get_funcionarios_by_nivel()
            proximas_ferias = pessoal_manager.get_proximas_ferias(dias_antecedencia=60)

            return render_template(
                'pessoal/pessoal_dashboard.html',
                user=current_user,
                status_counts=status_counts,
                funcionarios_por_cargo=funcionarios_por_cargo,
                funcionarios_por_nivel=funcionarios_por_nivel,
                proximas_ferias=proximas_ferias
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar dashboard de pessoal: {e}", 'danger')
        print(f"Erro de banco de dados em pessoal_dashboard: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar dashboard de pessoal: {e}", 'danger')
        print(f"Erro inesperado em pessoal_dashboard: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.6.7 ROTA DE DEPENDENTES - ANIVERSARIANTES DO MES - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/aniversariantes')
@login_required
def pessoal_aniversariantes():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o Relatório de Aniversariantes.', 'warning')
        return redirect(url_for('welcome'))

    mes_atual = date.today().month
    nome_mes = date(1900, mes_atual, 1).strftime('%B')

    meses_pt = {
        'January': 'Janeiro', 'February': 'Fevereiro', 'March': 'Março', 'April': 'Abril',
        'May': 'Maio', 'June': 'Junho', 'July': 'Julho', 'August': 'Agosto',
        'September': 'Setembro', 'October': 'Outubro', 'November': 'Novembro', 'December': 'Dezembro'
    }
    nome_mes_pt = meses_pt.get(nome_mes, nome_mes)

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            aniversariantes = pessoal_manager.get_aniversariantes_do_mes(mes=mes_atual)

            return render_template(
                'pessoal/aniversariantes_module.html',
                user=current_user,
                aniversariantes=aniversariantes,
                mes_referencia=nome_mes_pt
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar aniversariantes: {e}", 'danger')
        print(f"Erro de banco de dados em pessoal_aniversariantes: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar aniversariantes: {e}", 'danger')
        print(f"Erro inesperado em pessoal_aniversariantes: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.6.8 ROTA DE DEPENDENTES - EXPERIENCIA A VENCER - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/experiencia_a_vencer')
@login_required
def pessoal_experiencia_a_vencer():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o Relatório de Período de Experiência.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            periodos_a_vencer = pessoal_manager.get_periodos_experiencia_a_vencer()

            return render_template(
                'pessoal/experiencia_a_vencer_module.html',
                user=current_user,
                periodos_a_vencer=periodos_a_vencer,
                hoje=date.today()
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar períodos de experiência: {e}", 'danger')
        print(f"Erro de banco de dados em pessoal_experiencia_a_vencer: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar períodos de experiência: {e}", 'danger')
        print(f"Erro inesperado em pessoal_experiencia_a_vencer: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))

# ---------------------------------------------------------------
# 2.6.9 ROTA DE DEPENDENTES - DOCUMENTOS A VENCER - PESSOAL
# ---------------------------------------------------------------
@pessoal_bp.route('/documentos_a_vencer')
@login_required
def pessoal_documentos_a_vencer():
    if not current_user.can_access_module('Pessoal'):
        flash('Acesso negado. Você não tem permissão para acessar o Relatório de Documentos e Contratos a Vencer.', 'warning')
        return redirect(url_for('welcome'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            pessoal_manager = PessoalManager(db_base)

            documentos_a_vencer = pessoal_manager.get_documentos_contratos_a_vencer(
                dias_alerta_futuro=30,  
                dias_alerta_passado=7   
            )

            return render_template(
                'pessoal/documentos_a_vencer_module.html',
                user=current_user,
                documentos_a_vencer=documentos_a_vencer,
                hoje=date.today()
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar documentos e contratos a vencer: {e}", 'danger')
        print(f"Erro de banco de dados em pessoal_documentos_a_vencer: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar documentos e contratos a vencer: {e}", 'danger')
        print(f"Erro inesperado em pessoal_documentos_a_vencer: {e}")
        return redirect(url_for('pessoal_bp.pessoal_module'))