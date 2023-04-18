from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

PAGE_HEIGHT = A4[1]
PAGE_WIDTH = A4[0]
styles = getSampleStyleSheet()
line_spacing = 4 * mm


def create_letter_pdf_as_bytes(input_text: str, address: dict|None = None) -> bytes:
    def myFirstPage(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 10)
        if bool(address):
            lines = address.values()
            lines = [line for line in lines if line is not None]
            # height_offset = line_spacing * len(lines)
            for i, line in enumerate(lines):
                canvas.drawString(72, PAGE_HEIGHT - 60 * mm - i * line_spacing, line)

        canvas.drawString(inch, 0.75 * inch, "Seite 1")
        canvas.restoreState()

    def myLaterPages(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 10)
        canvas.drawString(inch, 0.75 * inch, f"Page {doc.page}")
        canvas.restoreState()

    buff = BytesIO()
    doc = SimpleDocTemplate(buff, pagesize=A4)
    Story = [Spacer(1, 60 * mm)]
    style = styles["Normal"]
    style.fontName = "Times-Roman"
    style.fontSize = 9

    paragraphs = input_text.split("\n")
    for paragraph in paragraphs:
        p = Paragraph(paragraph, style)
        Story.append(p)
        Story.append(Spacer(1, 8 * mm))
    doc.build(Story, onFirstPage=myFirstPage, onLaterPages=myLaterPages)
    pdf = buff.getvalue()
    buff.close()
    return pdf


if __name__ == "__main__":
    addressee_info = {
        "name": "Doris Paul",
        "address_line1": "Am Zehnpfenningshof 10",
        "address_line2": None,
        "zip": "50996",
        "city": "Cologne",
        "country": "Germany",
    }

    example_text = "Hello world!\nThis is a test letter."
    letter_name = "test_letter.pdf"

    letter_bytes = create_letter_pdf_as_bytes(
        address=addressee_info, input_text=example_text
    )
    from database_utils import BlobStorage
    import os

    blob_manager = BlobStorage(
        root_folder_path="../../" + os.environ["BLOB_STORAGE_ROOT_FOLDER"]
    )
    blob_manager.save_letter(letter_bytes=letter_bytes, letter_id=letter_name)
