from fastapi import FastAPI, Request
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

# Configurações do Banco
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")

def conectar_banco():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT
    )

@app.on_event("startup")
def iniciar_banco():
    try:
        conexao = conectar_banco()
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
        logging.error(f"❌ ERRO AO INICIAR BANCO: {e}")

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