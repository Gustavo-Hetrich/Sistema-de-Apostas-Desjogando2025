from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import asyncpg
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Configuração do banco de dados
DATABASE_URL = "postgresql://desjogandosql_user:isUyPC80jvkVlcE5iA4YboRmFqJRPAtM@dpg-cuh4kd0gph6c73dknn10-a.oregon-postgres.render.com/desjogandosql"

# Servindo arquivos estáticos da pasta 'static'
app.mount("/static", StaticFiles(directory="static"), name="static")

# Rota para servir o index.html
@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r") as f:
        content = f.read()
    return HTMLResponse(content=content)

# Adicionando o CORS para permitir chamadas de qualquer origem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectando ao PostgreSQL
async def connect_to_db():
    return await asyncpg.connect(DATABASE_URL)

# Modelo de dados do usuário
class Usuario(BaseModel):
    nome: str

@app.on_event("startup")
async def startup():
    conn = await connect_to_db()
    await conn.execute('''  
    CREATE TABLE IF NOT EXISTS usuarios (
        nome TEXT PRIMARY KEY,
        saldo INTEGER DEFAULT 100
    );
    ''')
    await conn.close()

@app.post("/login")
async def login(usuario: Usuario):
    conn = await connect_to_db()
    nome = usuario.nome.lower()
    
    # Verifica se o usuário já existe
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    
    if result is None:
        # Se o usuário não existir, cria o usuário com saldo inicial de 100
        await conn.execute('INSERT INTO usuarios (nome, saldo) VALUES ($1, $2)', nome, 100)
        saldo = 100
    else:
        saldo = result["saldo"]
    
    await conn.close()
    return {"mensagem": f"Bem-vindo, {nome}!", "saldo": saldo}

@app.get("/saldo/{nome}")
async def saldo(nome: str):
    conn = await connect_to_db()
    nome = nome.lower()
    
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    
    if result is None:
        await conn.close()
        return {"erro": "Usuário não encontrado"}
    
    await conn.close()
    return {"nome": nome, "saldo": result["saldo"]}

# Nova rota para listar todos os usuários e seus saldos
@app.get("/usuarios")
async def listar_usuarios():
    conn = await connect_to_db()
    
    # Consulta para pegar todos os usuários e seus saldos
    result = await conn.fetch('SELECT nome, saldo FROM usuarios')
    
    # Converte o resultado em uma lista de dicionários
    usuarios = [{"nome": row["nome"], "saldo": row["saldo"]} for row in result]
    
    await conn.close()
    
    # Retorna a lista de usuários
    return usuarios

# Variável global para controlar o estado da aposta
estado_aposta = 'não iniciada'

@app.post("/aposta/iniciar")
async def iniciar_aposta():
    global estado_aposta
    if estado_aposta == 'em andamento':
        return {"erro": "Aposta já está em andamento."}
    
    estado_aposta = 'em andamento'
    return {"status": "Aposta iniciada com sucesso."}

@app.post("/aposta/finalizar")
async def finalizar_aposta():
    global estado_aposta
    if estado_aposta == 'não iniciada':
        return {"erro": "Nenhuma aposta em andamento."}
    
    estado_aposta = 'não iniciada'
    return {"status": "Aposta finalizada com sucesso."}

@app.get("/aposta/status")
async def status_aposta():
    return {"status": estado_aposta}
