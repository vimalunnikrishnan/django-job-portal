
from rest_framework.throttling import ScopedRateThrottle


class PremiumRecruiterRateThrottle(ScopedRateThrottle):
    """
    Apply a dedicated rate limit to premium recruiter APIs.
    """

    scope = "premium_recruiter"