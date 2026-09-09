from rest_framework.views import exception_handler
from rest_framework import status


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if response is not None:

        response.data = {
            "success": False,
            "status_code": response.status_code,
            "errors": response.data,
        }

    return response