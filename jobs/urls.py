from django.urls import path
from .views import JobListAPIView, UserTestAPIView

urlpatterns = [
    path('jobs/', JobListAPIView.as_view(), name='job-list'),
    path('user-test/', UserTestAPIView.as_view(), name='user-test'),
]