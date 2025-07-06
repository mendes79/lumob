# modulos/users_bp.py

import mysql.connector
import os
from datetime import datetime, date

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user

# Importações dos managers de banco de dados
from database.db_base import DatabaseManager
from database.db_user_manager import UserManager

# Crie a instância do Blueprint para o Módulo Usuários
users_bp = Blueprint('users_bp', __name__, url_prefix='/users')

# 5.1 ROTAS DE USUARIOS
@users_bp.route('/')
@login_required
def users_module():
    """
    Rota principal do módulo Usuários.
    O módulo de usuários (users_module) deve ter acesso restrito apenas a 'admin'.
    """
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar o módulo Usuários.', 'warning')
        return redirect(url_for('welcome')) # Redireciona para uma rota geral no app.py

    try:
        # db_config é acessível porque está no contexto do app principal
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            user_manager = UserManager(db_base)
            users = user_manager.get_all_users()
            return render_template('users/users_module.html', users=users, user=current_user)
    except mysql.connector.Error as e:
        flash(f"Erro de banco de dados ao carregar usuários: {e}", 'danger')
        return redirect(url_for('welcome'))
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        return redirect(url_for('welcome'))

# 5.1.1 ROTAS DO CRUD DE USUARIOS - CRIAR
@users_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem adicionar usuários.', 'warning')
        return redirect(url_for('users_bp.users_module')) # Redireciona dentro do Blueprint

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']

        try:
            with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
                user_manager = UserManager(db_base)

                if user_manager.find_user_by_username(username):
                    flash(f"Usuário '{username}' já existe. Por favor, escolha outro.", 'danger')
                    available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
                    return render_template('users/add_user.html', user=current_user, available_roles=available_roles,
                                           old_username=username, old_email=email, old_role=role)

                if user_manager.find_user_by_email(email):
                    flash(f"Este e-mail '{email}' já está em uso. Por favor, escolha outro.", 'danger')
                    available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
                    return render_template('users/add_user.html', user=current_user, available_roles=available_roles,
                                           old_username=username, old_email=email, old_role=role)

                new_user_id = user_manager.add_user(username, password, role, email)
                if new_user_id:
                    flash(f"Usuário '{username}' adicionado com sucesso!", 'success')
                    return redirect(url_for('users_bp.users_module')) # Redireciona dentro do Blueprint
                else:
                    flash("Erro ao adicionar usuário.", 'danger')
        except mysql.connector.Error as e:
            flash(f"Erro de banco de dados: {e}", 'danger')
            print(f"Erro de banco de dados: {e}")
        except Exception as e:
            flash(f"Ocorreu um erro inesperado: {e}", 'danger')
            print(f"Erro inesperado durante a adição de usuário: {e}")

    # Para a página GET, ou em caso de erro no POST
    available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
    return render_template('users/add_user.html', user=current_user, available_roles=available_roles)

# 5.1.2 ROTAS DO CRUD DE USUARIOS - EDITAR
@users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem editar usuários.', 'warning')
        return redirect(url_for('users_bp.users_module'))

    # Este é o bloco TRY que precisa englobar toda a função
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            user_manager = UserManager(db_base)
            user_to_edit = user_manager.find_user_by_id(user_id)

            if not user_to_edit:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('users_bp.users_module'))

            if request.method == 'POST':
                # Este TRY/EXCEPT aninhado é para a lógica de processamento do POST
                try: 
                    new_username = request.form.get('username')
                    new_email = request.form.get('email')
                    new_password = request.form.get('password')
                    new_role = request.form.get('role')

                    if not new_username or not new_role or not new_email:
                        flash("Nome de usuário, Email e Papel (Role) são obrigatórios.", 'danger')
                        # Este return render_template deve estar ANINHADO ao POST, mas FORA do try/except mais interno
                        # E com a indentação correta para estar na lógica do POST
                        return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])

                    if new_username != user_to_edit['username']:
                        existing_user_with_new_name = user_manager.find_user_by_username(new_username)
                        if existing_user_with_new_name and existing_user_with_new_name['id'] != user_id:
                            flash(f"O nome de usuário '{new_username}' já está em uso por outro usuário.", 'danger')
                            return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])

                    if new_email != user_to_edit['email']:
                        existing_user_with_new_email = user_manager.find_user_by_email(new_email)
                        if existing_user_with_new_email and existing_user_with_new_email['id'] != user_id:
                            flash(f"O e-mail '{new_email}' já está em uso por outro usuário.", 'danger')
                            return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])

                    success = user_manager.update_user(user_id, new_username, new_password if new_password else None, new_role, new_email)
                    if success:
                        flash(f"Usuário '{user_to_edit['username']}' atualizado com sucesso!", 'success')
                        return redirect(url_for('users_bp.users_module'))
                    else:
                        flash("Erro ao atualizar usuário.", 'danger')
                except mysql.connector.Error as e:
                    flash(f"Erro de banco de dados: {e}", 'danger')
                    print(f"Erro de banco de dados no POST de edit_user: {e}")
                except Exception as e:
                    flash(f"Ocorreu um erro inesperado: {e}", 'danger')
                    print(f"Erro inesperado no POST de edit_user: {e}")
                
                # Este return é para quando o POST não foi bem-sucedido mas não deu um erro fatal
                # Deve estar alinhado com o 'if request.method == 'POST':'
                return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=['admin', 'rh', 'engenheiro', 'editor', 'seguranca'])
            
            else: # GET request (alinhado com o if request.method == 'POST':)
                available_roles = ['admin', 'rh', 'engenheiro', 'editor', 'seguranca']
                return render_template('users/edit_user.html', user_to_edit=user_to_edit, user=current_user, available_roles=available_roles)

    except mysql.connector.Error as e: # Estes excepts são para o TRY mais externo (carregamento inicial, erros de DB gerais)
        flash(f"Erro de banco de dados ao carregar usuário para edição: {e}", 'danger')
        print(f"Erro de banco de dados no GET de edit_user: {e}")
        return redirect(url_for('users_bp.users_module'))
    except Exception as e: # Este except é para erros gerais do bloco inicial (GET)
        flash(f"Ocorreu um erro inesperado ao carregar usuário para edição: {e}", 'danger')
        print(f"Erro inesperado no GET de edit_user: {e}")
        return redirect(url_for('users_bp.users_module'))
    
# 5.1.3 ROTAS DO CRUD DE USUARIOS - DELETAR
@users_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem deletar usuários.', 'warning')
        return redirect(url_for('users_bp.users_module'))

    if current_user.id == user_id:
        flash('Você não pode deletar sua própria conta.', 'danger')
        return redirect(url_for('users_bp.users_module'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            user_manager = UserManager(db_base)
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
        print(f"Erro de banco de dados: {e}")
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado: {e}")

    return redirect(url_for('users_bp.users_module'))

# 5.1.4 ROTAS DO CRUD DE USUARIOS - RESETAR SENHA
@users_bp.route('/reset_password/<int:user_id>', methods=['POST'])
@login_required
def reset_password(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem resetar senhas.', 'warning')
        return redirect(url_for('users_bp.users_module'))

    if current_user.id == user_id:
        flash('Você não pode resetar a sua própria senha padrão por aqui. Altere-a pela edição.', 'danger')
        return redirect(url_for('users_bp.users_module'))

    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
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
        print(f"Erro de banco de dados: {e}")
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", 'danger')
        print(f"Erro inesperado: {e}")

    return redirect(url_for('users_bp.users_module'))

# 5.1.5 ROTA PERMISSÕES DE USUARIOS
@users_bp.route('/permissions/<int:user_id>', methods=['GET', 'POST'])
@login_required
def manage_user_permissions(user_id):
    if current_user.role != 'admin':
        flash('Acesso negado. Apenas administradores podem gerenciar permissões.', 'warning')
        return redirect(url_for('users_bp.users_module'))

    # Este é o bloco TRY PRINCIPAL que engloba toda a lógica da função
    try:
        with DatabaseManager(**current_app.config['DB_CONFIG']) as db_base:
            user_manager = UserManager(db_base)
            user_to_manage = user_manager.find_user_by_id(user_id)

            if not user_to_manage:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('users_bp.users_module'))

            if user_to_manage['role'] == 'admin':
                flash('As permissões de um administrador são totais por padrão e não podem ser gerenciadas individualmente.', 'info')
                return render_template('users/manage_permissions.html',
                                       user_to_manage=user_to_manage,
                                       all_modules=[],
                                       current_permissions_ids=[],
                                       user=current_user)

            all_modules = user_manager.get_all_modules()
            current_permissions_ids = user_manager.get_user_module_permissions(user_id)

            if request.method == 'POST':
                # Este TRY/EXCEPT ANINHADO é para a lógica de processamento do POST
                try: 
                    selected_module_ids_str = request.form.getlist('module_ids')
                    selected_module_ids = [int(mod_id) for mod_id in selected_module_ids_str]

                    if user_manager.update_user_module_permissions(user_id, selected_module_ids):
                        flash(f"Permissões do usuário '{user_to_manage['username']}' atualizadas com sucesso!", 'success')
                        if current_user.id == user_id:
                            current_user.permissions = user_manager.get_user_permissions(current_user.id)
                        return redirect(url_for('users_bp.users_module'))
                    else:
                        flash("Erro ao atualizar permissões.", 'danger')
                except mysql.connector.Error as e: # Este except é para erros de DB do POST
                    flash(f"Erro de banco de dados: {e}", 'danger')
                    print(f"Erro de banco de dados no POST de manage_user_permissions: {e}")
                except Exception as e: # Este except é para erros gerais do POST
                    flash(f"Ocorreu um erro inesperado: {e}", 'danger')
                    print(f"Erro inesperado no POST de manage_user_permissions: {e}")
                
                # Este return render_template é para quando o POST não foi bem-sucedido mas não deu um erro fatal.
                # Ele deve estar alinhado com o 'if request.method == 'POST':'
                return render_template('users/manage_permissions.html',
                                       user_to_manage=user_to_manage,
                                       all_modules=all_modules,
                                       current_permissions_ids=current_permissions_ids,
                                       user=current_user)
            
            else: # GET request (alinhado com o 'if request.method == 'POST':')
                # Este return render_template é para o GET inicial da página
                return render_template('users/manage_permissions.html',
                                       user_to_manage=user_to_manage,
                                       all_modules=all_modules,
                                       current_permissions_ids=current_permissions_ids,
                                       user=current_user)

    except mysql.connector.Error as e: # Estes excepts são para o TRY PRINCIPAL (erros gerais, como ao carregar all_modules)
        flash(f"Erro de banco de dados ao carregar dados para gerenciamento de permissões: {e}", 'danger')
        print(f"Erro de banco de dados no GET de manage_user_permissions: {e}")
        return redirect(url_for('users_bp.users_module'))
    except Exception as e: # Este except é para erros gerais do bloco principal
        flash(f"Ocorreu um erro inesperado ao carregar dados para gerenciamento de permissões: {e}", 'danger')
        print(f"Erro inesperado no GET de manage_user_permissions: {e}")
        return redirect(url_for('users_bp.users_module'))