import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

async def check_links():
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client.second_brain
    
    # Get NVDA node
    nvda = await db.nodes.find_one({"label": "NVDA"})
    if not nvda:
        print("❌ NVDA node not found")
        return
    
    nvda_id = str(nvda["_id"])
    print(f"✅ NVDA Node ID: {nvda_id}")
    print(f"   Label: {nvda.get('label')}")
    print(f"   Content: {nvda.get('content', '')[:100]}")
    
    # Check all links
    print(f"\n🔗 Checking Links Collection Structure:")
    sample_link = await db.links.find_one()
    if sample_link:
        print(f"   Fields: {list(sample_link.keys())}")
        print(f"   Sample: {sample_link}")
    
    # Find links connected to NVDA
    print(f"\n🔍 Finding Links Connected to NVDA (ID: {nvda_id}):")
    
    # Try different ID formats
    from bson import ObjectId
    nvda_oid = nvda["_id"]
    
    links_from = await db.links.find({"source": nvda_oid}).to_list(length=10)
    links_to = await db.links.find({"target": nvda_oid}).to_list(length=10)
    
    print(f"\n📤 Outgoing Links (source = NVDA): {len(links_from)}")
    for link in links_from[:5]:
        target = await db.nodes.find_one({"_id": link["target"]})
        target_label = target.get("label", "?") if target else "Node not found"
        fwd = link.get("forward_label", "(no label)")
        print(f"   → {target_label} [{fwd}]")
    
    print(f"\n📥 Incoming Links (target = NVDA): {len(links_to)}")
    for link in links_to[:5]:
        source = await db.nodes.find_one({"_id": link["source"]})
        source_label = source.get("label", "?") if source else "Node not found"
        bwd = link.get("backward_label", "(no label)")
        print(f"   ← {source_label} [{bwd}]")
    
    # Check if ObjectId vs string mismatch
    print(f"\n🔬 ID Type Analysis:")
    print(f"   NVDA _id type: {type(nvda['_id'])}")
    if sample_link:
        print(f"   Link source type: {type(sample_link.get('source'))}")
        print(f"   Link target type: {type(sample_link.get('target'))}")
    
    # Check NVIDIA Corporation too
    print(f"\n🔍 Checking NVIDIA Corporation:")
    nvidia = await db.nodes.find_one({"label": "NVIDIA Corporation"})
    if nvidia:
        nvidia_links = await db.links.find({
            "$or": [
                {"source": nvidia["_id"]},
                {"target": nvidia["_id"]}
            ]
        }).to_list(length=10)
        print(f"   Links: {len(nvidia_links)}")
        for link in nvidia_links[:3]:
            source = await db.nodes.find_one({"_id": link["source"]})
            target = await db.nodes.find_one({"_id": link["target"]})
            source_label = source.get("label", "?") if source else "?"
            target_label = target.get("label", "?") if target else "?"
            fwd = link.get("forward_label", "(no label)")
            print(f"   {source_label} → {target_label} [{fwd}]")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_links())
