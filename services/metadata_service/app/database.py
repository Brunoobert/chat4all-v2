

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 1. URL de Conexão com o CockroachDB
# Formato: "cockroachdb://[user]:[password]@[host]:[port]/[database]"
# Usamos 'cockroachdb' como o nome do host (o nome do serviço no docker-compose)
# Por defeito, o user é 'root' e não tem password.
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"
)

# 2. O 'Engine' é o coração da conexão do SQLAlchemy
engine = create_engine(DATABASE_URL)

# 3. A 'SessionLocal' é a fábrica de sessões (conexões) com o banco
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 'Base' é a classe base que os nossos modelos (tabelas) vão herdar
Base = declarative_base()

# Função 'helper' para injetar a sessão nos nossos endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()