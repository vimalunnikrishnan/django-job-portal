from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, EmployerProfile, CandidateProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == "EMPLOYER":
            EmployerProfile.objects.create(
                user=instance,
                company_name="New Company"
            )

        elif instance.role == "CANDIDATE":
            CandidateProfile.objects.create(
                user=instance,
                skills="",
                experience=0
            )