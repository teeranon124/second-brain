"""Seed Initial Data to Database"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import mongodb, vector_db
from app.models import NodeCreate, LinkCreate
from app.services import get_graph_service


async def seed_initial_data():
    """Seed the database with initial sample data"""
    
    print("🌱 Seeding initial data...")
    
    # Connect to databases
    await mongodb.connect()
    await vector_db.connect()
    
    db = mongodb.get_database()
    service = get_graph_service(db)
    
    # Define initial nodes (from your existing data)
    initial_nodes = [
        NodeCreate(
            label="มหาสมุทร",
            type="Hub",
            content="น้ำเค็มที่ปกคลุมโลก เกิดจากการสะสมแร่ธาตุมานานหลายพันล้านปี",
            color="#0ea5e9",
            baseVal=20
        ),
        NodeCreate(
            label="หินบนบก",
            type="Entity",
            content="หินและแร่ธาตุต่างๆ ที่เป็นแหล่งกำเนิดไอออน เช่น โซเดียมและคลอไรด์",
            color="#94a3b8",
            baseVal=12
        ),
        NodeCreate(
            label="ฝนกรดอ่อน",
            type="Process",
            content="น้ำฝนที่มีฤทธิ์เป็นกรดอ่อนๆ จากคาร์บอนไดออกไซด์ในอากาศ ทำหน้าที่กัดเซาะหิน",
            color="#38bdf8",
            baseVal=10
        ),
        NodeCreate(
            label="เกลือ (NaCl)",
            type="Chemical",
            content="ไอออนที่ไหลจากแม่น้ำลงสู่ทะเลและเข้มข้นขึ้นเรื่อยๆ ผ่านการระเหยของน้ำ",
            color="#f8fafc",
            baseVal=10
        ),
        NodeCreate(
            label="ปะการัง",
            type="Animal",
            content="สัตว์ทะเลไม่มีกระดูกสันหลัง 'โพลิป' ที่สร้างหินปูนขึ้นปกป้องตัวเอง",
            color="#ec4899",
            baseVal=18
        ),
        NodeCreate(
            label="สภาวะโลกร้อน",
            type="Hub",
            content="อุณหภูมิน้ำทะเลที่สูงขึ้นเพียง 1-2 องศา ทำให้ปะการังเครียดจนเกิดการฟอกขาว",
            color="#f97316",
            baseVal=20
        ),
        NodeCreate(
            label="ปะการังฟอกขาว",
            type="Crisis",
            content="สภาวะที่ปะการังขับสาหร่ายซูแซนเทลลีออกไป ทิ้งไว้เพียงโครงสร้างหินปูนสีขาว",
            color="#ffffff",
            baseVal=12
        ),
    ]
    
    # Create nodes
    print("\n📌 Creating nodes...")
    created_nodes = {}
    
    for node_data in initial_nodes:
        try:
            node = await service.create_node(node_data)
            created_nodes[node_data.label] = node.id
            print(f"  ✅ Created: {node_data.label} (ID: {node.id})")
        except Exception as e:
            print(f"  ❌ Failed to create {node_data.label}: {e}")
    
    # Define initial links
    initial_links = [
        ("ฝนกรดอ่อน", "หินบนบก", "กัดเซาะ", "ถูกกัดเซาะโดย"),
        ("หินบนบก", "เกลือ (NaCl)", "ปล่อยแร่ธาตุ", "มาจาก"),
        ("เกลือ (NaCl)", "มหาสมุทร", "ไหลลงสู่", "รับแร่ธาตุจาก"),
        ("สภาวะโลกร้อน", "มหาสมุทร", "ทำให้น้ำร้อนขึ้น", "ได้รับความร้อนจาก"),
        ("สภาวะโลกร้อน", "ปะการังฟอกขาว", "เป็นสาเหตุหลักของ", "เกิดจาก"),
        ("ปะการังฟอกขาว", "ปะการัง", "ทำลาย", "ถูกทำลายโดย"),
        ("ปะการัง", "มหาสมุทร", "อาศัยอยู่ใน", "เป็นที่อยู่อาศัยของ"),
    ]
    
    # Create links
    print("\n🔗 Creating links...")
    
    for source_label, target_label, forward_label, backward_label in initial_links:
        if source_label in created_nodes and target_label in created_nodes:
            try:
                link_data = LinkCreate(
                    source=created_nodes[source_label],
                    target=created_nodes[target_label],
                    label=forward_label,
                    labelReverse=backward_label,
                )
                link = await service.create_link(link_data)
                print(f"  ✅ Linked: {source_label} → {target_label}")
            except Exception as e:
                print(f"  ❌ Failed to link {source_label} → {target_label}: {e}")
        else:
            print(f"  ⚠️ Skipped: {source_label} → {target_label} (nodes not found)")
    
    # Disconnect
    await mongodb.disconnect()
    await vector_db.disconnect()
    
    print("\n✅ Seeding complete!")
    print(f"   - Created {len(created_nodes)} nodes")
    print(f"   - MongoDB: {len(created_nodes)} documents")
    print(f"   - Vector DB: {len(created_nodes)} embeddings")


if __name__ == "__main__":
    asyncio.run(seed_initial_data())
