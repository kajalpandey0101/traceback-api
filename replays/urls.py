from django.urls import path

from replays.views import ReplayHistoryView

urlpatterns = [
    path('replays/<int:pk>/', ReplayHistoryView.as_view(), name='replay-history'),
]
