from django.urls import path

from projects.views import ProjectCreateView, ProjectListView

urlpatterns = [
    path('projects/', ProjectListView.as_view(), name='project-list'),
    path('projects/create/', ProjectCreateView.as_view(), name='project-create'),
]
