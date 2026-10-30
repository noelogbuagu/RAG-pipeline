"""Create a small, fictional DOCX fixture for trying the app without private documents."""

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_DIR / "examples" / "team-handbook.txt"
DESTINATION = PROJECT_DIR / "data" / "team-handbook.docx"
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def create_sample_document(destination: Path) -> Path:
    """Package the tracked sample text as a DOCX; never overwrite an existing file."""
    document = Element(f"{{{WORD_NAMESPACE}}}document")
    body = SubElement(document, f"{{{WORD_NAMESPACE}}}body")
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        paragraph = SubElement(body, f"{{{WORD_NAMESPACE}}}p")
        run = SubElement(paragraph, f"{{{WORD_NAMESPACE}}}r")
        SubElement(run, f"{{{WORD_NAMESPACE}}}t").text = line
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "x", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "word/document.xml",
            tostring(document, encoding="utf-8", xml_declaration=True),
        )
    return destination


if __name__ == "__main__":
    try:
        print(f"Created: {create_sample_document(DESTINATION)}")
    except FileExistsError:
        print(f"Already exists; left unchanged: {DESTINATION}")
