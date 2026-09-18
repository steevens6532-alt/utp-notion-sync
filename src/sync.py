import os
import uuid

from pathlib import Path
from datetime import datetime, timedelta

import requests

from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

ENV_FILE = BASE_DIR / "config" / ".env"

GOOGLE_CREDENTIALS_FILE = (
    BASE_DIR
    / "secrets"
    / "credentials.json"
)

GOOGLE_TOKEN_FILE = (
    BASE_DIR
    / "secrets"
    / "google_token.json"
)


# ============================================================
# CARGAR .ENV
# ============================================================

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True
)


# ============================================================
# CONFIGURACIÓN
# ============================================================

UTP_TOKEN = os.getenv("UTP_TOKEN")
UTP_USER_ID = os.getenv("UTP_USER_ID")
UTP_TENANT_ID = os.getenv("UTP_TENANT_ID")

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

GOOGLE_CALENDAR_ID = os.getenv(
    "GOOGLE_CALENDAR_ID"
)


# ============================================================
# MODO PRUEBA
# ============================================================

# True:
#   no crea ni modifica nada en Notion / Google Calendar.
#
# False:
#   sincronización real.

DRY_RUN = False


# ============================================================
# GOOGLE CALENDAR - FILTRO
# ============================================================

# None = enviar TODAS las actividades con fecha a Calendar.
#
# Si quieres solamente tareas y evaluaciones:
#
# CALENDAR_TYPES = {
#     "HOMEWORK",
#     "EVALUATION",
# }
#
# Por ahora dejamos todas.

CALENDAR_TYPES = {"HOMEWORK", "EVALUATION"}


# ============================================================
# ENDPOINTS
# ============================================================

UTP_URL = (
    "https://api-pao.utpxpedition.com/"
    "course/student/calendar/activities"
)

NOTION_API = "https://api.notion.com/v1"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar"
]


# ============================================================
# VALIDAR CONFIGURACIÓN
# ============================================================

required_variables = {
    "UTP_TOKEN": UTP_TOKEN,
    "UTP_USER_ID": UTP_USER_ID,
    "UTP_TENANT_ID": UTP_TENANT_ID,
    "NOTION_TOKEN": NOTION_TOKEN,
    "NOTION_DATABASE_ID": NOTION_DATABASE_ID,
    "GOOGLE_CALENDAR_ID": GOOGLE_CALENDAR_ID,
}

missing = [
    name
    for name, value in required_variables.items()
    if not value
]

if missing:
    raise ValueError(
        "Faltan variables en .env: "
        + ", ".join(missing)
    )


# ============================================================
# UTILIDADES DE FECHA
# ============================================================

def normalize_date(date_string):
    """
    Normaliza fechas para comparar UTP, Notion y Google.

    Ignoramos segundos:
    23:59:00 == 23:59:59
    """

    if not date_string:
        return None

    try:

        date_string = date_string.replace(
            "Z",
            "+00:00"
        )

        dt = datetime.fromisoformat(
            date_string
        )

        return dt.strftime(
            "%Y-%m-%d %H:%M"
        )

    except ValueError:

        return date_string


def notion_date(date_string):
    """
    Convierte la fecha de UTP a ISO para Notion.

    Perú = UTC-5.
    """

    if not date_string:
        return None

    try:

        dt = datetime.fromisoformat(
            date_string
        )

        dt = dt.replace(
            second=0,
            microsecond=0
        )

        return (
            dt.strftime(
                "%Y-%m-%dT%H:%M:00"
            )
            + "-05:00"
        )

    except ValueError:

        return (
            date_string
            .replace(" ", "T")
            + "-05:00"
        )


# ============================================================
# ESTADO AUTOMÁTICO
# ============================================================

def calcular_estado(activity):
    """
    Estado en Notion:

    DELIVERED -> Completada

    No entregada + fecha pasada
    -> Vencida

    No entregada + fecha futura
    -> Por Hacer
    """

    estado_utp = (
        activity.get("estado_utp")
        or ""
    ).upper()

    fecha_entrega = activity.get(
        "fecha_entrega"
    )

    # UTP confirma que fue entregada
    if estado_utp == "DELIVERED":

        return "Completada"

    if not fecha_entrega:

        return "Por Hacer"

    try:

        entrega = datetime.fromisoformat(
            fecha_entrega
        )

        ahora = datetime.now()

        if entrega < ahora:

            return "Vencida"

        return "Por Hacer"

    except ValueError:

        return "Por Hacer"


# ============================================================
# UTP+CLASS
# ============================================================

def get_utp_activities():

    query_date = datetime.now().strftime(
        "%Y-%m-%d 00:00:00"
    )

    params = {
        "userId": UTP_USER_ID,
        "dateToQuery": query_date,
        "intervalMode": "period",
    }

    headers = {
        "accept": "*/*",

        "authorization":
            f"Bearer {UTP_TOKEN}",

        "origin":
            "https://class.utp.edu.pe",

        "referer":
            "https://class.utp.edu.pe/",

        "transaction-id":
            str(uuid.uuid4()),

        "user-id":
            UTP_USER_ID,

        "user-id-to-access":
            "",

        "user-role":
            "STUDENT",

        "user-role-to-access":
            "",

        "x-tenant-id":
            UTP_TENANT_ID,
    }

    response = requests.get(
        UTP_URL,
        params=params,
        headers=headers,
        timeout=30,
    )

    if response.status_code in (
        401,
        403
    ):

        raise RuntimeError(
            f"UTP rechazó la autenticación "
            f"({response.status_code}). "
            f"Probablemente el token expiró."
        )

    response.raise_for_status()

    data = response.json()

    payload = data.get("data")


    # ========================================================
    # LOCALIZAR ACTIVIDADES
    # ========================================================

    if isinstance(payload, list):

        activities = payload

    elif isinstance(payload, dict):

        if "activities" in payload:

            activities = payload[
                "activities"
            ]

        elif "events" in payload:

            activities = payload[
                "events"
            ]

        elif isinstance(
            payload.get("current_interval"),
            dict
        ):

            activities = (
                payload[
                    "current_interval"
                ]
                .get(
                    "events",
                    []
                )
            )

        else:

            activities = []

    else:

        activities = []


    # ========================================================
    # DEDUPLICAR
    # ========================================================

    unique = {}

    for activity in activities:

        metadata = (
            activity.get("metadata")
            or {}
        )

        activity_id = (
            metadata.get("activityId")
            or activity.get("id")
        )

        if not activity_id:
            continue

        unique[activity_id] = {

            "utp_id":
                activity_id,

            "titulo":
                activity.get("title")
                or "Actividad UTP",

            "curso":
                metadata.get(
                    "courseName"
                ),

            "fecha_entrega":
                (
                    metadata.get(
                        "activityFinishAt"
                    )
                    or activity.get(
                        "finishAt"
                    )
                ),

            "fecha_publicacion":
                metadata.get(
                    "activityPublishAt"
                ),

            "semana":
                metadata.get(
                    "weekNumber"
                ),

            "estado_utp":
                metadata.get(
                    "studentStatus"
                ),

            "tipo_actividad":
                metadata.get(
                    "activityType"
                ),

            "evaluacion":
                metadata.get(
                    "evaluationSystem"
                ),

            "course_id":
                metadata.get(
                    "courseId"
                ),
        }

    result = list(
        unique.values()
    )

    result.sort(
        key=lambda x:
        x.get("fecha_entrega")
        or "9999-12-31"
    )

    return result


# ============================================================
# NOTION - HEADERS
# ============================================================

def notion_headers():

    return {

        "Authorization":
            f"Bearer {NOTION_TOKEN}",

        "Content-Type":
            "application/json",

        "Notion-Version":
            "2022-06-28",
    }


# ============================================================
# NOTION - LEER EXISTENTES
# ============================================================

def get_existing_notion_tasks():

    url = (
        f"{NOTION_API}/databases/"
        f"{NOTION_DATABASE_ID}/query"
    )

    existing = {}

    has_more = True
    cursor = None

    while has_more:

        body = {
            "page_size": 100
        }

        if cursor:

            body[
                "start_cursor"
            ] = cursor

        response = requests.post(
            url,
            headers=notion_headers(),
            json=body,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        for page in data.get(
            "results",
            []
        ):

            properties = page.get(
                "properties",
                {}
            )

            utp_property = (
                properties.get(
                    "UTP ID",
                    {}
                )
            )

            rich_text = (
                utp_property.get(
                    "rich_text",
                    []
                )
            )

            if not rich_text:
                continue

            utp_id = "".join(

                item.get(
                    "plain_text",
                    ""
                )

                for item in rich_text

            ).strip()

            if utp_id:

                existing[
                    utp_id
                ] = page

        has_more = data.get(
            "has_more",
            False
        )

        cursor = data.get(
            "next_cursor"
        )

    return existing


# ============================================================
# NOTION - PROPIEDADES
# ============================================================

def build_properties(activity):

    properties = {

        "Actividad": {

            "title": [
                {
                    "text": {
                        "content":
                            activity[
                                "titulo"
                            ]
                    }
                }
            ]
        },

        "UTP ID": {

            "rich_text": [
                {
                    "text": {
                        "content":
                            activity[
                                "utp_id"
                            ]
                    }
                }
            ]
        },

        "Estado": {

            "status": {
                "name":
                    calcular_estado(
                        activity
                    )
            }
        },
    }


    if activity.get("curso"):

        properties[
            "Curso"
        ] = {

            "select": {
                "name":
                    activity[
                        "curso"
                    ]
            }
        }


    if activity.get(
        "fecha_entrega"
    ):

        properties[
            "Entrega"
        ] = {

            "date": {

                "start":
                    notion_date(
                        activity[
                            "fecha_entrega"
                        ]
                    )
            }
        }


    if activity.get(
        "tipo_actividad"
    ):

        properties[
            "Tipo"
        ] = {

            "select": {

                "name":
                    activity[
                        "tipo_actividad"
                    ]
            }
        }


    if activity.get(
        "semana"
    ) is not None:

        properties[
            "Semana"
        ] = {

            "number":
                activity[
                    "semana"
                ]
        }


    if activity.get(
        "estado_utp"
    ):

        properties[
            "Estado UTP"
        ] = {

            "rich_text": [
                {
                    "text": {
                        "content":
                            activity[
                                "estado_utp"
                            ]
                    }
                }
            ]
        }


    if activity.get(
        "course_id"
    ):

        properties[
            "Course ID"
        ] = {

            "rich_text": [
                {
                    "text": {
                        "content":
                            activity[
                                "course_id"
                            ]
                    }
                }
            ]
        }


    return properties


# ============================================================
# NOTION - CREAR
# ============================================================

def create_notion_task(activity):

    if DRY_RUN:

        print(
            "➕ NOTION: "
            f"[{activity['curso']}] "
            f"{activity['titulo']}"
        )

        return

    body = {

        "parent": {
            "database_id":
                NOTION_DATABASE_ID
        },

        "properties":
            build_properties(
                activity
            ),
    }

    response = requests.post(

        f"{NOTION_API}/pages",

        headers=notion_headers(),

        json=body,

        timeout=30,
    )

    response.raise_for_status()


# ============================================================
# NOTION - ACTUALIZAR
# ============================================================

def update_notion_task(
    page_id,
    activity
):

    if DRY_RUN:

        print(
            "🔄 NOTION: "
            f"[{activity['curso']}] "
            f"{activity['titulo']}"
        )

        return

    body = {

        "properties":
            build_properties(
                activity
            )
    }

    response = requests.patch(

        f"{NOTION_API}/pages/"
        f"{page_id}",

        headers=notion_headers(),

        json=body,

        timeout=30,
    )

    response.raise_for_status()


# ============================================================
# NOTION - NORMALIZAR
# ============================================================

def normalize_notion_page(page):

    properties = page.get(
        "properties",
        {}
    )


    def text_value(name):

        items = (
            properties.get(
                name,
                {}
            )
            .get(
                "rich_text",
                []
            )
        )

        return "".join(

            item.get(
                "plain_text",
                ""
            )

            for item in items
        )


    def title_value(name):

        items = (
            properties.get(
                name,
                {}
            )
            .get(
                "title",
                []
            )
        )

        return "".join(

            item.get(
                "plain_text",
                ""
            )

            for item in items
        )


    def select_value(name):

        value = (
            properties.get(
                name,
                {}
            )
            .get("select")
        )

        return (
            value.get("name")
            if value
            else None
        )


    def status_value(name):

        value = (
            properties.get(
                name,
                {}
            )
            .get("status")
        )

        return (
            value.get("name")
            if value
            else None
        )


    def date_value(name):

        value = (
            properties.get(
                name,
                {}
            )
            .get("date")
        )

        return (
            value.get("start")
            if value
            else None
        )


    return {

        "titulo":
            title_value(
                "Actividad"
            ),

        "curso":
            select_value(
                "Curso"
            ),

        "fecha_entrega":
            date_value(
                "Entrega"
            ),

        "estado":
            status_value(
                "Estado"
            ),

        "tipo_actividad":
            select_value(
                "Tipo"
            ),

        "semana":
            properties.get(
                "Semana",
                {}
            ).get(
                "number"
            ),

        "estado_utp":
            text_value(
                "Estado UTP"
            ),

        "course_id":
            text_value(
                "Course ID"
            ),
    }


# ============================================================
# NOTION - DETECTAR CAMBIOS
# ============================================================

def activity_changed(
    activity,
    notion_page
):

    current = normalize_notion_page(
        notion_page
    )

    expected_date = normalize_date(
        activity.get(
            "fecha_entrega"
        )
    )

    current_date = normalize_date(
        current.get(
            "fecha_entrega"
        )
    )

    expected_status = calcular_estado(
        activity
    )


    return any([

        current["titulo"]
        != activity.get(
            "titulo"
        ),

        current["curso"]
        != activity.get(
            "curso"
        ),

        current_date
        != expected_date,

        current["estado"]
        != expected_status,

        current["tipo_actividad"]
        != activity.get(
            "tipo_actividad"
        ),

        current["semana"]
        != activity.get(
            "semana"
        ),

        current["estado_utp"]
        != activity.get(
            "estado_utp"
        ),

        current["course_id"]
        != activity.get(
            "course_id"
        ),
    ])


# ============================================================
# GOOGLE CALENDAR - AUTENTICACIÓN
# ============================================================

def get_google_calendar_service():

    creds = None

    if GOOGLE_TOKEN_FILE.exists():

        creds = (
            Credentials.from_authorized_user_file(
            str(GOOGLE_TOKEN_FILE),
            GOOGLE_SCOPES
            )
        )


    if not creds or not creds.valid:

        if (
            creds
            and creds.expired
            and creds.refresh_token
        ):

            creds.refresh(
                Request()
            )

        else:

            flow = (
            InstalledAppFlow.from_client_secrets_file(
            str(GOOGLE_CREDENTIALS_FILE),
            GOOGLE_SCOPES
                )
            )

            creds = (
                flow.run_local_server(
                    port=0
                )
            )

        with open(GOOGLE_TOKEN_FILE, "w") as token:
            
            token.write(
                creds.to_json()
            )


    return build(
        "calendar",
        "v3",
        credentials=creds
    )


# ============================================================
# GOOGLE CALENDAR - TÍTULO
# ============================================================

def calendar_title(activity):

    tipo = activity.get(
        "tipo_actividad"
    )

    if tipo == "EVALUATION":

        icon = "📝"

    elif tipo == "HOMEWORK":

        icon = "📚"

    elif tipo == "FORUM":

        icon = "💬"

    else:

        icon = "🎓"

    return (
        f"{icon} "
        f"{activity['titulo']}"
    )


# ============================================================
# GOOGLE CALENDAR - DESCRIPCIÓN
# ============================================================

def calendar_description(activity):

    return (
        f"Curso: "
        f"{activity.get('curso') or '-'}\n"

        f"Tipo: "
        f"{activity.get('tipo_actividad') or '-'}\n"

        f"Semana: "
        f"{activity.get('semana') or '-'}\n"

        f"Estado UTP: "
        f"{activity.get('estado_utp') or '-'}\n"

        f"Estado: "
        f"{calcular_estado(activity)}\n\n"

        f"UTP ID: "
        f"{activity['utp_id']}\n\n"

        "Sincronizado automáticamente "
        "desde UTP+Class."
    )


# ============================================================
# GOOGLE CALENDAR - ¿DEBE SINCRONIZARSE?
# ============================================================

def should_sync_calendar(activity):

    if not activity.get(
        "fecha_entrega"
    ):
        return False

    if CALENDAR_TYPES is None:
        return True

    return (
        activity.get(
            "tipo_actividad"
        )
        in CALENDAR_TYPES
    )


# ============================================================
# GOOGLE CALENDAR - EVENTO
# ============================================================

def build_calendar_event(activity):

    fecha = activity.get(
        "fecha_entrega"
    )

    if not fecha:
        return None

    start_dt = datetime.fromisoformat(
        fecha
    )

    start_dt = start_dt.replace(
        second=0,
        microsecond=0
    )

    end_dt = (
        start_dt
        + timedelta(
            minutes=30
        )
    )

    return {

        "summary":
            calendar_title(
                activity
            ),

        "description":
            calendar_description(
                activity
            ),

        "start": {

            "dateTime":
                start_dt.isoformat(),

            "timeZone":
                "America/Lima",
        },

        "end": {

            "dateTime":
                end_dt.isoformat(),

            "timeZone":
                "America/Lima",
        },

        "extendedProperties": {

            "private": {

                "utp_id":
                    activity[
                        "utp_id"
                    ]
            }
        },

        "reminders": {

            "useDefault":
                False,

            "overrides": [

                {
                    "method":
                        "popup",

                    "minutes":
                        1440
                },

                {
                    "method":
                        "popup",

                    "minutes":
                        120
                }
            ]
        }
    }


# ============================================================
# GOOGLE CALENDAR - LEER TODOS UNA SOLA VEZ
# ============================================================

def get_existing_calendar_events(
    service
):

    existing = {}

    page_token = None

    while True:

        result = (
            service
            .events()
            .list(
                calendarId=
                    GOOGLE_CALENDAR_ID,

                maxResults=2500,

                singleEvents=True,

                showDeleted=False,

                pageToken=
                    page_token,
            )
            .execute()
        )


        for event in result.get(
            "items",
            []
        ):

            private = (
                event
                .get(
                    "extendedProperties",
                    {}
                )
                .get(
                    "private",
                    {}
                )
            )

            utp_id = private.get(
                "utp_id"
            )

            if utp_id:

                existing[
                    utp_id
                ] = event


        page_token = result.get(
            "nextPageToken"
        )

        if not page_token:
            break

    return existing


# ============================================================
# GOOGLE CALENDAR - DETECTAR CAMBIOS
# ============================================================

def calendar_event_changed(
    event,
    activity
):

    expected = build_calendar_event(
        activity
    )

    if not expected:
        return False


    current_title = event.get(
        "summary",
        ""
    )

    current_description = event.get(
        "description",
        ""
    )

    current_start = (
        event.get(
            "start",
            {}
        )
        .get(
            "dateTime"
        )
    )

    current_end = (
        event.get(
            "end",
            {}
        )
        .get(
            "dateTime"
        )
    )

    expected_start = (
        expected[
            "start"
        ][
            "dateTime"
        ]
    )

    expected_end = (
        expected[
            "end"
        ][
            "dateTime"
        ]
    )


    return any([

        current_title
        != expected["summary"],

        current_description
        != expected["description"],

        normalize_date(
            current_start
        )
        != normalize_date(
            expected_start
        ),

        normalize_date(
            current_end
        )
        != normalize_date(
            expected_end
        ),
    ])


# ============================================================
# GOOGLE CALENDAR - CREAR
# ============================================================

def create_calendar_event(
    service,
    activity
):

    body = build_calendar_event(
        activity
    )

    if not body:
        return


    if DRY_RUN:

        print(
            "📅 CREAR CALENDAR: "
            f"[{activity['curso']}] "
            f"{activity['titulo']}"
        )

        return


    service.events().insert(

        calendarId=
            GOOGLE_CALENDAR_ID,

        body=body

    ).execute()


# ============================================================
# GOOGLE CALENDAR - ACTUALIZAR
# ============================================================

def update_calendar_event(
    service,
    event_id,
    activity
):

    body = build_calendar_event(
        activity
    )

    if not body:
        return


    if DRY_RUN:

        print(
            "📅 ACTUALIZAR CALENDAR: "
            f"[{activity['curso']}] "
            f"{activity['titulo']}"
        )

        return


    service.events().update(

        calendarId=
            GOOGLE_CALENDAR_ID,

        eventId=
            event_id,

        body=
            body

    ).execute()


# ============================================================
# SINCRONIZACIÓN PRINCIPAL
# ============================================================

def sync():

    print(
        "\n===== UTP → NOTION + GOOGLE CALENDAR =====\n"
    )


    if DRY_RUN:

        print(
            "🧪 MODO PRUEBA ACTIVADO"
        )

        print(
            "No se modificará Notion "
            "ni Google Calendar.\n"
        )


    # ========================================================
    # UTP
    # ========================================================

    print(
        "📡 Consultando UTP+Class..."
    )

    activities = get_utp_activities()

    print(
        f"📚 Actividades únicas UTP: "
        f"{len(activities)}"
    )


    # ========================================================
    # NOTION
    # ========================================================

    print(
        "🔎 Consultando Notion..."
    )

    notion_existing = (
        get_existing_notion_tasks()
    )

    print(
        "🗃️ Actividades UTP existentes "
        f"en Notion: "
        f"{len(notion_existing)}"
    )


    # ========================================================
    # GOOGLE CALENDAR
    # ========================================================

    print(
        "📅 Conectando Google Calendar..."
    )

    calendar_service = (
        get_google_calendar_service()
    )

    print(
        "🔎 Consultando eventos existentes "
        "en Calendar..."
    )

    calendar_existing = (
        get_existing_calendar_events(
            calendar_service
        )
    )

    print(
        "📅 Eventos UTP existentes "
        f"en Calendar: "
        f"{len(calendar_existing)}\n"
    )


    # ========================================================
    # CONTADORES NOTION
    # ========================================================

    notion_created = 0
    notion_updated = 0
    notion_unchanged = 0


    # ========================================================
    # CONTADORES CALENDAR
    # ========================================================

    calendar_created = 0
    calendar_updated = 0
    calendar_unchanged = 0
    calendar_skipped = 0


    errors = 0


    # ========================================================
    # PROCESAR ACTIVIDADES
    # ========================================================

    for activity in activities:

        try:

            utp_id = activity[
                "utp_id"
            ]


            # ==================================================
            # NOTION
            # ==================================================

            if (
                utp_id
                not in notion_existing
            ):

                create_notion_task(
                    activity
                )

                notion_created += 1


            else:

                page = notion_existing[
                    utp_id
                ]

                if activity_changed(
                    activity,
                    page
                ):

                    update_notion_task(
                        page["id"],
                        activity
                    )

                    notion_updated += 1

                else:

                    notion_unchanged += 1


            # ==================================================
            # GOOGLE CALENDAR
            # ==================================================

            if not should_sync_calendar(
                activity
            ):

                calendar_skipped += 1
                continue


            calendar_event = (
                calendar_existing.get(
                    utp_id
                )
            )


            if not calendar_event:

                create_calendar_event(
                    calendar_service,
                    activity
                )

                calendar_created += 1


            elif calendar_event_changed(
                calendar_event,
                activity
            ):

                update_calendar_event(
                    calendar_service,
                    calendar_event[
                        "id"
                    ],
                    activity
                )

                calendar_updated += 1


            else:

                calendar_unchanged += 1


        except Exception as error:

            errors += 1

            print(
                "\n❌ ERROR:"
            )

            print(
                activity.get(
                    "titulo"
                )
            )

            print(
                error
            )


    # ========================================================
    # RESUMEN
    # ========================================================

    print(
        "\n=============================="
    )

    print(
        "        RESUMEN NOTION"
    )

    print(
        "=============================="
    )


    if DRY_RUN:

        print(
            f"➕ Se crearían: "
            f"{notion_created}"
        )

        print(
            f"🔄 Se actualizarían: "
            f"{notion_updated}"
        )

    else:

        print(
            f"➕ Creadas: "
            f"{notion_created}"
        )

        print(
            f"🔄 Actualizadas: "
            f"{notion_updated}"
        )


    print(
        f"⏭️ Sin cambios: "
        f"{notion_unchanged}"
    )


    print(
        "\n=============================="
    )

    print(
        "     RESUMEN GOOGLE CALENDAR"
    )

    print(
        "=============================="
    )


    if DRY_RUN:

        print(
            f"📅 Se crearían: "
            f"{calendar_created}"
        )

        print(
            f"🔄 Se actualizarían: "
            f"{calendar_updated}"
        )

    else:

        print(
            f"📅 Creados: "
            f"{calendar_created}"
        )

        print(
            f"🔄 Actualizados: "
            f"{calendar_updated}"
        )


    print(
        f"⏭️ Sin cambios: "
        f"{calendar_unchanged}"
    )

    print(
        f"🚫 Omitidos: "
        f"{calendar_skipped}"
    )


    print(
        f"\n❌ Errores totales: "
        f"{errors}"
    )


    if DRY_RUN:

        print(
            "\n🧪 Prueba terminada."
        )

        print(
            "Notion y Google Calendar "
            "NO fueron modificados."
        )

    else:

        print(
            "\n✅ Sincronización terminada."
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    sync()