# modulos/obras_bp.py

import mysql.connector
import locale
import os
from dotenv import load_dotenv
from datetime import datetime, date, timedelta # Incluído timedelta para get_proximas_ferias se for movido
from decimal import Decimal, InvalidOperation

# Para a adição da opção exportar para Excel no módulo Pessoal
from flask import send_file # Adicione este import no topo do seu app.py
import pandas as pd         # Adicione este import no topo do seu app.py
from io import BytesIO      # Adicione este import no topo do seu app.py

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, Flask, session, get_flashed_messages, jsonify
from flask_login import login_required, current_user, LoginManager, UserMixin, login_user, logout_user 

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_obras_manager import ObrasManager
from database.db_pessoal_manager import PessoalManager # Para o dropdown de funcionários se necessário (em Segurança, por exemplo)

# Conversão da moeda para o padrão brasileiro R$ 1.234,56
from utils import formatar_moeda_brl

# Importação da função de análise de permissão do usuário aos módulos através do decorator @module_required('Obras')
from utils import module_required

# Crie a instância do Blueprint para o Módulo Obras
obras_bp = Blueprint('obras_bp', __name__, url_prefix='/obras')

# ==================================================================================================================================
# === ROTAS PARA O MÓDULO OBRAS ====================================================================================================
# ==================================================================================================================================

# ROTA HUB PRINCIPAL DO MÓDULO OBRAS
@obras_bp.route('/')
@login_required
@module_required('Obras')
def obras_module():
    """
    Rota principal do módulo Obras.
    Serve como hub de navegação para os submódulos de Obras.
    """
    
    return render_template('obras/obras_welcome.html', user=current_user)

@obras_bp.route('/dashboard')
@login_required
@module_required('Obras')
def obras_dashboard():
    """
    Rota para o Dashboard de Obras, exibindo KPIs e resumos.
    """
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base) 

            status_counts_list = obras_manager.get_obra_status_counts()
            status_counts = {item['Status_Obra']: item['Count'] for item in status_counts_list}

            # --- CORRIGIDO AQUI: CHAMAR O MÉTODO PARA OBTER A CONTAGEM TOTAL ---
            total_obras_geral = obras_manager.get_total_obras_count()
            # --- FIM DA CORREÇÃO ---

            total_contratos_ativos = obras_manager.get_total_contratos_ativos_valor()
            total_medicoes_realizadas = obras_manager.get_total_medicoes_realizadas_valor()
            avg_avanco_fisico = obras_manager.get_avg_avanco_fisico_obras_ativas()
            
            total_contratos_ativos_formatado = f"R$ {total_contratos_ativos:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_contratos_ativos is not None else "R$ 0,00"
            total_medicoes_realizadas_formatado = f"R$ {total_medicoes_realizadas:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if total_medicoes_realizadas is not None else "R$ 0,00"
            avg_avanco_fisico_formatado = f"{avg_avanco_fisico:.2f}%" if avg_avanco_fisico is not None else "0.00%"

            return render_template(
                'obras/obras_dashboard.html',
                user=current_user,
                status_counts=status_counts,
                # --- CORRIGIDO AQUI: PASSAR A VARIÁVEL total_obras_geral PARA O TEMPLATE ---
                total_obras_geral=total_obras_geral, 
                # --- FIM DA CORREÇÃO ---
                total_contratos_ativos=total_contratos_ativos_formatado,
                total_medicoes_realizadas=total_medicoes_realizadas_formatado,
                avg_avanco_fisico=avg_avanco_fisico_formatado
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar dashboard de obras: {e}", 'danger')
        print(f"Erro de banco de dados em obras_dashboard: {e}")
        return redirect(url_for('obras_bp.obras_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar dashboard de obras: {e}", 'danger')
        print(f"Erro inesperado em obras_dashboard: {e}")
        return redirect(url_for('obras_bp.obras_module'))

# ===============================================================
# 3.1 ROTAS DE OBRAS (CRUD e Relatórios)
# ===============================================================

# ROTA PARA A LISTAGEM/GERENCIAMENTO DE OBRAS ESPECÍFICAS (VERSÃO CORRIGIDA)
@obras_bp.route('/gerenciar')
@login_required
@module_required('Obras')
def gerenciar_obras_lista():
    """
    Rota para a listagem e filtragem de obras.
    Esta rota concentra a lógica que antes estava na 'obras_module'.
    """
   
    search_numero = request.args.get('numero_obra')
    search_nome = request.args.get('nome_obra')
    search_status = request.args.get('status_obra')
    search_cliente_id = request.args.get('cliente_id') 

    try:
        # Tenta definir o locale para o padrão brasileiro para formatar a moeda.
        # Este bloco try/except aninhado é para lidar com o caso do locale não estar instalado no OS.
        try:
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        except locale.Error:
            # Se 'pt_BR.UTF-8' não for encontrado, usa o locale padrão do sistema.
            locale.setlocale(locale.LC_ALL, '')

        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)

            obras = obras_manager.get_all_obras(
                search_numero=search_numero,
                search_nome=search_nome,
                search_status=search_status,
                search_cliente_id=search_cliente_id
            )

            # Formata o valor da obra para o padrão brasileiro
            if obras:
                for obra_item in obras:
                    valor = obra_item.get('Valor_Obra')
                    if valor is not None:
                        # Usa locale.currency para formatar corretamente (ex: R$ 652.894,10)
                        obra_item['Valor_Obra_Formatado'] = locale.currency(valor, grouping=True)
                    else:
                        obra_item['Valor_Obra_Formatado'] = locale.currency(0, grouping=True)

            clientes = obras_manager.get_all_clientes() 
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']

        return render_template(
            'obras/obras_module.html', 
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
        return redirect(url_for('obras_bp.obras_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar obras: {e}", 'danger')
        print(f"Erro inesperado em gerenciar_obras_lista: {e}")
        return redirect(url_for('obras_bp.obras_module'))

# ROTA PARA O RELATÓRIO DE ANDAMENTO DE OBRAS
@obras_bp.route('/relatorio_andamento')
@login_required
@module_required('Obras')
def obras_relatorio_andamento():
    """
    Rota para o relatório de andamento de obras, com filtros.
    """
    
    search_numero = request.args.get('numero_obra')
    search_nome = request.args.get('nome_obra')
    search_status = request.args.get('status_obra')
    search_cliente_id = request.args.get('cliente_id')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)

            # Assume que este método já existe no db_obras_manager.py
            obras_andamento = obras_manager.get_obras_andamento_para_relatorio(
                search_numero=search_numero,
                search_nome=search_nome,
                search_status=search_status,
                search_cliente_id=search_cliente_id
            )

            all_clientes = obras_manager.get_all_clientes()
            status_options = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']

            return render_template(
                'obras/obras_relatorio_andamento.html',
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
        return redirect(url_for('obras_bp.obras_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar relatório de andamento de obras: {e}", 'danger')
        print(f"Erro inesperado em obras_relatorio_andamento: {e}")
        return redirect(url_for('obras_bp.obras_module'))

# ROTA PARA ADICIONAR OBRA
@obras_bp.route('/add', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def add_obra():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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

                is_valid = True

                if not all([id_contratos, numero_obra, nome_obra, status_obra, data_inicio_prevista_str, data_fim_prevista_str]):
                    flash('Campos obrigatórios (Contrato, Número, Nome, Status, Datas de Início/Fim) não podem ser vazios.', 'danger')
                    is_valid = False

                data_inicio_prevista = None
                data_fim_prevista = None
                try:
                    data_inicio_prevista = datetime.strptime(data_inicio_prevista_str, '%Y-%m-%d').date()
                    data_fim_prevista = datetime.strptime(data_fim_prevista_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato de data inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False

                if obras_manager.get_obra_by_numero(numero_obra):
                    flash('Número da obra já existe. Por favor, use um número único.', 'danger')
                    is_valid = False

                if not is_valid:
                    form_data_to_template = request.form.to_dict()
                    form_data_to_template['data_inicio_prevista'] = data_inicio_prevista_str
                    form_data_to_template['data_fim_prevista'] = data_fim_prevista_str
                    # Garante que o ID do contrato esteja como string para o template
                    form_data_to_template['id_contratos'] = str(id_contratos)

                    all_contratos = obras_manager.get_all_contratos_for_dropdown()
                    status_options_list = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']
                    return render_template(
                        'obras/add_obra.html',
                        user=current_user,
                        obra=form_data_to_template,
                        all_contratos=all_contratos,
                        status_options=status_options_list
                    )

                success = obras_manager.add_obra(
                    id_contratos, numero_obra, nome_obra, endereco_obra, escopo_obra,
                    valor_obra, valor_aditivo_total, status_obra,
                    data_inicio_prevista, data_fim_prevista
                )
                if success:
                    flash('Obra adicionada com sucesso!', 'success')
                    return redirect(url_for('obras_bp.gerenciar_obras_lista'))
                else:
                    flash('Erro ao adicionar obra.', 'danger')

            else: # GET request: Carregar dados para o formulário
                form_data_to_template = {} # Inicia vazio para o GET
                # Você pode pré-popula campos aqui, se necessário
                # Ex: form_data_to_template['status_obra'] = 'Planejamento'

            all_contratos = obras_manager.get_all_contratos_for_dropdown()
            status_options_list = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']

            return render_template(
                'obras/add_obra.html',
                user=current_user,
                obra=form_data_to_template, # Passa form_data_to_template
                all_contratos=all_contratos,
                status_options=status_options_list
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_obra: {e}")
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_obra: {e}")
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))

# ROTA PARA EDITAR OBRA
@obras_bp.route('/edit/<int:obra_id>', methods=['GET', 'POST']) # Sua rota existente
@login_required
@module_required('Obras')
def edit_obra(obra_id):
    print(f"DEBUG_EDIT_OBRA: Início da função edit_obra para ID: {obra_id}")
    

    # Inicializa obra_from_db fora do try/except para que esteja sempre no escopo para depuração final
    # se necessário, embora não deva ser o caso mais
    obra_from_db = None 
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            
            obra_from_db = obras_manager.get_obra_by_id(obra_id)
            print(f"DEBUG_EDIT_OBRA: Obra do DB (original): {obra_from_db}")

            if not obra_from_db:
                flash('Obra não encontrada.', 'danger')
                print(f"DEBUG_EDIT_OBRA: Obra ID {obra_id} não encontrada no DB.")
                return redirect(url_for('obras_bp.gerenciar_obras_lista'))

            all_contratos = obras_manager.get_all_contratos_for_dropdown()
            status_options_list = ['Planejamento', 'Em Andamento', 'Concluída', 'Pausada', 'Cancelada']

            form_data_to_template = {} # Inicializa como um dicionário vazio para passar ao template

            if request.method == 'POST':
                print("DEBUG_EDIT_OBRA: Método POST detectado.")
                form_data_received = request.form.to_dict()

                is_valid = True

                # Validação e Conversão de Data de Início Prevista
                data_inicio_prevista_str = form_data_received.get('data_inicio_prevista', '').strip()
                data_inicio_prevista = None
                if data_inicio_prevista_str:
                    try:
                        data_inicio_prevista = datetime.strptime(data_inicio_prevista_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Início Prevista inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                else:
                    flash('Data de Início Prevista é obrigatória.', 'danger')
                    is_valid = False

                # Validação e Conversão de Data de Fim Prevista
                data_fim_prevista_str = form_data_received.get('data_fim_prevista', '').strip()
                data_fim_prevista = None
                if data_fim_prevista_str:
                    try:
                        data_fim_prevista = datetime.strptime(data_fim_prevista_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Fim Prevista inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                else:
                    flash('Data de Fim Prevista é obrigatória.', 'danger')
                    is_valid = False

                # Validação e Conversão de Valor da Obra
                valor_obra = None
                valor_obra_str = form_data_received.get('valor_obra', '').strip()
                if valor_obra_str:
                    try:
                        valor_obra = float(valor_obra_str.replace(',', '.'))
                    except ValueError:
                        flash('Valor da Obra inválido. Use números.', 'danger')
                        is_valid = False
                else:
                    flash('Valor da Obra é obrigatório.', 'danger')
                    is_valid = False

                # Validação e Conversão de Valor Aditivo Total (Opcional)
                valor_aditivo_total = None
                valor_aditivo_total_str = form_data_received.get('valor_aditivo_total', '0').strip()
                try:
                    valor_aditivo_total = float(valor_aditivo_total_str.replace(',', '.'))
                except ValueError:
                    flash('Valor Aditivo Total inválido. Use números.', 'danger')
                    is_valid = False

                # Captura de outros campos
                id_contratos = int(request.form.get('id_contratos'))
                numero_obra = request.form.get('numero_obra', '').strip()
                nome_obra = request.form.get('nome_obra', '').strip()
                endereco_obra = request.form.get('endereco_obra', '').strip()
                escopo_obra = request.form.get('escopo_obra', '').strip()
                status_obra = request.form.get('status_obra', '').strip()

                # Validações de Campos Obrigatórios (gerais)
                if not all([id_contratos, numero_obra, nome_obra, status_obra]):
                    flash('Campos obrigatórios (Contrato, Número, Nome, Status) não podem ser vazios.', 'danger')
                    is_valid = False

                # VALIDAÇÃO DE UNICIDADE DO NÚMERO DA OBRA (CORRIGIDO PARA EDIÇÃO)
                if is_valid: # Só verifica unicidade se os dados básicos já são válidos
                    existing_obra_by_numero = obras_manager.get_obra_by_numero(numero_obra)
                    if existing_obra_by_numero and existing_obra_by_numero['ID_Obras'] != obra_id:
                        flash('Número da obra já existe. Por favor, use um número único.', 'danger')
                        is_valid = False

                # --- SE HOUVER ERROS DE VALIDAÇÃO NO POST ---
                if not is_valid:
                    print("DEBUG_EDIT_OBRA: POST - Validação falhou. Repopulando formulário.")
                    form_data_to_template = request.form.to_dict()
                    form_data_to_template['data_inicio_prevista'] = data_inicio_prevista_str
                    form_data_to_template['data_fim_prevista'] = data_fim_prevista_str
                    form_data_to_template['valor_obra'] = valor_obra_str
                    form_data_to_template['valor_aditivo_total'] = valor_aditivo_total_str

                    form_data_to_template['ID_Obras'] = obra_id
                    form_data_to_template['ID_Contratos'] = str(id_contratos)

                    return render_template(
                        'obras/edit_obra.html',
                        user=current_user,
                        obra=form_data_to_template,
                        all_contratos=all_contratos,
                        status_options=status_options_list
                    )

                # --- SE TODAS AS VALIDAÇÕES PASSARAM NO POST, TENTA ATUALIZAR ---
                print("DEBUG_EDIT_OBRA: POST - Validação bem-sucedida. Tentando atualizar DB.")
                success = obras_manager.update_obra(
                    obra_id, id_contratos, numero_obra, nome_obra, endereco_obra, escopo_obra,
                    valor_obra, valor_aditivo_total, status_obra,
                    data_inicio_prevista, data_fim_prevista
                )
                if success:
                    flash('Obra atualizada com sucesso!', 'success')
                    print("DEBUG_EDIT_OBRA: Obra atualizada com sucesso.")
                    return redirect(url_for('obras_bp.gerenciar_obras_lista'))
                else:
                    flash('Erro ao atualizar obra.', 'danger')
                    print("DEBUG_EDIT_OBRA: Erro ao atualizar obra no DB.")

            else: # GET request (carregar dados do DB para o formulário)
                print("DEBUG_EDIT_OBRA: Método GET detectado. Carregando dados do DB.")

                # Popula form_data_to_template com os dados do banco de dados (chaves originais)
                form_data_to_template = obra_from_db.copy()

                form_data_to_template['ID_Contratos'] = str(form_data_to_template['ID_Contratos']) if form_data_to_template.get('ID_Contratos') is not None else ''

                text_fields = ['Numero_Obra', 'Nome_Obra', 'Endereco_Obra', 'Escopo_Obra', 'Status_Obra']
                for key in text_fields:
                    if key in form_data_to_template and form_data_to_template[key] is None:
                        form_data_to_template[key] = ''
                    else:
                        form_data_to_template[key] = form_data_to_template.get(key, '')

                data_fields = ['Data_Inicio_Prevista', 'Data_Fim_Prevista']
                for key in data_fields:
                    date_obj = form_data_to_template.get(key)
                    form_data_to_template[key] = date_obj.strftime('%Y-%m-%d') if isinstance(date_obj, date) else ''

                # --- CORREÇÃO AQUI: TRATAMENTO ROBUSTO PARA VALORES NUMÉRICOS (Valor_Obra, Valor_Aditivo_Total) ---
                numeric_fields_to_format = ['Valor_Obra', 'Valor_Aditivo_Total']
                for key in numeric_fields_to_format:
                    value = form_data_to_template.get(key)
                    print(f"DEBUG_EDIT_OBRA: GET - Preparando '{key}' para template. Valor: {value}, Tipo: {type(value)}")
                    if value is None:
                        form_data_to_template[key] = ''
                    else:
                        try:
                            # Usamos f-string que é mais robusta para formatar float
                            formatted_value_str = f"{float(value):.2f}"
                            form_data_to_template[key] = formatted_value_str
                            print(f"DEBUG_EDIT_OBRA: GET - '{key}' formatado para: {formatted_value_str}")
                        except (ValueError, TypeError) as conv_err:
                            # Em caso de qualquer falha na conversão para float, define como string vazia
                            print(f"DEBUG_EDIT_OBRA: GET - ERRO NA CONVERSÃO/FORMATAÇÃO DE '{key}'! Valor: {value}, Tipo: {type(value)}, Erro: {conv_err}")
                            form_data_to_template[key] = ''
                # --- FIM DA CORREÇÃO ---

            print("DEBUG_EDIT_OBRA: Renderizando template 'obras/edit_obra.html'.")
            return render_template(
                'obras/edit_obra.html',
                user=current_user,
                obra=form_data_to_template,
                all_contratos=all_contratos,
                status_options=status_options_list
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"DEBUG_EDIT_OBRA: Erro MySQL: {e}")
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"DEBUG_EDIT_OBRA: Erro Inesperado: {e}")
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))

  
# ROTA PARA DELETAR OBRA
@obras_bp.route('/delete/<int:obra_id>', methods=['POST'])
@login_required
@module_required('Obras')
def delete_obra(obra_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_obra(obra_id)
            if success:
                flash('Obra excluída com sucesso!', 'success')
            else:
                flash('Erro ao excluir obra. Verifique se ela existe e não possui dependências (ARTs, Medições, etc.).', 'danger')
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_obra: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir a obra pois existem registros relacionados (ARTs, Medições, etc.). Remova-os primeiro.", 'danger')
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_obra: {e}")
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))

# ROTA PARA DETALHES DA OBRA (AGORA COM LÓGICA DE DASHBOARD)
@obras_bp.route('/details/<int:obra_id>') # O nome da rota e o decorador permanecem os mesmos
@login_required
@module_required('Obras')
def obra_details(obra_id): # O nome da função permanece o mesmo
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            obra = obras_manager.get_obra_by_id(obra_id)

            if not obra:
                flash('Obra não encontrada.', 'danger')
                return redirect(url_for('obras_bp.gerenciar_obras_lista'))

            # --- A LÓGICA DE PROCESSAMENTO DO DASHBOARD ENTRA AQUI ---
            current_year = datetime.now().year

            avancos = obras_manager.get_avancos_by_obra_id(obra_id) #
            medicoes = obras_manager.get_medicoes_by_obra_id(obra_id) #

            months_labels = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
            monthly_physical = [0.0] * 12
            monthly_financial = [0.0] * 12

            if avancos:
                for avanco in avancos:
                    if avanco.get('Data_Avanco') and avanco['Data_Avanco'].year == current_year:
                        month_index = avanco['Data_Avanco'].month - 1
                        monthly_physical[month_index] += float(avanco.get('Percentual_Avanco_Fisico', 0.0))

            if medicoes:
                for medicao in medicoes:
                    if medicao.get('Data_Medicao') and medicao['Data_Medicao'].year == current_year:
                        month_index = medicao['Data_Medicao'].month - 1
                        monthly_financial[month_index] += float(medicao.get('Valor_Medicao', 0.0))

            accumulated_physical = [sum(monthly_physical[:i+1]) for i in range(12)]
            accumulated_financial = [sum(monthly_financial[:i+1]) for i in range(12)]

            dashboard_data = {
                "year": current_year,
                "months": months_labels,
                "monthly_physical": monthly_physical,
                "monthly_financial": monthly_financial,
                "accumulated_physical": accumulated_physical,
                "accumulated_financial": accumulated_financial
            }

        # O template renderizado continua sendo o 'obra_details.html'
        return render_template(
            'obras/obra_details.html', 
            user=current_user,
            obra=obra,
            dashboard_data=dashboard_data
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em obra_details: {e}")
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em obra_details: {e}")
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))

# ROTA PARA EXPORTAR OBRAS PARA EXCEL
@obras_bp.route('/export/excel')
@login_required
@module_required('Obras')
def export_obras_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('obras_bp.gerenciar_obras_lista'))

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
        return redirect(url_for('obras_bp.gerenciar_obras_lista'))

# ===============================================================
# 3.2 ROTAS DE CLIENTES - OBRAS
# ===============================================================

@obras_bp.route('/clientes')
@login_required
@module_required('Obras')
def clientes_module(): 
    
    search_nome = request.args.get('nome_cliente')
    search_cnpj = request.args.get('cnpj_cliente')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        return redirect(url_for('obras_bp.obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar clientes: {e}", 'danger')
        print(f"Erro inesperado em clientes_module: {e}")
        return redirect(url_for('obras_bp.obras_module')) 


@obras_bp.route('/clientes/add', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def add_cliente():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                    return redirect(url_for('obras_bp.clientes_module'))
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
        return redirect(url_for('obras_bp.clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_cliente: {e}")
        return redirect(url_for('obras_bp.clientes_module'))


@obras_bp.route('/clientes/edit/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def edit_cliente(cliente_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            cliente = obras_manager.get_cliente_by_id(cliente_id)

            if not cliente:
                flash('Cliente não encontrado.', 'danger')
                return redirect(url_for('obras_bp.clientes_module'))

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
                    return redirect(url_for('obras_bp.clientes_module'))
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
        return redirect(url_for('obras_bp.clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_cliente: {e}")
        return redirect(url_for('obras_bp.clientes_module'))


@obras_bp.route('/clientes/delete/<int:cliente_id>', methods=['POST'])
@login_required
@module_required('Obras')
def delete_cliente(cliente_id):

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_cliente(cliente_id)
            if success:
                flash('Cliente excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir cliente. Verifique se ele existe e não possui contratos associados.', 'danger')
        return redirect(url_for('obras_bp.clientes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_cliente: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir o cliente pois existem contratos ou obras associados a ele. Remova-os primeiro.", 'danger')
        return redirect(url_for('obras_bp.clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_cliente: {e}")
        return redirect(url_for('obras_bp.clientes_module'))


@obras_bp.route('/clientes/details/<int:cliente_id>')
@login_required
@module_required('Obras')
def cliente_details(cliente_id):

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            cliente = obras_manager.get_cliente_by_id(cliente_id)

            if not cliente:
                flash('Cliente não encontrado.', 'danger')
                return redirect(url_for('obras_bp.clientes_module'))

        return render_template(
            'obras/clientes/cliente_details.html',
            user=current_user,
            cliente=cliente
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em cliente_details: {e}")
        return redirect(url_for('obras_bp.clientes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em cliente_details: {e}")
        return redirect(url_for('obras_bp.clientes_module'))


@obras_bp.route('/clientes/export/excel')
@login_required
@module_required('Obras')
def export_clientes_excel():

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)

            search_nome = request.args.get('nome_cliente')
            search_cnpj = request.args.get('cnpj_cliente')

            clientes_data = obras_manager.get_all_clientes(
                search_nome=search_nome,
                search_cnpj=search_cnpj
            )

            if not clientes_data:
                flash('Nenhum cliente encontrado para exportar.', 'info')
                return redirect(url_for('obras_bp.clientes_module'))

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
        return redirect(url_for('obras_bp.clientes_module'))

# ===============================================================
# 3.3 ROTAS DE CONTRATOS - OBRAS
# ===============================================================

@obras_bp.route('/contratos')
@login_required
@module_required('Obras')
def contratos_module(): 

    search_numero = request.args.get('numero_contrato')
    search_cliente_id = request.args.get('cliente_id')
    search_status = request.args.get('status_contrato')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)

            contratos = obras_manager.get_all_contratos(
                search_numero=search_numero,
                search_cliente_id=search_cliente_id,
                search_status=search_status
            )

            # --- NOVA SEÇÃO: Formatação de moeda para a lista de contratos ---
            if contratos:
                for contrato in contratos:
                    contrato['Valor_Contrato_Formatado'] = formatar_moeda_brl(contrato.get('Valor_Contrato'))
            # --- FIM DA NOVA SEÇÃO ---

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
        return redirect(url_for('obras_bp.obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar contratos: {e}", 'danger')
        print(f"Erro inesperado em contratos_module: {e}")
        return redirect(url_for('obras_bp.obras_module')) 


@obras_bp.route('/contratos/add', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def add_contrato():

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                    return redirect(url_for('obras_bp.contratos_module'))
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
        return redirect(url_for('obras_bp.contratos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_contrato: {e}")
        return redirect(url_for('obras_bp.contratos_module'))

@obras_bp.route('/contratos/edit/<int:contrato_id>', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def edit_contrato(contrato_id):

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            contrato_from_db = obras_manager.get_contrato_by_id(contrato_id)

            if not contrato_from_db:
                flash('Contrato não encontrado.', 'danger')
                return redirect(url_for('obras_bp.contratos_module'))

            # Para dropdowns (clientes, status_options)
            all_clientes = obras_manager.get_all_clientes() 
            status_options = ['Ativo', 'Pendente', 'Encerrado', 'Aditivado', 'Cancelado']

            # Inicializa form_data_to_template aqui, será preenchido com dados do DB (GET) ou do form (POST com erro)
            form_data_to_template = {}
            
            if request.method == 'POST':
                # Captura todos os dados do formulário
                form_data_received = request.form.to_dict()

                # Tentativas de conversão de datas (podem falhar e precisam de tratamento)
                data_assinatura_obj = None
                data_ordem_inicio_obj = None
                data_termino_previsto_obj = None
                is_valid = True

                # ... (SUA LÓGICA DE VALIDAÇÃO DE DATAS, CAMPOS E UNICIDADE AQUI) ...
                # Certifique-se de que se alguma validação falhar, 'is_valid' se torna False

                # Exemplo da sua validação de data_assinatura:
                data_assinatura_str = form_data_received.get('data_assinatura', '').strip()
                if data_assinatura_str:
                    try:
                        data_assinatura_obj = datetime.strptime(data_assinatura_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Assinatura inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                else:
                    flash('Data de Assinatura é obrigatória.', 'danger')
                    is_valid = False
                # Repita para data_ordem_inicio_str, data_termino_previsto_str, valor_contrato, etc.

                # Se alguma validação falhou, passamos os dados recebidos para re-preencher o form
                if not is_valid:
                    form_data_to_template = form_data_received # Repopula com os dados que o usuário digitou
                    # Assegura que datas que vieram do form e são válidas, sejam passadas como string para o input
                    form_data_to_template['data_assinatura'] = data_assinatura_str
                    form_data_to_template['data_ordem_inicio'] = data_ordem_inicio_str
                    form_data_to_template['data_termino_previsto'] = data_termino_previsto_str
                    
                    # Garante que campos numericos também sejam string para o template, se a validação falhou
                    # form_data_to_template['valor_contrato'] = form_data_to_template.get('valor_contrato', '')

                    return render_template(
                        'obras/contratos/edit_contrato.html',
                        user=current_user,
                        contrato=form_data_to_template, # Passa form_data_to_template como 'contrato'
                        all_clientes=all_clientes,
                        status_options=status_options
                    )

                # Se todas as validações passaram, tenta atualizar
                numero_contrato = form_data_received.get('numero_contrato', '').strip()
                id_clientes = int(form_data_received.get('id_clientes')) # Já convertido em float acima se for number
                valor_contrato = float(form_data_received.get('valor_contrato', '0').replace(',', '.')) # Já convertido em float acima se for number
                status_contrato = form_data_received.get('status_contrato', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()
                prazo_contrato_dias = int(form_data_received.get('prazo_contrato_dias', 0))

                success = obras_manager.update_contrato(
                    contrato_id, id_clientes, numero_contrato, valor_contrato, data_assinatura_obj, 
                    data_ordem_inicio_obj, prazo_contrato_dias, # <-- Prazo_Contrato_Dias agora é pego do form
                    data_termino_previsto_obj, status_contrato, observacoes
                )
                if success:
                    flash('Contrato atualizado com sucesso!', 'success')
                    return redirect(url_for('obras_bp.contratos_module'))
                else:
                    flash('Erro ao atualizar contrato.', 'danger')
                
            else: # GET request (carregar dados do DB para o formulário)
                # Popula form_data_to_template com os dados do banco de dados
                form_data_to_template = contrato_from_db.copy()

                # Formata as datas para o formato 'YYYY-MM-DD' para os inputs HTML
                form_data_to_template['Data_Assinatura'] = contrato_from_db['Data_Assinatura'].strftime('%Y-%m-%d') if contrato_from_db['Data_Assinatura'] else ''
                form_data_to_template['Data_Ordem_Inicio'] = contrato_from_db['Data_Ordem_Inicio'].strftime('%Y-%m-%d') if contrato_from_db['Data_Ordem_Inicio'] else ''
                form_data_to_template['Data_Termino_Previsto'] = contrato_from_db['Data_Termino_Previsto'].strftime('%Y-%m-%d') if contrato_from_db['Data_Termino_Previsto'] else ''
                
                # Converte outros campos que podem ser None em string vazia
                form_data_to_template['Observacoes'] = form_data_to_template['Observacoes'] if form_data_to_template.get('Observacoes') is not None else ''
                form_data_to_template['Numero_Contrato'] = form_data_to_template['Numero_Contrato'] if form_data_to_template.get('Numero_Contrato') is not None else ''
                form_data_to_template['Valor_Contrato'] = "%.2f" % form_data_to_template['Valor_Contrato'] if form_data_to_template.get('Valor_Contrato') is not None else ''
                form_data_to_template['Prazo_Contrato_Dias'] = str(form_data_to_template['Prazo_Contrato_Dias']) if form_data_to_template.get('Prazo_Contrato_Dias') is not None else ''


            # Renderiza o template, sempre passando form_data_to_template como a variável 'contrato'
            return render_template(
                'obras/contratos/edit_contrato.html',
                user=current_user,
                contrato=form_data_to_template, # AGORA SEMPRE PASSA form_data_to_template COMO 'contrato'
                all_clientes=all_clientes,
                status_options=status_options
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_contrato: {e}")
        return redirect(url_for('obras_bp.contratos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_contrato: {e}")
        return redirect(url_for('obras_bp.contratos_module'))


@obras_bp.route('/contratos/delete/<int:contrato_id>', methods=['POST'])
@login_required
@module_required('Obras')
def delete_contrato(contrato_id):

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_contrato(contrato_id)
            if success:
                flash('Contrato excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir contrato. Verifique se ele existe e não possui obras ou outros registros associados.', 'danger')
        return redirect(url_for('obras_bp.contratos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_contrato: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir o contrato pois existem obras ou outros registros associados a ele. Remova-os primeiro.", 'danger')
        return redirect(url_for('obras_bp.contratos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_contrato: {e}")
        return redirect(url_for('obras_bp.contratos_module'))


@obras_bp.route('/contratos/details/<int:contrato_id>')
@login_required
@module_required('Obras')
def contrato_details(contrato_id):

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            contrato = obras_manager.get_contrato_by_id(contrato_id)

            if not contrato:
                flash('Contrato não encontrado.', 'danger')
                return redirect(url_for('obras_bp.contratos_module'))

            # --- NOVA SEÇÃO: Formatação de moeda para a página de detalhes ---
            if contrato:
                contrato['Valor_Contrato_Formatado'] = formatar_moeda_brl(contrato.get('Valor_Contrato'))
            # --- FIM DA NOVA SEÇÃO ---

        return render_template(
            'obras/contratos/contrato_details.html',
            user=current_user,
            contrato=contrato
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em contrato_details: {e}")
        return redirect(url_for('obras_bp.contratos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em contrato_details: {e}")
        return redirect(url_for('obras_bp.contratos_module'))


@obras_bp.route('/contratos/export/excel')
@login_required
@module_required('Obras')
def export_contratos_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('obras_bp.contratos_module'))

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
        return redirect(url_for('obras_bp.contratos_module'))


# ===============================================================
# 3.4 ROTAS DE ARTS - OBRAS
# ===============================================================

@obras_bp.route('/arts')
@login_required
@module_required('Obras')
def arts_module(): 
    
    search_numero = request.args.get('numero_art')
    search_obra_id = request.args.get('obra_id')
    search_status = request.args.get('status_art')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        return redirect(url_for('obras_bp.obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar ARTs: {e}", 'danger')
        print(f"Erro inesperado em arts_module: {e}")
        return redirect(url_for('obras_bp.obras_module')) 


@obras_bp.route('/arts/add', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def add_art():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            
            # --- CORRIGIDO AQUI: DEFINIR AS VARIÁVEIS PARA O DROPDOWN SEMPRE ---
            all_obras = obras_manager.get_all_obras_for_dropdown() # <-- MOVIDA PARA CÁ
            status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise'] # <-- MOVIDA PARA CÁ
            # --- FIM DA CORREÇÃO ---

            # Inicializa form_data_to_template para preencher o formulário em caso de erro ou GET
            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                data_pagamento_obj = None
                is_valid = True

                # Validação e Conversão de Data de Pagamento
                data_pagamento_str = form_data_received.get('data_pagamento', '').strip()
                if data_pagamento_str:
                    try:
                        data_pagamento_obj = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Pagamento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                # Converte valores numéricos
                valor_pagamento = None
                valor_pagamento_str = form_data_received.get('valor_pagamento', '').strip()
                try:
                    if valor_pagamento_str:
                        valor_pagamento = float(valor_pagamento_str.replace(',', '.'))
                    else: # Valor de Pagamento pode ser opcional/zero
                        valor_pagamento = 0.0
                except ValueError:
                    flash('Valor de Pagamento inválido. Use números.', 'danger')
                    is_valid = False
                
                # Captura de outros campos
                id_obras = None
                id_obras_str = form_data_received.get('id_obras', '').strip()
                try:
                    if id_obras_str:
                        id_obras = int(id_obras_str)
                    else:
                        flash('Obra é obrigatória.', 'danger')
                        is_valid = False
                except ValueError:
                    flash('ID da Obra inválido.', 'danger')
                    is_valid = False

                numero_art = form_data_received.get('numero_art', '').strip()
                status_art = form_data_received.get('status_art', '').strip()

                # Validações de campos obrigatórios
                if not all([id_obras, numero_art, status_art]):
                    flash('Campos obrigatórios (Obra, Número da ART, Status) não podem ser vazios.', 'danger')
                    is_valid = False

                # Validação de unicidade
                existing_art = obras_manager.get_art_by_numero(numero_art)
                if existing_art: # Não precisa de exclude_id no add
                    flash('Número da ART já existe. Por favor, use um número único.', 'danger')
                    is_valid = False

                # --- SE ALGUMA VALIDAÇÃO FALHOU NO POST ---
                if not is_valid:
                    form_data_to_template = form_data_received.copy() # Copia para repopular
                    # Garante que as strings originais do form sejam usadas para repopular os inputs
                    form_data_to_template['data_pagamento'] = data_pagamento_str
                    form_data_to_template['valor_pagamento'] = valor_pagamento_str # Valor pode ser string vazia

                    return render_template(
                        'obras/arts/add_art.html',
                        user=current_user,
                        all_obras=all_obras,
                        status_options=status_options,
                        form_data=form_data_to_template
                    )

                # --- SE TODAS AS VALIDAÇÕES PASSARAM NO POST ---
                success = obras_manager.add_art(
                    id_obras, numero_art, data_pagamento_obj, valor_pagamento, status_art
                )
                if success:
                    flash('ART adicionada com sucesso!', 'success')
                    return redirect(url_for('obras_bp.arts_module'))
                else:
                    flash('Erro ao adicionar ART. Verifique os dados e tente novamente.', 'danger')
            
            # --- ESTE BLOCO AGORA SÓ PRECISA RENDERIZAR, POIS AS VARIAVEIS FORAM DEFINIDAS ACIMA ---
            return render_template(
                'obras/arts/add_art.html',
                user=current_user,
                all_obras=all_obras,
                status_options=status_options,
                form_data={} # Para o GET, form_data é vazio
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_art: {e}")
        return redirect(url_for('obras_bp.arts_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_art: {e}")
        return redirect(url_for('obras_bp.arts_module'))


@obras_bp.route('/arts/edit/<int:art_id>', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def edit_art(art_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            art_from_db = obras_manager.get_art_by_id(art_id) # Renomeado para consistência

            if not art_from_db:
                flash('ART não encontrada.', 'danger')
                return redirect(url_for('obras_bp.arts_module'))

            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Paga', 'Emitida', 'Cancelada', 'Em Análise']

            # Inicializa form_data_to_template aqui
            form_data_to_template = {}
            
            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                data_pagamento_obj = None
                is_valid = True

                # Validação e Conversão de Data de Pagamento
                data_pagamento_str = form_data_received.get('data_pagamento', '').strip()
                if data_pagamento_str:
                    try:
                        data_pagamento_obj = datetime.strptime(data_pagamento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Pagamento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                # Converte valores numéricos
                valor_pagamento = None
                try:
                    valor_pagamento_str = form_data_received.get('valor_pagamento', '').strip()
                    if valor_pagamento_str:
                        valor_pagamento = float(valor_pagamento_str.replace(',', '.'))
                    else: # Valor de Pagamento pode ser opcional/zero, mas se preenchido deve ser numérico
                        valor_pagamento = 0.0 # Define como zero se vazio
                except ValueError:
                    flash('Valor de Pagamento inválido. Use números.', 'danger')
                    is_valid = False
                
                # Captura de outros campos
                id_obras = int(form_data_received.get('id_obras'))
                numero_art = form_data_received.get('numero_art', '').strip()
                status_art = form_data_received.get('status_art', '').strip()

                # Validações de campos obrigatórios
                if not all([id_obras, numero_art, status_art]):
                    flash('Campos obrigatórios (Obra, Número da ART, Status) não podem ser vazios.', 'danger')
                    is_valid = False

                # Validação de unicidade
                existing_art = obras_manager.get_art_by_numero(numero_art)
                if existing_art and existing_art['ID_Arts'] != art_id:
                    flash('Número da ART já existe. Por favor, use um número único.', 'danger')
                    is_valid = False

                # --- SE ALGUMA VALIDAÇÃO FALHOU NO POST ---
                if not is_valid:
                    form_data_to_template = form_data_received.copy() # Copia para repopular
                    # Garante que as strings originais do form sejam usadas para repopular os inputs
                    form_data_to_template['data_pagamento'] = data_pagamento_str
                    form_data_to_template['valor_pagamento'] = valor_pagamento_str if valor_pagamento_str else '' # Converte para string ou vazia
                    form_data_to_template['id_obras'] = str(id_obras) # ID da obra como string
                    form_data_to_template['art_id'] = art_id # Passa o ID da ART também

                    return render_template(
                        'obras/arts/edit_art.html',
                        user=current_user,
                        art=form_data_to_template, # Passa os dados para repopular
                        all_obras=all_obras,
                        status_options=status_options
                    )

                # --- SE TODAS AS VALIDAÇÕES PASSARAM NO POST ---
                success = obras_manager.update_art(
                    art_id, id_obras, numero_art, data_pagamento_obj, valor_pagamento, status_art
                )
                if success:
                    flash('ART atualizada com sucesso!', 'success')
                    return redirect(url_for('obras_bp.arts_module'))
                else:
                    flash('Erro ao atualizar ART.', 'danger')
            
            else: # GET request (carregar dados do DB para o formulário)
                # Popula form_data_to_template com os dados do banco de dados, normalizando as chaves
                form_data_to_template = art_from_db.copy()

                # Normaliza ID e números para strings
                form_data_to_template['art_id'] = form_data_to_template['ID_Arts'] # Mapeia para art_id
                form_data_to_template['id_obras'] = str(form_data_to_template['ID_Obras']) if form_data_to_template.get('ID_Obras') is not None else ''
                form_data_to_template['numero_art'] = form_data_to_template['Numero_Art'] if form_data_to_template.get('Numero_Art') is not None else ''

                # Formata datas para o formato 'YYYY-MM-DD' para os inputs HTML
                form_data_to_template['data_pagamento'] = form_data_to_template['Data_Pagamento'].strftime('%Y-%m-%d') if form_data_to_template.get('Data_Pagamento') else ''
                
                # Converte valores numéricos para string para exibição no input
                valor_pagamento_value = form_data_to_template.get('Valor_Pagamento')
                form_data_to_template['valor_pagamento'] = "%.2f" % float(valor_pagamento_value) if valor_pagamento_value is not None else '0.00'
                
                # Outros campos textuais
                form_data_to_template['status_art'] = form_data_to_template['Status_Art'] if form_data_to_template.get('Status_Art') is not None else ''


            # Renderiza o template, sempre passando form_data_to_template como a variável 'art'
            return render_template(
                'obras/arts/edit_art.html',
                user=current_user,
                art=form_data_to_template, # AGORA SEMPRE PASSA form_data_to_template COMO 'art'
                all_obras=all_obras,
                status_options=status_options
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_art: {e}")
        return redirect(url_for('obras_bp.arts_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_art: {e}")
        return redirect(url_for('obras_bp.arts_module'))


@obras_bp.route('/arts/delete/<int:art_id>', methods=['POST'])
@login_required
@module_required('Obras')
def delete_art(art_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_art(art_id)
            if success:
                flash('ART excluída com sucesso!', 'success')
            else:
                flash('Erro ao excluir ART. Verifique se ela existe.', 'danger')
        return redirect(url_for('obras_bp.arts_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_art: {e}")
        return redirect(url_for('obras_bp.arts_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_art: {e}")
        return redirect(url_for('obras_bp.arts_module'))


@obras_bp.route('/arts/details/<int:art_id>')
@login_required
@module_required('Obras')
def art_details(art_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            art = obras_manager.get_art_by_id(art_id)

            if not art:
                flash('ART não encontrada.', 'danger')
                return redirect(url_for('obras_bp.arts_module'))

        return render_template(
            'obras/arts/art_details.html',
            user=current_user,
            art=art
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em art_details: {e}")
        return redirect(url_for('obras_bp.arts_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em art_details: {e}")
        return redirect(url_for('obras_bp.arts_module'))


@obras_bp.route('/arts/export/excel')
@login_required
@module_required('Obras')
def export_arts_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('obras_bp.arts_module'))

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
        return redirect(url_for('obras_bp.arts_module'))

# ===============================================================
# 3.5 ROTAS DE MEDICOES - OBRAS
# ===============================================================

@obras_bp.route('/medicoes')
@login_required
@module_required('Obras')
def medicoes_module(): 

    # ... (código de busca de filtros não muda) ...
    search_numero_medicao = request.args.get('numero_medicao')
    search_obra_id = request.args.get('obra_id')
    search_status = request.args.get('status_medicao')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            medicoes = obras_manager.get_all_medicoes(
                search_numero_medicao=search_numero_medicao,
                search_obra_id=search_obra_id,
                search_status=search_status
            )
            
            # --- SEÇÃO DE FORMATAÇÃO ATUALIZADA ---
            if medicoes:
                for medicao in medicoes:
                    # Usa nossa nova função de formatação
                    medicao['Valor_Medicao_Formatado'] = formatar_moeda_brl(medicao.get('Valor_Medicao'))
            # --- FIM DA ATUALIZAÇÃO ---

            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']

        return render_template(
            'obras/medicoes/medicoes_module.html',
            user=current_user,
            medicoes=medicoes,
            all_obras=all_obras,
            # ... (resto dos parâmetros)
        )
    except Exception as e:
        # ... (blocos except não mudam)
        flash(f"Ocorreu um erro inesperado ao carregar Medições: {e}", 'danger')
        print(f"Erro inesperado em medicoes_module: {e}")
        return redirect(url_for('obras_bp.obras_module'))

@obras_bp.route('/medicoes/add', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def add_medicao():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                    return redirect(url_for('obras_bp.medicoes_module'))
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
        return redirect(url_for('obras_bp.medicoes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_medicao: {e}")
        return redirect(url_for('obras_bp.medicoes_module'))


@obras_bp.route('/medicoes/edit/<int:medicao_id>', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def edit_medicao(medicao_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            medicao_from_db = obras_manager.get_medicao_by_id(medicao_id) # Renomeado para consistência

            if not medicao_from_db:
                flash('Medição não encontrada.', 'danger')
                return redirect(url_for('obras_bp.medicoes_module'))

            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Emitida', 'Aprovada', 'Paga', 'Rejeitada']

            # Inicializa form_data_to_template aqui
            form_data_to_template = {}
            
            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                # Conversões de data para objeto date/datetime.date
                data_medicao_obj = None
                data_aprovacao_obj = None
                is_valid = True

                data_medicao_str = form_data_received.get('data_medicao', '').strip()
                if data_medicao_str:
                    try:
                        data_medicao_obj = datetime.strptime(data_medicao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data da Medição inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                else:
                    flash('Data da Medição é obrigatória.', 'danger')
                    is_valid = False # Data da Medição é obrigatória

                data_aprovacao_str = form_data_received.get('data_aprovacao', '').strip()
                if data_aprovacao_str:
                    try:
                        data_aprovacao_obj = datetime.strptime(data_aprovacao_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Aprovação inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                # Conversões de valores numéricos
                numero_medicao = None
                try:
                    numero_medicao_str = form_data_received.get('numero_medicao', '').strip()
                    if numero_medicao_str:
                        numero_medicao = int(numero_medicao_str)
                    else:
                        flash('Número da Medição é obrigatório.', 'danger')
                        is_valid = False
                except ValueError:
                    flash('Número da Medição inválido. Use números inteiros.', 'danger')
                    is_valid = False

                valor_medicao = None
                try:
                    valor_medicao_str = form_data_received.get('valor_medicao', '').strip()
                    if valor_medicao_str:
                        valor_medicao = float(valor_medicao_str.replace(',', '.'))
                    else:
                        flash('Valor da Medição é obrigatório.', 'danger')
                        is_valid = False
                except ValueError:
                    flash('Valor da Medição inválido. Use números.', 'danger')
                    is_valid = False

                # Captura de outros campos
                mes_referencia = form_data_received.get('mes_referencia', '').strip()
                status_medicao = form_data_received.get('status_medicao', '').strip()
                observacao_medicao = form_data_received.get('observacao_medicao', '').strip()
                id_obras = int(form_data_received.get('id_obras')) # ID da obra é obrigatório

                if not all([status_medicao, id_obras]): # Validação final de campos obrigatórios
                        flash('Status e Obra são obrigatórios.', 'danger')
                        is_valid = False

                # Validação de unicidade
                existing_medicao = obras_manager.get_medicao_by_obra_numero(id_obras, numero_medicao)
                if existing_medicao and existing_medicao['ID_Medicoes'] != medicao_id:
                    flash('Já existe uma medição com este número para a obra selecionada. Use um número único.', 'danger')
                    is_valid = False

                # --- SE ALGUMA VALIDAÇÃO FALHOU NO POST ---
                if not is_valid:
                    form_data_to_template = form_data_received.copy() # Copia para repopular
                    # Garante que as strings originais do form sejam usadas para repopular os inputs
                    form_data_to_template['data_medicao'] = data_medicao_str
                    form_data_to_template['data_aprovacao'] = data_aprovacao_str
                    form_data_to_template['numero_medicao'] = numero_medicao_str
                    form_data_to_template['valor_medicao'] = valor_medicao_str
                    form_data_to_template['id_obras'] = id_obras_str # ID da obra como string
                    form_data_to_template['medicao_id'] = medicao_id # Passa o ID da medição também

                    return render_template(
                        'obras/medicoes/edit_medicao.html',
                        user=current_user,
                        medicao=form_data_to_template, # Passa os dados para repopular
                        all_obras=all_obras,
                        status_options=status_options
                    )

                # --- SE TODAS AS VALIDAÇÕES PASSARAM NO POST ---
                success = obras_manager.update_medicao(
                    medicao_id, id_obras, numero_medicao, valor_medicao, data_medicao_obj, mes_referencia, data_aprovacao_obj, status_medicao, observacao_medicao
                )
                if success:
                    flash('Medição atualizada com sucesso!', 'success')
                    return redirect(url_for('obras_bp.medicoes_module'))
                else:
                    flash('Erro ao atualizar medição.', 'danger')
            
            else: # GET request (carregar dados do DB para o formulário)
                # Popula form_data_to_template com os dados do banco de dados, normalizando as chaves
                # e garantindo que o ID da medição seja 'medicao_id'
                form_data_to_template['medicao_id'] = medicao_from_db['ID_Medicoes']
                form_data_to_template['id_obras'] = str(medicao_from_db['ID_Obras']) if medicao_from_db['ID_Obras'] is not None else ''
                form_data_to_template['numero_medicao'] = str(medicao_from_db['Numero_Medicao']) if medicao_from_db['Numero_Medicao'] is not None else ''
                form_data_to_template['valor_medicao'] = "%.2f" % medicao_from_db['Valor_Medicao'] if medicao_from_db['Valor_Medicao'] is not None else ''
                
                form_data_to_template['data_medicao'] = medicao_from_db['Data_Medicao'].strftime('%Y-%m-%d') if medicao_from_db['Data_Medicao'] else ''
                form_data_to_template['mes_referencia'] = medicao_from_db['Mes_Referencia'] if medicao_from_db['Mes_Referencia'] is not None else ''
                form_data_to_template['data_aprovacao'] = medicao_from_db['Data_Aprovacao'].strftime('%Y-%m-%d') if medicao_from_db['Data_Aprovacao'] else ''
                form_data_to_template['status_medicao'] = medicao_from_db['Status_Medicao'] if medicao_from_db['Status_Medicao'] is not None else ''
                form_data_to_template['observacao_medicao'] = medicao_from_db['Observacao_Medicao'] if medicao_from_db['Observacao_Medicao'] is not None else ''


            # Renderiza o template, sempre passando form_data_to_template como a variável 'medicao'
            return render_template(
                'obras/medicoes/edit_medicao.html',
                user=current_user,
                medicao=form_data_to_template, # AGORA SEMPRE PASSA form_data_to_template COMO 'medicao'
                all_obras=all_obras,
                status_options=status_options
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_medicao: {e}")
        return redirect(url_for('obras_bp.medicoes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_medicao: {e}")
        return redirect(url_for('obras_bp.medicoes_module'))


@obras_bp.route('/medicoes/delete/<int:medicao_id>', methods=['POST'])
@login_required
@module_required('Obras')
def delete_medicao(medicao_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_medicao(medicao_id)
            if success:
                flash('Medição excluída com sucesso!', 'success')
            else:
                flash('Erro ao excluir medição. Verifique se ela existe.', 'danger')
        return redirect(url_for('obras_bp.medicoes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_medicao: {e}")
        return redirect(url_for('obras_bp.medicoes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_medicao: {e}")
        return redirect(url_for('obras_bp.medicoes_module'))


@obras_bp.route('/medicoes/details/<int:medicao_id>')
@login_required
@module_required('Obras')
def medicao_details(medicao_id):
   
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            medicao = obras_manager.get_medicao_by_id(medicao_id)

            if not medicao:
                flash('Medição não encontrada.', 'danger')
                return redirect(url_for('obras_bp.medicoes_module'))

            # --- SEÇÃO DE FORMATAÇÃO ATUALIZADA ---
            if medicao:
                # Usa nossa nova função de formatação
                medicao['Valor_Medicao_Formatado'] = formatar_moeda_brl(medicao.get('Valor_Medicao'))
            # --- FIM DA ATUALIZAÇÃO ---

        return render_template(
            'obras/medicoes/medicao_details.html',
            user=current_user,
            medicao=medicao
        )
    except Exception as e:
        # ... (blocos except não mudam)
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em medicao_details: {e}")
        return redirect(url_for('obras_bp.medicoes_module'))


@obras_bp.route('/medicoes/export/excel')
@login_required
@module_required('Obras')
def export_medicoes_excel():

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('obras_bp.medicoes_module'))

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
        return redirect(url_for('obras_bp.medicoes_module'))

# ===============================================================
# 3.6 ROTAS DE AVANCO FISICO - OBRAS
# ===============================================================

@obras_bp.route('/avancos_fisicos')
@login_required
@module_required('Obras')
def avancos_fisicos_module(): 
    
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
        return redirect(url_for('obras_bp.avancos_fisicos_module')) 

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        return redirect(url_for('obras_bp.obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Avanços Físicos: {e}", 'danger')
        print(f"Erro inesperado em avancos_fisicos_module: {e}")
        return redirect(url_for('obras_bp.obras_module')) 


@obras_bp.route('/avancos_fisicos/add', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def add_avanco_fisico():

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            form_data_to_template = {} # Para repopular o formulário em caso de erro

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                data_avanco_obj = None
                is_valid = True

                # Validação e Conversão de Data de Avanço
                data_avanco_str = form_data_received.get('data_avanco', '').strip()
                if data_avanco_str:
                    try:
                        data_avanco_obj = datetime.strptime(data_avanco_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Avanço inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                else:
                    flash('Data de Avanço é obrigatória.', 'danger')
                    is_valid = False

                # Validação e Conversão de Percentual de Avanço Físico
                percentual_avanco_fisico = None
                percentual_avanco_fisico_str = form_data_received.get('percentual_avanco_fisico', '').strip()
                if percentual_avanco_fisico_str:
                    try:
                        percentual_avanco_fisico = float(percentual_avanco_fisico_str.replace(',', '.'))
                    except ValueError:
                        flash('Percentual de Avanço Físico inválido. Use números.', 'danger')
                        is_valid = False
                    
                    if percentual_avanco_fisico is not None and not (0 <= percentual_avanco_fisico <= 100):
                        flash('Percentual de Avanço Físico deve ser entre 0 e 100.', 'danger')
                        is_valid = False
                else:
                    flash('Percentual de Avanço Físico é obrigatório.', 'danger')
                    is_valid = False
                
                # Validação e Conversão de ID da Obra
                id_obras = None
                id_obras_str = form_data_received.get('id_obras', '').strip()
                if id_obras_str:
                    try:
                        id_obras = int(id_obras_str)
                    except ValueError:
                        flash('ID da Obra inválido.', 'danger')
                        is_valid = False
                else:
                    flash('Obra é obrigatória.', 'danger')
                    is_valid = False

                # --- NOVA VALIDAÇÃO: NÃO PERMITIR AVANÇO ACUMULADO > 100% ---
                if is_valid: # Só faz a validação se os campos básicos já são válidos
                    avanco_acumulado_atual = obras_manager.get_avanco_acumulado_para_obra(id_obras)
                    
                    if (avanco_acumulado_atual + percentual_avanco_fisico) > 100.0:
                        flash(f'O avanço físico total da obra "{obras_manager.get_obra_by_id(id_obras)["Nome_Obra"]}" excederia 100% com este lançamento. Avanço acumulado atual: {avanco_acumulado_atual:.2f}%.', 'danger')
                        is_valid = False
                # --- FIM DA NOVA VALIDAÇÃO ---

                # Se alguma validação falhou, repopula o formulário
                if not is_valid:
                    form_data_to_template = form_data_received.copy()
                    form_data_to_template['data_avanco'] = data_avanco_str
                    form_data_to_template['percentual_avanco_fisico'] = percentual_avanco_fisico_str
                    form_data_to_template['id_obras'] = id_obras_str

                    # Calcula o avanço acumulado para exibir no template mesmo em caso de erro
                    if id_obras: # Só se a obra for válida para calcular o acumulado
                            form_data_to_template['avanco_acumulado_obra'] = obras_manager.get_avanco_acumulado_para_obra(id_obras)
                    else:
                            form_data_to_template['avanco_acumulado_obra'] = 0.0 # Se não tem obra selecionada, acumulado é 0

                    return render_template(
                        'obras/avancos_fisicos/add_avanco_fisico.html',
                        user=current_user,
                        all_obras=all_obras,
                        avanco=form_data_to_template # Passa os dados para repopular
                    )

                # Se todas as validações passaram, tenta adicionar
                success = obras_manager.add_avanco_fisico(
                    id_obras, percentual_avanco_fisico, data_avanco_obj
                )
                if success:
                    flash('Avanço Físico adicionado com sucesso!', 'success')
                    return redirect(url_for('obras_bp.avancos_fisicos_module'))
                else:
                    flash('Erro ao adicionar avanço físico.', 'danger')
            
            else: # GET request
                # Ao carregar o formulário pela primeira vez, não há avanço acumulado para exibir
                # a menos que uma obra já esteja pré-selecionada (o que não é o caso aqui).
                # Mas podemos passar um valor padrão para o template.
                form_data_to_template['avanco_acumulado_obra'] = 0.0 # Valor inicial para o template

            return render_template(
                'obras/avancos_fisicos/add_avanco_fisico.html',
                user=current_user,
                all_obras=all_obras,
                avanco=form_data_to_template # Passa os dados para o template (incluindo acumulado inicial)
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_avanco_fisico: {e}")
        return redirect(url_for('obras_bp.avancos_fisicos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_avanco_fisico: {e}")
        return redirect(url_for('obras_bp.avancos_fisicos_module'))


@obras_bp.route('/avancos_fisicos/edit/<int:avanco_id>', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def edit_avanco_fisico(avanco_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            avanco_from_db = obras_manager.get_avanco_fisico_by_id(avanco_id)

            if not avanco_from_db:
                flash('Avanço Físico não encontrado.', 'danger')
                return redirect(url_for('obras_bp.avancos_fisicos_module'))

            all_obras = obras_manager.get_all_obras_for_dropdown()
            
            form_data_to_template = {} # Inicializa como um dicionário vazio

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                data_avanco_obj = None
                is_valid = True

                # Validação e Conversão de Data de Avanço
                data_avanco_str = form_data_received.get('data_avanco', '').strip()
                if data_avanco_str:
                    try:
                        data_avanco_obj = datetime.strptime(data_avanco_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Avanço inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                else:
                    flash('Data de Avanço é obrigatória.', 'danger')
                    is_valid = False

                # Validação e Conversão de Percentual de Avanço Físico
                percentual_avanco_fisico = None
                percentual_avanco_fisico_str = form_data_received.get('percentual_avanco_fisico', '').strip()
                if percentual_avanco_fisico_str:
                    try:
                        percentual_avanco_fisico = float(percentual_avanco_fisico_str.replace(',', '.'))
                    except ValueError:
                        flash('Percentual de Avanço Físico inválido. Use números.', 'danger')
                        is_valid = False
                    
                    if percentual_avanco_fisico is not None and not (0 <= percentual_avanco_fisico <= 100):
                        flash('Percentual de Avanço Físico deve ser entre 0 e 100.', 'danger')
                        is_valid = False
                else:
                    flash('Percentual de Avanço Físico é obrigatório.', 'danger')
                    is_valid = False
                
                # Validação e Conversão de ID da Obra
                id_obras = None
                id_obras_str = form_data_received.get('id_obras', '').strip()
                if id_obras_str:
                    try:
                        id_obras = int(id_obras_str)
                    except ValueError:
                        flash('ID da Obra inválido.', 'danger')
                        is_valid = False
                else:
                    flash('Obra é obrigatória.', 'danger')
                    is_valid = False

                # --- VALIDAÇÃO: NÃO PERMITIR AVANÇO ACUMULADO > 100% (EDITAR) ---
                if is_valid: # Só faz a validação se os campos básicos já são válidos
                    avanco_acumulado_anterior = obras_manager.get_avanco_acumulado_para_obra(id_obras, avanco_id_excluir=avanco_id)
                    
                    if (avanco_acumulado_anterior + percentual_avanco_fisico) > 100.0:
                        flash(f'O avanço físico total da obra "{obras_manager.get_obra_by_id(id_obras)["Nome_Obra"]}" excederia 100% com esta edição. Avanço acumulado anterior (sem esta edição): {avanco_acumulado_anterior:.2f}%.', 'danger')
                        is_valid = False
                # --- FIM DA VALIDAÇÃO ---

                # Se alguma validação falhou, repopula o formulário com os dados recebidos (já em minúsculas)
                if not is_valid:
                    form_data_to_template = form_data_received.copy()
                    form_data_to_template['data_avanco'] = data_avanco_str
                    form_data_to_template['percentual_avanco_fisico'] = percentual_avanco_fisico_str
                    form_data_to_template['id_obras'] = id_obras_str
                    form_data_to_template['id_avancos_fisicos'] = avanco_id # Garante que o ID do avanço esteja aqui, em minúscula

                    # Calcula o avanço acumulado para exibir no template mesmo em caso de erro
                    if id_obras: 
                            form_data_to_template['avanco_acumulado_obra'] = obras_manager.get_avanco_acumulado_para_obra(id_obras, avanco_id_excluir=avanco_id)
                    else:
                            form_data_to_template['avanco_acumulado_obra'] = 0.0

                    return render_template(
                        'obras/avancos_fisicos/edit_avanco_fisico.html',
                        user=current_user,
                        avanco=form_data_to_template,
                        all_obras=all_obras
                    )

                # Se todas as validações passaram, tenta atualizar
                success = obras_manager.update_avanco_fisico(
                    avanco_id, id_obras, percentual_avanco_fisico, data_avanco_obj
                )
                if success:
                    flash('Avanço Físico atualizado com sucesso!', 'success')
                    return redirect(url_for('obras_bp.avancos_fisicos_module'))
                else:
                    flash('Erro ao atualizar avanço físico.', 'danger')
                
            else: # GET request (carregar dados do DB para o formulário)
                # Popula form_data_to_template com os dados do banco de dados, normalizando as chaves para minúsculas
                # e garantindo que o ID do avanço seja 'id_avancos_fisicos'
                form_data_to_template['id_avancos_fisicos'] = avanco_from_db['ID_Avancos_Fisicos']
                form_data_to_template['id_obras'] = str(avanco_from_db['ID_Obras']) if avanco_from_db['ID_Obras'] is not None else ''
                
                percentual_value = avanco_from_db.get('Percentual_Avanco_Fisico')
                form_data_to_template['percentual_avanco_fisico'] = "%.2f" % float(percentual_value) if percentual_value is not None else ''

                form_data_to_template['data_avanco'] = avanco_from_db['Data_Avanco'].strftime('%Y-%m-%d') if avanco_from_db['Data_Avanco'] else ''
                
                # Calcula o avanço acumulado para exibir no template no GET inicial
                # Passamos o avanco_id para EXCLUIR o próprio avanço atual do cálculo
                if form_data_to_template['id_obras']:
                    form_data_to_template['avanco_acumulado_obra'] = obras_manager.get_avanco_acumulado_para_obra(
                        int(form_data_to_template['id_obras']), avanco_id_excluir=avanco_id
                    )
                else:
                    form_data_to_template['avanco_acumulado_obra'] = 0.0

            # Renderiza o template, sempre passando form_data_to_template como a variável 'avanco'
            return render_template(
                'obras/avancos_fisicos/edit_avanco_fisico.html',
                user=current_user,
                avanco=form_data_to_template, # AGORA SEMPRE PASSA form_data_to_template COMO 'avanco' (chaves minúsculas)
                all_obras=all_obras
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_avanco_fisico: {e}")
        return redirect(url_for('obras_bp.avancos_fisicos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_avanco_fisico: {e}")
        return redirect(url_for('obras_bp.avancos_fisicos_module'))



@obras_bp.route('/avancos_fisicos/delete/<int:avanco_id>', methods=['POST'])
@login_required
@module_required('Obras')
def delete_avanco_fisico(avanco_id):
  
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_avanco_fisico(avanco_id)
            if success:
                flash('Avanço Físico excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir avanço físico. Verifique se ele existe.', 'danger')
        return redirect(url_for('obras_bp.avancos_fisicos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_avanco_fisico: {e}")
        return redirect(url_for('obras_bp.avancos_fisicos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_avanco_fisico: {e}")
        return redirect(url_for('obras_bp.avancos_fisicos_module'))


@obras_bp.route('/avancos_fisicos/details/<int:avanco_id>', methods=['GET'])
@login_required
@module_required('Obras')
def avanco_fisico_details(avanco_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            avanco = obras_manager.get_avanco_fisico_by_id(avanco_id)

            if not avanco:
                flash('Avanço Físico não encontrado.', 'danger')
                return redirect(url_for('obras_bp.avancos_fisicos_module'))

            # Obter o nome da obra associada
            obra_info = obras_manager.get_obra_by_id(avanco['ID_Obras'])
            nome_obra = obra_info['Nome_Obra'] if obra_info else 'Obra Desconhecida'

            # --- NOVO: Obter o avanço físico acumulado da obra ---
            avanco_acumulado_obra = obras_manager.get_avanco_acumulado_para_obra(avanco['ID_Obras'])
            # --- FIM DO NOVO ---

            return render_template(
                'obras/avancos_fisicos/avanco_fisico_details.html',
                user=current_user,
                avanco=avanco,
                nome_obra=nome_obra,
                avanco_acumulado_obra=avanco_acumulado_obra # Passa o avanço acumulado para o template
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em avanco_fisico_details: {e}")
        return redirect(url_for('obras_bp.avancos_fisicos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em avanco_fisico_details: {e}")
        return redirect(url_for('obras_bp.avancos_fisicos_module'))

@obras_bp.route('/avancos_fisicos/export/excel')
@login_required
@module_required('Obras')
def export_avancos_fisicos_excel():
   
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('obras_bp.avancos_fisicos_module')) 

            avancos_data = obras_manager.get_all_avancos_fisicos(
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_data_inicio=search_data_inicio,
                search_data_fim=search_data_fim
            )

            if not avancos_data:
                flash('Nenhuma Avanço Físico encontrado para exportar.', 'info')
                return redirect(url_for('obras_bp.avancos_fisicos_module'))

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
        return redirect(url_for('obras_bp.avancos_fisicos_module'))

# --- NOVA ROTA: Endpoint AJAX para obter avanço acumulado ---
@obras_bp.route('/get_acumulado_obra/<int:obra_id>', methods=['GET'])
@obras_bp.route('/get_acumulado_obra/<int:obra_id>/<int:avanco_id_excluir>', methods=['GET'])
@login_required
def get_acumulado_obra(obra_id, avanco_id_excluir=None):
    """
    Endpoint AJAX para retornar o percentual de avanço físico acumulado de uma obra.
    Pode excluir um avanço específico do cálculo (para edição).
    """
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            
            # Chama o método que já criamos no manager
            acumulado = obras_manager.get_avanco_acumulado_para_obra(obra_id, avanco_id_excluir)
            
            # Retorna o valor como JSON
            return jsonify({'avanco_acumulado': acumulado})

    except Exception as e:
        # Em caso de erro, retorna 0.0 e um status de erro para o frontend
        print(f"Erro ao obter avanço acumulado via AJAX: {e}")
        return jsonify({'avanco_acumulado': 0.0, 'error': str(e)}), 500


# ===============================================================
# 3.7 ROTAS DE REIDI - OBRAS
# ===============================================================

@obras_bp.route('/reidis')
@login_required
@module_required('Obras')
def reidis_module(): 
    
    search_numero_portaria = request.args.get('numero_portaria')
    search_numero_ato = request.args.get('numero_ato')
    search_obra_id = request.args.get('obra_id')
    search_status = request.args.get('status_reidi')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        return redirect(url_for('obras_bp.obras_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar REIDIs: {e}", 'danger')
        print(f"Erro inesperado em reidis_module: {e}")
        return redirect(url_for('obras_bp.obras_module'))


@obras_bp.route('/reidis/add', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def add_reidi():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)

            # --- CORRIGIDO AQUI: DEFINIR AS VARIÁVEIS PARA O DROPDOWN SEMPRE ---
            all_obras = obras_manager.get_all_obras_for_dropdown() # <-- MOVIDA PARA CÁ
            status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise'] # <-- MOVIDA PARA CÁ
            # --- FIM DA CORREÇÃO ---
            # Inicializa form_data_to_template para preencher o formulário em caso de erro ou GET
            form_data_to_template = {}
            
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

                #if obras_manager.get_reidi_by_numero_portaria(numero_portaria):
                #    flash('Número da Portaria já existe. Por favor, use um número único.', 'danger')
                #    all_obras = obras_manager.get_all_obras_for_dropdown()
                #    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                #    return render_template(
                #        'obras/reidis/add_reidi.html',
                #        user=current_user,
                #        all_obras=all_obras,
                #        status_options=status_options,
                #        form_data=request.form
                #    )

                #if obras_manager.get_reidi_by_numero_ato_declaratorio(numero_ato_declaratorio):
                #    flash('Número do Ato Declaratório já existe. Por favor, use um número único.', 'danger')
                #    all_obras = obras_manager.get_all_obras_for_dropdown()
                #    status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise']
                #    return render_template(
                #        'obras/reidis/add_reidi.html',
                #        user=current_user,
                #        all_obras=all_obras,
                #        status_options=status_options,
                #        form_data=request.form
                #    )

                success = obras_manager.add_reidi(
                    id_obras, numero_portaria, numero_ato_declaratorio, data_aprovacao_reidi, data_validade_reidi, status_reidi, observacoes_reidi
                )
                if success:
                    flash('REIDI adicionado com sucesso!', 'success')
                    return redirect(url_for('obras_bp.reidis_module'))
                else:
                    flash('Erro ao adicionar REIDI. Verifique os dados e tente novamente.', 'danger')

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
        return redirect(url_for('obras_bp.reidis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_reidi: {e}")
        return redirect(url_for('obras_bp.reidis_module'))


@obras_bp.route('/reidis/edit/<int:reidi_id>', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def edit_reidi(reidi_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            reidi_from_db = obras_manager.get_reidi_by_id(reidi_id) # Renomeado para evitar conflito

            if not reidi_from_db:
                flash('REIDI não encontrado.', 'danger')
                return redirect(url_for('obras_bp.reidis_module'))

            # Prepara opções para dropdowns
            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Ativo', 'Inativo', 'Vencido', 'Em Análise'] 

            # Inicializa form_data_to_template aqui, será preenchido com dados do DB (GET) ou do form (POST com erro)
            form_data_to_template = {}
            
            if request.method == 'POST':
                # Captura todos os dados do formulário
                form_data_received = request.form.to_dict()

                # Tentativas de conversão de datas (podem falhar e precisam de tratamento)
                data_aprovacao_reidi_obj = None
                data_validade_reidi_obj = None
                is_valid = True

                data_aprovacao_reidi_str = form_data_received.get('data_aprovacao_reidi', '').strip()
                if data_aprovacao_reidi_str:
                    try:
                        data_aprovacao_reidi_obj = datetime.strptime(data_aprovacao_reidi_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Aprovação inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                data_validade_reidi_str = form_data_received.get('data_validade_reidi', '').strip()
                if data_validade_reidi_str:
                    try:
                        data_validade_reidi_obj = datetime.strptime(data_validade_reidi_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Validade inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False

                # Outras validações do POST
                numero_portaria = form_data_received.get('numero_portaria', '').strip()
                numero_ato_declaratorio = form_data_received.get('numero_ato_declaratorio', '').strip()
                id_obras = int(form_data_received.get('id_obras'))
                status_reidi = form_data_received.get('status_reidi', '').strip()

                if not all([numero_portaria, numero_ato_declaratorio, id_obras]):
                    flash('Campos obrigatórios (Número da Portaria, Número do Ato Declaratório, Obra) não podem ser vazios.', 'danger')
                    is_valid = False

                ## Unicidade dos números
                #existing_reidi_portaria = obras_manager.get_reidi_by_numero_portaria(numero_portaria)
                #if existing_reidi_portaria and existing_reidi_portaria['ID_Reidis'] != reidi_id:
                #    flash('Número da Portaria já existe. Por favor, use um número único.', 'danger')
                #    is_valid = False

                #existing_reidi_ato = obras_manager.get_reidi_by_numero_ato_declaratorio(numero_ato_declaratorio)
                #if existing_reidi_ato and existing_reidi_ato['ID_Reidis'] != reidi_id:
                #    flash('Número do Ato Declaratório já existe. Por favor, use um número único.', 'danger')
                #   is_valid = False

                # Se alguma validação falhou, passamos os dados recebidos para re-preencher o form
                if not is_valid:
                    form_data_to_template = form_data_received # Repopula com os dados que o usuário digitou
                    # Assegura que datas que voltaram do form e são válidas, sejam passadas como string para o input
                    form_data_to_template['data_aprovacao_reidi'] = data_aprovacao_reidi_str
                    form_data_to_template['data_validade_reidi'] = data_validade_reidi_str
                    
                    # Garante que campos numericos/textuais também sejam string para o template, se a validação falhou
                    # form_data_to_template['numero_portaria'] = form_data_to_template.get('numero_portaria', '')

                    return render_template(
                        'obras/reidis/edit_reidi.html',
                        user=current_user,
                        reidi=form_data_to_template, # Passa form_data_to_template como 'reidi'
                        all_obras=all_obras,
                        status_options=status_options
                    )

                # Se todas as validações passaram, tenta atualizar
                observacoes_reidi = form_data_received.get('observacoes_reidi', '').strip()
                success = obras_manager.update_reidi(
                    reidi_id, id_obras, numero_portaria, numero_ato_declaratorio, data_aprovacao_reidi_obj, 
                    data_validade_reidi_obj, status_reidi, observacoes_reidi
                )
                if success:
                    flash('REIDI atualizado com sucesso!', 'success')
                    return redirect(url_for('obras_bp.reidis_module'))
                else:
                    flash('Erro ao atualizar REIDI.', 'danger')
                
            else: # GET request (carregar dados do DB para o formulário)
                # Popula form_data_to_template com os dados do banco de dados
                form_data_to_template = reidi_from_db.copy()

                # Formata as datas para o formato 'YYYY-MM-DD' para os inputs HTML
                form_data_to_template['Data_Aprovacao_Reidi'] = reidi_from_db['Data_Aprovacao_Reidi'].strftime('%Y-%m-%d') if reidi_from_db['Data_Aprovacao_Reidi'] else ''
                form_data_to_template['Data_Validade_Reidi'] = reidi_from_db['Data_Validade_Reidi'].strftime('%Y-%m-%d') if reidi_from_db['Data_Validade_Reidi'] else ''
                
                # Converte outros campos que podem ser None em string vazia
                for key in ['Numero_Portaria', 'Numero_Ato_Declaratorio', 'Observacoes_Reidi', 'Status_Reidi']:
                    if key in form_data_to_template and form_data_to_template[key] is None:
                        form_data_to_template[key] = ''

            # Renderiza o template, sempre passando form_data_to_template como a variável 'reidi'
            return render_template(
                'obras/reidis/edit_reidi.html',
                user=current_user,
                reidi=form_data_to_template, # AGORA SEMPRE PASSA form_data_to_template COMO 'reidi'
                all_obras=all_obras,
                status_options=status_options
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_reidi: {e}")
        return redirect(url_for('obras_bp.reidis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_reidi: {e}")
        return redirect(url_for('obras_bp.reidis_module'))


@obras_bp.route('/reidis/delete/<int:reidi_id>', methods=['POST'])
@login_required
@module_required('Obras')
def delete_reidi(reidi_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_reidi(reidi_id)
            if success:
                flash('REIDI excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir REIDI. Verifique se ele existe.', 'danger')
        return redirect(url_for('obras_bp.reidis_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_reidi: {e}")
        return redirect(url_for('obras_bp.reidis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_reidi: {e}")
        return redirect(url_for('obras_bp.reidis_module'))


@obras_bp.route('/reidis/details/<int:reidi_id>')
@login_required
@module_required('Obras')
def reidi_details(reidi_id):

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            reidi = obras_manager.get_reidi_by_id(reidi_id)

            if not reidi:
                flash('REIDI não encontrado.', 'danger')
                return redirect(url_for('obras_bp.reidis_module'))

        return render_template(
            'obras/reidis/reidi_details.html',
            user=current_user,
            reidi=reidi
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em reidi_details: {e}")
        return redirect(url_for('obras_bp.reidis_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em reidi_details: {e}")
        return redirect(url_for('obras_bp.reidis_module'))


@obras_bp.route('/reidis/export/excel')
@login_required
@module_required('Obras')
def export_reidis_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('obras_bp.reidis_module'))

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
        return redirect(url_for('obras_bp.reidis_module'))

# ===============================================================
# 3.8 ROTAS DE SEGUROS - OBRAS
# ===============================================================

@obras_bp.route('/seguros')
@login_required
@module_required('Obras')
def seguros_module(): 
    
    search_numero_apolice = request.args.get('numero_apolice')
    search_obra_id = request.args.get('obra_id')
    search_status = request.args.get('status_seguro')
    search_tipo = request.args.get('tipo_seguro')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)

            seguros = obras_manager.get_all_seguros(
                search_numero_apolice=search_numero_apolice,
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_status=search_status,
                search_tipo=search_tipo
            )

            # --- NOVA SEÇÃO: Formatação de moeda para a lista de seguros ---
            if seguros:
                for seguro in seguros:
                    seguro['Valor_Segurado_Formatado'] = formatar_moeda_brl(seguro.get('Valor_Segurado'))
            # --- FIM DA NOVA SEÇÃO ---

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
        return redirect(url_for('obras_bp.obras_module')) 
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em seguros_module: {e}")
        return redirect(url_for('obras_bp.obras_module'))

@obras_bp.route('/seguros/add', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def add_seguro():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            
            # --- CORRIGIDO AQUI: DEFINIR AS VARIÁVEIS PARA O DROPDOWN SEMPRE ---
            all_obras = obras_manager.get_all_obras_for_dropdown() # <-- MOVIDA PARA CÁ
            status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação'] # <-- MOVIDA PARA CÁ
            tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros'] # <-- MOVIDA PARA CÁ
            # --- FIM DA CORREÇÃO ---

            # Inicializa form_data_to_template para preencher o formulário em caso de erro ou GET
            form_data_to_template = {}

            if request.method == 'POST':
                id_obras = int(request.form['id_obras'])
                numero_apolice = request.form['numero_apolice'].strip()
                seguradora = request.form['seguradora'].strip()
                tipo_seguro = request.form['tipo_seguro'].strip()
                #valor_segurado = float(request.form.get('valor_segurado', '0').replace(',', '.'))
                # VERSÃO CORRIGIDA:
                valor_segurado_str = request.form.get('valor_segurado', '0').replace(',', '.')
                valor_segurado = Decimal(valor_segurado_str)                
                data_inicio_vigencia_str = request.form.get('data_inicio_vigencia', '').strip()
                data_fim_vigencia_str = request.form.get('data_fim_vigencia', '').strip()
                status_seguro = request.form.get('status_seguro', '').strip()
                observacoes_seguro = request.form.get('observacoes_seguro', '').strip()

                if not all([id_obras, numero_apolice, seguradora, tipo_seguro, data_inicio_vigencia_str]):
                    flash('Campos obrigatórios (Obra, Número da Apólice, Seguradora, Tipo, Data Início Vigência) não podem ser vazios.', 'danger')
                    # Já temos all_obras, status_options, tipo_seguro_options definidos acima
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
                    # Já temos all_obras, status_options, tipo_seguro_options definidos acima
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
                    # Já temos all_obras, status_options, tipo_seguro_options definidos acima
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
                    return redirect(url_for('obras_bp.seguros_module'))
                else:
                    flash('Erro ao adicionar seguro. Verifique os dados e tente novamente.', 'danger')
            
            # --- ESTE BLOCO AGORA SÓ PRECISA RENDERIZAR, POIS AS VARIAVEIS FORAM DEFINIDAS ACIMA ---
            return render_template(
                'obras/seguros/add_seguro.html',
                user=current_user,
                all_obras=all_obras,
                status_options=status_options,
                tipo_seguro_options=tipo_seguro_options,
                form_data={} # Para o GET, form_data é vazio
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em add_seguro: {e}")
        return redirect(url_for('obras_bp.seguros_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_seguro: {e}")
        return redirect(url_for('obras_bp.seguros_module'))


@obras_bp.route('/seguros/edit/<int:seguro_id>', methods=['GET', 'POST'])
@login_required
@module_required('Obras')
def edit_seguro(seguro_id):
   
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            seguro_from_db = obras_manager.get_seguro_by_id(seguro_id)

            if not seguro_from_db:
                flash('Seguro não encontrado.', 'danger')
                return redirect(url_for('obras_bp.seguros_module'))

            all_obras = obras_manager.get_all_obras_for_dropdown()
            status_options = ['Ativo', 'Vencido', 'Cancelado', 'Em Renovação']
            tipo_seguro_options = ['Responsabilidade Civil', 'Riscos de Engenharia', 'Garantia', 'Frota', 'Outros']

            form_data = {}

            if request.method == 'POST':
                form_data = request.form.to_dict()
                is_valid = True

                id_obras_str = form_data.get('id_obras')
                numero_apolice = form_data.get('numero_apolice', '').strip()
                seguradora = form_data.get('seguradora', '').strip()
                tipo_seguro = form_data.get('tipo_seguro', '').strip()
                valor_segurado_str = form_data.get('valor_segurado', '0').strip()
                data_inicio_vigencia_str = form_data.get('data_inicio_vigencia', '').strip()
                data_fim_vigencia_str = form_data.get('data_fim_vigencia', '').strip()
                status_seguro = form_data.get('status_seguro', '').strip()
                observacoes_seguro = form_data.get('observacoes_seguro', '').strip()

                if not all([id_obras_str, numero_apolice, seguradora, tipo_seguro, data_inicio_vigencia_str]):
                    flash('Campos obrigatórios (Obra, Apólice, Seguradora, Tipo, Início Vigência) não podem ser vazios.', 'danger')
                    is_valid = False

                id_obras = int(id_obras_str) if id_obras_str else None
                
                # --- ÁREA DA CORREÇÃO ---
                try:
                    # Usamos Decimal em vez de float para manter a precisão
                    valor_segurado = Decimal(valor_segurado_str.replace(',', '.')) if valor_segurado_str else Decimal('0.0')
                except InvalidOperation: # Usamos InvalidOperation para o erro de conversão do Decimal
                    flash('Valor Segurado inválido. Use apenas números.', 'danger')
                    is_valid = False
                    valor_segurado = Decimal('0.0')
                # --- FIM DA CORREÇÃO ---

                data_inicio_vigencia = None
                try:
                    if data_inicio_vigencia_str:
                        data_inicio_vigencia = datetime.strptime(data_inicio_vigencia_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato da Data de Início de Vigência inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False

                data_fim_vigencia = None
                try:
                    if data_fim_vigencia_str:
                        data_fim_vigencia = datetime.strptime(data_fim_vigencia_str, '%Y-%m-%d').date()
                except ValueError:
                    flash('Formato da Data de Fim de Vigência inválido. Use AAAA-MM-DD.', 'danger')
                    is_valid = False

                existing_seguro = obras_manager.get_seguro_by_numero_apolice(numero_apolice)
                if existing_seguro and existing_seguro['ID_Seguros'] != seguro_id:
                    flash('Número da Apólice já pertence a outro seguro.', 'danger')
                    is_valid = False

                if not is_valid:
                    return render_template(
                        'obras/seguros/edit_seguro.html',
                        user=current_user,
                        seguro=seguro_from_db,
                        form_data=form_data,
                        all_obras=all_obras,
                        status_options=status_options,
                        tipo_seguro_options=tipo_seguro_options
                    )

                success = obras_manager.update_seguro(
                    seguro_id, id_obras, numero_apolice, seguradora, tipo_seguro, valor_segurado, 
                    data_inicio_vigencia, data_fim_vigencia, status_seguro, observacoes_seguro
                )
                if success:
                    flash('Seguro atualizado com sucesso!', 'success')
                    return redirect(url_for('obras_bp.seguros_module'))
                else:
                    flash('Erro ao atualizar seguro.', 'danger')
            
            # GET request
            form_data = {
                'id_obras': seguro_from_db.get('ID_Obras'),
                'numero_apolice': seguro_from_db.get('Numero_Apolice', ''),
                'seguradora': seguro_from_db.get('Seguradora', ''),
                'tipo_seguro': seguro_from_db.get('Tipo_Seguro', ''),
                'valor_segurado': f"{seguro_from_db.get('Valor_Segurado'):.2f}" if seguro_from_db.get('Valor_Segurado') is not None else '0.00', # Formatado como string para o input
                'data_inicio_vigencia': seguro_from_db.get('Data_Inicio_Vigencia').strftime('%Y-%m-%d') if seguro_from_db.get('Data_Inicio_Vigencia') else '',
                'data_fim_vigencia': seguro_from_db.get('Data_Fim_Vigencia').strftime('%Y-%m-%d') if seguro_from_db.get('Data_Fim_Vigencia') else '',
                'status_seguro': seguro_from_db.get('Status_Seguro', ''),
                'observacoes_seguro': seguro_from_db.get('Observacoes_Seguro', '')
            }

            return render_template(
                'obras/seguros/edit_seguro.html',
                user=current_user,
                seguro=seguro_from_db,
                form_data=form_data,
                all_obras=all_obras,
                status_options=status_options,
                tipo_seguro_options=tipo_seguro_options
            )

    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_seguro: {e}")
        return redirect(url_for('obras_bp.seguros_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_seguro: {e}")
        return redirect(url_for('obras_bp.seguros_module'))


@obras_bp.route('/seguros/delete/<int:seguro_id>', methods=['POST'])
@login_required
@module_required('Obras')
def delete_seguro(seguro_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            success = obras_manager.delete_seguro(seguro_id)
            if success:
                flash('Seguro excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir seguro. Verifique se ele existe.', 'danger')
        return redirect(url_for('obras_bp.seguros_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_seguro: {e}")
        return redirect(url_for('obras_bp.seguros_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_seguro: {e}")
        return redirect(url_for('obras_bp.seguros_module'))


@obras_bp.route('/seguros/details/<int:seguro_id>')
@login_required
@module_required('Obras')
def seguro_details(seguro_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            obras_manager = ObrasManager(db_base)
            seguro = obras_manager.get_seguro_by_id(seguro_id)

            if not seguro:
                flash('Seguro não encontrado.', 'danger')
                return redirect(url_for('obras_bp.seguros_module'))

            # --- NOVA SEÇÃO: Formatação de moeda para a página de detalhes ---
            if seguro:
                seguro['Valor_Segurado_Formatado'] = formatar_moeda_brl(seguro.get('Valor_Segurado'))
            # --- FIM DA NOVA SEÇÃO ---

        return render_template(
            'obras/seguros/seguro_details.html',
            user=current_user,
            seguro=seguro
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em seguro_details: {e}")
        return redirect(url_for('obras_bp.seguros_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em seguro_details: {e}")
        return redirect(url_for('obras_bp.seguros_module'))


@obras_bp.route('/seguros/export/excel')
@login_required
@module_required('Obras')
def export_seguros_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('obras_bp.seguros_module'))

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
        return redirect(url_for('obras_bp.seguros_module'))