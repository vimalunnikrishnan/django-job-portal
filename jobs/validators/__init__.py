from django.core.exceptions import ValidationError

def validate_salary(value):
    if value < 0:
        raise ValidationError("Salary cannot be negative.")