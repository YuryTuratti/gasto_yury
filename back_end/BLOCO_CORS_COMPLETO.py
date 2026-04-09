# ============================================================================
# BLOCO CORS COMPLETO - TOPO DO main.py
# ============================================================================

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
    allow_origins=["*"],           # ✅ Permite requisições de QUALQUER origem
    allow_credentials=True,        # ✅ Permite envio de credenciais (cookies, headers auth)
    allow_methods=["*"],           # ✅ Permite GET, POST, PUT, DELETE, OPTIONS, etc
    allow_headers=["*"],           # ✅ Permite qualquer header customizado
)

# Configurações do Banco de Dados
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "gasto_yury")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")
DB_PORT = int(os.getenv("DB_PORT", 5432))

# ... resto do código continua normalmente
