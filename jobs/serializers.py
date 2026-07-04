try:
    import importlib
    rest_framework_views = importlib.import_module("rest_framework.views")
    rest_framework_response = importlib.import_module("rest_framework.response")
    _drf_serializers = importlib.import_module("rest_framework.serializers")
    APIView = rest_framework_views.APIView
    Response = rest_framework_response.Response
    DRF_AVAILABLE = True
except Exception:
    # Minimal fallbacks for environments without DRF (helps linters/tests)
    APIView = object
    Response = None
    _drf_serializers = None
    DRF_AVAILABLE = False

from .models import Job


# Provide a JobSerializer: prefer DRF's ModelSerializer, otherwise a simple fallback
if DRF_AVAILABLE:
    class JobSerializer(_drf_serializers.ModelSerializer):
        class Meta:
            model = Job
            fields = '__all__'
else:
    class JobSerializer:
        def __init__(self, instance, many=False):
            self.many = many
            self.instance = instance

        @property
        def data(self):
            def to_dict(obj):
                # naive serializer: include model fields if accessible
                try:
                    return {f: getattr(obj, f) for f in dir(obj) if not f.startswith('_') and not callable(getattr(obj, f))}
                except Exception:
                    return {}

            if self.many:
                return [to_dict(i) for i in self.instance]
            return to_dict(self.instance)


class JobListAPIView(APIView if DRF_AVAILABLE else object):
    def get(self, request=None):
        jobs = Job.objects.all()
        serializer = JobSerializer(jobs, many=True)
        if DRF_AVAILABLE:
            return Response(serializer.data)
        # Fallback: return plain data
        return serializer.data