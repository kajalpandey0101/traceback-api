from rest_framework import serializers

from capture.models import CapturedRequest


class CapturedRequestSummarySerializer(serializers.ModelSerializer):
    status = serializers.IntegerField(source='response_status', read_only=True)

    class Meta:
        model = CapturedRequest
        fields = ['id', 'request_id', 'method', 'path', 'status', 'latency_ms', 'created_at']


class CapturedRequestDetailSerializer(serializers.ModelSerializer):
    project = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = CapturedRequest
        fields = [
            'id', 'request_id', 'project', 'method', 'path', 'query_params', 'request_headers',
            'request_body', 'response_status', 'response_headers', 'response_body', 'latency_ms',
            'error_message', 'body_truncated', 'created_at', 'expires_at'
        ]
