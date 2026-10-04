from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def root_health_view(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)
    return JsonResponse({'project': 'Traceback', 'status': 'ok'})


def echo_view(request):
    payload = {"message": "ok", "method": request.method, "path": request.path}
    if request.method in {'POST', 'PUT', 'PATCH'}:
        try:
            payload['body'] = request.body.decode('utf-8')
        except Exception:
            payload['body'] = str(request.body)
    return JsonResponse(payload)


urlpatterns = [
    path('', root_health_view, name='root-health'),
    path('admin/', admin.site.urls),
    path('api/test/echo/', echo_view, name='echo-view'),
    path('api/', include('projects.urls')),
    path('api/', include('capture.urls')),
    path('api/', include('replays.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
