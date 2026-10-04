import time

from django.http import HttpResponse

from common.redaction import redact_headers
from capture.services import capture_request, generate_request_id, project_for_api_key


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
        response = self.get_response(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        project = project_for_api_key(request.META.get('HTTP_X_TRACEBACK_KEY'))
        if not project:
            return response
        try:
            capture_request(project, request, response, request_id=request_id, elapsed_ms=elapsed_ms)
        except Exception:
            pass
        response['X-Traceback-Request-ID'] = request_id
        return response

    def should_capture(self, request):
        api_key = request.META.get('HTTP_X_TRACEBACK_KEY')
        if not api_key:
            return False
        path = request.path_info or request.path
        excluded = ('/admin', '/static/', '/swagger', '/docs', '/schema', '/health', '/healthz')
        if any(path.startswith(prefix) for prefix in excluded):
            return False
        return True
