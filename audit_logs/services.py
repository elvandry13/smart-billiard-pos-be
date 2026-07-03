from django.core.exceptions import ObjectDoesNotExist

from users.models import User

from .models import AuditLog


class AuditService:
    """Service layer untuk mencatat entry AuditLog."""

    @staticmethod
    def log(
        *,
        user_id: int,
        outlet_id: int | None,
        action: str,
        object_type: str,
        object_id: int | None = None,
        changes: dict | None = None,
        notes: str = '',
    ) -> AuditLog:
        """
        Buat satu entry AuditLog.

        Args:
            user_id: ID user yang melakukan aksi.
            outlet_id: ID outlet tempat aksi terjadi (nullable).
            action: Tipe aksi (dari AuditLog.Action).
            object_type: Nama model yang diubah (e.g. 'PricingRule').
            object_id: ID objek yang diubah (nullable).
            changes: Dict perubahan — format bebas. Untuk update: {"field": {"old": ..., "new": ...}}.
                      Untuk create/delete/action: {"field": value} atau {} jika tidak ada perubahan.
            notes: Catatan tambahan (e.g. cancel reason).

        Returns:
            AuditLog yang baru dibuat.
        """
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            user = None

        return AuditLog.objects.create(
            user=user,
            outlet_id=outlet_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            changes=changes or {},
            notes=notes,
        )