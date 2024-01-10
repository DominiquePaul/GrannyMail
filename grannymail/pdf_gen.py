import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from grannymail.db_client import Address
from io import BytesIO

# Constants for page layout
PAGE_HEIGHT, PAGE_WIDTH = A4
ADDRESS_Y_OFFSET = 40 * mm
ADDRESS_X_OFFSET = 28 * mm
ADDRESS_TO_TEXT_GAP = 40 * mm
PAGE_NUMBER_OFFSET = 0.75 * inch
DEFAULT_FONT = "Times-Roman"
DEFAULT_FONT_SIZE = 11
PARAGRAPH_SPACING = 4 * mm

# Get the default style sheet
styles = getSampleStyleSheet()
normal_style = styles["Normal"]
normal_style.fontName = DEFAULT_FONT
normal_style.fontSize = DEFAULT_FONT_SIZE


def address_to_address_lines(address: Address):
    """Converts an address dict to a list of address lines."""
    if address.is_complete_address() is False:
        logging.info(f"Tried to send letter with invalid address: {address}")
        raise ValueError("Invalid address")
    address_lines = []
    address_lines.append(address.addressee)
    address_lines.append(address.address_line1)
    if address.address_line2:
        address_lines.append(address.address_line2)
    address_lines.append(f"{address.zip} {address.city}")
    # address_lines.append(address.country)
    return address_lines


def draw_address(canvas, address):
    """Draws the address on the canvas at the specified y_position."""
    address_lines = address_to_address_lines(address)
    for i, line in enumerate(address_lines):
        if line:  # Only draw non-empty lines
            canvas.drawString(ADDRESS_X_OFFSET,  # Use the new x-coordinate offset
                              PAGE_HEIGHT + 60*mm - ADDRESS_Y_OFFSET - i * 4 * mm, line)


def my_first_page(canvas, doc, address):
    """Creates the layout for the first page."""
    canvas.saveState()
    canvas.setFont(DEFAULT_FONT, DEFAULT_FONT_SIZE)
    if address.is_complete_address():
        draw_address(canvas, address)
    canvas.drawString(PAGE_NUMBER_OFFSET, PAGE_NUMBER_OFFSET, "Seite 1")
    canvas.restoreState()


def my_later_pages(canvas, doc):
    """Creates the layout for subsequent pages."""
    canvas.saveState()
    canvas.setFont(DEFAULT_FONT, DEFAULT_FONT_SIZE)
    canvas.drawString(PAGE_NUMBER_OFFSET,
                      PAGE_NUMBER_OFFSET, f"Page {doc.page}")
    canvas.restoreState()


def create_letter_pdf_as_bytes(input_text: str, address: Address = Address()) -> bytes:
    """Generates a PDF letter from input text and optional address."""
    # Create a file-like buffer to receive PDF data
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    # Create a list to hold the PDF elements
    story = [Spacer(1,  ADDRESS_Y_OFFSET + ADDRESS_TO_TEXT_GAP)]

    # Split the input text into paragraphs and add them to the story
    for paragraph_text in input_text.split("\n"):
        paragraph = Paragraph(paragraph_text, normal_style)
        story.extend([paragraph, Spacer(1, PARAGRAPH_SPACING)])

    # Build the PDF document
    doc.build(
        story,
        onFirstPage=lambda canvas, doc: my_first_page(canvas, doc, address),
        onLaterPages=my_later_pages
    )

    # Retrieve the PDF data and close the buffer
    pdf_data = buffer.getvalue()
    buffer.close()

    return pdf_data


def create_and_save_letter(file_path: str, input_text: str, address: Address = Address()):
    pdf_bytes = create_letter_pdf_as_bytes(
        input_text=input_text, address=address)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)


if __name__ == "__main__":
    address = Address(
        addressee="Pickle Rick",
        address_line1="Pickle Lane 42",
        address_line2=None,
        zip="50968",
        city="Spreewald city",
        country="Cucumber Land",
    )

    example_text = "Hello world!\nThis is a test letter."
    letter_name = "test_letter.pdf"

    letter_bytes = create_letter_pdf_as_bytes(
        address=address, input_text=example_text
    )
