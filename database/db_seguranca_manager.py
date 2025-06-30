# database/db_seguranca_manager.py
# Conteúdo criado em 2025-06-29

import mysql.connector
from datetime import datetime, date

class SegurancaManager:
    def __init__(self, db_manager_instance):
        self.db = db_manager_instance

    def _format_date_fields(self, item):
        """
        Função auxiliar para converter campos de data em dicionários de resultados
        para objetos date ou None.
        """
        if item is None:
            return None
        
        date_fields_to_format = [
            'Data_Criacao', 'Data_Modificacao',
            'Data_Hora_Ocorrencia', # Incidentes_Acidentes
            'Data_Fechamento' # Incidentes_Acidentes
        ]
        
        for key in date_fields_to_format:
            if key in item:
                value = item[key]
                if isinstance(value, str):
                    if not value.strip():
                        item[key] = None
                        continue
                    try:
                        # Tenta analisar como DATETIME completo primeiro, pois Data_Hora_Ocorrencia é DATETIME
                        item[key] = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        try:
                            # Se falhar, tenta como DATE
                            item[key] = datetime.strptime(value, '%Y-%m-%d').date()
                        except ValueError:
                            print(f"AVISO: Não foi possível converter a string de data '{value}' para objeto datetime/date para o campo '{key}'. Definindo como None.")
                            item[key] = None
                elif isinstance(value, date) and not isinstance(value, datetime):
                    # Se já for um objeto date, mantém como date
                    pass
                elif isinstance(value, datetime):
                    # Se for datetime, mantém como datetime (para Data_Hora_Ocorrencia)
                    pass
                elif value is None:
                    item[key] = None

        return item

    # --- Métodos de Incidentes e Acidentes ---
    def get_all_incidentes_acidentes(self, search_tipo=None, search_status=None, search_obra_id=None, search_responsavel_matricula=None):
        """
        Retorna uma lista de todos os incidentes/acidentes, opcionalmente filtrada.
        """
        query = """
            SELECT
                ia.ID_Incidente_Acidente,
                ia.Tipo_Registro,
                ia.Data_Hora_Ocorrencia,
                ia.Local_Ocorrencia,
                ia.ID_Obras,
                ia.Descricao_Resumida,
                ia.Status_Registro,
                ia.Responsavel_Investigacao_Funcionario_Matricula,
                o.Numero_Obra,
                o.Nome_Obra,
                f.Nome_Completo AS Nome_Responsavel_Investigacao,
                ia.Data_Criacao,
                ia.Data_Modificacao
            FROM
                incidentes_acidentes ia
            LEFT JOIN
                obras o ON ia.ID_Obras = o.ID_Obras
            LEFT JOIN
                funcionarios f ON ia.Responsavel_Investigacao_Funcionario_Matricula = f.Matricula
            WHERE 1=1
        """
        params = []

        if search_tipo:
            query += " AND ia.Tipo_Registro = %s"
            params.append(search_tipo)
        if search_status:
            query += " AND ia.Status_Registro = %s"
            params.append(search_status)
        if search_obra_id:
            query += " AND ia.ID_Obras = %s"
            params.append(search_obra_id)
        if search_responsavel_matricula:
            query += " AND ia.Responsavel_Investigacao_Funcionario_Matricula = %s"
            params.append(search_responsavel_matricula)
        
        query += " ORDER BY ia.Data_Hora_Ocorrencia DESC"

        results = self.db.execute_query(query, tuple(params), fetch_results=True)
        if results:
            return [self._format_date_fields(item) for item in results]
        return results

    def add_incidente_acidente(self, tipo_registro, data_hora_ocorrencia, local_ocorrencia, id_obras, descricao_resumida, causas_identificadas, acoes_corretivas_tomadas, acoes_preventivas_recomendadas, status_registro, responsavel_investigacao_matricula, data_fechamento, observacoes):
        """
        Adiciona um novo registro de incidente/acidente.
        """
        query = """
            INSERT INTO incidentes_acidentes (
                Tipo_Registro, Data_Hora_Ocorrencia, Local_Ocorrencia, ID_Obras,
                Descricao_Resumida, Causas_Identificadas, Acoes_Corretivas_Tomadas,
                Acoes_Preventivas_Recomendadas, Status_Registro, Responsavel_Investigacao_Funcionario_Matricula,
                Data_Fechamento, Observacoes, Data_Criacao, Data_Modificacao
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (
            tipo_registro, data_hora_ocorrencia, local_ocorrencia, id_obras,
            descricao_resumida, causas_identificadas, acoes_corretivas_tomadas,
            acoes_preventivas_recomendadas, status_registro, responsavel_investigacao_matricula,
            data_fechamento, observacoes
        )
        return self.db.execute_query(query, params, fetch_results=False)

    def get_incidente_acidente_by_id(self, incidente_id):
        """
        Retorna os dados de um incidente/acidente pelo ID.
        """
        query = """
            SELECT
                ia.ID_Incidente_Acidente,
                ia.Tipo_Registro,
                ia.Data_Hora_Ocorrencia,
                ia.Local_Ocorrencia,
                ia.ID_Obras,
                ia.Descricao_Resumida,
                ia.Causas_Identificadas,
                ia.Acoes_Corretivas_Tomadas,
                ia.Acoes_Preventivas_Recomendadas,
                ia.Status_Registro,
                ia.Responsavel_Investigacao_Funcionario_Matricula,
                ia.Data_Fechamento,
                ia.Observacoes,
                o.Numero_Obra,
                o.Nome_Obra,
                f.Nome_Completo AS Nome_Responsavel_Investigacao,
                ia.Data_Criacao,
                ia.Data_Modificacao
            FROM
                incidentes_acidentes ia
            LEFT JOIN
                obras o ON ia.ID_Obras = o.ID_Obras
            LEFT JOIN
                funcionarios f ON ia.Responsavel_Investigacao_Funcionario_Matricula = f.Matricula
            WHERE ia.ID_Incidente_Acidente = %s
        """
        result = self.db.execute_query(query, (incidente_id,), fetch_results=True)
        if result:
            return self._format_date_fields(result[0])
        return None

    def update_incidente_acidente(self, incidente_id, tipo_registro, data_hora_ocorrencia, local_ocorrencia, id_obras, descricao_resumida, causas_identificadas, acoes_corretivas_tomadas, acoes_preventivas_recomendadas, status_registro, responsavel_investigacao_matricula, data_fechamento, observacoes):
        """
        Atualiza os dados de um registro de incidente/acidente existente.
        """
        query = """
            UPDATE incidentes_acidentes
            SET
                Tipo_Registro = %s,
                Data_Hora_Ocorrencia = %s,
                Local_Ocorrencia = %s,
                ID_Obras = %s,
                Descricao_Resumida = %s,
                Causas_Identificadas = %s,
                Acoes_Corretivas_Tomadas = %s,
                Acoes_Preventivas_Recomendadas = %s,
                Status_Registro = %s,
                Responsavel_Investigacao_Funcionario_Matricula = %s,
                Data_Fechamento = %s,
                Observacoes = %s,
                Data_Modificacao = NOW()
            WHERE ID_Incidente_Acidente = %s
        """
        params = (
            tipo_registro, data_hora_ocorrencia, local_ocorrencia, id_obras,
            descricao_resumida, causas_identificadas, acoes_corretivas_tomadas,
            acoes_preventivas_recomendadas, # <--- CORRIGIDO AQUI NOS PARÂMETROS
            status_registro, responsavel_investigacao_matricula,
            data_fechamento, observacoes, incidente_id
        )
        return self.db.execute_query(query, params, fetch_results=False)

    def delete_incidente_acidente(self, incidente_id):
        """
        Exclui um registro de incidente/acidente do banco de dados.
        """
        query = "DELETE FROM incidentes_acidentes WHERE ID_Incidente_Acidente = %s"
        return self.db.execute_query(query, (incidente_id,), fetch_results=False)
