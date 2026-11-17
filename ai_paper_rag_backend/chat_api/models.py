from django.db import models


class BackgroundTask(models.Model):
    task_id = models.CharField(max_length=64, unique=True)
    task_type = models.CharField(max_length=64)
    status = models.CharField(max_length=32, default='queued')
    progress = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default='')
    created_at = models.FloatField()
    updated_at = models.FloatField()

    class Meta:
        ordering = ['-updated_at', '-id']

    def __str__(self):
        return f'{self.task_type}:{self.task_id}:{self.status}'
