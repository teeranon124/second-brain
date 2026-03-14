import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

async def check_db():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client.second_brain
    
    nodes_count = await db.nodes.count_documents({})
    links_count = await db.links.count_documents({})
    
    print(f"📊 Database: {nodes_count} nodes, {links_count} links")
    
    # Sample nodes
    nodes = await db.nodes.find().limit(10).to_list(length=10)
    print("\n📝 Sample Nodes:")
    for node in nodes:
        label = node.get("label", "No label")[:50]
        print(f"  - {label}")
    
    # Check for NVDA
    nvda_query = {
        "$or": [
            {"label": {"$regex": "nvda", "$options": "i"}},
            {"label": {"$regex": "nvidia", "$options": "i"}},
            {"content": {"$regex": "nvda", "$options": "i"}},
        ]
    }
    nvda_nodes = await db.nodes.find(nvda_query).limit(5).to_list(length=5)
    
    print(f"\n🔍 NVDA/NVIDIA nodes: {len(nvda_nodes)}")
    for node in nvda_nodes:
        print(f"  ✅ {node.get('label', '?')}")
        print(f"     ID: {node['_id']}")
    
    # Check links
    if links_count > 0:
        links = await db.links.find().limit(5).to_list(length=5)
        print(f"\n🔗 Sample Links:")
        for link in links:
            fwd = link.get("forward_label", "?")
            bwd = link.get("backward_label", "?")
            print(f"  - {fwd} (reverse: {bwd})")
    else:
        print("\n❌ No links in database!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_db())
