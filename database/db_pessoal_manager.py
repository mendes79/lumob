# database/db_pessoal_manager.py

import mysql.connector
from datetime import datetime, date

class PessoalManager:
    def __init__(self, db_connection):
        self.db = db_connection

    def _format_date_fields(self, item):
        """
        Função auxiliar para converter campos de data em dicionários de resultados
        para objetos date ou None.
        """
        if item is None:
            return None
        
        # Lista de campos de data/datetime que precisam de formatação para objeto date
        date_fields_to_format = [
            'Data_Criacao', 'Data_Modificacao', 
            'Data_Admissao', 
            'Data_Vigencia', 
            'Data_Emissao', 'Data_Vencimento', 'Data_Nascimento' 
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

    # --- Métodos de Funcionários ---
    def generate_next_matricula(self):
        """Gera a próxima matrícula sequencial baseada na última matrícula existente."""
        try:
            # Tenta encontrar a matrícula com o maior número
            query = "SELECT Matricula FROM funcionarios WHERE Matricula REGEXP '^MATR[0-9]+$' ORDER BY LENGTH(Matricula) DESC, Matricula DESC LIMIT 1"
            last_matricula_data = self.db.execute_query(query, fetch_results=True)
            
            if last_matricula_data and last_matricula_data[0]['Matricula']:
                last_matricula = last_matricula_data[0]['Matricula']
                # Extrai o número e incrementa
                num = int(last_matricula[4:]) + 1
                return f"MATR{num:03d}" # Formata para MATR001, MATR002, etc.
            return "MATR001" # Matrícula inicial se não houver nenhuma
        except Exception as e:
            print(f"Erro ao gerar próxima matrícula: {e}")
            return "MATR001" # Fallback em caso de erro

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

    def get_all_funcionarios_completo(self, search_matricula=None, search_nome=None, search_status=None, search_cargo_id=None):
        """
        Retorna uma lista de todos os funcionários com todos os dados associados (documentos, endereços, contatos)
        para fins de exportação ou relatórios detalhados.
        """
        # Esta é uma consulta complexa. Para simplicidade, vou buscar os dados principais
        # e depois buscar os detalhes em separado e combiná-los no Python.
        # Em um cenário de produção com muitos dados, seria mais eficiente com JOINs adequados ou Views no DB.
        
        main_funcionarios_query = """
            SELECT
                f.Matricula,
                f.Nome_Completo,
                f.Data_Admissao,
                c.Nome_Cargo,
                n.Nome_Nivel,
                f.Status,
                f.Data_Criacao,
                f.Data_Modificacao
            FROM
                funcionarios f
            LEFT JOIN cargos c ON f.ID_Cargos = c.ID_Cargos
            LEFT JOIN niveis n ON f.ID_Niveis = n.ID_Niveis
            WHERE 1=1
        """
        params = []
        if search_matricula:
            main_funcionarios_query += " AND f.Matricula LIKE %s"
            params.append(f"%{search_matricula}%")
        if search_nome:
            main_funcionarios_query += " AND f.Nome_Completo LIKE %s"
            params.append(f"%{search_nome}%")
        if search_status:
            main_funcionarios_query += " AND f.Status = %s"
            params.append(search_status)
        if search_cargo_id:
            main_funcionarios_query += " AND f.ID_Cargos = %s"
            params.append(search_cargo_id)
        main_funcionarios_query += " ORDER BY f.Nome_Completo"

        funcionarios_principais = self.db.execute_query(main_funcionarios_query, tuple(params), fetch_results=True)
        
        if not funcionarios_principais:
            return []

        # Converter datas para os principais
        funcionarios_principais_formatados = [self._format_date_fields(item) for item in funcionarios_principais]

        # Agora, buscar documentos, endereços e contatos para cada funcionário
        # E combinar os dados
        final_results = []
        for func in funcionarios_principais_formatados:
            matricula = func['Matricula']
            
            # Buscar documentos
            docs = self.get_funcionario_documentos_by_matricula(matricula)
            for doc in docs:
                if doc.get('Tipo_Documento') == 'RG':
                    func['Rg'] = doc.get('Numero_Documento')
                    func['Data_Nascimento'] = doc.get('Data_Nascimento')
                    func['Estado_Civil'] = doc.get('Estado_Civil')
                    func['Nacionalidade'] = doc.get('Nacionalidade')
                    func['Genero'] = doc.get('Genero')
                elif doc.get('Tipo_Documento') == 'CPF':
                    func['Cpf'] = doc.get('Numero_Documento')
                elif doc.get('Tipo_Documento') == 'CTPS':
                    func['Ctps_Numero'] = doc.get('Numero_Documento')
                    func['Ctps_Serie'] = doc.get('Ctps_Serie') # Se ainda existe
                elif doc.get('Tipo_Documento') == 'PIS/PASEP':
                    func['Pis_Pasep'] = doc.get('Numero_Documento')
                elif doc.get('Tipo_Documento') == 'CNH':
                    func['Cnh_Numero'] = doc.get('Numero_Documento')
                    func['Cnh_Categoria'] = doc.get('Cnh_Categoria') # Se ainda existe
                elif doc.get('Tipo_Documento') == 'Título de Eleitor':
                    func['Titulo_Eleitor_Numero'] = doc.get('Numero_Documento')
                    func['Titulo_Eleitor_Zona'] = doc.get('Titulo_Eleitor_Zona') # Se ainda existe
                    func['Titulo_Eleitor_Secao'] = doc.get('Titulo_Eleitor_Secao') # Se ainda existe

            # Buscar endereços (assumindo um principal residencial para o relatório)
            enderecos = self.get_funcionario_enderecos_by_matricula(matricula)
            if enderecos:
                res_endereco = next((end for end in enderecos if end.get('Tipo_Endereco') == 'Residencial'), None)
                if res_endereco:
                    func['Endereco_Residencial'] = f"{res_endereco.get('Logradouro')}, {res_endereco.get('Numero')}"
                    func['Numero_Endereco'] = res_endereco.get('Numero')
                    func['Complemento_Endereco'] = res_endereco.get('Complemento')
                    func['Bairro_Endereco'] = res_endereco.get('Bairro')
                    func['Cidade_Endereco'] = res_endereco.get('Cidade')
                    func['Estado_Endereco'] = res_endereco.get('Estado')
                    func['Cep_Endereco'] = res_endereco.get('Cep')
                else: # Se não houver residencial, pegar o primeiro que encontrar
                    first_endereco = enderecos[0]
                    func['Endereco_Residencial'] = f"{first_endereco.get('Logradouro')}, {first_endereco.get('Numero')}"
                    func['Numero_Endereco'] = first_endereco.get('Numero')
                    func['Complemento_Endereco'] = first_endereco.get('Complemento')
                    func['Bairro_Endereco'] = first_endereco.get('Bairro')
                    func['Cidade_Endereco'] = first_endereco.get('Cidade')
                    func['Estado_Endereco'] = first_endereco.get('Estado')
                    func['Cep_Endereco'] = first_endereco.get('Cep')

            # Buscar contatos (assumindo telefone principal e email pessoal para o relatório)
            contatos = self.get_funcionario_contatos_by_matricula(matricula)
            if contatos:
                tel_principal = next((cont for cont in contatos if cont.get('Tipo_Contato') == 'Telefone Principal'), None)
                if tel_principal:
                    func['Telefone_Principal'] = tel_principal.get('Valor_Contato')
                
                email_pessoal = next((cont for cont in contatos if cont.get('Tipo_Contato') == 'Email Pessoal'), None)
                if email_pessoal:
                    func['Email_Pessoal'] = email_pessoal.get('Valor_Contato')
            
            final_results.append(func)
        
        return final_results


    def add_funcionario(self, matricula, nome_completo, data_admissao, id_cargos, id_niveis, status):
        """Adiciona um novo funcionário."""
        query = """
            INSERT INTO funcionarios (Matricula, Nome_Completo, Data_Admissao, ID_Cargos, ID_Niveis, Status, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (matricula, nome_completo, data_admissao, id_cargos, id_niveis, status)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_funcionario_by_matricula(self, matricula):
        """Retorna os dados de um funcionário pela matrícula."""
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
            WHERE f.Matricula = %s
        """
        result = self.db.execute_query(query, (matricula,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_funcionario(self, old_matricula, new_matricula, nome_completo, data_admissao, id_cargos, id_niveis, status):
        """Atualiza os dados de um funcionário."""
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

    # --- Métodos de Documentos de Funcionários (NOVO) ---
    def add_funcionario_documentos(self, matricula, rg, cpf, data_nascimento, ctps_numero, ctps_serie, pis_pasep, cnh_numero, cnh_categoria, titulo_eleitor_numero, titulo_eleitor_zona, titulo_eleitor_secao, estado_civil, nacionalidade, genero):
        """Adiciona ou atualiza múltiplos documentos e dados pessoais para um funcionário."""
        # Esta função agrupa a inserção/atualização de vários tipos de documentos
        # e dados pessoais que na nova estrutura são tratados como documentos.
        # A lógica aqui será para criar ou atualizar se já existir.
        
        # RG
        if rg:
            self.update_or_insert_documento(matricula, 'RG', rg, None, None, None, None, estado_civil, nacionalidade, genero, data_nascimento) # data_nascimento é um campo de funcionario_documentos agora
        
        # CPF
        if cpf:
            self.update_or_insert_documento(matricula, 'CPF', cpf)
            
        # CTPS
        if ctps_numero:
            # Nota: ctps_serie não é um campo direto na nova tabela funcionarios_documentos para CTPS.
            # Se for crucial, pode ser concatenado com Numero_Documento ou ir para Observacoes.
            # Por enquanto, vou passá-lo como None.
            self.update_or_insert_documento(matricula, 'CTPS', ctps_numero, None, None, None, None, None, None, None)

        # PIS/PASEP
        if pis_pasep:
            self.update_or_insert_documento(matricula, 'PIS/PASEP', pis_pasep)

        # CNH
        if cnh_numero:
            # Nota: cnh_categoria não é um campo direto na nova tabela funcionarios_documentos para CNH.
            # Se for crucial, pode ser concatenado com Numero_Documento ou ir para Observacoes.
            self.update_or_insert_documento(matricula, 'CNH', cnh_numero, None, None, None, None, None, None, None, cnh_categoria) # CNH Categoria como observação?

        # Título de Eleitor
        if titulo_eleitor_numero:
            # Zona e Seção podem ir para observações ou em campos separados.
            # Por enquanto, vou passá-los como None.
            self.update_or_insert_documento(matricula, 'Título de Eleitor', titulo_eleitor_numero, None, None, None, None, None, None, None, None, titulo_eleitor_zona, titulo_eleitor_secao)
        
        # Data de Nascimento, Estado Civil, Nacionalidade, Gênero são específicos do RG (no contexto atual)
        # Se eles estiverem ligados ao RG, já são tratados acima.
        # Se forem campos independentes, você pode adicionar chamadas separadas.
        # A nova estrutura de `funcionarios_documentos` permite flexibilidade.
        # Para Estado Civil, Nacionalidade, Gênero, etc. que não são "documentos" de fato,
        # poderíamos ter uma tabela `funcionarios_dados_pessoais` no futuro.
        # Por enquanto, eles serão associados ao documento RG como tipo de dado pessoal.

    def update_or_add_funcionario_documentos(self, matricula, rg, cpf, data_nascimento, ctps_numero, ctps_serie, pis_pasep, cnh_numero, cnh_categoria, titulo_eleitor_numero, titulo_eleitor_zona, titulo_eleitor_secao, estado_civil, nacionalidade, genero):
        """
        Atualiza ou insere documentos e dados pessoais para um funcionário.
        Esta é uma lógica simplificada para a edição via formulário principal.
        """
        # RG - Data_Nascimento, Estado_Civil, Nacionalidade, Genero agora estão atrelados ao tipo 'RG'
        self._update_or_insert_single_documento(matricula, 'RG', rg, Data_Nascimento=data_nascimento, Estado_Civil=estado_civil, Nacionalidade=nacionalidade, Genero=genero)
        
        # CPF
        self._update_or_insert_single_documento(matricula, 'CPF', cpf)
        
        # CTPS (considerando serie na observacao por enquanto)
        if ctps_numero:
            self._update_or_insert_single_documento(matricula, 'CTPS', ctps_numero, Observacoes=f"Série: {ctps_serie}" if ctps_serie else None)

        # PIS/PASEP
        self._update_or_insert_single_documento(matricula, 'PIS/PASEP', pis_pasep)

        # CNH (considerando categoria na observacao por enquanto)
        if cnh_numero:
            self._update_or_insert_single_documento(matricula, 'CNH', cnh_numero, Observacoes=f"Categoria: {cnh_categoria}" if cnh_categoria else None)

        # Título de Eleitor (considerando zona e secao na observacao por enquanto)
        if titulo_eleitor_numero:
            obs = []
            if titulo_eleitor_zona: obs.append(f"Zona: {titulo_eleitor_zona}")
            if titulo_eleitor_secao: obs.append(f"Seção: {titulo_eleitor_secao}")
            self._update_or_insert_single_documento(matricula, 'Título de Eleitor', titulo_eleitor_numero, Observacoes=", ".join(obs) if obs else None)


    def _update_or_insert_single_documento(self, matricula, tipo_documento, numero_documento, Data_Emissao=None, Orgao_Emissor=None, Uf_Emissor=None, Data_Vencimento=None, Estado_Civil=None, Nacionalidade=None, Genero=None, Data_Nascimento=None, Observacoes=None):
        """
        Função interna auxiliar para atualizar ou inserir um único tipo de documento.
        Isso é necessário devido à estrutura de `funcionarios_documentos`.
        Ainda simplificado, apenas para os campos básicos do formulário de edição principal.
        """
        if not numero_documento: # Se o número do documento estiver vazio, remove o registro (se existir)
            existing_doc = self.db.execute_query("SELECT ID_Funcionario_Documento FROM funcionarios_documentos WHERE Matricula_Funcionario = %s AND Tipo_Documento = %s", (matricula, tipo_documento), fetch_results=True)
            if existing_doc:
                self.db.execute_query("DELETE FROM funcionarios_documentos WHERE ID_Funcionario_Documento = %s", (existing_doc[0]['ID_Funcionario_Documento'],), fetch_results=False)
            return

        # Tenta encontrar um documento existente do mesmo tipo para o funcionário
        existing_doc = self.db.execute_query("SELECT ID_Funcionario_Documento FROM funcionarios_documentos WHERE Matricula_Funcionario = %s AND Tipo_Documento = %s", (matricula, tipo_documento), fetch_results=True)

        # Campos adicionais para o tipo RG
        rg_extra_fields = ""
        rg_extra_params = []
        if tipo_documento == 'RG':
            rg_extra_fields += ", Data_Nascimento = %s, Estado_Civil = %s, Nacionalidade = %s, Genero = %s"
            rg_extra_params.extend([Data_Nascimento, Estado_Civil, Nacionalidade, Genero])


        if existing_doc:
            # Atualiza
            query = f"""
                UPDATE funcionarios_documentos
                SET
                    Numero_Documento = %s,
                    Data_Emissao = %s,
                    Orgao_Emissor = %s,
                    Uf_Emissor = %s,
                    Data_Vencimento = %s,
                    Observacoes = %s,
                    Data_Modificacao = NOW()
                    {rg_extra_fields}
                WHERE ID_Funcionario_Documento = %s
            """
            params = [numero_documento, Data_Emissao, Orgao_Emissor, Uf_Emissor, Data_Vencimento, Observacoes]
            params.extend(rg_extra_params)
            params.append(existing_doc[0]['ID_Funcionario_Documento'])
            self.db.execute_query(query, tuple(params), fetch_results=False)
        else:
            # Insere
            query = f"""
                INSERT INTO funcionarios_documentos (Matricula_Funcionario, Tipo_Documento, Numero_Documento, Data_Emissao, Orgao_Emissor, Uf_Emissor, Data_Vencimento, Observacoes, Data_Criacao, Data_Modificacao {', Data_Nascimento, Estado_Civil, Nacionalidade, Genero' if tipo_documento == 'RG' else ''})
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW() {', %s, %s, %s, %s' if tipo_documento == 'RG' else ''})
            """
            params = [matricula, tipo_documento, numero_documento, Data_Emissao, Orgao_Emissor, Uf_Emissor, Data_Vencimento, Observacoes]
            params.extend(rg_extra_params)
            self.db.execute_query(query, tuple(params), fetch_results=False)


    def get_funcionario_documentos_by_matricula(self, matricula):
        """Retorna todos os documentos de um funcionário."""
        query = """
            SELECT
                ID_Funcionario_Documento,
                Matricula_Funcionario,
                Tipo_Documento,
                Numero_Documento,
                Data_Emissao,
                Orgao_Emissor,
                Uf_Emissor,
                Data_Vencimento,
                Observacoes,
                Data_Criacao,
                Data_Modificacao,
                Data_Nascimento,
                Estado_Civil,
                Nacionalidade,
                Genero
            FROM funcionarios_documentos
            WHERE Matricula_Funcionario = %s
        """
        results = self.db.execute_query(query, (matricula,), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return []

    # --- Métodos de Endereços de Funcionários (NOVO) ---
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
        if not all([logradouro, numero, bairro, cidade, estado, cep]): # Se dados essenciais faltam, remove ou não insere
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
                ID_Funcionario_Endereco,
                Matricula_Funcionario,
                Tipo_Endereco,
                Logradouro,
                Numero,
                Complemento,
                Bairro,
                Cidade,
                Estado,
                Cep,
                Data_Criacao,
                Data_Modificacao
            FROM funcionarios_enderecos
            WHERE Matricula_Funcionario = %s
        """
        results = self.db.execute_query(query, (matricula,), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return []

    # --- Métodos de Contatos de Funcionários (NOVO) ---
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
        if not valor_contato: # Se o valor do contato estiver vazio, remove o registro (se existir)
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
                ID_Funcionario_Contato,
                Matricula_Funcionario,
                Tipo_Contato,
                Valor_Contato,
                Observacoes,
                Data_Criacao,
                Data_Modificacao
            FROM funcionarios_contatos
            WHERE Matricula_Funcionario = %s
        """
        results = self.db.execute_query(query, (matricula,), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return []

# Verificar se preciso desses 2 métodos "dropdown" <<<<<

    # --- Métodos de Cargos (Dropdown) ---
    def get_all_cargos_for_dropdown(self):
        """Retorna uma lista de cargos para preencher dropdowns."""
        query = "SELECT ID_Cargos, Nome_Cargo FROM cargos ORDER BY Nome_Cargo"
        return self.db.execute_query(query, fetch_results=True)

    # --- Métodos de Níveis (Dropdown) ---
    def get_all_niveis_for_dropdown(self):
        """Retorna uma lista de níveis para preencher dropdowns."""
        query = "SELECT ID_Niveis, Nome_Nivel FROM niveis ORDER BY Nome_Nivel"
        return self.db.execute_query(query, fetch_results=True)

# database/db_pessoal_manager.py (Adicione estes métodos dentro da classe PessoalManager, após os métodos de Funcionários)

    # --- Métodos de Cargos ---
    def get_all_cargos(self, search_nome=None):
        """
        Retorna uma lista de todos os cargos, opcionalmente filtrada.
        """
        query = """
            SELECT
                ID_Cargos,
                Nome_Cargo,
                Descricao_Cargo,
                Cbo,
                Data_Criacao,
                Data_Modificacao
            FROM
                cargos
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
        """
        Adiciona um novo cargo ao banco de dados.
        """
        query = """
            INSERT INTO cargos (Nome_Cargo, Descricao_Cargo, Cbo, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, %s, NOW(), NOW())
        """
        params = (nome_cargo, descricao_cargo, cbo)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_cargo_by_id(self, cargo_id):
        """
        Retorna os dados de um cargo pelo ID.
        """
        query = """
            SELECT
                ID_Cargos,
                Nome_Cargo,
                Descricao_Cargo,
                Cbo,
                Data_Criacao,
                Data_Modificacao
            FROM
                cargos
            WHERE ID_Cargos = %s
        """
        result = self.db.execute_query(query, (cargo_id,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_cargo(self, cargo_id, nome_cargo, descricao_cargo, cbo):
        """
        Atualiza os dados de um cargo existente.
        """
        query = """
            UPDATE cargos
            SET
                Nome_Cargo = %s,
                Descricao_Cargo = %s,
                Cbo = %s,
                Data_Modificacao = NOW()
            WHERE ID_Cargos = %s
        """
        params = (nome_cargo, descricao_cargo, cbo, cargo_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_cargo(self, cargo_id):
        """
        Exclui um cargo do banco de dados.
        Retorna False se houver funcionários associados.
        """
        # Verificar se há funcionários associados a este cargo
        check_query = "SELECT COUNT(*) AS count FROM funcionarios WHERE ID_Cargos = %s"
        result = self.db.execute_query(check_query, (cargo_id,), fetch_results=True)
        if result and result[0]['count'] > 0:
            print(f"Não é possível excluir o cargo ID {cargo_id}: Existem funcionários associados.")
            return False # Não permite exclusão se houver funcionários

        query = "DELETE FROM cargos WHERE ID_Cargos = %s"
        return self.db.execute_query(query, (cargo_id,), fetch_results=False)

    def get_cargo_by_nome(self, nome_cargo):
        """
        Verifica se um cargo com o dado nome já existe.
        """
        query = "SELECT ID_Cargos FROM cargos WHERE Nome_Cargo = %s"
        result = self.db.execute_query(query, (nome_cargo,), fetch_results=True)
        return result[0] if result else None


    # --- Métodos de Níveis ---
    def get_all_niveis(self, search_nome=None):
        """
        Retorna uma lista de todos os níveis, opcionalmente filtrada.
        """
        query = """
            SELECT
                ID_Niveis,
                Nome_Nivel,
                Descricao,
                Data_Criacao,
                Data_Modificacao
            FROM
                niveis
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
        """
        Adiciona um novo nível ao banco de dados.
        """
        query = """
            INSERT INTO niveis (Nome_Nivel, Descricao, Data_Criacao, Data_Modificacao)
            VALUES (%s, %s, NOW(), NOW())
        """
        params = (nome_nivel, descricao)
        return self.db.execute_query(query, params, fetch_results=False)

    def get_nivel_by_id(self, nivel_id):
        """
        Retorna os dados de um nível pelo ID.
        """
        query = """
            SELECT
                ID_Niveis,
                Nome_Nivel,
                Descricao,
                Data_Criacao,
                Data_Modificacao
            FROM
                niveis
            WHERE ID_Niveis = %s
        """
        result = self.db.execute_query(query, (nivel_id,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_nivel(self, nivel_id, nome_nivel, descricao):
        """
        Atualiza os dados de um nível existente.
        """
        query = """
            UPDATE niveis
            SET
                Nome_Nivel = %s,
                Descricao = %s,
                Data_Modificacao = NOW()
            WHERE ID_Niveis = %s
        """
        params = (nome_nivel, descricao, nivel_id)
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_nivel(self, nivel_id):
        """
        Exclui um nível do banco de dados.
        Retorna False se houver funcionários associados.
        """
        # Verificar se há funcionários associados a este nível
        check_query = "SELECT COUNT(*) AS count FROM funcionarios WHERE ID_Niveis = %s"
        result = self.db.execute_query(check_query, (nivel_id,), fetch_results=True)
        if result and result[0]['count'] > 0:
            print(f"Não é possível excluir o nível ID {nivel_id}: Existem funcionários associados.")
            return False # Não permite exclusão se houver funcionários

        query = "DELETE FROM niveis WHERE ID_Niveis = %s"
        return self.db.execute_query(query, (nivel_id,), fetch_results=False)

    def get_nivel_by_nome(self, nome_nivel):
        """
        Verifica se um nível com o dado nome já existe.
        """
        query = "SELECT ID_Niveis FROM niveis WHERE Nome_Nivel = %s"
        result = self.db.execute_query(query, (nome_nivel,), fetch_results=True)
        return result[0] if result else None