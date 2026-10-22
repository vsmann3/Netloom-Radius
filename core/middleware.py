from django.conf import settings


class TrustedHTTPSProxyMiddleware:
    """Recognize HTTPS only from explicitly configured, header-overwriting peers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (request.META.get("REMOTE_ADDR") in settings.CAF_CATALOG_PROXY_IPS
                and request.META.get("HTTP_X_FORWARDED_PROTO") == "https"):
            request.META["wsgi.url_scheme"] = "https"
        return self.get_response(request)
