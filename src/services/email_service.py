import imaplib
import email
import re
import os
import io
import urllib.request
import urllib.parse
import zipfile
from email.header import decode_header

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx
except ImportError:
    docx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import xlrd
except ImportError:
    xlrd = None



class IMAPConnectionError(Exception):
    """Raised when connecting to the IMAP server fails."""
    pass


class IMAPAuthenticationError(Exception):
    """Raised when logging in to the IMAP server fails."""
    pass


class IMAPMailboxError(Exception):
    """Raised when selecting or reading from the mailbox fails."""
    pass


def list_latest_emails(host, username, password, mailbox="INBOX", limit=5, status_filter="ALL"):
    """
    Connects to an IMAP server and retrieves the latest emails.

    Args:
        host: IMAP server address
        username: Email address
        password: App password (plaintext decrypted)
        mailbox: Mailbox name
        limit: Number of emails to fetch
        status_filter: Filter type ('ALL', 'UNSEEN', 'SEEN')

    Returns:
        List[dict]: Details of retrieved emails.
    """
    if status_filter not in ("ALL", "UNSEEN", "SEEN"):
        status_filter = "ALL"

    try:
        mail = imaplib.IMAP4_SSL(host)
    except Exception as e:
        raise IMAPConnectionError(f"Could not establish connection to host '{host}': {e}")

    try:
        try:
            mail.login(username, password)
        except imaplib.IMAP4.error as e:
            raise IMAPAuthenticationError(
                f"Failed to authenticate user '{username}' on IMAP server: {e}"
            )

        try:
            status, _ = mail.select(mailbox)
            if status != "OK":
                raise IMAPMailboxError(f"Unable to open mailbox: '{mailbox}'")
        except Exception as e:
            if not isinstance(e, IMAPMailboxError):
                raise IMAPMailboxError(f"Error selecting mailbox '{mailbox}': {e}")
            raise e

        status, messages = mail.search(None, status_filter)
        if status != "OK":
            raise IMAPMailboxError("Failed to list messages in the selected mailbox.")

        email_ids = messages[0].split()
        if not email_ids:
            return []

        # Get latest email ids
        email_ids = email_ids[-limit:]
        email_ids.reverse()  # Newest emails first

        email_list = []

        for msg_id in email_ids:
            try:
                status, msg_data = mail.fetch(msg_id, "(FLAGS RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                flags_metadata = msg_data[0][0]
                is_read = b'\\Seen' in flags_metadata

                msg = email.message_from_bytes(msg_data[0][1])

                subject_header = msg.get("Subject", "")
                subject_decoded = decode_header(subject_header)[0]
                subject = subject_decoded[0]

                if isinstance(subject, bytes):
                    subject = subject.decode(
                        subject_decoded[1] or "utf-8",
                        errors="ignore"
                    )

                attachments = []
                html_body = ""
                text_body = ""
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                text_body += payload.decode('utf-8', errors='ignore')
                        except Exception:
                            pass
                    elif content_type == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                html_body += payload.decode('utf-8', errors='ignore')
                        except Exception:
                            pass

                    filename = part.get_filename()
                    if filename:
                        decoded_filename_parts = decode_header(filename)
                        decoded_filename = ""
                        for decoded_text, encoding in decoded_filename_parts:
                            if isinstance(decoded_text, bytes):
                                try:
                                    decoded_filename += decoded_text.decode(encoding or "utf-8", errors="ignore")
                                except Exception:
                                    decoded_filename += decoded_text.decode("utf-8", errors="ignore")
                            else:
                                decoded_filename += decoded_text
                        if decoded_filename not in attachments:
                            attachments.append(decoded_filename)
                    elif part.get_content_disposition() == 'attachment':
                        attachments.append("unnamed_attachment")

                # Parse Google Drive attachments in HTML body
                if html_body:
                    drive_pattern = r'href="https://drive\.google\.com/file/d/[^"]+"[^>]*aria-label="([^"]+)"'
                    drive_matches = re.findall(drive_pattern, html_body)
                    if not drive_matches:
                        span_pattern = r'class="[^"]*gmail_drive_chip[^"]*".*?<span dir="ltr"[^>]*>([^<]+)</span>'
                        drive_matches = re.findall(span_pattern, html_body, re.DOTALL)
                    for match in drive_matches:
                        name = match.strip()
                        if name and name not in attachments:
                            attachments.append(name)

                # Parse Google Drive attachments in Plain Text body
                if text_body:
                    lines = [line.strip() for line in text_body.splitlines() if line.strip()]
                    for idx, line in enumerate(lines):
                        if "drive.google.com/file/d/" in line:
                            filename = "Google Drive File"
                            if idx > 0 and lines[idx - 1] and not ("drive.google.com" in lines[idx - 1] or "http" in lines[idx - 1]):
                                filename = lines[idx - 1].strip("<>()[]\"' ")
                            if filename and filename not in attachments:
                                attachments.append(filename)

                email_list.append(
                    {
                        "id": msg_id.decode("utf-8", errors="ignore"),
                        "subject": subject,
                        "from": msg.get("From"),
                        "to": msg.get("To"),
                        "date": msg.get("Date"),
                        "status": "Read" if is_read else "Unread",
                        "has_attachment": len(attachments) > 0,
                        "attachment_count": len(attachments),
                        "attachment_names": attachments,
                    }
                )
            except Exception:
                # Continue fetching other emails even if one fails
                continue

        return email_list

    finally:
        try:
            mail.logout()
        except:
            pass


def extract_text_from_attachment(content_bytes: bytes, filename: str) -> str:
    """
    Extracts text content from raw bytes of an attachment based on the file extension.

    Args:
        content_bytes: Raw bytes of the attachment
        filename: Name of the file (to determine extension)

    Returns:
        str: Extracted text content.
    """
    ext = filename.split('.')[-1].lower() if '.' in filename else ''

    if ext in ('txt', 'csv', 'json', 'xml', 'html', 'log', 'ini', 'cfg', 'md'):
        try:
            return content_bytes.decode('utf-8', errors='ignore')
        except Exception as e:
            return f"[Error decoding text file: {e}]"

    elif ext == 'pdf':
        if pypdf is None:
            return "[Error: pypdf library is not installed for PDF extraction]"
        try:
            pdf_file = io.BytesIO(content_bytes)
            reader = pypdf.PdfReader(pdf_file)
            text = ""
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
        except Exception as e:
            return f"[Error extracting text from PDF: {e}]"

    elif ext in ('docx', 'doc'):
        if docx is None:
            return "[Error: python-docx library is not installed for Word document extraction]"
        try:
            docx_file = io.BytesIO(content_bytes)
            doc = docx.Document(docx_file)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text if cell.text is not None else "" for cell in row.cells]
                    text.append(" | ".join(row_text))
            return "\n".join(text).strip()
        except Exception as e:
            return f"[Error extracting text from Word document: {e}]"

    elif ext == 'xlsx':
        if openpyxl is None:
            return "[Error: openpyxl library is not installed for Excel extraction]"
        try:
            excel_file = io.BytesIO(content_bytes)
            wb = openpyxl.load_workbook(excel_file, read_only=True, data_only=True)
            text = []
            for sheet in wb.worksheets:
                text.append(f"--- Sheet: {sheet.title} ---")
                for row in sheet.iter_rows(values_only=True):
                    if any(cell is not None for cell in row):
                        row_text = [str(cell) if cell is not None else "" for cell in row]
                        text.append(" | ".join(row_text))
            return "\n".join(text).strip()
        except Exception as e:
            return f"[Error extracting text from Excel (.xlsx): {e}]"

    elif ext == 'xls':
        if xlrd is None:
            return "[Error: xlrd library is not installed for older Excel (.xls) extraction]"
        try:
            wb = xlrd.open_workbook(file_contents=content_bytes)
            text = []
            for sheet_idx in range(wb.nsheets):
                sheet = wb.sheet_by_index(sheet_idx)
                text.append(f"--- Sheet: {sheet.name} ---")
                for row_idx in range(sheet.nrows):
                    row = sheet.row_values(row_idx)
                    if any(cell != "" for cell in row):
                        row_text = [str(cell) if cell != "" else "" for cell in row]
                        text.append(" | ".join(row_text))
            return "\n".join(text).strip()
        except Exception as e:
            return f"[Error extracting text from older Excel (.xls): {e}]"

    elif ext == 'zip':
        try:
            zip_file = io.BytesIO(content_bytes)
            text = []
            with zipfile.ZipFile(zip_file) as z:
                namelist = z.namelist()
                text.append(f"--- Archive Contains {len(namelist)} Files ---")
                for name in namelist:
                    if name.endswith('/'):
                        continue
                    text.append(f"\n[File Inside Zip: {name}]")
                    try:
                        file_bytes = z.read(name)
                        file_text = extract_text_from_attachment(file_bytes, name)
                        indented_text = "\n".join("  " + line for line in file_text.splitlines())
                        text.append(indented_text)
                    except Exception as e:
                        text.append(f"  [Error extracting text: {e}]")
            return "\n".join(text).strip()
        except Exception as e:
            return f"[Error extracting text from Zip file: {e}]"

    else:
        return f"[Content extraction not supported for file type: .{ext}]"



def extract_drive_links(text_body, html_body):
    """
    Extracts Google Drive file links from text and HTML bodies.
    Returns:
        List[dict]: List of dicts with 'filename' and 'file_id'.
    """
    links = []
    # 1. From HTML Body
    if html_body:
        drive_pattern = r'href="https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)/[^"]*"[^>]*aria-label="([^"]+)"'
        matches = re.findall(drive_pattern, html_body)
        for file_id, filename in matches:
            filename = filename.strip()
            if filename and not any(item['file_id'] == file_id for item in links):
                links.append({'filename': filename, 'file_id': file_id})
        
        chip_pattern = r'href="https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)/[^*?"]*".*?class="[^"]*gmail_drive_chip[^"]*".*?<span dir="ltr"[^>]*>([^<]+)</span>'
        matches2 = re.findall(chip_pattern, html_body, re.DOTALL)
        for file_id, filename in matches2:
            filename = filename.strip()
            if filename and not any(item['file_id'] == file_id for item in links):
                links.append({'filename': filename, 'file_id': file_id})

    # 2. From Plain Text Body
    if text_body:
        lines = [line.strip() for line in text_body.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', line)
            if match:
                file_id = match.group(1)
                filename = "Google Drive File"
                if idx > 0 and lines[idx - 1] and not ("drive.google.com" in lines[idx - 1] or "http" in lines[idx - 1]):
                    filename = lines[idx - 1].strip("<>()[]\"' ")
                
                if filename and not any(item['file_id'] == file_id for item in links):
                    links.append({'filename': filename, 'file_id': file_id})
                    
    return links


def download_file_from_google_drive(file_id, dest_path):
    """
    Downloads a public file from Google Drive by its file ID.
    Handles the virus scan warning page automatically.
    """
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    cookie_processor = urllib.request.HTTPCookieProcessor()
    opener = urllib.request.build_opener(cookie_processor)
    
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req) as response:
        content = response.read()
        
        # Check if Google Drive returned a confirmation warning page
        html = content.decode('utf-8', errors='ignore') if content else ""
        if "confirm=" in html:
            match = re.search(r'confirm=([a-zA-Z0-9_-]+)', html)
            if match:
                confirm_token = match.group(1)
                confirm_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
                req_confirm = urllib.request.Request(confirm_url, headers=headers)
                with opener.open(req_confirm) as confirm_response:
                    content = confirm_response.read()
                    html = content.decode('utf-8', errors='ignore') if content else ""

        # Verify if Google Drive redirected to a sign-in or account verification page
        if "accounts.google.com" in html and ("signin" in html or "ServiceLogin" in html or "base href" in html):
            raise PermissionError(
                f"File is private. Please open the link in your browser to download/view it:\n"
                f"  https://drive.google.com/file/d/{file_id}/view"
            )
                    
        with open(dest_path, "wb") as f:
            f.write(content)
            
        return content



def download_email_attachments(host, username, password, msg_id, download_dir, mailbox="INBOX"):
    """
    Connects to an IMAP server, fetches a specific email by msg_id,
    extracts all attachments (both MIME attachments and Google Drive links),
    saves them to download_dir, and extracts text content.

    Args:
        host: IMAP server address
        username: Email address
        password: App password (plaintext decrypted)
        msg_id: IMAP message ID (as string)
        download_dir: Target directory path
        mailbox: Mailbox name

    Returns:
        List[dict]: Details of downloaded attachments including 'filename', 'saved_path', and 'text_content'.
    """
    try:
        mail = imaplib.IMAP4_SSL(host)
    except Exception as e:
        raise IMAPConnectionError(f"Could not establish connection to host '{host}': {e}")

    try:
        try:
            mail.login(username, password)
        except imaplib.IMAP4.error as e:
            raise IMAPAuthenticationError(
                f"Failed to authenticate user '{username}' on IMAP server: {e}"
            )

        try:
            status, _ = mail.select(mailbox)
            if status != "OK":
                raise IMAPMailboxError(f"Unable to open mailbox: '{mailbox}'")
        except Exception as e:
            if not isinstance(e, IMAPMailboxError):
                raise IMAPMailboxError(f"Error selecting mailbox '{mailbox}': {e}")
            raise e

        # Fetch message by sequence ID
        status, msg_data = mail.fetch(str(msg_id).encode(), "(RFC822)")
        if status != "OK" or not msg_data or not msg_data[0]:
            raise IMAPMailboxError(f"Failed to fetch message ID '{msg_id}' from mailbox.")

        msg = email.message_from_bytes(msg_data[0][1])
        downloaded = []

        # Create download directory if it does not exist
        if not os.path.exists(download_dir):
            os.makedirs(download_dir, exist_ok=True)

        text_body = ""
        html_body = ""

        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        text_body += payload.decode('utf-8', errors='ignore')
                except:
                    pass
            elif content_type == "text/html":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_body += payload.decode('utf-8', errors='ignore')
                except:
                    pass

            filename = part.get_filename()
            content_disposition = part.get_content_disposition()
            
            # If it's a MIME attachment
            if filename or content_disposition == 'attachment':
                if not filename:
                    filename = "unnamed_attachment"
                
                # Decode filename
                decoded_filename_parts = decode_header(filename)
                decoded_filename = ""
                for decoded_text, encoding in decoded_filename_parts:
                    if isinstance(decoded_text, bytes):
                        try:
                            decoded_filename += decoded_text.decode(encoding or "utf-8", errors="ignore")
                        except Exception:
                            decoded_filename += decoded_text.decode("utf-8", errors="ignore")
                    else:
                        decoded_filename += decoded_text

                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                # Avoid overwriting files with conflict resolution (suffix)
                base_name, ext = os.path.splitext(decoded_filename)
                saved_path = os.path.join(download_dir, decoded_filename)
                counter = 1
                while os.path.exists(saved_path):
                    saved_path = os.path.join(download_dir, f"{base_name}_{counter}{ext}")
                    counter += 1

                with open(saved_path, "wb") as f:
                    f.write(payload)

                # Extract text content and store in a variable
                text_content = extract_text_from_attachment(payload, decoded_filename)

                downloaded.append({
                    "filename": os.path.basename(saved_path),
                    "saved_path": os.path.abspath(saved_path),
                    "text_content": text_content
                })

        # Process Google Drive attachments as well
        drive_links = extract_drive_links(text_body, html_body)
        for item in drive_links:
            filename = item['filename']
            file_id = item['file_id']

            # Resolve conflict in filenames
            base_name, ext = os.path.splitext(filename)
            saved_path = os.path.join(download_dir, filename)
            counter = 1
            while os.path.exists(saved_path):
                saved_path = os.path.join(download_dir, f"{base_name}_{counter}{ext}")
                counter += 1

            try:
                # Download Google Drive file
                payload = download_file_from_google_drive(file_id, saved_path)
                
                # Extract text content and store in a variable
                text_content = extract_text_from_attachment(payload, filename)

                downloaded.append({
                    "filename": os.path.basename(saved_path),
                    "saved_path": os.path.abspath(saved_path),
                    "text_content": text_content
                })
            except Exception as e:
                downloaded.append({
                    "filename": filename,
                    "saved_path": "[Failed to download Google Drive attachment]",
                    "text_content": f"[Error downloading Google Drive link: {e}]"
                })

        return downloaded


    finally:
        try:
            mail.logout()
        except:
            pass

