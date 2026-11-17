import os
import threading
import time as sys_time
from pathlib import Path

from django.core.files.storage import FileSystemStorage

from ai_paper_rag_backend.env import get_env, load_env

from .constants import COLLECTION_NAME, NO_DOCUMENTS_MESSAGE, UPLOADS_DIR
from .document_service import format_bytes
from .task_service import registry

load_env()

RAG_IMPORT_ERROR = None
chromadb = None
VectorStoreIndex = None
Settings = None
StorageContext = None
SimpleDirectoryReader = None
ChromaVectorStore = None
GoogleGenAI = None
GoogleGenAIEmbedding = None
LlamaParse = None
MarkdownNodeParser = None
SentenceSplitter = None
MetadataFilter = None
MetadataFilters = None
FilterCondition = None

try:
    import chromadb
    from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
    from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
    from llama_index.core.vector_stores import FilterCondition, MetadataFilter, MetadataFilters
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
    from llama_index.llms.google_genai import GoogleGenAI
    from llama_index.vector_stores.chroma import ChromaVectorStore
    from llama_parse import LlamaParse
except Exception as exc:
    RAG_IMPORT_ERROR = str(exc)

index = None
query_engine = None
startup_error = None
engine_lock = threading.Lock()


def apply_runtime_env():
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'GOOGLE_API_KEY', 'ANONYMIZED_TELEMETRY'):
        value = get_env(key)
        if value and not value.startswith('your-'):
            os.environ[key] = value


def is_placeholder(value):
    return not value or value.startswith('your-') or value.startswith('change-me')


def get_chroma_path():
    return get_env('CHROMA_DB_PATH', './rag_core/chroma_db')


def normalize_focus_documents(focus_documents):
    if not focus_documents:
        return []

    normalized = []
    seen = set()
    for document_name in focus_documents:
        name = str(document_name or '').strip()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    return normalized


def build_focus_filters(focus_documents):
    global MetadataFilter, MetadataFilters, FilterCondition

    normalized = normalize_focus_documents(focus_documents)
    if not normalized:
        return None

    if not all([MetadataFilters, MetadataFilter, FilterCondition]):
        try:
            from llama_index.core.vector_stores import FilterCondition as ImportedFilterCondition
            from llama_index.core.vector_stores import MetadataFilter as ImportedMetadataFilter
            from llama_index.core.vector_stores import MetadataFilters as ImportedMetadataFilters
        except Exception:
            return None

        MetadataFilter = ImportedMetadataFilter
        MetadataFilters = ImportedMetadataFilters
        FilterCondition = ImportedFilterCondition

    return MetadataFilters(
        filters=[MetadataFilter(key='source_file', value=document_name) for document_name in normalized],
        condition=FilterCondition.OR,
    )


def build_query_engine(current_index, focus_documents=None):
    query_kwargs = {
        'streaming': True,
        'similarity_top_k': 4,
    }
    filters = build_focus_filters(focus_documents)
    if filters is not None:
        query_kwargs['filters'] = filters
    return current_index.as_query_engine(**query_kwargs)


def configure_models():
    Settings.llm = GoogleGenAI(model=get_env('GOOGLE_LLM_MODEL', 'gemini-2.5-flash'))
    Settings.embed_model = GoogleGenAIEmbedding(model_name=get_env('GOOGLE_EMBED_MODEL', 'gemini-embedding-001'))


def get_collection():
    db = chromadb.PersistentClient(path=get_chroma_path())
    return db.get_or_create_collection(COLLECTION_NAME)


def get_index_batch_pause_seconds():
    try:
        return max(0.0, float(get_env('INDEX_BATCH_PAUSE_SECONDS', '0')))
    except (TypeError, ValueError):
        return 0.0


def extract_node_text(node):
    text = getattr(node, 'text', '') or ''
    if text:
        return text.strip()

    get_content = getattr(node, 'get_content', None)
    if callable(get_content):
        try:
            return (get_content() or '').strip()
        except TypeError:
            try:
                return (get_content(metadata_mode='none') or '').strip()
            except Exception:
                return ''
        except Exception:
            return ''

    return ''


def serialize_source_nodes(response, limit=4):
    source_nodes = getattr(response, 'source_nodes', None) or []
    if not source_nodes:
        return []

    seen = set()
    cards = []

    for source_node in source_nodes[:limit]:
        node = getattr(source_node, 'node', source_node)
        metadata = getattr(node, 'metadata', {}) or {}
        file_name = (
            metadata.get('source_file')
            or metadata.get('file_name')
            or metadata.get('filename')
            or metadata.get('document_title')
            or metadata.get('file_path')
            or 'Unknown document'
        )
        page_label = metadata.get('page_label') or metadata.get('page') or metadata.get('page_number')
        key = (file_name, page_label)
        if key in seen:
            continue
        seen.add(key)

        snippet = extract_node_text(node).replace('\n', ' ').strip()
        if len(snippet) > 240:
            snippet = snippet[:240].rstrip() + '...'

        score = getattr(source_node, 'score', None)
        cards.append(
            {
                'file_name': file_name,
                'page_label': str(page_label) if page_label is not None else '',
                'snippet': snippet,
                'score': round(float(score), 4) if score is not None else None,
                'metadata': {str(meta_key): str(meta_value) for meta_key, meta_value in metadata.items() if meta_value not in (None, '')},
            }
        )

    return cards


def format_sources(response):
    cards = serialize_source_nodes(response, limit=3)
    if not cards:
        return ''

    lines = ['', '', '---', '**参考来源**']
    for card in cards:
        line = f"- `{card['file_name']}`"
        if card['page_label']:
            line += f" 第 {card['page_label']} 页"
        if card['snippet']:
            line += f": {card['snippet']}"
        lines.append(line)
    return '\n'.join(lines)


def filter_serialized_sources(sources, focus_documents):
    normalized = set(normalize_focus_documents(focus_documents))
    if not normalized:
        return sources
    return [source for source in sources if source.get('file_name') in normalized]


def attach_source_metadata(nodes, filename):
    for node in nodes:
        metadata = getattr(node, 'metadata', None)
        if metadata is None:
            metadata = {}
            setattr(node, 'metadata', metadata)
        metadata.setdefault('source_file', filename)
        metadata.setdefault('file_name', filename)
    return nodes


def collect_response_text(response):
    response_gen = getattr(response, 'response_gen', None)
    if response_gen is None:
        return str(getattr(response, 'response', response))

    chunks = []
    for text in response_gen:
        chunks.append(text)
    combined = ''.join(chunks).strip()
    if combined:
        return combined
    return str(getattr(response, 'response', response))


def set_empty_engine_state():
    global index, query_engine, startup_error
    index = None
    query_engine = None
    startup_error = NO_DOCUMENTS_MESSAGE


def refresh_engine():
    global index, query_engine, startup_error

    with engine_lock:
        if RAG_IMPORT_ERROR:
            startup_error = f'RAG dependencies not installed: {RAG_IMPORT_ERROR}'
            index = None
            query_engine = None
            return

        apply_runtime_env()
        google_api_key = get_env('GOOGLE_API_KEY')
        if is_placeholder(google_api_key):
            startup_error = 'GOOGLE_API_KEY is not configured.'
            index = None
            query_engine = None
            return

        try:
            configure_models()
            chroma_collection = get_collection()
            if chroma_collection.count() == 0:
                set_empty_engine_state()
                return

            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            query_engine = build_query_engine(index)
            startup_error = None
        except Exception as exc:
            startup_error = f'RAG initialization failed: {exc}'
            index = None
            query_engine = None


def get_unavailable_message():
    return startup_error or 'RAG engine is unavailable.'


def is_ready():
    return bool(query_engine)


def get_startup_error():
    return startup_error


def get_import_error():
    return RAG_IMPORT_ERROR


def get_collection_count():
    if RAG_IMPORT_ERROR:
        return 0

    try:
        return get_collection().count()
    except Exception:
        return 0


def build_focus_prompt(question, focus_documents):
    normalized = normalize_focus_documents(focus_documents)
    if not normalized:
        return question
    scoped_documents = '、'.join(f'《{document_name}》' for document_name in normalized)
    return f'请优先仅依据以下文献回答：{scoped_documents}。\n\n用户问题：{question}'


def build_comparison_prompt(question, focus_documents):
    normalized = normalize_focus_documents(focus_documents)
    if len(normalized) < 2:
        return question

    scoped_documents = '、'.join(f'《{document_name}》' for document_name in normalized)
    return (
        f'你正在执行多文献对比问答，请严格依据以下文献进行分析：{scoped_documents}。\n'
        '请按以下结构组织回答：\n'
        '1. 研究问题对比\n'
        '2. 核心方法对比\n'
        '3. 实验结论或主要发现\n'
        '4. 适用场景与局限\n'
        '如果某一项证据不足，请明确说明“文献中未提供充分证据”。\n\n'
        f'用户问题：{question}'
    )


def build_paper_brief_prompt(question, focus_documents):
    normalized = normalize_focus_documents(focus_documents)
    if len(normalized) != 1:
        return question

    document_name = normalized[0]
    return (
        f'你正在为《{document_name}》生成论文速览卡，请严格只依据这篇文献。\n'
        '请严格使用以下 Markdown 二级标题输出：\n'
        '## 研究问题\n'
        '## 核心方法\n'
        '## 实验设计\n'
        '## 主要结论\n'
        '## 价值与局限\n'
        '每个部分用 2 到 4 句话概括，信息不足时直接说明证据不足。\n\n'
        f'用户问题：{question}'
    )


def summarize_sources_by_document(sources):
    grouped = []
    index_by_name = {}

    for source in sources:
        file_name = source.get('file_name') or 'Unknown document'
        if file_name not in index_by_name:
            index_by_name[file_name] = len(grouped)
            grouped.append(
                {
                    'file_name': file_name,
                    'source_count': 0,
                    'page_labels': [],
                    'top_snippets': [],
                    'best_score': None,
                }
            )

        bucket = grouped[index_by_name[file_name]]
        bucket['source_count'] += 1

        page_label = str(source.get('page_label') or '').strip()
        if page_label and page_label not in bucket['page_labels']:
            bucket['page_labels'].append(page_label)

        snippet = str(source.get('snippet') or '').strip()
        if snippet and snippet not in bucket['top_snippets'] and len(bucket['top_snippets']) < 2:
            bucket['top_snippets'].append(snippet)

        score = source.get('score')
        if score is not None and (bucket['best_score'] is None or score > bucket['best_score']):
            bucket['best_score'] = score

    return grouped


def build_comparison_brief(question, focus_documents, sources):
    normalized = normalize_focus_documents(focus_documents)
    if len(normalized) < 2:
        return None

    evidence = summarize_sources_by_document(sources)
    covered_documents = {item['file_name'] for item in evidence}
    missing_documents = [document_name for document_name in normalized if document_name not in covered_documents]

    summary = f'本次回答按多文献对比模式生成，目标比较 {len(normalized)} 篇文献，当前证据命中 {len(evidence)} 篇。'
    if missing_documents:
        summary += ' 有部分文献未直接命中来源卡片，说明该轮检索证据较弱。'

    return {
        'question': question,
        'documents': normalized,
        'summary': summary,
        'evidence': evidence,
        'missing_documents': missing_documents,
    }


def build_paper_brief(question, focus_documents, sources):
    normalized = normalize_focus_documents(focus_documents)
    if len(normalized) != 1:
        return None

    document_name = normalized[0]
    evidence = summarize_sources_by_document(sources)
    target_evidence = next((item for item in evidence if item['file_name'] == document_name), None)
    if target_evidence is None:
        target_evidence = {
            'file_name': document_name,
            'source_count': 0,
            'page_labels': [],
            'top_snippets': [],
        }

    summary = f'当前速览卡围绕《{document_name}》生成，共命中 {target_evidence["source_count"]} 条来源证据。'
    if not target_evidence['source_count']:
        summary += ' 当前回答更依赖模型概括，建议继续补充更具体的问题以增强证据覆盖。'

    return {
        'question': question,
        'document': document_name,
        'summary': summary,
        'source_count': target_evidence['source_count'],
        'page_labels': target_evidence['page_labels'],
        'top_snippets': target_evidence['top_snippets'],
    }


def run_query(question, focus_documents=None, comparison_mode=False, paper_brief_mode=False):
    if not query_engine:
        raise RuntimeError(get_unavailable_message())

    normalized_focus_documents = normalize_focus_documents(focus_documents)
    if comparison_mode and paper_brief_mode:
        raise RuntimeError('Comparison mode and paper brief mode cannot be enabled together.')
    if comparison_mode and len(normalized_focus_documents) < 2:
        raise RuntimeError('Comparison mode requires at least two focused documents.')
    if paper_brief_mode and len(normalized_focus_documents) != 1:
        raise RuntimeError('Paper brief mode requires exactly one focused document.')

    if comparison_mode:
        prompt_question = build_comparison_prompt(question, normalized_focus_documents)
    elif paper_brief_mode:
        prompt_question = build_paper_brief_prompt(question, normalized_focus_documents)
    else:
        prompt_question = question

    if not normalized_focus_documents:
        return query_engine.query(prompt_question)

    if index is None:
        raise RuntimeError(get_unavailable_message())

    try:
        scoped_query_engine = build_query_engine(index, normalized_focus_documents)
        return scoped_query_engine.query(prompt_question)
    except Exception:
        fallback_question = build_focus_prompt(prompt_question, normalized_focus_documents)
        return query_engine.query(fallback_question)


def query_stream(question, focus_documents=None, comparison_mode=False, paper_brief_mode=False):
    response = run_query(
        question,
        focus_documents=focus_documents,
        comparison_mode=comparison_mode,
        paper_brief_mode=paper_brief_mode,
    )
    response_gen = getattr(response, 'response_gen', None)
    if response_gen is not None:
        for text in response_gen:
            yield text
    else:
        yield str(response)

    sources_text = format_sources(response)
    if sources_text:
        yield sources_text


def query_json(question, focus_documents=None, comparison_mode=False, paper_brief_mode=False):
    normalized_focus_documents = normalize_focus_documents(focus_documents)
    response = run_query(
        question,
        focus_documents=normalized_focus_documents,
        comparison_mode=comparison_mode,
        paper_brief_mode=paper_brief_mode,
    )
    sources = filter_serialized_sources(serialize_source_nodes(response), normalized_focus_documents)
    return {
        'question': question,
        'answer': collect_response_text(response),
        'sources': sources,
        'source_count': len(sources),
        'focused_documents': normalized_focus_documents,
        'comparison_mode': bool(comparison_mode),
        'comparison_brief': build_comparison_brief(question, normalized_focus_documents, sources),
        'paper_brief_mode': bool(paper_brief_mode),
        'paper_brief': build_paper_brief(question, normalized_focus_documents, sources),
    }


def delete_document_entries(document_name):
    if RAG_IMPORT_ERROR:
        raise RuntimeError(get_unavailable_message())

    chroma_collection = get_collection()
    chroma_collection.delete(where={'source_file': document_name})
    refresh_engine()


def ensure_indexing_ready():
    global startup_error

    if RAG_IMPORT_ERROR:
        raise RuntimeError(get_unavailable_message())

    apply_runtime_env()
    google_api_key = get_env('GOOGLE_API_KEY')
    if is_placeholder(google_api_key):
        startup_error = 'GOOGLE_API_KEY is not configured.'
        raise RuntimeError(get_unavailable_message())

    configure_models()


def save_uploaded_file(uploaded_file):
    fs = FileSystemStorage(location=str(UPLOADS_DIR))
    filename = fs.save(uploaded_file.name, uploaded_file)
    return filename, fs.path(filename)


def _extract_nodes_for_file(file_path, filename, task_id=None):
    nodes = []
    llama_parse_key = get_env('LLAMA_PARSE_API_KEY')
    if task_id:
        registry.update(task_id, status='running', progress=18, message='正在解析 PDF 内容。')
    try:
        if not is_placeholder(llama_parse_key):
            parser = LlamaParse(api_key=llama_parse_key, result_type='markdown')
            documents = parser.load_data(file_path)
            nodes = MarkdownNodeParser().get_nodes_from_documents(documents)
    except Exception:
        nodes = []

    if not nodes:
        if task_id:
            registry.update(task_id, status='running', progress=34, message='使用本地切块器提取文本。')
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        nodes = SentenceSplitter(chunk_size=512, chunk_overlap=50).get_nodes_from_documents(documents)

    nodes = attach_source_metadata(nodes, filename)
    if not nodes:
        raise RuntimeError('Failed to extract content from the uploaded file.')
    return nodes


def _insert_nodes(nodes, task_id=None):
    global index, query_engine, startup_error

    chroma_collection = get_collection()
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    batch_size = 10

    if index is None:
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex(nodes[:batch_size], storage_context=storage_context)
        start_idx = batch_size
    else:
        start_idx = 0

    total_batches = max(1, ((len(nodes) - start_idx) + batch_size - 1) // batch_size) if len(nodes) > start_idx else 1
    processed_batches = 0

    pause_seconds = get_index_batch_pause_seconds()

    for i in range(start_idx, len(nodes), batch_size):
        if i > 0 and pause_seconds:
            sys_time.sleep(pause_seconds)
        batch = nodes[i:i + batch_size]
        index.insert_nodes(batch)
        processed_batches += 1
        if task_id:
            progress = 50 + int((processed_batches / total_batches) * 40)
            registry.update(task_id, status='running', progress=min(progress, 95), message=f'正在写入向量库，第 {processed_batches}/{total_batches} 批。')

    query_engine = build_query_engine(index)
    startup_error = None


def build_document_payload(file_path, filename):
    document_stat = Path(file_path).stat()
    return {
        'name': filename,
        'size': document_stat.st_size,
        'size_display': format_bytes(document_stat.st_size),
        'updated_at': document_stat.st_mtime,
        'updated_at_display': sys_time.strftime('%Y-%m-%d %H:%M:%S', sys_time.localtime(document_stat.st_mtime)),
        'path': str(file_path),
    }


def upload_document(uploaded_file):
    global index, query_engine, startup_error

    ensure_indexing_ready()
    filename, file_path = save_uploaded_file(uploaded_file)
    nodes = _extract_nodes_for_file(file_path, filename)

    with engine_lock:
        _insert_nodes(nodes)

    return build_document_payload(file_path, filename)


def start_async_upload(uploaded_file):
    ensure_indexing_ready()
    filename, file_path = save_uploaded_file(uploaded_file)
    task_id = registry.create('document_index', {'file_name': filename})

    def runner():
        try:
            registry.update(task_id, status='running', progress=8, message='文件已保存，等待索引启动。')
            nodes = _extract_nodes_for_file(file_path, filename, task_id=task_id)
            registry.update(task_id, status='running', progress=46, message=f'已生成 {len(nodes)} 个文本分块。')
            with engine_lock:
                _insert_nodes(nodes, task_id=task_id)
            document = build_document_payload(file_path, filename)
            registry.update(task_id, status='completed', progress=100, message='索引完成。', result=document)
        except Exception as exc:
            registry.update(task_id, status='failed', progress=100, message='索引失败。', error=str(exc))

    threading.Thread(target=runner, daemon=True).start()
    return task_id, filename


def get_task(task_id):
    return registry.get(task_id)


def list_recent_tasks(limit=10):
    return registry.list_recent(limit=limit)


refresh_engine()





