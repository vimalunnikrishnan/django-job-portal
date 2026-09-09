from rest_framework import serializers

from .models import (
    User,
    EmployerProfile,
    CandidateProfile,
)

from jobs.models import Job


class SignupSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True)

    class Meta:

        model = User

        fields = [
            "email",
            "username",
            "password",
            "phone",
            "role",
        ]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class EmployerProfileSerializer(serializers.ModelSerializer):

    class Meta:

        model = EmployerProfile

        fields = "__all__"

        read_only_fields = [
            "user",
            "is_company_verified",
            "is_deleted",
        ]


class CandidateProfileSerializer(serializers.ModelSerializer):

    class Meta:

        model = CandidateProfile

        fields = "__all__"

        read_only_fields = [
            "user",
            "is_deleted",
        ]


class ResumeUploadSerializer(serializers.ModelSerializer):

    class Meta:

        model = CandidateProfile

        fields = [
            "resume",
        ]

    def validate_resume(self, value):
        allowed_extensions = [
            ".pdf",
            ".docx",
        ]

        filename = value.name.lower()

        if not any(
            filename.endswith(ext)
            for ext in allowed_extensions
        ):
            raise serializers.ValidationError(
                "Only PDF and DOCX files are allowed."
            )

        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                "Maximum file size is 5 MB."
            )

        return value


class UserListSerializer(serializers.ModelSerializer):

    class Meta:

        model = User

        fields = (
            "id",
            "email",
            "username",
            "phone",
            "role",
            "is_verified",
            "created_at",
        )

