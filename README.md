# 🏢 LUMOB – Sistema de Gestão Interna Modular

<p align="center">
  <img src="https://raw.githubusercontent.com/mendes79/lumob/main/static/img/banner.png" width="70%" alt="Preview do LUMOB">
</p>

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1%2B-green.svg)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-orange.svg)](https://mysql.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-red.svg)]()

> Sistema de gestão empresarial modular focado em **funcionalidade robusta** e **escalabilidade**. Desenvolvido com a filosofia "funcionalidade primeiro" para garantir operações essenciais sólidas.

---

## 🎯 Visão Geral

O **LUMOB** é uma aplicação web modular desenvolvida com Flask e MySQL para empresas que precisam gerenciar **pessoal**, **obras**, **clientes**, **contratos**, **documentos técnicos** e **relatórios** de maneira integrada e organizada.

---

## 🔥 Diferenciais

- Arquitetura modular escalável
- CRUD completo por módulo
- Exportações em Excel
- Permissões de acesso detalhadas
- Relatórios gerenciais prontos

---

## 📋 Funcionalidades por Módulo

### 👥 Módulo Pessoal (RH/DP)
- Cadastro completo de funcionários (dados, documentos, contatos)
- Geração automática de matrícula
- Relatórios de férias, vencimentos, aniversariantes
- Exportação para Excel

### 🏗️ Módulo Obras
- Gestão de obras, contratos, clientes, ARTs e medições
- Submódulos independentes com exportação
- Avanços físicos, REIDIs e seguros

### 🛡️ Módulo SSMA (em desenvolvimento)
- Registro de incidentes
- ASOs e saúde ocupacional
- Treinamentos e certificações

### 🔐 Módulo Usuários
- Login seguro com Flask-Login
- Permissões por módulo
- CRUD de usuários e redefinição de senha

---

## 🛠️ Tecnologias

- **Backend**: Python 3.10+, Flask 3.1
- **Banco de Dados**: MySQL 8.0+
- **Exportação**: `pandas`, `openpyxl`
- **Segurança**: `Flask-Login`, `bcrypt`, `passlib`
- **Frontend**: HTML, CSS, JS, Jinja2

---

## 🚀 Como Rodar Localmente

### Pré-requisitos
- Python 3.10+
- MySQL 8.0+
- Git

### Passos:

```bash
# Clone o projeto
git clone https://github.com/mendes79/lumob.git
cd lumob

# Crie e ative o ambiente virtual
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# Instale as dependências
pip install -r requirements.txt

# Configure o banco
# → Crie um banco MySQL chamado lumob
# → Ajuste suas credenciais em config/database.py

# Execute a aplicação
python app.py

# Acesse em:
http://127.0.0.1:5000
```
---

## 🧱 Estrutura de Pastas
```
lumob/
├── database/
│   ├── __init__.py
│   ├── db_base.py
│   ├── db_hr_manager.py
│   ├── db_modulos_permissoes_manager.py
│   ├── db_obras_manager.py
│   ├── db_personal_manager.py
│   ├── db_pessoal_manager.py
│   ├── db_seguranca_manager.py
│   └── db_user_manager.py
├── static/
│   ├── css/
│   │   ├── listar_diretorios.py
│   │   ├── style.css
│   │   └── style_welcome.css
│   ├── fonts/
│   │   ├── MODERNA_.TTF
│   │   ├── grandview.zip
│   │   ├── moderna.zip
│   │   └── read_me.pdf
│   ├── img/
│   │   ├── branco.png
│   │   ├── landscape-construction.jpg
│   │   ├── landscape-construction1.jpg
│   │   ├── lightbulb-icon.png
│   │   ├── obras_colorful.jpg
│   │   ├── pessoal_colorful.jpg
│   │   ├── seguranca_colorful.jpg
│   │   └── users_colorful.jpg
│   └── js/
│       ├── script.js
│       └── script_welcome.js
├── templates/
│   ├── Obras/
│   │   ├── arts/
│   │   ├── avancos_fisicos/
│   │   ├── clientes/
│   │   ├── contratos/
│   │   ├── medicoes/
│   │   ├── reidis/
│   │   ├── seguros/
│   │   ├── add_obra.html
│   │   ├── edit_obra.html
│   │   ├── obra_details.html
│   │   ├── obras_module.html
│   │   └── obras_welcome.html
│   ├── pessoal/
│   │   ├── cargos/
│   │   ├── dependentes/
│   │   ├── ferias/
│   │   ├── funcionarios/
│   │   ├── niveis/
│   │   ├── salarios/
│   │   ├── aniversariantes_module.html
│   │   ├── documentos_a_vencer_module.html
│   │   ├── experiencia_a_vencer_module.html
│   │   ├── pessoal_dashboard.html
│   │   └── pessoal_welcome.html
│   ├── seguranca/
│   │   ├── asos/
│   │   ├── incidentes_acidentes/
│   │   ├── treinamentos/
│   │   └── seguranca_module.html
│   ├── users/
│   │   ├── add_user.html
│   │   ├── edit_user.html
│   │   ├── manage_permissions.html
│   │   └── users_module.html
│   ├── login.html
│   └── welcome.html
├── app.py
├── conexao_db.py
├── db_manager.py
└── README.md
```
---

🗂️ Wiki
📚 Documentação técnica e guias de uso em: Wiki do Projeto

---

🛣️ Roadmap
Em desenvolvimento:
- [x] CRUD Pessoal completo
- [x] CRUD Obras completo
- [x] CRUD Segurança Completo
- [x] Dashboard de obras
- [x] Dashboard de pessoal
- [x] Dashboard de segurança
- [x] UI com Bootstrap
- [x] Página de login estilizada
- [x] Gráficos com Chart.js
- [ ] Controle de Ponto
- [ ] Relatórios personalizados

---

🤝 Contribuições
# Etapas para contribuir
1. Fork o projeto
2. git checkout -b feature/NomeDaFeature
3. git commit -m "feat: minha contribuição"
4. git push origin feature/NomeDaFeature
5. Crie um Pull Request

---

📝 Licença
Este projeto está sob a licença MIT. Veja o arquivo LICENSE.

---

👨‍💻 Autor
mendes79
Engenheiro Eletricista, Programador, Maker, Tatuador e Músico  
Especialista em: Python, Flask, MySQL, Eletrônica, Pentest, Impressão 3D  
🔗 github.com/mendes79

⭐ Gostou do projeto? Deixe uma estrela! ⭐
