# Second Brain GraphRAG Backend

Backend สำหรับระบบ Graph Retrieval Augmented Generation (GraphRAG) พร้อม Vector Database

## 🏗️ Technology Stack

- **Framework**: FastAPI (Python 3.10+)
- **Database**: MongoDB Atlas (Document Store)
- **Vector Database**: Qdrant (Semantic Search)
- **AI/LLM**: Google Gemini API
- **Embeddings**: Sentence Transformers

## 📊 Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   MongoDB   │     │   Qdrant    │     │   Gemini    │
│   (Graph)   │◄────┤  (Vectors)  │◄────┤     AI      │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                    ▲                    ▲
       │                    │                    │
       └───────────┬────────┴────────────────────┘
                   │
            ┌──────▼──────┐
            │   FastAPI   │
            │   Backend   │
            └──────┬──────┘
                   │
            ┌──────▼──────┐
            │   React     │
            │  Frontend   │
            └─────────────┘
```

## 🚀 Setup & Installation

### 1. Prerequisites

- Python 3.10+
- MongoDB Atlas Account
- (Optional) Docker for Qdrant

### 2. Install Dependencies

```bash
cd backend

# Using pip
pip install -r requirements.txt

# Or using Poetry
poetry install
```

### 3. Configuration

สร้างไฟล์ `.env` จาก `.env.example`:

```bash
cp .env.example .env
```

แก้ไข `.env` และใส่ข้อมูลของคุณ:

```bash
# MongoDB Atlas
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.sk37lbc.mongodb.net/
MONGODB_DB_NAME=second_brain

# Qdrant (Local or Cloud)
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Gemini API
GEMINI_API_KEY=your_api_key_here
```

### 4. Run Qdrant (Vector Database)

#### Option A: Docker (แนะนำ)

```bash
docker run -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
```

#### Option B: Qdrant Cloud

ใช้ [Qdrant Cloud](https://qdrant.tech/cloud/) และตั้งค่า:
- `QDRANT_USE_HTTPS=true`
- `QDRANT_API_KEY=your_key`

### 5. Seed Initial Data

```bash
python scripts/seed_database.py
```

### 6. Run Backend

```bash
# Development mode (with auto-reload)
python run.py

# Or using uvicorn directly
uvicorn app.main:app --reload --port 8000
```

API จะเปิดที่: **http://localhost:8000**

API Docs: **http://localhost:8000/docs**

## 📡 API Endpoints

### Nodes

- `POST /api/nodes` - สร้างโหนดใหม่
- `GET /api/nodes` - ดึงโหนดทั้งหมด
- `GET /api/nodes/{id}` - ดึงโหนดเดียว
- `GET /api/nodes/{id}/relations` - ดึงโหนดพร้อม relationships
- `PUT /api/nodes/{id}` - อัปเดตโหนด
- `DELETE /api/nodes/{id}` - ลบโหนด

### Links

- `POST /api/links` - สร้าง link ใหม่
- `GET /api/links` - ดึง links ทั้งหมด
- `PUT /api/links/{id}` - อัปเดต link
- `DELETE /api/links/{id}` - ลบ link

### Graph

- `GET /api/graph` - ดึง graph ทั้งหมด (nodes + links)
- `POST /api/graph/bulk/nodes` - สร้างหลายโหนดพร้อมกัน
- `POST /api/graph/bulk/links` - สร้างหลาย links พร้อมกัน

### Query (GraphRAG)

- `POST /api/query` - Query graph ด้วย GraphRAG
- `POST /api/query/extract` - แยก entities จากข้อความ

## 🧠 GraphRAG Pipeline

ระบบใช้ 3 อัลกอริทึมหลัก:

### 1. Dense Retrieval (Vector Search)
```
Query → Embedding → Qdrant Search → Top-K Nodes
```
Based on: Karpukhin et al., 2020

### 2. BFS Traversal
```
Starting Nodes → Explore Neighbors → Max Depth
```
Based on: Goldberg, 2005

### 3. Entity Matching
```
Label Similarity → Deduplication → Merge
```
Based on: Mudgal et al., 2018

## 📦 Database Schema

### MongoDB Collections

#### `nodes`
```json
{
  "_id": "node_123",
  "label": "มหาสมุทร",
  "type": "Hub",
  "content": "น้ำเค็มที่ปกคลุมโลก...",
  "color": "#0ea5e9",
  "base_val": 20,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### `links`
```json
{
  "_id": "link_456",
  "source": "node_123",
  "target": "node_789",
  "label": "กัดเซาะ",
  "label_reverse": "ถูกกัดเซาะโดย",
  "curvature": 0.0,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Qdrant Collections

#### `graph_nodes`
- **Vector Size**: 384 (all-MiniLM-L6-v2)
- **Distance**: Cosine
- **Payload**: `{label, type, content}`

## 🔧 Development

### Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app
│   ├── config.py         # Configuration
│   ├── models/           # Pydantic models
│   ├── services/         # Business logic
│   │   ├── embedding_service.py
│   │   ├── gemini_service.py
│   │   ├── graph_service.py
│   │   └── rag_service.py
│   ├── api/              # API routes
│   └── db/               # Database connections
├── scripts/
│   └── seed_database.py
├── requirements.txt
├── pyproject.toml
└── run.py
```

### Testing

```bash
# Install dev dependencies
poetry install --with dev

# Run tests
pytest

# Type checking
mypy app/

# Code formatting
black app/
```

## 🐛 Troubleshooting

### MongoDB Connection Error
- ตรวจสอบ connection string ใน `.env`
- เช็ค IP whitelist ใน MongoDB Atlas
- ตรวจสอบ username/password

### Qdrant Not Available
- ระบบจะ fallback ไปใช้ Gemini-based retrieval
- ถ้าต้องการ vector search ต้องรัน Qdrant

### Embedding Model Download
- ครั้งแรกจะใช้เวลา download model (~100MB)
- Model จะถูก cache ไว้ใน `~/.cache/torch/`

## 📝 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URI` | MongoDB connection string | - |
| `MONGODB_DB_NAME` | Database name | `second_brain` |
| `QDRANT_HOST` | Qdrant host | `localhost` |
| `QDRANT_PORT` | Qdrant port | `6333` |
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |
| `API_PORT` | Backend port | `8000` |

## 📚 References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Sentence Transformers](https://www.sbert.net/)
- [Google Gemini API](https://ai.google.dev/)

## 📄 License

MIT
