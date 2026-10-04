from rest_framework import serializers

from projects.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name', 'target_base_url', 'created_at']


class ProjectCreateSerializer(serializers.ModelSerializer):
    api_key = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'target_base_url', 'api_key', 'created_at']

    def get_api_key(self, obj):
        return obj.api_key

    def create(self, validated_data):
        project = Project.objects.create(**validated_data)
        project.set_api_key()
        project.save(update_fields=['api_key', 'api_key_hash'])
        return project
