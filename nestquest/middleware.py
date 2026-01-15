"""
Simple middleware to log all HTTP requests and track visitors
"""
import logging
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger('django.server')

class AccessLogMiddleware:
    """
    Logs all HTTP requests with IP, path, and timestamp
    Also saves to database for easy tracking
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get client IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
        # Get user agent (browser/device info)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')[:200]
        referer = request.META.get('HTTP_REFERER', '')[:500]
        
        # Check if this is a login action
        is_login = (
            request.path == '/accounts/login/' and 
            request.method == 'POST'
        )
        
        # Log the access
        user_str = request.user.username if request.user.is_authenticated else 'Anonymous'
        logger.info(
            f"👤 {user_str:15s} | "
            f"IP: {ip:15s} | "
            f"📍 {request.method:4s} {request.path:40s} | "
            f"🕐 {timezone.now().strftime('%H:%M:%S')}"
        )
        
        # Save to database (async to avoid slowing down requests)
        try:
            # Only save important pages (not static files, etc.)
            if not any(request.path.startswith(prefix) for prefix in ['/static/', '/media/', '/favicon.ico']):
                from properties.models import Visitor
                Visitor.objects.create(
                    ip_address=ip,
                    user=request.user if request.user.is_authenticated else None,
                    path=request.path[:500],
                    method=request.method,
                    user_agent=user_agent,
                    referer=referer,
                    is_login=is_login
                )
        except Exception as e:
            # Don't break the request if tracking fails
            logger.debug(f"Failed to save visitor: {e}")
        
        response = self.get_response(request)
        return response
