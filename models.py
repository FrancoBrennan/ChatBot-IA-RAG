from sqlalchemy import (
    Column, Integer, String, Text, Boolean, TIMESTAMP, DateTime,
    ForeignKey, text
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import BIGINT as MySQLBigInt
from database import Base
from datetime import datetime

class Usuario(Base):
    __tablename__ = "usuarios"
    # id en DB es BIGINT UNSIGNED -> mapeamos igual
    id = Column(MySQLBigInt(unsigned=True), primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    nombre = Column(String(190))
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, nullable=False, server_default=text("0"))
    activo = Column(Boolean, nullable=False, server_default=text("1"))
    creado_en = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Relación con conversaciones del usuario
    conversaciones = relationship(
        "Conversacion",
        back_populates="usuario",
        cascade="all, delete-orphan"
    )

class Documento(Base):
    __tablename__ = "documentos"
    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String(255), nullable=False)
    fecha_subida = Column(DateTime, default=datetime.utcnow)
    texto_limpio = Column(Text)

class Conversacion(Base):
    __tablename__ = "conversaciones"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    # >>> NUEVO: owner de la conversación (FK a usuarios.id BIGINT UNSIGNED)
    user_id = Column(MySQLBigInt(unsigned=True), ForeignKey("usuarios.id"), nullable=False, index=True)
    usuario = relationship("Usuario", back_populates="conversaciones")

    mensajes = relationship(
        "Mensaje",
        back_populates="conversacion",
        cascade="all, delete-orphan"
    )

class Mensaje(Base):
    __tablename__ = "mensajes"
    id = Column(Integer, primary_key=True, index=True)
    contenido = Column(Text)
    rol = Column(String)  # "user" | "assistant"
    fecha = Column(DateTime, default=datetime.utcnow)

    conversacion_id = Column(Integer, ForeignKey("conversaciones.id"))
    conversacion = relationship("Conversacion", back_populates="mensajes")
