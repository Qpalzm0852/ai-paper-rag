import threading
import time
import uuid

from django.db.utils import OperationalError, ProgrammingError

from chat_api.models import BackgroundTask


TASK_TERMINAL_STATES = {'completed', 'failed'}
MIGRATION_REQUIRED_MESSAGE = 'BackgroundTask table is missing. Run `python manage.py migrate`.'


class TaskRegistry:
    def __init__(self):
        self._lock = threading.Lock()

    def serialize(self, record):
        return {
            'id': record.task_id,
            'task_type': record.task_type,
            'status': record.status,
            'progress': record.progress,
            'message': record.message,
            'created_at': record.created_at,
            'updated_at': record.updated_at,
            'metadata': record.metadata or {},
            'result': record.result,
            'error': record.error or '',
        }

    def create(self, task_type, metadata=None):
        task_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            try:
                BackgroundTask.objects.create(
                    task_id=task_id,
                    task_type=task_type,
                    status='queued',
                    progress=0,
                    message='任务已创建。',
                    created_at=now,
                    updated_at=now,
                    metadata=metadata or {},
                    result=None,
                    error='',
                )
            except (OperationalError, ProgrammingError) as exc:
                raise RuntimeError(MIGRATION_REQUIRED_MESSAGE) from exc
        return task_id

    def update(self, task_id, **fields):
        with self._lock:
            try:
                task = BackgroundTask.objects.get(task_id=task_id)
            except BackgroundTask.DoesNotExist:
                return None
            except (OperationalError, ProgrammingError):
                return None

            for key, value in fields.items():
                setattr(task, key, value)
            task.updated_at = time.time()
            try:
                task.save(update_fields=['status', 'progress', 'message', 'metadata', 'result', 'error', 'updated_at'])
            except (OperationalError, ProgrammingError):
                return None
            return self.serialize(task)

    def get(self, task_id):
        try:
            task = BackgroundTask.objects.get(task_id=task_id)
        except BackgroundTask.DoesNotExist:
            return None
        except (OperationalError, ProgrammingError):
            return None
        return self.serialize(task)

    def list_recent(self, limit=10):
        try:
            tasks = BackgroundTask.objects.order_by('-updated_at', '-id')[:limit]
            return [self.serialize(task) for task in tasks]
        except (OperationalError, ProgrammingError):
            return []

    def cleanup(self, keep_limit=30):
        try:
            task_ids = list(BackgroundTask.objects.order_by('-updated_at', '-id').values_list('task_id', flat=True)[:keep_limit])
            if not task_ids:
                return 0
            deleted_count, _ = BackgroundTask.objects.exclude(task_id__in=task_ids).filter(status__in=TASK_TERMINAL_STATES).delete()
            return deleted_count
        except (OperationalError, ProgrammingError):
            return 0


registry = TaskRegistry()
