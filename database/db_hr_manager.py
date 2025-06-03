# database/db_hr_manager.py
from datetime import date, datetime

class HrManager:
    def __init__(self, db_manager):
        self.db = db_manager
        # self.cursor = db_manager.cursor # REMOVIDO: DatabaseManager gerencia o cursor internamente.

    # Métodos CRUD para Cargos
    def adicionar_cargo(self, nome_cargo, descricao, cbo):
        query = "INSERT INTO cargos (Nome_Cargo, Descricao_Cargo, Cbo, Data_Criacao, Data_Modificacao) VALUES (%s, %s, %s, NOW(), NOW())"
        params = (nome_cargo, descricao, cbo)
        # Usar execute_query com fetch_results=False para INSERT/UPDATE/DELETE
        return self.db.execute_query(query, params, fetch_results=False)

    def buscar_cargo(self, id_cargo):
        query = "SELECT * FROM cargos WHERE ID_Cargos = %s"
        # Usar execute_query com fetch_results=True para SELECT
        result = self.db.execute_query(query, (id_cargo,), fetch_results=True)
        return result[0] if result else None # Retorna o primeiro registro ou None

    def buscar_todos_cargos(self):
        query = "SELECT * FROM cargos"
        return self.db.execute_query(query, fetch_results=True)

    def atualizar_cargo(self, id_cargo, nome_cargo, descricao, cbo):
        query = "UPDATE cargos SET Nome_Cargo = %s, Descricao_Cargo = %s, Cbo = %s, Data_Modificacao = NOW() WHERE ID_Cargos = %s"
        params = (nome_cargo, descricao, cbo, id_cargo)
        return self.db.execute_query(query, params, fetch_results=False)

    def deletar_cargo(self, id_cargo):
        query = "DELETE FROM cargos WHERE ID_Cargos = %s"
        return self.db.execute_query(query, (id_cargo,), fetch_results=False)

    # Métodos CRUD para Funcionários
    def adicionar_funcionario(self, matricula, nome_completo, data_admissao, id_cargo, id_nivel, status):
        query = "INSERT INTO funcionarios (Matricula, Nome_Completo, Data_Admissao, ID_Cargos, ID_Niveis, Status, Data_Criacao, Data_Modificacao) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())"
        params = (matricula, nome_completo, data_admissao, id_cargo, id_nivel, status)
        return self.db.execute_query(query, params, fetch_results=False)

    def buscar_funcionario(self, matricula):
        query = "SELECT * FROM funcionarios WHERE Matricula = %s"
        result = self.db.execute_query(query, (matricula,), fetch_results=True)
        return result[0] if result else None

    def buscar_todos_funcionarios(self):
        query = "SELECT * FROM funcionarios"
        return self.db.execute_query(query, fetch_results=True)

    def atualizar_funcionario(self, matricula, nome_completo, data_admissao, id_cargo, id_nivel, status):
        query = "UPDATE funcionarios SET Nome_Completo = %s, Data_Admissao = %s, ID_Cargos = %s, ID_Niveis = %s, Status = %s, Data_Modificacao = NOW() WHERE Matricula = %s"
        params = (nome_completo, data_admissao, id_cargo, id_nivel, status, matricula)
        return self.db.execute_query(query, params, fetch_results=False)

    def deletar_funcionario(self, matricula):
        query = "DELETE FROM funcionarios WHERE Matricula = %s"
        return self.db.execute_query(query, (matricula,), fetch_results=False)

    # Métodos para Salários
    def adicionar_salario(self, id_cargo, id_nivel, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia):
        query = """
            INSERT INTO salarios (
                ID_Cargos, ID_Niveis, Salario_Base, Periculosidade, Insalubridade,
                Ajuda_De_Custo, Vale_Refeicao, Gratificacao, Cesta_Basica, Outros_Beneficios,
                Data_Vigencia, Data_Criacao, Data_Modificacao
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (
            id_cargo, id_nivel, salario_base, periculosidade, insalubridade,
            ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios,
            data_vigencia
        )
        return self.db.execute_query(query, params, fetch_results=False)

    def buscar_salario(self, id_salario):
        query = "SELECT * FROM salarios WHERE ID_Salarios = %s"
        result = self.db.execute_query(query, (id_salario,), fetch_results=True)
        return result[0] if result else None

    def buscar_salarios_por_cargo_nivel(self, id_cargo=None, id_nivel=None):
        query = "SELECT * FROM salarios WHERE 1=1"
        params = []
        if id_cargo:
            query += " AND ID_Cargos = %s"
            params.append(id_cargo)
        if id_nivel:
            query += " AND ID_Niveis = %s"
            params.append(id_nivel)
        
        # Certifique-se de passar uma tupla para execute_query, mesmo se tiver apenas um item.
        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def atualizar_salario(self, id_salario, id_cargo, id_nivel, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia):
        query = """
            UPDATE salarios SET
                ID_Cargos = %s, ID_Niveis = %s, Salario_Base = %s, Periculosidade = %s, Insalubridade = %s,
                Ajuda_De_Custo = %s, Vale_Refeicao = %s, Gratificacao = %s, Cesta_Basica = %s, Outros_Beneficios = %s,
                Data_Vigencia = %s, Data_Modificacao = NOW()
            WHERE ID_Salarios = %s
        """
        params = (
            id_cargo, id_nivel, salario_base, periculosidade, insalubridade,
            ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios,
            data_vigencia, id_salario
        )
        return self.db.execute_query(query, params, fetch_results=False)

    def deletar_salario(self, id_salario):
        query = "DELETE FROM salarios WHERE ID_Salarios = %s"
        return self.db.execute_query(query, (id_salario,), fetch_results=False)

    # Métodos para Níveis
    def adicionar_nivel(self, nome_nivel, descricao):
        query = "INSERT INTO niveis (Nome_Nivel, Descricao, Data_Criacao, Data_Modificacao) VALUES (%s, %s, NOW(), NOW())"
        params = (nome_nivel, descricao)
        return self.db.execute_query(query, params, fetch_results=False)

    def buscar_nivel(self, id_nivel):
        query = "SELECT * FROM niveis WHERE ID_Niveis = %s"
        result = self.db.execute_query(query, (id_nivel,), fetch_results=True)
        return result[0] if result else None

    def buscar_todos_niveis(self):
        query = "SELECT * FROM niveis"
        return self.db.execute_query(query, fetch_results=True)

    def atualizar_nivel(self, id_nivel, nome_nivel, descricao):
        query = "UPDATE niveis SET Nome_Nivel = %s, Descricao = %s, Data_Modificacao = NOW() WHERE ID_Niveis = %s"
        params = (nome_nivel, descricao, id_nivel)
        return self.db.execute_query(query, params, fetch_results=False)

    def deletar_nivel(self, id_nivel):
        query = "DELETE FROM niveis WHERE ID_Niveis = %s"
        return self.db.execute_query(query, (id_nivel,), fetch_results=False)