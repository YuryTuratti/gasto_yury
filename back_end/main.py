from fastapi import FastAPI, Request
from datetime import datetime
import psycopg2
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = FastAPI()

# ---------------------------------------------------------
# CONFIGURAÇÃO DO POSTGRESQL (Usando .env)
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
        
        # Cria a tabela caso não exista
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
        print("✅ Banco de dados conectado e tabela verificada.")
    except Exception as e:
        print(f"❌ Erro ao conectar no PostgreSQL: {e}")
        print("Verifique se o Postgres está rodando e se os dados no .env estão corretos.")

# Executa a verificação do banco ao iniciar a API
iniciar_banco()

# ---------------------------------------------------------
# ROTA DO WEBHOOK (Recebe os gastos via WhatsApp)
# ---------------------------------------------------------
@app.post("/webhook")
async def receber_mensagem(request: Request):
    payload = await request.json()
    texto_whatsapp = payload.get("mensagem", "")
    
    try:
        # Lógica de separação da string
        dados = texto_whatsapp.split(";")
        
        if len(dados) != 4:
            return {"status": "erro", "mensagem": "Formato inválido. Use: Tipo ; Valor ; Categoria ; Descrição"}
            
        tipo = dados[0].strip().lower()
        # Tratamento para aceitar vírgula ou ponto nos centavos
        valor = float(dados[1].strip().replace(',', '.'))
        categoria = dados[2].strip()
        descricao = dados[3].strip()
        
        # Inserção segura no PostgreSQL
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        cursor.execute('''
            INSERT INTO transacoes (tipo, valor, categoria, descricao, data_registro)
            VALUES (%s, %s, %s, %s, %s)
        ''', (tipo, valor, categoria, descricao, datetime.now()))
        
        conexao.commit()
        cursor.close()
        conexao.close()

        print(f"✅ Registro salvo: {tipo.capitalize()} | R$ {valor:.2f} | {categoria} | {descricao}")
        
        return {"status": "sucesso", "mensagem": "Registro processado com sucesso!"}

    except ValueError:
        return {"status": "erro", "mensagem": "O valor informado não é um número válido."}
    except Exception as e:
        print(f"❌ Erro interno: {e}")
        return {"status": "erro", "mensagem": "Erro interno no servidor."}