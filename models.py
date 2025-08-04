from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String(255), nullable=False)
    fecha_subida = Column(DateTime, default=datetime.utcnow)
    texto_limpio = Column(Text)

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)

class Conversacion(Base):
    __tablename__ = "conversaciones"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    mensajes = relationship("Mensaje", back_populates="conversacion")

class Mensaje(Base):
    __tablename__ = "mensajes"
    id = Column(Integer, primary_key=True, index=True)
    contenido = Column(Text)
    rol = Column(String)  # "user" o "assistant"
    fecha = Column(DateTime, default=datetime.utcnow)
    conversacion_id = Column(Integer, ForeignKey("conversaciones.id"))
    conversacion = relationship("Conversacion", back_populates="mensajes")