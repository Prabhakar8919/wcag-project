from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponseServerError
from django.db.utils import DatabaseError, OperationalError

class SaaSAuthRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            # Paths that are exempt from authentication enforcement
            exempt_paths = [
                '/login/',
                '/signup/',
                '/admin/',
                '/verify-otp/',
            ]

            # Add reverse URLs safely
            try:
                exempt_paths.append(reverse('login'))
                exempt_paths.append(reverse('signup'))
                exempt_paths.append(reverse('verify_otp'))
                exempt_paths.append(reverse('resend_otp'))
            except Exception:
                pass

            # Check if request has a path that starts with any of the exempt paths
            path = request.path
            is_exempt = any(path == p or path.startswith(p) for p in exempt_paths)
            is_static = path.startswith(settings.STATIC_URL)

            # Allow access to exempt or static paths
            if is_exempt or is_static:
                return self.get_response(request)

            # Enforce authentication
            if not request.user.is_authenticated:
                return redirect('login')

            # Enforce email verification for authenticated users
            if hasattr(request.user, 'profile') and not request.user.profile.is_email_verified:
                # Set the pre-verified user email in session
                request.session['pre_verified_user_email'] = request.user.email
                # Log them out so they can't access authenticated endpoints
                from django.contrib.auth import logout as auth_logout
                auth_logout(request)
                return redirect('verify_otp')

            return self.get_response(request)

        except (OperationalError, DatabaseError) as db_error:
            return HttpResponseServerError(
                '<h2>Database connection failure</h2>'
                '<p>Unable to connect to the database. Please verify your PostgreSQL credentials in the environment variables or your DATABASE_URL setting.</p>'
                '<p>Error details: {}</p>'.format(db_error)
            )

