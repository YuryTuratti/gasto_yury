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
# FUNÇÃO AUXILIAR: EXTRAIR TEXTO DA EVOLUTION API
# ---------------------------------------------------------
def extrair_texto_evolution(payload):
    """
    Navega pelo JSON da Evolution API para encontrar o texto da mensagem.
    Suporta mensagens simples e mensagens com link/formatadas.
    """
    try:
        data = payload.get("data", {})
        message = data.get("message", {})
        
        # Tenta pegar mensagem simples ou mensagem estendida
        texto = message.get("conversation") or \
                message.get("extendedTextMessage", {}).get("text")
        
        return texto if texto else ""
    except Exception:
        return ""

# ---------------------------------------------------------
# ROTA DO WEBHOOK
# ---------------------------------------------------------
@app.post("/webhook")
async def receber_mensagem(request: Request):
    payload = await request.json()
    
    # LOG para depuração no Docker
    print("\n=== NOVO WEBHOOK RECEBIDO ===", flush=True)
    
    texto_whatsapp = extrair_texto_evolution(payload)
    print(f"Texto extraído: {texto_whatsapp}", flush=True)

    if not texto_whatsapp or ";" not in texto_whatsapp:
        print("Mensagem ignorada (não contém o formato esperado).", flush=True)
        return {"status": "ignorado", "motivo": "Formato inválido"}

    try:
        # Lógica de separação: Tipo ; Valor ; Categoria ; Descrição
        dados = texto_whatsapp.split(";")
        
        if len(dados) < 3:
            return {"status": "erro", "mensagem": "Use: Tipo ; Valor ; Categoria"}
            
        tipo = dados[0].strip().lower()
        valor = float(dados[1].strip().replace(',', '.'))
        categoria = dados[2].strip()
        descricao = dados[3].strip() if len(dados) > 3 else ""
        
        # Inserção no PostgreSQL
        conexao = conectar_banco()
        cursor = conexao.cursor()
        cursor.execute('''
            INSERT INTO transacoes (tipo, valor, categoria, descricao, data_registro)
            VALUES (%s, %s, %s, %s, %s)
        ''', (tipo, valor, categoria, descricao, datetime.now()))
        
        conexao.commit()
        cursor.close()
        conexao.close()

        print(f"✅ Salvo: {tipo} | R$ {valor} | {categoria}", flush=True)
        return {"status": "sucesso"}

    except Exception as e:
        print(f"❌ Erro ao processar: {e}", flush=True)
        return {"status": "erro", "detalhe": str(e)}