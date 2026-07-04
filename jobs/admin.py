from django.contrib import admin
from .models import (
    User,
    Employer,
    Candidate,
    Job,
    Application,
)

admin.site.register(User)
admin.site.register(Employer)
admin.site.register(Candidate)
admin.site.register(Job)
admin.site.register(Application)