from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):

    allowed_role = None
    message = "Permission denied."

    def has_permission(self, request, view):
        if self.allowed_role is None:
            return False

        return (
            request.user.is_authenticated
            and request.user.role == self.allowed_role
        )


class IsAdmin(RolePermission):
    allowed_role = "ADMIN"
    message = "Only Admin users can access this API."


class IsEmployer(RolePermission):
    allowed_role = "EMPLOYER"
    message = "Only Employer users can access this API."


class IsCandidate(RolePermission):
    allowed_role = "CANDIDATE"
    message = "Only Candidate users can access this API."