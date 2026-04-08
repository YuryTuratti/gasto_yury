from fastapi import FastAPI, Request
from datetime import datetime
import psycopg2
import os
import json
from dotenv import load_dotenv

# Carrega as variáveis de ambiente
load_dotenv()

app = FastAPI()

# ---------------------------------------------------------
# CONFIGURAÇÃO DO POSTGRESQL
# ---------------------------------------------------------
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")

def conectar_banco():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )

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
        print("✅ Banco de dados conectado e tabela verificada.", flush=True)
    except Exception as e:
        print(f"❌ Erro ao conectar no PostgreSQL: {e}", flush=True)

iniciar_banco()

# ---------------------------------------------------------
# ROTA DO WEBHOOK (Ouvindo a Evolution API)
# ---------------------------------------------------------
@app.post("/webhook")
async def receber_mensagem(request: Request):
    try:
        payload = await request.json()
        
        # LOG DE DEBUG: Isso vai mostrar exatamente o que a Evolution está enviando
        print("\n=== WEBHOOK RECEBIDO ===", flush=True)
        print(json.dumps(payload, indent=2), flush=True)

        # 1. Tenta extrair o texto da mensagem (Padrão Evolution API v1.x e v2.x)
        data = payload.get("data", {})
        message = data.get("message", {})
        
        # A mensagem pode vir em 'conversation' ou 'extendedTextMessage'
        texto_whatsapp = message.get("conversation") or \
                         message.get("extendedTextMessage", {}).get("text")

        if not texto_whatsapp:
            print("⚠️ Nenhuma mensagem de texto encontrada no payload.", flush=True)
            return {"status": "sucesso", "info": "evento_recebido_sem_texto"}

        print(f"📩 Texto extraído: {texto_whatsapp}", flush=True)

        # 2. Verifica se a mensagem segue o formato: tipo ; valor ; categoria ; descricao
        if ";" in texto_whatsapp:
            dados = texto_whatsapp.split(";")
            
            # Limpa e organiza os dados
            tipo = dados[0].strip().lower()
            valor = float(dados[1].strip().replace(',', '.'))
            categoria = dados[2].strip()
            descricao = dados[3].strip() if len(dados) > 3 else ""

            # 3. Salva no Banco de Dados
            conexao = conectar_banco()
            cursor = conexao.cursor()
            cursor.execute('''
                INSERT INTO transacoes (tipo, valor, categoria, descricao, data_registro)
                VALUES (%s, %s, %s, %s, %s)
            ''', (tipo, valor, categoria, descricao, datetime.now()))
            
            conexao.commit()
            cursor.close()
            conexao.close()

            print(f"✅ REGISTRO SALVO NO POSTGRES: {tipo} | R$ {valor}", flush=True)
            return {"status": "sucesso", "mensagem": "Gravado com sucesso"}
        
        else:
            print("ℹ️ Mensagem recebida, mas não está no formato 'tipo ; valor ; categoria'.", flush=True)
            return {"status": "sucesso", "info": "texto_ignorado"}

    except Exception as e:
        print(f"❌ ERRO NO PROCESSAMENTO: {str(e)}", flush=True)
        return {"status": "erro", "detalhes": str(e)}