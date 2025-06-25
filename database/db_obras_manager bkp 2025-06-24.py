# database/db_obras_manager.py
from datetime import datetime, date
import mysql.connector

class ObrasManager:
    def __init__(self, db_manager_instance):
        """
        Inicializa o ObrasManager com uma instância do seu DatabaseManager.
        Args:
            db_manager_instance: Uma instância da sua classe DatabaseManager (do db_base.py).
        """
        self.db = db_manager_instance

    def get_all_obras(self, search_numero=None, search_nome=None, search_status=None, search_cliente_id=None):
        """
        Retorna uma lista de todas as obras, opcionalmente filtrada.
        Args:
            search_numero (str, optional): Número da obra para filtrar.
            search_nome (str, optional): Nome (ou parte do nome) da obra para filtrar.
            search_status (str, optional): Status da obra para filtrar.
            search_cliente_id (int, optional): ID do Cliente para filtrar as obras.
        Returns:
            list: Uma lista de dicionários, onde cada dicionário representa uma obra.
        """
        query = """
            SELECT
                o.ID_Obras,
                o.Numero_Obra,
                o.Nome_Obra,
                o.Endereco_Obra,
                o.Status_Obra,
                o.Data_Inicio_Prevista,
                o.Data_Fim_Prevista,
                o.Valor_Obra,
                o.Valor_Aditivo_Total,
                c.Numero_Contrato,
                cl.Nome_Cliente
            FROM
                obras o
            LEFT JOIN
                contratos c ON o.ID_Contratos = c.ID_Contratos
            LEFT JOIN
                clientes cl ON c.ID_Clientes = cl.ID_Clientes
            WHERE 1=1
        """
        params = []

        if search_numero:
            query += " AND o.Numero_Obra LIKE %s"
            params.append(f"%{search_numero}%")
        if search_nome:
            query += " AND o.Nome_Obra LIKE %s"
            params.append(f"%{search_nome}%")
        if search_status:
            query += " AND o.Status_Obra = %s"
            params.append(search_status)
        if search_cliente_id:
            query += " AND cl.ID_Clientes = %s"
            params.append(search_cliente_id)
        
        query += " ORDER BY o.Nome_Obra" # Adiciona ordenação

        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def add_obra(self, id_contratos, numero_obra, nome_obra, endereco_obra, escopo_obra, valor_obra, valor_aditivo_total, status_obra, data_inicio_prevista, data_fim_prevista):
        """
        Adiciona uma nova obra ao banco de dados.
        Args:
            id_contratos (int): ID do contrato associado à obra.
            numero_obra (str): Número único da obra.
            nome_obra (str): Nome da obra.
            endereco_obra (str): Endereço da obra.
            escopo_obra (str): Descrição do escopo da obra.
            valor_obra (decimal): Valor total da obra.
            valor_aditivo_total (decimal): Valor total de aditivos (pode ser 0.00).
            status_obra (str): Status atual da obra.
            data_inicio_prevista (date): Data de início prevista.
            data_fim_prevista (date): Data de fim prevista.
        Returns:
            bool: True se a obra foi adicionada com sucesso, False caso contrário.
        """
        query = """
            INSERT INTO obras (ID_Contratos, Numero_Obra, Nome_Obra, Endereco_Obra, Escopo_Obra, Valor_Obra, Valor_Aditivo_Total, Status_Obra, Data_Inicio_Prevista, Data_Fim_Prevista, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (id_contratos, numero_obra, nome_obra, endereco_obra, escopo_obra, valor_obra, valor_aditivo_total, status_obra, data_inicio_prevista, data_fim_prevista)
        
        return self.db.execute_query(query, params, fetch_results=False)

    def get_obra_by_id(self, obra_id):
        """
        Retorna os dados de uma obra pelo ID.
        """
        query = """
            SELECT
                o.ID_Obras,
                o.Numero_Obra,
                o.Nome_Obra,
                o.Endereco_Obra,
                o.Escopo_Obra,
                o.Valor_Obra,
                o.Valor_Aditivo_Total,
                o.Status_Obra,
                o.Data_Inicio_Prevista,
                o.Data_Fim_Prevista,
                o.ID_Contratos,
                c.Numero_Contrato,
                cl.Nome_Cliente
            FROM
                obras o
            LEFT JOIN
                contratos c ON o.ID_Contratos = c.ID_Contratos
            LEFT JOIN
                clientes cl ON c.ID_Clientes = cl.ID_Clientes
            WHERE o.ID_Obras = %s
        """
        result = self.db.execute_query(query, (obra_id,), fetch_results=True)
        return result[0] if result else None

    def update_obra(self, obra_id, id_contratos, numero_obra, nome_obra, endereco_obra, escopo_obra, valor_obra, valor_aditivo_total, status_obra, data_inicio_prevista, data_fim_prevista):
        """
        Atualiza os dados de uma obra existente.
        """
        query = """
            UPDATE obras
            SET
                ID_Contratos = %s,
                Numero_Obra = %s,
                Nome_Obra = %s,
                Endereco_Obra = %s,
                Escopo_Obra = %s,
                Valor_Obra = %s,
                Valor_Aditivo_Total = %s,
                Status_Obra = %s,
                Data_Inicio_Prevista = %s,
                Data_Fim_Prevista = %s,
                Data_Modificacao = NOW()
            WHERE ID_Obras = %s
        """
        params = (id_contratos, numero_obra, nome_obra, endereco_obra, escopo_obra, valor_obra, valor_aditivo_total, status_obra, data_inicio_prevista, data_fim_prevista, obra_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_obra(self, obra_id):
        """
        Exclui uma obra do banco de dados.
        """
        query = "DELETE FROM obras WHERE ID_Obras = %s"
        return self.db.execute_query(query, (obra_id,), fetch_results=False)

    def get_all_contratos_for_dropdown(self):
        """
        Retorna uma lista de contratos para preencher dropdowns, incluindo Nome_Cliente.
        """
        query = """
            SELECT
                c.ID_Contratos,
                c.Numero_Contrato,
                cl.Nome_Cliente
            FROM
                contratos c
            JOIN
                clientes cl ON c.ID_Clientes = cl.ID_Clientes
            ORDER BY c.Numero_Contrato
        """
        return self.db.execute_query(query, fetch_results=True)

    def get_obra_by_numero(self, numero_obra):
        """
        Verifica se uma obra com o dado número já existe.
        """
        query = "SELECT ID_Obras FROM obras WHERE Numero_Obra = %s"
        result = self.db.execute_query(query, (numero_obra,), fetch_results=True)
        return result[0] if result else None
    
    # MÉTODOS PARA SUBMÓDULO CLIENTES DO MÓDULO OBRAS    
    
    def get_all_clientes(self, search_nome=None, search_cnpj=None):
        """
        Retorna uma lista de todos os clientes, opcionalmente filtrada.
        """
        query = """
            SELECT
                ID_Clientes,
                Nome_Cliente,
                CNPJ_Cliente,
                Razao_Social_Cliente,
                Endereco_Cliente,
                Telefone_Cliente,
                Email_Cliente,
                Contato_Principal_Nome,
                Data_Criacao,
                Data_Modificacao
            FROM
                clientes
            WHERE 1=1
        """
        params = []

        if search_nome:
            query += " AND Nome_Cliente LIKE %s"
            params.append(f"%{search_nome}%")
        if search_cnpj:
            query += " AND CNPJ_Cliente LIKE %s"
            params.append(f"%{search_cnpj}%")
        
        query += " ORDER BY Nome_Cliente"

        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def add_cliente(self, nome_cliente, cnpj_cliente, razao_social_cliente, endereco_cliente, telefone_cliente, email_cliente, contato_principal_nome):
        """
        Adiciona um novo cliente ao banco de dados.
        """
        query = """
            INSERT INTO clientes (Nome_Cliente, CNPJ_Cliente, Razao_Social_Cliente, Endereco_Cliente, Telefone_Cliente, Email_Cliente, Contato_Principal_Nome, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (nome_cliente, cnpj_cliente, razao_social_cliente, endereco_cliente, telefone_cliente, email_cliente, contato_principal_nome)
        
        return self.db.execute_query(query, params, fetch_results=False)

    def get_cliente_by_id(self, cliente_id):
        """
        Retorna os dados de um cliente pelo ID.
        """
        query = """
            SELECT
                ID_Clientes,
                Nome_Cliente,
                CNPJ_Cliente,
                Razao_Social_Cliente,
                Endereco_Cliente,
                Telefone_Cliente,
                Email_Cliente,
                Contato_Principal_Nome,
                Data_Criacao,
                Data_Modificacao
            FROM
                clientes
            WHERE ID_Clientes = %s
        """
        result = self.db.execute_query(query, (cliente_id,), fetch_results=True)
        return result[0] if result else None

    def update_cliente(self, cliente_id, nome_cliente, cnpj_cliente, razao_social_cliente, endereco_cliente, telefone_cliente, email_cliente, contato_principal_nome):
        """
        Atualiza os dados de um cliente existente.
        """
        query = """
            UPDATE clientes
            SET
                Nome_Cliente = %s,
                CNPJ_Cliente = %s,
                Razao_Social_Cliente = %s,
                Endereco_Cliente = %s,
                Telefone_Cliente = %s,
                Email_Cliente = %s,
                Contato_Principal_Nome = %s,
                Data_Modificacao = NOW()
            WHERE ID_Clientes = %s
        """
        params = (nome_cliente, cnpj_cliente, razao_social_cliente, endereco_cliente, telefone_cliente, email_cliente, contato_principal_nome, cliente_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_cliente(self, cliente_id):
        """
        Exclui um cliente do banco de dados.
        """
        query = "DELETE FROM clientes WHERE ID_Clientes = %s"
        return self.db.execute_query(query, (cliente_id,), fetch_results=False)

    def get_cliente_by_cnpj(self, cnpj_cliente):
        """
        Verifica se um cliente com o dado CNPJ já existe.
        """
        query = "SELECT ID_Clientes FROM clientes WHERE CNPJ_Cliente = %s"
        result = self.db.execute_query(query, (cnpj_cliente,), fetch_results=True)
        return result[0] if result else None
    
    # MÉTODOS PARA SUBMÓDULO CONTRATOS DO MÓDULO OBRAS
    
    # database/db_obras_manager.py (Adicione estes métodos dentro da classe ObrasManager)

    def get_all_contratos(self, search_numero=None, search_cliente_id=None, search_status=None):
        """
        Retorna uma lista de todos os contratos, opcionalmente filtrada,
        incluindo informações do cliente associado.
        """
        query = """
            SELECT
                c.ID_Contratos,
                c.Numero_Contrato,
                c.Valor_Contrato,
                c.Data_Assinatura,
                c.Data_Ordem_Inicio,
                c.Prazo_Contrato_Dias,
                c.Data_Termino_Previsto,
                c.Status_Contrato,
                c.Observacoes,
                cl.Nome_Cliente,
                cl.ID_Clientes,
                c.Data_Criacao,
                c.Data_Modificacao
            FROM
                contratos c
            LEFT JOIN
                clientes cl ON c.ID_Clientes = cl.ID_Clientes
            WHERE 1=1
        """
        params = []

        if search_numero:
            query += " AND c.Numero_Contrato LIKE %s"
            params.append(f"%{search_numero}%")
        if search_cliente_id:
            query += " AND c.ID_Clientes = %s"
            params.append(search_cliente_id)
        if search_status:
            query += " AND c.Status_Contrato = %s"
            params.append(search_status)
        
        query += " ORDER BY c.Numero_Contrato"

        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def add_contrato(self, id_clientes, numero_contrato, valor_contrato, data_assinatura, data_ordem_inicio, prazo_contrato_dias, data_termino_previsto, status_contrato, observacoes):
        """
        Adiciona um novo contrato ao banco de dados.
        """
        query = """
            INSERT INTO contratos (ID_Clientes, Numero_Contrato, Valor_Contrato, Data_Assinatura, Data_Ordem_Inicio, Prazo_Contrato_Dias, Data_Termino_Previsto, Status_Contrato, Observacoes, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (id_clientes, numero_contrato, valor_contrato, data_assinatura, data_ordem_inicio, prazo_contrato_dias, data_termino_previsto, status_contrato, observacoes)
        
        return self.db.execute_query(query, params, fetch_results=False)

    def get_contrato_by_id(self, contrato_id):
        """
        Retorna os dados de um contrato pelo ID.
        """
        query = """
            SELECT
                c.ID_Contratos,
                c.ID_Clientes,
                c.Numero_Contrato,
                c.Valor_Contrato,
                c.Data_Assinatura,
                c.Data_Ordem_Inicio,
                c.Prazo_Contrato_Dias,
                c.Data_Termino_Previsto,
                c.Status_Contrato,
                c.Observacoes,
                cl.Nome_Cliente,
                c.Data_Criacao,
                c.Data_Modificacao
            FROM
                contratos c
            LEFT JOIN
                clientes cl ON c.ID_Clientes = cl.ID_Clientes
            WHERE c.ID_Contratos = %s
        """
        result = self.db.execute_query(query, (contrato_id,), fetch_results=True)
        return result[0] if result else None

    def update_contrato(self, contrato_id, id_clientes, numero_contrato, valor_contrato, data_assinatura, data_ordem_inicio, prazo_contrato_dias, data_termino_previsto, status_contrato, observacoes):
        """
        Atualiza os dados de um contrato existente.
        """
        query = """
            UPDATE contratos
            SET
                ID_Clientes = %s,
                Numero_Contrato = %s,
                Valor_Contrato = %s,
                Data_Assinatura = %s,
                Data_Ordem_Inicio = %s,
                Prazo_Contrato_Dias = %s,
                Data_Termino_Previsto = %s,
                Status_Contrato = %s,
                Observacoes = %s,
                Data_Modificacao = NOW()
            WHERE ID_Contratos = %s
        """
        params = (id_clientes, numero_contrato, valor_contrato, data_assinatura, data_ordem_inicio, prazo_contrato_dias, data_termino_previsto, status_contrato, observacoes, contrato_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_contrato(self, contrato_id):
        """
        Exclui um contrato do banco de dados.
        """
        query = "DELETE FROM contratos WHERE ID_Contratos = %s"
        return self.db.execute_query(query, (contrato_id,), fetch_results=False)

    def get_contrato_by_numero(self, numero_contrato):
        """
        Verifica se um contrato com o dado número já existe.
        """
        query = "SELECT ID_Contratos FROM contratos WHERE Numero_Contrato = %s"
        result = self.db.execute_query(query, (numero_contrato,), fetch_results=True)
        return result[0] if result else None

    # MÉTODOS PARA SUBMÓDULO ARTs DO MÓDULO OBRAS - 2025-06-24 MENDES / GEMINI
    # database/db_obras_manager.py (Adicione estes métodos dentro da classe ObrasManager)

    def get_all_arts(self, search_numero=None, search_obra_id=None, search_status=None):
        """
        Retorna uma lista de todas as ARTs, opcionalmente filtrada,
        incluindo informações da obra associada.
        """
        query = """
            SELECT
                a.ID_Arts,
                a.ID_Obras,
                a.Numero_Art,
                a.Data_Pagamento,
                a.Valor_Pagamento,
                a.Status_Art,
                o.Numero_Obra,
                o.Nome_Obra,
                a.Data_Criacao,
                a.Data_Modificacao
            FROM
                arts a
            LEFT JOIN
                obras o ON a.ID_Obras = o.ID_Obras
            WHERE 1=1
        """
        params = []

        if search_numero:
            query += " AND a.Numero_Art LIKE %s"
            params.append(f"%{search_numero}%")
        if search_obra_id:
            query += " AND a.ID_Obras = %s"
            params.append(search_obra_id)
        if search_status:
            query += " AND a.Status_Art = %s"
            params.append(search_status)
        
        query += " ORDER BY a.Numero_Art"

        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def add_art(self, id_obras, numero_art, data_pagamento, valor_pagamento, status_art):
        """
        Adiciona uma nova ART ao banco de dados.
        """
        query = """
            INSERT INTO arts (ID_Obras, Numero_Art, Data_Pagamento, Valor_Pagamento, Status_Art, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (id_obras, numero_art, data_pagamento, valor_pagamento, status_art)
        
        return self.db.execute_query(query, params, fetch_results=False)

    def get_art_by_id(self, art_id):
        """
        Retorna os dados de uma ART pelo ID.
        """
        query = """
            SELECT
                a.ID_Arts,
                a.ID_Obras,
                a.Numero_Art,
                a.Data_Pagamento,
                a.Valor_Pagamento,
                a.Status_Art,
                o.Numero_Obra,
                o.Nome_Obra,
                a.Data_Criacao,
                a.Data_Modificacao
            FROM
                arts a
            LEFT JOIN
                obras o ON a.ID_Obras = o.ID_Obras
            WHERE a.ID_Arts = %s
        """
        result = self.db.execute_query(query, (art_id,), fetch_results=True)
        return result[0] if result else None

    def update_art(self, art_id, id_obras, numero_art, data_pagamento, valor_pagamento, status_art):
        """
        Atualiza os dados de uma ART existente.
        """
        query = """
            UPDATE arts
            SET
                ID_Obras = %s,
                Numero_Art = %s,
                Data_Pagamento = %s,
                Valor_Pagamento = %s,
                Status_Art = %s,
                Data_Modificacao = NOW()
            WHERE ID_Arts = %s
        """
        params = (id_obras, numero_art, data_pagamento, valor_pagamento, status_art, art_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_art(self, art_id):
        """
        Exclui uma ART do banco de dados.
        """
        query = "DELETE FROM arts WHERE ID_Arts = %s"
        return self.db.execute_query(query, (art_id,), fetch_results=False)

    def get_art_by_numero(self, numero_art):
        """
        Verifica se uma ART com o dado número já existe.
        """
        query = "SELECT ID_Arts FROM arts WHERE Numero_Art = %s"
        result = self.db.execute_query(query, (numero_art,), fetch_results=True)
        return result[0] if result else None

    def get_all_obras_for_dropdown(self):
        """
        Retorna uma lista de obras para preencher dropdowns.
        """
        query = """
            SELECT
                ID_Obras,
                Numero_Obra,
                Nome_Obra
            FROM
                obras
            ORDER BY Nome_Obra
        """
        return self.db.execute_query(query, fetch_results=True)
    
    # MÉTODOS PARA SUBMÓDULO MEDIÇÕES DO MÓDULO OBRAS - 2025-06-24 MENDES / GEMINI
    # database/db_obras_manager.py (Adicione estes métodos dentro da classe ObrasManager)

    def get_all_medicoes(self, search_numero_medicao=None, search_obra_id=None, search_status=None):
        """
        Retorna uma lista de todas as medições, opcionalmente filtrada,
        incluindo informações da obra associada.
        """
        query = """
            SELECT
                m.ID_Medicoes,
                m.ID_Obras,
                m.Numero_Medicao,
                m.Valor_Medicao,
                m.Data_Medicao,
                m.Mes_Referencia,
                m.Data_Aprovacao,
                m.Status_Medicao,
                m.Observacao_Medicao,
                o.Numero_Obra,
                o.Nome_Obra,
                m.Data_Criacao,
                m.Data_Modificacao
            FROM
                medicoes m
            LEFT JOIN
                obras o ON m.ID_Obras = o.ID_Obras
            WHERE 1=1
        """
        params = []

        if search_numero_medicao:
            # Busca exata ou por número completo, dependendo da necessidade.
            # Se for buscar por parte, use LIKE %s.
            query += " AND m.Numero_Medicao = %s"
            params.append(search_numero_medicao)
        if search_obra_id:
            query += " AND m.ID_Obras = %s"
            params.append(search_obra_id)
        if search_status:
            query += " AND m.Status_Medicao = %s"
            params.append(search_status)
        
        query += " ORDER BY o.Numero_Obra, m.Numero_Medicao"

        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def add_medicao(self, id_obras, numero_medicao, valor_medicao, data_medicao, mes_referencia, data_aprovacao, status_medicao, observacao_medicao):
        """
        Adiciona uma nova medição ao banco de dados.
        """
        query = """
            INSERT INTO medicoes (ID_Obras, Numero_Medicao, Valor_Medicao, Data_Medicao, Mes_Referencia, Data_Aprovacao, Status_Medicao, Observacao_Medicao, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (id_obras, numero_medicao, valor_medicao, data_medicao, mes_referencia, data_aprovacao, status_medicao, observacao_medicao)
        
        return self.db.execute_query(query, params, fetch_results=False)

    def get_medicao_by_id(self, medicao_id):
        """
        Retorna os dados de uma medição pelo ID.
        """
        query = """
            SELECT
                m.ID_Medicoes,
                m.ID_Obras,
                m.Numero_Medicao,
                m.Valor_Medicao,
                m.Data_Medicao,
                m.Mes_Referencia,
                m.Data_Aprovacao,
                m.Status_Medicao,
                m.Observacao_Medicao,
                o.Numero_Obra,
                o.Nome_Obra,
                m.Data_Criacao,
                m.Data_Modificacao
            FROM
                medicoes m
            LEFT JOIN
                obras o ON m.ID_Obras = o.ID_Obras
            WHERE m.ID_Medicoes = %s
        """
        result = self.db.execute_query(query, (medicao_id,), fetch_results=True)
        return result[0] if result else None

    def update_medicao(self, medicao_id, id_obras, numero_medicao, valor_medicao, data_medicao, mes_referencia, data_aprovacao, status_medicao, observacao_medicao):
        """
        Atualiza os dados de uma medição existente.
        """
        query = """
            UPDATE medicoes
            SET
                ID_Obras = %s,
                Numero_Medicao = %s,
                Valor_Medicao = %s,
                Data_Medicao = %s,
                Mes_Referencia = %s,
                Data_Aprovacao = %s,
                Status_Medicao = %s,
                Observacao_Medicao = %s,
                Data_Modificacao = NOW()
            WHERE ID_Medicoes = %s
        """
        params = (id_obras, numero_medicao, valor_medicao, data_medicao, mes_referencia, data_aprovacao, status_medicao, observacao_medicao, medicao_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_medicao(self, medicao_id):
        """
        Exclui uma medição do banco de dados.
        """
        query = "DELETE FROM medicoes WHERE ID_Medicoes = %s"
        return self.db.execute_query(query, (medicao_id,), fetch_results=False)

    def get_medicao_by_obra_numero(self, id_obras, numero_medicao):
        """
        Verifica se uma medição com o dado número já existe para uma obra específica.
        (Lembrando da UNIQUE (ID_Obras, Numero_Medicao))
        """
        query = "SELECT ID_Medicoes FROM medicoes WHERE ID_Obras = %s AND Numero_Medicao = %s"
        result = self.db.execute_query(query, (id_obras, numero_medicao), fetch_results=True)
        return result[0] if result else None

# MÉTODOS PARA SUBMÓDULO AVANÇO FÍSICO, DO MÓDULO OBRAS - 2025-06-24 MENDES / GEMINI
# database/db_obras_manager.py (Adicione estes métodos dentro da classe ObrasManager)

    def get_all_avancos_fisicos(self, search_obra_id=None, search_data_inicio=None, search_data_fim=None):
        """
        Retorna uma lista de todos os avanços físicos, opcionalmente filtrada,
        incluindo informações da obra associada.
        """
        query = """
            SELECT
                af.ID_Avancos_Fisicos,
                af.ID_Obras,
                af.Percentual_Avanco_Fisico,
                af.Data_Avanco,
                o.Numero_Obra,
                o.Nome_Obra,
                af.Data_Criacao,
                af.Data_Modificacao
            FROM
                avancos_fisicos af
            LEFT JOIN
                obras o ON af.ID_Obras = o.ID_Obras
            WHERE 1=1
        """
        params = []

        if search_obra_id:
            query += " AND af.ID_Obras = %s"
            params.append(search_obra_id)
        if search_data_inicio:
            query += " AND af.Data_Avanco >= %s"
            params.append(search_data_inicio)
        if search_data_fim:
            query += " AND af.Data_Avanco <= %s"
            params.append(search_data_fim)
        
        query += " ORDER BY o.Nome_Obra, af.Data_Avanco DESC"

        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def add_avanco_fisico(self, id_obras, percentual_avanco_fisico, data_avanco):
        """
        Adiciona um novo registro de avanço físico ao banco de dados.
        """
        query = """
            INSERT INTO avancos_fisicos (ID_Obras, Percentual_Avanco_Fisico, Data_Avanco, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, NOW(), NOW())
        """
        params = (id_obras, percentual_avanco_fisico, data_avanco)
        
        return self.db.execute_query(query, params, fetch_results=False)

    def get_avanco_fisico_by_id(self, avanco_id):
        """
        Retorna os dados de um avanço físico pelo ID.
        """
        query = """
            SELECT
                af.ID_Avancos_Fisicos,
                af.ID_Obras,
                af.Percentual_Avanco_Fisico,
                af.Data_Avanco,
                o.Numero_Obra,
                o.Nome_Obra,
                af.Data_Criacao,
                af.Data_Modificacao
            FROM
                avancos_fisicos af
            LEFT JOIN
                obras o ON af.ID_Obras = o.ID_Obras
            WHERE af.ID_Avancos_Fisicos = %s
        """
        result = self.db.execute_query(query, (avanco_id,), fetch_results=True)
        return result[0] if result else None

    def update_avanco_fisico(self, avanco_id, id_obras, percentual_avanco_fisico, data_avanco):
        """
        Atualiza os dados de um avanço físico existente.
        """
        query = """
            UPDATE avancos_fisicos
            SET
                ID_Obras = %s,
                Percentual_Avanco_Fisico = %s,
                Data_Avanco = %s,
                Data_Modificacao = NOW()
            WHERE ID_Avancos_Fisicos = %s
        """
        params = (id_obras, percentual_avanco_fisico, data_avanco, avanco_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_avanco_fisico(self, avanco_id):
        """
        Exclui um avanço físico do banco de dados.
        """
        query = "DELETE FROM avancos_fisicos WHERE ID_Avancos_Fisicos = %s"
        return self.db.execute_query(query, (avanco_id,), fetch_results=False)

# MÉTODOS PARA SUBMÓDULO REIDIS, DO MÓDULO OBRAS - 2025-06-24 MENDES / GEMINI
# database/db_obras_manager.py (Substitua os métodos de REIDIs existentes por estes)

    def get_all_reidis(self, search_numero_portaria=None, search_numero_ato=None, search_obra_id=None, search_status=None):
        """
        Retorna uma lista de todos os REIDIs, opcionalmente filtrada,
        incluindo informações da obra associada.
        """
        query = """
            SELECT
                r.ID_Reidis,
                r.ID_Obras,
                r.Numero_Portaria,
                r.Numero_Ato_Declaratorio,
                r.Data_Aprovacao_Reidi,
                r.Data_Validade_Reidi,
                r.Status_Reidi,
                r.Observacoes_Reidi,
                o.Numero_Obra,
                o.Nome_Obra,
                r.Data_Criacao,
                r.Data_Modificacao
            FROM
                reidis r
            LEFT JOIN
                obras o ON r.ID_Obras = o.ID_Obras
            WHERE 1=1
        """
        params = []

        if search_numero_portaria:
            query += " AND r.Numero_Portaria LIKE %s"
            params.append(f"%{search_numero_portaria}%")
        if search_numero_ato:
            query += " AND r.Numero_Ato_Declaratorio LIKE %s"
            params.append(f"%{search_numero_ato}%")
        if search_obra_id:
            query += " AND r.ID_Obras = %s"
            params.append(search_obra_id)
        if search_status:
            query += " AND r.Status_Reidi = %s"
            params.append(search_status)
        
        query += " ORDER BY o.Numero_Obra, r.Numero_Portaria"

        return self.db.execute_query(query, tuple(params), fetch_results=True)

    def add_reidi(self, id_obras, numero_portaria, numero_ato_declaratorio, data_aprovacao_reidi, data_validade_reidi, status_reidi, observacoes_reidi):
        """
        Adiciona um novo registro de REIDI ao banco de dados com as novas colunas.
        """
        query = """
            INSERT INTO reidis (ID_Obras, Numero_Portaria, Numero_Ato_Declaratorio, Data_Aprovacao_Reidi, Data_Validade_Reidi, Status_Reidi, Observacoes_Reidi, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (id_obras, numero_portaria, numero_ato_declaratorio, data_aprovacao_reidi, data_validade_reidi, status_reidi, observacoes_reidi)
        
        return self.db.execute_query(query, params, fetch_results=False)

    def get_reidi_by_id(self, reidi_id):
        """
        Retorna os dados de um REIDI pelo ID com as novas colunas.
        """
        query = """
            SELECT
                r.ID_Reidis,
                r.ID_Obras,
                r.Numero_Portaria,
                r.Numero_Ato_Declaratorio,
                r.Data_Aprovacao_Reidi,
                r.Data_Validade_Reidi,
                r.Status_Reidi,
                r.Observacoes_Reidi,
                o.Numero_Obra,
                o.Nome_Obra,
                r.Data_Criacao,
                r.Data_Modificacao
            FROM
                reidis r
            LEFT JOIN
                obras o ON r.ID_Obras = o.ID_Obras
            WHERE r.ID_Reidis = %s
        """
        result = self.db.execute_query(query, (reidi_id,), fetch_results=True)
        return result[0] if result else None

    def update_reidi(self, reidi_id, id_obras, numero_portaria, numero_ato_declaratorio, data_aprovacao_reidi, data_validade_reidi, status_reidi, observacoes_reidi):
        """
        Atualiza os dados de um REIDI existente com as novas colunas.
        """
        query = """
            UPDATE reidis
            SET
                ID_Obras = %s,
                Numero_Portaria = %s,
                Numero_Ato_Declaratorio = %s,
                Data_Aprovacao_Reidi = %s,
                Data_Validade_Reidi = %s,
                Status_Reidi = %s,
                Observacoes_Reidi = %s,
                Data_Modificacao = NOW()
            WHERE ID_Reidis = %s
        """
        params = (id_obras, numero_portaria, numero_ato_declaratorio, data_aprovacao_reidi, data_validade_reidi, status_reidi, observacoes_reidi, reidi_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_reidi(self, reidi_id):
        """
        Exclui um REIDI do banco de dados.
        """
        query = "DELETE FROM reidis WHERE ID_Reidis = %s"
        return self.db.execute_query(query, (reidi_id,), fetch_results=False)

    def get_reidi_by_numero_portaria(self, numero_portaria):
        """
        Verifica se um REIDI com o dado Numero_Portaria já existe.
        """
        query = "SELECT ID_Reidis FROM reidis WHERE Numero_Portaria = %s"
        result = self.db.execute_query(query, (numero_portaria,), fetch_results=True)
        return result[0] if result else None

    def get_reidi_by_numero_ato_declaratorio(self, numero_ato_declaratorio):
        """
        Verifica se um REIDI com o dado Numero_Ato_Declaratorio já existe.
        """
        query = "SELECT ID_Reidis FROM reidis WHERE Numero_Ato_Declaratorio = %s"
        result = self.db.execute_query(query, (numero_ato_declaratorio,), fetch_results=True)
        return result[0] if result else None
    
# MÉTODOS PARA SUBMÓDULO SEGUROS, DO MÓDULO OBRAS - 2025-06-24 MENDES / GEMINI
# database/db_obras_manager.py (Adicione estes métodos dentro da classe ObrasManager)

    def _format_date_fields(self, item):
        """Função auxiliar para converter campos de data para objetos date se forem strings."""
        if item is None:
            return None
        
        # Lista dos campos de data específicos da tabela 'seguros'
        # Adicione aqui qualquer outro campo DATETIME/DATE que você queira garantir que seja um objeto date
        date_fields = [
            'Data_Inicio_Vigencia',
            'Data_Fim_Vigencia',
            'Data_Criacao',
            'Data_Modificacao'
        ]
        
        for key in date_fields:
            if key in item and isinstance(item[key], str):
                try:
                    # Tenta analisar como data (AAAA-MM-DD)
                    item[key] = datetime.strptime(item[key], '%Y-%m-%d').date()
                except ValueError:
                    # Se falhar, tenta analisar como datetime completo e pega a data
                    try:
                        item[key] = datetime.strptime(item[key], '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        # Se ainda assim falhar, deixa como está (string) ou loga um aviso
                        pass 
            elif key in item and isinstance(item[key], datetime):
                # Se já for um objeto datetime, converte para date para consistência
                item[key] = item[key].date()
        return item

    def get_all_seguros(self, search_numero_apolice=None, search_obra_id=None, search_status=None, search_tipo=None):
        """
        Retorna uma lista de todos os seguros, opcionalmente filtrada,
        incluindo informações da obra associada.
        Converte campos de data para objetos date.
        """
        query = """
            SELECT
                s.ID_Seguros,
                s.ID_Obras,
                s.Numero_Apolice,
                s.Seguradora,
                s.Tipo_Seguro,
                s.Valor_Segurado,
                s.Data_Inicio_Vigencia,
                s.Data_Fim_Vigencia,
                s.Status_Seguro,
                s.Observacoes_Seguro,
                o.Numero_Obra,
                o.Nome_Obra,
                s.Data_Criacao,
                s.Data_Modificacao
            FROM
                seguros s
            LEFT JOIN
                obras o ON s.ID_Obras = o.ID_Obras
            WHERE 1=1
        """
        params = []

        if search_numero_apolice:
            query += " AND s.Numero_Apolice LIKE %s"
            params.append(f"%{search_numero_apolice}%")
        if search_obra_id:
            query += " AND s.ID_Obras = %s"
            params.append(search_obra_id)
        if search_status:
            query += " AND s.Status_Seguro = %s"
            params.append(search_status)
        if search_tipo:
            query += " AND s.Tipo_Seguro = %s"
            params.append(search_tipo)
        
        query += " ORDER BY o.Numero_Obra, s.Numero_Apolice"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        
        # Aplica a formatação de data a cada item na lista de resultados
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    def add_seguro(self, id_obras, numero_apolice, seguradora, tipo_seguro, valor_segurado, data_inicio_vigencia, data_fim_vigencia, status_seguro, observacoes_seguro):
        """
        Adiciona um novo registro de seguro ao banco de dados.
        """
        query = """
            INSERT INTO seguros (ID_Obras, Numero_Apolice, Seguradora, Tipo_Seguro, Valor_Segurado, Data_Inicio_Vigencia, Data_Fim_Vigencia, Status_Seguro, Observacoes_Seguro, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (id_obras, numero_apolice, seguradora, tipo_seguro, valor_segurado, data_inicio_vigencia, data_fim_vigencia, status_seguro, observacoes_seguro)
        
        return self.db.execute_query(query, params, fetch_results=False)

    def get_seguro_by_id(self, seguro_id):
        """
        Retorna os dados de um seguro pelo ID.
        Converte campos de data para objetos date.
        """
        query = """
            SELECT
                s.ID_Seguros,
                s.ID_Obras,
                s.Numero_Apolice,
                s.Seguradora,
                s.Tipo_Seguro,
                s.Valor_Segurado,
                s.Data_Inicio_Vigencia,
                s.Data_Fim_Vigencia,
                s.Status_Seguro,
                s.Observacoes_Seguro,
                o.Numero_Obra,
                o.Nome_Obra,
                s.Data_Criacao,
                s.Data_Modificacao
            FROM
                seguros s
            LEFT JOIN
                obras o ON s.ID_Obras = o.ID_Obras
            WHERE s.ID_Seguros = %s
        """
        result = self.db.execute_query(query, (seguro_id,), fetch_results=True)
        
        if result:
            seguro = result[0]
            # Aplica a formatação de data ao único item de resultado
            return self._format_date_fields(seguro)
        return None

    def update_seguro(self, seguro_id, id_obras, numero_apolice, seguradora, tipo_seguro, valor_segurado, data_inicio_vigencia, data_fim_vigencia, status_seguro, observacoes_seguro):
        """
        Atualiza os dados de um seguro existente.
        """
        query = """
            UPDATE seguros
            SET
                ID_Obras = %s,
                Numero_Apolice = %s,
                Seguradora = %s,
                Tipo_Seguro = %s,
                Valor_Segurado = %s,
                Data_Inicio_Vigencia = %s,
                Data_Fim_Vigencia = %s,
                Status_Seguro = %s,
                Observacoes_Seguro = %s,
                Data_Modificacao = NOW()
            WHERE ID_Seguros = %s
        """
        params = (id_obras, numero_apolice, seguradora, tipo_seguro, valor_segurado, data_inicio_vigencia, data_fim_vigencia, status_seguro, observacoes_seguro, seguro_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_seguro(self, seguro_id):
        """
        Exclui um seguro do banco de dados.
        """
        query = "DELETE FROM seguros WHERE ID_Seguros = %s"
        return self.db.execute_query(query, (seguro_id,), fetch_results=False)

    def get_seguro_by_numero_apolice(self, numero_apolice):
        """
        Verifica se um seguro com o dado número de apólice já existe.
        """
        query = "SELECT ID_Seguros FROM seguros WHERE Numero_Apolice = %s"
        result = self.db.execute_query(query, (numero_apolice,), fetch_results=True)
        return result[0] if result else None