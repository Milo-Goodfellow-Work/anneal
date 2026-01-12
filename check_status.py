import asyncio
import os
import tomllib
from pathlib import Path
from aristotlelib import Project, ProjectStatus

async def main():
    # Load keys
    secrets_path = Path("secrets.toml")
    if secrets_path.exists():
        with secrets_path.open("rb") as f:
            secrets = tomllib.load(f)
            key = secrets.get("secrets", {}).get("ARISTOTLE_API_KEY")
            if key:
                os.environ["ARISTOTLE_API_KEY"] = key
    
    if not os.environ.get("ARISTOTLE_API_KEY"):
        print("Error: ARISTOTLE_API_KEY not found.")
        return

    print("Fetching recent projects...")
    projects, _ = await Project.list_projects(limit=5)
    
    if not projects:
        print("No projects found.")
        return

    print(f"{'ID':<40} | {'Status':<15} | {'Created'}")
    print("-" * 70)
    for p in projects:
        print(f"{p.project_id:<40} | {p.status.value:<15} | {p.created_at}")

if __name__ == "__main__":
    asyncio.run(main())
