from django.urls import path

from capture.views import CapturedRequestDetailView, CapturedRequestListView, ReplayHistoryView, ReplayRequestView

urlpatterns = [
    path('requests/', CapturedRequestListView.as_view(), name='request-list'),
    path('requests/<int:pk>/', CapturedRequestDetailView.as_view(), name='request-detail'),
    path('requests/<int:pk>/replay/', ReplayRequestView.as_view(), name='request-replay'),
    path('requests/<int:pk>/replays/', ReplayHistoryView.as_view(), name='request-replays'),
]
