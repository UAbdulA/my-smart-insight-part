from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Берем адрес базы из настроек
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base() # Это "родитель" для всех будущих таблиц

# Добавь это в конец твоего файла database.py
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()