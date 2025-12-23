# 🤖 Chatbot IA con Conocimiento Restringido (RAG)

Aplicación web full-stack de **chatbot con Inteligencia Artificial**, diseñada para responder **exclusivamente** en base a documentos PDF cargados por un administrador.  
Implementa una arquitectura **RAG (Retrieval-Augmented Generation)** con controles anti-alucinación, autenticación JWT, conversaciones persistentes y panel de administración.

---

## 🎯 Objetivo

- Responder solo con **conocimiento validado**
- Evitar alucinaciones del LLM
- Mantener **trazabilidad por documento y página**
- Servir como base para sistemas de **soporte técnico, help desk o educación**

---

## 🧠 Arquitectura general

1. Admin sube PDFs
2. Backend extrae texto por página
3. Se generan chunks + embeddings
4. Indexación híbrida:
   - FAISS (dense)
   - BM25 (sparse)
5. Consulta del usuario
6. Recuperación + filtros de seguridad
7. Generación de respuesta con LLM
8. Persistencia de conversación

---

## 🛠️ Tecnologías

### Backend
- Python + FastAPI
- MySQL
- SQLAlchemy
- LangChain
- FAISS
- BM25
- HuggingFace Embeddings
- OpenAI / OpenRouter (LLM)
- JWT (auth)

### Frontend
- React
- React Router
- Axios
- Context API
- CSS puro

---

## 📂 Estructura del proyecto


```txt
backend/
├── main.py
├── database.py
├── models.py
├── auth.py
├── rag_chain.py
├── retrievers.py
├── rerank.py
├── vectorstore_langchain.py
├── embeddings_setup.py
├── text_pipeline.py
├── utils.py
├── uploads/        # PDFs
└── indices/        # FAISS + lexicon.json

frontend/
├── src/
│   ├── api/
│   │   ├── axios.js
│   │   ├── adminUsers.js
│   │   └── conversations.js
│   ├── context/
│   │   └── AuthContext.jsx
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Chat.jsx
│   │   └── AdminPanel.jsx
│   ├── components/
│   │   ├── Sidebar.jsx
│   │   ├── ChatMessage.jsx
│   │   └── PDFTable.jsx
│   ├── routes/
│   │   └── PrivateRoute.jsx
│   ├── App.jsx
│   └── main.jsx
```

## 📡 Endpoints de la API

### 🔐 Autenticación
- **POST `/login`**: inicia sesión y devuelve un token JWT.
- **GET `/me`**: devuelve los datos del usuario autenticado.

### 👤 Administración de usuarios (solo admin)
- **POST `/admin/users`**: crea un nuevo usuario.
- **GET `/admin/users`**: lista todos los usuarios.
- **PATCH `/admin/users/{user_id}/estado`**: activa o desactiva un usuario.
- **DELETE `/admin/users/{user_id}`**: elimina un usuario.

### 📄 Administración de documentos (solo admin)
- **POST `/upload`**: sube un PDF y reindexa automáticamente.
- **GET `/listar-datasets`**: lista los documentos cargados.
- **DELETE `/eliminar-dataset/{id}`**: elimina un documento y reindexa.
- **POST `/actualizar-documentos`**: reindexa manualmente todos los documentos.

### 💬 Conversaciones (usuario autenticado)
- **POST `/conversaciones`**: crea una nueva conversación.
- **GET `/conversaciones`**: lista las conversaciones del usuario.
- **GET `/conversaciones/{conv_id}`**: obtiene una conversación con sus mensajes.
- **POST `/conversaciones/{conv_id}/mensaje`**: agrega un mensaje y devuelve la respuesta del chatbot.
- **DELETE `/conversaciones/{conv_id}`**: elimina una conversación.

### 🔎 Consulta rápida
- **GET `/buscar`**: realiza una consulta directa al chatbot sin guardar conversación.

## 🖼️ Capturas de la aplicación

### Login

<img width="1819" height="871" alt="image" src="https://github.com/user-attachments/assets/f17886ca-6cd2-4301-9db3-9da54597807a" />

### Panel de Administración
Gestión de usuarios y datasets PDF.

<img width="1803" height="874" alt="image" src="https://github.com/user-attachments/assets/5a754537-4e1d-448a-842d-f632081ab121" />

### Chat con IA (RAG)
Conversaciones persistentes con respuestas trazables por documento.

<img width="1824" height="866" alt="image" src="https://github.com/user-attachments/assets/87cc6053-b361-4dc2-aa51-238f31f4d0f8" />
