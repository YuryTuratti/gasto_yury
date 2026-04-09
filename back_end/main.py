from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import psycopg2
import os
import json
import logging
from dotenv import load_dotenv

# Configuração de Logging para o Docker ler em tempo real
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

load_dotenv()
app = FastAPI()

# =============================================================================
# CORS MIDDLEWARE - Permite requisições do Frontend HTML/JavaScript
# =============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite qualquer origem (localhost, seu HTML, etc)
    allow_credentials=True,
    allow_methods=["*"],  # Permite GET, POST, OPTIONS, etc
    allow_headers=["*"],  # Permite qualquer header
)

# Configurações do Banco
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "gasto_yury")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")
DB_PORT = int(os.getenv("DB_PORT", 5432))

def conectar_banco():
    """Conecta ao banco de dados PostgreSQL"""
    try:
        # Log das configurações (sem mostrar a senha)
        logging.info(f"Conectando ao {DB_HOST}:{DB_PORT}/{DB_NAME} como {DB_USER}")
        
        conexao = psycopg2.connect(
            host=DB_HOST, 
            database=DB_NAME, 
            user=DB_USER, 
            password=DB_PASS, 
            port=DB_PORT,
            connect_timeout=5
        )
        logging.info("✅ Conexão com PostgreSQL estabelecida!")
        return conexao
    except psycopg2.OperationalError as e:
        logging.error(f"❌ Erro ao conectar ao banco: {e}")
        raise
    except Exception as e:
        logging.error(f"❌ Erro inesperado: {e}")
        raise

@app.on_event("startup")
def iniciar_banco():
    """Inicializa o banco de dados criando tabela se necessário"""
    try:
        logging.info("🔄 Tentando conectar ao banco de dados...")
        conexao = conectar_banco()
        logging.info("✅ Conectado ao banco com sucesso!")
        
        cursor = conexao.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transacoes (
                id SERIAL PRIMARY KEY,
                tipo VARCHAR(50),
                valor NUMERIC(10, 2),
                categoria VARCHAR(100),
                descricao TEXT,
                data_registro TIMESTAMP
            )
        ''')
        conexao.commit()
        cursor.close()
        conexao.close()
        logging.info("✅ BANCO DE DADOS CONECTADO E TABELA OK")
    except Exception as e:
        logging.warning(f"⚠️ AVISO AO INICIAR BANCO: {e}")
        logging.warning("⚠️ Usando dados simulados. Configure o PostgreSQL para dados reais.")

@app.post("/webhook")
async def receber_mensagem(request: Request):
    try:
        payload = await request.json()
        
        # Este log VAI aparecer no Docker logs agora
        logging.info("--- NOVA MENSAGEM RECEBIDA ---")
        logging.info(f"PAYLOAD BRUTO: {json.dumps(payload)}")

        # Extração Evolution API
        data = payload.get("data", {})
        message = data.get("message", {})
        
        # Tenta pegar de 'conversation' ou 'extendedTextMessage'
        texto = message.get("conversation") or \
                message.get("extendedTextMessage", {}).get("text")

        if texto and ";" in texto:
            logging.info(f"Texto detectado: {texto}")
            dados = texto.split(";")
            
            tipo = dados[0].strip().lower()
            valor = float(dados[1].strip().replace(',', '.'))
            categoria = dados[2].strip()
            descricao = dados[3].strip() if len(dados) > 3 else ""

            # Salva no Banco
            conexao = conectar_banco()
            cursor = conexao.cursor()
            cursor.execute('''
                INSERT INTO transacoes (tipo, valor, categoria, descricao, data_registro)
                VALUES (%s, %s, %s, %s, %s)
            ''', (tipo, valor, categoria, descricao, datetime.now()))
            conexao.commit()
            cursor.close()
            conexao.close()

            logging.info(f"✅ REGISTRO SALVO: {tipo} | R$ {valor}")
            return {"status": "sucesso"}
        
        logging.warning("⚠️ Mensagem recebida, mas não contém o padrão 'tipo ; valor ; categoria'")
        return {"status": "ignorado"}

    except Exception as e:
        logging.error(f"❌ ERRO NO PROCESSAMENTO: {e}")
        return {"status": "erro", "detalhe": str(e)}


# =============================================================================
# ROTAS PARA O DASHBOARD (Frontend)
# =============================================================================

@app.get("/")
def read_root():
    """Rota raiz - verificar se o servidor está rodando"""
    return {
        "mensagem": "✅ Backend FastAPI rodando!",
        "endpoints_disponiveis": [
            "GET /api/resumo",
            "GET /api/gastos-mensais",
            "GET /api/operacoes",
            "GET /api/armazenamento",
            "GET /api/transacoes"
        ]
    }


@app.get("/api/resumo")
def get_resumo_financeiro():
    """
    Retorna o resumo financeiro principal (KPIs)
    Frontend: Atualiza os 6 cards de números no topo
    """
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        # Calcula saldo total (soma de todas as transações)
        cursor.execute("SELECT COALESCE(SUM(valor), 0) FROM transacoes WHERE tipo = 'entrada'")
        saldo_total = cursor.fetchone()[0]
        
        # Calcula gasto mensal (soma de saídas do mês atual)
        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0) FROM transacoes 
            WHERE tipo = 'saida' AND EXTRACT(MONTH FROM data_registro) = EXTRACT(MONTH FROM NOW())
        """)
        gasto_mensal = cursor.fetchone()[0]
        
        cursor.close()
        conexao.close()
        
        return {
            "saldo_total": f"{saldo_total:,.2f}".replace(",", "."),
            "gasto_mensal": f"{gasto_mensal:,.2f}".replace(",", "."),
            "projetos_ativos": 27,
            "tarefas_pendentes": 154,
            "contas_ativas": 2935,
            "documentos": 32
        }
    except Exception as e:
        logging.error(f"❌ ERRO ao buscar resumo: {e}")
        # Retorna dados padrão se houver erro
        return {
            "saldo_total": "3.050,47",
            "gasto_mensal": "742,39",
            "projetos_ativos": 27,
            "tarefas_pendentes": 154,
            "contas_ativas": 2935,
            "documentos": 32
        }


@app.get("/api/gastos-mensais")
def get_gastos_mensais():
    """
    Retorna os gastos dos últimos 6 meses para o gráfico de linha
    Frontend: Atualiza o gráfico de linha (Gastos Mensais)
    """
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        # Query para pegar gastos dos últimos 6 meses
        cursor.execute("""
            SELECT 
                TO_CHAR(data_registro, 'Month') as mes,
                COALESCE(SUM(valor), 0) as total
            FROM transacoes
            WHERE tipo = 'saida' AND data_registro >= NOW() - INTERVAL '6 months'
            GROUP BY DATE_TRUNC('month', data_registro), TO_CHAR(data_registro, 'Month')
            ORDER BY DATE_TRUNC('month', data_registro)
        """)
        
        resultados = cursor.fetchall()
        cursor.close()
        conexao.close()
        
        meses = [r[0].strip() for r in resultados]
        gastos = [float(r[1]) for r in resultados]
        
        return {
            "meses": meses if meses else ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho"],
            "gastos": gastos if gastos else [620, 548, 745, 812, 675, 742]
        }
    except Exception as e:
        logging.error(f"❌ ERRO ao buscar gastos mensais: {e}")
        return {
            "meses": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho"],
            "gastos": [620, 548, 745, 812, 675, 742]
        }


@app.get("/api/operacoes")
def get_operacoes():
    """
    Retorna dados de operações para o gráfico de barras
    Frontend: Atualiza o gráfico de barras (Sucesso Operacional)
    """
    return {
        "meses": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "operacoes": [65, 59, 80, 81, 56, 55]
    }


@app.get("/api/armazenamento")
def get_armazenamento():
    """
    Retorna dados de armazenamento para o gráfico donut
    Frontend: Atualiza o gráfico donut (Armazenamento)
    """
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        # Conta transações por categoria
        cursor.execute("""
            SELECT categoria, COUNT(*) as quantidade
            FROM transacoes
            GROUP BY categoria
            LIMIT 3
        """)
        
        resultados = cursor.fetchall()
        cursor.close()
        conexao.close()
        
        if resultados and len(resultados) > 0:
            categorias = [r[0] for r in resultados]
            valores = [r[1] for r in resultados]
            return {"tipos": categorias, "valores": valores}
    except Exception as e:
        logging.error(f"❌ ERRO ao buscar armazenamento: {e}")
    
    # Dados padrão
    return {
        "tipos": ["SSD", "HDD", "Cloud"],
        "valores": [300, 150, 50]
    }


@app.get("/api/transacoes")
def get_transacoes():
    """
    Retorna a lista de transações recentes
    Frontend: Atualiza a tabela de Relatórios Recentes
    """
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        # Busca as 4 transações mais recentes
        cursor.execute("""
            SELECT id, categoria, valor, descricao, data_registro
            FROM transacoes
            ORDER BY data_registro DESC
            LIMIT 4
        """)
        
        resultados = cursor.fetchall()
        cursor.close()
        conexao.close()
        
        transacoes = []
        for row in resultados:
            transacoes.append({
                "id": row[0],
                "nome": row[2],  # categoria
                "status": "Submitted" if row[1] else "In Progress",
                "tamanho": f"R$ {row[2]:.2f}",
                "data": row[4].strftime("%d %b %Y") if row[4] else "N/A",
                "hora": row[4].strftime("%I:%M%p") if row[4] else "N/A"
            })
        
        if transacoes:
            return {"transacoes": transacoes}
    except Exception as e:
        logging.error(f"❌ ERRO ao buscar transações: {e}")
    
    # Dados padrão
    return {
        "transacoes": [
            {
                "id": 1,
                "nome": "Jonathan Sandoval",
                "status": "In Progress",
                "tamanho": "56 MB",
                "data": "10 Jun 2024",
                "hora": "04:48PM"
            },
            {
                "id": 2,
                "nome": "Matt Doherty",
                "status": "In Progress",
                "tamanho": "49 MB",
                "data": "10 Jun 2024",
                "hora": "04:00PM"
            },
            {
                "id": 3,
                "nome": "Adele Parkson",
                "status": "Submitted",
                "tamanho": "98 MB",
                "data": "10 Jun 2024",
                "hora": "04:37PM"
            },
            {
                "id": 4,
                "nome": "Miguel Chavez",
                "status": "Submitted",
                "tamanho": "26 MB",
                "data": "10 Jun 2024",
                "hora": "04:19PM"
            }
        ]
    }