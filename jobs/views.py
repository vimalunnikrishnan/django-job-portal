from rest_framework.views import APIView  # type: ignore[import]
from rest_framework.response import Response  # type: ignore[import]
from rest_framework import status  # type: ignore[import]
from .models import Job
from .serializers import JobSerializer


class JobListAPIView(APIView):

    # GET - List all jobs
    def get(self, request):
        jobs = Job.objects.all()
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data)

    # POST - Create a new job
    def post(self, request):
        serializer = JobSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserTestAPIView(APIView):
    def get(self, request):
        data = {
            "message": "Welcome to Django REST Framework!",
            "name": "Vimal",
            "course": "BCA",
            "status": "API is working successfully"
        }
        return Response(data)