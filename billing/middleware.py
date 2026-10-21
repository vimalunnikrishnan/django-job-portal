from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied



class PremiumAccessMiddleware:
    """
    Django middleware placeholder for premium access routing.

    Premium authorization is enforced by DRF permissions and
    feature-specific view checks, after authentication.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
