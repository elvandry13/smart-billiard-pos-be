from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, Tenant, Outlet, Role


class LoginSerializer(serializers.Serializer):
    """Serializer untuk login — menerima username & password, return JWT token."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer untuk profile user yang sedang login."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    outlet_name = serializers.CharField(source='outlet.name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone', 'role',
            'tenant_name', 'outlet_name', 'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'username', 'role', 'tenant_name', 'outlet_name', 'is_active', 'date_joined']


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer untuk membuat user baru (oleh Admin/Super Admin)."""
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'role', 'password', 'tenant', 'outlet']

    def validate_role(self, value):
        if not Role.objects.filter(name=value).exists():
            raise serializers.ValidationError(
                f"Role '{value}' tidak ditemukan. Pastikan Role sudah di-seed."
            )
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()  # User.save() syncs self.roles via M2M set
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password is not None:
            instance.set_password(password)
        instance = super().update(instance, validated_data)
        # instance.save() already called by super().update();
        # User.save() will sync self.roles if role changed.
        return instance


class UserListSerializer(serializers.ModelSerializer):
    """Serializer ringkas untuk list user."""
    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'is_active', 'date_joined']


class TenantSerializer(serializers.ModelSerializer):
    """Serializer untuk Tenant CRUD."""
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'code', 'is_active', 'created_at']
        read_only_fields = ['created_at']


class OutletSerializer(serializers.ModelSerializer):
    """Serializer untuk Outlet CRUD."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        model = Outlet
        fields = ['id', 'tenant', 'tenant_name', 'name', 'code', 'address', 'timezone', 'is_active', 'created_at']
        read_only_fields = ['created_at']


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer untuk ganti password."""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Password lama tidak sesuai.')
        return value
    
    def validate_new_password(self, value):
        validate_password(value, user=self.context['request'].user)
        return value
