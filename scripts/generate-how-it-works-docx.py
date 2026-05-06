import datetime
import os
import zipfile
from xml.sax.saxutils import escape


def paragraph_xml(text: str) -> str:
    return (
        '<w:p><w:r><w:t xml:space="preserve">'
        + escape(text)
        + "</w:t></w:r></w:p>"
    )


def build_docx(output_path: str) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    utc_now = (
        datetime.datetime.now(datetime.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    paragraphs = [
        "e-OSEWS: How Everything Works",
        f"Generated: {now}",
        "",
        "1) System Purpose",
        (
            "e-OSEWS (Electronic One Health Early Warning Surveillance System) supports early detection, "
            "reporting, and triage of Rift Valley Fever-like events from community and facility reporters."
        ),
        "",
        "2) Main Components",
        "- Backend API: Flask service in app/main.py",
        "- Data Store: SQLite database file (eosews.db)",
        "- Web App: public site + surveillance dashboard + report-case page",
        "- Mobile App: Expo React Native app in mobile-app/",
        "- Scripts: startup automation and documentation helpers in scripts/",
        "",
        "3) End-to-End Data Flow",
        "Step 1: Reporter logs in (web report-case or mobile app).",
        "Step 2: Reporter submits structured event form (role, district, syndrome, location, etc.).",
        "Step 3: Backend validates payload and stores event in database.",
        "Step 4: Risk logic evaluates event and can generate alerts/high-risk flags.",
        "Step 5: Dashboard views query API endpoints and render metrics/map/lists.",
        "Step 6: Admin users can manage users and validation status for flagged records.",
        "",
        "4) Authentication and Roles",
        "- Login endpoint issues token and role context.",
        "- Token can be used as X-API-Token or Authorization: Bearer <token>.",
        "- Admin role has full user-management and validation controls.",
        "- District users are district-scoped for operational workflows.",
        "",
        "5) Event Submission Logic",
        "- Dropdown-driven fields reduce reporting errors.",
        "- District selection drives parish options.",
        "- Reporter role drives species/patient and syndrome options.",
        "- Animal exposure defaults are auto-adjusted based on context.",
        "- Reporter metadata includes name/contact and IP capture support.",
        "",
        "6) High-Risk and Alerts",
        (
            "Events are scored using syndrome and exposure context. High-risk events and anomalous patterns "
            "can trigger alerts for review and response."
        ),
        "- Dashboard provides: Events, High Risk, Alerts, Data Flags, Environmental observations.",
        "- Clicking each metric loads exact related records.",
        "",
        "7) Mobile App Behavior",
        "- Login screen includes animated background and branded UI.",
        "- Home screen supports role-aware forms and validation messages.",
        "- API client handles offline queueing and delayed sync retries.",
        "- API host is dynamically resolved from Expo host URI with fallback.",
        "",
        "8) Web Dashboard Behavior",
        "- Landing page routes users to Report Case or Surveillance Dashboard.",
        "- Dashboard supports map visualisation with event GPS points.",
        "- Report Case page includes login, dynamic form updates, and success banner.",
        "- Admin panel exposes user activation, token reset, and role/district controls.",
        "",
        "9) Core API Areas",
        "- Health: /health",
        "- Auth: /api/auth/login",
        "- Events: /api/events and related flag/summary endpoints",
        "- Alerts: /api/alerts and alert status/history",
        "- USSD: /api/ussd/report",
        "- Environment: /api/environment and geo endpoints",
        "",
        "10) Local Run",
        "Backend: python -m app.main",
        "Mobile: cd mobile-app; npm run start",
        "Automation: scripts/run-all.ps1 or scripts/dev-all.ps1",
        "",
        "11) Render Deployment (Current Setup)",
        "- Repo contains render.yaml Blueprint config.",
        "- Build command: pip install -r requirements.txt",
        "- Start command: gunicorn --bind 0.0.0.0:$PORT app.main:app",
        "- Runtime pin: runtime.txt (python-3.11.9)",
        "- Required env var: EOSEWS_API_TOKEN",
        "",
        "12) Production Considerations",
        "- SQLite is acceptable for pilot/demo, but not ideal for scaled multi-user production.",
        "- Render free instances may reset local filesystem between deploys/restarts.",
        "- Recommended next step: migrate DB to managed Postgres.",
        "",
        "13) Quick Verification Checklist",
        "- Open /health and confirm success.",
        "- Test login on /report-case.",
        "- Submit one event and confirm dashboard visibility/map point.",
        "- Confirm admin actions work for user management.",
        "",
        "End of document.",
    ]

    body = "".join(paragraph_xml(p) for p in paragraphs)
    body += (
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    )

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:w10="urn:schemas-microsoft-com:office:word"
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
 xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
 xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
 xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
 xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
 mc:Ignorable="w14 wp14">
 <w:body>{body}</w:body>
</w:document>"""

    core = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>e-OSEWS How Everything Works</dc:title>
  <dc:creator>Cursor Agent</dc:creator>
  <cp:lastModifiedBy>Cursor Agent</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{utc_now}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{utc_now}</dcterms:modified>
</cp:coreProperties>"""

    app = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application>
</Properties>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app)


if __name__ == "__main__":
    target = r"d:\e-OSEWS\e-OSEWS_How_Everything_Works.docx"
    build_docx(target)
    print(target)
