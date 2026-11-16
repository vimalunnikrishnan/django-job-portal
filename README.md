# Zecpath – Django Job Portal

A Django-based job portal backend designed to connect job seekers and employers through job listings, applications, candidate profiles, and recruitment features.

## Features

- User registration and JWT authentication
- Role-based access control for candidates, employers, and administrators
- Candidate and employer profiles
- Job creation, listing, updating, and moderation
- Job applications and application status management
- Saved jobs and candidate ranking
- Resume upload and encrypted cloud storage integration
- Job matching and ATS scoring
- AI interview management and answer evaluation
- Interview scheduling and reminders
- Subscription and payment integration using Razorpay
- Background task processing using Celery
- API documentation using Swagger and ReDoc

## Technology Stack

- Python
- Django 5.2
- Django REST Framework
- Simple JWT
- SQLite (default local database)
- Celery
- Redis-compatible message broker
- AWS S3 and django-storages
- Cryptography
- Razorpay
- drf-spectacular
- Locust
- Git and GitHub

## Project Structure

```text
django-job-portal/
├── accounts/
├── billing/
├── config/
├── jobs/
├── docs/
├── manage.py
├── requirements.txt
├── requirements-linux.txt
└── schema.yml
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/vimalunnikrishnan/django-job-portal.git
cd django-job-portal
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

Windows:

```powershell
pip install -r requirements.txt
```

Linux:

```bash
pip install -r requirements-linux.txt
```

### 4. Configure environment variables

Create a local `.env` file in the project root. Do not commit this file.

Configure the values required by the features you enable, including:

```env
DJANGO_SECRET_KEY=replace-with-a-secure-local-secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

Additional integrations may require environment variables for AWS S3, AI services, and Razorpay. Use your own credentials and never publish secrets.

### 5. Apply database migrations

```bash
python manage.py migrate
```

### 6. Run the development server

```bash
python manage.py runserver
```

Open Swagger API documentation: http://127.0.0.1:8000/api/docs/

## API Documentation

When the development server is running:

| Documentation | Endpoint |
|---|---|
| Swagger UI | `/api/docs/` |
| ReDoc | `/api/redoc/` |
| OpenAPI Schema | `/api/schema/` |

### Main API Routes

| Module | Base endpoint |
|---|---|
| Accounts | `/api/` |
| Jobs | `/api/jobs/` |
| Billing | `/api/billing/` |

## Testing

Run Django system checks:

```bash
python manage.py check
```

Run the test suite:

```bash
python manage.py test
```

The project also includes Locust configuration for load-testing experiments.

## Security Notes

- Keep `.env` and all credentials private.
- Use a strong Django secret key.
- Configure production settings separately from local development.
- Keep resume encryption keys secure.
- Review AWS permissions and payment-provider credentials before deployment.

## Author

**Vimal U**

GitHub: https://github.com/vimalunnikrishnan

LinkedIn: https://www.linkedin.com/in/vimal-u-3a9405374

