from celery import shared_task

from capture.models import CapturedRequest


@shared_task
def cleanup_expired_requests():
    CapturedRequest.objects.filter(expires_at__isnull=False, expires_at__lt=models_now()).delete()


def models_now():
    from django.utils import timezone
    return timezone.now()
