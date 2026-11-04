"""
Configuracion base de Proyecto Heroes del Corazon
"""
import os
from datetime import timedelta
from pathlib import Path

import environ

# PATHS
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool,False),
    DJANGO_ALLOWED_HOSTS=(list,["localhost","127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list,[]),
    CSRF_TRUSTED_ORIGINS=(list,[]),
    EMAIL_USE_TLS=(bool,True),
)

# load .env
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# Core Django
# El valor por defecto es solo para dev; prod.py rechaza arrancar con el.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", default="insecure-default-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")


# APPS
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "axes",
]

LOCAL_APPS: list[str] = [
    "users",
    "questions",
]

AUTH_USER_MODEL = "users.User"

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# El orden importa: CorsMiddleware va primero y AxesMiddleware al final.
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',
    'axes.middleware.AxesMiddleware',
]

# Axes debe ir antes de ModelBackend para poder bloquear los intentos fallidos.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]


ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# DATABASE POSTGRES
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", default="heroesdelcorazon"),
        "USER": os.getenv("POSTGRES_USER", default="heroes_user"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", default="heroes_pass"),
        "HOST": os.getenv("POSTGRES_HOST", default="localhost"),
        "PORT": os.getenv("POSTGRES_PORT", default="5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# AUTHENTICATION PASSWORD VALIDATORS
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# i18n / TZ
LANGUAGE_CODE = 'es'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# STATIC / MEDIA
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# REST_FRAMEWORK CONFIG
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "common.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # El scope "login" lo activan explicitamente las vistas de auth con ScopedRateThrottle.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("THROTTLE_RATE_ANON", default="200/min"),
        "user": os.getenv("THROTTLE_RATE_USER", default="1000/min"),
        "login": os.getenv("THROTTLE_RATE_LOGIN", default="500/min"),
    },
}

# SIMPLE JSON WEB TOKEN CONFIG
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Rotacion + blacklist: cada refresh invalida el anterior (requiere la app token_blacklist).
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# COOKIES AUTHENTICACION CONFIG 
# El frontend web recibe el access/refresh token como cookies httpOnly (no
# localStorage) para que un XSS no pueda robarlos ni suplantar al usuario.
# Los clientes que usan el header Authorization (app móvil, Postman, etc.)
# no se ven afectados: CookieJWTAuthentication sigue aceptando ese header y
# solo cae a la cookie cuando no viene header.
AUTH_COOKIE_ACCESS_NAME = "access_token"
AUTH_COOKIE_REFRESH_NAME = "refresh_token"
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", default="Lax")
# En prod.py se fuerza a True (HTTPS). En dev queda en False por defecto para
# no requerir HTTPS local; puede activarse por env si se prueba con HTTPS.
AUTH_COOKIE_SECURE = env.bool("AUTH_COOKIE_SECURE", default=False)

# La cookie `csrftoken` (usada por enforce_csrf en common/authentication.py)
# tiene que poder viajar en el mismo tipo de request que access_token/
# refresh_token — si un despliegue cambia AUTH_COOKIE_SAMESITE a "None" para
# un escenario realmente cross-site pero esta cookie se queda en "Lax", el
# navegador manda las cookies de auth pero no la de CSRF, y todo mutating
# request autenticado por cookie empieza a fallar con "CSRF cookie not set".
CSRF_COOKIE_SAMESITE = AUTH_COOKIE_SAMESITE
SESSION_COOKIE_SAMESITE = AUTH_COOKIE_SAMESITE

SPECTACULAR_SETTINGS = {
    "TITLE": "Heroes del Corazon API",
    "DESCRIPTION": "API de evaluación de desempeño para la clínica",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Sirve los assets de Swagger/Redoc localmente (sin CDN externo) para
    # poder mantener una CSP estricta (default-src 'self').
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}


# AXES CONFIG
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = env.int("AXES_COOLOFF_TIME_HOURS", default=1)
# Lockout por la COMBINACIÓN (username + ip_address), no por username solo:
# con ["username"] cualquier atacante no autenticado que conozca un username
# válido puede bloquear esa cuenta 1h enviando 5 intentos fallidos desde
# cualquier IP (DoS dirigido). Con [["username", "ip_address"]] el bloqueo
# solo aplica a ese par específico, así que un atacante no puede tumbar la
# cuenta de otra persona sin operar desde su misma IP.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True


# CONTENT SECURITY CONFIG

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:"],
        "style-src": ["'self'"],
        "script-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "object-src": ["'none'"],
    }
}

#  CORS / CSRF CONFIG
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS") or env("CORS_ALLOWED_ORIGINS")
# Credenciales (cookies httpOnly) exigen un origen concreto, nunca '*'.
# En prod nginx unifica origen y esto no se usa; en dev Vite puede proxear
# /api o hablar directo a :8000 (login desde localhost:5173).
CORS_ALLOW_CREDENTIALS = True

# FRONTEND 
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", default="http://127.0.0.1:5173")


# Email Config
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env("EMAIL_USE_TLS")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    default="Heroes del Corazon <noreply@heroescorazon.local>",
)


# Logging (a stdout, apto para contenedores/Docker)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}


# Sentry (captura de errores/monitoreo) — solo se activa si hay DSN
SENTRY_DSN = os.getenv("SENTRY_DSN", default="")
if SENTRY_DSN:
    import logging

    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENVIRONMENT", default="production"),
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=None, event_level=logging.ERROR),
        ],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        send_default_pii=False,
    )