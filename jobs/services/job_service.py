from jobs.models import Job

def get_all_jobs():
    return Job.objects.all()