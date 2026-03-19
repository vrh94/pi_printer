import subprocess
import os
import logging
import tempfile

from config import DEFAULT_PRINTER, LPR_TIMEOUT

logger = logging.getLogger(__name__)

# Magic bytes for supported binary file types
_MAGIC = {
    b'%PDF': 'pdf',
    b'\x89PNG': 'png',
    b'\xff\xd8': 'jpeg',
}


def _detect_type(filepath):
    """Return a rough file type string based on magic bytes, or 'text'."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
        for magic, ftype in _MAGIC.items():
            if header.startswith(magic):
                return ftype
    except OSError:
        pass
    return 'text'


def list_printers():
    """
    Return a list of dicts describing installed CUPS printers.
    Each dict has 'name' and 'status' keys.
    Returns [] when CUPS is not installed or no printers are configured.
    """
    try:
        result = subprocess.run(
            ['lpstat', '-p'],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        logger.warning('lpstat not found — CUPS may not be installed')
        return []
    except subprocess.TimeoutExpired:
        logger.warning('lpstat timed out')
        return []

    printers = []
    for line in result.stdout.splitlines():
        # Example line: "printer HP_LaserJet is idle.  enabled since ..."
        parts = line.split()
        if len(parts) >= 4 and parts[0] == 'printer':
            name = parts[1]
            # Status is the word after 'is'
            try:
                is_idx = parts.index('is')
                status = parts[is_idx + 1].rstrip('.')
            except (ValueError, IndexError):
                status = 'unknown'
            printers.append({'name': name, 'status': status})

    return printers


_IMAGE_TYPES = ('png', 'jpeg')


def print_file(filepath, printer_name=None, page_from=None, page_to=None):
    """
    Send filepath to the printer.

    Images (PNG/JPEG) are converted to PDF via img2pdf before printing
    so the splix/foo2 driver receives a format it can process.

    page_from / page_to: optional 1-based integers for a page range (PDF only).

    Returns (success: bool, message: str).
    """
    if not os.path.isfile(filepath):
        return False, 'File not found'

    target_printer = printer_name or DEFAULT_PRINTER
    ftype = _detect_type(filepath)

    if ftype in _IMAGE_TYPES:
        return _print_image(filepath, target_printer)

    success, message = _lpr_print(filepath, target_printer, page_from, page_to)
    if success:
        return True, message

    # Only fall back to raw mode when lpr itself is missing (not when it
    # returned an error — an lpr error likely means a real printer problem).
    if 'not installed' in message:
        logger.warning('lpr not available, attempting raw /dev/usb/lp0 fallback')
        if ftype not in ('text',):
            return False, (
                'lpr not installed and raw USB mode only supports plain text. '
                'Install CUPS to print PDFs and images.'
            )
        return _raw_print(filepath)

    return False, message


def _print_image(filepath, printer_name=None):
    """Convert image to PDF via img2pdf, then send to lpr."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ['img2pdf', filepath, '-o', tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or 'img2pdf conversion failed'
            return False, f'Image conversion failed: {err}'

        logger.info('Converted %s to PDF for printing', filepath)
        return _lpr_print(tmp_path, printer_name, None, None)
    except FileNotFoundError:
        return False, 'img2pdf not installed — run: sudo apt install img2pdf'
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _lpr_print(filepath, printer_name=None, page_from=None, page_to=None):
    cmd = ['lpr']
    if printer_name:
        cmd += ['-P', printer_name]
    if page_from or page_to:
        start = int(page_from) if page_from else 1
        end = int(page_to) if page_to else 9999
        cmd += ['-o', f'page-ranges={start}-{end}']
    cmd.append(filepath)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=LPR_TIMEOUT,
        )
    except FileNotFoundError:
        return False, 'lpr not installed — please install CUPS'
    except subprocess.TimeoutExpired:
        return False, f'Print job timed out after {LPR_TIMEOUT}s'

    if result.returncode != 0:
        err = result.stderr.strip() or 'unknown error'
        return False, f'Print failed: {err}'

    return True, 'Print job sent successfully'


def _raw_print(filepath):
    usb_path = '/dev/usb/lp0'
    if not os.path.exists(usb_path):
        return False, f'{usb_path} not found — is the printer connected via USB?'

    try:
        with open(filepath, 'rb') as src, open(usb_path, 'wb') as dst:
            dst.write(src.read())
        return True, 'File sent to printer via raw USB'
    except PermissionError:
        return False, (
            f'Permission denied on {usb_path}. '
            'Run: sudo usermod -aG lp pi'
        )
    except OSError as exc:
        return False, f'Raw USB write failed: {exc}'
