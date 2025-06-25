# LUMOB - modular construction management management program
# 2025-05-28 - VERSION 0.0 (lead-off)
# db_manager.py (Agora um script de teste/exemplo de uso dos managers modulares)

import mysql.connector # Para a classe Error
from database.db_base import DatabaseManager
from database.db_user_manager import UserManager
from database.db_hr_manager import HrManager # Importa o novo manager de RH

# --- Testes de Conexão e CRUDs ---
if __name__ == "__main__":
    db_config = {
        "host": "localhost",
        "database": "lumob",
        "user": "mendes",
        "password": "Galo13BH79&*" # Sua senha real
    }

    try:
        with DatabaseManager(**db_config) as db_base:
            if db_base.connection and db_base.connection.is_connected():
                print("\n--- Testes de CRUDs (Novos e Existentes - via Managers) ---")

                # Inicializa os managers
                user_manager = UserManager(db_base)
                hr_manager = HrManager(db_base)

                # Testando CRUD de Usuários
                print("\n--- Testando CRUD de Usuários (via UserManager) ---")
                
                print("Adicionando usuário 'testeuser_novo'...")
                if user_manager.add_user('testeuser_novo', 'minhasenha123_novo', 'user'):
                    print("Usuário 'testeuser_novo' adicionado com sucesso.")
                else:
                    print("Usuário 'testeuser_novo' já existe ou falha ao adicionar.")

                print("Adicionando usuário 'admin_test_novo'...")
                if user_manager.add_user('admin_test_novo', 'adminpass_novo', 'admin'):
                    print("Usuário 'admin_test_novo' adicionado com sucesso.")
                else:
                    print("Usuário 'admin_test_novo' já existe ou falha ao adicionar.")

                print("\nBuscando usuário 'testeuser_novo' e verificando senha...")
                user_found = user_manager.get_user_by_username('testeuser_novo')
                if user_found:
                    print(f"Usuário encontrado: {user_found['username']} (Role: {user_found['role']})")
                    if user_manager.check_password(user_found['password'], 'minhasenha123_novo'):
                        print("Senha verificada com sucesso!")
                    else:
                        print("Senha incorreta!")
                else:
                    print("Usuário 'testeuser_novo' não encontrado.")

                print("\nListando todos os usuários:")
                all_users = user_manager.get_all_users()
                if all_users:
                    for user in all_users:
                        print(f"ID: {user['id']}, Username: {user['username']}, Role: {user['role']}, Created At: {user['created_at']}")
                else:
                    print("Nenhum usuário cadastrado.")

                print("\nAtualizando role de 'testeuser_novo' para 'moderator' e alterando senha...")
                user_to_update = user_manager.get_user_by_username('testeuser_novo')
                if user_to_update:
                    if user_manager.update_user(user_to_update['id'], role='moderator', password='novasenha789'):
                        print("Usuário 'testeuser_novo' atualizado com sucesso.")
                        updated_user = user_manager.get_user_by_username('testeuser_novo')
                        if user_manager.check_password(updated_user['password'], 'novasenha789'):
                            print("Nova senha de 'testeuser_novo' verificada com sucesso após atualização.")
                        else:
                            print("Falha na verificação da nova senha de 'testeuser_novo'.")
                    else:
                        print("Falha ao atualizar usuário 'testeuser_novo'.")
                else:
                    print("Usuário 'testeuser_novo' não encontrado para atualização.")
                
                # --- Testes de CRUDs Existentes (via HrManager) ---
                print("\n--- Testes de CRUDs Existentes (Cargos, Níveis, Funcionários, Salários, Documentos, Contatos - via HrManager) ---")

                # Teste adicionar Cargo
                print("\n--- Adicionando Cargo ---")
                if hr_manager.adicionar_cargo("Engenheiro Civil", "Profissional de engenharia civil", "2142-05"):
                    print("Cargo 'Engenheiro Civil' adicionado com sucesso.")
                else:
                    print("Falha ao adicionar cargo 'Engenheiro Civil' ou já existe.")

                # Teste buscar Cargos
                print("\n--- Buscando Cargos ---")
                cargos = hr_manager.buscar_cargos(nome_cargo="%engenheiro%")
                if cargos:
                    print("Cargos encontrados:")
                    for cargo in cargos:
                        print(f"ID: {cargo['ID_Cargos']}, Nome: {cargo['Nome_Cargo']}, CBO: {cargo['Cbo']}")
                else:
                    print("Nenhum cargo encontrado com o filtro 'engenheiro'.")

                # Teste atualizar Cargo
                print("\n--- Atualizando Cargo ---")
                cargo_para_atualizar = hr_manager.buscar_cargos(nome_cargo="Engenheiro Civil")
                if cargo_para_atualizar:
                    id_cargo = cargo_para_atualizar[0]['ID_Cargos']
                    if hr_manager.atualizar_cargo(id_cargo, descricao_cargo="Profissional que projeta e gerencia obras civis.", cbo="2142-10"):
                        print(f"Cargo '{cargo_para_atualizar[0]['Nome_Cargo']}' atualizado com sucesso.")
                    else:
                        print(f"Falha ao atualizar cargo '{cargo_para_atualizar[0]['Nome_Cargo']}'.")
                else:
                    print("Cargo 'Engenheiro Civil' não encontrado para atualização.")
                

                # Testes de Níveis
                print("\n--- Testando Níveis ---")
                if hr_manager.adicionar_nivel('Especialista', 'Nível para profissionais altamente qualificados.'):
                    print("Nível 'Especialista' adicionado.")
                else:
                    print("Nível 'Especialista' já existe ou falha.")
                
                niveis = hr_manager.buscar_niveis()
                if niveis:
                    print("Níveis:")
                    for n in niveis:
                        print(n)
                
                # Testes de Funcionários
                print("\n--- Testando Funcionários ---")
                matricula_teste_novo = '002DEF'
                if hr_manager.adicionar_funcionario(matricula_teste_novo, 'Maria Souza', '2024-03-01', 'Engenheiro Civil', 'Junior'):
                    print(f"Funcionário {matricula_teste_novo} adicionado.")
                else:
                    print(f"Funcionário {matricula_teste_novo} já existe ou falha.")
                
                funcs = hr_manager.buscar_funcionarios(matricula=matricula_teste_novo)
                if funcs:
                    print(f"Funcionário {matricula_teste_novo} encontrado: {funcs[0]['Nome_Completo']}")
                    if hr_manager.atualizar_funcionario(matricula_teste_novo, status='Férias'):
                         print(f"Status do funcionário {matricula_teste_novo} atualizado.")
                    else:
                        print(f"Falha ao atualizar status do funcionário {matricula_teste_novo}.")
                
                # Testes de Salários
                print("\n--- Testando Salários ---")
                if hr_manager.adicionar_salario('Engenheiro Civil', 'Junior', 4500.00, '2024-01-01', vale_refeicao=500.00):
                    print("Salário de Engenheiro Civil - Junior adicionado.")
                else:
                    print("Falha ao adicionar salário ou já existe.")
                
                salario_vigente = hr_manager.buscar_salario_vigente('Engenheiro Civil', 'Junior')
                if salario_vigente:
                    print(f"Salário vigente para Engenheiro Civil - Junior: {salario_vigente['Salario_Base']}")
                    
                    if hr_manager.atualizar_salario(salario_vigente['ID_Salarios'], salario_base=5000.00, data_vigencia='2025-01-01'):
                        print(f"Salário ID {salario_vigente['ID_Salarios']} atualizado para 5000.00.")
                    else:
                        print(f"Falha ao atualizar salário ID {salario_vigente['ID_Salarios']}.")
                
                # Testes de Documentos de Funcionários
                print("\n--- Testando Documentos de Funcionários ---")
                if hr_manager.adicionar_documento_funcionario(matricula_teste_novo, 'CPF', '987.654.321-00', '2005-07-20', 'RFB', 'SP'):
                    print(f"Documento CPF para {matricula_teste_novo} adicionado.")
                else:
                    print(f"Falha ao adicionar documento CPF para {matricula_teste_novo}.")

                docs_func = hr_manager.buscar_documentos_funcionario(matricula_funcionario=matricula_teste_novo)
                if docs_func:
                    print(f"Documentos de {matricula_teste_novo}:")
                    for doc in docs_func:
                        print(doc)
                    
                    id_doc_para_atualizar_novo = docs_func[0]['ID_Funcionario_Documento']
                    if hr_manager.atualizar_documento_funcionario(id_doc_para_atualizar_novo, observacoes='Validade até 2030.'):
                        print(f"Documento ID {id_doc_para_atualizar_novo} atualizado com observações.")
                    else:
                        print(f"Falha ao atualizar documento ID {id_doc_para_atualizar_novo}.")
                
                # Testes de Contatos de Funcionários
                print("\n--- Testando Contatos de Funcionários ---")
                if hr_manager.adicionar_contato_funcionario(matricula_teste_novo, 'Email Corporativo', 'maria.souza@company.com'):
                    print(f"Email para {matricula_teste_novo} adicionado.")
                else:
                    print(f"Falha ao adicionar email para {matricula_teste_novo}.")
                
                contatos_func = hr_manager.buscar_contatos_funcionario(matricula_funcionario=matricula_teste_novo)
                if contatos_func:
                    print(f"Contatos de {matricula_teste_novo}:")
                    for contato in contatos_func:
                        print(contato)

                    email_contato_novo = [c for c in contatos_func if c['Tipo_Contato'] == 'Email Corporativo']
                    if email_contato_novo:
                        id_email_para_atualizar_novo = email_contato_novo[0]['ID_Funcionario_Contato']
                        if hr_manager.atualizar_contato_funcionario(id_email_para_atualizar_novo, valor_contato='maria.souza.novo@company.com'):
                            print(f"Email corporativo do funcionário {matricula_teste_novo} atualizado com sucesso!")
                        else:
                            print(f"Falha ao atualizar email corporativo de {matricula_teste_novo}.")
                    else:
                        print(f"Email corporativo de {matricula_teste_novo} não encontrado para atualização.")

            else:
                print("Não foi possível estabelecer a conexão com o banco de dados.")

    except mysql.connector.Error as e:
        print(f"Ocorreu um erro de banco de dados: {e}")
    except Exception as e:
        print(f"Ocorreu um erro geral durante os testes: {e}")