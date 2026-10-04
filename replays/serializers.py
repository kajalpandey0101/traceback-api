from rest_framework import serializers

from replays.models import Replay


class ReplaySerializer(serializers.ModelSerializer):
    original_status = serializers.SerializerMethodField()
    original_latency_ms = serializers.SerializerMethodField()

    class Meta:
        model = Replay
        fields = [
            'id', 'captured_request', 'status', 'started_at', 'completed_at',
            'replay_status_code', 'replay_response_body', 'replay_latency_ms',
            'error_message', 'idempotency_key', 'created_at', 'original_status', 'original_latency_ms'
        ]

    def get_original_status(self, obj):
        return obj.captured_request.response_status

    def get_original_latency_ms(self, obj):
        return obj.captured_request.latency_ms
