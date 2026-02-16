"""
Audit SQL query counts for API endpoints.
Uses Django's CaptureQueriesContext to count queries per request.

Usage:
  python manage.py audit_query_counts
  python manage.py audit_query_counts --auth   # use staff user token for /api/inventory/ (needs existing admin)
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.test import Client
from django.test.utils import CaptureQueriesContext, override_settings
from django.db import connection


class Command(BaseCommand):
    help = 'Count SQL queries per API request and print a summary'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auth',
            action='store_true',
            help='Authenticate as first staff user for /api/inventory/ (requires existing Admin with token)',
        )

    def handle(self, *args, **options):
        use_auth = options['auth']
        client = Client()

        # Optional: get token for inventory API (many endpoints return 401 without auth)
        if use_auth:
            from rest_framework.authtoken.models import Token
            from inventory.models import Admin
            admin = Admin.objects.filter(user__is_staff=True).select_related('user').first()
            if admin and hasattr(admin.user, 'auth_token'):
                token = admin.user.auth_token.key
                client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
                self.stdout.write(self.style.NOTICE(f'Using token for user: {admin.user.username}'))
            else:
                self.stdout.write(self.style.WARNING('--auth: no staff user with token found; inventory endpoints may 401'))

        # Resolve a valid PK for detail routes (avoid 404 so we measure real view queries)
        product_id = None
        try:
            from inventory.models import Product
            p = Product.objects.filter(is_published=True).values_list('id', flat=True).first()
            if p:
                product_id = p
        except Exception:
            pass

        # Paths to audit: (method, path)
        paths = [
            ('GET', '/'),
            ('GET', '/api/v1/public/products/'),
            ('GET', '/api/v1/public/products/?page_size=5'),
            ('GET', '/api/inventory/products/'),
            ('GET', '/api/inventory/units/'),
            ('GET', '/api/inventory/notifications/unread_count/'),
            ('GET', '/api/inventory/brands/'),
            ('GET', '/api/inventory/colors/'),
        ]
        if product_id:
            paths.extend([
                ('GET', f'/api/v1/public/products/{product_id}/'),
                ('GET', f'/api/v1/public/products/{product_id}/units/'),
                ('GET', f'/api/inventory/products/{product_id}/'),
                ('GET', f'/api/inventory/products/{product_id}/stock-summary/'),
            ])

        self.stdout.write(self.style.SUCCESS('=' * 72))
        self.stdout.write(self.style.SUCCESS('API query count audit (SQL queries per request)'))
        self.stdout.write(self.style.SUCCESS('=' * 72))

        # Allow test client host and localhost so requests reach views (no 400/301 from host check)
        allowed = list(settings.ALLOWED_HOSTS) if settings.ALLOWED_HOSTS else []
        for h in ('testserver', 'localhost'):
            if h not in allowed:
                allowed.append(h)

        extra_headers = {'HTTP_HOST': 'localhost'}

        results = []
        with override_settings(ALLOWED_HOSTS=allowed):
            for method, path in paths:
                with CaptureQueriesContext(connection) as ctx:
                    if method == 'GET':
                        response = client.get(path, **extra_headers)
                    else:
                        response = client.post(path, {}, content_type='application/json', **extra_headers)
                    # Read count inside context; use connection.queries as fallback (ctx.captured_queries can be empty in some setups)
                    num_queries = len(getattr(ctx, 'captured_queries', None) or connection.queries)
                status = response.status_code
                results.append((path, status, num_queries))
                style = self.style.ERROR if num_queries > 50 else (self.style.WARNING if num_queries > 20 else self.style.SUCCESS)
                self.stdout.write(style(f'  {status:3}  {num_queries:3} queries  {method} {path}'))

        self.stdout.write('')
        total = sum(r[2] for r in results)
        self.stdout.write(self.style.SUCCESS(f'Total requests: {len(results)}  |  Total queries: {total}'))
        self.stdout.write(self.style.SUCCESS('=' * 72))
