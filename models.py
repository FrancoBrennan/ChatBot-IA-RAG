from sqlalchemy import Column, Integer, String, DateTime, Text
from database import Base
from datetime import datetime

class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String(255), nullable=False)
    fecha_subida = Column(DateTime, default=datetime.utcnow)
    texto_limpio = Column(Text)
