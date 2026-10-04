from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions

from replays.models import Replay
from replays.serializers import ReplaySerializer


class ReplayHistoryView(generics.ListAPIView):
    serializer_class = ReplaySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        captured_request_id = self.kwargs.get('pk')
        return Replay.objects.filter(captured_request_id=captured_request_id).order_by('-created_at')
