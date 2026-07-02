from django.core.exceptions import ValidationError
from django.db import models
from users.models import Outlet


class TableType(models.Model):
    """Kategori/tipe meja billiard dalam satu outlet."""
    outlet = models.ForeignKey(
        Outlet, on_delete=models.CASCADE, related_name='table_types',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['outlet', 'name']
        ordering = ['outlet', 'name']

    def __str__(self):
        return f"{self.outlet.name} — {self.name}"


class Table(models.Model):
    """Meja billiard individual di dalam outlet."""

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        OCCUPIED = 'occupied', 'Occupied'
        MAINTENANCE = 'maintenance', 'Maintenance'
        RESERVED = 'reserved', 'Reserved'

    outlet = models.ForeignKey(
        Outlet, on_delete=models.CASCADE, related_name='tables',
    )
    name = models.CharField(max_length=100)
    table_type = models.ForeignKey(
        TableType, on_delete=models.PROTECT, related_name='tables',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['outlet', 'name']
        ordering = ['outlet', 'name']

    def __str__(self):
        return f"{self.outlet.name} — {self.name} ({self.table_type.name})"

    def clean(self):
        super().clean()
        if self.table_type_id and self.outlet_id:
            if self.table_type.outlet_id != self.outlet_id:
                raise ValidationError({
                    'table_type': 'Table type must belong to the same outlet as the table.',
                })


class PricingRule(models.Model):
    """Aturan dynamic pricing per outlet, tabel type, dan waktu."""

    class DayType(models.TextChoices):
        WEEKDAY = 'weekday', 'Weekday'
        WEEKEND = 'weekend', 'Weekend'
        SPECIFIC_DAY = 'specific_day', 'Specific Day'

    outlet = models.ForeignKey(
        Outlet, on_delete=models.CASCADE, related_name='pricing_rules',
    )
    table_type = models.ForeignKey(
        TableType, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='pricing_rules',
        help_text='Leave blank to apply to all table types.',
    )
    name = models.CharField(max_length=100)
    day_type = models.CharField(
        max_length=20,
        choices=DayType.choices,
        default=DayType.WEEKDAY,
    )
    specific_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    price_per_minute = models.DecimalField(max_digits=10, decimal_places=2)
    priority = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['outlet', '-priority', 'start_time']

    def __str__(self):
        return f"{self.outlet.name} — {self.name} (priority={self.priority})"

    def clean(self):
        super().clean()
        errors = {}

        # specific_date required when day_type is specific_day
        if self.day_type == self.DayType.SPECIFIC_DAY and not self.specific_date:
            errors['specific_date'] = 'Specific date is required when day type is "specific_day".'
        elif self.day_type != self.DayType.SPECIFIC_DAY and self.specific_date:
            errors['specific_date'] = 'Specific date should only be set when day type is "specific_day".'

        # price_per_minute > 0
        if self.price_per_minute is not None and self.price_per_minute <= 0:
            errors['price_per_minute'] = 'Price per minute must be greater than 0.'

        # table_type must belong to same outlet
        if self.table_type_id and self.outlet_id:
            if self.table_type.outlet_id != self.outlet_id:
                errors['table_type'] = 'Table type must belong to the same outlet.'

        if errors:
            raise ValidationError(errors)


class AdditionalFee(models.Model):
    """Biaya tambahan seperti service fee atau tax."""

    class FeeType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage'
        FIXED = 'fixed', 'Fixed'

    outlet = models.ForeignKey(
        Outlet, on_delete=models.CASCADE, related_name='additional_fees',
    )
    name = models.CharField(max_length=100)
    type = models.CharField(
        max_length=20,
        choices=FeeType.choices,
    )
    value = models.DecimalField(max_digits=10, decimal_places=2)
    apply_to = models.CharField(
        max_length=50, default='session_subtotal',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['outlet', 'name']

    def __str__(self):
        return f"{self.outlet.name} — {self.name} ({self.get_type_display()})"

    def clean(self):
        super().clean()
        if self.value is not None and self.value <= 0:
            raise ValidationError({'value': 'Value must be greater than 0.'})