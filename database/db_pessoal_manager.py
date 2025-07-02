# database/db_pessoal_manager.py

import mysql.connector
from datetime import datetime, date, timedelta
import pandas as pd
from database.db_base import DatabaseManager 

class PessoalManager:
    def __init__(self, db_connection):
        self.db = db_connection

    # ==================================================================================================================================
    # === MÉTODOS AUXILIARES GERAIS ====================================================================================================
    # ==================================================================================================================================

    def _format_date_fields(self, item):
        """
        Função auxiliar para converter campos de data em dicionários de resultados
        para objetos date ou None.
        """
        if item is None:
            return None
        
        # Lista de campos de data/datetime que precisam de formatação para objeto date
        # INCLUA AQUI TODAS AS NOVAS COLUNAS DE DATA DA TABELA funcionarios_documentos
        date_fields_to_format = [
            'Data_Criacao', 'Data_Modificacao', 
            'Data_Admissao', # Funcionarios
            'Data_Vigencia', # Salarios
            'Periodo_Aquisitivo_Inicio', 'Periodo_Aquisitivo_Fim', # Ferias
            'Data_Inicio_Gozo', 'Data_Fim_Gozo', # Ferias
            'Data_Nascimento', # Funcionarios_Documentos e Dependentes
            'Rg_DataEmissao', # Funcionarios_Documentos
            'Cnh_DataValidade', # Funcionarios_Documentos
            'Ctps_DataEmissao', # Se decidir adicionar, descomente aqui (agora removida por opção)
            'Pispasep_DataCadastro' # Se decidir adicionar, descomente aqui (agora removida por opção)
        ]
        
        for key in date_fields_to_format:
            if key in item:
                value = item[key]
                if isinstance(value, str):
                    if not value.strip():
                        item[key] = None
                        continue
                    try:
                        item[key] = datetime.strptime(value, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            item[key] = datetime.strptime(value, '%Y-%m-%d %H:%M:%S').date()
                        except ValueError:
                            print(f"AVISO: Não foi possível converter a string de data '{value}' para objeto date para o campo '{key}'. Definindo como None.")
                            item[key] = None
                elif isinstance(value, datetime):
                    item[key] = value.date()
                elif value is None:
                    item[key] = None

        return item

    # ==================================================================================================================================
    # === MÉTODOS DO SUBMÓDULO: FUNCIONÁRIOS ==========================================================================================
    # ==================================================================================================================================

    # ----------------------------------------------------------------------------------------------------------------------------------
    # --- GERADOR DE NÚMERO DE MATRÍCULA PADRÃO SEQUENCIAL PARA SUGERIR NA INCLUSÃO DE NOVO FUNCIONÁRIO ------------------------------
    # ----------------------------------------------------------------------------------------------------------------------------------
    def generate_next_matricula(self):
        """Gera a próxima matrícula sequencial baseada na última matrícula existente."""
        try:
            query = "SELECT Matricula FROM funcionarios WHERE Matricula REGEXP '^MATR[0-9]+$' ORDER BY LENGTH(Matricula) DESC, Matricula DESC LIMIT 1"
            last_matricula_data = self.db.execute_query(query, fetch_results=True)
            
            if last_matricula_data and last_matricula_data[0]['Matricula']:
                last_matricula = last_matricula_data[0]['Matricula']
                num = int(last_matricula[4:]) + 1
                return f"MATR{num:03d}"
            return "MATR001"
        except Exception as e:
            print(f"Erro ao gerar próxima matrícula: {e}")
            return "MATR001"

    # ----------------------------------------------------------------------------------------------------------------------------------
    # --- MÉTODOS CRUD PRINCIPAIS DE FUNCIONÁRIOS (TABELA 'funcionarios') --------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------------------
    def get_all_funcionarios(self, search_matricula=None, search_nome=None, search_status=None, search_cargo_id=None):
        """
        Retorna uma lista de todos os funcionários, opcionalmente filtrada,
        incluindo informações de cargo e nível.
        """
        query = """
            SELECT
                f.Matricula,
                f.Nome_Completo,
                f.Data_Admissao,
                f.ID_Cargos,
                f.ID_Niveis,
                f.Status,
                c.Nome_Cargo,
                n.Nome_Nivel,
                f.Data_Criacao,
                f.Data_Modificacao
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
        if search_nome:
            query += " AND f.Nome_Completo LIKE %s"
            params.append(f"%{search_nome}%")
        if search_status:
            query += " AND f.Status = %s"
            params.append(search_status)
        if search_cargo_id:
            query += " AND f.ID_Cargos = %s"
            params.append(search_cargo_id)
        
        query += " ORDER BY f.Nome_Completo"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    def add_funcionario(self, matricula, nome_completo, data_admissao, id_cargos, id_niveis, status):
        """Adiciona um novo funcionário à tabela 'funcionarios'."""
        query = """
            INSERT INTO funcionarios (Matricula, Nome_Completo, Data_Admissao, ID_Cargos, ID_Niveis, Status, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (matricula, nome_completo, data_admissao, id_cargos, id_niveis, status)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_funcionario_by_matricula(self, matricula):
        """
        Retorna os dados principais de um funcionário e seus dados pessoais/documentos
        pela matrícula, usando JOIN com funcionarios_documentos.
        """
        query = """
            SELECT
                f.Matricula, f.Nome_Completo, f.Data_Admissao, f.ID_Cargos, f.ID_Niveis, f.Status,
                c.Nome_Cargo, n.Nome_Nivel,
                fd.Data_Nascimento, fd.Estado_Civil, fd.Nacionalidade, fd.Naturalidade, fd.Genero,
                fd.Rg_Numero, fd.Rg_OrgaoEmissor, fd.Rg_UfEmissor, fd.Rg_DataEmissao,
                fd.Cpf_Numero,
                fd.Ctps_Numero, fd.Ctps_Serie,
                fd.Pispasep,
                fd.Cnh_Numero, fd.Cnh_Categoria, fd.Cnh_DataValidade, fd.Cnh_OrgaoEmissor,
                fd.TitEleitor_Numero, fd.TitEleitor_Zona, fd.TitEleitor_Secao,
                fd.Observacoes, fd.Link_Foto,
                f.Data_Criacao, f.Data_Modificacao
            FROM
                funcionarios f
            LEFT JOIN cargos c ON f.ID_Cargos = c.ID_Cargos
            LEFT JOIN niveis n ON f.ID_Niveis = n.ID_Niveis
            LEFT JOIN funcionarios_documentos fd ON f.Matricula = fd.Matricula_Funcionario
            WHERE f.Matricula = %s
        """
        result = self.db.execute_query(query, (matricula,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_funcionario(self, old_matricula, new_matricula, nome_completo, data_admissao, id_cargos, id_niveis, status):
        """Atualiza os dados principais de um funcionário."""
        query = """
            UPDATE funcionarios
            SET
                Matricula = %s,
                Nome_Completo = %s,
                Data_Admissao = %s,
                ID_Cargos = %s,
                ID_Niveis = %s,
                Status = %s,
                Data_Modificacao = NOW()
            WHERE Matricula = %s
        """
        params = (new_matricula, nome_completo, data_admissao, id_cargos, id_niveis, status, old_matricula)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_funcionario(self, matricula):
        """Exclui um funcionário pelo ID. ON DELETE CASCADE cuidará das tabelas relacionadas."""
        query = "DELETE FROM funcionarios WHERE Matricula = %s"
        return self.db.execute_query(query, (matricula,), fetch_results=False)

    # ----------------------------------------------------------------------------------------------------------------------------------
    # --- MÉTODOS PARA DADOS PESSOAIS E DOCUMENTOS (TABELA 'funcionarios_documentos') --------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------------------
    def save_funcionario_dados_pessoais_documentos(self, matricula, data_nascimento, estado_civil, nacionalidade, naturalidade, genero,
                                                    rg_numero, rg_orgao_emissor, rg_uf_emissor, rg_data_emissao,
                                                    cpf_numero,
                                                    ctps_numero, ctps_serie,
                                                    pispasep,
                                                    cnh_numero, cnh_categoria, cnh_data_validade, cnh_orgao_emissor,
                                                    titeleitor_numero, titeleitor_zona, titeleitor_secao,
                                                    observacoes, link_foto):
        """
        Salva (insere ou atualiza) os dados pessoais e de documentos consolidados de um funcionário.
        Existe apenas uma linha por funcionário nesta tabela.
        """
        # Tenta encontrar um registro existente
        existing_data = self.db.execute_query("SELECT Matricula_Funcionario FROM funcionarios_documentos WHERE Matricula_Funcionario = %s", (matricula,), fetch_results=True)

        params = [
            data_nascimento, estado_civil, nacionalidade, naturalidade, genero,
            rg_numero, rg_orgao_emissor, rg_uf_emissor, rg_data_emissao,
            cpf_numero,
            ctps_numero, ctps_serie,
            pispasep,
            cnh_numero, cnh_categoria, cnh_data_validade, cnh_orgao_emissor,
            titeleitor_numero, titeleitor_zona, titeleitor_secao,
            observacoes, link_foto
        ]

        if existing_data:
            # Atualiza o registro existente
            query = """
                UPDATE funcionarios_documentos
                SET
                    Data_Nascimento = %s, Estado_Civil = %s, Nacionalidade = %s, Naturalidade = %s, Genero = %s,
                    Rg_Numero = %s, Rg_OrgaoEmissor = %s, Rg_UfEmissor = %s, Rg_DataEmissao = %s,
                    Cpf_Numero = %s,
                    Ctps_Numero = %s, Ctps_Serie = %s,
                    Pispasep = %s,
                    Cnh_Numero = %s, Cnh_Categoria = %s, Cnh_DataValidade = %s, Cnh_OrgaoEmissor = %s,
                    TitEleitor_Numero = %s, TitEleitor_Zona = %s, TitEleitor_Secao = %s,
                    Observacoes = %s, Link_Foto = %s,
                    Data_Modificacao = NOW()
                WHERE Matricula_Funcionario = %s
            """
            params.append(matricula) # Adiciona a matrícula para a cláusula WHERE
            return self.db.execute_query(query, tuple(params), fetch_results=False)
        else:
            # Insere um novo registro
            query = """
                INSERT INTO funcionarios_documentos (
                    Matricula_Funcionario, Data_Nascimento, Estado_Civil, Nacionalidade, Naturalidade, Genero,
                    Rg_Numero, Rg_OrgaoEmissor, Rg_UfEmissor, Rg_DataEmissao,
                    Cpf_Numero, Ctps_Numero, Ctps_Serie, Pispasep, Cnh_Numero, Cnh_Categoria, Cnh_DataValidade, Cnh_OrgaoEmissor,
                    TitEleitor_Numero, TitEleitor_Zona, TitEleitor_Secao, Observacoes, Link_Foto,
                    Data_Criacao, Data_Modificacao
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                )
            """
            # Adiciona a matrícula no início dos parâmetros para o INSERT
            insert_params = [matricula] + params 
            return self.db.execute_query(query, tuple(insert_params), fetch_results=False)

    def get_funcionario_dados_pessoais_documentos_by_matricula(self, matricula):
        """
        Retorna os dados pessoais e de documentos de um funcionário
        diretamente da tabela 'funcionarios_documentos'.
        """
        query = """
            SELECT
                Matricula_Funcionario, Data_Nascimento, Estado_Civil, Nacionalidade, Naturalidade, Genero,
                Rg_Numero, Rg_OrgaoEmissor, Rg_UfEmissor, Rg_DataEmissao,
                Cpf_Numero,
                Ctps_Numero, Ctps_Serie,
                Pispasep,
                Cnh_Numero, Cnh_Categoria, Cnh_DataValidade, Cnh_OrgaoEmissor,
                TitEleitor_Numero, TitEleitor_Zona, TitEleitor_Secao,
                Observacoes, Link_Foto,
                Data_Criacao, Data_Modificacao
            FROM funcionarios_documentos
            WHERE Matricula_Funcionario = %s
        """
        result = self.db.execute_query(query, (matricula,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    # ----------------------------------------------------------------------------------------------------------------------------------
    # --- MÉTODO PARA EXPORTAÇÃO COMPLETA DE FUNCIONÁRIOS (AGORA MAIS EFICIENTE) ------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------------------
    def get_all_funcionarios_completo(self, search_matricula=None, search_nome=None, search_status=None, search_cargo_id=None):
        """
        Retorna uma lista de todos os funcionários com todos os dados associados (pessoais, documentos, endereços, contatos)
        para fins de exportação ou relatórios detalhados, utilizando JOINs.
        """
        query = """
            SELECT
                f.Matricula, f.Nome_Completo, f.Data_Admissao, f.Status, f.Data_Criacao, f.Data_Modificacao,
                c.Nome_Cargo, n.Nome_Nivel,
                fd.Data_Nascimento, fd.Estado_Civil, fd.Nacionalidade, fd.Naturalidade, fd.Genero,
                fd.Rg_Numero, fd.Rg_OrgaoEmissor, fd.Rg_UfEmissor, fd.Rg_DataEmissao,
                fd.Cpf_Numero,
                fd.Ctps_Numero, fd.Ctps_Serie,
                fd.Pispasep,
                fd.Cnh_Numero, fd.Cnh_Categoria, fd.Cnh_DataValidade, fd.Cnh_OrgaoEmissor,
                fd.TitEleitor_Numero, fd.TitEleitor_Zona, fd.TitEleitor_Secao,
                fd.Observacoes AS Doc_Observacoes, fd.Link_Foto, -- Renomeado para evitar conflito com 'Observacoes' de outras tabelas
                fe.Logradouro AS End_Logradouro, fe.Numero AS End_Numero, fe.Complemento AS End_Complemento,
                fe.Bairro AS End_Bairro, fe.Cidade AS End_Cidade, fe.Estado AS End_Estado, fe.Cep AS End_Cep,
                fc.Valor_Contato AS Tel_Principal, fc2.Valor_Contato AS Email_Pessoal
            FROM
                funcionarios f
            LEFT JOIN cargos c ON f.ID_Cargos = c.ID_Cargos
            LEFT JOIN niveis n ON f.ID_Niveis = n.ID_Niveis
            LEFT JOIN funcionarios_documentos fd ON f.Matricula = fd.Matricula_Funcionario
            LEFT JOIN funcionarios_enderecos fe ON f.Matricula = fe.Matricula_Funcionario AND fe.Tipo_Endereco = 'Residencial'
            LEFT JOIN funcionarios_contatos fc ON f.Matricula = fc.Matricula_Funcionario AND fc.Tipo_Contato = 'Telefone Principal'
            LEFT JOIN funcionarios_contatos fc2 ON f.Matricula = fc2.Matricula_Funcionario AND fc2.Tipo_Contato = 'Email Pessoal'
            WHERE 1=1
        """
        params = []
        if search_matricula:
            query += " AND f.Matricula LIKE %s"
            params.append(f"%{search_matricula}%")
        if search_nome:
            query += " AND f.Nome_Completo LIKE %s"
            params.append(f"%{search_nome}%")
        if search_status:
            query += " AND f.Status = %s"
            params.append(search_status)
        if search_cargo_id:
            query += " AND f.ID_Cargos = %s"
            params.append(search_cargo_id)
        
        query += " ORDER BY f.Nome_Completo"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    # ==================================================================================================================================
    # === MÉTODOS DO SUBMÓDULO: ENDEREÇOS DE FUNCIONÁRIOS ==============================================================================
    # ==================================================================================================================================

    def add_funcionario_endereco(self, matricula, tipo_endereco, logradouro, numero, complemento, bairro, cidade, estado, cep):
        """Adiciona um endereço para um funcionário."""
        query = """
            INSERT INTO funcionarios_enderecos (Matricula_Funcionario, Tipo_Endereco, Logradouro, Numero, Complemento, Bairro, Cidade, Estado, Cep, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (matricula, tipo_endereco, logradouro, numero, complemento, bairro, cidade, estado, cep)
        return self.db.execute_query(query, params, fetch_results=False)

    def update_or_add_funcionario_endereco(self, matricula, tipo_endereco, logradouro, numero, complemento, bairro, cidade, estado, cep):
        """
        Atualiza um endereço existente de um tipo específico ou o insere se não existir.
        Simplificado para um único endereço por tipo (ex: apenas um residencial).
        """
        if not all([logradouro, numero, bairro, cidade, estado, cep]): 
            existing_end = self.db.execute_query("SELECT ID_Funcionario_Endereco FROM funcionarios_enderecos WHERE Matricula_Funcionario = %s AND Tipo_Endereco = %s", (matricula, tipo_endereco), fetch_results=True)
            if existing_end:
                self.db.execute_query("DELETE FROM funcionarios_enderecos WHERE ID_Funcionario_Endereco = %s", (existing_end[0]['ID_Funcionario_Endereco'],), fetch_results=False)
            return

        existing_end = self.db.execute_query("SELECT ID_Funcionario_Endereco FROM funcionarios_enderecos WHERE Matricula_Funcionario = %s AND Tipo_Endereco = %s", (matricula, tipo_endereco), fetch_results=True)
        
        if existing_end:
            query = """
                UPDATE funcionarios_enderecos
                SET
                    Logradouro = %s,
                    Numero = %s,
                    Complemento = %s,
                    Bairro = %s,
                    Cidade = %s,
                    Estado = %s,
                    Cep = %s,
                    Data_Modificacao = NOW()
                WHERE ID_Funcionario_Endereco = %s
            """
            params = (logradouro, numero, complemento, bairro, cidade, estado, cep, existing_end[0]['ID_Funcionario_Endereco'])
            self.db.execute_query(query, params, fetch_results=False)
        else:
            self.add_funcionario_endereco(matricula, tipo_endereco, logradouro, numero, complemento, bairro, cidade, estado, cep)

    def get_funcionario_enderecos_by_matricula(self, matricula):
        """Retorna todos os endereços de um funcionário."""
        query = """
            SELECT
                ID_Funcionario_Endereco, Matricula_Funcionario, Tipo_Endereco, Logradouro, Numero,
                Complemento, Bairro, Cidade, Estado, Cep, Data_Criacao, Data_Modificacao
            FROM funcionarios_enderecos
            WHERE Matricula_Funcionario = %s
        """
        results = self.db.execute_query(query, (matricula,), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return []

    # ==================================================================================================================================
    # === MÉTODOS DO SUBMÓDULO: CONTATOS DE FUNCIONÁRIOS ===============================================================================
    # ==================================================================================================================================

    def add_funcionario_contato(self, matricula, tipo_contato, valor_contato, observacoes=None):
        """Adiciona um contato para um funcionário."""
        query = """
            INSERT INTO funcionarios_contatos (Matricula_Funcionario, Tipo_Contato, Valor_Contato, Observacoes, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
        """
        params = (matricula, tipo_contato, valor_contato, observacoes)
        return self.db.execute_query(query, params, fetch_results=False)

    def update_or_add_funcionario_contato(self, matricula, tipo_contato, valor_contato, observacoes=None):
        """
        Atualiza um contato existente de um tipo específico ou o insere se não existir.
        Simplificado para um único contato por tipo (ex: apenas um telefone principal).
        """
        if not valor_contato:
            existing_contato = self.db.execute_query("SELECT ID_Funcionario_Contato FROM funcionarios_contatos WHERE Matricula_Funcionario = %s AND Tipo_Contato = %s", (matricula, tipo_contato), fetch_results=True)
            if existing_contato:
                self.db.execute_query("DELETE FROM funcionarios_contatos WHERE ID_Funcionario_Contato = %s", (existing_contato[0]['ID_Funcionario_Contato'],), fetch_results=False)
            return

        existing_contato = self.db.execute_query("SELECT ID_Funcionario_Contato FROM funcionarios_contatos WHERE Matricula_Funcionario = %s AND Tipo_Contato = %s", (matricula, tipo_contato), fetch_results=True)
        
        if existing_contato:
            query = """
                UPDATE funcionarios_contatos
                SET
                    Valor_Contato = %s,
                    Observacoes = %s,
                    Data_Modificacao = NOW()
                WHERE ID_Funcionario_Contato = %s
            """
            params = (valor_contato, observacoes, existing_contato[0]['ID_Funcionario_Contato'])
            self.db.execute_query(query, params, fetch_results=False)
        else:
            self.add_funcionario_contato(matricula, tipo_contato, valor_contato, observacoes)

    def get_funcionario_contatos_by_matricula(self, matricula):
        """Retorna todos os contatos de um funcionário."""
        query = """
            SELECT
                ID_Funcionario_Contato, Matricula_Funcionario, Tipo_Contato, Valor_Contato,
                Observacoes, Data_Criacao, Data_Modificacao
            FROM funcionarios_contatos
            WHERE Matricula_Funcionario = %s
        """
        results = self.db.execute_query(query, (matricula,), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return []

    # ==================================================================================================================================
    # === MÉTODOS DO SUBMÓDULO: CARGOS =================================================================================================
    # ==================================================================================================================================

    def get_all_cargos_for_dropdown(self):
        """Retorna uma lista de cargos para preencher dropdowns."""
        query = "SELECT ID_Cargos, Nome_Cargo FROM cargos ORDER BY Nome_Cargo"
        return self.db.execute_query(query, fetch_results=True)

    def get_all_cargos(self, search_nome=None):
        """Retorna uma lista de todos os cargos, opcionalmente filtrada."""
        query = """
            SELECT
                ID_Cargos, Nome_Cargo, Descricao_Cargo, Cbo, Data_Criacao, Data_Modificacao
            FROM cargos
            WHERE 1=1
        """
        params = []
        if search_nome:
            query += " AND Nome_Cargo LIKE %s"
            params.append(f"%{search_nome}%")
        
        query += " ORDER BY Nome_Cargo"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    def add_cargo(self, nome_cargo, descricao_cargo, cbo):
        """Adiciona um novo cargo ao banco de dados."""
        query = """
            INSERT INTO cargos (Nome_Cargo, Descricao_Cargo, Cbo, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, NOW(), NOW())
        """
        params = (nome_cargo, descricao_cargo, cbo)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_cargo_by_id(self, cargo_id):
        """Retorna os dados de um cargo pelo ID."""
        query = """
            SELECT
                ID_Cargos, Nome_Cargo, Descricao_Cargo, Cbo, Data_Criacao, Data_Modificacao
            FROM cargos
            WHERE ID_Cargos = %s
        """
        result = self.db.execute_query(query, (cargo_id,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_cargo(self, cargo_id, nome_cargo, descricao_cargo, cbo):
        """Atualiza os dados de um cargo existente."""
        query = """
            UPDATE cargos
            SET
                Nome_Cargo = %s, Descricao_Cargo = %s, Cbo = %s, Data_Modificacao = NOW()
            WHERE ID_Cargos = %s
        """
        params = (nome_cargo, descricao_cargo, cbo, cargo_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_cargo(self, cargo_id):
        """
        Exclui um cargo do banco de dados.
        Retorna False se houver funcionários associados.
        """
        check_query = "SELECT COUNT(*) AS count FROM funcionarios WHERE ID_Cargos = %s"
        result = self.db.execute_query(check_query, (cargo_id,), fetch_results=True)
        if result and result[0]['count'] > 0:
            print(f"Não é possível excluir o cargo ID {cargo_id}: Existem funcionários associados.")
            return False
        query = "DELETE FROM cargos WHERE ID_Cargos = %s"
        return self.db.execute_query(query, (cargo_id,), fetch_results=False)

    def get_cargo_by_nome(self, nome_cargo):
        """Verifica se um cargo com o dado nome já existe."""
        query = "SELECT ID_Cargos FROM cargos WHERE Nome_Cargo = %s"
        result = self.db.execute_query(query, (nome_cargo,), fetch_results=True)
        return result[0] if result else None

    # ==================================================================================================================================
    # === MÉTODOS DO SUBMÓDULO: NÍVEIS =================================================================================================
    # ==================================================================================================================================

    def get_all_niveis_for_dropdown(self):
        """Retorna uma lista de níveis para preencher dropdowns."""
        query = "SELECT ID_Niveis, Nome_Nivel FROM niveis ORDER BY Nome_Nivel"
        return self.db.execute_query(query, fetch_results=True)

    def get_all_niveis(self, search_nome=None):
        """Retorna uma lista de todos os níveis, opcionalmente filtrada."""
        query = """
            SELECT
                ID_Niveis, Nome_Nivel, Descricao, Data_Criacao, Data_Modificacao
            FROM niveis
            WHERE 1=1
        """
        params = []
        if search_nome:
            query += " AND Nome_Nivel LIKE %s"
            params.append(f"%{search_nome}%")
        
        query += " ORDER BY Nome_Nivel"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    def add_nivel(self, nome_nivel, descricao):
        """Adiciona um novo nível ao banco de dados."""
        query = """
            INSERT INTO niveis (Nome_Nivel, Descricao, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, NOW(), NOW())
        """
        params = (nome_nivel, descricao)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_nivel_by_id(self, nivel_id):
        """Retorna os dados de um nível pelo ID."""
        query = """
            SELECT
                ID_Niveis, Nome_Nivel, Descricao, Data_Criacao, Data_Modificacao
            FROM niveis
            WHERE ID_Niveis = %s
        """
        result = self.db.execute_query(query, (nivel_id,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_nivel(self, nivel_id, nome_nivel, descricao):
        """Atualiza os dados de um nível existente."""
        query = """
            UPDATE niveis
            SET
                Nome_Nivel = %s, Descricao = %s, Data_Modificacao = NOW()
            WHERE ID_Niveis = %s
        """
        params = (nome_nivel, descricao, nivel_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_nivel(self, nivel_id):
        """
        Exclui um nível do banco de dados.
        Retorna False se houver funcionários associados.
        """
        check_query = "SELECT COUNT(*) AS count FROM funcionarios WHERE ID_Niveis = %s"
        result = self.db.execute_query(check_query, (nivel_id,), fetch_results=True)
        if result and result[0]['count'] > 0:
            print(f"Não é possível excluir o nível ID {nivel_id}: Existem funcionários associados.")
            return False
        query = "DELETE FROM niveis WHERE ID_Niveis = %s"
        return self.db.execute_query(query, (nivel_id,), fetch_results=False)

    def get_nivel_by_nome(self, nome_nivel):
        """Verifica se um nível com o dado nome já existe."""
        query = "SELECT ID_Niveis FROM niveis WHERE Nome_Nivel = %s"
        result = self.db.execute_query(query, (nome_nivel,), fetch_results=True)
        return result[0] if result else None

    # ==================================================================================================================================
    # === MÉTODOS DO SUBMÓDULO: SALÁRIOS E BENEFÍCIOS ==================================================================================
    # ==================================================================================================================================

    def get_all_salarios(self, search_cargo_id=None, search_nivel_id=None):
        """
        Retorna uma lista de todos os pacotes salariais, opcionalmente filtrada,
        incluindo informações de cargo e nível.
        """
        query = """
            SELECT
                s.ID_Salarios, s.ID_Cargos, s.ID_Niveis, s.Salario_Base, s.Periculosidade,
                s.Insalubridade, s.Ajuda_De_Custo, s.Vale_Refeicao, s.Gratificacao, s.Cesta_Basica,
                s.Outros_Beneficios, s.Data_Vigencia, c.Nome_Cargo, n.Nome_Nivel,
                s.Data_Criacao, s.Data_Modificacao
            FROM salarios s
            LEFT JOIN cargos c ON s.ID_Cargos = c.ID_Cargos
            LEFT JOIN niveis n ON s.ID_Niveis = n.ID_Niveis
            WHERE 1=1
        """
        params = []

        if search_cargo_id:
            query += " AND s.ID_Cargos = %s"
            params.append(search_cargo_id)
        if search_nivel_id:
            query += " AND s.ID_Niveis = %s"
            params.append(search_nivel_id)
        
        query += " ORDER BY c.Nome_Cargo, n.Nome_Nivel, s.Data_Vigencia DESC"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    def add_salario(self, id_cargos, id_niveis, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia):
        """Adiciona um novo pacote salarial ao banco de dados."""
        query = """
            INSERT INTO salarios (ID_Cargos, ID_Niveis, Salario_Base, Periculosidade, Insalubridade, Ajuda_De_Custo, Vale_Refeicao, Gratificacao, Cesta_Basica, Outros_Beneficios, Data_Vigencia, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (id_cargos, id_niveis, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_salario_by_id(self, salario_id):
        """Retorna os dados de um pacote salarial pelo ID."""
        query = """
            SELECT
                s.ID_Salarios, s.ID_Cargos, s.ID_Niveis, s.Salario_Base, s.Periculosidade,
                s.Insalubridade, s.Ajuda_De_Custo, s.Vale_Refeicao, s.Gratificacao, s.Cesta_Basica,
                s.Outros_Beneficios, s.Data_Vigencia, c.Nome_Cargo, n.Nome_Nivel,
                s.Data_Criacao, s.Data_Modificacao
            FROM salarios s
            LEFT JOIN cargos c ON s.ID_Cargos = c.ID_Cargos
            LEFT JOIN niveis n ON s.ID_Niveis = n.ID_Niveis
            WHERE s.ID_Salarios = %s
        """
        result = self.db.execute_query(query, (salario_id,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_salario(self, salario_id, id_cargos, id_niveis, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia):
        """Atualiza os dados de um pacote salarial existente."""
        query = """
            UPDATE salarios
            SET
                ID_Cargos = %s, ID_Niveis = %s, Salario_Base = %s, Periculosidade = %s, Insalubridade = %s,
                Ajuda_De_Custo = %s, Vale_Refeicao = %s, Gratificacao = %s, Cesta_Basica = %s,
                Outros_Beneficios = %s, Data_Vigencia = %s, Data_Modificacao = NOW()
            WHERE ID_Salarios = %s
        """
        params = (id_cargos, id_niveis, salario_base, periculosidade, insalubridade, ajuda_de_custo, vale_refeicao, gratificacao, cesta_basica, outros_beneficios, data_vigencia, salario_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_salario(self, salario_id):
        """Exclui um pacote salarial do banco de dados."""
        query = "DELETE FROM salarios WHERE ID_Salarios = %s"
        return self.db.execute_query(query, (salario_id,), fetch_results=False)

    def get_salario_by_cargo_nivel_vigencia(self, id_cargos, id_niveis, data_vigencia):
        """Verifica se já existe um pacote salarial para a mesma combinação de cargo, nível e data de vigência."""
        query = "SELECT ID_Salarios FROM salarios WHERE ID_Cargos = %s AND ID_Niveis = %s AND Data_Vigencia = %s"
        result = self.db.execute_query(query, (id_cargos, id_niveis, data_vigencia), fetch_results=True)
        return result[0] if result else None

    # ==================================================================================================================================
    # === MÉTODOS DO SUBMÓDULO: FÉRIAS =================================================================================================
    # ==================================================================================================================================

    def get_all_ferias(self, search_matricula=None, search_status=None, search_periodo_inicio=None, search_periodo_fim=None):
        """
        Retorna uma lista de todos os registros de férias, opcionalmente filtrada,
        incluindo informações do funcionário.
        """
        query = """
            SELECT
                f.ID_Ferias, f.Matricula_Funcionario, f.Periodo_Aquisitivo_Inicio, f.Periodo_Aquisitivo_Fim,
                f.Data_Inicio_Gozo, f.Data_Fim_Gozo, f.Dias_Gozo, f.Status_Ferias, f.Observacoes,
                func.Nome_Completo AS Nome_Funcionario, f.Data_Criacao, f.Data_Modificacao
            FROM ferias f
            LEFT JOIN funcionarios func ON f.Matricula_Funcionario = func.Matricula
            WHERE 1=1
        """
        params = []

        if search_matricula:
            query += " AND f.Matricula_Funcionario LIKE %s"
            params.append(f"%{search_matricula}%")
        if search_status:
            query += " AND f.Status_Ferias = %s"
            params.append(search_status)
        if search_periodo_inicio:
            query += " AND f.Periodo_Aquisitivo_Inicio >= %s"
            params.append(search_periodo_inicio)
        if search_periodo_fim:
            query += " AND f.Periodo_Aquisitivo_Fim <= %s"
            params.append(search_periodo_fim)
        
        query += " ORDER BY f.Periodo_Aquisitivo_Inicio DESC, func.Nome_Completo"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    def add_ferias(self, matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim, data_inicio_gozo, data_fim_gozo, dias_gozo, status_ferias, observacoes):
        """Adiciona um novo registro de férias ao banco de dados."""
        query = """
            INSERT INTO ferias (Matricula_Funcionario, Periodo_Aquisitivo_Inicio, Periodo_Aquisitivo_Fim, Data_Inicio_Gozo, Data_Fim_Gozo, Dias_Gozo, Status_Ferias, Observacoes, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim, data_inicio_gozo, data_fim_gozo, dias_gozo, status_ferias, observacoes)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_ferias_by_id(self, ferias_id):
        """Retorna os dados de um registro de férias pelo ID."""
        query = """
            SELECT
                f.ID_Ferias, f.Matricula_Funcionario, f.Periodo_Aquisitivo_Inicio, f.Periodo_Aquisitivo_Fim,
                f.Data_Inicio_Gozo, f.Data_Fim_Gozo, f.Dias_Gozo, f.Status_Ferias, f.Observacoes,
                func.Nome_Completo AS Nome_Funcionario, f.Data_Criacao, f.Data_Modificacao
            FROM ferias f
            LEFT JOIN funcionarios func ON f.Matricula_Funcionario = func.Matricula
            WHERE f.ID_Ferias = %s
        """
        result = self.db.execute_query(query, (ferias_id,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_ferias(self, ferias_id, matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim, data_inicio_gozo, data_fim_gozo, dias_gozo, status_ferias, observacoes):
        """Atualiza os dados de um registro de férias existente."""
        query = """
            UPDATE ferias
            SET
                Matricula_Funcionario = %s, Periodo_Aquisitivo_Inicio = %s, Periodo_Aquisitivo_Fim = %s,
                Data_Inicio_Gozo = %s, Data_Fim_Gozo = %s, Dias_Gozo = %s, Status_Ferias = %s,
                Observacoes = %s, Data_Modificacao = NOW()
            WHERE ID_Ferias = %s
        """
        params = (matricula_funcionario, periodo_aquisitivo_inicio, periodo_aquisitivo_fim, data_inicio_gozo, data_fim_gozo, dias_gozo, status_ferias, observacoes, ferias_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_ferias(self, ferias_id):
        """Exclui um registro de férias do banco de dados."""
        query = "DELETE FROM ferias WHERE ID_Ferias = %s"
        return self.db.execute_query(query, (ferias_id,), fetch_results=False)
    
    # ==================================================================================================================================
    # === MÉTODOS DO SUBMÓDULO: DEPENDENTES ============================================================================================
    # ==================================================================================================================================

    def get_all_dependentes(self, search_matricula=None, search_nome=None, search_parentesco=None):
        """
        Retorna uma lista de todos os dependentes, opcionalmente filtrada,
        incluindo informações do funcionário.
        """
        query = """
            SELECT
                d.ID_Dependente, d.Matricula_Funcionario, d.Nome_Completo, d.Parentesco, d.Data_Nascimento,
                d.Cpf, d.Contato_Emergencia, d.Telefone_Emergencia, d.Observacoes,
                func.Nome_Completo AS Nome_Funcionario, d.Data_Criacao, d.Data_Modificacao
            FROM dependentes d
            LEFT JOIN funcionarios func ON d.Matricula_Funcionario = func.Matricula
            WHERE 1=1
        """
        params = []

        if search_matricula:
            query += " AND d.Matricula_Funcionario LIKE %s"
            params.append(f"%{search_matricula}%")
        if search_nome:
            query += " AND d.Nome_Completo LIKE %s"
            params.append(f"%{search_nome}%")
        if search_parentesco:
            query += " AND d.Parentesco = %s"
            params.append(search_parentesco)
        
        query += " ORDER BY func.Nome_Completo, d.Nome_Completo"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    def add_dependente(self, matricula_funcionario, nome_completo, parentesco, data_nascimento, cpf, contato_emergencia, telefone_emergencia, observacoes):
        """Adiciona um novo dependente ao banco de dados."""
        query = """
            INSERT INTO dependentes (Matricula_Funcionario, Nome_Completo, Parentesco, Data_Nascimento, Cpf, Contato_Emergencia, Telefone_Emergencia, Observacoes, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (matricula_funcionario, nome_completo, parentesco, data_nascimento, cpf, contato_emergencia, telefone_emergencia, observacoes)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_dependente_by_id(self, dependente_id):
        """Retorna os dados de um dependente pelo ID."""
        query = """
            SELECT
                d.ID_Dependente, d.Matricula_Funcionario, d.Nome_Completo, d.Parentesco, d.Data_Nascimento,
                d.Cpf, d.Contato_Emergencia, d.Telefone_Emergencia, d.Observacoes,
                func.Nome_Completo AS Nome_Funcionario, d.Data_Criacao, d.Data_Modificacao
            FROM dependentes d
            LEFT JOIN funcionarios func ON d.Matricula_Funcionario = func.Matricula
            WHERE d.ID_Dependente = %s
        """
        result = self.db.execute_query(query, (dependente_id,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_dependente(self, dependente_id, matricula_funcionario, nome_completo, parentesco, data_nascimento, cpf, contato_emergencia, telefone_emergencia, observacoes):
        """Atualiza os dados de um dependente existente."""
        query = """
            UPDATE dependentes
            SET
                Matricula_Funcionario = %s, Nome_Completo = %s, Parentesco = %s, Data_Nascimento = %s,
                Cpf = %s, Contato_Emergencia = %s, Telefone_Emergencia = %s, Observacoes = %s,
                Data_Modificacao = NOW()
            WHERE ID_Dependente = %s
        """
        params = (matricula_funcionario, nome_completo, parentesco, data_nascimento, cpf, contato_emergencia, telefone_emergencia, observacoes, dependente_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_dependente(self, dependente_id):
        """Exclui um dependente do banco de dados."""
        query = "DELETE FROM dependentes WHERE ID_Dependente = %s"
        return self.db.execute_query(query, (dependente_id,), fetch_results=False)

    def get_dependente_by_cpf(self, cpf, exclude_id=None):
        """Verifica se um dependente com o dado CPF já existe (para CPF único)."""
        query = "SELECT ID_Dependente FROM dependentes WHERE Cpf = %s"
        params = [cpf]
        if exclude_id:
            query += " AND ID_Dependente != %s"
            params.append(exclude_id)
        result = self.db.execute_query(query, tuple(params), fetch_results=True)
        return result[0] if result else None

    # ==================================================================================================================================
    # === MÉTODOS PARA DASHBOARD E RELATÓRIOS (MÓDULO PESSOAL) =========================================================================
    # ==================================================================================================================================

    def get_funcionario_status_counts(self):
        """Retorna a contagem de funcionários por status."""
        query = "SELECT Status, COUNT(*) AS Total FROM funcionarios GROUP BY Status"
        results = self.db.execute_query(query, fetch_results=True)
        return {item['Status']: item['Total'] for item in results} if results else {}

    def get_funcionarios_by_cargo(self):
        """Retorna a contagem de funcionários por cargo."""
        query = """
            SELECT c.Nome_Cargo, COUNT(f.Matricula) AS Total
            FROM funcionarios f
            JOIN cargos c ON f.ID_Cargos = c.ID_Cargos
            GROUP BY c.Nome_Cargo
            ORDER BY Total DESC
        """
        results = self.db.execute_query(query, fetch_results=True)
        return results if results else []

    def get_funcionarios_by_nivel(self):
        """Retorna a contagem de funcionários por nível."""
        query = """
            SELECT n.Nome_Nivel, COUNT(f.Matricula) AS Total
            FROM funcionarios f
            JOIN niveis n ON f.ID_Niveis = n.ID_Niveis
            GROUP BY n.Nome_Nivel
            ORDER BY Total DESC
        """
        results = self.db.execute_query(query, fetch_results=True)
        return results if results else []

    def get_proximas_ferias(self, dias_antecedencia=60):
        """Retorna uma lista de funcionários com férias programadas para os próximos dias_antecedencia."""
        hoje = date.today()
        data_limite = hoje + timedelta(days=dias_antecedencia)
        query = """
            SELECT
                f.Matricula, f.Nome_Completo,
                fe.Data_Inicio_Gozo, fe.Data_Fim_Gozo, fe.Dias_Gozo, fe.Status_Ferias
            FROM ferias fe
            JOIN funcionarios f ON fe.Matricula_Funcionario = f.Matricula
            WHERE fe.Data_Inicio_Gozo BETWEEN %s AND %s
            ORDER BY fe.Data_Inicio_Gozo ASC
        """
        params = (hoje, data_limite)
        results = self.db.execute_query(query, params=params, fetch_results=True)
        return results if results else []
    
    def get_aniversariantes_do_mes(self, mes=None):
        """
        Retorna uma lista de funcionários que fazem aniversário no mês especificado.
        Se 'mes' for None, usa o mês atual.
        """
        if mes is None:
            mes = date.today().month

        query = """
            SELECT
                fd.Matricula_Funcionario AS Matricula,
                f.Nome_Completo,
                fd.Data_Nascimento,
                c.Nome_Cargo,
                fd.Naturalidade -- Adicionado naturalidade ao retorno
            FROM
                funcionarios_documentos fd
            JOIN
                funcionarios f ON fd.Matricula_Funcionario = f.Matricula
            LEFT JOIN
                cargos c ON f.ID_Cargos = c.ID_Cargos
            WHERE
                fd.Data_Nascimento IS NOT NULL AND -- Garante que a data de nascimento existe
                MONTH(fd.Data_Nascimento) = %s AND
                f.Status = 'Ativo'
            ORDER BY
                DAY(fd.Data_Nascimento), f.Nome_Completo
        """
        results = self.db.execute_query(query, (mes,), fetch_results=True)
        
        if results:
            return [self._format_date_fields(item) for item in results]
        return []