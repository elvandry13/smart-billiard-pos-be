from rest_framework import serializers

from shifts.models import Shift


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = [
            'id', 'outlet', 'officer', 'opening_cash', 'closing_cash',
            'expected_cash', 'difference', 'status',
            'opened_at', 'closed_at', 'notes',
        ]
        read_only_fields = [
            'id', 'expected_cash', 'difference', 'opened_at', 'closed_at',
        ]
        extra_kwargs = {
            'outlet': {'required': False},
            'officer': {'required': False},
        }

    def validate(self, data):
        instance = self.instance
        # Resolve outlet/officer: data takes precedence, fallback to instance.
        officer = data.get('officer') or (instance and instance.officer)
        outlet = data.get('outlet') or (instance and instance.outlet)
        # Extract pk: bisa berupa objek model atau integer (id)
        officer_id = officer.pk if hasattr(officer, 'pk') else officer
        outlet_id = outlet.pk if hasattr(outlet, 'pk') else outlet

        # Default status: OPEN untuk create, existing status untuk update
        status = data.get('status')
        if status is None:
            status = instance.status if instance else Shift.Status.OPEN

        errors = Shift.validate_invariants(
            status=status,
            opening_cash=data.get('opening_cash', instance.opening_cash if instance else None),
            closing_cash=data.get('closing_cash', instance.closing_cash if instance else None),
            expected_cash=data.get('expected_cash', instance.expected_cash if instance else None),
            difference=data.get('difference', instance.difference if instance else None),
            officer_id=officer_id,
            outlet_id=outlet_id,
            exclude_pk=instance.pk if instance else None,
        )
        if errors:
            raise serializers.ValidationError(errors)
        return data
