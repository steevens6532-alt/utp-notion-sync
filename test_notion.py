import os
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    raise ValueError(
        "Falta NOTION_TOKEN o NOTION_DATABASE_ID en el archivo .env"
    )

url = "https://api.notion.com/v1/pages"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

data = {
    "parent": {
        "database_id": DATABASE_ID
    },
    "properties": {
        "Actividad": {
            "title": [
                {
                    "text": {
                        "content": "PRUEBA UTP SYNC"
                    }
                }
            ]
        },
        "Curso": {
            "select": {
                "name": "SISTEMAS OPERATIVOS"
            }
        },
        "Entrega": {
            "date": {
                "start": "2026-12-13T23:59:00-05:00"
            }
        },
        "Tipo": {
            "select": {
                "name": "EVALUATION"
            }
        },
        "Semana": {
            "number": 18
        },
        "UTP ID": {
            "rich_text": [
                {
                    "text": {
                        "content": "TEST-001"
                    }
                }
            ]
        },
        "Estado UTP": {
            "rich_text": [
                {
                    "text": {
                        "content": "PROGRAMMED"
                    }
                }
            ]
        },
        "Course ID": {
            "rich_text": [
                {
                    "text": {
                        "content": "TEST-COURSE"
                    }
                }
            ]
        }
    }
}

response = requests.post(
    url,
    headers=headers,
    json=data,
    timeout=30
)

print("HTTP:", response.status_code)

if response.status_code == 200:
    print("✅ Tarea creada correctamente en Notion.")
    print("Page ID:", response.json()["id"])
else:
    print("❌ Error de Notion:")
    print(response.text)