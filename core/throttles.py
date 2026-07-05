from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Rate limiting untuk auth endpoints berdasarkan IP address.

    Scope: `auth` (5 requests/menit).
    Menggunakan ident IP request, tidak peduli apakah user sudah terautentikasi atau belum.
    """

    scope = 'auth'

    def get_cache_key(self, request, view):
        """Gunakan IP-based caching key (sama seperti AnonRateThrottle default)."""
        return self.get_ident(request)