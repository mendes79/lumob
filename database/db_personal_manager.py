# database/db_personal_manager.py

import mysql.connector

class PersonalManager:
    def __init__(self, db_connection):
        """
        Inicializa o PersonalManager com uma conexão de banco de dados.
        Args:
            db_connection: Uma instância da conexão de banco de dados (mysql.connector.connection).
        """
        self.db = db_connection

    def get_all_employees(self, search_matricula=None, search_name=None, search_cargo_id=None, search_type_contratacao=None):
        """
        Retorna uma lista de todos os funcionários, opcionalmente filtrada.
        Args:
            search_matricula (str, optional): Matrícula para filtrar.
            search_name (str, optional): Nome (ou parte do nome) para filtrar.
            search_cargo_id (int, optional): ID do Cargo para filtrar.
            search_type_contratacao (str, optional): Tipo de Contratação para filtrar.
        Returns:
            list: Uma lista de dicionários, onde cada dicionário representa um funcionário.
        """
        cursor = self.db.cursor(dictionary=True)
        query = """
            SELECT
                f.Matricula,
                f.Nome_Completo,
                f.Data_Admissao,
                f.Status,
                f.Tipo_Contratacao,
                c.Nome_Cargo,
                n.Nome_Nivel
            FROM
                funcionarios f
            LEFT JOIN
                cargos c ON f.ID_Cargos = c.ID_Cargos
            LEFT JOIN
                niveis n ON f.ID_Niveis = n.ID_Niveis
            WHERE 1=1
        """
        params = []

        if search_matricula:
            query += " AND f.Matricula LIKE %s"
            params.append(f"%{search_matricula}%")
        if search_name:
            query += " AND f.Nome_Completo LIKE %s"
            params.append(f"%{search_name}%")
        if search_cargo_id:
            query += " AND f.ID_Cargos = %s"
            params.append(search_cargo_id)
        if search_type_contratacao:
            query += " AND f.Tipo_Contratacao = %s"
            params.append(search_type_contratacao)

        try:
            cursor.execute(query, params)
            employees = cursor.fetchall()
            return employees
        except mysql.connector.Error as err:
            print(f"Erro ao buscar funcionários: {err}")
            return []
        finally:
            cursor.close()

    def get_employee_by_matricula(self, matricula):
        """
        Retorna os dados de um funcionário pela matrícula.
        Args:
            matricula (str): A matrícula do funcionário.
        Returns:
            dict or None: Um dicionário com os dados do funcionário ou None se não encontrado.
        """
        cursor = self.db.cursor(dictionary=True)
        query = """
            SELECT
                f.Matricula,
                f.Nome_Completo,
                f.Data_Admissao,
                f.ID_Cargos,
                f.ID_Niveis,
                f.Status,
                f.Tipo_Contratacao,
                c.Nome_Cargo,
                n.Nome_Nivel
            FROM
                funcionarios f
            LEFT JOIN
                cargos c ON f.ID_Cargos = c.ID_Cargos
            LEFT JOIN
                niveis n ON f.ID_Niveis = n.ID_Niveis
            WHERE f.Matricula = %s
        """
        try:
            cursor.execute(query, (matricula,))
            employee = cursor.fetchone()
            return employee
        except mysql.connector.Error as err:
            print(f"Erro ao buscar funcionário por matrícula: {err}")
            return None
        finally:
            cursor.close()

    def add_employee(self, matricula, nome_completo, data_admissao, id_cargos, id_niveis, status, tipo_contratacao):
        """
        Adiciona um novo funcionário ao banco de dados.
        Args:
            matricula (str): Matrícula do funcionário.
            nome_completo (str): Nome completo do funcionário.
            data_admissao (date): Data de admissão do funcionário.
            id_cargos (int): ID do cargo do funcionário.
            id_niveis (int): ID do nível do funcionário.
            status (str): Status do funcionário.
            tipo_contratacao (str): Tipo de contratação do funcionário.
        Returns:
            bool: True se o funcionário foi adicionado com sucesso, False caso contrário.
        """
        cursor = self.db.cursor()
        query = """
            INSERT INTO funcionarios
            (Matricula, Nome_Completo, Data_Admissao, ID_Cargos, ID_Niveis, Status, Tipo_Contratacao, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        try:
            cursor.execute(query, (matricula, nome_completo, data_admissao, id_cargos, id_niveis, status, tipo_contratacao))
            self.db.commit()
            return True
        except mysql.connector.IntegrityError as err:
            print(f"Erro de integridade ao adicionar funcionário: {err}")
            return False
        except mysql.connector.Error as err:
            print(f"Erro ao adicionar funcionário: {err}")
            return False
        finally:
            cursor.close()

    def update_employee(self, matricula, nome_completo, data_admissao, id_cargos, id_niveis, status, tipo_contratacao):
        """
        Atualiza os dados de um funcionário existente.
        Args:
            matricula (str): Matrícula do funcionário (chave para identificação).
            nome_completo (str): Novo nome completo.
            data_admissao (date): Nova data de admissão.
            id_cargos (int): Novo ID do cargo.
            id_niveis (int): Novo ID do nível.
            status (str): Novo status.
            tipo_contratacao (str): Novo tipo de contratação.
        Returns:
            bool: True se o funcionário foi atualizado com sucesso, False caso contrário.
        """
        cursor = self.db.cursor()
        query = """
            UPDATE funcionarios
            SET
                Nome_Completo = %s,
                Data_Admissao = %s,
                ID_Cargos = %s,
                ID_Niveis = %s,
                Status = %s,
                Tipo_Contratacao = %s,
                Data_Modificacao = NOW()
            WHERE Matricula = %s
        """
        try:
            cursor.execute(query, (nome_completo, data_admissao, id_cargos, id_niveis, status, tipo_contratacao, matricula))
            self.db.commit()
            return cursor.rowcount > 0 # Retorna True se alguma linha foi afetada
        except mysql.connector.Error as err:
            print(f"Erro ao atualizar funcionário: {err}")
            return False
        finally:
            cursor.close()

    def delete_employee(self, matricula):
        """
        Exclui um funcionário do banco de dados.
        Args:
            matricula (str): Matrícula do funcionário a ser excluído.
        Returns:
            bool: True se o funcionário foi excluído com sucesso, False caso contrário.
        """
        cursor = self.db.cursor()
        query = "DELETE FROM funcionarios WHERE Matricula = %s"
        try:
            cursor.execute(query, (matricula,))
            self.db.commit()
            return cursor.rowcount > 0 # Retorna True se alguma linha foi afetada
        except mysql.connector.Error as err:
            print(f"Erro ao excluir funcionário: {err}")
            return False
        finally:
            cursor.close()

    def get_last_matricula(self):
        """
        Retorna a última matrícula numérica usada, para sugestão de nova matrícula.
        Assume que as matrículas podem ser convertidas para números para encontrar o "maior".
        Returns:
            str or None: A última matrícula como string ou None se não houver funcionários.
        """
        cursor = self.db.cursor(dictionary=True)
        # Tenta ordenar numericamente se a matrícula for um número, caso contrário, alfabeticamente.
        # Adapte esta query se sua matrícula tiver um formato mais complexo (ex: prefixo + número)
        query = "SELECT Matricula FROM funcionarios ORDER BY Matricula DESC LIMIT 1"
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            return result['Matricula'] if result else None
        except mysql.connector.Error as err:
            print(f"Erro ao obter a última matrícula: {err}")
            return None
        finally:
            cursor.close()

    def get_all_cargos(self):
        """
        Retorna todos os cargos disponíveis.
        Returns:
            list: Lista de dicionários com ID_Cargos e Nome_Cargo.
        """
        cursor = self.db.cursor(dictionary=True)
        query = "SELECT ID_Cargos, Nome_Cargo FROM cargos ORDER BY Nome_Cargo"
        try:
            cursor.execute(query)
            return cursor.fetchall()
        except mysql.connector.Error as err:
            print(f"Erro ao buscar cargos: {err}")
            return []
        finally:
            cursor.close()

    def get_all_niveis(self):
        """
        Retorna todos os níveis disponíveis.
        Returns:
            list: Lista de dicionários com ID_Niveis e Nome_Nivel.
        """
        cursor = self.db.cursor(dictionary=True)
        query = "SELECT ID_Niveis, Nome_Nivel FROM niveis ORDER BY Nome_Nivel"
        try:
            cursor.execute(query)
            return cursor.fetchall()
        except mysql.connector.Error as err:
            print(f"Erro ao buscar níveis: {err}")
            return []
        finally:
            cursor.close()

    # --- Funções para gerenciar detalhes (contatos, documentos, endereços) ---
    # Serão implementadas na Etapa C
    
    def get_employee_contacts(self, matricula_funcionario):
        """
        Retorna os contatos de um funcionário.
        (A ser implementado em detalhes na Etapa C)
        """
        cursor = self.db.cursor(dictionary=True)
        query = "SELECT * FROM funcionarios_contatos WHERE Matricula_Funcionario = %s"
        try:
            cursor.execute(query, (matricula_funcionario,))
            return cursor.fetchone() # Assumindo um único registro completo
        except mysql.connector.Error as err:
            print(f"Erro ao buscar contatos do funcionário: {err}")
            return None
        finally:
            cursor.close()

    def get_employee_documents(self, matricula_funcionario):
        """
        Retorna os documentos de um funcionário.
        (A ser implementado em detalhes na Etapa C)
        """
        cursor = self.db.cursor(dictionary=True)
        query = "SELECT * FROM funcionarios_documentos WHERE Matricula_Funcionario = %s"
        try:
            cursor.execute(query, (matricula_funcionario,))
            return cursor.fetchall() # Pode ter vários documentos (CPF, RG, CNH, etc.)
        except mysql.connector.Error as err:
            print(f"Erro ao buscar documentos do funcionário: {err}")
            return []
        finally:
            cursor.close()

    def get_employee_address(self, matricula_funcionario):
        """
        Retorna o endereço de um funcionário.
        (A ser implementado em detalhes na Etapa C)
        """
        cursor = self.db.cursor(dictionary=True)
        query = "SELECT * FROM funcionarios_enderecos WHERE Matricula_Funcionario = %s"
        try:
            cursor.execute(query, (matricula_funcionario,))
            return cursor.fetchone() # Assumindo um único registro completo
        except mysql.connector.Error as err:
            print(f"Erro ao buscar endereço do funcionário: {err}")
            return None
        finally:
            cursor.close()

    def check_document_unique(self, numero_documento, tipo_documento, exclude_matricula=None):
        """
        Verifica se um número de documento específico (como CPF) já existe,
        excluindo opcionalmente a matrícula do funcionário que está sendo editado.
        Args:
            numero_documento (str): O número do documento a ser verificado.
            tipo_documento (str): O tipo de documento (ex: 'CPF').
            exclude_matricula (str, optional): Matrícula do funcionário a ser excluído da verificação (para edições).
        Returns:
            bool: True se o documento já existe, False caso contrário.
        """
        cursor = self.db.cursor(dictionary=True)
        query = "SELECT COUNT(*) AS count FROM funcionarios_documentos WHERE Numero_Documento = %s AND Tipo_Documento = %s"
        params = [numero_documento, tipo_documento]

        if exclude_matricula:
            query += " AND Matricula_Funcionario != %s"
            params.append(exclude_matricula)
        
        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result['count'] > 0
        except mysql.connector.Error as err:
            print(f"Erro ao verificar unicidade do documento: {err}")
            return False
        finally:
            cursor.close()