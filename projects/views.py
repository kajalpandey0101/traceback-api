from rest_framework import generics, permissions

from projects.models import Project
from projects.serializers import ProjectCreateSerializer, ProjectSerializer


class ProjectCreateView(generics.CreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectCreateSerializer
    permission_classes = [permissions.AllowAny]


class ProjectListView(generics.ListAPIView):
    queryset = Project.objects.order_by('-created_at')
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
