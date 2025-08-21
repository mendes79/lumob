# modulos/seguranca_bp.py

import mysql.connector
import os
from datetime import datetime, date, timedelta
import pandas as pd
from io import BytesIO

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, send_file
from flask_login import login_required, current_user

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_obras_manager import ObrasManager # Para dropdown de obras em Incidentes/Acidentes
from database.db_pessoal_manager import PessoalManager # Para dropdown de funcionários em Incidentes/Acidentes e ASOs
from database.db_seguranca_manager import SegurancaManager

# Importação da função de análise de permissão do usuário aos módulos através do decorator @module_required('Segurança')
from utils import module_required

# Crie a instância do Blueprint para o Módulo Segurança
seguranca_bp = Blueprint('seguranca_bp', __name__, url_prefix='/seguranca')

# ==================================================================================================================================
# === ROTAS PARA O MÓDULO SEGURANCA ================================================================================================
# ==================================================================================================================================

# ROTA HUB PRINCIPAL DO MÓDULO SEGURANÇA
@seguranca_bp.route('/')
@login_required
@module_required('Segurança')
def seguranca_module():
    """
    Rota principal do módulo Segurança.
    Serve como hub de navegação para os submódulos.
    """
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            # Futuramente, você pode buscar dados relacionados à segurança aqui para um dashboard ou overview
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
# 4.4 ROTAS PARA DASHBOARD - SEGURANCA
# ===============================================================
@seguranca_bp.route('/dashboard')
@login_required
@module_required('Segurança')
def seguranca_dashboard():
    """
    Rota para o Dashboard de Segurança, exibindo KPIs e resumos.
    """
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)

            total_incidentes_acidentes = seguranca_manager.get_total_incidentes_acidentes()

            type_counts_list = seguranca_manager.get_incidentes_acidentes_counts_by_type()
            type_counts_dict = {item['Tipo_Registro']: item['Count'] for item in type_counts_list}

            status_counts_list_from_db = seguranca_manager.get_incidentes_acidentes_counts_by_status()
            status_counts_dict = {item['Status_Registro']: item['Count'] for item in status_counts_list_from_db}

            monthly_counts = seguranca_manager.get_incidentes_acidentes_counts_by_month_year()

            return render_template(
                'seguranca/seguranca_dashboard.html',
                user=current_user,
                total_incidentes_acidentes=total_incidentes_acidentes,
                type_counts=type_counts_list,
                status_counts=status_counts_dict,
                status_counts_list=status_counts_list_from_db,
                monthly_counts=monthly_counts
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar dashboard de segurança: {e}", 'danger')
        print(f"Erro de banco de dados em seguranca_dashboard: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar dashboard de segurança: {e}", 'danger')
        print(f"Erro inesperado em seguranca_dashboard: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))

# ===============================================================
# 4.1 ROTAS DE INCIDENTES_ACIDENTES - SEGURANCA
# ===============================================================
@seguranca_bp.route('/incidentes_acidentes')
@login_required
@module_required('Segurança')
def incidentes_acidentes_module():
    
    search_tipo = request.args.get('tipo_registro')
    search_status = request.args.get('status_registro')
    search_obra_id = request.args.get('obra_id')
    search_responsavel_matricula = request.args.get('responsavel_matricula')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            obras_manager = ObrasManager(db_base)
            pessoal_manager = PessoalManager(db_base)

            incidentes = seguranca_manager.get_all_incidentes_acidentes(
                search_tipo=search_tipo,
                search_status=search_status,
                search_obra_id=int(search_obra_id) if search_obra_id else None,
                search_responsavel_matricula=search_responsavel_matricula
            )

            all_obras = obras_manager.get_all_obras_for_dropdown()
            all_funcionarios = pessoal_manager.get_all_funcionarios()

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
        return redirect(url_for('seguranca_bp.seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Incidentes/Acidentes: {e}", 'danger')
        print(f"Erro inesperado em incidentes_acidentes_module: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))

# ---------------------------------------------------------------
# 4.1.1 ROTAS DO CRUD DE INCIDENTES_ACIDENTES - CRIAR - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/incidentes_acidentes/add', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def add_incidente_acidente():
   
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            obras_manager = ObrasManager(db_base)
            pessoal_manager = PessoalManager(db_base)

            all_obras = obras_manager.get_all_obras_for_dropdown()
            all_funcionarios = pessoal_manager.get_all_funcionarios()
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

                form_data_to_template = form_data_received
                form_data_to_template['data_hora_ocorrencia'] = data_hora_ocorrencia_str
                form_data_to_template['data_fechamento'] = data_fechamento_str

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
                        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))
                    else:
                        flash('Erro ao adicionar registro de Incidente/Acidente. Verifique os dados e tente novamente.', 'danger')

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
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_incidente_acidente: {e}")
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))

# ---------------------------------------------------------------
# 4.1.2 ROTAS DO CRUD DE INCIDENTES_ACIDENTES- EDITAR - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/incidentes_acidentes/edit/<int:incidente_id>', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def edit_incidente_acidente(incidente_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            obras_manager = ObrasManager(db_base)
            pessoal_manager = PessoalManager(db_base)

            incidente_from_db = seguranca_manager.get_incidente_acidente_by_id(incidente_id)
            if not incidente_from_db:
                flash('Registro de Incidente/Acidente não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))

            all_obras = obras_manager.get_all_obras_for_dropdown()
            all_funcionarios = pessoal_manager.get_all_funcionarios()
            tipo_registro_options = ['Incidente', 'Acidente']
            status_registro_options = ['Aberto', 'Em Investigação', 'Concluído', 'Fechado']

            form_data_to_template = {}

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                # 1. Captura e Validação/Conversão de Campos do Formulário
                tipo_registro = form_data_received.get('tipo_registro', '').strip()
                data_hora_ocorrencia_str = form_data_received.get('data_hora_ocorrencia', '').strip()
                local_ocorrencia = form_data_received.get('local_ocorrencia', '').strip()
                id_obras_str = form_data_received.get('id_obras')
                descricao_resumida = form_data_received.get('descricao_resumida', '').strip()
                causas_identificadas = form_data_received.get('causas_identificadas', '').strip()
                acoes_corretivas_tomadas = form_data_received.get('acoes_corretivas_tomadas', '').strip()
                acoes_preventivas_recomendadas = form_data_received.get('acoes_preventivas_recomendadas', '').strip()
                status_registro = form_data_received.get('status_registro', '').strip()
                responsavel_matricula = form_data_received.get('responsavel_matricula', '').strip()
                data_fechamento_str = form_data_received.get('data_fechamento', '').strip()
                observacoes = form_data_received.get('observacoes', '').strip()

                # Conversões para objetos Python (datas, ints)
                data_hora_ocorrencia_obj = None
                data_fechamento_obj = None
                id_obras_obj = None # Para o manager
                
                is_valid = True

                # Validação de campos obrigatórios iniciais
                if not all([tipo_registro, data_hora_ocorrencia_str, descricao_resumida, status_registro]):
                    flash('Campos obrigatórios (Tipo, Data/Hora, Descrição, Status) não podem ser vazios.', 'danger')
                    is_valid = False

                # Conversão de datas com tratamento de erro
                try:
                    if data_hora_ocorrencia_str:
                        data_hora_ocorrencia_obj = datetime.strptime(data_hora_ocorrencia_str, '%Y-%m-%dT%H:%M')
                    else: # Data/Hora Ocorrência é obrigatório
                        flash('Data e Hora da Ocorrência é obrigatória.', 'danger')
                        is_valid = False
                except ValueError:
                    flash('Formato de Data/Hora de Ocorrência inválido. Use AAAA-MM-DDTHH:MM.', 'danger')
                    is_valid = False

                if data_fechamento_str:
                    try:
                        data_fechamento_obj = datetime.strptime(data_fechamento_str, '%Y-%m-%d').date()
                    except ValueError:
                        flash('Formato de Data de Fechamento inválido. Use AAAA-MM-DD.', 'danger')
                        is_valid = False
                
                # Conversão de ID da Obra
                if id_obras_str:
                    try:
                        id_obras_obj = int(id_obras_str)
                    except ValueError:
                        flash('ID da Obra inválido.', 'danger')
                        is_valid = False
                # else: # ID da Obra é opcional, não precisa de flash se for vazio

                # --- SE ALGUMA VALIDAÇÃO FALHOU NO POST ---
                if not is_valid:
                    # Repopula form_data_to_template com os dados recebidos do formulário (chaves minúsculas)
                    form_data_to_template = form_data_received.copy()
                    # Garante que datas sejam passadas como string para o input
                    form_data_to_template['data_hora_ocorrencia'] = data_hora_ocorrencia_str
                    form_data_to_template['data_fechamento'] = data_fechamento_str
                    # Garante que ID da Obra seja string
                    form_data_to_template['id_obras'] = id_obras_str if id_obras_str else ''

                    return render_template(
                        'seguranca/incidentes_acidentes/edit_incidente_acidente.html',
                        user=current_user,
                        incidente=form_data_to_template, # Passa form_data_to_template como 'incidente'
                        all_obras=all_obras,
                        all_funcionarios=all_funcionarios,
                        tipo_registro_options=tipo_registro_options,
                        status_registro_options=status_registro_options
                    )

                # --- SE TODAS AS VALIDAÇÕES PASSARAM NO POST, TENTA ATUALIZAR ---
                success = seguranca_manager.update_incidente_acidente(
                    incidente_id, tipo_registro, data_hora_ocorrencia_obj, local_ocorrencia,
                    id_obras_obj, descricao_resumida,
                    causas_identificadas, acoes_corretivas_tomadas,
                    acoes_preventivas_recomendadas,
                    status_registro, responsavel_matricula if responsavel_matricula else None,
                    data_fechamento_obj, observacoes
                )
                if success:
                    flash('Registro de Incidente/Acidente atualizado com sucesso!', 'success')
                    return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))
                else:
                    flash('Erro ao atualizar registro de Incidente/Acidente. Verifique os dados e tente novamente.', 'danger')

            else: # GET request (carregar dados do DB para o formulário)
                # Popula form_data_to_template com os dados do DB, normalizando as chaves para minúsculas
                form_data_to_template['id_incidente_acidente'] = incidente_from_db['ID_Incidente_Acidente']
                form_data_to_template['tipo_registro'] = incidente_from_db['Tipo_Registro']
                form_data_to_template['local_ocorrencia'] = incidente_from_db['Local_Ocorrencia'] if incidente_from_db.get('Local_Ocorrencia') is not None else ''
                form_data_to_template['id_obras'] = str(incidente_from_db['ID_Obras']) if incidente_from_db.get('ID_Obras') is not None else ''
                form_data_to_template['descricao_resumida'] = incidente_from_db['Descricao_Resumida']
                form_data_to_template['causas_identificadas'] = incidente_from_db['Causas_Identificadas'] if incidente_from_db.get('Causas_Identificadas') is not None else ''
                form_data_to_template['acoes_corretivas_tomadas'] = incidente_from_db['Acoes_Corretivas_Tomadas'] if incidente_from_db.get('Acoes_Corretivas_Tomadas') is not None else ''
                form_data_to_template['acoes_preventivas_recomendadas'] = incidente_from_db['Acoes_Preventivas_Recomendadas'] if incidente_from_db.get('Acoes_Preventivas_Recomendadas') is not None else ''
                form_data_to_template['status_registro'] = incidente_from_db['Status_Registro']
                form_data_to_template['responsavel_matricula'] = incidente_from_db['Responsavel_Investigacao_Funcionario_Matricula'] if incidente_from_db.get('Responsavel_Investigacao_Funcionario_Matricula') is not None else ''
                form_data_to_template['observacoes'] = incidente_from_db['Observacoes'] if incidente_from_db.get('Observacoes') is not None else ''

                # Formatar datas/datetimes para o formato esperado pelos inputs HTML
                form_data_to_template['data_hora_ocorrencia'] = incidente_from_db['Data_Hora_Ocorrencia'].strftime('%Y-%m-%dT%H:%M') if isinstance(incidente_from_db.get('Data_Hora_Ocorrencia'), datetime) else ''
                form_data_to_template['data_fechamento'] = incidente_from_db['Data_Fechamento'].strftime('%Y-%m-%d') if isinstance(incidente_from_db.get('Data_Fechamento'), date) else ''
                
            return render_template(
                'seguranca/incidentes_acidentes/edit_incidente_acidente.html',
                user=current_user,
                incidente=form_data_to_template, # Passa o dicionário com chaves minúsculas
                all_obras=all_obras,
                all_funcionarios=all_funcionarios,
                tipo_registro_options=tipo_registro_options,
                status_registro_options=status_registro_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_incidente_acidente: {e}")
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_incidente_acidente: {e}")
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))
        
# ---------------------------------------------------------------
# 4.1.3 ROTAS DO CRUD DE INCIDENTES_ACIDENTES- DELETAR- SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/incidentes_acidentes/delete/<int:incidente_id>', methods=['POST'])
@login_required
@module_required('Segurança')
def delete_incidente_acidente(incidente_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_incidente_acidente(incidente_id)
            if success:
                flash('Registro de Incidente/Acidente excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir registro de Incidente/Acidente. Verifique se ele existe.', 'danger')
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_incidente_acidente: {e}")
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_incidente_acidente: {e}")
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))

# ---------------------------------------------------------------
# 4.1.4 ROTAS DO CRUD DE INCIDENTES_ACIDENTES -DETALHES SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/incidentes_acidentes/details/<int:incidente_id>')
@login_required
@module_required('Segurança')
def incidente_acidente_details(incidente_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            incidente = seguranca_manager.get_incidente_acidente_by_id(incidente_id)

            if not incidente:
                flash('Registro de Incidente/Acidente não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))

        return render_template(
            'seguranca/incidentes_acidentes/incidente_acidente_details.html',
            user=current_user,
            incidente=incidente
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em incidente_acidente_details: {e}")
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em incidente_acidente_details: {e}")
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))

# ---------------------------------------------------------------
# 4.1.5 ROTA INCIDENTES_ACIDENTES - EXPORTAR P/ EXCEL - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/incidentes_acidentes/export/excel')
@login_required
@module_required('Segurança')
def export_incidentes_acidentes_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))

            df = pd.DataFrame(incidentes_data)

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
        return redirect(url_for('seguranca_bp.incidentes_acidentes_module'))

# ===============================================================
# 4.2 ROTAS DE ASOS - SEGURANCA
# ===============================================================
@seguranca_bp.route('/asos')
@login_required
@module_required('Segurança')
def asos_module():
    
    search_matricula = request.args.get('matricula')
    search_tipo = request.args.get('tipo_aso')
    search_resultado = request.args.get('resultado')
    search_data_emissao_inicio = request.args.get('data_emissao_inicio')
    search_data_emissao_fim = request.args.get('data_emissao_fim')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            pessoal_manager = PessoalManager(db_base)

            asos = seguranca_manager.get_all_asos(
                search_matricula=search_matricula,
                search_tipo=search_tipo,
                search_resultado=search_resultado,
                search_data_emissao_inicio=datetime.strptime(search_data_emissao_inicio, '%Y-%m-%d').date() if search_data_emissao_inicio else None,
                search_data_emissao_fim=datetime.strptime(search_data_emissao_fim, '%Y-%m-%d').date() if search_data_emissao_fim else None
            )

            all_funcionarios = pessoal_manager.get_all_funcionarios()
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
        return redirect(url_for('seguranca_bp.seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar ASOs: {e}", 'danger')
        print(f"Erro inesperado em asos_module: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))

# ---------------------------------------------------------------
# 4.2.1 ROTAS DO CRUD DE ASOS - CRIAR - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/asos/add', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def add_aso():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                        return redirect(url_for('seguranca_bp.asos_module'))
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
        return redirect(url_for('seguranca_bp.asos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_aso: {e}")
        return redirect(url_for('seguranca_bp.asos_module'))

# ---------------------------------------------------------------
# 4.2.2 ROTAS DO CRUD DE ASOS - EDITAR - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/asos/edit/<int:aso_id>', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def edit_aso(aso_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            pessoal_manager = PessoalManager(db_base)

            aso_from_db = seguranca_manager.get_aso_by_id(aso_id)
            if not aso_from_db:
                flash('ASO não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.asos_module'))

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
                        return redirect(url_for('seguranca_bp.asos_module'))
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
        return redirect(url_for('seguranca_bp.asos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_aso: {e}")
        return redirect(url_for('seguranca_bp.asos_module'))

# ---------------------------------------------------------------
# 4.2.3 ROTAS DO CRUD DE ASOS - DELETAR - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/asos/delete/<int:aso_id>', methods=['POST'])
@login_required
@module_required('Segurança')
def delete_aso(aso_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_aso(aso_id)
            if success:
                flash('ASO excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir ASO. Verifique se ele existe.', 'danger')
        return redirect(url_for('seguranca_bp.asos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_aso: {e}")
        return redirect(url_for('seguranca_bp.asos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_aso: {e}")
        return redirect(url_for('seguranca_bp.asos_module'))

# ---------------------------------------------------------------
# 4.2.4 ROTAS DO CRUD DE ASOS - DETALHES SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/asos/details/<int:aso_id>')
@login_required
@module_required('Segurança')
def aso_details(aso_id):
   
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            aso = seguranca_manager.get_aso_by_id(aso_id)

            if not aso:
                flash('ASO não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.asos_module'))

        return render_template(
            'seguranca/asos/aso_details.html',
            user=current_user,
            aso=aso
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em aso_details: {e}")
        return redirect(url_for('seguranca_bp.asos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em aso_details: {e}")
        return redirect(url_for('seguranca_bp.asos_module'))

# ---------------------------------------------------------------
# 4.2.5 ROTA ASOS - EXPORTAR P/ EXCEL - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/asos/export/excel')
@login_required
@module_required('Segurança')
def export_asos_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('seguranca_bp.asos_module'))

            df = pd.DataFrame(asos_data)

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
        return redirect(url_for('seguranca_bp.asos_module'))

# ===============================================================
# 4.3 ROTAS DE TREINAMENTOS - SEGURANCA
# ===============================================================
@seguranca_bp.route('/treinamentos')
@login_required
@module_required('Segurança')
def treinamentos_module():
    
    search_nome = request.args.get('nome_treinamento')
    search_tipo = request.args.get('tipo_treinamento')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        return redirect(url_for('seguranca_bp.seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Treinamentos: {e}", 'danger')
        print(f"Erro inesperado em treinamentos_module: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))

# ---------------------------------------------------------------
# 4.3.1 ROTAS DO CRUD DE TREINAMENTOS - CRIAR - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/treinamentos/add', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def add_treinamento():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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

                if not is_valid:
                    form_data_to_template = form_data_received # Para preencher o formulário em caso de erro
                    return render_template(
                        'seguranca/treinamentos/add_treinamento.html',
                        user=current_user,
                        tipo_treinamento_options=tipo_treinamento_options,
                        form_data=form_data_to_template
                    )

                success = seguranca_manager.add_treinamento(
                    nome_treinamento, descricao, carga_horaria_horas, tipo_treinamento,
                    validade_dias, instrutor_responsavel
                )
                if success:
                    flash('Treinamento adicionado com sucesso!', 'success')
                    return redirect(url_for('seguranca_bp.treinamentos_module'))
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
        return redirect(url_for('seguranca_bp.treinamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_treinamento: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_module'))

# ---------------------------------------------------------------
# 4.3.2 ROTAS DO CRUD DE TREINAMENTOS - EDITAR - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/treinamentos/edit/<int:treinamento_id>', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def edit_treinamento(treinamento_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)

            treinamento_from_db = seguranca_manager.get_treinamento_by_id(treinamento_id)
            if not treinamento_from_db:
                flash('Treinamento não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.treinamentos_module'))

            tipo_treinamento_options = ['Obrigatório', 'Reciclagem', 'Voluntário', 'Outro']
            form_data_to_template = {} # Inicializa para passar ao template

            if request.method == 'POST':
                form_data_received = request.form.to_dict()

                nome_treinamento = form_data_received.get('nome_treinamento', '').strip()
                descricao = form_data_received.get('descricao', '').strip()
                instrutor_responsavel = form_data_received.get('instrutor_responsavel', '').strip()
                tipo_treinamento = form_data_received.get('tipo_treinamento', '').strip()

                # Conversões de valores numéricos
                carga_horaria_horas = None
                carga_horaria_horas_str = form_data_received.get('carga_horaria_horas', '').strip()
                try:
                    if carga_horaria_horas_str:
                        carga_horaria_horas = float(carga_horaria_horas_str.replace(',', '.'))
                    else: # Campo obrigatório
                        flash('Carga Horária é obrigatória.', 'danger')
                        is_valid = False
                except ValueError:
                    flash('Carga Horária inválida. Use números.', 'danger')
                    is_valid = False

                validade_dias = None
                validade_dias_str = form_data_received.get('validade_dias', '').strip()
                try:
                    if validade_dias_str: # Campo opcional, só converte se preenchido
                        validade_dias = int(validade_dias_str)
                except ValueError:
                    flash('Validade (dias) inválida. Use números inteiros.', 'danger')
                    is_valid = False
                
                is_valid = True # Reset da flag, caso algo acima a tenha definido

                # Validações de campos obrigatórios
                if not all([nome_treinamento, carga_horaria_horas_str, tipo_treinamento]): # Use strings aqui
                    flash('Campos obrigatórios (Nome, Carga Horária, Tipo) não podem ser vazios.', 'danger')
                    is_valid = False

                # Validação de unicidade
                if is_valid:
                    existing_treinamento = seguranca_manager.get_treinamento_by_nome(nome_treinamento)
                    if existing_treinamento and existing_treinamento['ID_Treinamento'] != treinamento_id:
                        flash('Já existe um treinamento com este nome.', 'danger')
                        is_valid = False

                # --- SE HOUVER ERROS DE VALIDAÇÃO NO POST ---
                if not is_valid:
                    # Repopula form_data_to_template com os dados recebidos do formulário
                    form_data_to_template = form_data_received.copy()
                    # Garante que números sejam strings formatadas (ou vazias)
                    form_data_to_template['carga_horaria_horas'] = carga_horaria_horas_str
                    form_data_to_template['validade_dias'] = validade_dias_str
                    
                    return render_template(
                        'seguranca/treinamentos/edit_treinamento.html',
                        user=current_user,
                        treinamento=form_data_to_template,
                        tipo_treinamento_options=tipo_treinamento_options
                    )

                # --- SE TODAS AS VALIDAÇÕES PASSARAM NO POST, TENTA ATUALIZAR ---
                success = seguranca_manager.update_treinamento(
                    treinamento_id, nome_treinamento, descricao, carga_horaria_horas, tipo_treinamento,
                    validade_dias, instrutor_responsavel
                )
                if success:
                    flash('Treinamento atualizado com sucesso!', 'success')
                    return redirect(url_for('seguranca_bp.treinamentos_module'))
                else:
                    flash('Erro ao atualizar treinamento.', 'danger')

            else: # GET request (carregar dados do DB para o formulário)
                # Popula form_data_to_template com os dados do DB, normalizando chaves e formatos
                form_data_to_template['ID_Treinamento'] = treinamento_from_db['ID_Treinamento'] # ID para URL
                form_data_to_template['Nome_Treinamento'] = treinamento_from_db['Nome_Treinamento']
                form_data_to_template['Descricao'] = treinamento_from_db['Descricao'] if treinamento_from_db.get('Descricao') is not None else ''
                form_data_to_template['Tipo_Treinamento'] = treinamento_from_db['Tipo_Treinamento']
                form_data_to_template['Instrutor_Responsavel'] = treinamento_from_db['Instrutor_Responsavel'] if treinamento_from_db.get('Instrutor_Responsavel') is not None else ''

                # Tratamento robusto para números (Carga_Horaria_Horas, Validade_Dias)
                carga_horaria_raw = treinamento_from_db.get('Carga_Horaria_Horas')
                if carga_horaria_raw is None:
                    form_data_to_template['Carga_Horaria_Horas'] = ''
                else:
                    try:
                        form_data_to_template['Carga_Horaria_Horas'] = f"{float(carga_horaria_raw):.2f}"
                    except (ValueError, TypeError):
                        form_data_to_template['Carga_Horaria_Horas'] = ''

                validade_raw = treinamento_from_db.get('Validade_Dias')
                if validade_raw is None:
                    form_data_to_template['Validade_Dias'] = ''
                else:
                    try:
                        form_data_to_template['Validade_Dias'] = str(int(validade_raw)) # Garante int e depois string
                    except (ValueError, TypeError):
                        form_data_to_template['Validade_Dias'] = ''

            return render_template(
                'seguranca/treinamentos/edit_treinamento.html',
                user=current_user,
                treinamento=form_data_to_template, # Passa o dicionário com chaves normalizadas
                tipo_treinamento_options=tipo_treinamento_options
            )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em edit_treinamento: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_treinamento: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_module'))

# ---------------------------------------------------------------
# 4.3.3 ROTAS DO CRUD DE TREINAMENTOS - DELETAR - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/treinamentos/delete/<int:treinamento_id>', methods=['POST'])
@login_required
@module_required('Segurança')
def delete_treinamento(treinamento_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_treinamento(treinamento_id)
            if success:
                flash('Treinamento excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir treinamento. Verifique se não há agendamentos associados.', 'danger')
        return redirect(url_for('seguranca_bp.treinamentos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_treinamento: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir o treinamento pois existem agendamentos associados a ele. Remova-os primeiro.", 'danger')
        return redirect(url_for('seguranca_bp.treinamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_treinamento: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_module'))

# ---------------------------------------------------------------
# 4.3.4 ROTAS DO CRUD DE TREINAMENTOS - DETALHES SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/treinamentos/details/<int:treinamento_id>')
@login_required
@module_required('Segurança')
def treinamento_details(treinamento_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            treinamento = seguranca_manager.get_treinamento_by_id(treinamento_id)

            if not treinamento:
                flash('Treinamento não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.treinamentos_module'))

        return render_template(
            'seguranca/treinamentos/treinamento_details.html',
            user=current_user,
            treinamento=treinamento
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em treinamento_details: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em treinamento_details: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_module'))

# ---------------------------------------------------------------
# 4.3.5 ROTA TREINAMENTOS - EXPORTAR P/ EXCEL - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/treinamentos/export/excel')
@login_required
@module_required('Segurança')
def export_treinamentos_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)

            search_nome = request.args.get('nome_treinamento')
            search_tipo = request.args.get('tipo_treinamento')

            treinamentos_data = seguranca_manager.get_all_treinamentos(
                search_nome=search_nome,
                search_tipo=search_tipo
            )

            if not treinamentos_data:
                flash('Nenhum treinamento encontrado para exportar.', 'info')
                return redirect(url_for('seguranca_bp.treinamentos_module'))

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
        return redirect(url_for('seguranca_bp.treinamentos_module'))


# ---------------------------------------------------------------
# 4.3.6 ROTAS RELATORIO DE TREINAMENTOS - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/relatorio_treinamentos')
@login_required
@module_required('Segurança')
def seguranca_relatorio_treinamentos():
    """
    Rota para o relatório de treinamentos de segurança, com filtros.
    """
  
    search_nome_treinamento = request.args.get('nome_treinamento')
    search_tipo_treinamento = request.args.get('tipo_treinamento')
    search_status_agendamento = request.args.get('status_agendamento')
    search_matricula_participante = request.args.get('matricula_participante')

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            pessoal_manager = PessoalManager(db_base)

            treinamentos_relatorio_data = seguranca_manager.get_treinamentos_para_relatorio(
                search_nome_treinamento=search_nome_treinamento,
                search_tipo_treinamento=search_tipo_treinamento,
                search_status_agendamento=search_status_agendamento,
                search_matricula_participante=search_matricula_participante
            )

            all_treinamentos_for_filter = seguranca_manager.get_all_treinamentos_for_dropdown()
            all_funcionarios_for_filter = pessoal_manager.get_all_funcionarios()

            tipo_treinamento_options = ['Obrigatório', 'Reciclagem', 'Voluntário', 'Outro']
            status_agendamento_options = ['Programado', 'Realizado', 'Cancelado', 'Adiado']

        return render_template(
            'seguranca/treinamentos/treinamentos_relatorio.html',
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
        return redirect(url_for('seguranca_bp.seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar relatório de treinamentos de segurança: {e}", 'danger')
        print(f"Erro inesperado em seguranca_relatorio_treinamentos: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))

# ---------------------------------------------------------------
# 4.3.7 ROTAS TREINAMENTOS AGENDAMENTOS - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/treinamentos/agendamentos')
@login_required
@module_required('Segurança')
def treinamentos_agendamentos_module():
    
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

        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            # --- CORREÇÃO AQUI: INSTANCIAR PessoalManager ---
            pessoal_manager = PessoalManager(db_base)
            # --- FIM DA CORREÇÃO ---

            agendamentos = seguranca_manager.get_all_treinamentos_agendamentos(
                search_treinamento_id=int(search_treinamento_id) if search_treinamento_id else None,
                search_status=search_status,
                search_data_inicio=data_inicio,
                search_data_fim=data_fim
            )

            all_treinamentos = seguranca_manager.get_all_treinamentos_for_dropdown()
            # all_funcionarios = seguranca_manager.get_all_funcionarios_for_dropdown() # Removido, agora vem de pessoal_manager
            all_funcionarios = pessoal_manager.get_all_funcionarios() # <-- USA O pessoal_manager INSTANCIADO ACIMA

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
        return redirect(url_for('seguranca_bp.seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado ao carregar Agendamentos: {e}", 'danger')
        print(f"Erro inesperado em treinamentos_agendamentos_module: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))

# ·······························································
# 4.3.7.1 TREINAMENTOS AGENDAMENTOS CRUD CRIAR - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/agendamentos/add', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def add_treinamento_agendamento():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            # FIX: all_funcionarios estava sendo pego de seguranca_manager.get_all_funcionarios_for_dropdown()
            # que não existe. Deve ser de pessoal_manager.get_all_funcionarios().
            pessoal_manager = PessoalManager(db_base) # Precisa instanciar aqui

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

                if not is_valid:
                    return render_template(
                        'seguranca/treinamentos/agendamentos/add_agendamento.html',
                        user=current_user,
                        all_treinamentos=all_treinamentos,
                        status_agendamento_options=status_agendamento_options,
                        form_data=form_data_to_template
                    )

                success = seguranca_manager.add_treinamento_agendamento(
                    id_treinamento, data_hora_inicio, data_hora_fim, local_treinamento,
                    status_agendamento, observacoes
                )
                if success:
                    flash('Agendamento de Treinamento adicionado com sucesso!', 'success')
                    return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))
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
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_treinamento_agendamento: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

# ·······························································
# 4.3.7.2 TREINAMENTOS AGENDAMENTOS CRUD EDITAR - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/agendamentos/edit/<int:agendamento_id>', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def edit_treinamento_agendamento(agendamento_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            # FIX: all_funcionarios estava sendo pego de seguranca_manager.get_all_funcionarios_for_dropdown()
            # que não existe. Deve ser de pessoal_manager.get_all_funcionarios().
            pessoal_manager = PessoalManager(db_base) # Precisa instanciar aqui

            agendamento_from_db = seguranca_manager.get_treinamento_agendamento_by_id(agendamento_id)
            if not agendamento_from_db:
                flash('Agendamento não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

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

                if not is_valid:
                    return render_template(
                        'seguranca/treinamentos/agendamentos/edit_agendamento.html',
                        user=current_user,
                        agendamento=form_data_to_template,
                        all_treinamentos=all_treinamentos,
                        status_agendamento_options=status_agendamento_options
                    )

                success = seguranca_manager.update_treinamento_agendamento(
                    agendamento_id, id_treinamento, data_hora_inicio, data_hora_fim, local_treinamento,
                    status_agendamento, observacoes
                )
                if success:
                    flash('Agendamento atualizado com sucesso!', 'success')
                    return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))
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
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_treinamento_agendamento: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

# ·······························································
# 4.3.7.3 TREINAMENTOS AGENDAMENTOS CRUD DELETAR - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/agendamentos/delete/<int:agendamento_id>', methods=['POST'])
@login_required
@module_required('Segurança')
def delete_treinamento_agendamento(agendamento_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_treinamento_agendamento(agendamento_id)
            if success:
                flash('Agendamento de Treinamento excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir agendamento. Verifique se não há participantes associados.', 'danger')
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_treinamento_agendamento: {e}")
        if "foreign key constraint fails" in str(e).lower():
            flash("Não foi possível excluir o agendamento pois existem participantes associados a ele. Remova-os primeiro.", 'danger')
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_treinamento_agendamento: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

# ·······························································
# 4.3.7.4 TREINAMENTOS AGENDAMENTOS CRUD DETALHES - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/agendamentos/details/<int:agendamento_id>')
@login_required
@module_required('Segurança')
def treinamento_agendamento_details(agendamento_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            agendamento = seguranca_manager.get_treinamento_agendamento_by_id(agendamento_id)
            participantes = seguranca_manager.get_all_treinamentos_participantes(search_agendamento_id=agendamento_id)

            if not agendamento:
                flash('Agendamento não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

        return render_template(
            'seguranca/treinamentos/agendamentos/agendamento_details.html',
            user=current_user,
            agendamento=agendamento,
            participantes=participantes
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em treinamento_agendamento_details: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em treinamento_agendamento_details: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

# ·······························································
# 4.3.7.5 TREINAMENTOS AGENDAMENTOS EXPORTAR P/ EXCEL - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/agendamentos/export/excel')
@login_required
@module_required('Segurança')
def export_treinamentos_agendamentos_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
                return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

            agendamentos_data = seguranca_manager.get_all_treinamentos_agendamentos(
                search_treinamento_id=int(search_treinamento_id) if search_treinamento_id else None,
                search_status=search_status,
                search_data_inicio=data_inicio,
                search_data_fim=data_fim
            )

            if not agendamentos_data:
                flash('Nenhum agendamento de treinamento encontrado para exportar.', 'info')
                return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

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
        return redirect(url_for('seguranca_bp.treinamentos_agendamentos_module'))

# ---------------------------------------------------------------
# 4.3.8 ROTAS TREINAMENTOS PARTICIPANTES - SEGURANCA
# ---------------------------------------------------------------
@seguranca_bp.route('/treinamentos/participantes')
@login_required
@module_required('Segurança')
def treinamentos_participantes_module():
    
    search_agendamento_id = request.args.get('agendamento_id')
    search_matricula = request.args.get('matricula')
    search_presenca = request.args.get('presenca') # String 'True', 'False' ou None

    presenca_filter = None
    if search_presenca == 'True':
        presenca_filter = True
    elif search_presenca == 'False':
        presenca_filter = False

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            # FIX: all_funcionarios estava sendo pego de seguranca_manager.get_all_funcionarios_for_dropdown()
            # que não existe. Deve ser de pessoal_manager.get_all_funcionarios().
            pessoal_manager = PessoalManager(db_base) # Precisa instanciar aqui
            all_funcionarios = pessoal_manager.get_all_funcionarios()

            participantes = seguranca_manager.get_all_treinamentos_participantes(
                search_agendamento_id=int(search_agendamento_id) if search_agendamento_id else None,
                search_matricula=search_matricula,
                search_presenca=presenca_filter
            )

            all_agendamentos = seguranca_manager.get_all_agendamentos_for_dropdown()
            # all_funcionarios = seguranca_manager.get_all_funcionarios_for_dropdown() # Removido, agora vem de pessoal_manager.get_all_funcionarios()

            presenca_options = [('True', 'Presente'), ('False', 'Ausente')]

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
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em treinamentos_participantes_module: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em treinamentos_participantes_module: {e}")
        return redirect(url_for('seguranca_bp.seguranca_module'))

# ·······························································
# 4.3.8.1 TREINAMENTOS AGENDAMENTOS CRUD CRIAR - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/participantes/add', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def add_treinamento_participante():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            # FIX: all_funcionarios estava sendo pego de seguranca_manager.get_all_funcionarios_for_dropdown()
            # que não existe. Deve ser de pessoal_manager.get_all_funcionarios().
            pessoal_manager = PessoalManager(db_base) # Precisa instanciar aqui

            all_agendamentos = seguranca_manager.get_all_agendamentos_for_dropdown()
            all_funcionarios = pessoal_manager.get_all_funcionarios() # Pegar de pessoal_manager

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

                if seguranca_manager.get_participante_by_agendamento_funcionario(id_agendamento, matricula_funcionario):
                    flash('Este funcionário já está registrado para este agendamento.', 'danger')
                    is_valid = False

                form_data_to_template = form_data_received
                form_data_to_template['data_conclusao'] = data_conclusao_str
                form_data_to_template['presenca'] = presenca
                form_data_to_template['certificado_emitido'] = certificado_emitido

                if not is_valid:
                    return render_template(
                        'seguranca/treinamentos/participantes/add_participante.html',
                        user=current_user,
                        all_agendamentos=all_agendamentos,
                        all_funcionarios=all_funcionarios,
                        form_data=form_data_to_template
                    )

                success = seguranca_manager.add_treinamento_participante(
                    id_agendamento, matricula_funcionario, presenca, nota_avaliacao,
                    data_conclusao, certificado_emitido
                )
                if success:
                    flash('Participante adicionado com sucesso!', 'success')
                    return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))
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
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em add_treinamento_participante: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))

# ·······························································
# 4.3.8.2 TREINAMENTOS AGENDAMENTOS CRUD EDITAR - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/participantes/edit/<int:participante_id>', methods=['GET', 'POST'])
@login_required
@module_required('Segurança')
def edit_treinamento_participante(participante_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            # FIX: all_funcionarios estava sendo pego de seguranca_manager.get_all_funcionarios_for_dropdown()
            # que não existe. Deve ser de pessoal_manager.get_all_funcionarios().
            pessoal_manager = PessoalManager(db_base) # Precisa instanciar aqui

            participante_from_db = seguranca_manager.get_treinamento_participante_by_id(participante_id)
            if not participante_from_db:
                flash('Participante não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))

            all_agendamentos = seguranca_manager.get_all_agendamentos_for_dropdown()
            all_funcionarios = pessoal_manager.get_all_funcionarios() # Pegar de pessoal_manager
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

                if seguranca_manager.get_participante_by_agendamento_funcionario(id_agendamento, matricula_funcionario, exclude_id=participante_id):
                    flash('Este funcionário já está registrado para este agendamento.', 'danger')
                    is_valid = False

                form_data_to_template = form_data_received
                form_data_to_template['data_conclusao'] = data_conclusao_str
                form_data_to_template['presenca'] = presenca
                form_data_to_template['certificado_emitido'] = certificado_emitido

                if not is_valid:
                    return render_template(
                        'seguranca/treinamentos/participantes/edit_participante.html',
                        user=current_user,
                        participante=form_data_to_template,
                        all_agendamentos=all_agendamentos,
                        all_funcionarios=all_funcionarios
                    )

                success = seguranca_manager.update_treinamento_participante(
                    participante_id, id_agendamento, matricula_funcionario, presenca, nota_avaliacao,
                    data_conclusao, certificado_emitido
                )
                if success:
                    flash('Participante atualizado com sucesso!', 'success')
                    return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))
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
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em edit_treinamento_participante: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))

# ·······························································
# 4.3.8.3 TREINAMENTOS AGENDAMENTOS CRUD DELETAR - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/participantes/delete/<int:participante_id>', methods=['POST'])
@login_required
@module_required('Segurança')
def delete_treinamento_participante(participante_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            success = seguranca_manager.delete_treinamento_participante(participante_id)
            if success:
                flash('Participante excluído com sucesso!', 'success')
            else:
                flash('Erro ao excluir participante. Verifique se ele existe.', 'danger')
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em delete_treinamento_participante: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em delete_treinamento_participante: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))

# ·······························································
# 4.3.8.4 TREINAMENTOS AGENDAMENTOS CRUD DETALHES - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/participantes/details/<int:participante_id>')
@login_required
@module_required('Segurança')
def treinamento_participante_details(participante_id):
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)
            participante = seguranca_manager.get_treinamento_participante_by_id(participante_id)

            if not participante:
                flash('Participante não encontrado.', 'danger')
                return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))

        return render_template(
            'seguranca/treinamentos/participantes/participante_details.html',
            user=current_user,
            participante=participante
        )
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados: {e}", 'danger')
        print(f"Erro de banco de dados em treinamento_participante_details: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado em treinamento_participante_details: {e}")
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))

# ·······························································
# 4.3.8.5 TREINAMENTOS AGENDAMENTOS EXPORTAR P/ EXCEL - SEGURANCA
# ·······························································
@seguranca_bp.route('/treinamentos/participantes/export/excel')
@login_required
@module_required('Segurança')
def export_treinamentos_participantes_excel():
    
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            seguranca_manager = SegurancaManager(db_base)

            search_agendamento_id = request.args.get('agendamento_id')
            search_matricula = request.args.get('matricula')
            search_presenca = request.args.get('presenca') # String 'True', 'False' ou None

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
                return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))

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

            # --- CORREÇÃO APLICADA AQUI ---
            # O nome da coluna agora é 'Presença' (com acento), e não mais 'Presenca'.
            df['Presença'] = df['Presença'].apply(lambda x: 'Sim' if x else 'Não')
            
            # Esta linha já estava correta, pois usa o nome novo 'Certificado Emitido'.
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
        return redirect(url_for('seguranca_bp.treinamentos_participantes_module'))