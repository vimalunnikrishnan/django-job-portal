import django_filters

from .models import Job


class JobFilter(django_filters.FilterSet):

    min_salary = django_filters.NumberFilter(
        field_name="min_salary",
        lookup_expr="gte",
    )

    max_salary = django_filters.NumberFilter(
        field_name="max_salary",
        lookup_expr="lte",
    )

    experience = django_filters.NumberFilter()

    location = django_filters.CharFilter(
        lookup_expr="icontains",
    )

    skills = django_filters.CharFilter(
        lookup_expr="icontains",
    )

    job_type = django_filters.CharFilter()

    class Meta:

        model = Job

        fields = [
            "job_type",
            "location",
            "skills",
            "experience",
            "min_salary",
            "max_salary",
        ]