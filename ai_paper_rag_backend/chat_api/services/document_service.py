import time as sys_time

from .constants import UPLOADS_DIR


def format_bytes(size):
    if size < 1024:
        return f'{size} B'
    if size < 1024 * 1024:
        return f'{size / 1024:.1f} KB'
    return f'{size / (1024 * 1024):.1f} MB'


def list_uploaded_documents():
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    documents = []
    for path in sorted(UPLOADS_DIR.glob('*.pdf'), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = path.stat()
        documents.append(
            {
                'name': path.name,
                'size': stat.st_size,
                'size_display': format_bytes(stat.st_size),
                'updated_at': stat.st_mtime,
                'updated_at_display': sys_time.strftime('%Y-%m-%d %H:%M:%S', sys_time.localtime(stat.st_mtime)),
                'path': str(path),
            }
        )
    return documents


def get_document_path(document_name):
    return UPLOADS_DIR / document_name


def delete_uploaded_document(document_name):
    file_path = get_document_path(document_name)
    if not file_path.exists():
        raise FileNotFoundError('Document not found.')
    file_path.unlink(missing_ok=True)
