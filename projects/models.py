import hashlib
import uuid

from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255, unique=True, blank=True, default='')
    api_key_hash = models.CharField(max_length=128, unique=True, blank=True, default='')
    target_base_url = models.URLField(default='http://localhost:8001')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project'

    def __str__(self):
        return self.name

    def set_api_key(self, raw_key=None):
        if raw_key is None:
            raw_key = f'tb_live_{uuid.uuid4().hex}'
        self.api_key = raw_key
        self.api_key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        self.save(update_fields=['api_key', 'api_key_hash'])
        return raw_key

    def verify_api_key(self, raw_key):
        if not raw_key:
            return False
        return self.api_key_hash == hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
