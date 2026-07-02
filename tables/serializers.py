from rest_framework import serializers

from tables.models import TableType, Table, PricingRule, AdditionalFee


class TableTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TableType
        fields = ['id', 'outlet', 'name', 'description', 'created_at']
        read_only_fields = ['created_at']


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ['id', 'outlet', 'name', 'table_type', 'status', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        outlet = data.get('outlet', getattr(self.instance, 'outlet', None))
        table_type = data.get('table_type', getattr(self.instance, 'table_type', None))
        if outlet and table_type and table_type.outlet_id != outlet.id:
            raise serializers.ValidationError({
                'table_type': 'Table type must belong to the same outlet.',
            })
        return data


class PricingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRule
        fields = [
            'id', 'outlet', 'table_type', 'name', 'day_type',
            'specific_date', 'start_time', 'end_time',
            'price_per_minute', 'priority', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        day_type = data.get('day_type', getattr(self.instance, 'day_type', None))
        specific_date = data.get('specific_date', getattr(self.instance, 'specific_date', None) if self.instance else None)
        price_per_minute = data.get('price_per_minute',
                                     getattr(self.instance, 'price_per_minute', None) if self.instance else None)
        outlet = data.get('outlet', getattr(self.instance, 'outlet', None) if self.instance else None)
        table_type = data.get('table_type', getattr(self.instance, 'table_type', None) if self.instance else None)

        errors = {}

        if day_type == PricingRule.DayType.SPECIFIC_DAY and not specific_date:
            errors['specific_date'] = 'Specific date is required when day type is "specific_day".'
        elif day_type != PricingRule.DayType.SPECIFIC_DAY and specific_date:
            errors['specific_date'] = 'Specific date should only be set when day type is "specific_day".'

        if price_per_minute is not None and price_per_minute <= 0:
            errors['price_per_minute'] = 'Price per minute must be greater than 0.'
        
        start_time = data.get('start_time', getattr(self.instance, 'start_time', None) if self.instance else None)
        end_time = data.get('end_time', getattr(self.instance, 'end_time', None) if self.instance else None)
        if start_time and end_time and start_time >= end_time:
            errors['end_time'] = 'End time must be after start time.'

        if outlet and table_type and table_type.outlet_id != outlet.id:
            errors['table_type'] = 'Table type must belong to the same outlet.'

        if errors:
            raise serializers.ValidationError(errors)

        return data


class AdditionalFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdditionalFee
        fields = [
            'id', 'outlet', 'name', 'type', 'value',
            'apply_to', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_value(self, value):
        if value <= 0:
            raise serializers.ValidationError('Value must be greater than 0.')
        return value