import sys
sys.path.insert(0, '.')

try:
    from app.api import quiz
    print("SUCCESS: Quiz module imported")
    print(f"Prefix: {quiz.router.prefix}")
    print(f"Routes: {len(quiz.router.routes)}")
    for route in quiz.router.routes:
        if hasattr(route, 'path'):
            print(f"  - {route.path}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
