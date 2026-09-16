from rest_framework import serializers

from .models import Job, Application, SavedJob, ATSScore


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


class ATSScoreSerializer(serializers.ModelSerializer):

    class Meta:
        model = ATSScore
        fields = [
            "id",
            "candidate",
            "job",
            "skill_score",
            "experience_score",
            "education_score",
            "match_percentage",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class RankedCandidateSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    candidate_id = serializers.IntegerField()
    candidate_email = serializers.EmailField()
    application_id = serializers.IntegerField()
    application_status = serializers.CharField()
    skill_score = serializers.FloatField()
    experience_score = serializers.FloatField()
    education_score = serializers.FloatField()
    match_percentage = serializers.FloatField()


class RankedCandidateSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    candidate_id = serializers.IntegerField()
    candidate_email = serializers.EmailField()
    application_id = serializers.IntegerField()
    application_status = serializers.CharField()
    skill_score = serializers.FloatField()
    experience_score = serializers.FloatField()
    education_score = serializers.FloatField()
    match_percentage = serializers.FloatField()