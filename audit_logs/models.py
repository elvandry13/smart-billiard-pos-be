from django.db import models


class AuditLog(models.Model):
    """Mencatat setiap aksi sensitif di sistem."""

    class Action:
        """Dokumentasi action yang umum digunakan (tidak membatasi — field bebas string)."""
        CREATE = 'create'
        UPDATE = 'update'
        DELETE = 'delete'
        CANCEL_SESSION = 'cancel_session'
        OPEN_SHIFT = 'open_shift'
        CLOSE_SHIFT = 'close_shift'
        OPEN_SESSION = 'open_session'
        END_SESSION = 'end_session'
        TRANSFER_TABLE = 'transfer_table'
        LOGIN = 'login'
        LOGOUT = 'logout'
        UPDATE_PROFILE = 'update_profile'
        CHANGE_PASSWORD = 'change_password'

    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
    )
    outlet = models.ForeignKey(
        'users.Outlet',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64)
    object_id = models.IntegerField(null=True, blank=True)
    changes = models.JSONField(default=dict)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['outlet', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['object_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.action} | {self.object_type}#{self.object_id} by {self.user}'