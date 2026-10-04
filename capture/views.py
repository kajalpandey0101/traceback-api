from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import filters, generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from capture.models import CapturedRequest
from capture.serializers import CapturedRequestDetailSerializer, CapturedRequestSummarySerializer
from replays.models import Replay
from replays.serializers import ReplaySerializer


class CapturedRequestListView(generics.ListAPIView):
    queryset = CapturedRequest.objects.select_related('project').order_by('-created_at')
    serializer_class = CapturedRequestSummarySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'response_status', 'latency_ms']

    def get_queryset(self):
        qs = super().get_queryset()
        status_code = self.request.query_params.get('status')
        method = self.request.query_params.get('method')
        path = self.request.query_params.get('path')
        request_id = self.request.query_params.get('request_id')
        if status_code:
            qs = qs.filter(response_status=status_code)
        if method:
            qs = qs.filter(method__iexact=method)
        if path:
            qs = qs.filter(path__icontains=path)
        if request_id:
            qs = qs.filter(request_id__icontains=request_id)
        return qs


class CapturedRequestDetailView(generics.RetrieveAPIView):
    queryset = CapturedRequest.objects.select_related('project')
    serializer_class = CapturedRequestDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'pk'


class ReplayRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        captured = get_object_or_404(CapturedRequest, pk=pk)
        method = captured.method.upper()
        confirm = request.data.get('confirm', False) in (True, 'true', 'True', '1')
        if method in {'POST', 'PUT', 'PATCH'} and not confirm:
            return Response({'error': 'replay_confirmation_required', 'message': 'Confirmation is required for this replay type.'}, status=status.HTTP_400_BAD_REQUEST)
        if method == 'DELETE':
            return Response({'error': 'replay_blocked', 'message': 'DELETE replays are blocked by default.'}, status=status.HTTP_400_BAD_REQUEST)

        idempotency_key = request.data.get('idempotency_key') or request.headers.get('Idempotency-Key')
        if not idempotency_key:
            idempotency_key = f'replay_{captured.id}_{captured.request_id}'

        if Replay.objects.filter(captured_request=captured, idempotency_key=idempotency_key).exists():
            return Response({'error': 'duplicate_replay', 'message': 'This replay has already been processed.'}, status=status.HTTP_409_CONFLICT)

        replay = Replay.objects.create(
            captured_request=captured,
            status='QUEUED',
            idempotency_key=idempotency_key,
        )
        try:
            response = replay.execute()
            serializer = ReplaySerializer(replay)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            replay.status = 'FAILED'
            replay.error_message = str(exc)
            replay.completed_at = replay.started_at
            replay.save(update_fields=['status', 'error_message', 'completed_at'])
            return Response({'error': 'replay_failed', 'message': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReplayHistoryView(generics.ListAPIView):
    serializer_class = ReplaySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        captured_id = self.kwargs.get('pk')
        return Replay.objects.filter(captured_request_id=captured_id).order_by('-created_at')
