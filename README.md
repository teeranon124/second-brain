# Second Brain - Graph RAG System

ระบบ Graph Retrieval Augmented Generation (GraphRAG) แบบ Full-Stack พร้อม Vector Database

## 🌟 Features

- **📊 3D Graph Visualization** - แสดงกราฟความรู้แบบ 3 มิติ
- **🔍 Vector Search** - ค้นหาความหมายด้วย Dense Retrieval
- **🧠 AI-Powered Extraction** - สกัดความรู้จากข้อความยาวด้วย Gemini AI
- **🔄 BFS Traversal** - สำรวจกราฟแบบ Breadth-First Search
- **💬 GraphRAG Chat** - ตอบคำถามจากกราฟความรู้
- **📱 Responsive UI** - ออกแบบให้ใช้งานง่าย

## 🏗️ Architecture

```
second-brain-n8n/
├── backend/                 # Python FastAPI Backend
│   ├── app/
│   │   ├── api/            # API Routes
│   │   ├── db/             # Database Connections
│   │   ├── models/         # Pydantic Models
│   │   ├── services/       # Business Logic
│   │   └── main.py         # FastAPI App
│   ├── scripts/            # Utility Scripts
│   ├── requirements.txt
│   └── README.md
│
├── second-brain-ui/        # React Frontend
│   ├── src/
│   │   ├── App.jsx         # Main Component
│   │   └── ...
│   ├── package.json
│   └── README.md
│
├── docker-compose.yml      # Qdrant Container
└── README.md              # This file
```

## 🚀 Quick Start

### 1. Setup Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# แก้ไข .env ใส่ MongoDB URI และ Gemini API Key

# Start Qdrant (Vector Database)
docker-compose up -d

# Seed initial data
python scripts/seed_database.py

# Run backend
python run.py
```

Backend จะเปิดที่: **http://localhost:8000**

### 2. Setup Frontend

```bash
cd second-brain-ui

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend จะเปิดที่: **http://localhost:5173**

## 📊 Database Design

### MongoDB Collections

#### 1. **nodes** - Graph Nodes
```javascript
{
  _id: "node_xxx",
  label: "ชื่อโหนด",
  type: "Concept | Process | Entity | ...",
  content: "คำอธิบาย",
  color: "#hex",
  base_val: 15,
  created_at: ISODate(),
  updated_at: ISODate()
}
```

**Indexes:**
- `label` (text)
- `type`
- `created_at`
- Full-text: `(label, content)`

#### 2. **links** - Graph Edges
```javascript
{
  _id: "link_xxx",
  source: "node_id",
  target: "node_id",
  label: "กริยาไปข้างหน้า",
  label_reverse: "กริยาย้อนกลับ",
  curvature: 0.0,
  created_at: ISODate()
}
```

**Indexes:**
- `source`
- `target`
- `(source, target)` (unique)

#### 3. **chat_history** - Conversation Logs
```javascript
{
  _id: "chat_xxx",
  session_id: "uuid",
  messages: [
    {
      role: "user|ai",
      text: "...",
      sources: ["node1", "node2"],
      timestamp: ISODate()
    }
  ],
  created_at: ISODate()
}
```

#### 4. **query_logs** - Analytics
```javascript
{
  query: "คำถาม",
  query_hash: 123456,
  starting_nodes: ["id1", "id2"],
  nodes_explored: ["id1", "id2", "id3"],
  query_time_ms: 234.56,
  timestamp: ISODate()
}
```

### Qdrant Collection

#### **graph_nodes** - Vector Embeddings
```python
{
  id: "node_id",
  vector: [0.123, 0.456, ...],  # 384 dimensions
  payload: {
    label: "ชื่อโหนด",
    type: "Concept",
    content: "คำอธิบาย"
  }
}
```

**Configuration:**
- Vector Size: 384 (all-MiniLM-L6-v2)
- Distance Metric: Cosine Similarity
- Index Type: HNSW

## 🧠 GraphRAG Pipeline

### 1. Dense Retrieval
```
User Query
    ↓
Generate Embedding (Sentence Transformer)
    ↓
Vector Search (Qdrant)
    ↓
Top-K Similar Nodes
```

### 2. BFS Traversal
```
Starting Nodes
    ↓
Explore Neighbors (depth 1-3)
    ↓
Collect Context
    ↓
Build Knowledge Graph
```

### 3. Answer Generation
```
Context + Query
    ↓
Gemini API
    ↓
Natural Language Answer
```

## 📡 API Endpoints

### Graph Operations
- `GET /api/graph` - ดึง graph ทั้งหมด
- `POST /api/nodes` - สร้างโหนด
- `PUT /api/nodes/{id}` - แก้ไขโหนด
- `DELETE /api/nodes/{id}` - ลบโหนด
- `POST /api/links` - สร้าง link

### Query & RAG
- `POST /api/query` - Query graph ด้วย GraphRAG
- `POST /api/query/extract` - Extract entities จากข้อความ

### Health Check
- `GET /health` - ตรวจสอบสถานะระบบ
- `GET /docs` - API Documentation (Swagger)

## 🔧 Configuration

### Backend (.env)
```bash
# MongoDB Atlas
MONGODB_URI=mongodb+srv://<user>:<pass>@cluster0.xxx.mongodb.net/
MONGODB_DB_NAME=second_brain

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Gemini AI
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash

# API
API_PORT=8000
CORS_ORIGINS=http://localhost:5173
```

### Frontend (.env.local)
```bash
VITE_API_URL=http://localhost:8000
```

## 📊 Scaling Strategy

### Horizontal Scaling
- **Backend**: Deploy multiple FastAPI instances behind load balancer
- **MongoDB Atlas**: Auto-scaling clusters
- **Qdrant**: Distributed mode with sharding

### Vertical Scaling
- **Embeddings**: Cache frequently used embeddings
- **BFS**: Limit max depth and node exploration
- **Database**: MongoDB indexes + connection pooling

### Caching Layer
```
Redis Layer
    ↓
- Frequent Queries
- Session Data
- Rate Limiting
```

## 🐛 Troubleshooting

### Backend Issues

**MongoDB Connection Failed**
```bash
# ตรวจสอบ connection string
echo $MONGODB_URI

# Test connection
python -c "from pymongo import MongoClient; MongoClient('your_uri').admin.command('ping')"
```

**Qdrant Not Running**
```bash
# Start Qdrant
docker-compose up -d qdrant

# Check status
curl http://localhost:6333/health
```

**Slow Embedding Generation**
```bash
# Model จะ download ครั้งแรก (~100MB)
# ตรวจสอบ: ~/.cache/torch/sentence_transformers/
```

### Frontend Issues

**API Connection Failed**
- ตรวจสอบ CORS settings ใน backend
- ตรวจสอบ `VITE_API_URL` ใน `.env.local`

## 📚 Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: MongoDB Atlas
- **Vector DB**: Qdrant
- **AI/LLM**: Google Gemini
- **Embeddings**: Sentence Transformers
- **Language**: Python 3.10+

### Frontend
- **Framework**: React + Vite
- **3D Rendering**: 3D Force Graph
- **Styling**: Tailwind CSS
- **Icons**: Lucide React

## 📄 License

MIT

## 🤝 Contributing

ยินดีรับ Pull Requests!

1. Fork the project
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

## 📞 Contact

สำหรับคำถามและข้อเสนอแนะ กรุณาเปิด Issue ใน GitHub
