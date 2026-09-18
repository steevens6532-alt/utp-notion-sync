# 🎓 UTP Academic Sync

Automatización en Python para sincronizar actividades académicas de **UTP+Class** con **Notion** y **Google Calendar**.

El proyecto obtiene tareas, evaluaciones y otras actividades desde UTP+Class, elimina duplicados, interpreta su estado y mantiene actualizados los registros en Notion y los eventos relevantes en Google Calendar.

> ⚠️ Proyecto no oficial y no afiliado a la Universidad Tecnológica del Perú.

---

## ✨ Características

- Obtención automática de actividades desde UTP+Class.
- Eliminación de duplicados mediante `activityId`.
- Sincronización con una base de datos de Notion.
- Sincronización de tareas y evaluaciones con Google Calendar.
- Actualización automática cuando cambia:
  - título;
  - fecha de entrega;
  - curso;
  - tipo de actividad;
  - semana;
  - estado.
- Estados automáticos en Notion:
  - `DELIVERED` → `Completada`
  - actividad vencida no entregada → `Vencida`
  - actividad futura → `Por Hacer`
- Recordatorios en Google Calendar.
- Modo `DRY_RUN` para probar la sincronización sin modificar datos.
- Uso de variables de entorno para evitar exponer credenciales.
- Soporte para distintos tipos de actividad:
  - `HOMEWORK`
  - `EVALUATION`
  - `FORUM`
  - entre otros.

---

## 🧩 Arquitectura

```text
                    UTP+Class
                        │
                        ▼
                 Python Sync Engine
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
          Notion              Google Calendar
             │                     │
       Todas las tareas       HOMEWORK / EVALUATION
       Estados                Deadlines
       Cursos                 Recordatorios
       Fechas                 Actualizaciones

```

## 📂 Estructura del proyecto
utp-sync/
│
├── src/
│   └── sync.py
│
├── secrets/
│   └── .gitkeep
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── LICENSE
Los archivos sensibles no deben subirse al repositorio.

## ⚙️ Requisitos
- Python 3.10 o superior
- Cuenta de UTP+Class
- Cuenta de Notion
- Cuenta de Google
- Google Calendar API habilitada
- Integración de Notion creada
## 📦 Instalación

Clona el repositorio:
git clone https://github.com/TU_USUARIO/utp-sync.git
cd utp-sync
Crea un entorno virtual.
Windows
python -m venv .venv
.venv\Scripts\activate
Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
Instala las dependencias:
pip install -r requirements.txt

## 📚 Dependencias
El archivo requirements.txt debe incluir:
requests
python-dotenv
google-api-python-client
google-auth-httplib2
google-auth-oauthlib

## 🔐 Variables de entorno
Copia:
.env.example
como:
.env
y completa tus credenciales.
Ejemplo:
# =========================
# UTP+CLASS
# =========================

UTP_TOKEN=your_utp_access_token
UTP_USER_ID=your_utp_user_id
UTP_TENANT_ID=your_utp_tenant_id


# =========================
# NOTION
# =========================

NOTION_TOKEN=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id


# =========================
# GOOGLE CALENDAR
# =========================

GOOGLE_CALENDAR_ID=your_google_calendar_id
Nunca subas tu archivo .env a GitHub.

## 🟦 Configuración de Notion
Crea una base de datos con las siguientes propiedades:
Propiedad	Tipo
Actividad	Title
Curso	Select
Entrega	Date
Estado	Status
Tipo	Select
Semana	Number
UTP ID	Text
Estado UTP	Text
Course ID	Text


## Estados recomendados:
Por Hacer
Completada
Vencida
Después conecta la integración de Notion a esa base de datos.
📅 Configuración de Google Calendar
Crea un proyecto en Google Cloud y habilita:
Google Calendar API
Crea un OAuth Client de tipo:
Desktop App
Descarga el archivo de credenciales y guárdalo localmente como:
secrets/credentials.json
En la primera ejecución se abrirá el navegador para autorizar tu cuenta.
Después se generará:
secrets/google_token.json
Ambos archivos deben permanecer fuera del repositorio.

## ▶️ Ejecución
Desde la raíz del proyecto:
python src/sync.py
🧪 Modo DRY RUN
El proyecto incluye un modo de prueba:
DRY_RUN = True
Cuando está activado:
UTP+Class → se consulta normalmente
Notion → no se modifica
Google Calendar → no se modifica
Ejemplo:

===== UTP → NOTION + GOOGLE CALENDAR =====

🧪 MODO PRUEBA ACTIVADO

📡 Consultando UTP+Class...
📚 Actividades únicas UTP: 76

🔎 Consultando Notion...
🗃️ Actividades existentes: 76

📅 Conectando Google Calendar...
📅 Eventos existentes: 41

===== RESUMEN =====

Notion
➕ Crear: 0
🔄 Actualizar: 0
⏭️ Sin cambios: 76

Google Calendar
📅 Crear: 0
🔄 Actualizar: 0
⏭️ Sin cambios: 41

❌ Errores: 0
Para realizar cambios reales:
DRY_RUN = False
🧠 Lógica de estados
El estado de cada actividad se calcula automáticamente.
Actividad entregada
UTP studentStatus = DELIVERED
se convierte en:
Completada
Actividad pendiente y vencida
Fecha de entrega < fecha actual
se convierte en:
Vencida
Actividad futura
Fecha de entrega > fecha actual
se convierte en:
Por Hacer

## 📅 Filtro de Google Calendar
Por defecto se pueden sincronizar solo actividades relevantes:
CALENDAR_TYPES = {
    "HOMEWORK",
    "EVALUATION",
}
Así Notion puede conservar todas las actividades, mientras Google Calendar muestra únicamente tareas y evaluaciones con fechas límite.

## 🔁 Prevención de duplicados
Cada actividad de UTP+Class posee un identificador único:
activityId
Ese ID se guarda en Notion como:
UTP ID
y en Google Calendar como una propiedad privada:
utp_id
Esto permite determinar si una actividad:
no existe → CREATE

ya existe y cambió → UPDATE

ya existe y no cambió → SKIP

## 🔔 Recordatorios
Los eventos creados en Google Calendar incluyen recordatorios configurables.
Actualmente:
24 horas antes
2 horas antes
Estos valores se pueden modificar en sync.py.

## 🔒 Seguridad
Nunca subas los siguientes archivos:
.env
secrets/credentials.json
secrets/google_token.json
Ejemplo de .gitignore:
.env

secrets/*
!secrets/.gitkeep

__pycache__/
*.pyc

.venv/
venv/

.vscode/
.idea/

.DS_Store
Thumbs.db
Si una credencial fue publicada accidentalmente, debe considerarse comprometida y ser reemplazada.

## ⚠️ Limitaciones
UTP+Class no dispone, hasta donde se ha identificado públicamente, de una API oficial documentada para desarrolladores externos.
Este proyecto utiliza endpoints utilizados por la propia aplicación web de UTP+Class.
Por esta razón:
- cambios internos en UTP+Class pueden romper la integración;
- los tokens de autenticación pueden expirar;
- actualmente puede ser necesario renovar manualmente el token de UTP;
- el proyecto no solicita ni almacena la contraseña del usuario.

## 🚧 Roadmap
Posibles mejoras futuras:
- Renovación automática del token UTP.
- Ejecución automática en VPS.
- Multiusuario.
- OAuth para múltiples cuentas Google.
- Integración OAuth con Notion.
- Interfaz web.
- Dashboard de sincronización.
- Configuración personalizada por usuario.
- Notificaciones de nuevas actividades.
- Sincronización de clases con Google Calendar.
- Extensión de navegador para UTP+Class.
- Dockerización.
- Logs persistentes.
- Tests automatizados.

## 🛠️ Tecnologías utilizadas
- Python
- REST APIs
- OAuth 2.0
- OpenID Connect
- Google Calendar API
- Notion API
- Requests
- python-dotenv
  
## 🎯 Objetivo del proyecto
El objetivo es evitar que un estudiante tenga que copiar manualmente las tareas publicadas en UTP+Class hacia sus herramientas personales de organización.
El flujo esperado es:
Profesor publica actividad
        ↓
UTP+Class
        ↓
Python Sync
        ↓
Notion + Google Calendar
        ↓
Actividad disponible automáticamente

## 📌 Disclaimer
Este proyecto:
- no es oficial;
- no está afiliado a UTP;
- no representa a la Universidad Tecnológica del Perú;
- está desarrollado con fines educativos y personales;
- utiliza únicamente datos correspondientes a la cuenta autenticada por el propio usuario.
El usuario es responsable de utilizar el software de acuerdo con los términos y políticas de las plataformas involucradas.
## 👨‍💻 Autor
Steevens Vargas
Software Engineering Student
GitHub: @steevens6532-alt
## 📄 Licencia
Este proyecto puede distribuirse bajo la licencia MIT.
Consulta el archivo:
LICENSE
para más información.
