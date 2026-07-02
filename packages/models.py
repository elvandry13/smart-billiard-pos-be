from django.core.exceptions import ValidationError
from django.db import models

from users.models import Outlet


class Package(models.Model):
    class PackageType(models.TextChoices):
        PER_MINUTE = 'per_minute', 'Per Minute'
        FIXED_DURATION = 'fixed_duration', 'Fixed Duration'
        OPEN_LOSS = 'open_loss', 'Open Loss'
        HAPPY_HOUR = 'happy_hour', 'Happy Hour'

    class DayType(models.TextChoices):
        ALL = 'all', 'All Days'
        WEEKDAY = 'weekday', 'Weekday'
        WEEKEND = 'weekend', 'Weekend'
        SPECIFIC_DAY = 'specific_day', 'Specific Day'

    outlet = models.ForeignKey(Outlet, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=PackageType.choices)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    fixed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_minute = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    valid_day_type = models.CharField(
        max_length=20,
        choices=DayType.choices,
        default=DayType.ALL,
    )
    specific_date = models.DateField(null=True, blank=True)
    valid_start_time = models.TimeField(null=True, blank=True)
    valid_end_time = models.TimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['outlet', 'name']
        ordering = ['outlet', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_type_display()}) — {self.outlet.name}'

    def clean(self):
        errors = {}

        # --- Type-specific validation ---
        if self.type in (self.PackageType.FIXED_DURATION, self.PackageType.HAPPY_HOUR):
            if not self.duration_minutes:
                errors['duration_minutes'] = (
                    f'Duration is required for package type "{self.get_type_display()}".'
                )
            if not self.fixed_price:
                errors['fixed_price'] = (
                    f'Fixed price is required for package type "{self.get_type_display()}".'
                )

        if self.type == self.PackageType.PER_MINUTE:
            if not self.price_per_minute:
                errors['price_per_minute'] = (
                    'Price per minute is required for package type "Per Minute".'
                )

        if self.type == self.PackageType.OPEN_LOSS:
            if self.duration_minutes is not None:
                errors['duration_minutes'] = (
                    'Duration must be empty for package type "Open Loss".'
                )
            if self.fixed_price is not None:
                errors['fixed_price'] = (
                    'Fixed price must be empty for package type "Open Loss".'
                )

        # --- Numeric value validation ---
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            errors['duration_minutes'] = 'Duration must be greater than 0.'

        if self.fixed_price is not None and self.fixed_price <= 0:
            errors['fixed_price'] = 'Fixed price must be greater than 0.'

        if self.price_per_minute is not None and self.price_per_minute <= 0:
            errors['price_per_minute'] = 'Price per minute must be greater than 0.'

        # --- Day type + specific date validation ---
        if self.valid_day_type == self.DayType.SPECIFIC_DAY and not self.specific_date:
            errors['specific_date'] = 'Specific date is required when day type is "Specific Day".'
        elif self.valid_day_type != self.DayType.SPECIFIC_DAY and self.specific_date:
            errors['specific_date'] = (
                'Specific date should only be set when day type is "Specific Day".'
            )

        # --- Time range validation ---
        if self.valid_start_time and self.valid_end_time and self.valid_start_time >= self.valid_end_time:
            errors['valid_end_time'] = 'End time must be after start time.'

        if errors:
            raise ValidationError(errors)