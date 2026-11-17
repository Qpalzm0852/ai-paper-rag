import os

from ai_paper_rag_backend.env import get_env

from . import rag_service
from .constants import COLLECTION_NAME, ENV_FILE_PATH
from .document_service import list_uploaded_documents

SETTINGS_FIELDS = [
    {
        'key': 'GOOGLE_API_KEY',
        'label': 'Google API Key',
        'help_text': 'Gemini LLM and embedding requests use this key.',
        'type': 'password',
        'secret': True,
        'default': '',
    },
    {
        'key': 'GOOGLE_LLM_MODEL',
        'label': 'LLM Model',
        'help_text': 'Chat model used by the query engine.',
        'type': 'text',
        'secret': False,
        'default': 'gemini-2.5-flash',
    },
    {
        'key': 'GOOGLE_EMBED_MODEL',
        'label': 'Embedding Model',
        'help_text': 'Embedding model used during indexing and retrieval.',
        'type': 'text',
        'secret': False,
        'default': 'gemini-embedding-001',
    },
    {
        'key': 'LLAMA_PARSE_API_KEY',
        'label': 'LlamaParse API Key',
        'help_text': 'Optional. Enables markdown-oriented PDF parsing when configured.',
        'type': 'password',
        'secret': True,
        'default': '',
    },
    {
        'key': 'CHROMA_DB_PATH',
        'label': 'Chroma DB Path',
        'help_text': 'Persistent vector database directory.',
        'type': 'text',
        'secret': False,
        'default': './rag_core/chroma_db',
    },
    {
        'key': 'HTTP_PROXY',
        'label': 'HTTP Proxy',
        'help_text': 'Optional outbound HTTP proxy.',
        'type': 'text',
        'secret': False,
        'default': '',
    },
    {
        'key': 'HTTPS_PROXY',
        'label': 'HTTPS Proxy',
        'help_text': 'Optional outbound HTTPS proxy.',
        'type': 'text',
        'secret': False,
        'default': '',
    },
    {
        'key': 'NO_PROXY',
        'label': 'NO_PROXY',
        'help_text': 'Comma-separated hosts that bypass proxy settings.',
        'type': 'text',
        'secret': False,
        'default': 'localhost,127.0.0.1',
    },
    {
        'key': 'ANONYMIZED_TELEMETRY',
        'label': 'Anonymized Telemetry',
        'help_text': 'Set to true or false.',
        'type': 'text',
        'secret': False,
        'default': 'False',
    },
]


def mask_secret(value):
    if not value:
        return ''
    if len(value) <= 6:
        return '*' * len(value)
    return f'{value[:3]}{"*" * (len(value) - 6)}{value[-3:]}'


def build_settings_payload():
    items = []
    for field in SETTINGS_FIELDS:
        current_value = get_env(field['key'], field['default'])
        items.append(
            {
                'key': field['key'],
                'label': field['label'],
                'help_text': field['help_text'],
                'type': field['type'],
                'secret': field['secret'],
                'value': current_value,
                'masked_value': mask_secret(current_value) if field['secret'] else current_value,
                'default': field['default'],
            }
        )
    return items


def build_status_snapshot():
    documents = list_uploaded_documents()
    return {
        'rag_ready': rag_service.is_ready(),
        'startup_error': rag_service.get_startup_error(),
        'dependencies_ok': rag_service.get_import_error() is None,
        'rag_import_error': rag_service.get_import_error(),
        'google_api_key_configured': not rag_service.is_placeholder(get_env('GOOGLE_API_KEY')),
        'llama_parse_configured': not rag_service.is_placeholder(get_env('LLAMA_PARSE_API_KEY')),
        'document_count': len(documents),
        'documents': documents[:6],
        'vector_record_count': rag_service.get_collection_count(),
        'collection_name': COLLECTION_NAME,
        'uploads_dir': str(rag_service.UPLOADS_DIR),
        'chroma_db_path': rag_service.get_chroma_path(),
        'models': {
            'llm': get_env('GOOGLE_LLM_MODEL', 'gemini-2.5-flash'),
            'embedding': get_env('GOOGLE_EMBED_MODEL', 'gemini-embedding-001'),
        },
        'recent_tasks': rag_service.list_recent_tasks(limit=6),
    }


def persist_env_updates(updates):
    ENV_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = []
    if ENV_FILE_PATH.exists():
        existing_lines = ENV_FILE_PATH.read_text(encoding='utf-8').splitlines()

    remaining = dict(updates)
    output_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in line:
            output_lines.append(line)
            continue

        key, _ = line.split('=', 1)
        key = key.strip()
        if key in remaining:
            output_lines.append(f'{key}={remaining.pop(key)}')
        else:
            output_lines.append(line)

    for key, value in remaining.items():
        output_lines.append(f'{key}={value}')

    ENV_FILE_PATH.write_text('\n'.join(output_lines).rstrip() + '\n', encoding='utf-8')


def update_runtime_env(updates):
    for key, value in updates.items():
        os.environ[key] = value


def save_settings(submitted_items):
    allowed_keys = {field['key'] for field in SETTINGS_FIELDS}
    updates = {}
    for key, value in submitted_items.items():
        if key not in allowed_keys:
            continue
        updates[key] = str(value or '').strip()

    if not updates:
        raise ValueError('No valid settings were provided.')

    persist_env_updates(updates)
    update_runtime_env(updates)
    rag_service.refresh_engine()
    return {
        'settings': build_settings_payload(),
        'status': build_status_snapshot(),
    }
