import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from chat_api.services import document_service, rag_service, settings_service


def read_request_json(request):
    try:
        return json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return None


def read_focus_documents(payload):
    raw_documents = payload.get('focus_documents')
    if not isinstance(raw_documents, list):
        return []
    return [str(document_name or '').strip() for document_name in raw_documents if str(document_name or '').strip()]


def read_comparison_mode(payload):
    return bool(payload.get('comparison_mode'))


def read_paper_brief_mode(payload):
    return bool(payload.get('paper_brief_mode'))


def status_api(request):
    if request.method != 'GET':
        return JsonResponse({'code': 405, 'msg': 'Only GET is supported.'})
    return JsonResponse({'code': 200, 'data': settings_service.build_status_snapshot()})


def task_status_api(request, task_id):
    if request.method != 'GET':
        return JsonResponse({'code': 405, 'msg': 'Only GET is supported.'})

    task = rag_service.get_task(task_id)
    if not task:
        return JsonResponse({'code': 404, 'msg': 'Task not found.'})
    return JsonResponse({'code': 200, 'data': task})


@csrf_exempt
def settings_api(request):
    if request.method == 'GET':
        return JsonResponse({'code': 200, 'data': settings_service.build_settings_payload()})

    if request.method not in {'POST', 'PUT'}:
        return JsonResponse({'code': 405, 'msg': 'Only GET, POST and PUT are supported.'})

    payload = read_request_json(request)
    if payload is None:
        return JsonResponse({'code': 400, 'msg': 'Invalid JSON payload.'})

    try:
        data = settings_service.save_settings(payload.get('settings') or {})
        return JsonResponse({'code': 200, 'msg': 'Settings saved successfully.', 'data': data})
    except ValueError as exc:
        return JsonResponse({'code': 400, 'msg': str(exc)})
    except Exception as exc:
        return JsonResponse({'code': 500, 'msg': f'Failed to save settings: {exc}'})


@csrf_exempt
def documents_api(request):
    if request.method == 'GET':
        return JsonResponse({'code': 200, 'data': document_service.list_uploaded_documents()})

    if request.method != 'DELETE':
        return JsonResponse({'code': 405, 'msg': 'Only GET and DELETE are supported.'})

    payload = read_request_json(request)
    if payload is None:
        return JsonResponse({'code': 400, 'msg': 'Invalid JSON payload.'})

    document_name = (payload.get('name') or '').strip()
    if not document_name:
        return JsonResponse({'code': 400, 'msg': 'Document name is required.'})

    try:
        document_service.delete_uploaded_document(document_name)
        rag_service.delete_document_entries(document_name)
        return JsonResponse(
            {
                'code': 200,
                'msg': f'Deleted {document_name}.',
                'data': document_service.list_uploaded_documents(),
                'status': settings_service.build_status_snapshot(),
            }
        )
    except FileNotFoundError as exc:
        return JsonResponse({'code': 404, 'msg': str(exc)})
    except RuntimeError as exc:
        return JsonResponse({'code': 500, 'msg': str(exc)})
    except Exception as exc:
        return JsonResponse({'code': 500, 'msg': f'Failed to delete document: {exc}'})


@csrf_exempt
def ask_paper(request):
    if request.method != 'POST':
        return JsonResponse({'code': 405, 'msg': 'Only POST is supported.'})

    if not rag_service.is_ready():
        return JsonResponse({'code': 500, 'msg': rag_service.get_unavailable_message()})

    payload = read_request_json(request)
    if payload is None:
        return JsonResponse({'code': 400, 'msg': 'Invalid JSON payload.'})

    user_question = (payload.get('question') or '').strip()
    if not user_question:
        return JsonResponse({'code': 400, 'msg': 'Question cannot be empty.'})
    focus_documents = read_focus_documents(payload)
    comparison_mode = read_comparison_mode(payload)
    paper_brief_mode = read_paper_brief_mode(payload)

    if comparison_mode and paper_brief_mode:
        return JsonResponse({'code': 400, 'msg': 'Comparison mode and paper brief mode cannot be enabled together.'})
    if comparison_mode and len(focus_documents) < 2:
        return JsonResponse({'code': 400, 'msg': 'Comparison mode requires at least two focused documents.'})
    if paper_brief_mode and len(focus_documents) != 1:
        return JsonResponse({'code': 400, 'msg': 'Paper brief mode requires exactly one focused document.'})

    def stream_generator():
        try:
            for text in rag_service.query_stream(
                user_question,
                focus_documents=focus_documents,
                comparison_mode=comparison_mode,
                paper_brief_mode=paper_brief_mode,
            ):
                yield text
        except Exception as exc:
            yield f'\n[Model request failed: {exc}]'

    return StreamingHttpResponse(stream_generator(), content_type='text/plain; charset=utf-8')


@csrf_exempt
def ask_paper_json(request):
    if request.method != 'POST':
        return JsonResponse({'code': 405, 'msg': 'Only POST is supported.'})

    if not rag_service.is_ready():
        return JsonResponse({'code': 500, 'msg': rag_service.get_unavailable_message()})

    payload = read_request_json(request)
    if payload is None:
        return JsonResponse({'code': 400, 'msg': 'Invalid JSON payload.'})

    user_question = (payload.get('question') or '').strip()
    if not user_question:
        return JsonResponse({'code': 400, 'msg': 'Question cannot be empty.'})
    focus_documents = read_focus_documents(payload)
    comparison_mode = read_comparison_mode(payload)
    paper_brief_mode = read_paper_brief_mode(payload)

    if comparison_mode and paper_brief_mode:
        return JsonResponse({'code': 400, 'msg': 'Comparison mode and paper brief mode cannot be enabled together.'})
    if comparison_mode and len(focus_documents) < 2:
        return JsonResponse({'code': 400, 'msg': 'Comparison mode requires at least two focused documents.'})
    if paper_brief_mode and len(focus_documents) != 1:
        return JsonResponse({'code': 400, 'msg': 'Paper brief mode requires exactly one focused document.'})

    try:
        return JsonResponse(
            {
                'code': 200,
                'data': rag_service.query_json(
                    user_question,
                    focus_documents=focus_documents,
                    comparison_mode=comparison_mode,
                    paper_brief_mode=paper_brief_mode,
                ),
            }
        )
    except Exception as exc:
        return JsonResponse({'code': 500, 'msg': f'Model request failed: {exc}'})


@csrf_exempt
def upload_paper(request):
    if request.method != 'POST' or not request.FILES.get('file'):
        return JsonResponse({'code': 400, 'msg': 'A PDF file upload is required.'})

    try:
        task_id, filename = rag_service.start_async_upload(request.FILES['file'])
        return JsonResponse(
            {
                'code': 202,
                'msg': f'Upload accepted for {filename}. Indexing is running in the background.',
                'data': {
                    'task_id': task_id,
                    'file_name': filename,
                },
                'status': settings_service.build_status_snapshot(),
            }
        )
    except RuntimeError as exc:
        return JsonResponse({'code': 500, 'msg': str(exc)})
    except Exception as exc:
        return JsonResponse({'code': 500, 'msg': f'Upload failed: {exc}'})
