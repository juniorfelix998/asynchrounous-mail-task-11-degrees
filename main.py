import os
import re
import logging
import asyncio
from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText

from PyPDF2 import PdfReader
import smtplib
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


load_dotenv()

absolute_path = os.path.abspath(".")

folder_name = "generated_pdfs"

PDF_FOLDER = os.getenv("PDF_FOLDER", os.path.join(absolute_path, folder_name))
MAIL_TRAP_USER = os.environ.get("MAIL_TRAP_USER")
SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = int(os.environ.get("SMTP_PORT"))
MAIL_TRAP_PASSWORD = os.environ.get("MAIL_TRAP_PASSWORD")
FROM_EMAIL_ADDRESS = os.environ.get("FROM_EMAIL_ADDRESS")
SENT_FOLDER = os.environ.get("SENT_FOLDER")
ERROR_FOLDER = os.environ.get("ERROR_FOLDER")


async def extract_emails_from_pdf_file(pdf_path):
    """
        Extracts email addresses from a PDF files.

        Args:
            pdf_path (str): Path to the PDF file.

        Returns:
            set: A set containing unique email addresses extracted from the PDF.
        """
    emails = set()
    with open(pdf_path, "rb") as file:
        reader = PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            extracted_emails = set(
                re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text)
            )
            emails.update(extracted_emails)
    return emails


async def send_email_with_pdf_attachment(recipient, file_path):
    """
        Sends an email with a PDF attachment to the specified recipient.

        Args:
            recipient (str): Email address of the recipient.
            file_path (str): Path to the PDF file to be attached.

        Returns:
            bool: True if the email is sent successfully, False otherwise.
        """
    message = MIMEMultipart()
    message["From"] = FROM_EMAIL_ADDRESS
    message["To"] = recipient
    message["Subject"] = "Job Application Attachment"

    message.attach(MIMEText("Hello from from felix pdf"))
    file_name_ = file_path.split("/")[-1]
    part = MIMEBase("application", "octet-stream")
    with open(file_path, "rb") as file:
        part.set_payload(file.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", "attachment; filename={}".format(file_name_)
        )
        message.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.login(MAIL_TRAP_USER, MAIL_TRAP_PASSWORD)
            server.send_message(message)
    except Exception as exc:
        logger.exception(f"An error occurred while sending email to {recipient}: {exc}")
        return False
    else:
        return True


async def move_file_after_sending_email(file_path, destination_folder):
    """
        Moves a file to a specified destination folder after sending an email.

        Args:
            file_path (str): Path to the file to be moved.
            destination_folder (str): Path to the destination folder.

        Raises:
            Exception: If an error occurs while moving the file.
        """
    try:
        os.makedirs(destination_folder, exist_ok=True)
        destination_path = os.path.join(destination_folder, os.path.basename(file_path))
        os.rename(file_path, destination_path)
    except Exception as e:
        logger.exception(f"An error occurred while moving file: {e}")


async def process_pdf_and_send_email():
    """
        Processes PDF files in a folder, extracts email addresses, and sends emails with attachments.

        If sending emails is successful, moves the PDF files to a 'sent' folder.
        If there are any errors during sending, moves the PDF files to an 'error' folder.

        Note: PDF_FOLDER, SENT_FOLDER, and ERROR_FOLDER should be defined somewhere in the code.

        Raises:
            Exception: If an error occurs during file processing or email sending.
        """
    pdf_files = [file for file in os.listdir(PDF_FOLDER) if file.endswith(".pdf")]
    for file in pdf_files:
        pdf_path = os.path.join(PDF_FOLDER, file)
        recipient_emails = await extract_emails_from_pdf_file(pdf_path)
        success = True
        for email in recipient_emails:
            if not await send_email_with_pdf_attachment(email, pdf_path):
                success = False
                break
        if success:
            await move_file_after_sending_email(pdf_path, SENT_FOLDER)
        else:
            await move_file_after_sending_email(pdf_path, ERROR_FOLDER)


async def main():
    tasks = [process_pdf_and_send_email()]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
