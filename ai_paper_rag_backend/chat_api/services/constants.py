from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOADS_DIR = BASE_DIR / 'uploads'
ENV_FILE_PATH = BASE_DIR / '.env'
COLLECTION_NAME = 'ai_paper'
NO_DOCUMENTS_MESSAGE = 'No indexed documents. Upload a PDF to start.'
