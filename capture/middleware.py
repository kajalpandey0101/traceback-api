import logging
import time

from django.conf import settings

from capture.services import capture_request, generate_request_id, project_for_api_key

logger = logging.getLogger(__name__)


class TracebackMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self.should_capture(request):
            return self.get_response(request)

        request_id = generate_request_id()
        request.META['TRACEBACK_REQUEST_ID'] = request_id
        request.META['TRACEBACK_PROJECT_KEY'] = request.META.get('HTTP_X_TRACEBACK_KEY', '')
        start = time.perf_counter()
        try:
            response = self.get_response(request)
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self.capture_safely(request, None, request_id, elapsed_ms, error=exc)
            raise
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        try:
            project = project_for_api_key(request.META.get('HTTP_X_TRACEBACK_KEY'))
        except Exception:
            logger.exception('Unable to resolve project for captured request.')
            return response
        if not project:
            return response

        try:
            response['X-Traceback-Request-ID'] = request_id
        except Exception:
            logger.exception('Unable to add request ID to captured response.')
        self.capture_safely(request, response, request_id, elapsed_ms, project=project)
        return response

    @staticmethod
    def capture_safely(request, response, request_id, elapsed_ms, *, error=None, project=None):
        try:
            if project is None:
                project = project_for_api_key(request.META.get('HTTP_X_TRACEBACK_KEY'))
            if project:
                capture_request(
                    project,
                    request,
                    response,
                    request_id=request_id,
                    elapsed_ms=elapsed_ms,
                    error=error,
                )
        except Exception:
            logger.exception('Unable to persist captured request.')

    def should_capture(self, request):
        api_key = request.META.get('HTTP_X_TRACEBACK_KEY')
        if not api_key:
            return False
        path = request.path_info or request.path
        excluded = getattr(
            settings,
            'TRACEBACK_CAPTURE_EXCLUDE_PREFIXES',
            ('/admin', '/static/', '/swagger', '/docs', '/schema', '/health', '/healthz'),
        )
        if any(path.startswith(prefix) for prefix in excluded):
            return False
        return True
