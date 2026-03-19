import os

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'txt'}
MAX_CONTENT_LENGTH = 300 * 1024 * 1024  # 300 MB

# Set to True to delete files from uploads/ after a successful print job
AUTO_DELETE_AFTER_PRINT = False

# Override to force a specific printer name (e.g. 'HP_LaserJet').
# None = use the CUPS default printer.
DEFAULT_PRINTER = None

# Seconds to wait for lpr before giving up
LPR_TIMEOUT = 30
