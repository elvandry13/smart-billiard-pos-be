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

    @classmethod
    def validate_invariants(cls, pkg_type, duration_minutes, fixed_price,
                            price_per_minute, valid_day_type, specific_date,
                            valid_start_time, valid_end_time):
        """Return a dict of field-level errors, or an empty dict.

        Single source of truth for Package business-rule validation.
        Called by both model-level clean() and serializer validate().
        """
        errors = {}

        # --- Type-specific validation ---
        if pkg_type in (cls.PackageType.FIXED_DURATION, cls.PackageType.HAPPY_HOUR):
            if not duration_minutes:
                errors['duration_minutes'] = (
                    f'Duration is required for package type "{pkg_type}".'
                )
            if not fixed_price:
                errors['fixed_price'] = (
                    f'Fixed price is required for package type "{pkg_type}".'
                )

        if pkg_type == cls.PackageType.PER_MINUTE:
            if not price_per_minute:
                errors['price_per_minute'] = (
                    'Price per minute is required for package type "per_minute".'
                )

        if pkg_type == cls.PackageType.OPEN_LOSS:
            if duration_minutes is not None:
                errors['duration_minutes'] = (
                    'Duration must be empty for package type "open_loss".'
                )
            if fixed_price is not None:
                errors['fixed_price'] = (
                    'Fixed price must be empty for package type "open_loss".'
                )

        # --- Numeric value validation ---
        if duration_minutes is not None and duration_minutes <= 0:
            errors['duration_minutes'] = 'Duration must be greater than 0.'

        if fixed_price is not None and fixed_price <= 0:
            errors['fixed_price'] = 'Fixed price must be greater than 0.'

        if price_per_minute is not None and price_per_minute <= 0:
            errors['price_per_minute'] = 'Price per minute must be greater than 0.'

        # --- Day type + specific date validation ---
        if valid_day_type == cls.DayType.SPECIFIC_DAY and not specific_date:
            errors['specific_date'] = 'Specific date is required when day type is "specific_day".'
        elif valid_day_type and valid_day_type != cls.DayType.SPECIFIC_DAY and specific_date:
            errors['specific_date'] = (
                'Specific date should only be set when day type is "specific_day".'
            )

        # --- Time range validation ---
        if valid_start_time and valid_end_time and valid_start_time >= valid_end_time:
            errors['valid_end_time'] = 'End time must be after start time.'

        return errors

    def clean(self):
        errors = self.validate_invariants(
            pkg_type=self.type,
            duration_minutes=self.duration_minutes,
            fixed_price=self.fixed_price,
            price_per_minute=self.price_per_minute,
            valid_day_type=self.valid_day_type,
            specific_date=self.specific_date,
            valid_start_time=self.valid_start_time,
            valid_end_time=self.valid_end_time,
        )
        if errors:
            raise ValidationError(errors)
