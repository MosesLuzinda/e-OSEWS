import datetime
import os
import urllib.parse
import urllib.request
import zipfile
from xml.sax.saxutils import escape


def paragraph_xml(text: str) -> str:
    return (
        '<w:p><w:r><w:t xml:space="preserve">'
        + escape(text)
        + "</w:t></w:r></w:p>"
    )


def qr_drawing_xml(rel_id: str, image_name: str, cx: int = 1905000, cy: int = 1905000) -> str:
    return (
        "<w:p><w:r><w:drawing>"
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        '<wp:docPr id="1" name="Expo QR Code"/>'
        '<wp:cNvGraphicFramePr>'
        '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
        "</wp:cNvGraphicFramePr>"
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        "<pic:nvPicPr>"
        f'<pic:cNvPr id="0" name="{escape(image_name)}"/>'
        "<pic:cNvPicPr/>"
        "</pic:nvPicPr>"
        "<pic:blipFill>"
        f'<a:blip r:embed="{rel_id}"/>'
        "<a:stretch><a:fillRect/></a:stretch>"
        "</pic:blipFill>"
        "<pic:spPr>"
        f'<a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        "</pic:spPr>"
        "</pic:pic>"
        "</a:graphicData>"
        "</a:graphic>"
        "</wp:inline>"
        "</w:drawing></w:r></w:p>"
    )


def fetch_qr_png(data: str) -> bytes:
    encoded = urllib.parse.quote(data, safe="")
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=360x360&data={encoded}"
    with urllib.request.urlopen(qr_url, timeout=20) as response:
        return response.read()


def build_docx(output_path: str, expo_url: str) -> None:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    utc_now = datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    paragraphs = [
        "e-OSEWS Code Documentation",
        f"Generated: {now}",
        "",
        "1. Project Overview",
        (
            "e-OSEWS is an early warning and event reporting system with a Flask backend "
            "and an Expo React Native mobile frontend. It supports role-based reporting, "
            "offline event queueing, quality flagging, and validation workflows."
        ),
        "",
        "2. Repository Structure",
        "- app/: Flask backend API and SQLite logic",
        "- mobile-app/: Expo/React Native mobile application",
        "- scripts/: helper automation scripts",
        "- .vscode/: local task automation configuration",
        "",
        "3. Backend (Flask) - app/main.py",
        "- Auth, role-based access, and event submission endpoints",
        "- Event quality/flagging logic and validation status updates",
        "- IP capture support (reporter_ip) and idempotency handling (idempotency_key)",
        "- Summary and flagged-events endpoints used by the mobile dashboard",
        "",
        "4. Mobile App (Expo/React Native)",
        "- App entry and session persistence in mobile-app/App.js",
        "- Login UI with motion-enhanced background in mobile-app/src/screens/LoginScreen.js",
        "- Main dashboard/forms in mobile-app/src/screens/HomeScreen.js",
        "- API integration and offline queue in mobile-app/src/api/client.js",
        "",
        "5. Key User-Facing Features",
        "- Dashboard metrics (events, high risk, alerts, data flags)",
        "- Event form and USSD form with dropdown-based structured fields",
        "- Dynamic district -> parish and role -> species/syndrome options",
        "- Auto-default behavior for animal exposure with helper text",
        "- Client-side form validation with inline error messages",
        "- GPS and network/IP context attached to submissions",
        "",
        "6. Development Run Steps",
        "Backend: python -m app.main",
        "Mobile app: cd mobile-app && npm run start -- --port 8082",
        (
            "If Expo QR does not appear, confirm no port conflict and ensure "
            "the backend is reachable from the phone network."
        ),
        "",
        "7. Deployment Notes",
        "- Use production WSGI server (e.g., gunicorn) behind nginx",
        "- Enable HTTPS and environment-based API URLs",
        "- Configure process manager and backups for SQLite (or migrate to managed DB for scale)",
        "",
        "8. Important Configuration Files",
        "- mobile-app/app.json (Expo config, splash/icon)",
        "- .vscode/tasks.json (automation task)",
        "- scripts/dev-all.ps1 (dev startup helper)",
        "- requirements.txt (Python dependencies)",
        "",
        "9. Expo QR Code",
        "Scan this QR code with Expo Go (Android) or Camera app (iOS):",
        expo_url,
        "",
        "End of document.",
    ]

    body = "".join(paragraph_xml(p) for p in paragraphs)
    body += qr_drawing_xml(rel_id="rIdImage1", image_name="expo-qr.png")
    body += (
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    )

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
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

    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdImage1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/expo-qr.png"/>
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
  <dc:title>e-OSEWS Code Documentation</dc:title>
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
    qr_png = fetch_qr_png(expo_url)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", doc_rels)
        archive.writestr("word/media/expo-qr.png", qr_png)
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app)


if __name__ == "__main__":
    target = r"d:\e-OSEWS\e-OSEWS_Code_Documentation.docx"
    expo_link = "exp://192.168.30.191:8082"
    build_docx(target, expo_link)
    print(target)
