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
        instance = self.instance
        errors = Package.validate_invariants(
            pkg_type=data.get('type', getattr(instance, 'type', None) if instance else None),
            duration_minutes=data.get('duration_minutes',
                                      getattr(instance, 'duration_minutes', None) if instance else None),
            fixed_price=data.get('fixed_price',
                                 getattr(instance, 'fixed_price', None) if instance else None),
            price_per_minute=data.get('price_per_minute',
                                      getattr(instance, 'price_per_minute', None) if instance else None),
            valid_day_type=data.get('valid_day_type',
                                    getattr(instance, 'valid_day_type', None) if instance else None),
            specific_date=data.get('specific_date',
                                   getattr(instance, 'specific_date', None) if instance else None),
            valid_start_time=data.get('valid_start_time',
                                      getattr(instance, 'valid_start_time', None) if instance else None),
            valid_end_time=data.get('valid_end_time',
                                    getattr(instance, 'valid_end_time', None) if instance else None),
        )
        if errors:
            raise serializers.ValidationError(errors)

        return data
