from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from chat_api.models import BackgroundTask
from chat_api.services.task_service import registry


class ChatApiViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_status_api_returns_snapshot(self):
        response = self.client.get('/api/status/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 200)
        self.assertIn('rag_ready', payload['data'])
        self.assertIn('document_count', payload['data'])
        self.assertIn('recent_tasks', payload['data'])

    @patch('chat_api.views.settings_service.save_settings')
    def test_settings_api_updates_allowed_keys(self, save_settings_mock):
        save_settings_mock.return_value = {'settings': [], 'status': {}}
        response = self.client.put(
            '/api/settings/',
            data='{"settings": {"GOOGLE_LLM_MODEL": "gemini-test", "IGNORED": "value"}}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 200)
        save_settings_mock.assert_called_once_with({'GOOGLE_LLM_MODEL': 'gemini-test', 'IGNORED': 'value'})

    @patch('chat_api.views.settings_service.save_settings')
    def test_settings_api_rejects_empty_payload(self, save_settings_mock):
        save_settings_mock.side_effect = ValueError('No valid settings were provided.')
        response = self.client.put('/api/settings/', data='{"settings": {}}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 400)

    @patch('chat_api.views.rag_service.query_json')
    @patch('chat_api.views.rag_service.is_ready')
    def test_ask_paper_json_returns_structured_payload(self, is_ready_mock, query_json_mock):
        is_ready_mock.return_value = True
        query_json_mock.return_value = {
            'question': 'test question',
            'answer': 'test answer',
            'sources': [{'file_name': 'paper.pdf', 'page_label': '2', 'snippet': 'snippet', 'score': 0.91}],
            'source_count': 1,
            'focused_documents': ['paper.pdf'],
            'comparison_mode': False,
            'comparison_brief': None,
            'paper_brief_mode': False,
            'paper_brief': None,
        }

        response = self.client.post(
            '/api/ask-json/',
            data='{"question": "test question", "focus_documents": ["paper.pdf"]}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['source_count'], 1)
        self.assertEqual(payload['data']['focused_documents'], ['paper.pdf'])
        self.assertFalse(payload['data']['comparison_mode'])
        self.assertFalse(payload['data']['paper_brief_mode'])
        query_json_mock.assert_called_once_with('test question', focus_documents=['paper.pdf'], comparison_mode=False, paper_brief_mode=False)

    @patch('chat_api.views.rag_service.query_json')
    @patch('chat_api.views.rag_service.is_ready')
    def test_ask_paper_json_supports_comparison_mode(self, is_ready_mock, query_json_mock):
        is_ready_mock.return_value = True
        query_json_mock.return_value = {
            'question': 'compare question',
            'answer': 'compare answer',
            'sources': [
                {'file_name': 'paper-a.pdf', 'page_label': '2', 'snippet': 'a snippet', 'score': 0.88},
                {'file_name': 'paper-b.pdf', 'page_label': '5', 'snippet': 'b snippet', 'score': 0.9},
            ],
            'source_count': 2,
            'focused_documents': ['paper-a.pdf', 'paper-b.pdf'],
            'comparison_mode': True,
            'comparison_brief': {
                'documents': ['paper-a.pdf', 'paper-b.pdf'],
                'summary': 'comparison summary',
                'evidence': [],
                'missing_documents': [],
            },
            'paper_brief_mode': False,
            'paper_brief': None,
        }

        response = self.client.post(
            '/api/ask-json/',
            data='{"question": "compare question", "focus_documents": ["paper-a.pdf", "paper-b.pdf"], "comparison_mode": true}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 200)
        self.assertTrue(payload['data']['comparison_mode'])
        self.assertEqual(payload['data']['comparison_brief']['documents'], ['paper-a.pdf', 'paper-b.pdf'])
        query_json_mock.assert_called_once_with(
            'compare question',
            focus_documents=['paper-a.pdf', 'paper-b.pdf'],
            comparison_mode=True,
            paper_brief_mode=False,
        )

    @patch('chat_api.views.rag_service.query_json')
    @patch('chat_api.views.rag_service.is_ready')
    def test_ask_paper_json_supports_paper_brief_mode(self, is_ready_mock, query_json_mock):
        is_ready_mock.return_value = True
        query_json_mock.return_value = {
            'question': 'brief question',
            'answer': '## 研究问题\nfoo',
            'sources': [{'file_name': 'paper-a.pdf', 'page_label': '3', 'snippet': 'summary snippet', 'score': 0.86}],
            'source_count': 1,
            'focused_documents': ['paper-a.pdf'],
            'comparison_mode': False,
            'comparison_brief': None,
            'paper_brief_mode': True,
            'paper_brief': {
                'document': 'paper-a.pdf',
                'summary': 'brief summary',
                'source_count': 1,
                'page_labels': ['3'],
                'top_snippets': ['summary snippet'],
            },
        }

        response = self.client.post(
            '/api/ask-json/',
            data='{"question": "brief question", "focus_documents": ["paper-a.pdf"], "paper_brief_mode": true}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 200)
        self.assertTrue(payload['data']['paper_brief_mode'])
        self.assertEqual(payload['data']['paper_brief']['document'], 'paper-a.pdf')
        query_json_mock.assert_called_once_with(
            'brief question',
            focus_documents=['paper-a.pdf'],
            comparison_mode=False,
            paper_brief_mode=True,
        )

    @patch('chat_api.views.rag_service.is_ready')
    def test_ask_paper_json_rejects_comparison_mode_with_single_document(self, is_ready_mock):
        is_ready_mock.return_value = True

        response = self.client.post(
            '/api/ask-json/',
            data='{"question": "compare question", "focus_documents": ["paper-a.pdf"], "comparison_mode": true}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 400)

    @patch('chat_api.views.rag_service.is_ready')
    def test_ask_paper_json_rejects_paper_brief_mode_with_multiple_documents(self, is_ready_mock):
        is_ready_mock.return_value = True

        response = self.client.post(
            '/api/ask-json/',
            data='{"question": "brief question", "focus_documents": ["paper-a.pdf", "paper-b.pdf"], "paper_brief_mode": true}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 400)

    @patch('chat_api.views.settings_service.build_status_snapshot')
    @patch('chat_api.views.rag_service.start_async_upload')
    def test_upload_paper_returns_async_task_payload(self, start_async_upload_mock, build_status_snapshot_mock):
        start_async_upload_mock.return_value = ('task-123', 'paper.pdf')
        build_status_snapshot_mock.return_value = {'recent_tasks': []}

        response = self.client.post(
            '/api/upload/',
            data={'file': SimpleUploadedFile('paper.pdf', b'%PDF-1.4 test file', content_type='application/pdf')},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 202)
        self.assertEqual(payload['data']['task_id'], 'task-123')
        self.assertEqual(payload['data']['file_name'], 'paper.pdf')
        start_async_upload_mock.assert_called_once()

    @patch('chat_api.views.rag_service.get_task')
    def test_task_status_api_returns_task_payload(self, get_task_mock):
        get_task_mock.return_value = {
            'id': 'task-123',
            'task_type': 'document_index',
            'status': 'running',
            'progress': 42,
            'message': '正在索引',
            'metadata': {'file_name': 'paper.pdf'},
            'result': None,
            'error': '',
        }

        response = self.client.get('/api/tasks/task-123/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 200)
        self.assertEqual(payload['data']['status'], 'running')
        self.assertEqual(payload['data']['progress'], 42)

    @patch('chat_api.views.rag_service.get_task')
    def test_task_status_api_returns_404_for_missing_task(self, get_task_mock):
        get_task_mock.return_value = None

        response = self.client.get('/api/tasks/missing-task/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 404)

    def test_task_registry_persists_task_records(self):
        task_id = registry.create('document_index', {'file_name': 'paper.pdf'})
        registry.update(task_id, status='running', progress=65, message='处理中')

        record = BackgroundTask.objects.get(task_id=task_id)
        self.assertEqual(record.task_type, 'document_index')
        self.assertEqual(record.status, 'running')
        self.assertEqual(record.progress, 65)
        self.assertEqual(record.metadata['file_name'], 'paper.pdf')

        task = registry.get(task_id)
        self.assertEqual(task['status'], 'running')
        self.assertEqual(task['progress'], 65)
