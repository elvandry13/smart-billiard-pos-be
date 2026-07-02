from rest_framework import serializers

from packages.models import Package


class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = [
            'id', 'outlet', 'name', 'type',
            'duration_minutes', 'fixed_price', 'price_per_minute',
            'valid_day_type', 'specific_date',
            'valid_start_time', 'valid_end_time',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        # Resolve values from data or existing instance
        instance = self.instance
        pkg_type = data.get('type', getattr(instance, 'type', None) if instance else None)
        duration = data.get('duration_minutes',
                            getattr(instance, 'duration_minutes', None) if instance else None)
        fixed_price = data.get('fixed_price',
                               getattr(instance, 'fixed_price', None) if instance else None)
        price_per_min = data.get('price_per_minute',
                                 getattr(instance, 'price_per_minute', None) if instance else None)
        valid_day_type = data.get('valid_day_type',
                                  getattr(instance, 'valid_day_type', None) if instance else None)
        specific_date = data.get('specific_date',
                                 getattr(instance, 'specific_date', None) if instance else None)
        start_time = data.get('valid_start_time',
                              getattr(instance, 'valid_start_time', None) if instance else None)
        end_time = data.get('valid_end_time',
                            getattr(instance, 'valid_end_time', None) if instance else None)

        errors = {}

        # --- Type-specific validation ---
        if pkg_type in (Package.PackageType.FIXED_DURATION, Package.PackageType.HAPPY_HOUR):
            if not duration:
                errors['duration_minutes'] = (
                    f'Duration is required for package type "{pkg_type}".'
                )
            if not fixed_price:
                errors['fixed_price'] = (
                    f'Fixed price is required for package type "{pkg_type}".'
                )

        if pkg_type == Package.PackageType.PER_MINUTE:
            if not price_per_min:
                errors['price_per_minute'] = (
                    'Price per minute is required for package type "per_minute".'
                )

        if pkg_type == Package.PackageType.OPEN_LOSS:
            if duration is not None:
                errors['duration_minutes'] = (
                    'Duration must be empty for package type "open_loss".'
                )
            if fixed_price is not None:
                errors['fixed_price'] = (
                    'Fixed price must be empty for package type "open_loss".'
                )

        # --- Numeric value validation ---
        if duration is not None and duration <= 0:
            errors['duration_minutes'] = 'Duration must be greater than 0.'

        if fixed_price is not None and fixed_price <= 0:
            errors['fixed_price'] = 'Fixed price must be greater than 0.'

        if price_per_min is not None and price_per_min <= 0:
            errors['price_per_minute'] = 'Price per minute must be greater than 0.'

        # --- Day type + specific date validation ---
        if valid_day_type == Package.DayType.SPECIFIC_DAY and not specific_date:
            errors['specific_date'] = 'Specific date is required when day type is "specific_day".'
        elif valid_day_type and valid_day_type != Package.DayType.SPECIFIC_DAY and specific_date:
            errors['specific_date'] = (
                'Specific date should only be set when day type is "specific_day".'
            )

        # --- Time range validation ---
        if start_time and end_time and start_time >= end_time:
            errors['valid_end_time'] = 'End time must be after start time.'

        if errors:
            raise serializers.ValidationError(errors)

        return data