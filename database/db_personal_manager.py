# database/db_personal_manager.py

import mysql.connector # Ainda útil para o tratamento de erros como IntegrityError

class PersonalManager:
    def __init__(self, db_manager_instance):
        """
        Inicializa o PersonalManager com uma instância do seu DatabaseManager.
        Args:
            db_manager_instance: Uma instância da sua classe DatabaseManager (do db_base.py).
        """
        self.db = db_manager_instance # 'self.db' agora é a instância do DatabaseManager

    def get_all_employees(self, search_matricula=None, search_name=None, search_cargo_id=None, search_type_contratacao=None):
        """
        Retorna uma lista de todos os funcionários, opcionalmente filtrada,
        utilizando o método execute_query do DatabaseManager.
        """
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
        
        query += " ORDER BY f.Nome_Completo" # Adiciona ordenação

        # Usa self.db.execute_query() para buscar os resultados
        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def get_employee_by_matricula(self, matricula):
        """
        Retorna os dados de um funcionário pela matrícula, usando execute_query.
        Inclui Nome_Cargo e Nome_Nivel.
        """
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
        # Usa self.db.execute_query()
        result = self.db.execute_query(query, (matricula,), fetch_results=True)
        return result[0] if result else None # Retorna o primeiro item da lista ou None

    def add_employee(self, matricula, nome_completo, data_admissao, id_cargos, id_niveis, status, tipo_contratacao):
        """
        Adiciona um novo funcionário ao banco de dados, usando execute_query.
        """
        query = """
            INSERT INTO funcionarios
            (Matricula, Nome_Completo, Data_Admissao, ID_Cargos, ID_Niveis, Status, Tipo_Contratacao, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (matricula, nome_completo, data_admissao, id_cargos, id_niveis, status, tipo_contratacao)
        # Usa self.db.execute_query()
        # Para INSERT/UPDATE/DELETE, fetch_results deve ser False
        return self.db.execute_query(query, params, fetch_results=False)

    def update_employee(self, matricula, nome_completo, data_admissao, id_cargos, id_niveis, status, tipo_contratacao):
        """
        Atualiza os dados de um funcionário existente, usando execute_query.
        """
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
        params = (nome_completo, data_admissao, id_cargos, id_niveis, status, tipo_contratacao, matricula)
        # Usa self.db.execute_query()
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_employee(self, matricula):
        """
        Exclui um funcionário do banco de dados, usando execute_query.
        """
        query = "DELETE FROM funcionarios WHERE Matricula = %s"
        # Usa self.db.execute_query()
        return self.db.execute_query(query, (matricula,), fetch_results=False)

    def get_last_matricula(self):
        """
        Retorna a maior matrícula numérica existente como uma string formatada (ex: '0005').
        Considera apenas matrículas que podem ser convertidas em números.
        Se não houver matrículas numéricas, retorna None.
        """
        query = """
            SELECT Matricula
            FROM funcionarios
            WHERE Matricula REGEXP '^[0-9]+$' -- Filtra apenas matrículas que são números
            ORDER BY CAST(Matricula AS UNSIGNED) DESC -- Converte para UNSIGNED para ordenar numericamente
            LIMIT 1
        """
        # Usa self.db.execute_query()
        result = self.db.execute_query(query, fetch_results=True)
        # Retorna o valor da coluna 'Matricula' do primeiro resultado, se existir
        return result[0]['Matricula'] if result and result[0] and 'Matricula' in result[0] else None

    def get_all_cargos(self):
        """
        Retorna todos os cargos disponíveis, usando execute_query.
        """
        query = "SELECT ID_Cargos, Nome_Cargo FROM cargos ORDER BY Nome_Cargo"
        # Usa self.db.execute_query()
        return self.db.execute_query(query, fetch_results=True)

    def get_all_niveis(self):
        """
        Retorna todos os níveis disponíveis, usando execute_query.
        """
        query = "SELECT ID_Niveis, Nome_Nivel FROM niveis ORDER BY Nome_Nivel"
        # Usa self.db.execute_query()
        return self.db.execute_query(query, fetch_results=True)

    # --- Funções para gerenciar detalhes (contatos, documentos, endereços) ---
    # Estas funções também foram adaptadas para usar self.db.execute_query()

    def get_employee_contacts(self, matricula_funcionario):
        query = "SELECT * FROM funcionarios_contatos WHERE Matricula_Funcionario = %s"
        # Usa self.db.execute_query()
        result = self.db.execute_query(query, (matricula_funcionario,), fetch_results=True)
        return result[0] if result else None # Assumindo um único registro completo

    def get_employee_documents(self, matricula_funcionario):
        query = "SELECT * FROM funcionarios_documentos WHERE Matricula_Funcionario = %s"
        # Usa self.db.execute_query()
        return self.db.execute_query(query, (matricula_funcionario,), fetch_results=True) # Pode ter vários documentos

    def get_employee_address(self, matricula_funcionario):
        query = "SELECT * FROM funcionarios_enderecos WHERE Matricula_Funcionario = %s"
        # Usa self.db.execute_query()
        result = self.db.execute_query(query, (matricula_funcionario,), fetch_results=True)
        return result[0] if result else None # Assumindo um único registro completo

    def check_document_unique(self, numero_documento, tipo_documento, exclude_matricula=None):
        query = "SELECT COUNT(*) AS count FROM funcionarios_documentos WHERE Numero_Documento = %s AND Tipo_Documento = %s"
        params = [numero_documento, tipo_documento]

        if exclude_matricula:
            query += " AND Matricula_Funcionario != %s"
            params.append(exclude_matricula)
        
        # Usa self.db.execute_query()
        result = self.db.execute_query(query, tuple(params), fetch_results=True)
        return result[0]['count'] > 0 if result and result[0] else False
