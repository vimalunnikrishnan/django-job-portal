from rest_framework import serializers

from .models import Job, Application, SavedJob


class JobSerializer(serializers.ModelSerializer):

    class Meta:

        model = Job

        fields = "__all__"

        read_only_fields = [
            "employer",
            "created_at",
            "updated_at",
        ]


class ApplicationSerializer(serializers.ModelSerializer):

    class Meta:

        model = Application

        fields = "__all__"

        read_only_fields = (
            "candidate",
            "status",
            "applied_at",
            "updated_at",
        )


class ApplicationStatusSerializer(serializers.ModelSerializer):

    class Meta:

        model = Application

        fields = [
            "status",
        ]


class SavedJobSerializer(serializers.ModelSerializer):

    class Meta:
        model = SavedJob
        fields = "__all__"

        read_only_fields = (
            "candidate",
            "saved_at",
        )